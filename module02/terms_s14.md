# Terms from Session 14 — what they are, and where they come back

| Term | What it is | Say it as | Comes back at |
|---|---|---|---|
| Prompt | The text (and examples) sent to a model to get a behaviour. | Your instruction, plus everything it needs. | Every session from here |
| System message | The message that sets standing rules for the whole conversation. | The model's job description. | S19; Module 6 |
| User message | The message carrying this request's task, context and input. | The job on today's desk. | Every session |
| Role | The part of a prompt saying who the model is and who it writes for. | Who is speaking, to whom. | S15; S16 |
| Task | The one-sentence instruction, starting with a verb. | What to do. | Every session |
| Context | Facts and rules the model cannot know, supplied in the prompt. | What it must be told. | M5 RAG (context fetched automatically) |
| Constraints | Limits on length, content, and what must never be revealed. | The fence around the answer. | S18 defensive prompting |
| Output format | The exact shape of the reply (bullets, a word, JSON keys). | The shape of the answer. | S16; S20 |
| Zero-shot / one-shot / few-shot | A prompt with no, one, or several worked examples. | Show it how, in 0, 1 or a few examples. | S15; S16 |
| House convention | A rule obvious inside your organisation but invisible to a model, taught best by examples. | Your bank's own rules of thumb. | S16; S17 |
| Acceptance check | A small piece of code that tests whether an output is good enough. | A test for an answer. | S17 golden sets; S52 evaluations |
| Prompt library | A file of every prompt version, its output and its check results, kept in version control. | The prompt's history. | S16–S18; S38; S54 |
| Prompt versioning | Adding a new version instead of editing an old one. | Never overwrite; add v2. | S54 LLMOps |
| Work repository | Your own Git repository, where you push your work. | Your folder on GitHub. | Every submission |
| Commit / push | Recording a snapshot locally / sending your snapshots to GitHub. | Save a version, then hand it in. | Every submission |
| Remote / origin | The GitHub copy of a repository that your local copy is linked to. | The online twin. | Every submission |
