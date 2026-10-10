"""Session 14 helpers - prompt anatomy, a versioned prompt library, and a self-check for your work repository.

Three ideas live here:
  1. A prompt has parts (role, task, context, constraints, output format, examples). PromptSpec holds them
     and shows where each one goes in the messages list.
  2. A prompt is an asset: save each version, with its results, in a library you keep in Git.
  3. check_work_repo() tells you, in plain English, whether your first submission is really pushed.

Takes a client and a model name, so it works with any OpenAI-compatible provider."""
from __future__ import annotations

import datetime
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PARTS = ("role", "task", "context", "constraints", "output_format")

TIPS = {
    "role": "Role - who should the model be, and who is it writing for? ('You are a credit analyst writing for a credit committee.')",
    "task": "Task - say exactly what to do, in one sentence, starting with a verb.",
    "context": "Context - give the facts and rules the model cannot know: policy text, definitions, the audience.",
    "constraints": "Constraints - limits it must respect: length, things to include, things it must never reveal.",
    "output_format": "Output format - the exact shape of the reply: bullet lines, JSON keys, a single word.",
}


# ---------------------------------------------------------------- the prompt, as parts
@dataclass
class PromptSpec:
    role: str = ""
    task: str = ""
    context: str = ""
    constraints: list = field(default_factory=list)
    output_format: str = ""
    examples: list = field(default_factory=list)        # [(input, output), ...] -> few-shot

    def __post_init__(self):
        if isinstance(self.constraints, str):            # a student passes one string by mistake: accept it
            self.constraints = [self.constraints]

    def _system(self) -> str:
        parts = []
        if self.role.strip():
            parts.append(self.role.strip())
        rules = [c.strip() for c in self.constraints if c and c.strip()]
        if rules:
            parts.append("Rules:\n" + "\n".join(f"- {c}" for c in rules))
        if self.output_format.strip():
            parts.append("Output format: " + self.output_format.strip())
        return "\n\n".join(parts)

    def _user(self, text: str) -> str:
        parts = []
        if self.task.strip():
            parts.append("Task: " + self.task.strip())
        if self.context.strip():
            parts.append("Context:\n" + self.context.strip())
        if text.strip():
            parts.append("Input:\n" + text.strip())
        return "\n\n".join(parts)

    def to_messages(self, user_input: str = "") -> list:
        """Standing rules (role, constraints, format) go in the system message. The job (task, context, the
        actual input) goes in the user message. Examples become earlier user/assistant turns."""
        msgs = []
        system = self._system()
        if system:
            msgs.append({"role": "system", "content": system})
        for ex_in, ex_out in self.examples:
            msgs.append({"role": "user", "content": self._user(ex_in)})
            msgs.append({"role": "assistant", "content": ex_out})
        msgs.append({"role": "user", "content": self._user(user_input)})
        return msgs


def missing_parts(spec: PromptSpec) -> list:
    return [p for p in PARTS if not getattr(spec, p)]


def show_tips(spec: PromptSpec) -> None:
    gaps = missing_parts(spec)
    if not gaps:
        print("All five parts present." + ("" if spec.examples else " (No examples: fine, unless the format is unusual.)"))
        return
    print("Missing parts:")
    for p in gaps:
        print("  -", TIPS[p])


def chat(client, model: str, messages: list, temperature: float = 0, max_tokens: int = 1500) -> dict:
    """One call. max_tokens is generous because reasoning models spend tokens thinking before they answer."""
    r = client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    return {"text": r.choices[0].message.content or "", "prompt_tokens": r.usage.prompt_tokens,
            "completion_tokens": r.usage.completion_tokens}


# ---------------------------------------------------------------- check results
@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def results_table(results: list) -> str:
    lines = [f"  {'PASS' if r.passed else 'FAIL'}  {r.name}" + (f"   ({r.detail})" if r.detail else "") for r in results]
    return "\n".join(lines) + f"\n  -> {sum(r.passed for r in results)}/{len(results)} checks passed"


# ---------------------------------------------------------------- the prompt library (lives in YOUR work repo)
LIBRARY_HEADER = """# Prompt library

One entry per prompt version. Newest at the bottom. Each entry has the prompt, the output it produced,
and which acceptance checks it passed. Never edit an old entry: add a new version.

"""

GITIGNORE = """# Never commit secrets or machine-specific files
.env
.venv/
__pycache__/
.ipynb_checkpoints/
"""

README_STUB = """# genai-course-work

My work for the Generative AI, Agentic AI & AI Agents course.

- `prompts/library.md` - my versioned prompt library (Session 14 onward)
"""


def init_work_repo(repo_path) -> list:
    """Create .gitignore, README.md and prompts/library.md inside your cloned work repo - only if missing.
    Returns the names of the files it created."""
    repo = Path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(f"{repo} does not exist. Clone your work repository there first (see the work-repo steps).")
    created = []
    for rel, text in ((".gitignore", GITIGNORE), ("README.md", README_STUB), ("prompts/library.md", LIBRARY_HEADER)):
        target = repo / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            created.append(rel)
    return created


def save_to_library(repo_path, task_id: str, version: int, spec: PromptSpec, output: str, results: list,
                    purpose: str = "") -> Path:
    """Append one versioned entry to prompts/library.md. Older entries are never touched."""
    library = Path(repo_path) / "prompts" / "library.md"
    if not library.exists():
        init_work_repo(repo_path)
    passed = sum(r.passed for r in results)
    quoted = "\n".join("> " + line for line in (output.strip() or "(no output)").splitlines())
    checks = "\n".join(f"- [{'x' if r.passed else ' '}] {r.name}" + (f" ({r.detail})" if r.detail else "") for r in results)
    entry = f"""
## {task_id} | v{version} | {datetime.date.today().isoformat()}

**Purpose:** {purpose or task_id}
**Result:** {passed}/{len(results)} checks passed

### Prompt
- **Role:** {spec.role or '(none)'}
- **Task:** {spec.task or '(none)'}
- **Context:** {(spec.context or '(none)').strip()}
- **Constraints:** {'; '.join(c for c in spec.constraints if c) or '(none)'}
- **Output format:** {spec.output_format or '(none)'}
- **Examples:** {len(spec.examples)}

### Output
{quoted}

### Checks
{checks}
"""
    with library.open("a", encoding="utf-8") as f:
        f.write(entry)
    return library


ENTRY_RE = re.compile(r"^## (\S+) \| v(\d+) \| ", re.MULTILINE)


def task_ids_in(library_text: str) -> set:
    """The distinct task ids that have at least one entry in a library file's text."""
    return {m.group(1) for m in ENTRY_RE.finditer(library_text)}


def count_entries(library_text: str) -> int:
    return len(ENTRY_RE.findall(library_text))


# ---------------------------------------------------------------- is my first submission really pushed?
def _git(repo: Path, *args) -> tuple:
    try:
        p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "").strip()
    except FileNotFoundError:
        return 127, "git is not installed or not on PATH"


def check_work_repo(repo_path, required_tasks: int = 3) -> list:
    """Nine plain-English checks on your work repository. Each failure carries the exact fix."""
    repo = Path(repo_path)
    out = []
    if not repo.exists():
        return [CheckResult("work repo folder exists", False,
                            f"{repo} not found. Clone it: cd ~\\Documents ; git clone https://github.com/<you>/genai-course-work.git")]
    out.append(CheckResult("work repo folder exists", True))
    is_repo = (repo / ".git").exists()
    out.append(CheckResult("it is a Git repository (cloned, not downloaded as a zip)", is_repo,
                           "" if is_repo else "no .git folder: re-clone it with git clone, do not download a zip"))
    if not is_repo:
        return out

    rc_n, name = _git(repo, "config", "user.name")
    rc_e, email = _git(repo, "config", "user.email")
    out.append(CheckResult("Git knows your name and email", bool(name and email),
                           "" if name and email else 'git config --global user.name "Your Name" ; git config --global user.email "you@example.com"'))

    rc, url = _git(repo, "remote", "get-url", "origin")
    out.append(CheckResult("a remote called origin points at GitHub", rc == 0 and bool(url),
                           url if rc == 0 else "git remote add origin https://github.com/<you>/genai-course-work.git"))

    library = repo / "prompts" / "library.md"
    text = library.read_text(encoding="utf-8", errors="replace") if library.exists() else ""
    ids = task_ids_in(text)
    out.append(CheckResult(f"prompts/library.md has entries for {required_tasks} different tasks", len(ids) >= required_tasks,
                           f"found {len(ids)}: {sorted(ids)}" if ids else "file missing or empty: run the notebook's library cells"))

    gi = (repo / ".gitignore").read_text(encoding="utf-8", errors="replace") if (repo / ".gitignore").exists() else ""
    out.append(CheckResult(".gitignore lists .env", ".env" in gi.splitlines(),
                           "" if ".env" in gi.splitlines() else "add a line containing exactly .env to .gitignore"))
    rc, tracked = _git(repo, "ls-files", ".env")
    out.append(CheckResult("your .env is NOT tracked by Git", tracked == "",
                           "" if tracked == "" else "git rm --cached .env ; commit ; and CREATE A NEW API KEY - the old one may be public"))

    rc, status = _git(repo, "status", "--porcelain")
    out.append(CheckResult("nothing left uncommitted", rc == 0 and status == "",
                           "" if status == "" else 'git add . ; git commit -m "Session 14: prompt library"'))

    rc, upstream = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if rc != 0:
        out.append(CheckResult("everything is pushed to GitHub", False, "no upstream set: git push -u origin main"))
    else:
        rc2, ahead = _git(repo, "rev-list", "--count", "@{u}..HEAD")
        ok = rc2 == 0 and ahead == "0"
        out.append(CheckResult("everything is pushed to GitHub", ok, "" if ok else f"{ahead} commit(s) not pushed: git push"))
    return out
