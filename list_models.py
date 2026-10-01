"""Which models can my key use?  Run:  uv run python list_models.py"""
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
for m in sorted(x.id for x in client.models.list()):
    print(m)
