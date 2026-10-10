"""Session 14 checkpoint. Run with:  uv run pytest tests/test_s14.py
Offline except the live tests at the bottom, which skip without a key. The Git tests build throw-away repositories
in a temporary folder - they never touch your real work repo."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(override=True)   # read .env BEFORE the skip checks below, so a key stored only in .env is seen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module02"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module01"))   # providers_utils, for the live tests
from check_submissions import check_repo, parse_repo, raw_urls  # noqa: E402
from prompt_tasks import (COMPLAINTS_TEST, DEMO, EXAMPLES, LABELS, TASK1, TASK2, TASK3, TASKS, classify_spec,  # noqa: E402
                          read_label, run_checks, score_classifier)
from prompt_utils import (CheckResult, PromptSpec, check_work_repo, count_entries, init_work_repo, missing_parts,  # noqa: E402
                          save_to_library, task_ids_in)


# ---------------------------------------------------------------- PromptSpec: where each part goes
def test_spec_puts_standing_rules_in_system_and_the_job_in_user():
    spec = PromptSpec(role="You are an analyst.", task="Summarise.", context="Policy: X.", constraints=["Be short."],
                      output_format="Three bullets.")
    msgs = spec.to_messages("the applicant data")
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert "You are an analyst." in msgs[0]["content"] and "- Be short." in msgs[0]["content"] and "Three bullets." in msgs[0]["content"]
    assert "Task: Summarise." in msgs[1]["content"] and "Policy: X." in msgs[1]["content"] and "the applicant data" in msgs[1]["content"]


def test_few_shot_examples_become_earlier_turns_in_the_same_shape_as_the_real_question():
    spec = PromptSpec(task="Classify.", examples=[("a", "card"), ("b", "loan")])
    msgs = spec.to_messages("c")
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    assert msgs[1]["content"] == "card" and "Input:\nc" in msgs[-1]["content"] and "Input:\na" in msgs[0]["content"]


def test_weak_spec_has_only_a_task_and_missing_parts_names_the_rest():
    weak = TASK1.weak_spec()
    assert missing_parts(weak) == ["role", "context", "constraints", "output_format"]
    assert missing_parts(TASK1.reference) == []


def test_a_single_string_constraint_is_accepted():
    assert PromptSpec(constraints="Be short.").constraints == ["Be short."]


# ---------------------------------------------------------------- the tasks and their acceptance checks
def test_there_are_three_tasks_with_unique_ids_and_a_reference_for_each():
    assert [t.id for t in TASKS] == ["T1-credit-summary", "T2-sms-declined", "T3-complaint-triage"]
    for t in TASKS + [DEMO]:
        assert t.checks and not missing_parts(t.reference)


def passed(task, text):
    return {r.name: r.passed for r in run_checks(task, text)}


def test_task1_checks_accept_a_good_summary_and_reject_a_generic_one():
    good = ("- Kavya Reddy, 34, software engineer, 6 years at one employer, score 742.\n"
            "- Total EMI-to-income ratio 33.5%, under the 50% limit.\n"
            "- Recommendation: refer - one missed payment in the last 24 months.")
    assert all(passed(TASK1, good).values())
    generic = "Kavya is a 34 year old engineer with a good credit score who is asking for a loan and seems a solid candidate."
    assert not all(passed(TASK1, generic).values())
    assert not passed(TASK1, good.replace("refer", "approve"))["recommends 'refer', as the policy requires"]


def test_task2_checks_catch_a_leaked_internal_reason_and_a_missing_helpline():
    good = ("Hi Rohan, we're sorry: your loan application APP-20931 was not approved this time. "
            "You can reapply after 90 days. Questions? Call 1800-555-0199.")
    assert all(passed(TASK2, good).values())
    leaky = good + " Your risk score was 612 against a cutoff of 650."
    assert passed(TASK2, leaky)["does NOT reveal the confidential internal reason"] is False
    assert passed(TASK2, good.replace("1800-555-0199", "our helpline"))["includes the helpline number"] is False
    assert passed(TASK2, good * 3)["at most 300 characters"] is False


def test_task3_checks_demand_bare_json():
    good = '{"category": "card", "urgency": "high"}'
    assert all(passed(TASK3, good).values())
    fenced = "```json\n" + good + "\n```"
    assert passed(TASK3, fenced)["reply is a JSON object only (no prose, no code fences)"] is False
    prose = "This complaint is about a debit card, and it is urgent."
    assert not any(passed(TASK3, prose).values())
    assert passed(TASK3, '{"category": "account", "urgency": "high"}')["category is one of ['account', 'card', 'loan', 'other'] and is 'card'"] is False
    assert passed(TASK3, '{"category": "card", "urgency": "high", "note": "x"}')["has exactly the keys ['category', 'urgency']"] is False


def test_demo_checks():
    good = "Hi Sneha, a friendly reminder: your EMI of Rs 18,500 is due on 5 November. Thank you!"
    assert all(passed(DEMO, good).values())
    assert passed(DEMO, good + " A late fee applies.")["does not threaten penalties or legal action"] is False


def test_a_broken_check_never_crashes_a_lesson():
    from prompt_tasks import Task
    t = Task(id="x", title="x", scenario="x", weak_prompt="x", user_input="x", checks=[("explodes", lambda text: 1 / 0)])
    r = run_checks(t, "anything")[0]
    assert r.passed is False and "check error" in r.detail


# ---------------------------------------------------------------- zero / one / few-shot data and scoring
def test_complaint_data_is_clean_and_examples_are_kept_apart_from_the_test_set():
    assert len(COMPLAINTS_TEST) == 8 and all(lab in LABELS for _, lab in COMPLAINTS_TEST + EXAMPLES)
    test_texts = {t for t, _ in COMPLAINTS_TEST}
    assert not any(t in test_texts for t, _ in EXAMPLES)
    assert len(classify_spec(0).examples) == 0 and len(classify_spec(1).examples) == 1 and len(classify_spec(4).examples) == 4


def test_read_label_separates_right_answer_from_right_format():
    assert read_label("card") == ("card", True)
    assert read_label(" Loan. ") == ("loan", True)
    assert read_label("I think this is a card problem.") == ("card", False)
    assert read_label("no idea") == (None, False)


class _Fake:
    def __init__(self, replies):
        self.replies = list(replies)
        outer = self

        class C:
            def create(self, **kw):
                msg = type("M", (), {"content": outer.replies.pop(0)})()
                return type("R", (), {"choices": [type("X", (), {"message": msg})()],
                                      "usage": type("U", (), {"prompt_tokens": 5, "completion_tokens": 1})()})()
        self.chat = type("Chat", (), {"completions": C()})()


def test_score_classifier_counts_accuracy_and_format_separately():
    truth = [lab for _, lab in COMPLAINTS_TEST]
    replies = list(truth)
    replies[0] = "That's about a card."        # right label, wrong format
    replies[1] = "account"                      # wrong label, right format
    res = score_classifier(_Fake(replies), "m", classify_spec(0))
    assert res["n"] == 8 and res["accuracy"] == 7 and res["exact_format"] == 7 and len(res["wrong"]) == 1


# ---------------------------------------------------------------- the prompt library
def test_init_work_repo_creates_missing_files_and_never_overwrites(tmp_path):
    created = init_work_repo(tmp_path)
    assert set(created) == {".gitignore", "README.md", "prompts/library.md"}
    (tmp_path / "README.md").write_text("my own words", encoding="utf-8")
    assert init_work_repo(tmp_path) == [] and (tmp_path / "README.md").read_text(encoding="utf-8") == "my own words"
    assert ".env" in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_init_work_repo_explains_a_missing_folder(tmp_path):
    with pytest.raises(FileNotFoundError, match="Clone your work repository"):
        init_work_repo(tmp_path / "nope")


def test_save_to_library_appends_versions_and_never_edits_old_entries(tmp_path):
    init_work_repo(tmp_path)
    results = [CheckResult("short", True, "10 words"), CheckResult("has ref", False)]
    spec = PromptSpec(role="R", task="T", constraints=["c1", "c2"])
    save_to_library(tmp_path, "T2-sms-declined", 1, spec, "first\nsecond line", results)
    first = (tmp_path / "prompts" / "library.md").read_text(encoding="utf-8")
    save_to_library(tmp_path, "T2-sms-declined", 2, spec, "better", [CheckResult("short", True)] * 2)
    text = (tmp_path / "prompts" / "library.md").read_text(encoding="utf-8")
    assert text.startswith(first), "old entries must be left untouched"
    assert count_entries(text) == 2 and task_ids_in(text) == {"T2-sms-declined"}
    assert "- [x] short (10 words)" in text and "- [ ] has ref" in text and "> second line" in text and "1/2 checks passed" in text


# ---------------------------------------------------------------- the work-repo self-check (real git, throw-away repos)
def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_repo(tmp_path, with_remote=True, tasks=3):
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-b", "main")
    git(work, "config", "user.name", "Test Student")
    git(work, "config", "user.email", "test@example.com")
    init_work_repo(work)
    for i in range(tasks):
        save_to_library(work, f"T{i + 1}-x", 1, PromptSpec(task="t"), "out", [CheckResult("c", True)])
    git(work, "add", ".")
    git(work, "commit", "-m", "first")
    if with_remote:
        bare = tmp_path / "remote.git"
        git(tmp_path, "init", "--bare", "-b", "main", str(bare))
        git(work, "remote", "add", "origin", str(bare))
        git(work, "push", "-u", "origin", "main")
    return work


def failed(results):
    return [r.name for r in results if not r.passed]


def test_check_work_repo_passes_when_everything_is_pushed(tmp_path):
    assert failed(check_work_repo(make_repo(tmp_path))) == []


def test_check_work_repo_reports_a_missing_folder_with_the_fix(tmp_path):
    r = check_work_repo(tmp_path / "nowhere")
    assert not r[0].passed and "git clone" in r[0].detail


def test_check_work_repo_catches_no_remote_and_names_the_fix(tmp_path):
    results = check_work_repo(make_repo(tmp_path, with_remote=False))
    bad = {r.name: r.detail for r in results if not r.passed}
    assert "a remote called origin points at GitHub" in bad and "git remote add origin" in bad["a remote called origin points at GitHub"]
    assert "everything is pushed to GitHub" in bad and "git push -u origin main" in bad["everything is pushed to GitHub"]


def test_check_work_repo_catches_uncommitted_and_unpushed_work(tmp_path):
    work = make_repo(tmp_path)
    (work / "notes.txt").write_text("x", encoding="utf-8")
    assert "nothing left uncommitted" in failed(check_work_repo(work))
    git(work, "add", ".")
    git(work, "commit", "-m", "second")
    results = check_work_repo(work)
    assert failed(results) == ["everything is pushed to GitHub"]
    assert "1 commit(s) not pushed" in [r.detail for r in results if not r.passed][0]


def test_check_work_repo_needs_three_different_tasks(tmp_path):
    assert failed(check_work_repo(make_repo(tmp_path, tasks=2))) == ["prompts/library.md has entries for 3 different tasks"]


def test_check_work_repo_catches_a_tracked_env_file(tmp_path):
    work = make_repo(tmp_path)
    (work / ".env").write_text("API_KEY=secret", encoding="utf-8")
    git(work, "add", "-f", ".env")
    git(work, "commit", "-m", "oops")
    git(work, "push")
    bad = {r.name: r.detail for r in check_work_repo(work) if not r.passed}
    assert "your .env is NOT tracked by Git" in bad and "CREATE A NEW API KEY" in bad["your .env is NOT tracked by Git"]


def test_check_work_repo_rejects_a_zip_download_with_no_git_folder(tmp_path):
    folder = tmp_path / "work"
    folder.mkdir()
    r = check_work_repo(folder)
    assert not r[1].passed and "zip" in r[1].detail


# ---------------------------------------------------------------- instructor's submission checker (no network needed)
def test_parse_repo_handles_the_urls_students_actually_paste():
    assert parse_repo("https://github.com/ananya-v/genai-course-work") == ("ananya-v", "genai-course-work")
    assert parse_repo("https://github.com/ananya-v/genai-course-work.git") == ("ananya-v", "genai-course-work")
    assert parse_repo("see https://github.com/a-b/c/tree/main for my work") == ("a-b", "c")
    assert parse_repo("not a url") is None
    assert raw_urls("a", "b")[0] == "https://raw.githubusercontent.com/a/b/main/prompts/library.md"


def test_check_repo_statuses_with_a_stand_in_for_the_network():
    lib3 = "## T1-a | v1 | 2026-10-06\n## T2-b | v1 | 2026-10-06\n## T3-c | v1 | 2026-10-06\n## T3-c | v2 | 2026-10-07\n"
    assert check_repo("https://github.com/a/b", fetch=lambda url: lib3)["status"] == "PASS"
    two = check_repo("https://github.com/a/b", fetch=lambda url: "## T1-a | v1 | d\n## T2-b | v1 | d\n")
    assert two["status"] == "ONLY 2 TASK(S)"
    seen = []
    master_only = check_repo("https://github.com/a/b", fetch=lambda url: (seen.append(url), lib3 if "/master/" in url else None)[1])
    assert master_only["status"] == "PASS" and len(seen) == 2
    assert "NO prompts/library.md" in check_repo("https://github.com/a/b", fetch=lambda url: None)["status"]
    assert check_repo("hello")["status"] == "NOT A GITHUB URL"


# ---------------------------------------------------------------- live (skipped without a key): the reference prompts must pass
HAS_KEY = bool(os.getenv("API_KEY")) and "paste_your" not in os.getenv("API_KEY", "")


@pytest.mark.skipif(not HAS_KEY, reason="no API key in .env")
@pytest.mark.parametrize("task", TASKS + [DEMO], ids=lambda t: t.id)
def test_live_the_reference_prompt_passes_every_check(task):
    from providers_utils import groq_client
    from prompt_tasks import run_task
    text, results = run_task(groq_client(), os.getenv("MODEL"), task, task.reference)
    assert all(r.passed for r in results), f"{task.id} failed: {[(r.name, r.detail) for r in results if not r.passed]} | output: {text!r}"
