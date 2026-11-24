"""S4: Normalizer-tool assisted multi-step strategy (max 4 normalizer steps + target call)."""

from __future__ import annotations

import json
from typing import Any

from indoarg.eval.parse import extract_tool_call
from indoarg.runners.base import BaseRunner
from indoarg.strategies import StrategyResult, format_user_turn
from indoarg.tools.mock_executors import execute_normalizer_tool
from indoarg.tools.registry import ToolRegistry
from indoarg.utils.hashing import sha256_text


def run_s4_normalizer_tool(
    *,
    runner: BaseRunner,
    prompt: str,
    reference_time: str,
    system_prompt: str,
    target_registry: ToolRegistry,
    normalizer_registry: ToolRegistry,
    max_normalizer_steps: int = 4,
    seed: int | None = None,
) -> StrategyResult:
    norm_names = set(normalizer_registry.names)
    target_names = set(target_registry.names)
    all_tools = [*normalizer_registry.openai_tools, *target_registry.openai_tools]

    s4_system = (
        f"{system_prompt}\n\n"
        "Anda juga dapat memanggil tool bantu normalisasi "
        "(parse_waktu, parse_nominal, cari_wilayah, parse_satuan) terlebih dahulu "
        "sebelum memanggil tool target bila ada nilai informal, slang, singkatan wilayah, "
        "atau satuan yang perlu dinormalisasi."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": s4_system},
        {"role": "user", "content": format_user_turn(prompt, reference_time)},
    ]

    steps: list[dict[str, Any]] = []
    total_latency = 0.0
    total_prompt_toks = 0
    total_comp_toks = 0
    vram_peaks: list[float] = []
    thinking_forced = False
    last_resp = None
    final_parsed: dict[str, Any] | None = None

    for _step_idx in range(max_normalizer_steps + 1):
        resp = runner.chat(messages, tools=all_tools, seed=seed)
        last_resp = resp
        total_latency += resp.latency_ms
        total_prompt_toks += resp.prompt_tokens
        total_comp_toks += resp.completion_tokens
        if resp.vram_peak_mb is not None:
            vram_peaks.append(resp.vram_peak_mb)
        thinking_forced = thinking_forced or resp.thinking_forced

        if resp.error:
            break

        # Separate normalizer calls vs target call from this turn
        if resp.tool_calls:
            normalizer_calls = [tc for tc in resp.tool_calls if tc.get("name") in norm_names]
            target_calls = [tc for tc in resp.tool_calls if tc.get("name") in target_names]

            if target_calls and not normalizer_calls:
                tc = target_calls[-1]
                final_parsed = {"name": tc["name"], "arguments": tc["arguments"]}
                break

            if normalizer_calls:
                assistant_tcs = []
                tool_results_msgs = []
                for idx, tc in enumerate(normalizer_calls):
                    tc_id = tc.get("id") or f"norm_{len(steps)}_{idx}"
                    args = tc.get("arguments") if isinstance(tc.get("arguments"), dict) else {}
                    res = execute_normalizer_tool(tc["name"], args)
                    steps.append({"tool": tc["name"], "args": args, "result": res})
                    assistant_tcs.append(
                        {
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(args, ensure_ascii=False),
                            },
                        }
                    )
                    tool_results_msgs.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": tc["name"],
                            "content": json.dumps(res, ensure_ascii=False),
                        }
                    )
                messages.append({"role": "assistant", "content": "", "tool_calls": assistant_tcs})
                messages.extend(tool_results_msgs)

                # If model also emitted a target call in the same turn, keep it as fallback if loop ends
                if target_calls:
                    tc = target_calls[-1]
                    final_parsed = {"name": tc["name"], "arguments": tc["arguments"]}
                    break
                continue

            # Unknown tool name emitted via structured tool_calls
            tc = resp.tool_calls[-1]
            final_parsed = {"name": tc["name"], "arguments": tc["arguments"]}
            break

        # No structured tool_calls — inspect raw text
        parsed = extract_tool_call(
            resp.raw_output,
            resp.tool_calls,
            known_tools=target_names | norm_names,
        )
        if parsed and parsed.get("name") in norm_names:
            args = parsed.get("arguments") if isinstance(parsed.get("arguments"), dict) else {}
            res = execute_normalizer_tool(parsed["name"], args)
            steps.append({"tool": parsed["name"], "args": args, "result": res})
            messages.append({"role": "assistant", "content": resp.raw_output})
            messages.append(
                {
                    "role": "user",
                    "content": f"Hasil {parsed['name']}: {json.dumps(res, ensure_ascii=False)}. Lanjutkan pemanggilan tool target.",
                }
            )
            continue

        final_parsed = parsed
        break

    return StrategyResult(
        raw_output=last_resp.raw_output if last_resp else "",
        parsed_call=final_parsed,
        steps=steps,
        latency_ms=round(total_latency, 2),
        prompt_tokens=total_prompt_toks,
        completion_tokens=total_comp_toks,
        tokens_per_s_decode=last_resp.tokens_per_s_decode if last_resp else None,
        vram_peak_mb=max(vram_peaks) if vram_peaks else None,
        thinking_forced=thinking_forced,
        request=last_resp.request_payload if last_resp else {},
        prompt_hash=sha256_text(s4_system),
        error=last_resp.error if last_resp else None,
    )
