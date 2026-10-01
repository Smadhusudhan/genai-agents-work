import importlib.util
import os
from pathlib import Path

module_path = Path(__file__).resolve().parent / "module01" / "tokens_utils.py"
spec = importlib.util.spec_from_file_location("tokens_utils", module_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load tokens_utils from {module_path}")

tokens_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tokens_utils)

chat_client = tokens_utils.chat_client
ollama_client = tokens_utils.ollama_client
usage_for = tokens_utils.usage_for
count_tokens = tokens_utils.count_tokens

MODEL = os.getenv("MODEL")
groq = chat_client()
ollama = ollama_client()
print("chat model:", MODEL)

TEXTS = {
    "english": "Can I get a personal loan of 8 lakh rupees for five years?",
    "telugu": "నాకు ఐదు సంవత్సరాలకు 8 లక్షల రూపాయల వ్యక్తిగత రుణం లభిస్తుందా?",
    "python": "def emi(p, r, n):\n    r = r/12/100\n    return p*r*(1+r)**n/((1+r)**n-1)",
    "json": '{"pan": "ABCDE1234F", "amount": 800000, "tenure_months": 60}',
}


def usage(client, model, text):
    return usage_for(client, model, text)[0]


overhead_groq = usage(groq, MODEL, "hi") - count_tokens("hi")
print(f"{'text':8} {'tiktoken':>9} {'groq usage':>11} {'minus wrapper':>14} {'ollama usage':>13}")
for name, t in TEXTS.items():
    est = count_tokens(t)
    g = usage(groq, MODEL, t)
    try:
        o = usage(ollama, "llama3.2:3b", t)
    except Exception as e:
        o = f"(no ollama: {type(e).__name__}: {e})"
    print(f"{name:8} {est:9d} {g:11d} {g - overhead_groq:14d} {o:>13}")
