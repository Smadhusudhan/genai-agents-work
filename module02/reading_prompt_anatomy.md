# Pre-read for Session 14 — ten minutes

**The model is the same. The words change everything.** Sessions 9–13 were about the model: what it sees, which one to pick, where it runs. Module 2 is about what you say to it. A model given "Write a reminder." has to guess the audience, the length, the facts and the tone. A model given a good prompt does not guess. That is the cheapest improvement in AI engineering: it costs nothing, takes minutes, and should always be tried before anything expensive.

**A prompt has parts.** Five you should always think about, plus one optional:
- **Role** — who the model is and who it is writing for. It sets vocabulary and level.
- **Task** — what to do, in one sentence that starts with a verb.
- **Context** — the facts and rules the model *cannot know*: your policy text, your definitions, the situation. If it isn't in the prompt, the model does not have it.
- **Constraints** — limits it must respect: length, what to include, what to never reveal.
- **Output format** — the exact shape of the reply: three bullet lines, a single word, JSON with these keys.
- **Examples** (optional) — worked input/output pairs.

In a chat request, the standing rules (role, constraints, format) usually go in the **system** message and the job (task, context, the actual input) in the **user** message. Examples become earlier user/assistant turns.

**Zero-shot, one-shot, few-shot.** Zero-shot is an instruction with no examples. One-shot adds one worked example; few-shot adds several. Examples are the best way to teach a *house convention*, such as "UPI problems are 'account', address changes are 'other'" — rules that are obvious to your bank and invisible to the model. The price: examples are tokens, and you pay for them on every call.

**"Better" needs a number.** "This looks better" is an opinion. An **acceptance check** is a small test of an output — at most 80 words, mentions the application reference, never contains the internal score, parses as JSON. Write the checks first, then improve the prompt until they pass. This is the seed of the evaluation work in Session 17.

**A prompt is an asset.** Someone will edit your prompt next month and not know why it says what it says. So keep each version, the output it produced, and the checks it passed, in a file under version control. Never edit an old entry; add a new one. That file is your **prompt library**, and it is what you will hand in today.

**Your own repository.** Today you also create your own GitHub repository and push to it for the first time. Two folders, two jobs: the course repository is where you *pull* from; your work repository is where you *push* to. Read `module02/work_repo_steps.md` before class.

**Three questions to arrive with**
- A model answers a customer message with three paragraphs and an emoji. Which two parts of the prompt would you add first?
- Why can't a model follow a policy it has never been shown, however capable it is?
- Why keep an old version of a prompt that no longer works?
