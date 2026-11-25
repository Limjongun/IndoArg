"""Unit tests for IndoArg scoring metrics and statistical inference."""

from __future__ import annotations

import pandas as pd

from indoarg.data import EvalItem, GoldCall, SoftKeySpec
from indoarg.eval import (
    aggregate_metrics,
    baseline_floor_check,
    holm_correction,
    mcnemar_test,
    paired_bootstrap_ci,
    paired_register_gap_ci,
    quant_register_interaction_gee,
    score_item,
)
from indoarg.tools.registry import ToolRegistry


def test_score_item_and_aggregate_metrics() -> None:
    reg = ToolRegistry.default_target_tools()
    gold_call = GoldCall(
        name="transfer_ewallet",
        arguments={"penerima": "Rina", "nominal": 50000, "platform": "gopay"},
    )
    soft = {"penerima": SoftKeySpec(method="casefold")}

    items = [
        EvalItem(
            item_id="P0042__formal",
            pair_id="P0042",
            split="test",
            register_name="formal",
            prompt="Kirim Rp50.000 ke Rina lewat GoPay.",
            reference_time="2026-11-23T18:00:00+07:00",
            tool_target="transfer_ewallet",
            gold_call=gold_call,
            strict_keys=["nominal", "platform"],
            soft_keys=soft,
            value_categories=["nominal_slang"],
        ),
        EvalItem(
            item_id="P0042__informal",
            pair_id="P0042",
            split="test",
            register_name="informal",
            prompt="tf gocap ke rina pake gopay",
            reference_time="2026-11-23T18:00:00+07:00",
            tool_target="transfer_ewallet",
            gold_call=gold_call,
            strict_keys=["nominal", "platform"],
            soft_keys=soft,
            value_categories=["nominal_slang"],
        ),
        EvalItem(
            item_id="N0003__formal",
            pair_id="N0003",
            split="test",
            register_name="formal",
            prompt="Apa ibu kota Jawa Timur?",
            reference_time="2026-11-23T18:00:00+07:00",
            tool_target=None,
            gold_call=None,
            strict_keys=[],
            soft_keys={},
            value_categories=["no_call"],
        ),
    ]

    raw_recs = [
        {
            "pair_id": "P0042",
            "register": "formal",
            "raw_output": "{}",
            "parsed_call": {"name": "transfer_ewallet", "arguments": {"penerima": "rina", "nominal": 50000, "platform": "gopay"}},
            "latency_ms": 200.0,
            "tokens_per_s_decode": 40.0,
            "vram_peak_mb": 3200.0,
            "steps": [],
        },
        {
            "pair_id": "P0042",
            "register": "informal",
            "raw_output": "{}",
            "parsed_call": {"name": "transfer_ewallet", "arguments": {"penerima": "rina", "nominal": 5000, "platform": "gopay"}},
            "latency_ms": 220.0,
            "tokens_per_s_decode": 38.0,
            "vram_peak_mb": 3250.0,
            "steps": [],
        },
        {
            "pair_id": "N0003",
            "register": "formal",
            "raw_output": "Surabaya.",
            "parsed_call": None,
            "latency_ms": 150.0,
            "tokens_per_s_decode": 45.0,
            "vram_peak_mb": 3200.0,
            "steps": [],
        },
    ]

    scored = [score_item(rec, it, reg) for rec, it in zip(raw_recs, items, strict=True)]
    assert scored[0]["exa"] is True
    assert scored[1]["cvr"] is True and scored[1]["exa"] is False and scored[1]["wvs"] is True
    assert scored[2]["abs"] is True

    agg = aggregate_metrics(scored)
    assert agg["CVR"] == 1.0
    assert agg["TSA"] == 1.0
    assert agg["WVS"] == 0.5
    assert agg["ABS"] == 1.0
    assert agg["delta_register"]["formal_minus_informal"] == 1.0


def test_bootstrap_mcnemar_holm_and_gee() -> None:
    pair_scores = {f"P{i:04d}": [1.0, 0.0, 1.0] if i % 2 == 0 else [1.0, 1.0, 1.0] for i in range(20)}
    ci = paired_bootstrap_ci(pair_scores, n_resamples=1000, seed=1)
    assert 0.0 <= ci["ci_low"] <= ci["mean"] <= ci["ci_high"] <= 1.0

    reg_scores = {f"P{i:04d}": {"formal": 1, "informal": 0 if i < 10 else 1} for i in range(20)}
    gap_ci = paired_register_gap_ci(reg_scores, "formal", "informal", n_resamples=1000, seed=1)
    assert gap_ci["delta"] == 0.5
    assert gap_ci["ci_low"] > 0.0

    mc = mcnemar_test([1] * 20, [0] * 10 + [1] * 10)
    assert mc["n10"] == 10 and mc["n01"] == 0
    assert mc["p_value"] < 0.01

    hc = holm_correction([0.001, 0.04, 0.20])
    assert hc["reject"] == [True, False, False]

    assert baseline_floor_check(0.15)["passed"] is False
    assert baseline_floor_check(0.65)["passed"] is True

    # GEE interaction test for Exp B
    rows = []
    for pid in range(30):
        for reg in ("formal", "informal", "campur"):
            for bits in (16, 8, 6, 4, 3):
                prob_like = 1 if (bits >= 6 or (reg == "formal" and bits >= 4) or pid % 3 == 0) else 0
                rows.append({"pair_id": f"P{pid:04d}", "register": reg, "quant_bits": bits, "exa": prob_like})
    gee_res = quant_register_interaction_gee(pd.DataFrame(rows))
    assert gee_res["n_obs"] == 30 * 3 * 5
    assert "quant_bits" in gee_res["params"]


def test_load_all_workspace_yaml_configs() -> None:
    from indoarg.config import load_experiment_config, load_inference_config, load_models_config

    models = load_models_config()
    assert len(models.models) == 5
    inf = load_inference_config()
    assert inf.main.thinking == "off"
    assert inf.main.temperature == 0.0
    assert load_experiment_config("configs/experiment_A.yaml").quant == "Q4_K_M"
    assert load_experiment_config("configs/experiment_B.yaml").all_quants() == ["BF16", "Q8_0", "Q6_K", "Q4_K_M", "Q3_K_M"]
    assert len(load_experiment_config("configs/experiment_C.yaml").all_runtimes()) == 3


def test_s2_s3_explicit_no_call_sentinel_scoring() -> None:
    reg = ToolRegistry.default_target_tools()
    gold_nocall = EvalItem(
        item_id="N0001__formal",
        pair_id="N0001",
        split="dev",
        register_name="formal",
        prompt="Apa ibu kota Indonesia?",
        reference_time="2026-11-23T18:00:00+07:00",
        tool_target=None,
        gold_call=None,
        strict_keys=[],
        soft_keys={},
        value_categories=["no_call"],
    )
    gold_call_item = EvalItem(
        item_id="P0002__formal",
        pair_id="P0002",
        split="dev",
        register_name="formal",
        prompt="Buatkan pengingat lusa pukul 07.30.",
        reference_time="2026-11-23T18:00:00+07:00",
        tool_target="buat_pengingat",
        gold_call=GoldCall(name="buat_pengingat", arguments={"judul": "bayar kos", "waktu": "2026-11-25T07:30:00+07:00"}),
        strict_keys=["waktu"],
        soft_keys={"judul": SoftKeySpec(method="fuzzy", threshold=75)},
        value_categories=["waktu_relatif"],
    )
    raw_sentinel = '{"name": "no_call", "arguments": {}}'

    # On gold no_call, explicit {"name": "no_call"} must score ABS=True, EXA=True, 0 errors (NOT E_PARSE)
    s_nc = score_item({"pair_id": "N0001", "register": "formal", "raw_output": raw_sentinel, "parsed_call": None}, gold_nocall, reg)
    assert s_nc["exa"] is True and s_nc["abs"] is True and s_nc["error_codes"] == []

    # On gold call, explicit {"name": "no_call"} must score E_UNDERCALL (NOT E_PARSE)
    s_uc = score_item({"pair_id": "P0002", "register": "formal", "raw_output": raw_sentinel, "parsed_call": None}, gold_call_item, reg)
    assert s_uc["exa"] is False and s_uc["error_codes"] == ["E_UNDERCALL"]

    # Truly broken JSON must still score E_PARSE
    s_bad = score_item({"pair_id": "P0002", "register": "formal", "raw_output": '{"name": "buat_pengingat", "arguments": {', "parsed_call": None}, gold_call_item, reg)
    assert s_bad["error_codes"] == ["E_PARSE"]
