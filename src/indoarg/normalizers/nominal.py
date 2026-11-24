"""Indonesian currency, abbreviation, number-word, and Betawi slang normalizer."""

from __future__ import annotations

import csv
import functools
import re
from pathlib import Path
from typing import Any

from indoarg.config import repo_root

_UNITS: dict[str, int] = {
    "nol": 0,
    "kosong": 0,
    "satu": 1,
    "dua": 2,
    "tiga": 3,
    "empat": 4,
    "lima": 5,
    "enam": 6,
    "tujuh": 7,
    "delapan": 8,
    "sembilan": 9,
    "sepuluh": 10,
    "sebelas": 11,
}

_FOREIGN_CURRENCIES = (
    "usd", "dolar", "dollar", "sgd", "eur", "euro", "jpy", "yen",
    "myr", "ringgit", "gbp", "pound", "aud", "hkd", "cny", "rmb",
)


@functools.lru_cache(maxsize=1)
def _load_slang_table(csv_path: Path | None = None) -> dict[str, tuple[int, int]]:
    path = csv_path or (repo_root() / "data" / "gazetteer" / "slang_angka.csv")
    table: dict[str, tuple[int, int]] = {}
    if not path.exists():
        return table
    with path.open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = row["slang"].strip().lower()
            table[key] = (int(row["nilai_dasar"]), int(row["nilai_rupiah_konteks_uang"]))
    return table


def _parse_decimal(raw: str) -> float:
    cleaned = raw.strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def _parse_indonesian_words(text: str) -> int | None:
    """Parse Indonesian cardinal number phrases such as 'dua ratus lima puluh ribu'."""
    low = re.sub(r"[^a-z\s]", " ", text.lower())
    low = re.sub(r"\s+", " ", low).strip()
    if not low:
        return None

    # Handle explicit fractional idioms first
    if re.search(r"\bsejuta\s+setengah\b", low):
        return 1_500_000
    if re.search(r"\bsetengah\s+juta\b", low):
        return 500_000
    if re.search(r"\bseperempat\s+juta\b", low):
        return 250_000

    # Expand common fused Indonesian prefixes ("seratus", "seribu", "sejuta", "limapuluh")
    low = re.sub(r"\bseratus\b", "satu ratus", low)
    low = re.sub(r"\bseribu\b", "satu ribu", low)
    low = re.sub(r"\bsejuta\b", "satu juta", low)
    low = re.sub(r"\bsemiliar\b", "satu miliar", low)
    low = re.sub(r"\blimapuluh\b", "lima puluh", low)
    low = re.sub(r"\bduapuluh\b", "dua puluh", low)
    low = re.sub(r"\btigapuluh\b", "tiga puluh", low)

    tokens = low.split()
    total = 0
    group = 0
    pending = 0
    matched_any = False
    for tok in tokens:
        if tok in _UNITS:
            pending += _UNITS[tok]
            matched_any = True
        elif tok == "belas":
            group += (pending if pending else 1) + 10
            pending = 0
            matched_any = True
        elif tok == "puluh":
            group += (pending if pending else 1) * 10
            pending = 0
            matched_any = True
        elif tok == "ratus":
            group += (pending if pending else 1) * 100
            pending = 0
            matched_any = True
        elif tok == "ribu":
            chunk = group + pending
            total += (chunk if chunk else 1) * 1_000
            group = 0
            pending = 0
            matched_any = True
        elif tok == "juta":
            chunk = group + pending
            total += (chunk if chunk else 1) * 1_000_000
            group = 0
            pending = 0
            matched_any = True
        elif tok in ("miliar", "milyar"):
            chunk = group + pending
            total += (chunk if chunk else 1) * 1_000_000_000
            group = 0
            pending = 0
            matched_any = True
        elif tok == "setengah" and matched_any:
            # e.g., "dua juta setengah"
            if total >= 1_000_000 and total % 1_000_000 == 0:
                total += 500_000
            elif total >= 1_000 and total % 1_000 == 0:
                total += 500

    if not matched_any:
        return None
    return total + group + pending


def parse_nominal(teks: str, currency_context: str = "auto") -> dict[str, Any]:
    """Normalize Indonesian money expressions (slang, short forms, words, Rp) to integer."""
    raw = teks.strip()
    low = raw.lower()

    is_foreign = False
    if currency_context != "auto":
        is_foreign = currency_context.upper() != "IDR"
    else:
        is_foreign = any(re.search(rf"\b{cur}\b", low) for cur in _FOREIGN_CURRENCIES)

    # 1. Explicit slang + "ribu"/"rb"/"k" (e.g. "cepek ribu", "gocap ribu", "gopek ribu")
    slang_table = _load_slang_table()
    for slang, (base_val, _idr_val) in sorted(slang_table.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"\b{re.escape(slang)}\s*(?:ribu|rb|k)\b", low):
            val = base_val * 1_000 if base_val < 1_000 else base_val
            return {"nominal": int(val), "source": "slang_ribu"}

    # 2. Standalone slang match (e.g. "gocap", "ceban", "noban", "cepek")
    # Hanya cocokkan kosakata slang satu/dua kata Betawi, bukan subfrasa bilangan baku ("lima puluh ribu" dalam "seratus lima puluh ribu").
    _word_num_prefixes = ("satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "seratus", "ratus", "seribu", "sejuta", "setengah", "seperempat", "limapuluh")
    for slang, (base_val, idr_val) in sorted(slang_table.items(), key=lambda kv: len(kv[0]), reverse=True):
        if slang.split()[0] in _word_num_prefixes:
            continue
        if re.search(rf"\b{re.escape(slang)}\b", low):
            val = base_val if is_foreign else idr_val
            # Check trailing "setengah" (e.g. "ceban setengah" -> 15000)
            if re.search(rf"\b{re.escape(slang)}\s+setengah\b", low):
                val = int(val * 1.5)
            return {"nominal": int(val), "source": "slang"}

    # 3. Numeric value with scale suffix: 1,5jt / 50rb / 50k / 200 ribu / 2,5 juta
    if m := re.search(
        r"(?:rp\.?\s*)?(\d+(?:[.,]\d+)?)\s*(jt|juta|miliar|milyar|rb|ribu|k)\b",
        low,
    ):
        num = _parse_decimal(m.group(1))
        unit = m.group(2)
        mult = {
            "k": 1_000,
            "rb": 1_000,
            "ribu": 1_000,
            "jt": 1_000_000,
            "juta": 1_000_000,
            "miliar": 1_000_000_000,
            "milyar": 1_000_000_000,
        }[unit]
        return {"nominal": int(round(num * mult)), "source": "numeric_suffix"}

    # 4. Formatted rupiah or dotted thousands: Rp50.000, Rp 1.500.000, 200.000
    if m := re.search(r"(?:rp\.?\s*)?(\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?\b", low):
        digits = m.group(1).replace(".", "")
        return {"nominal": int(digits), "source": "formatted_thousands"}

    # 5. Indonesian number words ("dua ratus ribu", "seratus lima puluh ribu", "setengah juta")
    word_val = _parse_indonesian_words(low)
    if word_val is not None:
        return {"nominal": int(word_val), "source": "words"}

    # 6. Plain integer (e.g. "Rp50000", "100 USD")
    if m := re.search(r"(?:rp\.?\s*)?(\d+)\b", low):
        return {"nominal": int(m.group(1)), "source": "plain_int"}

    return {"error": f"Tidak dapat menormalisasi nominal: '{teks}'", "nominal": None}
