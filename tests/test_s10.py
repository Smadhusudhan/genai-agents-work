"""Session 10 checkpoint. Run with:  uv run pytest tests/test_s10.py
All offline: no API key and no Ollama needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module01"))
from landscape_utils import (EXPECTED_EMI, EXPECTED_RATIO, SCENARIOS, check_answer, eligible,  # noqa: E402
                             emi, load_catalog, monthly_cost_usd, rank)

REQUIRED = {"id", "name", "access", "open_weight", "runs_on_prem", "ctx_tokens", "price_in", "price_out",
            "quality", "latency_s"}


def test_catalog_is_well_formed():
    cat = load_catalog()
    assert len(cat) >= 8
    ids = [m["id"] for m in cat]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for m in cat:
        assert REQUIRED <= m.keys(), f"{m['id']} missing fields"
        assert 1 <= m["quality"] <= 5
        assert m["latency_s"] > 0


def test_monthly_cost_known_value():
    m = {"price_in": 1.0, "price_out": 2.0, "fixed_monthly_usd": 0}
    # 1,000 calls/day x 30 days = 30,000 calls; 1,000 in + 100 out each
    # = 30M in x $1 + 3M out x $2 = $36
    assert monthly_cost_usd(m, 1_000, 1_000, 100) == 36.0
    assert monthly_cost_usd({**m, "fixed_monthly_usd": 500}, 1_000, 1_000, 100) == 536.0
    assert monthly_cost_usd({"price_in": 1.0, "price_out": None}, 1, 1, 1) is None


def test_hard_constraint_removes_cloud_models_for_pii():
    ranked, excluded = rank(SCENARIOS["documents"])
    assert ranked, "at least one on-prem model should remain"
    assert all(m["runs_on_prem"] for m in ranked)
    assert any("on-prem" in " ".join(why) for _, why in excluded)


def test_latency_limit_applies_to_agent_assist():
    ranked, _ = rank(SCENARIOS["agent_assist"])
    assert all(m["latency_s"] <= 3.0 for m in ranked)


def test_unknown_price_is_flagged_not_hidden():
    cat = load_catalog()
    blank = next(m for m in cat if m["price_out"] is None)
    ok, why = eligible(blank, SCENARIOS["faq"])
    assert not ok and any("price" in w for w in why)
    # after the student fills it in, the model is eligible again
    ranked, _ = rank(SCENARIOS["faq"], overrides={blank["id"]: {"price_out": 0.08}})
    assert any(m["id"] == blank["id"] for m in ranked)


def test_scores_are_ordered_and_bounded():
    ranked, _ = rank(SCENARIOS["faq"])
    scores = [m["score"] for m in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)


def test_emi_and_answer_checker():
    assert abs(emi(800_000, 11.5, 60) - 17594.09) < 0.01
    assert EXPECTED_RATIO == 42.7
    good = f"EMI is Rs {EXPECTED_EMI:,.0f} per month. With existing EMIs the ratio is {EXPECTED_RATIO}%, under 50%."
    assert check_answer(good)["score_out_of_2"] == 2
    bad = "The EMI is Rs 9,800 and the ratio is 29%."
    assert check_answer(bad)["score_out_of_2"] == 0


def test_laptop_cannot_serve_production_volume():
    laptop = next(m for m in load_catalog() if m["access"] == "local")
    ok, why = eligible(laptop, SCENARIOS["faq"])
    assert not ok and any("calls/day" in w for w in why)
