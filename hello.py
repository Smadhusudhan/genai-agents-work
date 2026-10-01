"""Session 2 — your first LLM call. Run with:  uv run python hello.py"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is missing — copy .env.example to .env and fill in the real value.")
    value = value.strip()
    if "#" in value:
        value = value.split("#", 1)[0].rstrip()
    if name == "API_KEY" and value.startswith(("'", '"')):
        raise RuntimeError("API_KEY must not be wrapped in quotes in .env.")
    if name == "API_KEY" and "paste_your" in value.lower():
        raise RuntimeError("API_KEY is still a placeholder — replace it in .env.")
    return value


client = OpenAI(base_url=_require_env("BASE_URL"), api_key=_require_env("API_KEY"))
MODEL = _require_env("MODEL")

stream = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "You are a concise assistant for a retail bank."},
        {"role": "user", "content": "Say hello and tell me one thing AI agents can do."},
    ],
    stream=True,
    stream_options={"include_usage": True},
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
    if chunk.usage:
        u = chunk.usage
        print(f"\n\nprompt={u.prompt_tokens} completion={u.completion_tokens} total={u.total_tokens}")
        break