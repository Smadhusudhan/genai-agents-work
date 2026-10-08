"""Session 13 checkpoint. Run with:  uv run python -m pytest tests/test_s13.py
Offline tests use a fake client; the two live tests skip cleanly without a key."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module01"))
from vision_utils import (KYC_JSON_SCHEMA, KycRecord, SAMPLE_DIR, TRANSCRIBE_PROMPT, compare_to_truth,  # noqa: E402
                          encode_image, extract_validated, find_vision_model, level3_schema, parse_and_validate,
                          sample_transcript, strip_fences, vision_messages)

GOOD = '{"document_type":"id_card","full_name":"ANANYA RAO VEMULA","date_of_birth":"1994-03-14","id_number":"ABCDE1234F","address":null}'


class FakeClient:
    """Returns scripted replies in order and records every request it receives."""

    def __init__(self, replies, models=()):
        self.replies, self.calls, self._models = list(replies), [], models
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                text = outer.replies.pop(0)
                msg = type("M", (), {"content": text})()
                choice = type("C", (), {"message": msg})()
                usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5})()
                return type("R", (), {"choices": [choice], "usage": usage})()

        class _Models:
            def list(self):
                return type("L", (), {"data": [type("X", (), {"id": m})() for m in outer._models]})()

        self.chat = type("Chat", (), {"completions": _Completions()})()
        self.models = _Models()


# ---------------------------------------------------------------- images
def test_sample_documents_exist_with_transcripts():
    for stem in ("doc1_id_card", "doc2_utility_bill", "doc3_messy_scan"):
        assert (SAMPLE_DIR / f"{stem}.png").exists()
        assert "SAMPLE" in sample_transcript(stem)


def test_encode_image_makes_a_data_url():
    url = encode_image(SAMPLE_DIR / "doc1_id_card.png")
    assert url.startswith("data:image/png;base64,") and len(url) > 1000


def test_vision_messages_put_text_and_image_in_one_content_list():
    msgs = vision_messages("read this", SAMPLE_DIR / "doc1_id_card.png")
    parts = msgs[-1]["content"]
    assert [p["type"] for p in parts] == ["text", "image_url"]


def test_find_vision_model_picks_a_listed_preference_or_none():
    assert find_vision_model(FakeClient([], models=["llama-3.1-8b-instant"])) is None
    assert find_vision_model(FakeClient([], models=["x", "meta-llama/llama-4-scout-17b-16e-instruct"])) \
        == "meta-llama/llama-4-scout-17b-16e-instruct"


# ---------------------------------------------------------------- the contract
def test_schema_is_strict_mode_compliant():
    props = set(KYC_JSON_SCHEMA["properties"])
    assert set(KYC_JSON_SCHEMA["required"]) == props, "strict mode needs every property required"
    assert KYC_JSON_SCHEMA["additionalProperties"] is False


def test_kyc_record_accepts_good_data_and_coerces_the_date():
    rec = KycRecord(**__import__("json").loads(GOOD))
    assert rec.date_of_birth.year == 1994


@pytest.mark.parametrize("bad", [
    {"document_type": "id_card", "full_name": "A B", "date_of_birth": "1994-03-14", "id_number": "12345ABCDE"},  # bad PAN shape
    {"document_type": "id_card", "full_name": "A B", "date_of_birth": "2999-01-01", "id_number": "ABCDE1234F"},  # future DOB
    {"document_type": "id_card", "full_name": "A B", "date_of_birth": None, "id_number": "ABCDE1234F"},          # id card without DOB
    {"document_type": "passport", "full_name": "A B"},                                                          # not in the enum
])
def test_kyc_record_rejects_schema_valid_but_wrong_data(bad):
    with pytest.raises(Exception):
        KycRecord(**bad)


def test_utility_bill_needs_no_dob_or_id_number():
    rec = KycRecord(document_type="utility_bill", full_name="RAHUL KUMAR SHARMA", address="12-4-56 Lake View")
    assert rec.id_number is None


# ---------------------------------------------------------------- parsing and retry
def test_strip_fences_handles_fences_chatter_and_bare_json():
    assert strip_fences("```json\n{\"a\": 1}\n```") == '{"a": 1}'
    assert strip_fences('Sure! Here you go: {"a": 1} Hope that helps.') == '{"a": 1}'
    assert strip_fences('{"a": 1}') == '{"a": 1}'


def test_parse_and_validate_reports_plain_english_errors():
    rec, err = parse_and_validate("this is not json at all")
    assert rec is None and "not valid JSON" in err
    rec, err = parse_and_validate('{"document_type":"id_card","full_name":"A B","date_of_birth":"1994-03-14","id_number":"bad"}')
    assert rec is None and ("id_number" in err or "ABCDE1234F" in err)


def test_extract_validated_succeeds_first_time():
    out = extract_validated(FakeClient([GOOD]), "m", "doc text", mode="schema")
    assert out["record"] is not None and out["attempts"] == 1


def test_extract_validated_retries_once_and_feeds_the_error_back():
    client = FakeClient(["Sure, here it is: not json", GOOD])
    out = extract_validated(client, "m", "doc text", mode="prompt", max_retries=1)
    assert out["record"] is not None and out["attempts"] == 2 and len(out["errors"]) == 1
    retry_messages = client.calls[1]["messages"]
    assert any("not valid JSON" in str(m["content"]) for m in retry_messages), "error must be fed back"


def test_extract_validated_gives_up_after_the_retry_budget():
    out = extract_validated(FakeClient(["nope", "still nope"]), "m", "doc", mode="json_mode", max_retries=1)
    assert out["record"] is None and out["attempts"] == 2


def test_schema_level_sends_a_strict_json_schema_response_format():
    client = FakeClient([GOOD])
    level3_schema(client, "m", "doc")
    rf = client.calls[0]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True


# ---------------------------------------------------------------- live (skipped without a key)
HAS_KEY = bool(os.getenv("API_KEY")) and "paste_your" not in os.getenv("API_KEY", "")


@pytest.mark.skipif(not HAS_KEY, reason="no API key in .env")
def test_live_schema_extraction_on_the_clean_id_card():
    from providers_utils import groq_client
    out = extract_validated(groq_client(), os.getenv("MODEL"), sample_transcript("doc1_id_card"), mode="schema")
    assert out["record"] is not None, out["errors"]
    assert out["record"].id_number == "ABCDE1234F"
    assert str(out["record"].date_of_birth) == "1994-03-14"


@pytest.mark.skipif(not HAS_KEY, reason="no API key in .env")
def test_live_vision_reads_the_clean_id_card_if_a_vision_model_exists():
    from providers_utils import groq_client
    from vision_utils import read_image_text
    client = groq_client()
    vm = find_vision_model(client)
    if vm is None:
        pytest.skip("no vision model offered by this provider")
    text = read_image_text(client, vm, SAMPLE_DIR / "doc1_id_card.png")["text"].upper()
    assert "ABCDE1234F" in text.replace(" ", "")


# ---------------------------------------------------------------- compare a reading with the saved truth
def test_compare_to_truth_all_match_ignores_case_spacing_and_missing_labels():
    truth = sample_transcript("doc3_messy_scan")
    reading = "sample identity card\nMeera  Iyer\n09/11/1988\nPQRST5678Z\nSAMPLE - NOT A REAL DOCUMENT"
    assert all(ok for _line, ok in compare_to_truth(reading, truth))


def test_compare_to_truth_flags_a_single_misread_character():
    truth = sample_transcript("doc3_messy_scan")
    reading = truth.replace("PQRST5678Z", "PQRST56782")
    results = dict(compare_to_truth(reading, truth))
    assert results["ID NUMBER: PQRST5678Z"] is False
    assert results["FULL NAME: MEERA IYER"] is True


def test_the_cost_comparison_and_the_real_read_share_one_prompt():
    msgs = vision_messages(TRANSCRIBE_PROMPT, SAMPLE_DIR / "doc1_id_card.png")
    assert msgs[-1]["content"][0]["text"] == TRANSCRIBE_PROMPT
