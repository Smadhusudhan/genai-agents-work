# Terms from Session 11 — what they are, and where they come back

| Term | What it is | Say it as | Comes back at |
|---|---|---|---|
| Messages list | The conversation sent to a model: a list of role/content pairs. | The whole conversation, not just the question. | Every session |
| system / user / assistant roles | Who is speaking in each message. system sets the model's behaviour; user is the human; assistant is the model's own prior replies. | Who said what. | S19 chat state; Module 6 agents |
| temperature | How much randomness goes into picking the next token. 0 is close to deterministic. | The randomness dial. | S34 agents (kept low for tool selection) |
| top_p | An alternative way to shape the same randomness, by probability mass. | A different dial, same job. | Rarely used alongside temperature |
| max_tokens | A hard ceiling on how long the reply can be. | The answer's ceiling. | S10 (reasoning models eating the budget) |
| stop sequence | A string that ends generation the instant it appears. | A tripwire for the output. | Structured-output labs |
| Provider-agnostic code | Code that works unchanged against any provider because only config (BASE_URL, API_KEY, MODEL) changes. | Swap the plug, not the appliance. | Module 12 deployment |
| OpenAI-compatible endpoint | An API that speaks the same request/response shape as OpenAI's, even from a different vendor. | Same language, different speaker. | S12 local models |
