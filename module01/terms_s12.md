# Terms from Session 12 — what they are, and where they come back

| Term | What it is | Say it as | Comes back at |
|---|---|---|---|
| Hugging Face | The public hub where open-weight models, datasets and tokenizers are published. | Where open models come from. | S24 (choosing an embedding model) |
| Model card | A page describing a model: its training, intended use, licence, limitations. | The model's label. | S12; S57 governance |
| Gated model | A model that requires requesting access and agreeing to a licence before downloading. | Ask permission first. | S12; S57 |
| Quantization | Storing each weight with fewer bits to shrink memory, at a small accuracy cost. | Squeezing the numbers. | S10 (preview); every local-model decision |
| Precision (fp32/fp16/int8/int4) | How many bits represent each weight. | The size of each number. | S12 |
| Tool / function calling (local capability) | Whether a specific model reliably emits structured tool-call output rather than just describing one. | Can it actually press the button? | Module 6 (agents) |
| Tokens per second (local) | Output speed on your own hardware, measured, not assumed. | How fast your laptop talks. | S22 streaming; S53 |
| Ollama tag | The short name Ollama uses for a pulled model, e.g. llama3.2:3b. | The local nickname. | Every local-model session |
