"""
Showcase A3 - Healthcare, row A (workflow)
==========================================
A patient writes to a clinic's booking assistant, one message at a time.

    safety rule (code) -> intent router (model) -> slot filling (model reads, CODE decides) -> booking (code) -> confirmation (template)

This is a WORKFLOW. Notice who owns what:
  * The MODEL only reads messy language: "which intent is this?" and "which details did they mention?"
  * The CODE owns the loop: which question to ask next, when enough is known, when to book,
    and a safety rule that fires BEFORE any model is called.
The model never decides what happens next. Compare row B (S21 onward), where it does.

MOCK DATA ONLY. Not medical advice, not a triage tool - the emergency rule exists to show a code-owned
safety check, nothing more.

Run with:
    uv run python showcase/a3_healthcare/appointment_flow.py                    # the happy path
    uv run python showcase/a3_healthcare/appointment_flow.py --scenario emergency
    uv run python showcase/a3_healthcare/appointment_flow.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from appointments_data import (AVAILABILITY, DAYS, EMERGENCY_KEYWORDS, SCENARIOS, SPECIALTIES,  # noqa: E402
                               TIMES_OF_DAY)

INTENTS = ["book", "cancel", "reschedule", "info", "other"]

# ---------------------------------------------------------------- templates (no model writes patient-facing text)
QUESTIONS = {
    "specialty": "Which kind of doctor would you like to see? (cardiology, dermatology, general physician or orthopedics)",
    "day": "Which day suits you? (Monday to Friday)",
    "time_of_day": "Do you prefer morning, afternoon or evening?",
    "patient_name": "May I have the patient's full name?",
}
SLOT_ORDER = ["specialty", "day", "time_of_day", "patient_name"]   # the CODE fixes the order of questions
EMERGENCY_TEXT = ("This sounds like it may be an emergency. Please call your local emergency number or go to the nearest "
                  "emergency department now. This assistant cannot help with urgent medical problems.")
HANDOFF_TEXT = "I'll pass this to our front-desk team, who can change or cancel appointments. They will contact you shortly."
INFO_TEXT = "The clinic is open Monday to Friday, 9:00 to 19:00. For anything else, please call the front desk."
OUT_OF_SCOPE_TEXT = "I can only help with booking clinic appointments. Would you like to book one?"


# ---------------------------------------------------------------- state and the code-owned decisions
@dataclass
class Slots:
    specialty: str | None = None
    day: str | None = None
    time_of_day: str | None = None
    patient_name: str | None = None

    def merge(self, found: dict) -> None:
        """Newest mention wins; a null never erases something already known."""
        for key in SLOT_ORDER:
            if found.get(key):
                setattr(self, key, found[key])

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in SLOT_ORDER}


def next_missing(slots: Slots) -> str | None:
    """CODE decides what to ask next - always in SLOT_ORDER, never the model's choice."""
    for key in SLOT_ORDER:
        if getattr(slots, key) is None:
            return key
    return None


def has_emergency(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in EMERGENCY_KEYWORDS)


def find_slot(slots: Slots) -> tuple | None:
    for row in AVAILABILITY:
        if row[1] == slots.specialty and row[2] == slots.day and row[3] == slots.time_of_day:
            return row
    return None


def alternatives(slots: Slots) -> list[tuple]:
    return [row for row in AVAILABILITY if row[1] == slots.specialty]


def confirmation(row: tuple, slots: Slots) -> str:
    doctor, _spec, day, _tod, clock = row
    return (f"Booked: {slots.patient_name} with {doctor} ({slots.specialty.replace('_', ' ')}) on "
            f"{day.capitalize()} at {clock}. Please arrive 10 minutes early.")


def no_slot_text(slots: Slots) -> str:
    opts = "; ".join(f"{r[0]} {r[2].capitalize()} {r[4]}" for r in alternatives(slots)) or "none available"
    return f"Sorry, there is no {slots.specialty.replace('_', ' ')} slot on {slots.day.capitalize()} {slots.time_of_day}. Available instead: {opts}."


# ---------------------------------------------------------------- the two model jobs
INTENT_SCHEMA = {"type": "object", "properties": {"intent": {"type": "string", "enum": INTENTS}},
                 "required": ["intent"], "additionalProperties": False}
SLOT_SCHEMA = {"type": "object", "properties": {
    "specialty": {"type": ["string", "null"], "enum": SPECIALTIES + [None]},
    "day": {"type": ["string", "null"], "enum": DAYS + [None]},
    "time_of_day": {"type": ["string", "null"], "enum": TIMES_OF_DAY + [None]},
    "patient_name": {"type": ["string", "null"]},
}, "required": SLOT_ORDER, "additionalProperties": False}

INTENT_SYSTEM = "Classify a clinic patient's message as exactly one intent: book, cancel, reschedule, info or other."
SLOT_SYSTEM = ("Extract appointment details the patient mentions. specialty is one of cardiology, dermatology, "
               "general_physician, orthopedics (a skin doctor is dermatology; a knee or bone problem is orthopedics; "
               "a heart doctor is cardiology). day is monday-friday. time_of_day is morning, afternoon or evening. "
               "patient_name is the patient's name. Use null for anything not mentioned. Never guess.")


def _structured(client, model, system, user, schema, name) -> dict:
    """Ask for JSON in the given shape. Strict schema first; if the provider rejects it, fall back to JSON mode."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    attempts = [{"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
                {"type": "json_object"}]
    last_error = None
    for rf in attempts:
        try:
            r = client.chat.completions.create(model=model, messages=messages, response_format=rf,
                                               max_tokens=1000, temperature=0)
            raw = (r.choices[0].message.content or "").strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            return json.loads(m.group(0) if m else raw)
        except Exception as e:  # noqa: BLE001 - deliberate: try the next, weaker level
            last_error = e
    raise RuntimeError(f"model call failed at every level: {last_error}")


def make_model_fns(client, model):
    """Return (classify, extract): the only two places a model is used in this whole workflow."""
    def classify(text: str) -> str:
        intent = _structured(client, model, INTENT_SYSTEM, text, INTENT_SCHEMA, "intent").get("intent")
        return intent if intent in INTENTS else "other"

    def extract(text: str) -> dict:
        found = _structured(client, model, SLOT_SYSTEM, text, SLOT_SCHEMA, "slots")
        return {k: (found.get(k) if found.get(k) in (SPECIALTIES + DAYS + TIMES_OF_DAY) or k == "patient_name" else None)
                for k in SLOT_ORDER}

    return classify, extract


# ---------------------------------------------------------------- the whole workflow, in order
def run_dialogue(user_turns, classify, extract, *, verbose: bool = True) -> dict:
    slots, intent, transcript, booking, outcome = Slots(), None, [], None, "incomplete"

    def say(who, text):
        transcript.append((who, text))
        if verbose:
            print(f"  {who:7}: {text}")

    for turn in user_turns:
        say("patient", turn)

        # 1. Safety rule - CODE, before any model call.
        if has_emergency(turn):
            say("bot", EMERGENCY_TEXT); outcome = "emergency"; break

        # 2. Intent router - MODEL reads, CODE branches.
        if intent is None:
            intent = classify(turn)
            if verbose:
                print(f"           [router -> {intent}]")
            if intent in ("cancel", "reschedule"):
                say("bot", HANDOFF_TEXT); outcome = "handoff"; break
            if intent == "info":
                say("bot", INFO_TEXT); outcome = "info"; break
            if intent == "other":
                say("bot", OUT_OF_SCOPE_TEXT); outcome = "out_of_scope"; break

        # 3. Slot filling - MODEL extracts what was said, CODE decides what to ask next.
        slots.merge(extract(turn))
        if verbose:
            print(f"           [slots -> {slots.as_dict()}]")
        missing = next_missing(slots)
        if missing:
            say("bot", QUESTIONS[missing]); continue

        # 4. Booking - plain CODE lookup. 5. Confirmation - TEMPLATE.
        booking = find_slot(slots)
        if booking:
            say("bot", confirmation(booking, slots)); outcome = "booked"
        else:
            say("bot", no_slot_text(slots)); outcome = "no_slot"
        break

    return {"intent": intent, "slots": slots.as_dict(), "booking": booking, "outcome": outcome, "transcript": transcript}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", choices=list(SCENARIOS), default="happy_path")
    parser.add_argument("--all", action="store_true", help="run every scripted scenario")
    args = parser.parse_args()

    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv(override=True)
    client = OpenAI(base_url=os.getenv("BASE_URL"), api_key=os.getenv("API_KEY"))
    classify, extract = make_model_fns(client, os.getenv("MODEL"))

    for name in (SCENARIOS if args.all else [args.scenario]):
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        result = run_dialogue(SCENARIOS[name], classify, extract)
        print(f"  -> outcome: {result['outcome']}")
