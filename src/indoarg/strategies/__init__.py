"""Strategies S1-S4 for IndoArg tool-calling evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from indoarg.runners.base import BaseRunner
from indoarg.tools.registry import ToolRegistry


def format_user_turn(prompt: str, reference_time: str) -> str:
    return f"Waktu acuan: {reference_time}\nPermintaan pengguna: {prompt}"


@dataclass
class StrategyResult:
    raw_output: str
    parsed_call: dict[str, Any] | None
    steps: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_per_s_decode: float | None = None
    vram_peak_mb: float | None = None
    thinking_forced: bool = False
    request: dict[str, Any] = field(default_factory=dict)
    prompt_hash: str = ""
    error: str | None = None


def run_strategy(
    strategy: str,
    *,
    runner: BaseRunner,
    prompt: str,
    reference_time: str,
    system_prompt: str,
    target_registry: ToolRegistry,
    normalizer_registry: ToolRegistry | None = None,
    grammar_text: str | None = None,
    stage1_prompt: str | None = None,
    stage2_prompt: str | None = None,
    seed: int | None = None,
) -> StrategyResult:
    from .s1_native import run_s1_native
    from .s2_grammar import run_s2_grammar
    from .s3_two_stage import run_s3_two_stage
    from .s4_normalizer_tool import run_s4_normalizer_tool

    code = strategy.upper()
    if code == "S1":
        return run_s1_native(
            runner=runner,
            prompt=prompt,
            reference_time=reference_time,
            system_prompt=system_prompt,
            target_registry=target_registry,
            seed=seed,
        )
    if code == "S2":
        return run_s2_grammar(
            runner=runner,
            prompt=prompt,
            reference_time=reference_time,
            system_prompt=system_prompt,
            target_registry=target_registry,
            grammar_text=grammar_text,
            seed=seed,
        )
    if code == "S3":
        return run_s3_two_stage(
            runner=runner,
            prompt=prompt,
            reference_time=reference_time,
            system_prompt=system_prompt,
            target_registry=target_registry,
            grammar_text=grammar_text,
            stage1_prompt=stage1_prompt,
            stage2_prompt=stage2_prompt,
            seed=seed,
        )
    if code == "S4":
        return run_s4_normalizer_tool(
            runner=runner,
            prompt=prompt,
            reference_time=reference_time,
            system_prompt=system_prompt,
            target_registry=target_registry,
            normalizer_registry=normalizer_registry or ToolRegistry.default_normalizer_tools(),
            seed=seed,
        )
    raise ValueError(f"Strategi tidak dikenal: '{strategy}' (harus S1, S2, S3, atau S4)")


__all__ = ["StrategyResult", "format_user_turn", "run_strategy"]
