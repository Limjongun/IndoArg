"""Read and verify GGUF quantization metadata (general.file_type)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gguf import GGUFReader, LlamaFileType

# Pemetaan kanonik nama singkat kuantisasi dari enum llama_ftype.
_SHORT_MAP: dict[int, str] = {
    0: "F32",
    1: "F16",
    2: "Q4_0",
    3: "Q4_1",
    7: "Q8_0",
    8: "Q5_0",
    9: "Q5_1",
    10: "Q2_K",
    11: "Q3_K_S",
    12: "Q3_K_M",
    13: "Q3_K_L",
    14: "Q4_K_S",
    15: "Q4_K_M",
    16: "Q5_K_S",
    17: "Q5_K_M",
    18: "Q6_K",
    19: "IQ2_XXS",
    20: "IQ2_XS",
    21: "Q2_K_S",
    22: "IQ3_XS",
    23: "IQ3_XXS",
    24: "IQ1_S",
    25: "IQ4_NL",
    26: "IQ3_S",
    27: "IQ3_M",
    28: "IQ2_S",
    29: "IQ2_M",
    30: "IQ4_XS",
    31: "IQ1_M",
    32: "BF16",
}


def ftype_code_to_label(code: int) -> str:
    """Convert numeric GGUF general.file_type to canonical quantization label."""
    try:
        enum_member = LlamaFileType(code)
        name = enum_member.name
        if name.startswith("MOSTLY_"):
            return name.removeprefix("MOSTLY_")
        if name.startswith("ALL_"):
            return name.removeprefix("ALL_")
        return name
    except ValueError:
        return _SHORT_MAP.get(code, f"UNKNOWN({code})")


def read_file_type_code(path: str | Path) -> int:
    reader = GGUFReader(str(path))
    field = reader.fields.get("general.file_type")
    if field is None:
        raise ValueError(f"Metadata 'general.file_type' tidak ditemukan di {path}")
    return int(field.parts[field.data[0]][0])


def read_file_type(path: str | Path) -> str:
    """Read canonical quantization type string from GGUF metadata."""
    return ftype_code_to_label(read_file_type_code(path))


def _decode_str_field(reader: GGUFReader, key: str) -> str | None:
    field = reader.fields.get(key)
    if field is None:
        return None
    try:
        raw = bytes(field.parts[field.data[0]])
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return str(field.parts[field.data[0]])


def read_gguf_summary(path: str | Path) -> dict[str, Any]:
    """Return structured metadata summary for reproducibility manifests."""
    p = Path(path)
    reader = GGUFReader(str(p))
    ft_code = read_file_type_code(p)
    return {
        "file": str(p),
        "size_bytes": p.stat().st_size,
        "file_type_code": ft_code,
        "file_type": ftype_code_to_label(ft_code),
        "architecture": _decode_str_field(reader, "general.architecture"),
        "name": _decode_str_field(reader, "general.name"),
        "has_chat_template": "tokenizer.chat_template" in reader.fields,
    }
