"""Per-item scoring and aggregated IndoArg metrics (CVR, TSA, EXA, WVS, VA[k], ABS, DeltaReg)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np

from indoarg.data import EvalItem
from indoarg.eval.taxonomy import classify_errors
from indoarg.tools.registry import ToolRegistry


def score_item(
    raw_record: dict[str, Any],
    gold_item: EvalItem,
    registry: ToolRegistry,
) -> dict[str, Any]:
    """Attach cvr, tsa, exa, wvs, abs, error_codes, and value_correct to a run log record."""
    errors, value_correct, cvr, tsa, exa = classify_errors(
        raw_output=str(raw_record.get("raw_output", "")),
        parsed_call=raw_record.get("parsed_call"),
        gold_call=gold_item.gold_call,
        strict_keys=gold_item.strict_keys,
        soft_keys=gold_item.soft_keys,
        reference_time=gold_item.reference_time,
        registry=registry,
    )
    is_no_call = gold_item.gold_call is None
    wvs = bool(cvr and not exa) if not is_no_call else False
    abstention_ok = bool(exa) if is_no_call else None

    scored = dict(raw_record)
    scored.update(
        {
            "is_no_call": is_no_call,
            "tool_target": gold_item.tool_target,
            "value_categories": gold_item.value_categories,
            "difficulty": gold_item.difficulty,
            "cvr": cvr,
            "tsa": tsa,
            "exa": exa,
            "wvs": wvs,
            "abs": abstention_ok,
            "error_codes": errors,
            "value_correct": value_correct,
        }
    )
    return scored


def aggregate_metrics(scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary metrics across a set of scored items."""
    if not scored_rows:
        return {"n_items": 0}

    call_rows = [r for r in scored_rows if not r.get("is_no_call", False)]
    nocall_rows = [r for r in scored_rows if r.get("is_no_call", False)]

    cvr_rate = float(np.mean([r["cvr"] for r in call_rows])) if call_rows else None
    tsa_rate = float(np.mean([r["tsa"] for r in call_rows])) if call_rows else None
    exa_call = float(np.mean([r["exa"] for r in call_rows])) if call_rows else None
    exa_all = float(np.mean([r["exa"] for r in scored_rows]))
    abs_rate = float(np.mean([r["abs"] for r in nocall_rows])) if nocall_rows else None

    valid_call_rows = [r for r in call_rows if r["cvr"]]
    wvs_rate = (
        float(np.mean([not r["exa"] for r in valid_call_rows])) if valid_call_rows else None
    )

    # Value accuracy by category (VA[k])
    cat_hits: dict[str, list[int]] = defaultdict(list)
    for r in scored_rows:
        for cat in r.get("value_categories", []):
            cat_hits[cat].append(1 if r["exa"] else 0)
    va_by_cat = {cat: round(float(np.mean(vals)), 4) for cat, vals in sorted(cat_hits.items())}

    # Register breakdown & paired DeltaReg
    by_reg: dict[str, list[int]] = defaultdict(list)
    by_pair: dict[str, dict[str, int]] = defaultdict(dict)
    for r in scored_rows:
        reg = r["register"]
        by_reg[reg].append(1 if r["exa"] else 0)
        by_pair[r["pair_id"]][reg] = 1 if r["exa"] else 0

    exa_by_reg = {reg: round(float(np.mean(vals)), 4) for reg, vals in sorted(by_reg.items())}
    delta_reg: dict[str, float | None] = {}
    for other in ("informal", "campur"):
        diffs = [
            d["formal"] - d[other]
            for d in by_pair.values()
            if "formal" in d and other in d
        ]
        delta_reg[f"formal_minus_{other}"] = round(float(np.mean(diffs)), 4) if diffs else None

    # Error counts
    err_counter: Counter[str] = Counter()
    for r in scored_rows:
        for code in r.get("error_codes", []):
            err_counter[code] += 1

    # Efficiency metrics
    latencies = [float(r["latency_ms"]) for r in scored_rows if r.get("latency_ms") is not None]
    tps_vals = [float(r["tokens_per_s_decode"]) for r in scored_rows if r.get("tokens_per_s_decode") is not None]
    vram_vals = [float(r["vram_peak_mb"]) for r in scored_rows if r.get("vram_peak_mb") is not None]
    steps_vals = [len(r.get("steps") or []) for r in scored_rows]

    return {
        "n_items": len(scored_rows),
        "n_call": len(call_rows),
        "n_no_call": len(nocall_rows),
        "CVR": round(cvr_rate, 4) if cvr_rate is not None else None,
        "TSA": round(tsa_rate, 4) if tsa_rate is not None else None,
        "EXA": round(exa_all, 4),
        "EXA_call_only": round(exa_call, 4) if exa_call is not None else None,
        "WVS": round(wvs_rate, 4) if wvs_rate is not None else None,
        "ABS": round(abs_rate, 4) if abs_rate is not None else None,
        "VA_by_category": va_by_cat,
        "EXA_by_register": exa_by_reg,
        "delta_register": delta_reg,
        "error_counts": dict(sorted(err_counter.items())),
        "efficiency": {
            "latency_p50_ms": round(float(np.percentile(latencies, 50)), 2) if latencies else None,
            "latency_p95_ms": round(float(np.percentile(latencies, 95)), 2) if latencies else None,
            "mean_tokens_per_s": round(float(np.mean(tps_vals)), 2) if tps_vals else None,
            "vram_peak_mb": round(float(np.max(vram_vals)), 1) if vram_vals else None,
            "mean_steps": round(float(np.mean(steps_vals)), 2) if steps_vals else 0.0,
        },
    }
