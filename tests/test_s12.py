"""Session 12 checkpoint. Run with:  uv run pytest tests/test_s12.py
Offline-safe except two live tests that skip cleanly if Ollama isn't running."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module01"))
from local_models_utils import (fits_on, laptop_options, load_local_catalog,  # noqa: E402
                                model_size_gb, probe_tool_calling, speed_table)
from providers_utils import ollama_client  # noqa: E402


def _ollama_up() -> bool:
    try:
        ollama_client().models.list()
        return True
    except Exception:
        return False


def test_model_size_gb_known_values():
    assert model_size_gb(20, "fp32") == 80.0
    assert model_size_gb(20, "fp16") == 40.0
    assert model_size_gb(20, "int8") == 20.0
    assert model_size_gb(20, "int4") == 10.0


def test_model_size_gb_rejects_unknown_precision():
    with pytest.raises(ValueError):
        model_size_gb(7, "fp8")


def test_fits_on_respects_headroom():
    # a 10 GB model on 16 GB RAM: fits with default 2 GB headroom (needs <=14)
    assert fits_on(20, "int4", 16) is True
    # same model on 8 GB RAM does not fit
    assert fits_on(20, "int4", 8) is False


def test_catalog_has_a_spread_of_sizes_and_tool_calling_flags():
    cat = load_local_catalog()
    assert len(cat) >= 5
    sizes = [m["params_billion"] for m in cat]
    assert min(sizes) < 2 and max(sizes) >= 20
    assert any(m["tool_calling"] for m in cat)
    assert any(not m["tool_calling"] for m in cat)


def test_laptop_options_scales_with_ram():
    small = laptop_options(8)
    large = laptop_options(32)
    assert len(small) < len(large)
    assert all(m["name"] in [x["name"] for x in large] for m in small)


def test_speed_table_formats_without_error():
    fake = {"groq": {"ttft_s": 0.4, "total_s": 1.2, "completion_tokens": 120, "tokens_per_s": 95.0},
            "ollama": {"ttft_s": 2.1, "total_s": 14.0, "completion_tokens": 120, "tokens_per_s": 8.5}}
    out = speed_table(fake)
    assert "groq" in out and "ollama" in out and "tok/s" in out


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running")
def test_live_tool_calling_probe_on_llama32():
    result = probe_tool_calling(ollama_client(), "llama3.2:3b")
    assert "supports_tool_calling" in result


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running")
def test_live_ollama_lists_at_least_one_model():
    models = ollama_client().models.list()
    assert len(models.data) >= 1
