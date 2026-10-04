"""Checkpoint for Showcase A2. Run with:  uv run pytest showcase/a2_insurance/test_a2_insurance.py
Offline tests check the router and schema; one live test (skipped with no key) checks the real call."""
import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent))
from claims_data import CLAIMS, CLAIMS_BY_ID  # noqa: E402
from insurance_claim import (ClaimForm, FAST_TRACK_TEMPLATE, HUMAN_ADJUSTER_TEMPLATE,  # noqa: E402
                             extract_claim_form, route_claim)


def test_mock_data_has_a_spread_of_cases():
    assert len(CLAIMS) >= 6
    ids = [c[0] for c in CLAIMS]
    assert len(ids) == len(set(ids)), "duplicate claim ids"
    assert all(len(text) > 20 for _, text in CLAIMS), "a claim description looks too short to be real"


def test_claim_form_validates_good_data():
    form = ClaimForm(damage="scratched bumper", injuries=False, severity="minor")
    assert form.severity == "minor"


def test_claim_form_rejects_bad_severity():
    with pytest.raises(ValidationError):
        ClaimForm(damage="scratched bumper", injuries=False, severity="catastrophic")


def test_router_sends_minor_no_injury_to_fast_track():
    form = ClaimForm(damage="scratched bumper", injuries=False, severity="minor")
    route, response = route_claim(form)
    assert route == "fast_track"
    assert response == FAST_TRACK_TEMPLATE


def test_router_sends_everything_else_to_a_human():
    cases = [
        ClaimForm(damage="fractured arm, car rolled over", injuries=True, severity="major"),
        ClaimForm(damage="minor scratch", injuries=True, severity="minor"),  # injury wins even if "minor"
        ClaimForm(damage="total loss", injuries=False, severity="major"),
    ]
    for form in cases:
        route, _ = route_claim(form)
        assert route == "human_adjuster", f"expected human_adjuster for {form}"
    # and the router never invents a third route
    assert route_claim(cases[0])[1] == HUMAN_ADJUSTER_TEMPLATE


def test_router_is_not_called_with_the_model():
    """The router takes a ClaimForm, not a client or raw text — proof it is plain code, no model call."""
    import inspect
    sig = inspect.signature(route_claim)
    params = list(sig.parameters)
    assert params == ["form"]


@pytest.mark.skipif(not os.getenv("API_KEY") or "paste_your" in os.getenv("API_KEY", ""), reason="no API key in .env")
def test_live_extraction_on_a_clear_minor_claim():
    text = CLAIMS_BY_ID["minor_glass_only"]
    form, usage = extract_claim_form(text)
    assert form.severity == "minor"
    assert form.injuries is False
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0


@pytest.mark.skipif(not os.getenv("API_KEY") or "paste_your" in os.getenv("API_KEY", ""), reason="no API key in .env")
def test_live_extraction_on_a_clear_major_claim():
    text = CLAIMS_BY_ID["major_injury"]
    form, _ = extract_claim_form(text)
    assert form.severity == "major"
    assert form.injuries is True
