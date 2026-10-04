# Showcase A2 — Insurance (row A: workflow)

Part of the course's 4x4 showcase matrix: row A (workflow — the **code** decides the
steps), column Insurance.

**The pipeline:**

```
free-text claim  -->  model extracts a structured form  -->  code routes by severity  -->  template answers
                       (tokens in, JSON out)                 (no model involved)
```

The model is given one job — read messy human text and turn it into a fixed JSON
shape. It never decides what happens *after* that. A plain Python `if` reads the
`severity` and `injuries` fields and picks one of two canned responses. That fixed,
code-decided sequence is what makes this a **workflow**, not an agent — compare with
row B (`showcase/b2_insurance`, from Session 21 onward), where the model itself
chooses which tool to call next on the same kind of problem.

## Files

| File | What it is |
|---|---|
| `claims_data.py` | Eight mock claim descriptions, free text, as a customer would actually type them — a spread of minor, major, injury, no-injury, and one ambiguous and one suspicious case. |
| `insurance_claim.py` | The pipeline: `extract_claim_form` (the only step that calls the model), `route_claim` (plain code, no model), and `process_claim` (runs both in order and prints what happened at each step). |
| `test_a2_insurance.py` | Offline tests for the schema and the router; two live tests (skipped automatically with no API key) that check real extraction on a clear minor and a clear major claim. |

## Run it

```powershell
# one claim, with full step-by-step output including the token count
uv run python showcase/a2_insurance/insurance_claim.py

# a specific claim
uv run python showcase/a2_insurance/insurance_claim.py --claim major_injury

# every mock claim in one run
uv run python showcase/a2_insurance/insurance_claim.py --all

# checkpoint
uv run pytest showcase/a2_insurance/test_a2_insurance.py
```

Uses the same `.env` as everything else in the repo — no extra setup.

## What to watch for when you run it

- The **TOKENS** line after the extraction step — that is the only point in the whole
  pipeline where a model is called, and it is where the cost comes from.
- The **ROUTE** line is decided entirely by `route_claim()`, which takes only a
  `ClaimForm` — not a client, not raw text. It has no way to call the model even if it
  wanted to. That is the workflow boundary, made concrete.
- Try `--claim ambiguous_whiplash` or `--claim fraud_flag_suspicious` — these are
  written to be borderline on purpose, so you can see how the model's judgement (not
  a hardcoded rule) decides the severity field.
