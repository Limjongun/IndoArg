"""OpenAI-compatible client runner for llama.cpp (llama-server / llama serve)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from indoarg.config import InferenceConfig, ModelSpec
from indoarg.runners.base import BaseRunner, RunnerResponse
from indoarg.utils.sysinfo import current_vram_used_mb, get_runtime_versions


class LlamaCppRunner(BaseRunner):
    runtime_name = "llamacpp_server"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080/v1",
        model_spec: ModelSpec | None = None,
        inference_cfg: InferenceConfig | None = None,
        timeout: float = 120.0,
        runtime_name: str = "llamacpp_server",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_spec = model_spec
        self.inference_cfg = inference_cfg
        self.timeout = timeout
        self.runtime_name = runtime_name
        self.client = OpenAI(base_url=self.base_url, api_key="not-needed", timeout=timeout)
        self._version_cache: str | None = None

    def get_runtime_version(self) -> str:
        if self._version_cache:
            return self._version_cache
        root_url = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        try:
            resp = httpx.get(f"{root_url}/props", timeout=3.0)
            if resp.status_code == 200:
                props = resp.json()
                build = props.get("build_info") or props.get("version")
                if build:
                    self._version_cache = str(build)
                    return self._version_cache
        except Exception:
            pass
        cli_ver = get_runtime_versions().get("llamacpp_version")
        self._version_cache = cli_ver or "unknown"
        return self._version_cache

    def get_loaded_model_info(self) -> dict[str, str | None]:
        """Inspect active llama-server /props and /v1/models to identify the loaded GGUF."""
        root_url = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        info: dict[str, str | None] = {"model_path": None, "model_alias": None, "v1_model_id": None}
        try:
            r_props = httpx.get(f"{root_url}/props", timeout=3.0)
            if r_props.status_code == 200:
                props = r_props.json()
                info["model_path"] = props.get("model_path")
                info["model_alias"] = props.get("model_alias")
        except Exception:
            pass
        try:
            r_models = httpx.get(f"{self.base_url}/models", timeout=3.0)
            if r_models.status_code == 200:
                payload = r_models.json()
                data = payload.get("data") or []
                if data and isinstance(data[0], dict):
                    info["v1_model_id"] = data[0].get("id")
                models = payload.get("models") or []
                if not info["model_path"] and models and isinstance(models[0], dict):
                    info["model_path"] = models[0].get("model")
        except Exception:
            pass
        return info

    def verify_loaded_model(self, expected_model_id: str) -> tuple[bool, dict[str, str | None]]:
        """Guard against Windows port collision (e.g. old M1 server still listening on :8080)."""
        info = self.get_loaded_model_info()
        target_file = f"{expected_model_id.lower()}.gguf"
        candidates = [v for v in info.values() if isinstance(v, str) and v.strip()]
        if not candidates:
            return True, info
        for val in candidates:
            norm = val.replace("\\", "/").lower()
            if norm == expected_model_id.lower() or norm.endswith(f"/{target_file}") or norm == target_file:
                return True, info
        return False, info

    def _default_model_name(self) -> str:
        if self.model_spec:
            return self.model_spec.name
        return "local-model"

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _create_completion(self, kwargs: dict[str, Any]) -> Any:
        return self.client.chat.completions.create(**kwargs)

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

        extra_body: dict[str, Any] = {
            "top_k": dec.top_k if dec else 0,
            "min_p": dec.min_p if dec else 0.0,
            "repeat_penalty": dec.repeat_penalty if dec else 1.0,
        }
        if dec and dec.thinking == "off":
            extra_body["chat_template_kwargs"] = {"enable_thinking": False}
        if grammar:
            extra_body["grammar"] = grammar

        kwargs: dict[str, Any] = {
            "model": self._default_model_name(),
            "messages": messages,
            "temperature": temp,
            "top_p": tp,
            "max_tokens": mtok,
            "extra_body": extra_body,
        }
        if dec and dec.stop:
            kwargs["stop"] = dec.stop
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format
        if seed is not None:
            kwargs["seed"] = seed

        vram_before = current_vram_used_mb()
        t0 = time.perf_counter()
        try:
            resp = self._create_completion(kwargs)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return RunnerResponse(
                raw_output="",
                latency_ms=round(elapsed, 2),
                vram_peak_mb=vram_before,
                request_payload={
                    "messages": messages,
                    "tools": tools,
                    "params": {
                        "temperature": temp,
                        "top_p": tp,
                        "max_tokens": mtok,
                        "extra_body": {k: v for k, v in extra_body.items() if k != "grammar"},
                        "has_grammar": bool(grammar),
                    },
                },
                error=str(exc),
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        vram_after = current_vram_used_mb()
        vram_peak = max(v for v in (vram_before, vram_after) if v is not None) if (vram_before or vram_after) else None

        choice = resp.choices[0]
        msg = choice.message
        content = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", None) or ""
        thinking_forced = bool(reasoning) or ("<think>" in content)

        tool_calls_out: list[dict[str, Any]] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                raw_args = tc.function.arguments
                if isinstance(raw_args, str):
                    try:
                        parsed_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        parsed_args = raw_args
                else:
                    parsed_args = raw_args
                tool_calls_out.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": parsed_args,
                        "raw_arguments": raw_args,
                    }
                )

        usage = resp.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        timings = getattr(resp, "timings", None)
        tps = None
        if isinstance(timings, dict) and timings.get("predicted_per_second"):
            tps = round(float(timings["predicted_per_second"]), 2)
        elif completion_tokens > 0 and elapsed_ms > 0:
            tps = round(completion_tokens / (elapsed_ms / 1000.0), 2)

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
            request_payload={
                "messages": messages,
                "tools": tools,
                "params": {
                    "temperature": temp,
                    "top_p": tp,
                    "max_tokens": mtok,
                    "extra_body": {k: v for k, v in extra_body.items() if k != "grammar"},
                    "has_grammar": bool(grammar),
                },
            },
        )
