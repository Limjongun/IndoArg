"""Canonicalize argument values and evaluate strict & soft key equality."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from rapidfuzz import fuzz

from indoarg.data import SoftKeySpec

WIB = timezone(timedelta(hours=7))

_LOWERCASE_ENUM_KEYS = {"platform", "kurir", "layanan", "jenis"}
_UPPERCASE_CODE_KEYS = {"stasiun_asal", "stasiun_tujuan", "dari", "ke"}
_ISO_DATETIME_KEYS = {"waktu", "mulai"}
_ISO_DATE_KEYS = {"tanggal"}
_INT_KEYS = {"nominal", "berat_gram", "durasi_menit", "top_k"}
_FLOAT_KEYS = {"jumlah"}


def _clean_str(val: str) -> str:
    return re.sub(r"\s+", " ", val.strip())


def _canon_iso_datetime(val: Any) -> Any:
    if not isinstance(val, str):
        return val
    s = _clean_str(val)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=WIB)
        return dt.astimezone(WIB).replace(microsecond=0).isoformat()
    except ValueError:
        return s


def _canon_iso_date(val: Any) -> Any:
    if not isinstance(val, str):
        return val
    s = _clean_str(val)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return s


def canonicalize_value(key: str, val: Any) -> Any:
    """Normalize superficial formatting differences without masking semantic/format errors."""
    if val is None:
        return None
    if key in _LOWERCASE_ENUM_KEYS and isinstance(val, str):
        return _clean_str(val).lower()
    if key in _UPPERCASE_CODE_KEYS and isinstance(val, str):
        return _clean_str(val).upper()
    if key in _ISO_DATETIME_KEYS:
        return _canon_iso_datetime(val)
    if key in _ISO_DATE_KEYS:
        return _canon_iso_date(val)
    if key in _INT_KEYS:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)) and float(val).is_integer():
            return int(val)
        return val
    if key in _FLOAT_KEYS:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return round(float(val), 6)
        return val
    if isinstance(val, str):
        return _clean_str(val)
    if isinstance(val, list):
        return [_clean_str(v) if isinstance(v, str) else v for v in val]
    return val


def match_strict_value(key: str, pred: Any, gold: Any) -> bool:
    c_pred = canonicalize_value(key, pred)
    c_gold = canonicalize_value(key, gold)
    if isinstance(c_pred, bool) != isinstance(c_gold, bool):
        return False
    if isinstance(c_pred, (int, float)) and isinstance(c_gold, (int, float)):
        return abs(float(c_pred) - float(c_gold)) < 1e-6
    return c_pred == c_gold


def match_soft_value(pred: Any, gold: Any, spec: SoftKeySpec) -> bool:
    if spec.method == "set_casefold":
        if not isinstance(pred, list) or not isinstance(gold, list):
            return False
        pred_set = {_clean_str(str(x)).casefold() for x in pred}
        gold_set = {_clean_str(str(x)).casefold() for x in gold}
        return pred_set == gold_set

    if not isinstance(pred, str) or not isinstance(gold, str):
        return False

    p_norm = _clean_str(pred).casefold()
    candidates = [_clean_str(gold).casefold(), *[_clean_str(a).casefold() for a in spec.aliases]]

    if spec.method == "casefold":
        return p_norm in candidates

    if spec.method == "fuzzy":
        best = max(
            max(fuzz.ratio(p_norm, c), fuzz.token_set_ratio(p_norm, c))
            for c in candidates
        )
        return best >= spec.threshold

    return False
