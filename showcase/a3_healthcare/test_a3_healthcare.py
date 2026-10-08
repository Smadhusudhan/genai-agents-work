"""Checkpoint for Showcase A3. Run with:  uv run pytest showcase/a3_healthcare/test_a3_healthcare.py
The workflow's own logic is tested offline with a keyword stand-in for the model; live tests skip without a key."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from appointment_flow import (Slots, alternatives, confirmation, find_slot, has_emergency,  # noqa: E402
                              make_model_fns, next_missing, run_dialogue)
from appointments_data import SCENARIOS  # noqa: E402


class FakeModel:
    """A keyword stand-in for the two model jobs. Counts calls so tests can prove WHEN the model is used."""

    def __init__(self):
        self.classify_calls = self.extract_calls = 0

    def classify(self, text):
        self.classify_calls += 1
        t = text.lower()
        if "cancel" in t: return "cancel"
        if "weather" in t: return "other"
        return "book"

    def extract(self, text):
        self.extract_calls += 1
        t, found = text.lower(), {}
        for spec, words in {"dermatology": ["skin"], "orthopedics": ["knee", "orthopedic"], "cardiology": ["cardiolog"],
                            "general_physician": ["general physician"]}.items():
            if any(w in t for w in words): found["specialty"] = spec
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
            if day in t: found["day"] = day
        for tod in ["morning", "afternoon", "evening"]:
            if tod in t: found["time_of_day"] = tod
        if "name is " in t: found["patient_name"] = text.split("name is ")[-1].strip().title()
        if "i'm " in t: found["patient_name"] = text.lower().split("i'm ")[1].split(" and")[0].title()
        if t.strip() in ("priya menon", "sneha reddy"): found["patient_name"] = text.strip()
        return found


def run(name):
    fm = FakeModel()
    return run_dialogue(SCENARIOS[name], fm.classify, fm.extract, verbose=False), fm


# ---------------------------------------------------------------- code-owned decisions
def test_next_missing_follows_the_fixed_order():
    s = Slots()
    order = []
    for key, value in [("specialty", "cardiology"), ("day", "monday"), ("time_of_day", "morning"), ("patient_name", "A B")]:
        order.append(next_missing(s))
        setattr(s, key, value)
    assert order == ["specialty", "day", "time_of_day", "patient_name"] and next_missing(s) is None


def test_merge_newest_wins_and_null_never_erases():
    s = Slots(specialty="cardiology", day="monday")
    s.merge({"specialty": None, "day": "tuesday", "time_of_day": None})
    assert s.specialty == "cardiology" and s.day == "tuesday"


def test_emergency_words_are_detected_case_insensitively():
    assert has_emergency("I have CHEST PAIN") and not has_emergency("I have a rash")


def test_find_slot_and_alternatives():
    s = Slots(specialty="cardiology", day="monday", time_of_day="morning", patient_name="A B")
    row = find_slot(s)
    assert row and row[0] == "Dr. Rao" and "Dr. Rao" in confirmation(row, s)
    s.day = "friday"
    assert find_slot(s) is None and len(alternatives(s)) == 2


# ---------------------------------------------------------------- the whole workflow
def test_emergency_is_decided_by_code_and_the_model_is_never_called():
    result, fm = run("emergency")
    assert result["outcome"] == "emergency"
    assert fm.classify_calls == 0 and fm.extract_calls == 0


def test_happy_path_asks_in_code_order_then_books():
    result, _ = run("happy_path")
    bot = [t for who, t in result["transcript"] if who == "bot"]
    assert "kind of doctor" in bot[0] and "day" in bot[1].lower() and "morning" in bot[2] and "full name" in bot[3]
    assert result["outcome"] == "booked" and result["booking"][0] == "Dr. Iyer"


def test_all_in_one_message_books_without_any_follow_up_question():
    result, _ = run("all_in_one")
    assert result["outcome"] == "booked" and len([1 for who, _ in result["transcript"] if who == "bot"]) == 1


def test_vague_then_filled_still_books():
    result, _ = run("vague_then_filled")
    assert result["outcome"] == "booked" and result["booking"][0] == "Dr. Sharma"


def test_no_matching_slot_offers_alternatives_instead_of_inventing_one():
    result, _ = run("no_matching_slot")
    assert result["outcome"] == "no_slot" and result["booking"] is None
    assert "Available instead" in result["transcript"][-1][1]


def test_cancel_is_handed_to_a_human_and_slots_are_never_extracted():
    result, fm = run("cancel_request")
    assert result["outcome"] == "handoff" and fm.extract_calls == 0


def test_off_topic_is_declined():
    assert run("off_topic")[0]["outcome"] == "out_of_scope"


def test_every_scenario_ends_in_a_known_outcome():
    for name in SCENARIOS:
        assert run(name)[0]["outcome"] in {"booked", "no_slot", "handoff", "emergency", "out_of_scope", "info", "incomplete"}


# ---------------------------------------------------------------- the real model wrappers, with a fake client
class _FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        outer = self

        class _C:
            def create(self, **kw):
                text = outer.replies.pop(0)
                if isinstance(text, Exception): raise text
                msg = type("M", (), {"content": text})()
                return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()
        self.chat = type("Chat", (), {"completions": _C()})()


def test_classify_falls_back_to_other_for_an_unknown_label():
    classify, _ = make_model_fns(_FakeClient(['{"intent": "teleport"}']), "m")
    assert classify("x") == "other"


def test_extract_drops_values_outside_the_allowed_lists_but_keeps_the_name():
    _, extract = make_model_fns(_FakeClient(['{"specialty":"astrology","day":"monday","time_of_day":null,"patient_name":"A B"}']), "m")
    found = extract("x")
    assert found["specialty"] is None and found["day"] == "monday" and found["patient_name"] == "A B"


def test_structured_falls_back_to_json_mode_when_strict_schema_is_rejected():
    classify, _ = make_model_fns(_FakeClient([RuntimeError("strict not supported"), 'Sure: {"intent": "book"}']), "m")
    assert classify("x") == "book"


# ---------------------------------------------------------------- live
HAS_KEY = bool(os.getenv("API_KEY")) and "paste_your" not in os.getenv("API_KEY", "")


@pytest.mark.skipif(not HAS_KEY, reason="no API key in .env")
def test_live_all_in_one_booking():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv(override=True)
    classify, extract = make_model_fns(OpenAI(base_url=os.getenv("BASE_URL"), api_key=os.getenv("API_KEY")), os.getenv("MODEL"))
    result = run_dialogue(SCENARIOS["all_in_one"], classify, extract, verbose=False)
    assert result["outcome"] == "booked"
