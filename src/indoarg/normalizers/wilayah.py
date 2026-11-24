"""Indonesian region code (Kemendagri) and KRL station normalizer."""

from __future__ import annotations

import csv
import functools
import re
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

from indoarg.config import repo_root


@functools.lru_cache(maxsize=1)
def _load_wilayah_data(
    gazetteer_dir: Path | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    base = gazetteer_dir or (repo_root() / "data" / "gazetteer")
    by_code: dict[str, dict[str, str]] = {}
    aliases: dict[str, str] = {}

    wilayah_csv = base / "wilayah.csv"
    if wilayah_csv.exists():
        with wilayah_csv.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                code = row["kode"].strip()
                nama = row["nama_resmi"].strip()
                by_code[code] = {
                    "kode": code,
                    "nama_resmi": nama,
                    "provinsi": row["provinsi"].strip(),
                    "tingkat": row["tingkat"].strip(),
                }
                aliases[nama.lower()] = code
                short = re.sub(r"^(?:kota administrasi|kabupaten administrasi|kota|kabupaten)\s+", "", nama.lower())
                aliases.setdefault(short, code)

    alias_csv = base / "alias_wilayah.csv"
    if alias_csv.exists():
        with alias_csv.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                aliases[row["alias"].strip().lower()] = row["kode"].strip()

    return by_code, aliases


@functools.lru_cache(maxsize=1)
def _load_krl_data(
    gazetteer_dir: Path | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    base = gazetteer_dir or (repo_root() / "data" / "gazetteer")
    by_code: dict[str, dict[str, str]] = {}
    aliases: dict[str, str] = {}

    krl_csv = base / "stasiun_krl.csv"
    if krl_csv.exists():
        with krl_csv.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                code = row["kode"].strip().upper()
                nama = row["nama_stasiun"].strip()
                by_code[code] = {
                    "kode": code,
                    "nama_stasiun": nama,
                    "lintas": row["lintas"].strip(),
                }
                aliases[code.lower()] = code
                aliases[nama.lower()] = code
                for a in row.get("alias", "").split("|"):
                    a_clean = a.strip().lower()
                    if a_clean:
                        aliases[a_clean] = code
    return by_code, aliases


def _clean_place(teks: str) -> str:
    low = teks.strip().lower()
    low = re.sub(r"[^\w\s.]", " ", low)
    low = re.sub(r"^(?:dari|dr|ke|di|menuju|kota|kab\.?|kabupaten)\s+", "", low)
    low = re.sub(r"\s+", " ", low).strip()
    return low


def cari_wilayah(teks: str, fuzzy_threshold: float = 75.0) -> dict[str, Any]:
    """Resolve city/regency name or abbreviation (e.g. 'Jaksel', 'sby') to Kemendagri code."""
    by_code, aliases = _load_wilayah_data()
    raw = teks.strip()

    if re.fullmatch(r"\d{2}\.\d{2}", raw) and raw in by_code:
        return {**by_code[raw], "score": 100.0, "source": "exact_code"}

    candidates = [raw.lower().strip(), _clean_place(raw)]
    for cand in candidates:
        if cand in aliases:
            code = aliases[cand]
            info = by_code.get(code, {"kode": code, "nama_resmi": code})
            return {**info, "score": 100.0, "source": "exact_alias"}

    query = _clean_place(raw)
    if not query or not aliases:
        return {"error": f"Wilayah tidak ditemukan: '{teks}'", "kode": None}

    match = process.extractOne(query, list(aliases.keys()), scorer=fuzz.WRatio)
    if match and match[1] >= fuzzy_threshold:
        code = aliases[match[0]]
        info = by_code.get(code, {"kode": code, "nama_resmi": code})
        return {**info, "score": round(float(match[1]), 1), "source": "fuzzy"}

    return {"error": f"Wilayah tidak ditemukan: '{teks}'", "kode": None}


def cari_stasiun_krl(teks: str, fuzzy_threshold: float = 78.0) -> dict[str, Any]:
    """Resolve KRL station name or colloquial alias to official station code."""
    by_code, aliases = _load_krl_data()
    raw = teks.strip()
    up = raw.upper()
    if up in by_code:
        return {**by_code[up], "score": 100.0, "source": "exact_code"}

    cleaned = re.sub(r"^(?:stasiun|st\.?|sta\.?)\s+", "", raw.lower().strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for cand in (raw.lower().strip(), cleaned):
        if cand in aliases:
            code = aliases[cand]
            return {**by_code[code], "score": 100.0, "source": "exact_alias"}

    if not cleaned or not aliases:
        return {"error": f"Stasiun KRL tidak ditemukan: '{teks}'", "kode": None}

    match = process.extractOne(cleaned, list(aliases.keys()), scorer=fuzz.WRatio)
    if match and match[1] >= fuzzy_threshold:
        code = aliases[match[0]]
        return {**by_code[code], "score": round(float(match[1]), 1), "source": "fuzzy"}

    return {"error": f"Stasiun KRL tidak ditemukan: '{teks}'", "kode": None}
