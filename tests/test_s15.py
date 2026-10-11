"""Session 15 checkpoint. Run with:  uv run pytest tests/test_s15.py
Offline except the live tests at the bottom, which skip without a key (or without Ollama). The offline tests use a scripted
stand-in for the model, so they cost nothing, never touch the network, and give the same result every time."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv

load_dotenv(override=True)   # read .env BEFORE the skip checks below, so a key stored only in .env is seen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module02"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module01"))   # providers_utils, for the live tests
from prompt_tasks import TASK1, TASK2, TASK3, classify_spec  # noqa: E402
from prompt_utils import PromptSpec, init_work_repo, save_to_library  # noqa: E402
from check_s15_submissions import check_repo_s15  # noqa: E402
from reasoning_tasks import (DEMO, LOAN_CASES, OTHER, PROBLEMS, R1, R2, R4, S1, S2, S3, STRETCH, classify_cot_spec,  # noqa: E402
                             problem_card, score_classifier_lab)
from reasoning_utils import (Attempt, DailyLimit, DiskCache, Lab, Meter, accuracy_markdown, case_table,  # noqa: E402
                             check_accuracy_table, check_library_v2, check_s15_work, comparison_table,
                             cost_usd, estimate_tokens, extract_final, is_correct, majority_vote, pass_rate,
                             parse_answer, pick_hardest, pick_local_chat_model, pick_trouble, rate_limit_wait,
                             run_spec, run_strategy, save_accuracy_table,
                             scratch_leaks, solve_cot, solve_plain, solve_self_consistency, solve_stepback,
                             split_scratchpad, split_think, strategy_summary, tasks_with_version, timed_chat, verdict,
                             vote_key, with_scratchpad)


L05 = LOAN_CASES[4]       # the 'age at the end of the term' case: two rules pass, the third fails quietly


# ---------------------------------------------------------------- a scripted stand-in for the model
def reply(text, prompt=100, completion=50, reasoning=None, thinking=None, finish="stop"):
    details = SimpleNamespace(reasoning_tokens=reasoning) if reasoning is not None else None
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, completion_tokens_details=details)
    msg = SimpleNamespace(content=text, reasoning=thinking)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)], usage=usage)


class FakeClient:
    """handler(kwargs, call_number) returns a reply (or an Exception to raise). Every call is kept in .calls."""

    def __init__(self, handler):
        self.handler, self.calls = handler, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.handler(kwargs, len(self.calls))
        if isinstance(out, Exception):
            raise out
        return out


class RateLimitError(Exception):
    def __init__(self, retry_after=None):
        super().__init__("429")
        self.status_code = 429
        self.response = SimpleNamespace(headers={"retry-after": str(retry_after)} if retry_after is not None else {})


def constant(text, **kw):
    return FakeClient(lambda kwargs, n: reply(text, **kw))


def lab_for(client, **kw):
    return Lab(client, "openai/gpt-oss-20b", sleep=lambda s: None, **kw)


def user_text(kwargs):
    return kwargs["messages"][-1]["content"]


# ---------------------------------------------------------------- reading a reply
def test_extract_final_takes_the_last_final_line_and_ignores_decoration():
    assert extract_final("working...\nFINAL: 5\nhmm, wait\n**FINAL: 7**") == "7"
    assert extract_final("> FINAL : Rs 1,26,000") == "Rs 1,26,000"
    assert extract_final("no answer line here") is None
    assert extract_final("<think>FINAL: 99</think>\nFINAL: 42") == "42"


def test_split_think_separates_inline_thinking():
    visible, thinking = split_think("<think>step one</think>The answer.")
    assert visible == "The answer." and thinking == "step one"


def test_parse_answer_numbers_and_labels():
    assert parse_answer("Rs 1,26,000", "number") == 126000
    assert parse_answer("37.5%", "number") == 37.5
    assert parse_answer("3.6 mL", "number") == 3.6
    assert parse_answer("**5779**", "number") == 5779
    assert parse_answer("about twelve", "number") is None
    assert parse_answer("Declined", "label", ("approve", "decline")) == "decline"
    assert parse_answer("rejected: age rule", "label", ("approve", "decline")) == "decline"
    assert parse_answer("maybe", "label", ("approve", "decline")) is None
    assert parse_answer(None, "number") is None


# ---------------------------------------------------------------- the problems: truths are worked by hand here, again
def test_ground_truths_match_hand_worked_numbers():
    assert round(DEMO.truth, 2) == 1340.0                 # 2000 x 0.8 x 0.9 - 100
    assert round(R1.truth, 2) == 5778.99                  # 5997 x 0.85 = 5097.45; -200 = 4897.45; x 1.18; shipping free
    assert R2.truth == 126000                             # 240000 x 5/8 = 150000; -10000; x 0.9
    assert round(R4.truth, 2) == 37.5                     # 0.012 / 0.032
    assert round(S1.truth, 2) == 3.6                      # 270 mg a day, 90 mg a dose, 3.6 mL
    assert round(S2.truth, 2) == 253.33                   # 19 days x 400 / 30
    assert round(S3.truth, 1) == 16607.2                  # standard reducing-balance EMI


def test_the_ten_loan_cases_have_the_right_decisions_worked_by_hand():
    expected = {"L01-clean": "approve",            # 29.2%, 760, age at end 37
                "L02-ratio-narrow": "decline",     # 33,000 / 80,000 = 41.25%
                "L03-score-699": "decline",        # score 699
                "L04-boundaries": "approve",       # 40,000 / 100,000 = exactly 40%, score exactly 700
                "L05-age-at-end": "decline",       # 54 + 7 = 61
                "L06-age-60": "approve",           # 50 + 10 = 60
                "L07-existing-emis": "decline",    # (18,000 + 8,000) / 60,000 = 43.3%
                "L08-two-fail": "decline",         # score 640 and age at end 63
                "L09-large-numbers": "approve",    # 95,000 / 250,000 = 38%, 705, 53
                "L10-months": "approve"}           # 48 months = 4 years: 56 + 4 = 60
    assert {c.id: c.truth for c in LOAN_CASES} == expected
    assert sum(c.truth == "approve" for c in LOAN_CASES) == 5          # balanced: a model that always says one word scores 5/10


def test_each_loan_case_prompt_carries_the_policy_and_its_own_applicant():
    for c in LOAN_CASES:
        assert "ALL three hold" in c.text and "What is the decision?" in c.text and c.trap
    assert "age 54" in L05.text and "Rs 90,000" in L05.text and "Rs 21,500" in L05.text
    assert "48 months" in LOAN_CASES[9].text
    assert "Rs 1,20,000" in LOAN_CASES[0].text and "Rs 2,50,000" in LOAN_CASES[8].text     # Indian digit grouping, as a bank writes it


def test_the_tempting_wrong_answers_are_rejected():
    assert not is_correct(R2, 125000)        # co-pay applied before the deductible
    assert not is_correct(L05, "approve")    # forgot the age rule
    assert not is_correct(R4, 60)            # machine A's share instead of Bayes
    assert not is_correct(S2, 240)           # 18 days instead of 19
    assert not is_correct(R1, 5778.99 + 99)  # charged shipping that should have been free
    assert not is_correct(R1, None)


def test_tolerances_accept_rounding_but_not_slips():
    assert is_correct(R1, 5779) and is_correct(R1, 5778) and not is_correct(R1, 5781)
    assert is_correct(R4, 37.5) and is_correct(R4, 37.55) and not is_correct(R4, 37.7)
    assert is_correct(S3, 16607) and is_correct(S3, 16608) and not is_correct(S3, 16620)
    assert is_correct(L05, "decline") and not is_correct(L05, None)


def test_the_problem_set_is_well_formed():
    assert [c.id[:3] for c in LOAN_CASES] == [f"L{i:02d}" for i in range(1, 11)]
    assert [p.id for p in OTHER] == ["R1-retail-order", "R2-insurance-claim", "R4-defect-source"]
    assert len(STRETCH) == 3 and len({p.id for p in PROBLEMS}) == len(PROBLEMS) == 16
    for p in PROBLEMS + [DEMO]:
        assert p.kind in ("number", "label") and p.trap and p.answer_format and p.text
        assert (p.kind == "label") == bool(p.labels)
    assert "Rs 2,000" in problem_card(DEMO)
    domains = {p.domain for p in PROBLEMS}
    assert {"Retail", "Insurance", "BFS", "Manufacturing", "Healthcare", "Telecom"} <= domains


# ---------------------------------------------------------------- voting
def test_majority_vote_winner_ties_and_empties():
    assert majority_vote([5, 7, 5, None, 5]) == (5, 3, 4)
    assert majority_vote([7, 5, 7, 5]) == (7, 2, 4)            # a tie goes to the answer seen first
    assert majority_vote([None, None]) == (None, 0, 0)
    assert majority_vote([]) == (None, 0, 0)


def test_vote_key_groups_numbers_that_round_together():
    assert vote_key(R1, 5778.99) == vote_key(R1, 5779.2) == 5779
    assert vote_key(R4, 37.52) == vote_key(R4, 37.54) == 37.5
    assert vote_key(L05, "decline") == "decline" and vote_key(R1, None) is None


# ---------------------------------------------------------------- one measured call
def test_timed_chat_reports_tokens_thinking_and_seconds():
    client = constant("FINAL: 5", prompt=120, completion=300, reasoning=250)
    ticks = iter([10.0, 12.5])
    r = timed_chat(client, "m", [{"role": "user", "content": "q"}], clock=lambda: next(ticks))
    assert (r["prompt_tokens"], r["completion_tokens"], r["reasoning_tokens"], r["reasoning_source"]) == (120, 300, 250, "reported")
    assert r["seconds"] == 2.5 and not r["truncated"] and not r["cached"]


def test_thinking_tokens_are_estimated_when_only_the_text_is_reported():
    client = constant("FINAL: 5", completion=300, thinking="x" * 400)
    r = timed_chat(client, "m", [{"role": "user", "content": "q"}])
    assert r["reasoning_tokens"] == 100 and r["reasoning_source"] == "estimated"
    assert estimate_tokens("x" * 400) == 100 and estimate_tokens("") == 0


def test_a_model_that_does_not_think_aloud_reports_none():
    r = timed_chat(constant("FINAL: 5"), "m", [{"role": "user", "content": "q"}])
    assert r["reasoning_tokens"] is None and r["reasoning_source"] is None


def test_inline_think_tags_are_removed_from_the_answer_and_counted_as_thinking():
    r = timed_chat(constant("<think>" + "y" * 80 + "</think>FINAL: 9"), "m", [{"role": "user", "content": "q"}])
    assert r["text"] == "FINAL: 9" and r["thinking"] == "y" * 80 and r["reasoning_tokens"] == 20


def test_a_reply_cut_off_by_max_tokens_is_flagged():
    r = timed_chat(constant("", finish="length"), "m", [{"role": "user", "content": "q"}])
    assert r["truncated"] is True and r["text"] == ""


def test_effort_goes_in_extra_body_only_when_asked_for():
    client = constant("FINAL: 1")
    timed_chat(client, "m", [{"role": "user", "content": "q"}])
    timed_chat(client, "m", [{"role": "user", "content": "q"}], effort="low", temperature=0.7)
    assert "extra_body" not in client.calls[0]
    assert client.calls[1]["extra_body"] == {"reasoning_effort": "low"} and client.calls[1]["temperature"] == 0.7


# ---------------------------------------------------------------- memory and meter
def test_a_repeated_question_is_answered_from_memory_for_free(tmp_path):
    client, meter = constant("FINAL: 5", prompt=100, completion=200), Meter()
    cache = DiskCache(tmp_path / "c.json")
    a = timed_chat(client, "m", [{"role": "user", "content": "q"}], cache=cache, meter=meter)
    b = timed_chat(client, "m", [{"role": "user", "content": "q"}], cache=cache, meter=meter)
    assert len(client.calls) == 1 and not a["cached"] and b["cached"] and b["text"] == a["text"]
    assert (meter.calls, meter.cached, meter.tokens) == (1, 1, 300)


def test_different_sample_numbers_are_different_questions(tmp_path):
    client, cache = constant("FINAL: 5"), DiskCache(tmp_path / "c.json")
    for sample in (0, 1, 2):
        timed_chat(client, "m", [{"role": "user", "content": "q"}], cache=cache, sample=sample)
    assert len(client.calls) == 3


def test_memory_survives_a_restart_and_a_broken_file_is_ignored(tmp_path):
    path = tmp_path / "c.json"
    client = constant("FINAL: 5")
    timed_chat(client, "m", [{"role": "user", "content": "q"}], cache=DiskCache(path))
    timed_chat(client, "m", [{"role": "user", "content": "q"}], cache=DiskCache(path))
    assert len(client.calls) == 1
    path.write_text("{not json", encoding="utf-8")
    assert DiskCache(path).data == {}
    cache = DiskCache(path)
    cache.put("k", {"a": 1})
    cache.clear()
    assert not path.exists() and cache.data == {}


def test_meter_report_says_how_much_of_the_daily_limit_is_used():
    m = Meter()
    m.add({"prompt_tokens": 10_000, "completion_tokens": 10_000})
    m.add({"cached": True, "prompt_tokens": 5, "completion_tokens": 5})
    text = m.report(daily_budget=200_000)
    assert "1 call (1 answered from memory)" in text and "20,000 tokens" in text and "10%" in text


# ---------------------------------------------------------------- rate limits
def test_a_rate_limit_is_waited_out_and_the_wait_is_not_counted_as_call_time():
    waits, ticks = [], iter([0.0, 5.0, 7.0])   # attempt 1 starts at 0 and fails; attempt 2 runs from 5 to 7
    client = FakeClient(lambda kw, n: RateLimitError(retry_after=12) if n == 1 else reply("FINAL: 3"))
    meter = Meter()
    r = timed_chat(client, "m", [{"role": "user", "content": "q"}], sleep=waits.append, clock=lambda: next(ticks), meter=meter)
    assert waits == [13.0] and r["seconds"] == 2.0 and meter.waited == 13.0 and len(client.calls) == 2


def test_a_daily_limit_stops_straight_away_without_retrying():
    client = FakeClient(lambda kw, n: RateLimitError(retry_after=7200))
    with pytest.raises(DailyLimit) as e:
        timed_chat(client, "m", [{"role": "user", "content": "q"}], sleep=lambda s: None)
    assert "daily limit" in str(e.value) and len(client.calls) == 1


def test_other_errors_are_not_retried_and_retries_run_out():
    boom = FakeClient(lambda kw, n: ValueError("bad request"))
    with pytest.raises(ValueError):
        timed_chat(boom, "m", [{"role": "user", "content": "q"}], sleep=lambda s: None)
    assert len(boom.calls) == 1
    always = FakeClient(lambda kw, n: RateLimitError(retry_after=1))
    with pytest.raises(RateLimitError):
        timed_chat(always, "m", [{"role": "user", "content": "q"}], retries=2, sleep=lambda s: None)
    assert len(always.calls) == 3
    assert rate_limit_wait(ValueError("x")) is None
    assert rate_limit_wait(RateLimitError()) == 21.0          # no header: default 20 s plus one


# ---------------------------------------------------------------- the four strategies
def solver(answers, **kw):
    """A fake model that answers each call in turn: step-back's first call gets 'principles', others get a FINAL line."""
    def handler(kwargs, n):
        text = user_text(kwargs)
        if "Do NOT solve this yet" in text:
            return reply("- rule one\n- rule two", **kw)
        return reply(f"working...\nFINAL: {answers[min(n - 1, len(answers) - 1)]}", **kw)
    return FakeClient(handler)


def test_plain_asks_for_no_working_and_makes_one_call():
    client = solver(["126000"], prompt=200, completion=80, reasoning=60)
    a = solve_plain(lab_for(client), R2)
    assert len(client.calls) == 1 and "Do not show any working" in user_text(client.calls[0])
    assert a.correct and a.answer == 126000 and a.calls == 1 and a.tokens == 280 and a.reasoning_tokens == 60


def test_cot_asks_for_steps_and_makes_one_call():
    client = solver(["125000"])
    a = solve_cot(lab_for(client), R2)
    assert len(client.calls) == 1 and "Think step by step" in user_text(client.calls[0])
    assert not a.correct and a.answer == 125000 and a.raw == "125000"


def test_stepback_makes_two_calls_and_carries_the_rules_into_the_second():
    client = solver(["37.5"], prompt=100, completion=100, reasoning=40)
    a = solve_stepback(lab_for(client), R4)
    assert len(client.calls) == 2 and a.calls == 2 and a.tokens == 400 and a.reasoning_tokens == 80
    assert "Do NOT solve this yet" in user_text(client.calls[0])
    assert "- rule one" in user_text(client.calls[1]) and "Think step by step" in user_text(client.calls[1])
    assert a.correct and a.notes["principles"].startswith("- rule one")


def test_self_consistency_takes_the_majority_and_sums_the_cost():
    answers = ["125000", "126000", "126000", "125000", "126000"]
    client = solver(answers, prompt=100, completion=100)
    a = solve_self_consistency(lab_for(client), R2, n=5, temperature=0.8)
    assert len(client.calls) == 5 and a.calls == 5 and a.tokens == 1000
    assert a.correct and a.answer == 126000
    assert a.notes["votes"] == {"126000": 3, "125000": 2} and a.notes["agreement"] == 0.6 and a.notes["single_sample_correct"] == 3
    assert {c["temperature"] for c in client.calls} == {0.8}


def test_self_consistency_can_vote_for_the_wrong_answer():
    client = solver(["125000", "125000", "126000"])
    a = solve_self_consistency(lab_for(client), R2, n=3)
    assert not a.correct and a.answer == 125000


def test_unreadable_replies_never_crash_and_count_as_wrong():
    client = constant("I think it is fine.")
    a = solve_cot(lab_for(client), R1)
    assert a.answer is None and not a.correct
    cut = constant("", finish="length")
    assert solve_plain(lab_for(cut), R1).truncated


def test_labels_are_voted_and_read_like_numbers():
    client = solver(["Decline", "decline", "approve"])
    a = solve_self_consistency(lab_for(client), L05, n=3)
    assert a.answer == "decline" and a.correct


def test_run_strategy_dispatches_and_rejects_unknown_names():
    client = solver(["5779"])
    assert run_strategy(lab_for(client), R1, "cot").correct
    assert run_strategy(lab_for(client), R1, "vote", n=2).calls == 2
    with pytest.raises(ValueError):
        run_strategy(lab_for(client), R1, "magic")


def test_a_variant_lab_changes_one_setting_and_shares_the_meter():
    client = solver(["5779"])
    lab = lab_for(client, effort="medium")
    low = lab.variant(effort="low")
    solve_plain(low, R1)
    assert client.calls[0]["extra_body"] == {"reasoning_effort": "low"} and low.meter is lab.meter and lab.meter.calls == 1
    lab.chat([{"role": "user", "content": "q"}], effort=None)
    assert "extra_body" not in client.calls[1]


# ---------------------------------------------------------------- reading the numbers
def test_cost_uses_the_published_prices():
    assert cost_usd("openai/gpt-oss-20b", 1_000_000, 0) == pytest.approx(0.075)
    assert cost_usd("openai/gpt-oss-20b", 0, 1_000_000) == pytest.approx(0.30)
    assert cost_usd("some-local-model", 1000, 1000) is None


def make_attempt(pid, strategy, correct, tokens, seconds, prompt=100):
    return Attempt(pid, strategy, answer=1.0, correct=correct, calls=1, prompt_tokens=prompt,
                   completion_tokens=tokens - prompt, seconds=seconds)


def test_tables_show_every_row_and_a_summary_per_strategy():
    rows = [make_attempt("R1-retail-order", "plain", True, 600, 1.0), make_attempt("R1-retail-order", "cot", True, 1200, 2.0),
            make_attempt("R2-insurance-claim", "plain", False, 800, 1.5), make_attempt("R2-insurance-claim", "cot", True, 1400, 2.5)]
    table = comparison_table(rows, "openai/gpt-oss-20b")
    assert table.count("\n") == 5 and "WRONG" in table and "ok" in table and "$/1000 q" in table
    summary = strategy_summary(rows, "openai/gpt-oss-20b")
    lines = summary.splitlines()
    assert lines[2].startswith("plain") and "1/2" in lines[2] and lines[3].startswith("cot") and "2/2" in lines[3]
    assert "700" in lines[2] and "1,300" in lines[3]
    assert strategy_summary(rows).splitlines()[2].rstrip().endswith("-")        # no price known: a dash, not a made-up number


def test_a_cut_off_answer_is_labelled_as_such():
    a = Attempt("R1-retail-order", "plain", truncated=True)
    assert "CUT OFF" in comparison_table([a])


POOL = [R1, R2, L05, R4]


def test_pick_hardest_prefers_wrong_answers_then_tokens():
    rows = [make_attempt(R1.id, "plain", True, 500, 1), make_attempt(R2.id, "plain", False, 500, 1),
            make_attempt(L05.id, "plain", False, 900, 1), make_attempt(R4.id, "plain", True, 5000, 1)]
    assert pick_hardest(rows, POOL) is L05
    assert pick_hardest([make_attempt(R1.id, "plain", True, 500, 1), make_attempt(R4.id, "plain", True, 900, 1)], [R1, R4]) is R4


def test_pick_trouble_returns_the_k_worst_cases_in_their_original_order():
    rows = [make_attempt(R1.id, "plain", True, 500, 1), make_attempt(R2.id, "plain", False, 500, 1),
            make_attempt(L05.id, "cot", False, 900, 1), make_attempt(R4.id, "plain", True, 5000, 1)]
    assert pick_trouble(rows, POOL, 2) == [R2, L05]
    assert pick_trouble([], POOL, 2) == POOL[:2]                  # no results yet: the first two, never an error
    allright = [make_attempt(p.id, "plain", True, t, 1) for p, t in zip(POOL, (100, 400, 300, 200))]
    assert pick_trouble(allright, POOL, 2) == [R2, L05]         # nothing wrong: the two that cost the most tokens


def test_case_table_shows_each_strategy_per_case_with_a_dash_for_what_was_not_run():
    ok = Attempt(L05.id, "plain", answer="decline", correct=True)
    bad = Attempt(L05.id, "cot", answer="approve", correct=False)
    table = case_table({(L05.id, "plain"): ok, (L05.id, "cot"): bad}, [L05, LOAN_CASES[0]], ("plain", "cot", "vote x5"))
    lines = table.splitlines()
    assert "decline ok" in lines[2] and "approve WRONG" in lines[2] and lines[2].split()[-1] == "-"
    assert lines[3].startswith("L01-clean") and lines[3].count("-") >= 3


def test_accuracy_markdown_has_a_row_per_case_and_totals(tmp_path):
    results = {}
    for i, c in enumerate(LOAN_CASES):
        results[(c.id, "plain")] = Attempt(c.id, "plain", answer=c.truth if i < 7 else "x", correct=i < 7, prompt_tokens=100, completion_tokens=100)
        results[(c.id, "cot")] = Attempt(c.id, "cot", answer=c.truth, correct=True, prompt_tokens=100, completion_tokens=300)
    md = accuracy_markdown(results, LOAN_CASES, ("plain", "cot"), "openai/gpt-oss-20b", today="2026-10-07")
    assert md.count("\n| L") == 10 and "| **Right** | | 7/10 | 10/10 |" in md and "| 200 | 400 |" in md and "2026-10-07" in md
    path = save_accuracy_table(tmp_path, md)
    assert path == tmp_path / "experiments" / "s15_accuracy_table.md" and path.read_text(encoding="utf-8") == md
    assert all(r.passed for r in check_accuracy_table(tmp_path))
    path.write_text("| L01-clean | approve |\n", encoding="utf-8")
    assert not check_accuracy_table(tmp_path)[1].passed
    assert not check_accuracy_table(tmp_path / "nowhere")[0].passed


def test_pick_local_chat_model_skips_embedding_models():
    assert pick_local_chat_model(["nomic-embed-text:latest", "llama3.2:3b"]) == "llama3.2:3b"
    assert pick_local_chat_model(["nomic-embed-text"]) is None and pick_local_chat_model([]) is None


# ---------------------------------------------------------------- reasoning behind a curtain
def test_split_scratchpad_in_every_shape_a_model_might_answer():
    s, f = split_scratchpad("<scratchpad>score is 612</scratchpad>\n<final>Hi Rohan.</final>")
    assert (s, f) == ("score is 612", "Hi Rohan.")
    assert split_scratchpad("<scratchpad>a</scratchpad>The reply") == ("a", "The reply")
    assert split_scratchpad("<scratchpad>a</scratchpad><final>cut off mid") == ("a", "cut off mid")
    assert split_scratchpad("just an answer") == ("", "just an answer")
    assert split_scratchpad("") == ("", "")


def test_with_scratchpad_adds_the_curtain_without_touching_the_original():
    original = TASK2.reference
    before = (list(original.constraints), original.output_format)
    v2 = with_scratchpad(original)
    assert (list(original.constraints), original.output_format) == before
    assert len(v2.constraints) == len(before[0]) + 1 and "<scratchpad>" in v2.constraints[-1]
    assert "<final>" in v2.output_format and before[1] in v2.output_format
    assert "<final>" in v2.to_messages("x")[0]["content"]       # standing rules live in the system message


def test_scratch_leaks_finds_confidential_terms():
    assert scratch_leaks("internal risk score 612 is below cutoff", ["612", "650", "risk score", "cutoff"]) == ["612", "risk score", "cutoff"]
    assert scratch_leaks("all clean", ["612"]) == []


GOOD_SMS = "Hi Rohan, your loan application APP-20931 was not approved. You can apply again after 90 days. Questions? Call 1800-555-0199."


def test_checks_run_on_the_final_part_only_and_a_leaky_scratchpad_is_flagged():
    client = constant(f"<scratchpad>score 612 is below the cutoff 650, do not say so</scratchpad><final>{GOOD_SMS}</final>")
    out = run_spec(lab_for(client), TASK2, TASK2.reference, hidden_reasoning=True)
    assert out["passed"] == out["of"] == 6 and out["final"] == GOOD_SMS
    assert out["leaks"] == ["612", "650", "cutoff"]                 # the scratchpad knows the secret ...
    from prompt_tasks import run_checks
    whole = run_checks(TASK2, client.calls and "<scratchpad>score 612 ...</scratchpad>" + GOOD_SMS)
    assert not all(r.passed for r in whole)                          # ... and checking the whole reply would have failed


def test_run_spec_without_a_curtain_checks_the_whole_reply():
    client = constant(GOOD_SMS)
    out = run_spec(lab_for(client), TASK2, TASK2.reference)
    assert out["passed"] == out["of"] and out["scratch"] == "" and out["leaks"] == []
    assert "<final>" not in client.calls[0]["messages"][0]["content"]


def test_pass_rate_and_verdict_put_a_price_on_the_change():
    v1 = pass_rate(lab_for(constant(GOOD_SMS, prompt=300, completion=100)), TASK2, TASK2.reference, runs=2)
    v2 = pass_rate(lab_for(constant(f"<scratchpad>x</scratchpad><final>{GOOD_SMS}</final>", prompt=300, completion=300)),
                   TASK2, TASK2.reference, hidden_reasoning=True, runs=2)
    assert v1["all_passed"] == 2 and v2["all_passed"] == 2 and v1["avg_tokens"] == 400 and v2["avg_tokens"] == 600
    assert "same number of checks" in verdict(v1, v2) and "1.5x the tokens" in verdict(v1, v2)
    worse = dict(v2, avg_checks=v1["avg_checks"] - 1)
    better = dict(v2, avg_checks=v1["avg_checks"] + 1)
    assert "keep v1" in verdict(v1, worse) and "passes more checks" in verdict(v1, better)


# ---------------------------------------------------------------- the control task and Session 14's classifier
def test_the_thinking_classifier_asks_for_a_final_line():
    spec = classify_cot_spec()
    assert "FINAL: <category>" in spec.task and "single word" not in spec.task and spec.examples == []


def test_score_classifier_reads_a_single_word_or_a_final_line():
    plain = score_classifier_lab(lab_for(constant("card", prompt=50, completion=2)), classify_spec(0), mode="plain")
    assert plain["n"] == 8 and plain["calls"] == 8 and plain["accuracy"] == 2 and plain["tokens"] == 8 * 52
    thinking = score_classifier_lab(lab_for(constant("It mentions a card.\nFINAL: card", prompt=50, completion=40)),
                                    classify_cot_spec(), mode="cot")
    assert thinking["accuracy"] == 2 and thinking["tokens"] == 8 * 90
    no_final = score_classifier_lab(lab_for(constant("It is about a card, I think.")), classify_cot_spec(), mode="cot")
    assert no_final["accuracy"] == 0                                 # no FINAL line: do not guess a label from the prose


# ---------------------------------------------------------------- the library, version 2
def library_with(tmp_path, entries):
    repo = tmp_path / "work"
    repo.mkdir()
    init_work_repo(repo)
    from prompt_utils import CheckResult
    for task, version in entries:
        save_to_library(repo, task.id, version, task.reference, "out", [CheckResult("c", True)])
    return repo


def test_tasks_with_version_reads_the_library_text():
    text = "## T1-credit-summary | v1 | 2026-10-06\n\n## T1-credit-summary | v2 | 2026-10-08\n## T3-complaint-triage | v1 | 2026-10-06\n"
    assert tasks_with_version(text, 2) == {"T1-credit-summary"} and tasks_with_version(text, 1) == {"T1-credit-summary", "T3-complaint-triage"}


def test_library_check_passes_with_two_v2_entries_and_the_v1_history(tmp_path):
    repo = library_with(tmp_path, [(TASK1, 1), (TASK2, 1), (TASK3, 1), (TASK1, 2), (TASK2, 2)])
    results = check_library_v2(repo)
    assert all(r.passed for r in results), [(r.name, r.detail) for r in results if not r.passed]


def test_the_combined_check_needs_both_the_library_and_the_table(tmp_path):
    repo = library_with(tmp_path, [(TASK1, 1), (TASK2, 1), (TASK1, 2), (TASK2, 2)])
    assert not all(r.passed for r in check_s15_work(repo))             # library fine, no accuracy table yet
    save_accuracy_table(repo, "\n".join(f"| L{i:02d}-x | approve | approve ok |" for i in range(1, 11)))
    results = check_s15_work(repo)
    assert len(results) == 5 and all(r.passed for r in results), [(r.name, r.detail) for r in results if not r.passed]


def test_library_check_explains_each_gap(tmp_path):
    only_v1 = {r.name: r for r in check_library_v2(library_with(tmp_path, [(TASK1, 1)]))}
    assert only_v1["library still has your version 1 entries"].passed
    assert not only_v1["version 2 entries for at least 2 tasks"].passed
    other = tmp_path / "second"
    other.mkdir()
    init_work_repo(other)
    save_to_library(other, TASK1.id, 2, TASK1.reference, "out", [])
    save_to_library(other, TASK2.id, 2, TASK2.reference, "out", [])
    gaps = {r.name: r for r in check_library_v2(other)}
    assert not gaps["library still has your version 1 entries"].passed
    assert not gaps["every v2 task still has its v1 entry (history kept)"].passed
    assert not check_library_v2(tmp_path / "missing")[0].passed


# ---------------------------------------------------------------- the instructor's submission checker
LIB_OK = ("## T1-credit-summary | v1 | d\n## T2-sms-declined | v1 | d\n## T3-complaint-triage | v1 | d\n"
          "## T1-credit-summary | v2 | d\n## T2-sms-declined | v2 | d\n")
TABLE_OK = "\n".join(f"| L{i:02d}-x | approve | approve ok |" for i in range(1, 11))


def fake_repo(files):
    """A stand-in for the network: files maps a path inside the repo to its text; main branch only."""
    def fetch(url):
        marker = "/main/"
        return files.get(url.split(marker, 1)[1]) if marker in url else None
    return fetch


def test_s15_submission_statuses():
    url = "https://github.com/a/b"
    ok = check_repo_s15(url, fetch=fake_repo({"prompts/library.md": LIB_OK, "experiments/s15_accuracy_table.md": TABLE_OK}))
    assert ok["status"] == "PASS" and ok["v2_tasks"] == 2 and ok["case_rows"] == 10
    no_table = check_repo_s15(url, fetch=fake_repo({"prompts/library.md": LIB_OK}))
    assert "NO accuracy table" in no_table["status"]
    short = check_repo_s15(url, fetch=fake_repo({"prompts/library.md": LIB_OK, "experiments/s15_accuracy_table.md": "\n".join(TABLE_OK.splitlines()[:6])}))
    assert "TABLE HAS 6 CASE ROWS" in short["status"]
    one_v2 = check_repo_s15(url, fetch=fake_repo({"prompts/library.md": "## T1-a | v1 | d\n## T1-a | v2 | d\n", "experiments/s15_accuracy_table.md": TABLE_OK}))
    assert "ONLY 1 v2 TASK(S)" in one_v2["status"]
    overwritten = check_repo_s15(url, fetch=fake_repo({"prompts/library.md": "## T1-a | v2 | d\n## T2-b | v2 | d\n", "experiments/s15_accuracy_table.md": TABLE_OK}))
    assert "v1 ENTRY MISSING" in overwritten["status"]
    assert "NO prompts/library.md" in check_repo_s15(url, fetch=lambda u: None)["status"]
    assert check_repo_s15("hello")["status"] == "NOT A GITHUB URL"


# ---------------------------------------------------------------- the notebook itself
def test_every_code_cell_in_the_notebook_compiles():
    nb = json.loads((Path(__file__).resolve().parents[1] / "module02" / "s15_reasoning.ipynb").read_text(encoding="utf-8"))
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code) >= 15
    for i, cell in enumerate(code):
        compile("".join(cell["source"]), f"cell {i}", "exec")


# ---------------------------------------------------------------- live tests: skip without a key or Ollama
LIVE = bool(os.getenv("API_KEY") and os.getenv("BASE_URL") and os.getenv("MODEL"))


@pytest.mark.skipif(not LIVE, reason="no API key in .env")
def test_live_plain_and_cot_on_the_warm_up_problem():
    from providers_utils import groq_client
    lab = Lab(groq_client(), os.getenv("MODEL"))
    plain, cot = solve_plain(lab, DEMO), solve_cot(lab, DEMO)
    for a in (plain, cot):
        assert a.calls == 1 and a.tokens > 0 and a.seconds > 0
    assert plain.answer is not None or plain.truncated
    assert cot.answer is not None or cot.truncated


def _ollama():
    try:
        from providers_utils import ollama_client
        client = ollama_client().with_options(timeout=2, max_retries=0)
        names = [m.id for m in client.models.list().data]
        return client, pick_local_chat_model(names)
    except Exception:  # noqa: BLE001 - no Ollama is a normal state, not a failure
        return None, None


_OLLAMA_CLIENT, _OLLAMA_MODEL = _ollama()


@pytest.mark.skipif(_OLLAMA_MODEL is None, reason="Ollama is not running or has no chat model")
def test_live_local_model_answers_in_the_final_line_format():
    from providers_utils import ollama_client
    a = solve_cot(Lab(ollama_client(), _OLLAMA_MODEL, max_tokens=1500), DEMO)
    assert a.calls == 1 and a.tokens > 0 and a.reasoning_tokens is None or a.reasoning_tokens >= 0
