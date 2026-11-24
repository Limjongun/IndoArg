"""Error taxonomy classification (10 error codes from IndoArg Blueprint §8)."""

from __future__ import annotations

from typing import Any

from indoarg.data import GoldCall, SoftKeySpec
from indoarg.eval.canonicalize import match_soft_value, match_strict_value
from indoarg.eval.parse import looks_like_malformed_call
from indoarg.normalizers import (
    cari_stasiun_krl,
    cari_wilayah,
    parse_nominal,
    parse_satuan,
    parse_waktu,
)
from indoarg.tools.registry import ToolRegistry

_INFORMAL_BRAND_MAP: dict[str, str] = {
    "ojol": "motor",
    "gojek": "motor",
    "goride": "motor",
    "grabbike": "motor",
    "gocar": "mobil",
    "grabcar": "mobil",
    "gopey": "gopay",
    "go-pay": "gopay",
    "shopeepay": "shopeepay",
    "spay": "shopeepay",
    "sicepat": "sicepat",
    "j&t": "jnt",
    "listrik": "pln",
    "air": "pdam",
}


def _diagnose_value_error(
    key: str,
    pred_val: Any,
    gold_val: Any,
    reference_time: str,
) -> str:
    """Distinguish E_VALUE_FORMAT vs E_VALUE_LANG vs E_VALUE_WRONG."""
    if isinstance(pred_val, str):
        low = pred_val.strip().lower()

        # 1. Region / KRL / brand colloquial text instead of canonical code/enum -> E_VALUE_LANG
        if key in ("asal", "tujuan", "wilayah"):
            res = cari_wilayah(pred_val)
            if res.get("kode") == gold_val:
                return "E_VALUE_LANG"
        if key in ("stasiun_asal", "stasiun_tujuan"):
            res = cari_stasiun_krl(pred_val)
            if res.get("kode") == gold_val:
                return "E_VALUE_LANG"
        if key in ("layanan", "platform", "kurir", "jenis"):
            if _INFORMAL_BRAND_MAP.get(low) == str(gold_val).lower():
                return "E_VALUE_LANG"

        # 2. Numeric / unit / datetime expressed in raw format instead of canonical int/ISO -> E_VALUE_FORMAT
        if key in ("nominal", "jumlah"):
            res = parse_nominal(pred_val)
            if res.get("nominal") is not None and abs(float(res["nominal"]) - float(gold_val)) < 1e-6:
                return "E_VALUE_FORMAT"
        if key == "berat_gram":
            res = parse_satuan(pred_val, "gram")
            if res.get("nilai") is not None and abs(float(res["nilai"]) - float(gold_val)) < 1e-6:
                return "E_VALUE_FORMAT"
        if key == "durasi_menit":
            res = parse_satuan(pred_val, "menit")
            if res.get("nilai") is not None and abs(float(res["nilai"]) - float(gold_val)) < 1e-6:
                return "E_VALUE_FORMAT"
        if key in ("waktu", "mulai"):
            res = parse_waktu(pred_val, reference_time)
            if res.get("iso") == gold_val:
                return "E_VALUE_FORMAT"
        if key == "tanggal":
            res = parse_waktu(pred_val, reference_time)
            if res.get("date") == gold_val:
                return "E_VALUE_FORMAT"

    return "E_VALUE_WRONG"


def classify_errors(
    *,
    raw_output: str,
    parsed_call: dict[str, Any] | None,
    gold_call: GoldCall | None,
    strict_keys: list[str],
    soft_keys: dict[str, SoftKeySpec],
    reference_time: str,
    registry: ToolRegistry,
) -> tuple[list[str], dict[str, bool], bool, bool, bool]:
    """Return (error_codes, value_correct, cvr, tsa, exa)."""
    errors: list[str] = []
    value_correct: dict[str, bool] = {}

    # Case A: gold is no_call
    if gold_call is None:
        if parsed_call is None:
            if looks_like_malformed_call(raw_output):
                return ["E_PARSE"], {}, False, False, False
            return [], {}, True, True, True
        return ["E_OVERCALL"], {}, True, False, False

    # Case B: gold requires a tool call
    if parsed_call is None:
        if looks_like_malformed_call(raw_output):
            return ["E_PARSE"], {}, False, False, False
        return ["E_UNDERCALL"], {}, False, False, False

    if parsed_call.get("_parse_error"):
        return ["E_PARSE"], {}, False, False, False

    pred_name = parsed_call.get("name")
    pred_args = parsed_call.get("arguments")
    if not isinstance(pred_name, str) or not isinstance(pred_args, dict):
        return ["E_PARSE"], {}, False, False, False

    schema_ok, _schema_msgs = registry.validate_call(pred_name, pred_args)
    cvr = schema_ok
    if not schema_ok:
        errors.append("E_SCHEMA")

    tsa = pred_name == gold_call.name
    if not tsa:
        errors.append("E_TOOL")
        return sorted(set(errors)), {}, cvr, False, False

    tool_schema = registry.get(gold_call.name) or {}
    schema_props = tool_schema.get("parameters", {}).get("properties", {})
    req_keys = set(tool_schema.get("parameters", {}).get("required", []))

    # Hallucinated extra arguments
    extra_keys = set(pred_args.keys()) - set(schema_props.keys())
    if extra_keys:
        errors.append("E_HALLUC_ARG")

    # Missing required arguments
    missing_keys = req_keys - set(pred_args.keys())
    if missing_keys:
        errors.append("E_MISSING")

    # Evaluate every gold argument
    all_keys_ok = not missing_keys and not extra_keys
    for k, gold_val in gold_call.arguments.items():
        if k not in pred_args:
            value_correct[k] = False
            all_keys_ok = False
            continue
        pred_val = pred_args[k]
        if k in soft_keys:
            ok = match_soft_value(pred_val, gold_val, soft_keys[k])
        else:
            ok = match_strict_value(k, pred_val, gold_val)
        value_correct[k] = ok
        if not ok:
            all_keys_ok = False
            err_code = _diagnose_value_error(k, pred_val, gold_val, reference_time)
            errors.append(err_code)

    exa = tsa and all_keys_ok and schema_ok
    return sorted(set(errors)), value_correct, cvr, tsa, exa
