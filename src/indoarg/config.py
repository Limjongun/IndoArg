"""Load and validate YAML configuration files for IndoArg."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


def repo_root() -> Path:
    """Return workspace root directory containing pyproject.toml / configs."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "configs").is_dir() and (parent / "data").is_dir():
            return parent
    return Path.cwd()


class ModelSpec(BaseModel):
    id: str
    name: str
    family: str
    params_b: float
    hf_repo: str
    file_pattern: str = "*{QUANT}.gguf"
    chat_template: str = "embedded"
    thinking_toggle: str | None = None
    requires_smoke_pass: bool = False
    note: str | None = None


class ModelsConfig(BaseModel):
    quantizer_policy: str = "same_quantizer_preferred"
    models: list[ModelSpec]

    def by_id(self, model_id: str) -> ModelSpec:
        for m in self.models:
            if m.id == model_id:
                return m
        raise KeyError(f"Model ID '{model_id}' tidak ditemukan di configs/models.yaml")


class ExperimentConfig(BaseModel):
    name: str
    quant: str | None = None
    quant_ladder: list[str] | None = None
    model_dir: str = "models"
    models: list[str]
    strategies: list[str]
    runtime: str | None = None
    runtimes: list[str] | None = None
    split: Literal["dev", "test"] = "test"
    registers: list[Literal["formal", "informal", "campur"]] = Field(
        default_factory=lambda: ["formal", "informal", "campur"]
    )
    decoding: str = "greedy"
    robustness_seeds: list[int] | None = None

    @model_validator(mode="after")
    def _validate_quant_and_runtime(self) -> ExperimentConfig:
        if not self.quant and not self.quant_ladder:
            raise ValueError("Konfigurasi eksperimen harus memiliki 'quant' atau 'quant_ladder'.")
        if not self.runtime and not self.runtimes:
            raise ValueError("Konfigurasi eksperimen harus memiliki 'runtime' atau 'runtimes'.")
        return self

    def all_quants(self) -> list[str]:
        if self.quant_ladder:
            return list(self.quant_ladder)
        assert self.quant is not None
        return [self.quant]

    def all_runtimes(self) -> list[str]:
        if self.runtimes:
            return list(self.runtimes)
        assert self.runtime is not None
        return [self.runtime]


class DecodingParams(BaseModel):
    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = 0
    min_p: float = 0.0
    repeat_penalty: float = 1.0
    max_tokens: int = 512
    n_ctx: int = 8192
    stop: list[str] = Field(default_factory=list)
    thinking: str = "off"

    @field_validator("thinking", mode="before")
    @classmethod
    def _coerce_thinking(cls, v: object) -> str:
        # PyYAML (YAML 1.1) parses bare `off`/`on` as bool False/True.
        if isinstance(v, bool):
            return "on" if v else "off"
        return str(v).strip().lower()


class RobustnessParams(BaseModel):
    temperature: float = 0.7
    top_p: float = 0.95
    seeds: list[int] = Field(default_factory=lambda: [11, 22, 33])


class ServerParams(BaseModel):
    llamacpp: str = "--jinja -ngl 99 -c 8192 -fa on --parallel 1"
    batch_concurrency: int = 1


class InferenceConfig(BaseModel):
    main: DecodingParams
    robustness: RobustnessParams = Field(default_factory=RobustnessParams)
    server: ServerParams = Field(default_factory=ServerParams)


def _read_yaml(path: str | Path) -> dict:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"YAML tidak valid pada {p}")
    return data


def load_models_config(path: str | Path | None = None) -> ModelsConfig:
    p = Path(path) if path else repo_root() / "configs" / "models.yaml"
    return ModelsConfig.model_validate(_read_yaml(p))


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(_read_yaml(path))


def load_inference_config(path: str | Path | None = None) -> InferenceConfig:
    p = Path(path) if path else repo_root() / "configs" / "inference.yaml"
    return InferenceConfig.model_validate(_read_yaml(p))


def load_prompt_text(name: str, prompts_dir: str | Path | None = None) -> str:
    base = Path(prompts_dir) if prompts_dir else repo_root() / "configs" / "prompts"
    p = base / name
    return p.read_text(encoding="utf-8").strip()
