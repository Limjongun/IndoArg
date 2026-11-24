"""Native Ollama client runner for Experiment C (runtime variance)."""

from __future__ import annotations

import json
import time
from typing import Any

import ollama

from indoarg.config import InferenceConfig
from indoarg.runners.base import BaseRunner, RunnerResponse
from indoarg.utils.sysinfo import current_vram_used_mb, get_runtime_versions


class OllamaRunner(BaseRunner):
    runtime_name = "ollama_native"

    def __init__(
        self,
        model_tag: str,
        host: str = "http://127.0.0.1:11434",
        inference_cfg: InferenceConfig | None = None,
    ) -> None:
        self.model_tag = model_tag
        self.host = host
        self.inference_cfg = inference_cfg
        self.client = ollama.Client(host=host)
        self._version_cache: str | None = None

    def get_runtime_version(self) -> str:
        if self._version_cache:
            return self._version_cache
        ver = get_runtime_versions().get("ollama_version")
        self._version_cache = ver or "unknown"
        return self._version_cache

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
        dec = self.inference_cfg.main if self.inference_cfg else None
        temp = dec.temperature if (temperature is None and dec) else (0.0 if temperature is None else temperature)
        tp = dec.top_p if (top_p is None and dec) else (1.0 if top_p is None else top_p)
        mtok = dec.max_tokens if (max_tokens is None and dec) else (512 if max_tokens is None else max_tokens)

        options: dict[str, Any] = {
            "temperature": temp,
            "top_p": tp,
            "top_k": dec.top_k if dec else 0,
            "repeat_penalty": dec.repeat_penalty if dec else 1.0,
            "num_ctx": dec.n_ctx if dec else 8192,
            "num_predict": mtok,
        }
        if seed is not None:
            options["seed"] = seed

        kwargs: dict[str, Any] = {
            "model": self.model_tag,
            "messages": messages,
            "options": options,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
        if response_format and isinstance(response_format, dict):
            schema = response_format.get("json_schema", {}).get("schema")
            kwargs["format"] = schema or "json"
        if dec and dec.thinking == "off":
            kwargs["think"] = False

        vram_before = current_vram_used_mb()
        t0 = time.perf_counter()
        try:
            resp = self.client.chat(**kwargs)
        except Exception as exc:
            # Fallback if installed Ollama model rejects `think=False`
            if "think" in kwargs:
                kwargs.pop("think", None)
                try:
                    resp = self.client.chat(**kwargs)
                except Exception as exc2:
                    elapsed = (time.perf_counter() - t0) * 1000.0
                    return RunnerResponse(
                        raw_output="",
                        latency_ms=round(elapsed, 2),
                        vram_peak_mb=vram_before,
                        request_payload={"messages": messages, "tools": tools, "params": options},
                        error=str(exc2),
                    )
            else:
                elapsed = (time.perf_counter() - t0) * 1000.0
                return RunnerResponse(
                    raw_output="",
                    latency_ms=round(elapsed, 2),
                    vram_peak_mb=vram_before,
                    request_payload={"messages": messages, "tools": tools, "params": options},
                    error=str(exc),
                )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        vram_after = current_vram_used_mb()
        vram_peak = max(v for v in (vram_before, vram_after) if v is not None) if (vram_before or vram_after) else None

        msg = resp.get("message", {}) if isinstance(resp, dict) else resp.message
        content = (msg.get("content") if isinstance(msg, dict) else msg.content) or ""
        thinking_text = (msg.get("thinking") if isinstance(msg, dict) else getattr(msg, "thinking", None)) or ""
        thinking_forced = bool(thinking_text) or ("<think>" in content)

        raw_tcs = (msg.get("tool_calls") if isinstance(msg, dict) else msg.tool_calls) or []
        tool_calls_out: list[dict[str, Any]] = []
        for idx, tc in enumerate(raw_tcs):
            fn = tc.get("function", {}) if isinstance(tc, dict) else tc.function
            name = fn.get("name") if isinstance(fn, dict) else fn.name
            args = fn.get("arguments") if isinstance(fn, dict) else fn.arguments
            tool_calls_out.append(
                {
                    "id": f"ollama_tc_{idx}",
                    "name": name,
                    "arguments": args,
                    "raw_arguments": json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args),
                }
            )

        prompt_tokens = int(
            (resp.get("prompt_eval_count") if isinstance(resp, dict) else getattr(resp, "prompt_eval_count", 0)) or 0
        )
        completion_tokens = int(
            (resp.get("eval_count") if isinstance(resp, dict) else getattr(resp, "eval_count", 0)) or 0
        )
        eval_dur_ns = (
            (resp.get("eval_duration") if isinstance(resp, dict) else getattr(resp, "eval_duration", 0)) or 0
        )
        tps = round(completion_tokens / (eval_dur_ns / 1e9), 2) if (completion_tokens > 0 and eval_dur_ns > 0) else None
        raw_out = content if content else json.dumps(tool_calls_out, ensure_ascii=False)

        return RunnerResponse(
            raw_output=raw_out,
            tool_calls=tool_calls_out,
            latency_ms=round(elapsed_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_per_s_decode=tps,
            vram_peak_mb=vram_peak,
            thinking_forced=thinking_forced,
            request_payload={"messages": messages, "tools": tools, "params": options},
        )
