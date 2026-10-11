# Pre-read for Session 15 — ten minutes

**Session 14 was about what you say. Session 15 is about whether to ask the model to think.** Thinking is not free: every word a model writes before its answer is billed, takes time, and can be wrong. So the question is never "does thinking help?" It is "does it help *this* kind of question, by enough to pay for?"

**Four ways to ask the same question**
- **Plain** — "Reply with only the final answer." One call, the cheapest.
- **Step by step (chain of thought)** — "Think step by step, then answer." One call, longer reply. It helps most when the answer needs several linked steps that a model would otherwise jump over.
- **Step back** — first ask for the *rules and formulas* that apply, in a call that is not allowed to solve anything; then solve with those rules in front of it. Two calls. It helps when the trap is knowing which rule applies.
- **Self-consistency (voting)** — ask the step-by-step question several times at a temperature above zero and take the most common answer. N calls for one answer. It buys reliability with money, and only works when there is one checkable answer to vote on.

**Some models already think.** The model you have used since Session 2 is a *reasoning model*: before it writes its visible answer it produces hidden working, and you pay for those tokens as output. So "think step by step" asks it to do something it has already started to do, and the visible working may add little. A small local Llama does not think first, so the same sentence can change its answers a lot. We do not guess which is which: today you measure it, on your own screen, and the numbers are the lesson. Some reasoning models also have a dial, `reasoning_effort` (low, medium, high), that trades cost and delay against care.

**What thinking cannot do**
- It cannot recover a rule the model was never told. A bank's own convention ("UPI problems are `account`") is taught with *examples* or *context*, as in Session 14. Thinking harder about a rule you did not supply just produces a more confident wrong answer.
- It cannot be exact where a machine can be. If a calculator can do the sum, give the model a calculator (Session 20, function calling). Do not pay for a vote on arithmetic.
- It does not make an output private. Working written out can repeat things the reply must never reveal. Today's pattern: ask for working inside `<scratchpad>` tags and the real reply inside `<final>` tags; your code strips the scratchpad, runs the acceptance checks on `<final>` only, and never shows or stores the scratchpad where a customer can read it.

**Measure, do not argue.** Today's job is a loan-eligibility checker: one policy, ten applicants, each hiding a different trap (a value exactly on a limit, a term given in months, a rule that fails quietly). Every strategy gets the same ten cases, each with one correct answer that Python worked out independently. For each you read three numbers: right or wrong, tokens, seconds. Then a fourth, which is what finance asks: *what does a thousand of these cost?* At 200,000 questions a month, a strategy that costs five times as much is not a detail.

**Free-plan limits, so nothing surprises you.** A free Groq key allows roughly 8,000 tokens a minute and 200,000 a day for this model (October 2026; limits change). The notebook waits politely when the provider says "slow down", remembers every answer on disk so a re-run costs nothing, and shows a meter of what you have spent. If you see "daily limit", stop; your saved answers are not lost.

**What you commit.** An accuracy table for the ten cases (`experiments/s15_accuracy_table.md`), and version 2 of two prompts in the library you made in Session 14, each with a one-line reason in numbers. You promised never to overwrite an old library entry: v2 is added beside v1, and nothing in v1 is edited.

**Three questions to arrive with**
- A model answers a three-step arithmetic question correctly with no working shown. Where might the working have happened, and who paid for it?
- Why can five votes on a question with a *wrong rule* never reach the right answer?
- Your reply must never mention an internal score. Is it safe to let the model write its reasoning in a log customers can read? Why not?
