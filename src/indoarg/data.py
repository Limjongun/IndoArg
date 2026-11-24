"""Dataset loader and variant expansion for IndoArg."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

Register = Literal["formal", "informal", "campur"]


class GoldCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class SoftKeySpec(BaseModel):
    method: Literal["casefold", "fuzzy", "set_casefold"]
    threshold: float = 80.0
    aliases: list[str] = Field(default_factory=list)


class Variants(BaseModel):
    formal: str
    informal: str
    campur: str

    def get(self, register: Register) -> str:
        return getattr(self, register)


class PairRecord(BaseModel):
    pair_id: str
    split: Literal["dev", "test"]
    tool_target: str | None = None
    reference_time: str
    variants: Variants
    gold_call: GoldCall | None = None
    strict_keys: list[str] = Field(default_factory=list)
    soft_keys: dict[str, SoftKeySpec] = Field(default_factory=dict)
    value_categories: list[str]
    difficulty: Literal["mudah", "sedang", "sulit"] = "sedang"
    annotator: str
    verified_by: str
    notes: str | None = None


class EvalItem(BaseModel):
    item_id: str
    pair_id: str
    split: Literal["dev", "test"]
    register_name: Register
    prompt: str
    reference_time: str
    tool_target: str | None = None
    gold_call: GoldCall | None = None
    strict_keys: list[str] = Field(default_factory=list)
    soft_keys: dict[str, SoftKeySpec] = Field(default_factory=dict)
    value_categories: list[str] = Field(default_factory=list)
    difficulty: str = "sedang"


class SmokeItem(BaseModel):
    id: str
    tool_target: str | None = None
    register_name: Register = Field(alias="register")
    reference_time: str
    prompt: str
    gold_call: GoldCall | None = None
    strict_keys: list[str] = Field(default_factory=list)
    soft_keys: dict[str, SoftKeySpec] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON tidak valid di {path} baris {line_no}: {exc}") from exc
    return records


def load_pairs(path: str | Path) -> list[PairRecord]:
    return [PairRecord.model_validate(row) for row in load_jsonl(path)]


def load_smoke(path: str | Path) -> list[SmokeItem]:
    return [SmokeItem.model_validate(row) for row in load_jsonl(path)]


def load_split_ids(path: str | Path) -> set[str]:
    ids: set[str] = set()
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s and not s.startswith("#"):
                ids.add(s)
    return ids


def expand_pairs(
    pairs: list[PairRecord],
    split: Literal["dev", "test"] | None = None,
    registers: list[Register] | None = None,
) -> list[EvalItem]:
    regs: list[Register] = registers or ["formal", "informal", "campur"]
    items: list[EvalItem] = []
    for pair in pairs:
        if split is not None and pair.split != split:
            continue
        for reg in regs:
            items.append(
                EvalItem(
                    item_id=f"{pair.pair_id}__{reg}",
                    pair_id=pair.pair_id,
                    split=pair.split,
                    register_name=reg,
                    prompt=pair.variants.get(reg),
                    reference_time=pair.reference_time,
                    tool_target=pair.tool_target,
                    gold_call=pair.gold_call,
                    strict_keys=pair.strict_keys,
                    soft_keys=pair.soft_keys,
                    value_categories=pair.value_categories,
                    difficulty=pair.difficulty,
                )
            )
    return items
