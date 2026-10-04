# Pre-read for Session 12 — ten minutes

**Before class:** pull a second local model so the lab has something to compare against `llama3.2:3b`:
```powershell
ollama pull qwen2.5:7b
```
About 4-5 GB — do this on good Wi-Fi, not in the classroom.

**Where open-weight models actually come from.** Hugging Face is the public library most open-weight models are published to — Meta's Llama family, Alibaba's Qwen family, and OpenAI's own gpt-oss all have pages there. Ollama does not train anything; it packages models from sources like this into a format that runs easily on a laptop. The same weights can appear in three places with three different names: `meta-llama/Llama-3.2-3B-Instruct` on Hugging Face, `llama3.2:3b` as an Ollama tag, and (if a provider hosts it) under its own naming on a service like Groq.

**Quantization, properly.** A model's weights are numbers; quantization stores each number with fewer bits. Going from 16-bit to 4-bit roughly quarters the memory needed, at a real but usually small cost in accuracy. This is the entire reason a 20-billion-parameter model can run on a laptop at all — at full 16-bit precision it would need about 40 GB; quantized to 4-bit, about 10 GB.

**Not every small model can call tools.** Function/tool calling — the mechanism agents depend on — is a capability some models are specifically trained for and others aren't. A small model might produce a perfectly fluent sentence describing what it *would* do, without ever emitting the structured call your code is waiting for. This matters directly once Module 6 starts: an agent built on a model that can't reliably call tools isn't an agent.

**Three questions to arrive with**
- Why would a bank care whether a model can run entirely on a laptop, even though a hosted model is faster?
- If your laptop has 8 GB of RAM, roughly how large a model (at 4-bit) can you realistically run?
- A model's page on Hugging Face says "gated — request access." What do you think that means?
