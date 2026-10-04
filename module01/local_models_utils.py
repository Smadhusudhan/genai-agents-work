"""Session 12 helpers - quantization sizing, local model catalog, tool-calling probe,
and the local-vs-hosted timing comparison. Reuses ollama_client(), time_stream() and
ask() from the earlier sessions rather than duplicating them."""
from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------- quantization sizing
BYTES_PER_PARAM = {
    "fp32": 4.0, "fp16": 2.0, "bf16": 2.0, "int8": 1.0, "int4": 0.5,
}


def model_size_gb(params_billion: float, precision: str) -> float:
    """How many GB a model's weights take at a given precision. Rule of thumb only -
    real deployments add overhead (activations, KV cache) on top of this."""
    if precision not in BYTES_PER_PARAM:
        raise ValueError(f"unknown precision {precision!r}; choose one of {list(BYTES_PER_PARAM)}")
    return round(params_billion * 1_000_000_000 * BYTES_PER_PARAM[precision] / 1_000_000_000, 2)


def fits_on(params_billion: float, precision: str, ram_gb: float, headroom_gb: float = 2.0) -> bool:
    """Rough check: does the quantized model fit in a laptop's RAM, leaving headroom
    for the OS and everything else running."""
    return model_size_gb(params_billion, precision) <= (ram_gb - headroom_gb)


# ---------------------------------------------------------------- local model catalog
CATALOG = Path(__file__).with_name("local_models_catalog.json")


def load_local_catalog() -> list[dict]:
    return json.loads(CATALOG.read_text())["models"]


def laptop_options(ram_gb: float, catalog: list[dict] | None = None) -> list[dict]:
    """Which models from the catalog actually fit on a laptop with this much RAM,
    at the precision each row specifies."""
    catalog = catalog or load_local_catalog()
    out = []
    for m in catalog:
        if fits_on(m["params_billion"], m["precision"], ram_gb):
            out.append(m)
    return out


# ---------------------------------------------------------------- tool-calling probe
PROBE_TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_account_balance",
        "description": "Look up a customer's account balance by account number.",
        "parameters": {
            "type": "object",
            "properties": {"account_number": {"type": "string"}},
            "required": ["account_number"],
        },
    },
}]


def probe_tool_calling(client, model: str) -> dict:
    """Send one message that should trigger a tool call. Returns whether the model
    actually emitted a structured tool call, or just talked instead."""
    try:
        r = client.chat.completions.create(
            model=model, max_tokens=200, tools=PROBE_TOOLS, tool_choice="auto",
            messages=[{"role": "user", "content": "What's the balance on account 00123456?"}],
        )
    except Exception as e:
        return {"supports_tool_calling": False, "error": f"{type(e).__name__}: {str(e)[:150]}"}
    msg = r.choices[0].message
    called = bool(getattr(msg, "tool_calls", None))
    return {
        "supports_tool_calling": called,
        "raw_text": msg.content,
        "tool_calls": [tc.function.name for tc in msg.tool_calls] if called else [],
    }


# ---------------------------------------------------------------- compare local vs hosted
def speed_table(results: dict) -> str:
    """results: {label: time_stream()-shaped dict}. Returns a printable table."""
    lines = [f"{'provider':10} {'TTFT s':>8} {'total s':>9} {'tokens':>8} {'tok/s':>8}"]
    for label, r in results.items():
        lines.append(f"{label:10} {r['ttft_s']:8.2f} {r['total_s']:9.2f} {r['completion_tokens']:8d} {r['tokens_per_s']:8.1f}")
    return "\n".join(lines)
