"""Indonesian colloquial date & time normalizer -> ISO-8601 (+07:00)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import dateparser

WIB = timezone(timedelta(hours=7))

_MONTHS: dict[str, int] = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2, "peb": 2, "pebruari": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agt": 8, "agustus": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "okt": 10, "oktober": 10, "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "des": 12, "desember": 12, "dec": 12, "december": 12,
}

_WEEKDAYS: dict[str, int] = {
    "senin": 0,
    "selasa": 1,
    "rabu": 2,
    "kamis": 3,
    "jumat": 4,
    "jum'at": 4,
    "sabtu": 5,
    "minggu": 6,
    "ahad": 6,
}


def _parse_ref(waktu_acuan: str) -> datetime:
    dt = datetime.fromisoformat(waktu_acuan)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WIB)
    return dt.astimezone(WIB)


def _extract_date(low: str, ref: datetime) -> tuple[datetime | None, bool]:
    # 1. Explicit ISO date YYYY-MM-DD
    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d, tzinfo=WIB), True

    # 2. Explicit DD/MM(/YYYY) or DD-MM(-YYYY)
    if m := re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", low):
        d, mo = int(m.group(1)), int(m.group(2))
        y_raw = m.group(3)
        y = ref.year if y_raw is None else (2000 + int(y_raw) if len(y_raw) == 2 else int(y_raw))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return datetime(y, mo, d, tzinfo=WIB), True

    # 3. DD MonthName (YYYY)
    month_pat = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
    if m := re.search(rf"\b(?:tgl|tanggal)?\s*(\d{{1,2}})\s+({month_pat})\b(?:\s+(\d{{4}}))?", low):
        d = int(m.group(1))
        mo = _MONTHS[m.group(2)]
        y = int(m.group(3)) if m.group(3) else ref.year
        return datetime(y, mo, d, tzinfo=WIB), True

    # 4. tgl DD / tanggal DD
    if m := re.search(r"\b(?:tgl|tanggal)\s+(\d{1,2})\b", low):
        d = int(m.group(1))
        y, mo = ref.year, ref.month
        if d < ref.day:
            mo += 1
            if mo > 12:
                mo = 1
                y += 1
        return datetime(y, mo, d, tzinfo=WIB), True

    # 5. Relative words
    if re.search(r"\blusa\b", low):
        return (ref + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0), True
    if re.search(r"\b(?:besok|bsk|esok)\b", low):
        return (ref + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0), True
    if re.search(r"\b(?:kemarin|kmrn)\b", low):
        return (ref - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0), True
    if re.search(r"\b(?:hari ini|hr ini|skrg|sekarang)\b", low):
        return ref.replace(hour=0, minute=0, second=0, microsecond=0), True

    # 6. "minggu depan" (= +7 hari, kecuali "hari minggu depan" = hari Minggu berikutnya)
    if re.search(r"\bminggu depan\b", low) and not re.search(r"\bhari\s+minggu depan\b", low):
        return (ref + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0), True

    # 7. Weekday + depan / ini (e.g. "Senin depan", "hari Minggu depan")
    wk_pat = "|".join(_WEEKDAYS.keys())
    if m := re.search(rf"\b({wk_pat})\s+(depan|berikutnya|ini)\b", low):
        target_wd = _WEEKDAYS[m.group(1)]
        qualifier = m.group(2)
        diff = (target_wd - ref.weekday()) % 7
        if qualifier in ("depan", "berikutnya"):
            if diff == 0:
                diff = 7
        target = ref + timedelta(days=diff)
        return target.replace(hour=0, minute=0, second=0, microsecond=0), True

    return None, False


def _apply_period(hour: int, period: str | None) -> int:
    if period is None:
        return hour
    p = period.lower()
    if p in ("pagi", "subuh", "dini hari"):
        return 0 if hour == 12 else hour
    if p == "siang":
        if 1 <= hour <= 5:
            return hour + 12
        return hour
    if p in ("sore", "petang"):
        if 1 <= hour <= 11:
            return hour + 12
        return hour
    if p in ("malam", "malem", "mlm"):
        if hour == 12:
            return 0
        if 1 <= hour <= 11:
            return hour + 12
        return hour
    return hour


def _extract_time(low: str) -> tuple[int, int, bool]:
    period_m = re.search(r"\b(pagi|subuh|dini hari|siang|sore|petang|malam|malem|mlm)\b", low)
    period = period_m.group(1) if period_m else None

    # 1. "setengah <H>" (Indonesian: setengah 8 = 07:30)
    if m := re.search(r"\b(?:setengah|stgh|1/2)\s+(\d{1,2})\b", low):
        raw_h = int(m.group(1))
        h = (raw_h - 1) if raw_h > 1 else 12
        h = _apply_period(h, period)
        return h % 24, 30, True

    # 2. "jam/pukul H kurang/lewat M"
    if m := re.search(
        r"\b(?:jam|pukul|pkl)\s*(\d{1,2})(?:an)?\s+(kurang|lewat|lebih)\s+(\d{1,2}|seperempat|setengah)\b",
        low,
    ):
        raw_h = int(m.group(1))
        rel = m.group(2)
        min_raw = m.group(3)
        mins = 15 if min_raw == "seperempat" else (30 if min_raw == "setengah" else int(min_raw))
        h = _apply_period(raw_h, period)
        base_minutes = (h * 60) + (mins if rel in ("lewat", "lebih") else -mins)
        base_minutes %= 24 * 60
        return base_minutes // 60, base_minutes % 60, True

    # 3. "jam/pukul HH:MM" or "HH.MM"
    if m := re.search(r"\b(?:jam|pukul|pkl)?\s*(\d{1,2})[:.](\d{2})(?:\s*(?:wib|am|pm))?\b", low):
        raw_h, raw_m = int(m.group(1)), int(m.group(2))
        if 0 <= raw_h <= 23 and 0 <= raw_m <= 59:
            # Handle explicit am/pm if present
            if re.search(r"\bpm\b", low) and 1 <= raw_h <= 11:
                raw_h += 12
            elif re.search(r"\bam\b", low) and raw_h == 12:
                raw_h = 0
            elif raw_h <= 12 and period:
                raw_h = _apply_period(raw_h, period)
            return raw_h, raw_m, True

    # 4. "jam/pukul H(an)"
    if m := re.search(r"\b(?:jam|pukul|pkl)\s*(\d{1,2})(?:an)?\b", low):
        raw_h = int(m.group(1))
        if 0 <= raw_h <= 23:
            h = _apply_period(raw_h, period) if raw_h <= 12 else raw_h
            return h % 24, 0, True

    # 5. Standalone "<H> am/pm"
    if m := re.search(r"\b(\d{1,2})\s*(am|pm)\b", low):
        raw_h = int(m.group(1))
        ampm = m.group(2)
        if ampm == "pm" and 1 <= raw_h <= 11:
            raw_h += 12
        elif ampm == "am" and raw_h == 12:
            raw_h = 0
        return raw_h % 24, 0, True

    return 0, 0, False


def parse_waktu(teks: str, waktu_acuan: str) -> dict[str, Any]:
    """Normalize Indonesian date/time expression relative to waktu_acuan."""
    ref = _parse_ref(waktu_acuan)
    low = teks.strip().lower()

    date_dt, found_date = _extract_date(low, ref)
    hour, minute, found_time = _extract_time(low)

    if found_date or found_time:
        base = date_dt if found_date and date_dt is not None else ref.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if found_time:
            result_dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=WIB)
        else:
            result_dt = base.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=WIB)
        return {
            "iso": result_dt.isoformat(),
            "date": result_dt.strftime("%Y-%m-%d"),
            "has_time": found_time,
            "source": "rule",
        }

    # Fallback to dateparser for unhandled expressions
    dp = dateparser.parse(
        teks,
        languages=["id", "en"],
        settings={
            "RELATIVE_BASE": ref.replace(tzinfo=None),
            "PREFER_DATES_FROM": "future",
            "DATE_ORDER": "DMY",
        },
    )
    if dp is not None:
        result_dt = dp.replace(second=0, microsecond=0, tzinfo=WIB)
        return {
            "iso": result_dt.isoformat(),
            "date": result_dt.strftime("%Y-%m-%d"),
            "has_time": True,
            "source": "dateparser",
        }

    return {"error": f"Tidak dapat menormalisasi waktu: '{teks}'", "iso": None, "date": None}
