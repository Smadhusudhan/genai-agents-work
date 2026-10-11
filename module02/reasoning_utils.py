"""Session 15 helpers - make a model think, and measure what the thinking costs.

Four ways to ask the same question:
  plain             "Give only the answer."                       1 call
  cot               "Think step by step, then answer."            1 call, more output tokens
  stepback          "First state the rules, then solve."          2 calls
  self-consistency  Ask cot several times, take the majority.     N calls

Every call goes through Lab.chat(), which records tokens (including the model's hidden thinking when it reports it),
seconds, and a running meter, waits politely when the provider says 429, and remembers answers on disk so that
re-running a notebook costs nothing. Takes any OpenAI-compatible client, like the earlier sessions."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from prompt_utils import ENTRY_RE, CheckResult, PromptSpec

# ---------------------------------------------------------------- prices and limits (INDICATIVE - verify before you quote them)
# USD per million tokens: (input, output). openai/gpt-oss-20b on Groq, from Groq's model page, checked October 2026.
PRICES = {"openai/gpt-oss-20b": (0.075, 0.30)}
GROQ_FREE_TPM = 8_000       # tokens per minute on the free plan for this model (Groq rate-limit page, October 2026)
GROQ_FREE_TPD = 200_000     # tokens per day on the free plan


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int):
    """Dollar cost of a call, or None when we have no price for the model (a local model costs electricity, not tokens)."""
    price = PRICES.get(model)
    if price is None:
        return None
    return (prompt_tokens * price[0] + completion_tokens * price[1]) / 1_000_000


def estimate_tokens(text: str) -> int:
    """About 4 characters per token for English prose. A rough count, used only when the provider does not report one."""
    return max(1, round(len(text) / 4)) if text else 0


# ---------------------------------------------------------------- reading a reply
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_FINAL_LINE_RE = re.compile(r"^[ \t>*_`#-]*FINAL[ \t]*:[ \t]*(.+?)[ \t*_`]*$", re.IGNORECASE | re.MULTILINE)


def split_think(text: str) -> tuple:
    """(visible text, thinking text). Some models put their thinking inside <think> tags in the reply itself."""
    thinking = "\n".join(m.strip() for m in _THINK_RE.findall(text or ""))
    return _THINK_RE.sub("", text or "").strip(), thinking


def extract_final(text: str):
    """The text after the LAST line that starts with FINAL: , or None. Taking the last one means a model that
    rehearses 'FINAL: 5' while thinking and then corrects itself is judged on its last word."""
    visible, _ = split_think(text)
    found = _FINAL_LINE_RE.findall(visible)
    return found[-1].strip() if found else None


_SYNONYMS = {"approved": "approve", "accept": "approve", "accepted": "approve",
             "declined": "decline", "reject": "decline", "rejected": "decline", "deny": "decline", "denied": "decline"}


def parse_answer(raw, kind: str, labels: tuple = ()):
    """Turn the text after FINAL: into a number (float) or a label (str). None when it cannot be read.
    Numbers: commas are dropped, so 'Rs 1,26,000' reads as 126000; '37.5%' reads as 37.5."""
    if raw is None:
        return None
    s = raw.strip().strip("*`_ ")
    if kind == "number":
        m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
        return float(m.group()) if m else None
    if kind == "label":
        for word in re.findall(r"[a-z]+", s.lower()):
            word = _SYNONYMS.get(word, word)
            if word in labels:
                return word
    return None


def is_correct(problem, value) -> bool:
    if value is None:
        return False
    if problem.kind == "number":
        return abs(value - problem.truth) <= problem.tol
    return value == problem.truth


def vote_key(problem, value):
    """Two numeric answers vote together when they round to the same number."""
    if value is None:
        return None
    if problem.kind == "number":
        return round(value) if problem.tol >= 0.5 else round(value, 1)
    return value


def majority_vote(keys: list) -> tuple:
    """(winning key, its votes, number of valid votes). None entries are ignored. A tie goes to the answer seen first,
    so the result is the same every time you run it."""
    valid = [k for k in keys if k is not None]
    if not valid:
        return None, 0, 0
    counts = Counter(valid)
    best = max(counts.values())
    winner = next(k for k in valid if counts[k] == best)
    return winner, best, len(valid)


# ---------------------------------------------------------------- an on-disk memory of answers, and a meter
DEFAULT_CACHE = Path.home() / ".genai_course" / "s15_cache.json"


class DiskCache:
    """Answers remembered on disk, so re-running a notebook costs nothing and gives the same numbers.
    Delete the file (or call clear()) to ask the model again. It lives in your home folder, not in a Git repo."""

    def __init__(self, path=None):
        self.path = Path(path) if path else DEFAULT_CACHE
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (OSError, ValueError):
            self.data = {}

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        self.data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data), encoding="utf-8")
        except OSError:
            pass          # a cache that cannot be saved is just a cache that does not help

    def clear(self):
        self.data = {}
        try:
            self.path.unlink()
        except OSError:
            pass


@dataclass
class Meter:
    """Running total of what this notebook has spent. Cached answers are free and are counted separately."""
    calls: int = 0
    cached: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    waited: float = 0.0

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, r: dict) -> None:
        if r.get("cached"):
            self.cached += 1
            return
        self.calls += 1
        self.prompt_tokens += r["prompt_tokens"]
        self.completion_tokens += r["completion_tokens"]

    def report(self, daily_budget: int = GROQ_FREE_TPD) -> str:
        share = 100 * self.tokens / daily_budget if daily_budget else 0
        wait = f", waited {self.waited:.0f}s for rate limits" if self.waited else ""
        return (f"spent so far: {self.calls} call{'s' if self.calls != 1 else ''} ({self.cached} answered from memory), {self.tokens:,} tokens "
                f"= about {share:.0f}% of a {daily_budget:,}-token free daily limit{wait}")


# ---------------------------------------------------------------- one call, measured
class DailyLimit(RuntimeError):
    """The provider asked us to wait far longer than a per-minute limit would."""


def rate_limit_wait(err, default: float = 20.0, cap: float = 70.0):
    """Seconds to wait before retrying when err is a 429 rate-limit error, otherwise None.
    A request to wait more than two minutes is a daily limit, not a per-minute one: raise DailyLimit."""
    if getattr(err, "status_code", None) != 429 and type(err).__name__ != "RateLimitError":
        return None
    headers = getattr(getattr(err, "response", None), "headers", None) or {}
    try:
        asked = float(headers.get("retry-after"))
    except (TypeError, ValueError, AttributeError):
        asked = default
    if asked > 120:
        raise DailyLimit(f"The provider says to wait about {asked / 60:.0f} minutes. That is a daily limit, not a per-minute one: "
                         "stop here, or carry on tomorrow. Answers already received are saved, so nothing is lost.") from err
    return min(max(asked, 1.0), cap) + 1.0


def _cache_key(model, messages, temperature, effort, max_tokens, sample) -> str:
    blob = json.dumps([model, messages, temperature, effort, max_tokens, sample], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def timed_chat(client, model: str, messages: list, *, temperature: float = 0.0, max_tokens: int = 2500, effort=None,
               sample: int = 0, cache=None, meter=None, retries: int = 5, sleep=time.sleep, clock=time.perf_counter) -> dict:
    """One call, measured. Returns text, thinking text, prompt/completion/reasoning tokens, seconds and whether it was cut off.

    reasoning_tokens is what the provider reports, else an estimate from the thinking text, else None
    (a model that does not think out loud has nothing to report). `seconds` is the time of the call that
    succeeded: time spent waiting for a rate limit is not counted in it.
    `sample` only separates repeated draws of the same question in the memory, so sample 0..4 are five different answers."""
    key = _cache_key(model, messages, temperature, effort, max_tokens, sample)
    if cache is not None:
        hit = cache.get(key)
        if hit:
            result = {**hit, "cached": True}
            if meter is not None:
                meter.add(result)
            return result

    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}
    for attempt in range(retries + 1):
        started = clock()
        try:
            r = client.chat.completions.create(**kwargs)
            seconds = clock() - started
            break
        except Exception as err:  # noqa: BLE001 - only rate limits are retried; everything else is re-raised
            wait = rate_limit_wait(err)
            if wait is None or attempt == retries:
                raise
            if meter is not None:
                meter.waited += wait
            print(f"   (rate limit: waiting {wait:.0f}s, then trying again)")
            sleep(wait)

    msg = r.choices[0].message
    content = getattr(msg, "content", None) or ""
    extra = getattr(msg, "model_extra", None) or {}
    thinking = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or extra.get("reasoning") or ""
    text, inline_thinking = split_think(content)
    thinking = thinking or inline_thinking

    usage = r.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "completion_tokens_details", None)
    reported = getattr(details, "reasoning_tokens", None) if details is not None else None
    if reported is not None:
        reasoning_tokens, source = reported, "reported"
    elif thinking:
        reasoning_tokens, source = estimate_tokens(thinking), "estimated"
    else:
        reasoning_tokens, source = None, None
    finish = getattr(r.choices[0], "finish_reason", None)

    result = {"text": text, "thinking": thinking, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
              "reasoning_tokens": reasoning_tokens, "reasoning_source": source, "seconds": seconds,
              "finish_reason": finish, "truncated": finish == "length", "cached": False}
    if cache is not None:
        cache.put(key, result)
    if meter is not None:
        meter.add(result)
    return result


_UNSET = object()


class Lab:
    """A client, a model and the settings every call shares. chat() is timed_chat() with those settings filled in."""

    def __init__(self, client, model: str, *, effort=None, max_tokens: int = 2500, cache=None, meter=None, sleep=time.sleep):
        self.client, self.model, self.effort, self.max_tokens = client, model, effort, max_tokens
        self.cache, self.meter, self.sleep = cache, meter if meter is not None else Meter(), sleep

    def chat(self, messages: list, *, temperature: float = 0.0, sample: int = 0, effort=_UNSET, max_tokens=None) -> dict:
        return timed_chat(self.client, self.model, messages, temperature=temperature, sample=sample,
                          effort=self.effort if effort is _UNSET else effort,
                          max_tokens=max_tokens or self.max_tokens, cache=self.cache, meter=self.meter, sleep=self.sleep)

    def variant(self, **changes) -> "Lab":
        """The same lab with something changed (another model, another effort). The cache and the meter are shared."""
        settings = dict(effort=self.effort, max_tokens=self.max_tokens, cache=self.cache, meter=self.meter, sleep=self.sleep)
        model = changes.pop("model", self.model)
        client = changes.pop("client", self.client)
        settings.update(changes)
        return Lab(client, model, **settings)


# ---------------------------------------------------------------- four ways to ask
SYSTEM = "You are a careful analyst. Apply the rules in the question exactly as written."


def _plain_instruction(p) -> str:
    return (f"Reply with only the final answer, on one line in the form FINAL: <answer>, where <answer> is {p.answer_format}. "
            "Do not show any working.")


def _cot_instruction(p) -> str:
    return ("Think step by step and show each calculation. Then end with one last line in the form FINAL: <answer>, "
            f"where <answer> is {p.answer_format}.")


def _messages(user: str) -> list:
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


@dataclass
class Attempt:
    problem_id: str
    strategy: str
    answer: object = None
    raw: object = None
    correct: bool = False
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: object = None      # None when the model never reported any thinking tokens
    seconds: float = 0.0
    cached_calls: int = 0
    truncated: bool = False
    text: str = ""
    notes: dict = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def _fold(self, r: dict) -> None:
        self.calls += 1
        self.prompt_tokens += r["prompt_tokens"]
        self.completion_tokens += r["completion_tokens"]
        self.seconds += r["seconds"]
        self.cached_calls += bool(r.get("cached"))
        self.truncated = self.truncated or bool(r.get("truncated"))
        if r.get("reasoning_tokens") is not None:
            self.reasoning_tokens = (self.reasoning_tokens or 0) + r["reasoning_tokens"]
        self.text = r["text"]


def _read(problem, attempt: Attempt, text: str) -> None:
    attempt.raw = extract_final(text)
    attempt.answer = parse_answer(attempt.raw, problem.kind, problem.labels)
    attempt.correct = is_correct(problem, attempt.answer)


def solve_plain(lab: Lab, problem) -> Attempt:
    a = Attempt(problem.id, "plain")
    r = lab.chat(_messages(f"{problem.text}\n\n{_plain_instruction(problem)}"))
    a._fold(r)
    _read(problem, a, r["text"])
    return a


def solve_cot(lab: Lab, problem) -> Attempt:
    a = Attempt(problem.id, "cot")
    r = lab.chat(_messages(f"{problem.text}\n\n{_cot_instruction(problem)}"))
    a._fold(r)
    _read(problem, a, r["text"])
    return a


STEPBACK_ASK = ("Do NOT solve this yet. Step back: list, in at most five short bullet points, the general rules, formulas "
                "or traps that apply to this kind of problem.")


def solve_stepback(lab: Lab, problem) -> Attempt:
    """Two calls. First the principles, in a call that is not allowed to solve; then the solving, with those principles in front."""
    a = Attempt(problem.id, "stepback")
    first = lab.chat(_messages(f"{problem.text}\n\n{STEPBACK_ASK}"))
    a._fold(first)
    principles = first["text"].strip()
    a.notes["principles"] = principles
    second = lab.chat(_messages(f"{problem.text}\n\nRules and formulas to apply:\n{principles}\n\n{_cot_instruction(problem)}"))
    a._fold(second)
    _read(problem, a, second["text"])
    return a


def solve_self_consistency(lab: Lab, problem, n: int = 5, temperature: float = 0.8) -> Attempt:
    """n independent step-by-step answers at a temperature above zero, then the most common answer wins."""
    a = Attempt(problem.id, f"vote x{n}")
    keys, values, correct_each = [], {}, 0
    for i in range(n):
        r = lab.chat(_messages(f"{problem.text}\n\n{_cot_instruction(problem)}"), temperature=temperature, sample=i)
        a._fold(r)
        value = parse_answer(extract_final(r["text"]), problem.kind, problem.labels)
        key = vote_key(problem, value)
        keys.append(key)
        values.setdefault(key, value)
        correct_each += is_correct(problem, value)
    winner, votes, valid = majority_vote(keys)
    a.answer = values.get(winner) if winner is not None else None
    a.raw = None if winner is None else str(a.answer)
    a.correct = is_correct(problem, a.answer)
    a.notes.update(votes={str(k): c for k, c in Counter(k for k in keys if k is not None).most_common()},
                   agreement=(votes / valid if valid else 0.0), valid_votes=valid, n=n,
                   single_sample_correct=correct_each)
    return a


STRATEGIES = {"plain": solve_plain, "cot": solve_cot, "stepback": solve_stepback, "vote": solve_self_consistency}


def run_strategy(lab: Lab, problem, strategy: str, **kwargs) -> Attempt:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; choose one of {list(STRATEGIES)}")
    return STRATEGIES[strategy](lab, problem, **kwargs)


# ---------------------------------------------------------------- reading the results
def _money_per_1000(model, attempt: Attempt) -> str:
    c = cost_usd(model, attempt.prompt_tokens, attempt.completion_tokens) if model else None
    return "-" if c is None else f"${c * 1000:,.2f}"


def comparison_table(attempts: list, model: str = None) -> str:
    """One row per (problem, strategy): answer, right or wrong, calls, tokens, thinking tokens, seconds, and the cost of 1,000 such questions."""
    head = f"{'problem':<22}{'strategy':<10}{'answer':>10}  {'result':<7}{'calls':>5}{'tokens':>8}{'thinking':>9}{'secs':>7}{'$/1000 q':>10}"
    lines = [head, "-" * len(head)]
    for a in attempts:
        answer = "none" if a.answer is None else (f"{a.answer:g}" if isinstance(a.answer, float) else str(a.answer))
        result = "CUT OFF" if a.truncated and a.answer is None else ("ok" if a.correct else "WRONG")
        think = "-" if a.reasoning_tokens is None else f"{a.reasoning_tokens:,}"
        lines.append(f"{a.problem_id[:21]:<22}{a.strategy:<10}{answer:>10}  {result:<7}{a.calls:>5}{a.tokens:>8,}{think:>9}"
                     f"{a.seconds:>7.1f}{_money_per_1000(model, a):>10}")
    return "\n".join(lines)


def strategy_summary(attempts: list, model: str = None) -> str:
    """One row per strategy: how many were right, and what an average question cost in tokens, seconds and dollars."""
    order = []
    for a in attempts:
        if a.strategy not in order:
            order.append(a.strategy)
    head = f"{'strategy':<10}{'right':>8}{'avg tokens':>12}{'avg secs':>10}{'avg $/1000 q':>14}"
    lines = [head, "-" * len(head)]
    for s in order:
        rows = [a for a in attempts if a.strategy == s]
        n = len(rows)
        costs = [cost_usd(model, a.prompt_tokens, a.completion_tokens) for a in rows] if model else [None]
        money = "-" if any(c is None for c in costs) else f"${sum(costs) / n * 1000:,.2f}"
        lines.append(f"{s:<10}{sum(a.correct for a in rows):>5}/{n:<2}{sum(a.tokens for a in rows) / n:>12,.0f}"
                     f"{sum(a.seconds for a in rows) / n:>10.1f}{money:>14}")
    return "\n".join(lines)


def pick_hardest(attempts: list, problems: list):
    """The problem that was answered wrongly most often; ties go to the one that used the most tokens."""
    def score(p):
        rows = [a for a in attempts if a.problem_id == p.id]
        return (sum(not a.correct for a in rows), sum(a.tokens for a in rows))
    return max(problems, key=score)


def pick_trouble(attempts: list, problems: list, k: int = 3) -> list:
    """The k problems answered wrongly most often (ties: the ones that used the most tokens), in their original order.
    When everything was right, that means the k that cost the most thinking."""
    def score(p):
        rows = [a for a in attempts if a.problem_id == p.id]
        return (sum(not a.correct for a in rows), sum(a.tokens for a in rows))
    chosen = sorted(problems, key=score, reverse=True)[:k]
    return [p for p in problems if p in chosen]


def case_table(results: dict, problems: list, strategies: tuple) -> str:
    """One row per case: the right answer, then what each strategy said and whether it was right.
    results maps (problem id, strategy) to an Attempt; a strategy not run for a case shows a dash."""
    head = f"{'case':<20}{'right answer':<14}" + "".join(f"{s:<18}" for s in strategies)
    lines = [head, "-" * len(head)]
    for p in problems:
        cells = []
        for st in strategies:
            a = results.get((p.id, st))
            if a is None:
                cells.append(f"{'-':<18}")
            else:
                said = "none" if a.answer is None else (f"{a.answer:g}" if isinstance(a.answer, float) else str(a.answer))
                cells.append(f"{said + (' ok' if a.correct else ' WRONG'):<18}")
        lines.append(f"{p.id[:19]:<20}{str(p.truth)[:13]:<14}" + "".join(cells))
    return "\n".join(lines)


def accuracy_markdown(results: dict, problems: list, strategies: tuple, model: str, today: str = None) -> str:
    """The accuracy table for the ten cases as a Markdown file you commit: one row per case, a totals row, and the cost."""
    import datetime
    today = today or datetime.date.today().isoformat()
    lines = [f"# Session 15 - loan eligibility, ten cases ({today})", "",
             f"Model: `{model}`. Strategies: {', '.join(strategies)}. A cell shows the answer, and ok or WRONG against the answer key.", "",
             "| Case | Right answer | " + " | ".join(strategies) + " |", "|---|---|" + "---|" * len(strategies)]
    for p in problems:
        cells = []
        for st in strategies:
            a = results.get((p.id, st))
            cells.append("-" if a is None else f"{'none' if a.answer is None else a.answer} {'ok' if a.correct else 'WRONG'}")
        lines.append(f"| {p.id} | {p.truth} | " + " | ".join(cells) + " |")
    totals, tokens = [], []
    for st in strategies:
        rows = [results[(p.id, st)] for p in problems if (p.id, st) in results]
        totals.append(f"{sum(a.correct for a in rows)}/{len(rows)}" if rows else "-")
        tokens.append(f"{sum(a.tokens for a in rows) / len(rows):,.0f}" if rows else "-")
    lines += [f"| **Right** | | " + " | ".join(totals) + " |", f"| **Average tokens per case** | | " + " | ".join(tokens) + " |", ""]
    return "\n".join(lines)


def save_accuracy_table(repo_path, text: str) -> Path:
    """Write the table to experiments/s15_accuracy_table.md in your work repo. Git keeps the history of earlier runs."""
    target = Path(repo_path) / "experiments" / "s15_accuracy_table.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def pick_local_chat_model(names: list):
    """First locally installed model that is a chat model (embedding models cannot answer questions)."""
    for n in names:
        if "embed" not in n.lower():
            return n
    return None


# ---------------------------------------------------------------- reasoning behind a curtain
_SCRATCH_RE = re.compile(r"<scratchpad>(.*?)</scratchpad>", re.DOTALL | re.IGNORECASE)
_FINAL_TAG_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)


def split_scratchpad(text: str) -> tuple:
    """(scratchpad, final). The scratchpad is private working; only `final` may be shown, checked or stored as the answer.
    Tolerates a missing <final> tag (uses whatever follows the scratchpad) and a reply with no tags at all."""
    text = text or ""
    scratch = "\n".join(m.strip() for m in _SCRATCH_RE.findall(text))
    finals = _FINAL_TAG_RE.findall(text)
    if finals:
        return scratch, finals[-1].strip()
    if "<final>" in text.lower():                      # opened but never closed: the reply was cut off
        return scratch, re.split(r"<final>", text, flags=re.IGNORECASE)[-1].strip()
    return scratch, _SCRATCH_RE.sub("", text).strip()


def with_scratchpad(spec: PromptSpec) -> PromptSpec:
    """A copy of a spec that asks for private working first and the real reply inside <final>. The original is not changed."""
    rule = "Do your reasoning inside <scratchpad>...</scratchpad> first. The scratchpad is private working and is never shown to anyone."
    shape = ("A <scratchpad> block, then <final>...</final> containing exactly this: "
             + (spec.output_format.strip() or "the reply"))
    return dataclasses.replace(spec, constraints=[*spec.constraints, rule], output_format=shape)


def scratch_leaks(scratch: str, secret_terms: list) -> list:
    """Which confidential terms the private working mentions. It is why a scratchpad is never shown or logged where customers can read it."""
    low = scratch.lower()
    return [t for t in secret_terms if t.lower() in low]


SECRETS = {"T2-sms-declined": ["612", "650", "risk score", "cutoff"]}


def run_spec(lab: Lab, task, spec: PromptSpec, *, hidden_reasoning: bool = False, temperature: float = 0.0, sample: int = 0) -> dict:
    """Run a Session 14 task with a spec; with hidden_reasoning the acceptance checks run on the <final> part only."""
    from prompt_tasks import run_checks
    used = with_scratchpad(spec) if hidden_reasoning else spec
    r = lab.chat(used.to_messages(task.user_input), temperature=temperature, sample=sample)
    scratch, final = split_scratchpad(r["text"]) if hidden_reasoning else ("", r["text"].strip())
    results = run_checks(task, final)
    return {"final": final, "scratch": scratch, "results": results, "passed": sum(x.passed for x in results),
            "of": len(results), "tokens": r["prompt_tokens"] + r["completion_tokens"], "seconds": r["seconds"],
            "leaks": scratch_leaks(scratch, SECRETS.get(task.id, [])), "call": r}


def pass_rate(lab: Lab, task, spec: PromptSpec, *, hidden_reasoning: bool = False, runs: int = 2, temperature: float = 0.7) -> dict:
    """Run the same spec several times at a temperature above zero and report how often every check passed."""
    rows = [run_spec(lab, task, spec, hidden_reasoning=hidden_reasoning, temperature=temperature, sample=i) for i in range(runs)]
    return {"runs": runs, "all_passed": sum(r["passed"] == r["of"] for r in rows),
            "avg_checks": sum(r["passed"] for r in rows) / runs, "of": rows[0]["of"],
            "avg_tokens": sum(r["tokens"] for r in rows) / runs, "avg_seconds": sum(r["seconds"] for r in rows) / runs,
            "any_leak": any(r["leaks"] for r in rows), "rows": rows}


def verdict(v1: dict, v2: dict) -> str:
    """Plain-English comparison of two pass_rate() results, with the price of the change."""
    ratio = (v2["avg_tokens"] / v1["avg_tokens"]) if v1["avg_tokens"] else float("inf")
    if v2["avg_checks"] > v1["avg_checks"]:
        better = f"v2 passes more checks ({v2['avg_checks']:.1f} vs {v1['avg_checks']:.1f} of {v1['of']})"
    elif v2["avg_checks"] < v1["avg_checks"]:
        better = f"v2 passes FEWER checks ({v2['avg_checks']:.1f} vs {v1['avg_checks']:.1f} of {v1['of']}): keep v1"
    else:
        better = f"v1 and v2 pass the same number of checks ({v1['avg_checks']:.1f} of {v1['of']}): no reason to switch"
    return f"{better}, at {ratio:.1f}x the tokens per call."


# ---------------------------------------------------------------- the prompt library, version 2
def entries_in(library_text: str) -> list:
    """[(task id, version)] for every entry in a library file's text."""
    return [(m.group(1), int(m.group(2))) for m in ENTRY_RE.finditer(library_text)]


def tasks_with_version(library_text: str, version: int = 2) -> set:
    return {t for t, v in entries_in(library_text) if v == version}


def check_library_v2(repo_path, need: int = 2) -> list:
    """Plain-English checks that your library has version 2 entries and that version 1 is still there."""
    library = Path(repo_path) / "prompts" / "library.md"
    if not library.exists():
        return [CheckResult("prompts/library.md exists in your work repo", False, "run the Session 14 notebook cells first")]
    text = library.read_text(encoding="utf-8", errors="replace")
    pairs = entries_in(text)
    v2 = tasks_with_version(text, 2)
    out = [CheckResult("library still has your version 1 entries", any(v == 1 for _, v in pairs),
                       "" if any(v == 1 for _, v in pairs) else "a v1 entry is missing: never overwrite, always add")]
    out.append(CheckResult(f"version 2 entries for at least {need} tasks", len(v2) >= need,
                           f"found {len(v2)}: {sorted(v2)}" if v2 else "none yet: set SAVE_V2 = True in section 9 and run that cell once"))
    missing_v1 = sorted(t for t in v2 if (t, 1) not in pairs)
    out.append(CheckResult("every v2 task still has its v1 entry (history kept)", not missing_v1,
                           f"no v1 for {missing_v1}" if missing_v1 else ""))
    return out


def check_accuracy_table(repo_path, cases: int = 10) -> list:
    """Plain-English check that the accuracy table for the ten cases is in your work repo."""
    table = Path(repo_path) / "experiments" / "s15_accuracy_table.md"
    if not table.exists():
        return [CheckResult("experiments/s15_accuracy_table.md exists", False, "set SAVE_V2 = True in section 11 and run that cell once")]
    rows = [ln for ln in table.read_text(encoding="utf-8", errors="replace").splitlines() if re.match(r"^\| L\d\d-", ln)]
    return [CheckResult("experiments/s15_accuracy_table.md exists", True),
            CheckResult(f"the table has all {cases} loan cases", len(rows) >= cases, f"found {len(rows)} case rows")]


def check_s15_work(repo_path) -> list:
    """Everything Session 15 asks you to commit: library v2 entries, v1 history kept, and the ten-case accuracy table."""
    return check_library_v2(repo_path) + check_accuracy_table(repo_path)
