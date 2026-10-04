"""
Showcase A2 — Insurance, row A (workflow)
==========================================
Free-text claim -> the model extracts a structured form (tokens in, JSON out)
-> plain Python code routes by severity -> a template answers.

This is a WORKFLOW, not an agent: the code decides the *sequence* of steps
(extract, then route, then answer) before a single customer ever types
anything. The model only fills in one step — reading messy language and
turning it into structure. It never chooses what happens next.

Compare with row B (S21+): same kind of problem, except the model itself
chooses which tool to call and in what order. That is an agent.

Run with:
    uv run python showcase/a2_insurance/insurance_claim.py
    uv run python showcase/a2_insurance/insurance_claim.py --claim major_injury
    uv run python showcase/a2_insurance/insurance_claim.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

sys.path.insert(0, str(Path(__file__).parent))
from claims_data import CLAIMS, CLAIMS_BY_ID  # noqa: E402

# ---------------------------------------------------------------- config (same pattern as hello.py)
load_dotenv(override=True)  # .env wins over anything an editor put in the environment
client = OpenAI(base_url=os.getenv("BASE_URL"), api_key=os.getenv("API_KEY"))
MODEL = os.getenv("MODEL")

# ---------------------------------------------------------------- step 1: the structured form
SYSTEM_PROMPT = """You are a claims intake assistant for a motor insurer.
Read the customer's free-text claim description and extract a structured form.
Reply with JSON only — no markdown fences, no commentary, just the object:
{"damage": "<short description of vehicle damage>",
 "injuries": <true or false>,
 "severity": "<minor or major>"}

Rules for severity:
- "major" if: any injury is mentioned, the vehicle is described as not drivable,
  a total loss, badly damaged, or multiple vehicles are involved.
- "minor" otherwise (small dents, scratches, glass chips, no injuries).
When in doubt between minor and major, choose major — a human should review it."""


class ClaimForm(BaseModel):
    """What the model must hand back. Validated the same way tools.py validates EMI input."""

    damage: str = Field(min_length=1)
    injuries: bool
    severity: str = Field(pattern="^(minor|major)$")


def extract_claim_form(claim_text: str) -> tuple[ClaimForm, dict]:
    """Step 1 (the only step that touches the model). Returns the validated form and raw usage."""
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": claim_text},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"model did not return valid JSON: {raw!r}") from e
    try:
        form = ClaimForm(**data)
    except ValidationError as e:
        raise RuntimeError(f"model JSON did not match the schema: {e}") from e
    usage = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "total_tokens": resp.usage.total_tokens,
    }
    return form, usage 


# ---------------------------------------------------------------- step 2: the router (plain code, no model)
FAST_TRACK_TEMPLATE = (
    "Thank you — this looks like a straightforward claim. We have fast-tracked it for repair. "
    "Please upload photos of the damage and we will arrange an inspection within 2 working days."
)
HUMAN_ADJUSTER_TEMPLATE = (
    "Thank you for reporting this. Given the details, a claims adjuster will contact you within "
    "24 hours to take this forward. If anyone is hurt, please seek medical attention first."
)


def route_claim(form: ClaimForm) -> tuple[str, str]:
    """The code decides what happens next. The model never sees this function."""
    if form.severity == "minor" and not form.injuries:
        return "fast_track", FAST_TRACK_TEMPLATE
    return "human_adjuster", HUMAN_ADJUSTER_TEMPLATE


# ---------------------------------------------------------------- the whole workflow, in order
def process_claim(claim_text: str, *, verbose: bool = True) -> dict:
    form, usage = extract_claim_form(claim_text)
    route, response = route_claim(form)

    if verbose:
        print(f"\nCLAIM TEXT:\n  {claim_text}")
        print(f"\nEXTRACTED FORM (model, step 1):")
        print(f"  damage:    {form.damage}")
        print(f"  injuries:  {form.injuries}")
        print(f"  severity:  {form.severity}")
        print(f"\nTOKENS (step 1 only — the only step that costs anything):")
        print(f"  prompt={usage['prompt_tokens']}  completion={usage['completion_tokens']}  "
              f"total={usage['total_tokens']}")
        print(f"\nROUTE (code, step 2 — the model never sees this decision): {route}")
        print(f"\nRESPONSE (template, step 3):\n  {response}")

    return {"form": form.model_dump(), "usage": usage, "route": route, "response": response}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claim", choices=list(CLAIMS_BY_ID), default="minor_no_injury",
                         help="which mock claim to run (default: minor_no_injury)")
    parser.add_argument("--all", action="store_true", help="run every mock claim, one after another")
    args = parser.parse_args()

    if args.all:
        for cid, text in CLAIMS:
            print(f"\n{'=' * 70}\n{cid}\n{'=' * 70}")
            process_claim(text)
    else:
        process_claim(CLAIMS_BY_ID[args.claim])
