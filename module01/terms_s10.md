# Terms from Session 10 — what they are, and where they come back

| Term | What it is | Say it as | Comes back at |
|---|---|---|---|
| API (hosted API) | A service you call over the internet; the provider runs the model. | Someone else's machine. | S11; every lab |
| Vendor API / closed model | A model only its vendor runs; weights not downloadable. | You rent it. | Module 12 cloud platforms |
| Frontier model | The most capable models available at a given time, mostly closed. | The top of the range. | S37 SDK selection; S54 routing |
| Model family and tier | A vendor's line-up: flagship, mid-tier, economy — same brand, different size, price, speed. | Same family, different size. | S54 routing and fallbacks |
| Open-weight | The trained numbers (weights) are published and downloadable. | You can take it home. | S12 |
| Open-source vs open-weight | Open-source would also release code and training data; open-weight releases only the weights, under a licence that may restrict use. | Read the licence. | S12; S57 |
| Hosted open-weight | A provider (e.g. Groq) runs published weights for you. | Open model, rented compute. | S11 multi-provider |
| Self-hosted / on-premises | You run the model on your own hardware, where the data lives. | You run it, you secure it. | S12; S57; Module 12 |
| Parameters | The learned numbers inside a model; 3B, 20B, 120B = billions of them. | Model size. | S12 quantization and memory |
| Mixture-of-experts (MoE) | Many parameters in total, only a fraction active per token. Fast for the size. | Big library, few books opened per question. | S12 |
| Max output tokens | A separate, smaller limit on how long one answer can be. | The answer's ceiling. | S11 `max_tokens` |
| Time to first token (TTFT) | Delay before the first visible token. Includes hidden thinking for reasoning models. | How long until it starts. | S22 streaming; S53 observability |
| Tokens per second | Output speed once it starts. | How fast it talks. | S22; S54 |
| Price per million tokens | How providers bill; input and output priced separately. | Two prices, not one. | S53 cost tracking; S54 |
| Cached input / batch API | Discounts: repeated prompt prefixes cost less; asynchronous batch jobs cost about half. | Ways to pay less for the same tokens. | S38; S54 |
| Reasoning tokens | Hidden thinking tokens, billed as output. | You pay to think. | S15; S34 budgets |
| Benchmark / leaderboard | A public test score for models. Useful to shortlist; contamination and narrow tasks make it unreliable to decide. | A hint, not a verdict. | S17 your own golden set; S52 |
| Hard constraint | A requirement that removes options before any scoring (residency, latency limit, capacity). | Pass or out. | S37; S40; S61 capstone design |
| Weighted score | Combining cost, speed and quality with weights that reflect the business. | Who chooses the weights matters. | S37; S54 |
| Data residency | Rules on where data may be processed or stored. | Where may it go? | S57; Module 12 |
