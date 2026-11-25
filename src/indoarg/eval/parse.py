"""Extract canonical tool call {name, arguments} from diverse local LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any

_NO_CALL_SENTINELS = {"no_call", "nocall", "none", "null", ""}


def _normalize_extracted(obj: dict[str, Any]) -> dict[str, Any] | None:
    name = obj.get("name")
    if name is None or str(name).strip().lower() in _NO_CALL_SENTINELS:
        return None
    args = obj.get("arguments", obj.get("parameters", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {"name": str(name).strip(), "arguments": args, "_parse_error": "arguments_not_json"}
    if not isinstance(args, dict):
        return {"name": str(name).strip(), "arguments": args, "_parse_error": "arguments_not_object"}
    return {"name": str(name).strip(), "arguments": args}


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def _parse_gemma4_tool_call(text: str) -> dict[str, Any] | None:
    """Parse Gemma 4 native format: <|tool_call>call:name{key:<|"|>val<|"|>,n:10}<tool_call|>."""
    m = re.search(r"<\|tool_call>call:([A-Za-z0-9_]+)\{(.*?)\}<tool_call\|>", text, flags=re.DOTALL)
    if not m:
        m = re.search(r"call:([A-Za-z0-9_]+)\{(.*?)\}", text, flags=re.DOTALL)
    if not m:
        return None
    name = m.group(1).strip()
    body = m.group(2).strip()
    if not body:
        return {"name": name, "arguments": {}}

    # Convert Gemma <|"|> delimiters into standard JSON quotes and quote bare keys
    normalized = body.replace('<|"|>', '"')
    normalized = re.sub(r'(^|[,{]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', normalized)
    try:
        args = json.loads("{" + normalized + "}")
        if isinstance(args, dict):
            return {"name": name, "arguments": args}
    except json.JSONDecodeError:
        return {"name": name, "arguments": body, "_parse_error": "gemma4_args_parse_failed"}
    return None


def _try_json_objects(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    # 1. Direct JSON
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            candidates.append(parsed)
        elif isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            candidates.append(parsed[0])
    except json.JSONDecodeError:
        pass

    # 2. <tool_call>...</tool_call> tags (Qwen / Hermes style)
    for blk in re.findall(r"<tool_call>(.*?)</tool_call>", stripped, flags=re.DOTALL | re.IGNORECASE):
        try:
            parsed = json.loads(blk.strip())
            if isinstance(parsed, dict):
                candidates.append(parsed)
        except json.JSONDecodeError:
            pass

    # 3. Markdown ```json ... ``` blocks
    for blk in re.findall(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE):
        try:
            parsed = json.loads(blk.strip())
            if isinstance(parsed, dict):
                candidates.append(parsed)
        except json.JSONDecodeError:
            pass

    # 4. Scan balanced JSON object substrings
    if not candidates:
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(stripped):
            if ch == "{":
                try:
                    parsed, _end = decoder.raw_decode(stripped[idx:])
                    if isinstance(parsed, dict):
                        candidates.append(parsed)
                        break
                except json.JSONDecodeError:
                    continue
    return candidates


def looks_like_malformed_call(raw_output: str) -> bool:
    """Heuristic to distinguish broken tool-call syntax (E_PARSE) from plain-text or sentinel abstention."""
    cleaned = _strip_thinking(raw_output or "")
    if not cleaned:
        return False
    # Clean explicit no-call sentinel JSON from S2/S3 (e.g. {"name": "no_call", "arguments": {}})
    # is an intentional abstention, NOT a malformed tool call.
    for obj in _try_json_objects(cleaned):
        inner = obj["function"] if isinstance(obj.get("function"), dict) else obj
        if "name" in inner:
            name_val = inner.get("name")
            if name_val is None or str(name_val).strip().lower() in _NO_CALL_SENTINELS:
                return False
    markers = ("<tool_call>", "<|tool_call>", '"arguments"', '"name"', "```json", "call:")
    if any(tok in cleaned for tok in markers):
        return True
    if cleaned.startswith("{") or cleaned.endswith("}"):
        return True
    return False


def extract_tool_call(
    raw_output: str,
    tool_calls: list[dict[str, Any]] | None = None,
    known_tools: set[str] | None = None,
) -> dict[str, Any] | None:
    """Extract a single canonical {name, arguments} dict, or None if abstention/unparseable."""
    # 1. Structured runtime tool_calls take precedence
    if tool_calls:
        tc = tool_calls[-1]
        return _normalize_extracted({"name": tc.get("name"), "arguments": tc.get("arguments", {})})

    cleaned = _strip_thinking(raw_output or "")
    if not cleaned:
        return None

    # 2. JSON objects (direct, <tool_call>, fenced, balanced)
    for obj in _try_json_objects(cleaned):
        if "function" in obj and isinstance(obj["function"], dict):
            obj = obj["function"]
        if "name" in obj:
            return _normalize_extracted(obj)
        # Shorthand: {"tool_name": {...}} when tool_name is known
        if known_tools and len(obj) == 1:
            only_key = next(iter(obj.keys()))
            if only_key in known_tools and isinstance(obj[only_key], dict):
                return {"name": only_key, "arguments": obj[only_key]}

    # 3. Gemma 4 native format
    if gemma := _parse_gemma4_tool_call(cleaned):
        return _normalize_extracted(gemma)

    return None
