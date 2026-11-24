"""GERBANG VERIFIKASI KUANTISASI: gagal (exit 1) bila GGUF dalam satu eksperimen tidak seragam."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from indoarg.config import load_experiment_config
from indoarg.utils.gguf_meta import read_file_type
from indoarg.utils.hashing import sha256_file


def verify_experiment_quant(
    exp_cfg_path: str | Path,
    quant_filter: str | None = None,
    models_filter: list[str] | None = None,
) -> tuple[bool, list[dict[str, Any]], list[tuple[str, str, str]]]:
    """Verify uniform GGUF quantization for every model and level in an experiment config."""
    cfg = load_experiment_config(exp_cfg_path)
    quants = [quant_filter] if quant_filter else cfg.all_quants()
    model_ids = models_filter if models_filter else cfg.models

    rows: list[dict[str, Any]] = []
    bad: list[tuple[str, str, str]] = []

    for expected in quants:
        for m in model_ids:
            p = Path(cfg.model_dir) / expected / f"{m}.gguf"
            if not p.exists():
                rows.append(
                    {
                        "experiment": cfg.name,
                        "expected_quant": expected,
                        "model": m,
                        "file": str(p),
                        "file_type": "MISSING",
                        "sha256": None,
                    }
                )
                bad.append((m, expected, "MISSING"))
                continue

            ft = read_file_type(p)
            digest = sha256_file(p)
            rows.append(
                {
                    "experiment": cfg.name,
                    "expected_quant": expected,
                    "model": m,
                    "file": str(p),
                    "file_type": ft,
                    "sha256": digest,
                }
            )
            if ft != expected:
                bad.append((m, expected, ft))

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = logs_dir / f"quant_manifest_{cfg.name}.json"
    manifest_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(bad) == 0, rows, bad


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gerbang verifikasi kuantisasi GGUF seragam (Blueprint §5)."
    )
    parser.add_argument("exp_cfg", help="Path ke configs/experiment_*.yaml")
    parser.add_argument("--quant", help="Verifikasi satu tingkat kuantisasi saja (opsional)")
    parser.add_argument("--models", nargs="*", help="Filter subset model ID (opsional)")
    args = parser.parse_args()

    ok, rows, bad = verify_experiment_quant(args.exp_cfg, quant_filter=args.quant, models_filter=args.models)
    if not ok:
        print(f"[GAGAL] kuantisasi tidak seragam atau file hilang: {bad}")
        return 1
    quants_checked = sorted({r["expected_quant"] for r in rows})
    print(f"[OK] semua {len(rows)} model terverifikasi seragam untuk kuantisasi {quants_checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
