"""Instructor tool: who pushed the Session 15 work? A ten-case accuracy table, and prompt library version 2 for two tasks.

    uv run python module02/check_s15_submissions.py submissions.txt

submissions.txt is the same file as for Session 14 (one GitHub repository URL per line, or a CSV exported from your form).
Repositories must be PUBLIC. It reads two files straight from GitHub (branch main, then master) and writes s15_report.csv."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_submissions import fetch_text, parse_repo, read_lines  # noqa: E402
from reasoning_utils import entries_in  # noqa: E402

CASE_ROW = re.compile(r"^\| L\d\d-", re.MULTILINE)


def raw_url(owner: str, repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"


def fetch_from_branches(owner: str, repo: str, path: str, fetch=fetch_text):
    for branch in ("main", "master"):
        text = fetch(raw_url(owner, repo, branch, path))
        if text is not None:
            return text
    return None


def check_repo_s15(line: str, fetch=fetch_text, need_v2: int = 2, need_cases: int = 10) -> dict:
    parsed = parse_repo(line)
    if not parsed:
        return {"repo": line.strip(), "status": "NOT A GITHUB URL", "v2_tasks": 0, "case_rows": 0}
    owner, repo = parsed
    library = fetch_from_branches(owner, repo, "prompts/library.md", fetch)
    table = fetch_from_branches(owner, repo, "experiments/s15_accuracy_table.md", fetch)
    entries = entries_in(library) if library else []
    v2 = {t for t, v in entries if v == 2}
    history_kept = all((t, 1) in entries for t in v2)
    rows = len(CASE_ROW.findall(table)) if table else 0
    problems = []
    if library is None:
        problems.append("NO prompts/library.md")
    elif len(v2) < need_v2:
        problems.append(f"ONLY {len(v2)} v2 TASK(S)")
    elif not history_kept:
        problems.append("v1 ENTRY MISSING (history overwritten)")
    if table is None:
        problems.append("NO accuracy table")
    elif rows < need_cases:
        problems.append(f"TABLE HAS {rows} CASE ROWS")
    return {"repo": f"{owner}/{repo}", "status": "PASS" if not problems else "; ".join(problems), "v2_tasks": len(v2), "case_rows": rows}


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    results = [check_repo_s15(line) for line in read_lines(Path(argv[1]))]
    print(f"{'repository':42} {'v2':>3} {'cases':>5}  status")
    for r in results:
        print(f"{r['repo'][:42]:42} {r['v2_tasks']:>3} {r['case_rows']:>5}  {r['status']}")
    print(f"\n{sum(r['status'] == 'PASS' for r in results)}/{len(results)} pass")
    with open("s15_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["repo", "status", "v2_tasks", "case_rows"])
        w.writeheader()
        w.writerows(results)
    print("wrote s15_report.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
