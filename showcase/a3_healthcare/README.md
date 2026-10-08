# Showcase A3 — Healthcare (row A: workflow)

Part of the course's 4x4 showcase matrix: row A (workflow — the **code** decides the steps), column Healthcare.

```
safety rule  ->  intent router  ->  slot filling  ->  booking  ->  confirmation
 (code)          (model reads)      (model reads,      (code)        (template)
                                     CODE decides
                                     what to ask next)
```

A patient messages a clinic's booking assistant. The model does exactly two jobs, both of them *reading*:
which intent is this message, and which appointment details did the patient mention? Everything else
is code: the order of the questions, when enough is known, the availability lookup, the confirmation text —
and a safety rule that runs **before any model is called**.

That ownership is the lesson. Compare row B (`showcase/b3_healthcare`, from Session 29), where the model itself
chooses what to do next on the same kind of problem.

> **Mock data only.** Invented doctors, invented patients. This is not medical advice and not a triage tool;
> the emergency rule exists to demonstrate a code-owned safety check.

## Files

| File | What it is |
|---|---|
| `appointments_data.py` | Mock availability, the emergency keyword list, and seven scripted patient conversations. |
| `appointment_flow.py` | `classify` and `extract` (the only two model calls), `next_missing` / `find_slot` / `has_emergency` (plain code), `run_dialogue` (the whole workflow in order). |
| `test_a3_healthcare.py` | 15 offline tests using a keyword stand-in for the model, plus one live test that skips without a key. |

## Run it

```powershell
uv run python showcase/a3_healthcare/appointment_flow.py                      # happy_path
uv run python showcase/a3_healthcare/appointment_flow.py --scenario emergency
uv run python showcase/a3_healthcare/appointment_flow.py --all
uv run pytest showcase/a3_healthcare/test_a3_healthcare.py                    # checkpoint
```

## What to watch for

- The **`[router -> ...]` and `[slots -> ...]`** lines are the model's work. Everything labelled `bot:` is a template or a code decision.
- Run `--scenario emergency`: the reply appears and **no model call is made at all**. A safety rule the model can't talk its way around.
- Run `--scenario all_in_one`: one message fills every slot, so the code skips straight to booking. The *model* extracted four facts; the *code* noticed nothing was missing.
- Run `--scenario no_matching_slot`: the code offers real alternatives. It cannot invent a slot, because the availability table is code, not language.
