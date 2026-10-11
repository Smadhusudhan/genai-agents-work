"""Session 15 problems. Each one needs several steps of arithmetic or rule-following, has ONE correct answer that
Python can check, and hides a trap that a rushed answer falls into. Everything is synthetic: fictional people, fake
numbers. The healthcare problem is a teaching exercise with an invented formulary, not medical advice.

The correct answers are computed here from the same rules the problem text states, and tests/test_s15.py checks
them again against hand-worked numbers, so a wrong "truth" cannot hide in this file."""
from __future__ import annotations

from dataclasses import dataclass

from prompt_tasks import CLASSIFY_INSTRUCTION, COMPLAINTS_TEST, read_label
from prompt_utils import PromptSpec
from reasoning_utils import extract_final


@dataclass
class Problem:
    id: str
    domain: str
    title: str
    text: str
    kind: str                  # "number" or "label"
    truth: object
    answer_format: str         # goes into the prompt: what <answer> should look like after "FINAL:"
    tol: float = 0.0           # numbers: how far off still counts as right
    labels: tuple = ()         # labels: the allowed words
    trap: str = ""             # instructor note: the mistake a rushed answer makes


# ---------------------------------------------------------------- worked-out truths (kept as functions so they can be read)
def _retail_total() -> float:
    subtotal = 2 * 1499 + 2999                                  # 5,997
    after = subtotal * 0.85 if subtotal >= 5000 else subtotal   # 15% off at 5,000 or more
    after = after - 200 if after > 4000 else after              # Rs 200 coupon if still above 4,000
    gst = after * 0.18                                          # GST on the discounted amount
    shipping = 0 if after >= 4500 else 99                       # free shipping from 4,500; shipping carries no GST
    return after + gst + shipping


def _insurance_payout() -> float:
    bill, rent, cap = 240_000, 8_000, 5_000
    eligible = bill * (cap / rent) if rent > cap else bill      # proportionate deduction on the WHOLE bill
    return (eligible - 10_000) * 0.90                            # deductible first, then 10% co-pay


def _loan_truth(age: int, years: int, income: int, existing: int, new: int, score: int) -> str:
    """Integer arithmetic on purpose: 'at most 40%' must be exact when the ratio is exactly 40%."""
    ratio_ok = (existing + new) * 100 <= 40 * income
    score_ok = score >= 700
    age_ok = age + years <= 60                                   # age at the END of the term
    return "approve" if ratio_ok and score_ok and age_ok else "decline"


def _bayes_percent() -> float:
    from_a, from_b = 0.60 * 0.02, 0.40 * 0.05
    return from_a / (from_a + from_b) * 100


def _dosage_ml() -> float:
    per_dose_mg = 18 * 15 / 3
    assert per_dose_mg <= 200
    return per_dose_mg / 125 * 5


def _proration_extra() -> float:
    days = 30 - 12 + 1                                           # day 12 to day 30, both included
    return (999 - 599) * days / 30


def _emi() -> float:
    p, r, n = 500_000, 0.01, 36
    return p * r * (1 + r) ** n / ((1 + r) ** n - 1)


# ---------------------------------------------------------------- the warm-up shown live
DEMO = Problem(
    id="D0-jacket", domain="Retail", title="Two discounts and a coupon",
    text=("A jacket is priced at Rs 2,000. The shop takes 20% off, then takes a further 10% off the REDUCED price, "
          "and then subtracts a Rs 100 coupon. What does the customer pay, in rupees?"),
    kind="number", truth=2_000 * 0.8 * 0.9 - 100, tol=0.5, answer_format="the amount in rupees, as a number",
    trap="20% then 10% is not 30%: the second discount applies to the reduced price.")

# ---------------------------------------------------------------- the main set: a loan-eligibility checker, ten cases
LOAN_POLICY = ("Policy: approve a personal loan only if ALL three hold: (a) total monthly EMIs, existing plus the new one, are at most "
               "40% of monthly income; (b) the credit score is 700 or more; (c) the borrower's age at the END of the loan term is "
               "at most 60. Otherwise decline.")


def _inr(n: int) -> str:
    """Indian digit grouping: 120000 -> 1,20,000."""
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail, groups = s[:-3], s[-3:], []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def _loan_case(code, title, name, age, income, existing, new, term_text, years, score, trap) -> Problem:
    text = (f"{LOAN_POLICY}\nApplicant: {name}, age {age}, monthly income Rs {_inr(income)}, existing EMIs Rs {_inr(existing)}, "
            f"new loan EMI Rs {_inr(new)}, term {term_text}, credit score {score}.\nWhat is the decision?")
    return Problem(id=code, domain="BFS", title=title, text=text, kind="label",
                   truth=_loan_truth(age, years, income, existing, new, score), labels=("approve", "decline"),
                   answer_format="exactly one word: approve or decline", trap=trap)


LOAN_CASES = [
    _loan_case("L01-clean", "A clean approval", "Meera Nair", 32, 120_000, 10_000, 25_000, "5 years", 5, 760,
               "No trap: a control case."),
    _loan_case("L02-ratio-narrow", "Ratio just over the limit", "Imran Qureshi", 40, 80_000, 12_000, 21_000, "6 years", 6, 735,
               "Total EMIs are 41.25% of income: just over 40%."),
    _loan_case("L03-score-699", "One point under the score floor", "Divya Menon", 38, 150_000, 20_000, 30_000, "8 years", 8, 699,
               "A score of 699 is not '700 or more'."),
    _loan_case("L04-boundaries", "Exactly on two limits", "Arjun Patel", 45, 100_000, 15_000, 25_000, "10 years", 10, 700,
               "Ratio is exactly 40% and the score exactly 700: 'at most' and 'or more' both pass."),
    _loan_case("L05-age-at-end", "Age at the end of the term", "Suresh Rao", 54, 90_000, 14_000, 21_500, "7 years", 7, 731,
               "Two rules pass; the third fails quietly: 54 + 7 = 61."),
    _loan_case("L06-age-60", "Age exactly 60 at the end", "Lakshmi Iyer", 50, 110_000, 8_000, 22_000, "10 years", 10, 745,
               "50 + 10 = 60, and 'at most 60' passes."),
    _loan_case("L07-existing-emis", "Existing EMIs count", "Farhan Ali", 30, 60_000, 18_000, 8_000, "5 years", 5, 780,
               "The new EMI alone is 13% of income; with the existing EMIs it is 43.3%."),
    _loan_case("L08-two-fail", "Two rules fail at once", "Nandan Das", 58, 140_000, 10_000, 20_000, "5 years", 5, 640,
               "Score 640 and age at end 63 both fail; a model may stop at the first."),
    _loan_case("L09-large-numbers", "Large numbers, still fine", "Pooja Shah", 38, 250_000, 40_000, 55_000, "15 years", 15, 705,
               "Ratio is 38%, age at end 53: approve, though the numbers look big."),
    _loan_case("L10-months", "A term given in months", "Ravi Teja", 56, 90_000, 9_000, 20_000, "48 months", 4, 712,
               "48 months is 4 years, so age at the end is exactly 60."),
]

# ---------------------------------------------------------------- other domains (a live demo, and section 9 of the notebook)
R1 = Problem(
    id="R1-retail-order", domain="Retail", title="An order with a discount, a coupon, GST and shipping",
    text=("A cart holds 2 headphones at Rs 1,499 each and 1 speaker at Rs 2,999. Apply these rules in this order:\n"
          "1. If the cart subtotal is Rs 5,000 or more, take 15% off the subtotal.\n"
          "2. Then, if the amount after step 1 is above Rs 4,000, subtract a Rs 200 coupon.\n"
          "3. GST of 18% is charged on the amount after steps 1 and 2.\n"
          "4. Shipping is Rs 99, but free if the amount after steps 1 and 2 is Rs 4,500 or more. Shipping carries no GST.\n"
          "What does the customer pay in total, rounded to the nearest rupee?"),
    kind="number", truth=_retail_total(), tol=1.0, answer_format="the total in rupees, rounded to a whole number",
    trap="Rules chain: the coupon test uses the discounted amount, and free shipping is judged BEFORE GST is added.")

R2 = Problem(
    id="R2-insurance-claim", domain="Insurance", title="A hospital claim with a room-rent cap",
    text=("A policyholder's hospital bill is Rs 2,40,000. It includes 5 days of room rent at Rs 8,000 per day. "
          "The policy caps room rent at Rs 5,000 per day. If the rent charged is above the cap, the ENTIRE bill is reduced "
          "in the ratio cap / rent charged (this is called proportionate deduction). After that, a deductible of Rs 10,000 "
          "is subtracted. Then the insurer pays 90% of what is left; the patient pays the other 10% as co-pay. "
          "How much does the insurer pay, in rupees?"),
    kind="number", truth=_insurance_payout(), tol=1.0, answer_format="the insurer's payment in rupees, as a whole number",
    trap="Order matters: deductible BEFORE co-pay gives 1,26,000; co-pay first gives 1,25,000.")

R4 = Problem(
    id="R4-defect-source", domain="Manufacturing", title="Which machine made the defective part?",
    text=("Machine A makes 60% of a factory's parts, and 2% of its parts are defective. Machine B makes the other 40%, "
          "and 5% of its parts are defective. One part is picked at random and it is defective. "
          "What is the probability, as a percentage, that it came from machine A?"),
    kind="number", truth=_bayes_percent(), tol=0.1, answer_format="a percentage as a number, for example 12.5",
    trap="The tempting answer is 60% (machine A's share). The right answer weighs share by defect rate: 37.5%.")

OTHER = [R1, R2, R4]

# ---------------------------------------------------------------- more domains (optional, section 9)
S1 = Problem(
    id="S1-dosage", domain="Healthcare", title="A syrup dose by body weight (invented formulary)",
    text=("Teaching exercise with an invented formulary; not medical advice. A child weighs 18 kg. The daily dose is 15 mg per kg "
          "of body weight, split into 3 equal doses. A single dose must never exceed 200 mg. The syrup contains 125 mg in every "
          "5 mL. How many mL does the child get per dose?"),
    kind="number", truth=_dosage_ml(), tol=0.05, answer_format="millilitres per dose, to one decimal place",
    trap="Per-dose milligrams first (90 mg), then convert to mL; the 200 mg cap is a check, not a number to use.")

S2 = Problem(
    id="S2-telecom-proration", domain="Telecom", title="A mid-cycle plan upgrade",
    text=("A customer is on a Rs 599 plan, billed for a 30-day cycle that starts on day 1. On day 12 they upgrade to a Rs 999 plan; "
          "the new plan applies from day 12, counting day 12 itself. Prorate per day (price / 30). Refund the old plan for "
          "day 12 to day 30 and charge the new plan for the same days. What extra amount is charged, rounded to the nearest rupee?"),
    kind="number", truth=_proration_extra(), tol=1.0, answer_format="the extra amount in rupees, as a whole number",
    trap="Day 12 to day 30 inclusive is 19 days, not 18.")

S3 = Problem(
    id="S3-emi", domain="BFS", title="A reducing-balance EMI",
    text=("A loan of Rs 5,00,000 is repaid in 36 equal monthly instalments at 12% per annum, so the monthly rate r is 1%. "
          "Use EMI = P x r x (1+r)^n / ((1+r)^n - 1), with P the loan amount and n the number of instalments. "
          "What is the EMI, rounded to the nearest rupee?"),
    kind="number", truth=_emi(), tol=1.0, answer_format="the EMI in rupees, as a whole number",
    trap="(1.01)^36 is about 1.4308: a slip there moves the EMI by hundreds of rupees. This is the one to hand to a calculator tool (Session 21).")

STRETCH = [S1, S2, S3]
PROBLEMS = LOAN_CASES + OTHER + STRETCH


def problem_card(p: Problem) -> str:
    return f"=== {p.id}  ({p.domain}): {p.title}\n{p.text}\n"


# ---------------------------------------------------------------- the control: a task that does NOT need thinking
def classify_cot_spec() -> PromptSpec:
    """Same classification job as Session 14, but asking the model to think first. Zero-shot, like classify_spec(0)."""
    task = CLASSIFY_INSTRUCTION.replace(
        "Reply with that single word only.",
        "Think step by step in a few lines, then end with one last line in the form FINAL: <category>.")
    return PromptSpec(task=task)


def score_classifier_lab(lab, spec: PromptSpec, items=COMPLAINTS_TEST, *, mode: str = "plain", max_tokens: int = 1500) -> dict:
    """Run a classifier spec over labelled messages through a Lab, so tokens and seconds are counted.
    mode 'plain' reads the reply as a single word; mode 'cot' reads the label after 'FINAL:'."""
    right = calls = prompt_tokens = completion_tokens = 0
    seconds = 0.0
    wrong = []
    for text, truth in items:
        r = lab.chat(spec.to_messages(text), temperature=0.0, max_tokens=max_tokens)
        calls += 1
        prompt_tokens += r["prompt_tokens"]
        completion_tokens += r["completion_tokens"]
        seconds += r["seconds"]
        if mode == "cot":
            final = extract_final(r["text"])
            label = read_label(final)[0] if final else None
        else:
            label = read_label(r["text"])[0]
        right += label == truth
        if label != truth:
            wrong.append((text, truth, label))
    return {"accuracy": right, "n": len(items), "calls": calls, "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "tokens": prompt_tokens + completion_tokens,
            "seconds": seconds, "wrong": wrong}
