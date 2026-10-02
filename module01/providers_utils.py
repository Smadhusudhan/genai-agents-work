"""Session 11 helpers — three providers, one client library, and a tiny classifier
used for the temperature sweep. Imported by the notebook and the test."""
from __future__ import annotations

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)  # .env wins over anything an editor put in the environment

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def groq_client() -> OpenAI:
    """The provider pinned in .env for the rest of the course (default: Groq)."""
    return OpenAI(base_url=os.getenv("BASE_URL"), api_key=os.getenv("API_KEY"))


def gemini_client() -> OpenAI:
    """Google's official OpenAI-compatible endpoint. Needs GEMINI_API_KEY in .env,
    from a free key at aistudio.google.com. Same client library, different base_url."""
    key = os.getenv("GEMINI_API_KEY")
    if not key or "paste_your" in key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env — see the .env.example block.")
    return OpenAI(base_url=GEMINI_BASE_URL, api_key=key)


def ollama_client() -> OpenAI:
    """Local Ollama. No key, no internet."""
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")


def list_gemini_models() -> list[str]:
    """Model names change often on Gemini's Flash tier. Run this instead of trusting
    a name written down months ago — same idea as list_models.py for Groq."""
    client = gemini_client()
    return sorted(m.id for m in client.models.list() if "flash" in m.id.lower())


# ---------------------------------------------------------------- one call, any provider
def ask(client: OpenAI, model: str, system: str, user: str, *, temperature: float = 0.0,
        max_tokens: int = 200, stop: list[str] | None = None) -> dict:
    """The one function every provider slide boils down to: same shape, different client."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    if stop:
        kwargs["stop"] = stop
    r = client.chat.completions.create(**kwargs)
    
    return {
        "text": r.choices[0].message.content,
        "prompt_tokens": r.usage.prompt_tokens,
        "completion_tokens": r.usage.completion_tokens,
        "total_tokens": r.usage.total_tokens,
    }


# ---------------------------------------------------------------- the temperature-sweep classifier
CLASSIFIER_SYSTEM = (
    "You classify a customer support ticket into exactly one category: "
    "billing, technical, or general. Reply with only that one word, nothing else."
)


def classify_ticket(client: OpenAI, model: str, ticket_text: str, *, temperature: float = 0.0) -> dict:
    """Same shape as ask(), specialised for the sweep: one word in, one label out."""
    result = ask(client, model, CLASSIFIER_SYSTEM, ticket_text, temperature=temperature, max_tokens=300)
    label = result["text"].strip().lower().strip(".")
    return {**result, "label": label, "valid": label in {"billing", "technical", "general"}}
