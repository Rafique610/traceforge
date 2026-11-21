"""Live smoke test: `uv run python -m traceforge.agent.smoke --provider ollama`."""

import argparse
import json

from traceforge.agent.gateway import chat
from traceforge.config import get_settings

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_service_status",
            "description": "Get the status of a service.",
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string"}},
                "required": ["service"],
            },
        },
    }
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)
    ap.add_argument("--model")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    update = {"llm_provider": a.provider} | ({"llm_model": a.model} if a.model else {})
    s = get_settings().model_copy(update=update)
    msgs = [{"role": "user", "content": "Check the status of the worker service."}]
    for i in (1, 2):
        r = chat(msgs, TOOLS, settings=s, use_cache=not a.no_cache)
        assert r.tool_calls, "no tool call returned"
        assert "service" in json.loads(r.tool_calls[0].arguments), "bad tool arguments"
        print(f"run {i}: {r.tool_calls[0]} cache_hit={r.cache_hit} latency_ms={r.latency_ms:.0f}")
    print("OK")


if __name__ == "__main__":
    main()
