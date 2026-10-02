# Pre-read — ten minutes

**The idea in one sentence.** A provider is a place where a model runs; a model is which brain answers. Your code should only ever need to know three things to talk to either: where (`BASE_URL`), who (`API_KEY`), and which (`MODEL`).

**Why a second provider at all.** If your code only ever worked with one vendor, you would not know whether it is genuinely provider-agnostic or just happens to work with one vendor's defaults. Today you prove it by running the exact same function against Groq, Gemini and (optionally) your own laptop.

**Getting a Gemini key.** Go to aistudio.google.com, sign in with any Google account, click "Get API key", create one. No card required, generous free tier. Google also publishes an official OpenAI-compatible endpoint for it, so the same client library you already use works unchanged — only the `base_url` and the key differ.

**The sampling controls, briefly.**
- `temperature` — how much randomness goes into picking the next token. 0 is as close to "always pick the most likely token" as a provider allows.
- `top_p` — a different way of shaping the same randomness; rarely combined with temperature.
- `max_tokens` — a hard ceiling on the length of the reply. Too low on a reasoning model can mean an empty visible answer.
- `stop` — end generation the instant a given string appears in the output.

**Why temperature matters for a routing decision.** If your system classifies a support ticket into "billing" or "technical", that decision should not depend on a coin flip. Today's lab deliberately runs the same ticket several times at several temperatures so you can see — not just hear — where it starts to drift.

**One question to arrive with:** if your code never changes when you switch providers, what exactly does change?
