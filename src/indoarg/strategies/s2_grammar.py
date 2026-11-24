"""S2: Grammar-constrained decoding (GBNF / JSON schema) with tool descriptions in system prompt."""

from __future__ import annotations

from typing import Any

from indoarg.eval.parse import extract_tool_call
from indoarg.runners.base import BaseRunner
from indoarg.strategies import StrategyResult, format_user_turn
from indoarg.tools.registry import ToolRegistry
from indoarg.utils.hashing import sha256_text


def build_s2_json_schema(target_registry: ToolRegistry) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "indoarg_tool_call",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": [*target_registry.names, "no_call"]},
                    "arguments": {"type": "object"},
                },
                "required": ["name", "arguments"],
                "additionalProperties": False,
            },
        },
    }


def run_s2_grammar(
    *,
    runner: BaseRunner,
    prompt: str,
    reference_time: str,
    system_prompt: str,
    target_registry: ToolRegistry,
    grammar_text: str | None = None,
    seed: int | None = None,
) -> StrategyResult:
    tool_spec = target_registry.render_prompt_description()
    s2_system = (
        f"{system_prompt}\n\n{tool_spec}\n\n"
        'Keluarkan HANYA satu objek JSON valid berbentuk {"name": "<nama_tool>", "arguments": {...}}. '
        'Jika tidak membutuhkan tool apa pun, keluarkan {"name": "no_call", "arguments": {}}.'
    )
    messages = [
        {"role": "system", "content": s2_system},
        {"role": "user", "content": format_user_turn(prompt, reference_time)},
    ]
    resp = runner.chat(
        messages,
        grammar=grammar_text,
        response_format=None if grammar_text else build_s2_json_schema(target_registry),
        seed=seed,
    )
    parsed = extract_tool_call(resp.raw_output, resp.tool_calls, known_tools=set(target_registry.names))
    return StrategyResult(
        raw_output=resp.raw_output,
        parsed_call=parsed,
        steps=[],
        latency_ms=resp.latency_ms,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        tokens_per_s_decode=resp.tokens_per_s_decode,
        vram_peak_mb=resp.vram_peak_mb,
        thinking_forced=resp.thinking_forced,
        request=resp.request_payload,
        prompt_hash=sha256_text(s2_system),
        error=resp.error,
    )
