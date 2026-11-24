"""Evaluation, parsing, canonicalization, error taxonomy, and statistical testing."""

from .canonicalize import canonicalize_value, match_soft_value, match_strict_value
from .metrics import aggregate_metrics, score_item
from .parse import extract_tool_call, looks_like_malformed_call
from .stats import (
    baseline_floor_check,
    holm_correction,
    mcnemar_test,
    paired_bootstrap_ci,
    paired_register_gap_ci,
    quant_register_interaction_gee,
)
from .taxonomy import classify_errors

__all__ = [
    "extract_tool_call",
    "looks_like_malformed_call",
    "canonicalize_value",
    "match_strict_value",
    "match_soft_value",
    "classify_errors",
    "score_item",
    "aggregate_metrics",
    "paired_bootstrap_ci",
    "paired_register_gap_ci",
    "mcnemar_test",
    "holm_correction",
    "quant_register_interaction_gee",
    "baseline_floor_check",
]
