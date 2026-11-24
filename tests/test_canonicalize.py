"""Unit tests for output parsing, value canonicalization, and error taxonomy."""

from __future__ import annotations

from indoarg.data import GoldCall, SoftKeySpec
from indoarg.eval import (
    canonicalize_value,
    classify_errors,
    extract_tool_call,
    match_soft_value,
    match_strict_value,
)
from indoarg.tools.registry import ToolRegistry

REF_TIME = "2026-11-23T18:00:00+07:00"


def test_extract_tool_call_formats() -> None:
    known = {"transfer_ewallet", "buat_pengingat"}

    # 1. Plain JSON
    out = extract_tool_call(
        '{"name": "transfer_ewallet", "arguments": {"penerima": "Rina", "nominal": 50000, "platform": "gopay"}}',
        known_tools=known,
    )
    assert out == {
        "name": "transfer_ewallet",
        "arguments": {"penerima": "Rina", "nominal": 50000, "platform": "gopay"},
    }

    # 2. Qwen <tool_call> wrapper
    qwen_raw = '<tool_call>\n{"name": "buat_pengingat", "arguments": {"judul": "rapat", "waktu": "2026-11-24T19:00:00+07:00"}}\n</tool_call>'
    out_qwen = extract_tool_call(qwen_raw, known_tools=known)
    assert out_qwen is not None and out_qwen["name"] == "buat_pengingat"

    # 3. Gemma 4 native <|tool_call>call:name{...}<tool_call|>
    gemma_raw = '<|tool_call>call:transfer_ewallet{nominal:50000,penerima:<|"|>Rina<|"|>,platform:<|"|>gopay<|"|>}<tool_call|>'
    out_gemma = extract_tool_call(gemma_raw, known_tools=known)
    assert out_gemma == {
        "name": "transfer_ewallet",
        "arguments": {"nominal": 50000, "penerima": "Rina", "platform": "gopay"},
    }

    # 4. no_call sentinel
    assert extract_tool_call('{"name": "no_call", "arguments": {}}', known_tools=known) is None


def test_canonicalize_and_soft_keys() -> None:
    assert canonicalize_value("platform", " GoPay ") == "gopay"
    assert canonicalize_value("dari", "usd") == "USD"
    assert canonicalize_value("waktu", "2026-11-24T19:00+07:00") == "2026-11-24T19:00:00+07:00"
    assert match_strict_value("nominal", 50000.0, 50000) is True
    assert match_strict_value("nominal", "50rb", 50000) is False

    spec_fuzzy = SoftKeySpec(method="fuzzy", threshold=80, aliases=["meeting"])
    assert match_soft_value("meeting", "rapat", spec_fuzzy) is True
    assert match_soft_value("belanja", "rapat", spec_fuzzy) is False

    spec_set = SoftKeySpec(method="set_casefold")
    assert match_soft_value(["sari", "andi"], ["Andi", "Sari"], spec_set) is True


def test_taxonomy_error_classification() -> None:
    reg = ToolRegistry.default_target_tools()
    gold = GoldCall(
        name="cek_ongkir",
        arguments={"asal": "35.78", "tujuan": "31.74", "berat_gram": 2000, "kurir": "jne"},
    )

    # E_VALUE_LANG ("Jaksel") + E_VALUE_FORMAT ("2 kilo") + E_SCHEMA
    errs, val_ok, cvr, tsa, exa = classify_errors(
        raw_output="{}",
        parsed_call={
            "name": "cek_ongkir",
            "arguments": {"asal": "35.78", "tujuan": "Jaksel", "berat_gram": "2 kilo", "kurir": "jne"},
        },
        gold_call=gold,
        strict_keys=["asal", "tujuan", "berat_gram", "kurir"],
        soft_keys={},
        reference_time=REF_TIME,
        registry=reg,
    )
    assert tsa is True
    assert cvr is False
    assert exa is False
    assert "E_VALUE_LANG" in errs
    assert "E_VALUE_FORMAT" in errs
    assert val_ok["asal"] is True
    assert val_ok["tujuan"] is False

    # E_OVERCALL on no_call
    errs_over, _, _, _, exa_over = classify_errors(
        raw_output="{}",
        parsed_call={"name": "cek_cuaca", "arguments": {"wilayah": "35.78", "tanggal": "2026-11-24"}},
        gold_call=None,
        strict_keys=[],
        soft_keys={},
        reference_time=REF_TIME,
        registry=reg,
    )
    assert errs_over == ["E_OVERCALL"]
    assert exa_over is False

    # Valid abstention on no_call
    errs_abs, _, cvr_abs, _, exa_abs = classify_errors(
        raw_output="Ibu kota Jawa Timur adalah Surabaya.",
        parsed_call=None,
        gold_call=None,
        strict_keys=[],
        soft_keys={},
        reference_time=REF_TIME,
        registry=reg,
    )
    assert errs_abs == []
    assert cvr_abs is True
    assert exa_abs is True
