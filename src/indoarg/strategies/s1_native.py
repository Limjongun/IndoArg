"""S1: Native tool calling via runtime API `tools` parameter."""

from __future__ import annotations

from indoarg.eval.parse import extract_tool_call
from indoarg.runners.base import BaseRunner
from indoarg.strategies import StrategyResult, format_user_turn
from indoarg.tools.registry import ToolRegistry
from indoarg.utils.hashing import sha256_text


def run_s1_native(
    *,
    runner: BaseRunner,
    prompt: str,
    reference_time: str,
    system_prompt: str,
    target_registry: ToolRegistry,
    seed: int | None = None,
) -> StrategyResult:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": format_user_turn(prompt, reference_time)},
    ]
    resp = runner.chat(messages, tools=target_registry.openai_tools, seed=seed)
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
        prompt_hash=sha256_text(system_prompt),
        error=resp.error,
    )
