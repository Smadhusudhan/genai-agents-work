"""Session 2 checkpoint. Run with:  uv run pytest tests/test_setup.py"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module01"))

load_dotenv()


def test_python_version():
    assert sys.version_info[:2] == (3, 12), "Run commands with `uv run`, never plain `python`."


def test_env_present():
    for key in ("BASE_URL", "API_KEY", "MODEL"):
        assert os.getenv(key), f"{key} missing — did you copy .env.example to .env?"
    assert "paste_your" not in os.getenv("API_KEY"), "API_KEY is still the placeholder."
    assert not os.getenv("API_KEY").startswith(("'", '"')), "No quotes around the key in .env."


def test_model_answers():
    from openai import OpenAI

    client = OpenAI(base_url=os.getenv("BASE_URL"), api_key=os.getenv("API_KEY"))
    r = client.chat.completions.create(
        model=os.getenv("MODEL"),
        max_tokens=64,
        messages=[{"role": "user", "content": "Reply with OK"}],
    )
    assert r.choices[0].message.content


def test_chat_client_requires_real_env(monkeypatch):
    from tokens_utils import chat_client

    monkeypatch.setenv("BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("API_KEY", "paste_your_groq_key_here")

    with pytest.raises(RuntimeError, match="placeholder|copy .env.example"):
        chat_client()
