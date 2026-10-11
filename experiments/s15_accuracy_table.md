# Session 15 - loan eligibility, ten cases (2026-10-11)

Model: `openai/gpt-oss-20b`. Strategies: plain, cot, stepback, vote x5. A cell shows the answer, and ok or WRONG against the answer key.

| Case | Right answer | plain | cot | stepback | vote x5 |
|---|---|---|---|---|---|
| L01-clean | approve | approve ok | approve ok | - | - |
| L02-ratio-narrow | decline | decline ok | decline ok | - | - |
| L03-score-699 | decline | decline ok | decline ok | decline ok | - |
| L04-boundaries | approve | approve ok | approve ok | approve ok | approve ok |
| L05-age-at-end | decline | decline ok | decline ok | - | - |
| L06-age-60 | approve | approve ok | approve ok | - | - |
| L07-existing-emis | decline | decline ok | decline ok | - | - |
| L08-two-fail | decline | decline ok | decline ok | decline ok | - |
| L09-large-numbers | approve | approve ok | approve ok | - | - |
| L10-months | approve | approve ok | approve ok | - | - |
| **Right** | | 10/10 | 10/10 | 3/3 | 1/1 |
| **Average tokens per case** | | 468 | 773 | 1,653 | 3,809 |
