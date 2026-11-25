"""Load OpenAI-style tool schemas and validate tool calls with jsonschema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from indoarg.config import repo_root


class ToolRegistry:
    def __init__(self, tools: list[dict[str, Any]]) -> None:
        self._tools = tools
        self._by_name: dict[str, dict[str, Any]] = {}
        self._validators: dict[str, Draft202012Validator] = {}
        for entry in tools:
            fn = entry["function"]
            name = fn["name"]
            self._by_name[name] = fn
            self._validators[name] = Draft202012Validator(fn["parameters"])

    @classmethod
    def from_file(cls, path: str | Path) -> ToolRegistry:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data)

    @classmethod
    def default_target_tools(cls) -> ToolRegistry:
        return cls.from_file(repo_root() / "data" / "tools" / "tools_v1.json")

    @classmethod
    def default_normalizer_tools(cls) -> ToolRegistry:
        return cls.from_file(repo_root() / "data" / "tools" / "normalizer_tools.json")

    @property
    def openai_tools(self) -> list[dict[str, Any]]:
        return list(self._tools)

    @property
    def names(self) -> list[str]:
        return list(self._by_name.keys())

    def get(self, name: str) -> dict[str, Any] | None:
        return self._by_name.get(name)

    def has(self, name: str) -> bool:
        return name in self._by_name

    def validate_call(self, name: str, arguments: Any) -> tuple[bool, list[str]]:
        if name not in self._validators:
            return False, [f"Tool tidak dikenal: '{name}'"]
        if not isinstance(arguments, dict):
            return False, ["Argumen harus berupa objek JSON (dict)."]
        errors = [e.message for e in self._validators[name].iter_errors(arguments)]
        return len(errors) == 0, errors

    def render_prompt_description(self) -> str:
        """Render concise Indonesian tool specification block for prompt-based strategies (S2/S3)."""
        lines = ["Daftar tool yang tersedia:"]
        for entry in self._tools:
            fn = entry["function"]
            params = fn["parameters"]
            props = params.get("properties", {})
            req = set(params.get("required", []))
            prop_parts = []
            for k, spec in props.items():
                t = spec.get("type", "any")
                extra = ""
                if "enum" in spec:
                    vals = spec["enum"]
                    preview = ", ".join(map(str, vals))
                    extra = f" enum=[{preview}]"
                elif "pattern" in spec:
                    extra = f" pattern={spec['pattern']}"
                desc = spec.get("description", "")
                star = "*" if k in req else ""
                prop_parts.append(f"    - {k}{star} ({t}{extra}): {desc}")
            lines.append(f"- {fn['name']}: {fn['description']}")
            lines.extend(prop_parts)
        return "\n".join(lines)
