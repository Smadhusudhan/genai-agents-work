"""Session 10 helpers - model catalog, monthly cost, hard constraints, weighted scoring, latency and quality checks.
Imported by the notebook and the test. No network is needed except time_stream()."""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

CATALOG = Path(__file__).with_name("models_catalog.json")
USD_TO_INR = 84.0          # edit
DAYS = 30

# ---------------------------------------------------------------- catalog
def load_catalog() -> list[dict]:
    return json.loads(CATALOG.read_text())["models"]


# ---------------------------------------------------------------- scenarios (the loan assistant, three jobs)
SCENARIOS = {
    "faq": {
        "title": "Public product FAQ chatbot",
        "calls_per_day": 20_000, "in_tokens": 1_200, "out_tokens": 200,
        "needs_on_prem": False, "max_latency_s": None, "min_ctx": 8_000,
        "weights": {"cost": 0.6, "latency": 0.2, "quality": 0.2}, "min_quality": 2,
    },
    "documents": {
        "title": "Loan-document analysis (customer PII)",
        "calls_per_day": 2_000, "in_tokens": 6_000, "out_tokens": 500,
        "needs_on_prem": True, "max_latency_s": None, "min_ctx": 16_000,
        "weights": {"cost": 0.2, "latency": 0.2, "quality": 0.6}, "min_quality": 3,
    },
    "agent_assist": {
        "title": "Call-centre agent-assist (live suggestions)",
        "calls_per_day": 30_000, "in_tokens": 1_500, "out_tokens": 150,
        "needs_on_prem": False, "max_latency_s": 3.0, "min_ctx": 8_000,
        "weights": {"cost": 0.2, "latency": 0.5, "quality": 0.3}, "min_quality": 3,
    },
}


# ---------------------------------------------------------------- cost
def monthly_cost_usd(model: dict, calls_per_day: int, in_tokens: int, out_tokens: int, days: int = DAYS):
    """Per-token bill plus any fixed monthly cost. None if a needed price is unknown."""
    if model.get("price_in") is None or model.get("price_out") is None:
        return None
    calls = calls_per_day * days
    variable = (calls * in_tokens * model["price_in"] + calls * out_tokens * model["price_out"]) / 1_000_000
    return round(variable + (model.get("fixed_monthly_usd") or 0), 2)


def monthly_cost_inr(model: dict, scenario: dict):
    usd = monthly_cost_usd(model, scenario["calls_per_day"], scenario["in_tokens"], scenario["out_tokens"])
    return None if usd is None else round(usd * USD_TO_INR)


# ---------------------------------------------------------------- hard constraints, then weighted score
def eligible(model: dict, scenario: dict, overrides: dict | None = None) -> tuple[bool, list[str]]:
    m = {**model, **((overrides or {}).get(model["id"], {}))}
    why = []
    if scenario["needs_on_prem"] and not m["runs_on_prem"]:
        why.append("data must stay on-prem; this model's provider sees the prompt")
    if scenario["max_latency_s"] is not None and m["latency_s"] > scenario["max_latency_s"]:
        why.append(f"too slow ({m['latency_s']} s > {scenario['max_latency_s']} s)")
    cap = m.get("max_calls_per_day")
    if cap and scenario["calls_per_day"] > cap:
        why.append(f"cannot serve {scenario['calls_per_day']:,} calls/day (this setup tops out near {cap:,})")
    if m["ctx_tokens"] < scenario["min_ctx"]:
        why.append("context window too small")
    if m["quality"] < scenario["min_quality"]:
        why.append(f"quality {m['quality']} below the minimum {scenario['min_quality']}")
    if monthly_cost_usd(m, scenario["calls_per_day"], scenario["in_tokens"], scenario["out_tokens"]) is None:
        why.append("a price is unknown - fill it in")
    return (not why), why


def _norm_low_is_good(v, lo, hi):
    return 1.0 if hi == lo else 1 - (v - lo) / (hi - lo)


def _norm_cost(v, lo, hi):
    """Costs span orders of magnitude (Rs 0 to Rs 5,00,000+). On a straight scale one expensive outlier makes
    every cheap model look identical, so we compare on a log scale."""
    return _norm_low_is_good(math.log1p(v), math.log1p(lo), math.log1p(hi))


def rank(scenario: dict, catalog: list[dict] | None = None, overrides: dict | None = None):
    """Returns (ranked, excluded). ranked: list of dicts with score 0-100; excluded: list of (name, reasons)."""
    catalog = catalog or load_catalog()
    ok, out = [], []
    for base in catalog:
        m = {**base, **((overrides or {}).get(base["id"], {}))}
        good, why = eligible(base, scenario, overrides)
        if good:
            m["cost_usd"] = monthly_cost_usd(m, scenario["calls_per_day"], scenario["in_tokens"], scenario["out_tokens"])
            ok.append(m)
        else:
            out.append((m["name"], why))
    if not ok:
        return [], out
    costs = [m["cost_usd"] for m in ok]; lats = [m["latency_s"] for m in ok]
    w = scenario["weights"]
    for m in ok:
        c = _norm_cost(m["cost_usd"], min(costs), max(costs))
        l = _norm_low_is_good(m["latency_s"], min(lats), max(lats))
        q = (m["quality"] - 1) / 4
        m["score"] = round(100 * (w["cost"] * c + w["latency"] * l + w["quality"] * q), 1)
        m["cost_inr"] = round(m["cost_usd"] * USD_TO_INR)
    return sorted(ok, key=lambda m: m["score"], reverse=True), out


# ---------------------------------------------------------------- the same prompt on every model
PROMPT = ("Applicant earns Rs 60,000 per month and already pays Rs 8,000 per month in EMIs. "
          "She asks for a Rs 8,00,000 personal loan at 11.5% per annum for 60 months. "
          "Compute the monthly EMI, then say whether (EMI + existing EMIs) is under 50% of her income. "
          "Answer in three short lines.")


def emi(principal: float, annual_rate_pct: float, months: int) -> float:
    r = annual_rate_pct / 12 / 100
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


EXPECTED_EMI = round(emi(800_000, 11.5, 60), 2)
EXPECTED_RATIO = round((EXPECTED_EMI + 8_000) / 60_000 * 100, 1)


def numbers_in(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", text) if x.replace(",", "").replace(".", "").isdigit()]


def check_answer(text: str) -> dict:
    """Did the model get the EMI (within 1%) and the EMI-to-income ratio (within 0.6 points)?"""
    nums = numbers_in(text)
    emi_ok = any(abs(n - EXPECTED_EMI) <= 0.01 * EXPECTED_EMI for n in nums)
    ratio_ok = any(abs(n - EXPECTED_RATIO) <= 0.6 for n in nums)
    return {"emi_ok": emi_ok, "ratio_ok": ratio_ok, "score_out_of_2": int(emi_ok) + int(ratio_ok)}


RUBRIC = """Quality rubric (1-5), fill in yourself after reading the answer:
 5  EMI and ratio both right, exactly three short lines, clear yes/no on the 50% test
 4  Both numbers right but format or wording off
 3  One number right, or right numbers with a wrong conclusion
 2  Both numbers wrong but the method is visible
 1  Wrong and confident, or no answer"""


# ---------------------------------------------------------------- latency (needs a live client)
def time_stream(client, model: str, prompt: str = PROMPT, max_tokens: int = 1500) -> dict:
    """Stream one answer; return time to first visible token, total time, tokens and speed."""
    t0 = time.perf_counter(); first = None; text = []; usage = None
    kwargs = dict(model=model, max_tokens=max_tokens, stream=True, messages=[{"role": "user", "content": prompt}])
    try:
        stream = client.chat.completions.create(stream_options={"include_usage": True}, **kwargs)
    except Exception:
        stream = client.chat.completions.create(**kwargs)
    chunks = 0
    for ch in stream:
        if ch.choices and ch.choices[0].delta.content:
            if first is None:
                first = time.perf_counter() - t0
            text.append(ch.choices[0].delta.content); chunks += 1
        if getattr(ch, "usage", None):
            usage = ch.usage
    total = time.perf_counter() - t0
    out_tokens = usage.completion_tokens if usage else chunks
    return {"ttft_s": round(first or total, 2), "total_s": round(total, 2), "completion_tokens": out_tokens,
            "tokens_per_s": round(out_tokens / total, 1) if total else 0, "text": "".join(text)}
