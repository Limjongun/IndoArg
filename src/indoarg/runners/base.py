"""Abstract runner interface and response container."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunnerResponse:
    raw_output: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_per_s_decode: float | None = None
    vram_peak_mb: float | None = None
    thinking_forced: bool = False
    request_payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseRunner(ABC):
    runtime_name: str = "base"

    @abstractmethod
    def get_runtime_version(self) -> str:
        """Return version string of the active inference runtime."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        grammar: str | None = None,
        response_format: dict[str, Any] | None = None,
        seed: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
    ) -> RunnerResponse:
        """Send chat completion request and return structured metrics + output."""
