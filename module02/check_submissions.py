"""Instructor tool: which students have pushed a prompt library with three different tasks?

    uv run python module02/check_submissions.py submissions.txt

submissions.txt: one GitHub repository URL per line, or a CSV exported from your form (the first cell on each
line containing 'github.com' is used). Repositories must be PUBLIC. It reads prompts/library.md straight from
GitHub (branch main, then master) - nothing is cloned, nothing is written except submissions_report.csv."""
from __future__ import annotations

import csv
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from prompt_utils import count_entries, task_ids_in  # noqa: E402

REPO_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def parse_repo(text: str):
    """Pull (owner, repo) out of any GitHub URL a student might paste, or None."""
    m = REPO_RE.search(text)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return owner, repo[:-4] if repo.endswith(".git") else repo


def raw_urls(owner: str, repo: str) -> list:
    return [f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/prompts/library.md" for branch in ("main", "master")]


def fetch_text(url: str, timeout: int = 15):
    """Return the file's text, or None if it is not there (404) or the network fails."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def check_repo(line: str, fetch=fetch_text, required: int = 3) -> dict:
    parsed = parse_repo(line)
    if not parsed:
        return {"repo": line.strip(), "status": "NOT A GITHUB URL", "entries": 0, "tasks": 0}
    owner, repo = parsed
    for url in raw_urls(owner, repo):
        text = fetch(url)
        if text is not None:
            ids = task_ids_in(text)
            status = "PASS" if len(ids) >= required else f"ONLY {len(ids)} TASK(S)"
            return {"repo": f"{owner}/{repo}", "status": status, "entries": count_entries(text), "tasks": len(ids)}
    return {"repo": f"{owner}/{repo}", "status": "NO prompts/library.md FOUND (private repo, wrong name, or not pushed)", "entries": 0, "tasks": 0}


def read_lines(path: Path) -> list:
    lines = []
    for row in csv.reader(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        cell = next((c for c in row if "github.com" in c), None)
        if cell:
            lines.append(cell)
    return lines


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    results = [check_repo(line) for line in read_lines(Path(argv[1]))]
    print(f"{'repository':42} {'tasks':>5} {'entries':>7}  status")
    for r in results:
        print(f"{r['repo'][:42]:42} {r['tasks']:>5} {r['entries']:>7}  {r['status']}")
    passed = sum(r["status"] == "PASS" for r in results)
    print(f"\n{passed}/{len(results)} pass")
    with open("submissions_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["repo", "status", "tasks", "entries"])
        w.writeheader()
        w.writerows(results)
    print("wrote submissions_report.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
