"""Session 13 helpers - images in, structured data out.

Two ideas live here:
  1. Vision: an image is just another kind of message content (base64 inside the messages list).
  2. Structured output has three levels - ask nicely, JSON mode, schema-enforced - and even the
     strictest level only guarantees SHAPE. Your own validation (Pydantic) guarantees MEANING.

Everything takes a client and a model name, so it works with any OpenAI-compatible provider."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

SAMPLE_DIR = Path(__file__).with_name("sample_docs")

# Preferred vision models, newest guess first. Model names rotate: find_vision_model() checks
# what the provider actually offers instead of trusting a name written down months ago.
VISION_PREFERENCES = (
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
)


# ---------------------------------------------------------------- images as message content
def encode_image(path: str | Path) -> str:
    """Read an image file and return a data URL: 'data:image/png;base64,....'
    This string is what travels inside the messages list."""
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def vision_messages(prompt: str, image_path: str | Path, system: str = "") -> list[dict]:
    """A user message whose content is a LIST: one text part and one image part."""
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": encode_image(image_path)}},
    ]})
    return msgs


def find_vision_model(client, preferred=VISION_PREFERENCES) -> Optional[str]:
    """Return the first preferred vision model the provider actually lists, else None."""
    try:
        available = {m.id for m in client.models.list().data}
    except Exception:
        return None
    for name in preferred:
        if name in available:
            return name
    return None


# One shared prompt: read_image_text() sends it, and the notebook's cost comparison sends the SAME words
# without the picture - so the difference in prompt tokens is the picture, not a changed instruction.
TRANSCRIBE_PROMPT = ("Transcribe every piece of text visible in this image, one line per field, exactly as printed. "
                     "Do not interpret or reformat anything.")


def read_image_text(client, model: str, image_path: str | Path, max_tokens: int = 400) -> dict:
    """Ask a vision model to transcribe the text it can see. Returns text plus usage, so the
    cost of an image is visible: compare prompt_tokens with a text-only call."""
    r = client.chat.completions.create(
        model=model, max_tokens=max_tokens, temperature=0,
        messages=vision_messages(TRANSCRIBE_PROMPT, image_path),
    )
    return {"text": r.choices[0].message.content, "prompt_tokens": r.usage.prompt_tokens,
            "completion_tokens": r.usage.completion_tokens}


def _norm(text: str) -> str:
    """Upper-case and keep only letters and digits, so spacing, case and punctuation do not matter."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def compare_to_truth(read_text: str, truth_text: str) -> list[tuple[str, bool]]:
    """For each line of the saved ground truth, did the model's reading contain its value?
    Only the part after a colon is compared, so a missing 'FULL NAME:' label is not a mismatch.
    Returns [(truth_line, matched), ...]. One wrong character in an ID number makes that line DIFFERENT."""
    got = _norm(read_text)
    out = []
    for line in truth_text.splitlines():
        if not line.strip():
            continue
        value = line.split(":", 1)[1] if ":" in line else line
        out.append((line.strip(), _norm(value) in got))
    return out


def sample_transcript(doc_stem: str) -> str:
    """The text a good vision model should return for a sample image - the offline fallback."""
    return (SAMPLE_DIR / f"{doc_stem}.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------- the contract: a Pydantic model
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class KycRecord(BaseModel):
    """What downstream code is allowed to receive. Types AND business rules."""

    document_type: str = Field(pattern="^(id_card|utility_bill|other)$")
    full_name: str = Field(min_length=2)
    date_of_birth: Optional[date] = None          # id cards have one; a utility bill does not
    id_number: Optional[str] = None
    address: Optional[str] = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob_in_past(cls, v):
        if v is not None and v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v

    @model_validator(mode="after")
    def _id_card_rules(self):
        if self.document_type == "id_card":
            if not self.id_number or not PAN_RE.match(self.id_number):
                raise ValueError("id_card needs an id_number like ABCDE1234F (5 letters, 4 digits, 1 letter)")
            if self.date_of_birth is None:
                raise ValueError("id_card needs a date_of_birth")
        return self


# The SHAPE contract sent to the provider for strict mode. Strict mode wants: every property
# listed in "required", additionalProperties false, and "nullable" written as a type list.
KYC_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string", "enum": ["id_card", "utility_bill", "other"]},
        "full_name": {"type": "string"},
        "date_of_birth": {"type": ["string", "null"], "description": "YYYY-MM-DD, or null if the document has none"},
        "id_number": {"type": ["string", "null"]},
        "address": {"type": ["string", "null"]},
    },
    "required": ["document_type", "full_name", "date_of_birth", "id_number", "address"],
    "additionalProperties": False,
}

EXTRACT_SYSTEM = (
    "You extract fields from the text of an identity or address document. "
    "document_type is id_card, utility_bill or other. date_of_birth must be written YYYY-MM-DD "
    "(convert from DD/MM/YYYY if needed) and is null if the document has no date of birth. "
    "Use null for anything not present. Never guess."
)


# ---------------------------------------------------------------- three levels of asking for JSON
def _call(client, model, messages, response_format=None, max_tokens=1500, temperature=0):
    kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
    if response_format:
        kwargs["response_format"] = response_format
    r = client.chat.completions.create(**kwargs)
    return r.choices[0].message.content or ""


def level1_prompt_only(client, model, doc_text, extra_messages=()):
    """Level 1: ask politely. Nothing enforces anything."""
    msgs = [{"role": "system", "content": EXTRACT_SYSTEM + " Reply with JSON only."},
            {"role": "user", "content": doc_text}, *extra_messages]
    return _call(client, model, msgs)


def level2_json_mode(client, model, doc_text, extra_messages=()):
    """Level 2: JSON mode. The reply is guaranteed to be syntactically valid JSON - of any shape."""
    msgs = [{"role": "system", "content": EXTRACT_SYSTEM + " Reply with a JSON object."},
            {"role": "user", "content": doc_text}, *extra_messages]
    return _call(client, model, msgs, response_format={"type": "json_object"})


def level3_schema(client, model, doc_text, extra_messages=()):
    """Level 3: schema-enforced. The provider constrains decoding to KYC_JSON_SCHEMA, so the
    SHAPE is guaranteed on models that support strict mode (gpt-oss-20b does)."""
    msgs = [{"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": doc_text}, *extra_messages]
    rf = {"type": "json_schema", "json_schema": {"name": "kyc_record", "strict": True, "schema": KYC_JSON_SCHEMA}}
    return _call(client, model, msgs, response_format=rf)


LEVELS = {"prompt": level1_prompt_only, "json_mode": level2_json_mode, "schema": level3_schema}


# ---------------------------------------------------------------- parse, validate, retry
def strip_fences(raw: str) -> str:
    """Models often wrap JSON in markdown fences or add a sentence around it. Pull the object out."""
    raw = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        raw = raw[start:end + 1]
    return raw


def parse_and_validate(raw: str) -> tuple[Optional[KycRecord], Optional[str]]:
    """Returns (record, None) on success or (None, plain-English error) on failure.
    The error text is written so it can be fed straight back to the model on a retry."""
    try:
        data = json.loads(strip_fences(raw))
    except json.JSONDecodeError as e:
        return None, f"The reply was not valid JSON ({e.msg}). Reply with the JSON object only."
    if not isinstance(data, dict):
        return None, "The reply must be a single JSON object."
    try:
        return KycRecord(**data), None
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(str(p) for p in err['loc']) or 'record'}: {err['msg']}" for err in e.errors())
        return None, f"The JSON broke these rules: {problems}. Fix them and reply with the corrected JSON object only."


def extract_validated(client, model, doc_text, mode: str = "schema", max_retries: int = 1) -> dict:
    """Extract, validate, and on failure retry ONCE with the error message fed back.
    Returns {record, attempts, errors, raw, mode}. record is None if every attempt failed."""
    fn = LEVELS[mode]
    errors, extra, raw = [], [], ""
    for attempt in range(1, max_retries + 2):
        raw = fn(client, model, doc_text, extra_messages=extra)
        record, err = parse_and_validate(raw)
        if record is not None:
            return {"record": record, "attempts": attempt, "errors": errors, "raw": raw, "mode": mode}
        errors.append(err)
        extra = [{"role": "assistant", "content": raw}, {"role": "user", "content": err}]
    return {"record": None, "attempts": max_retries + 1, "errors": errors, "raw": raw, "mode": mode}


def success_rate(client, model, doc_text, mode: str, runs: int = 5) -> dict:
    """Run one level several times and count how often the reply parses AND validates.
    A tiny evaluation: Session 17 builds the full version."""
    ok = 0
    for _ in range(runs):
        record, _err = parse_and_validate(LEVELS[mode](client, model, doc_text))
        ok += record is not None
    return {"mode": mode, "ok": ok, "runs": runs}
