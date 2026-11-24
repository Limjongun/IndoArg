"""Indonesian unit & duration normalizer (weight, duration, length, volume)."""

from __future__ import annotations

import re
from typing import Any

_WORD_NUM: dict[str, float] = {
    "setengah": 0.5,
    "stgh": 0.5,
    "seperempat": 0.25,
    "se": 1.0,
    "satu": 1.0,
    "dua": 2.0,
    "tiga": 3.0,
    "empat": 4.0,
    "lima": 5.0,
    "enam": 6.0,
    "tujuh": 7.0,
    "delapan": 8.0,
    "sembilan": 9.0,
    "sepuluh": 10.0,
    "lima belas": 15.0,
    "dua puluh": 20.0,
    "tiga puluh": 30.0,
    "empat puluh lima": 45.0,
}

# Conversion factors to canonical base unit per target category.
_FACTORS: dict[str, dict[str, float]] = {
    "gram": {
        "g": 1.0, "gr": 1.0, "gram": 1.0,
        "ons": 100.0,
        "kg": 1000.0, "kilo": 1000.0, "kilogram": 1000.0,
        "kuintal": 100_000.0, "kwintal": 100_000.0,
        "ton": 1_000_000.0,
    },
    "menit": {
        "detik": 1.0 / 60.0, "dtk": 1.0 / 60.0, "sec": 1.0 / 60.0,
        "menit": 1.0, "mnt": 1.0, "min": 1.0, "minute": 1.0, "minutes": 1.0,
        "jam": 60.0, "hr": 60.0, "hour": 60.0, "hours": 60.0,
    },
    "meter": {
        "mm": 0.001, "milimeter": 0.001,
        "cm": 0.01, "sentimeter": 0.01,
        "m": 1.0, "meter": 1.0,
        "km": 1000.0, "kilometer": 1000.0,
    },
    "mililiter": {
        "ml": 1.0, "mililiter": 1.0, "cc": 1.0,
        "l": 1000.0, "lt": 1000.0, "liter": 1000.0,
    },
}


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


def parse_satuan(teks: str, target: str) -> dict[str, Any]:
    """Convert Indonesian quantity expression to canonical target unit (gram/menit/meter/mililiter)."""
    tgt = target.strip().lower()
    if tgt not in _FACTORS:
        return {"error": f"Satuan target tidak dikenal: '{target}'", "nilai": None}

    factors = _FACTORS[tgt]
    low = teks.strip().lower()
    # Expand Indonesian "se-" fused units: sekilo -> 1 kilo, sejam -> 1 jam, seliter -> 1 liter, semeter -> 1 meter
    low = re.sub(r"\bsekilo(?:gram)?\b", "1 kilo", low)
    low = re.sub(r"\bsejam\b", "1 jam", low)
    low = re.sub(r"\bseliter\b", "1 liter", low)
    low = re.sub(r"\bsemeter\b", "1 meter", low)
    low = re.sub(r"\bseons\b", "1 ons", low)

    unit_pat = "|".join(sorted(factors.keys(), key=len, reverse=True))

    # 1. Compound expressions like "1 jam 30 menit" or "2 kilo 500 gram"
    matches = list(re.finditer(rf"(\d+(?:[.,]\d+)?)\s*({unit_pat})\b", low))
    if matches:
        total = 0.0
        for m in matches:
            qty = _to_float(m.group(1))
            unit = m.group(2)
            # Check trailing "setengah" or "seperempat" right after this match
            after = low[m.end():].lstrip()
            if re.match(r"^(?:setengah|stgh)\b", after):
                qty += 0.5
            elif re.match(r"^seperempat\b", after):
                qty += 0.25
            total += qty * factors[unit]
        rounded = int(round(total)) if abs(total - round(total)) < 1e-6 else round(total, 4)
        return {"nilai": rounded, "target": tgt, "source": "numeric"}

    # 2. Word quantity + unit (e.g., "setengah kilo", "seperempat kilo", "dua jam setengah", "dua jam seperempat")
    word_pat = "|".join(sorted(_WORD_NUM.keys(), key=len, reverse=True))
    if m := re.search(rf"\b({word_pat})\s+({unit_pat})(?:\s+(setengah|stgh|seperempat))?\b", low):
        qty = _WORD_NUM[m.group(1)]
        if m.group(3) in ("setengah", "stgh"):
            qty += 0.5
        elif m.group(3) == "seperempat":
            qty += 0.25
        total = qty * factors[m.group(2)]
        rounded = int(round(total)) if abs(total - round(total)) < 1e-6 else round(total, 4)
        return {"nilai": rounded, "target": tgt, "source": "word"}

    return {"error": f"Tidak dapat mengonversi '{teks}' ke satuan '{target}'", "nilai": None}
