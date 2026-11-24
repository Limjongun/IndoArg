"""S3: Two-stage strategy (free-form value normalization followed by grammar-locked JSON call)."""

from __future__ import annotations

from indoarg.config import load_prompt_text
from indoarg.eval.parse import extract_tool_call
from indoarg.runners.base import BaseRunner
from indoarg.strategies import StrategyResult, format_user_turn
from indoarg.strategies.s2_grammar import build_s2_json_schema
from indoarg.tools.registry import ToolRegistry
from indoarg.utils.hashing import sha256_text


def run_s3_two_stage(
    *,
    runner: BaseRunner,
    prompt: str,
    reference_time: str,
    system_prompt: str,
    target_registry: ToolRegistry,
    grammar_text: str | None = None,
    stage1_prompt: str | None = None,
    stage2_prompt: str | None = None,
    seed: int | None = None,
) -> StrategyResult:
    st1_inst = stage1_prompt or load_prompt_text("s3_stage1_id.txt")
    st2_inst = stage2_prompt or load_prompt_text("s3_stage2_id.txt")
    tool_spec = target_registry.render_prompt_description()
    full_system = f"{system_prompt}\n\n{tool_spec}"

    user_turn = format_user_turn(prompt, reference_time)
    messages_stage1 = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": f"{st1_inst}\n\n{user_turn}"},
    ]
    resp1 = runner.chat(messages_stage1, seed=seed)
    if resp1.error:
        return StrategyResult(
            raw_output=resp1.raw_output,
            parsed_call=None,
            steps=[{"stage": 1, "output": resp1.raw_output, "error": resp1.error}],
            latency_ms=resp1.latency_ms,
            prompt_tokens=resp1.prompt_tokens,
            completion_tokens=resp1.completion_tokens,
            tokens_per_s_decode=resp1.tokens_per_s_decode,
            vram_peak_mb=resp1.vram_peak_mb,
            thinking_forced=resp1.thinking_forced,
            request=resp1.request_payload,
            prompt_hash=sha256_text(full_system + st1_inst + st2_inst),
            error=resp1.error,
        )

    messages_stage2 = [
        *messages_stage1,
        {"role": "assistant", "content": resp1.raw_output},
        {"role": "user", "content": st2_inst},
    ]
    resp2 = runner.chat(
        messages_stage2,
        grammar=grammar_text,
        response_format=None if grammar_text else build_s2_json_schema(target_registry),
        seed=seed,
    )
    parsed = extract_tool_call(resp2.raw_output, resp2.tool_calls, known_tools=set(target_registry.names))

    total_latency = round(resp1.latency_ms + resp2.latency_ms, 2)
    total_prompt_toks = resp1.prompt_tokens + resp2.prompt_tokens
    total_comp_toks = resp1.completion_tokens + resp2.completion_tokens
    vram_vals = [v for v in (resp1.vram_peak_mb, resp2.vram_peak_mb) if v is not None]
    vram_peak = max(vram_vals) if vram_vals else None

    return StrategyResult(
        raw_output=resp2.raw_output,
        parsed_call=parsed,
        steps=[
            {"stage": 1, "output": resp1.raw_output, "latency_ms": resp1.latency_ms},
            {"stage": 2, "output": resp2.raw_output, "latency_ms": resp2.latency_ms},
        ],
        latency_ms=total_latency,
        prompt_tokens=total_prompt_toks,
        completion_tokens=total_comp_toks,
        tokens_per_s_decode=resp2.tokens_per_s_decode,
        vram_peak_mb=vram_peak,
        thinking_forced=resp1.thinking_forced or resp2.thinking_forced,
        request=resp2.request_payload,
        prompt_hash=sha256_text(full_system + st1_inst + st2_inst),
        error=resp2.error,
    )
