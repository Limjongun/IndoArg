"""Validasi dataset IndoArg (skema JSON, gold_call, duplikasi varian, split, dan sebaran)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator
from rich.console import Console
from rich.table import Table

from indoarg.data import load_jsonl, load_split_ids
from indoarg.tools.registry import ToolRegistry

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validasi dataset pair IndoArg.")
    parser.add_argument("dataset", help="Path ke data/pairs/indoarg_v1.jsonl")
    parser.add_argument(
        "--schema",
        default="data/pairs/indoarg_v1.schema.json",
        help="Path ke JSON schema pair",
    )
    parser.add_argument(
        "--tools",
        default="data/tools/tools_v1.json",
        help="Path ke definisi tool",
    )
    parser.add_argument("--dev-split", default="data/splits/dev.txt")
    parser.add_argument("--test-split", default="data/splits/test.txt")
    parser.add_argument(
        "--strict-targets",
        action="store_true",
        help="Gagal jika jumlah pair belum memenuhi target final §7.2 (220 pair, >=15/tool, >=20/kategori)",
    )
    args = parser.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    pair_validator = Draft202012Validator(schema)
    registry = ToolRegistry.from_file(args.tools)
    rows = load_jsonl(args.dataset)

    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    dev_ids_in_data: set[str] = set()
    test_ids_in_data: set[str] = set()

    tool_counts: Counter[str] = Counter()
    cat_counts: Counter[str] = Counter()
    diff_counts: Counter[str] = Counter()
    n_call = 0
    n_nocall = 0

    for idx, row in enumerate(rows, start=1):
        pid = row.get("pair_id", f"ROW_{idx}")
        for err in pair_validator.iter_errors(row):
            errors.append(f"{pid}: pelanggaran skema pair -> {err.message}")

        if pid in seen_ids:
            errors.append(f"{pid}: pair_id duplikat")
        seen_ids.add(pid)

        split = row.get("split")
        if split == "dev":
            dev_ids_in_data.add(pid)
        elif split == "test":
            test_ids_in_data.add(pid)

        # Check identical variants
        variants = row.get("variants", {})
        if isinstance(variants, dict):
            norm_vars = {k: str(v).strip().casefold() for k, v in variants.items()}
            if len(set(norm_vars.values())) < len(norm_vars):
                errors.append(f"{pid}: terdapat varian register yang identik")

        # Validate gold_call vs tool_target and tool schema
        tool_target = row.get("tool_target")
        gold_call = row.get("gold_call")
        if tool_target is None:
            n_nocall += 1
            if gold_call is not None:
                errors.append(f"{pid}: tool_target null tetapi gold_call tidak null")
        else:
            n_call += 1
            tool_counts[tool_target] += 1
            if not isinstance(gold_call, dict):
                errors.append(f"{pid}: tool_target='{tool_target}' tetapi gold_call null")
            else:
                if gold_call.get("name") != tool_target:
                    errors.append(
                        f"{pid}: gold_call.name='{gold_call.get('name')}' != tool_target='{tool_target}'"
                    )
                ok, tool_errs = registry.validate_call(
                    str(gold_call.get("name", "")),
                    gold_call.get("arguments"),
                )
                if not ok:
                    errors.append(f"{pid}: gold_call gagal validasi skema tool -> {tool_errs}")

        for cat in row.get("value_categories", []):
            cat_counts[cat] += 1
        diff_counts[row.get("difficulty", "unknown")] += 1

    # Check dev/test split files consistency
    dev_path, test_path = Path(args.dev_split), Path(args.test_split)
    if dev_path.exists() and test_path.exists():
        dev_file_ids = load_split_ids(dev_path)
        test_file_ids = load_split_ids(test_path)
        overlap = dev_file_ids & test_file_ids
        if overlap:
            errors.append(f"Split dev.txt dan test.txt tumpang-tindih: {sorted(overlap)}")
        if dev_file_ids != dev_ids_in_data:
            errors.append("Daftar ID di dev.txt tidak cocok dengan split='dev' pada JSONL")
        if test_file_ids != test_ids_in_data:
            errors.append("Daftar ID di test.txt tidak cocok dengan split='test' pada JSONL")

    # Distribution checks against §7.2 targets
    if n_call < 200 or n_nocall < 20:
        warnings.append(
            f"Jumlah pair saat ini {len(rows)} ({n_call} call, {n_nocall} no_call); "
            "target final §7.2 adalah 220 pair (200 call, 20 no_call)."
        )
    for tname in registry.names:
        if tool_counts[tname] < 15:
            warnings.append(f"Tool '{tname}' baru {tool_counts[tname]} pair (target >=15).")
    expected_cats = schema["properties"]["value_categories"]["items"]["enum"]
    for cname in expected_cats:
        if cat_counts[cname] < 20:
            warnings.append(f"Kategori '{cname}' baru {cat_counts[cname]} kemunculan (target >=20).")
    if rows:
        sulit_ratio = diff_counts["sulit"] / len(rows)
        if sulit_ratio < 0.30:
            warnings.append(f"Proporsi kesulitan 'sulit' baru {sulit_ratio:.1%} (target >=30% per §17).")

    # Render summary table
    table = Table(title=f"Ringkasan Validasi Dataset: {args.dataset}")
    table.add_column("Metrik")
    table.add_column("Nilai")
    table.add_row("Total pair / item (x3 register)", f"{len(rows)} pair / {len(rows) * 3} item")
    table.add_row("Call / No-call", f"{n_call} / {n_nocall}")
    table.add_row("Split dev / test", f"{len(dev_ids_in_data)} / {len(test_ids_in_data)}")
    table.add_row("Kesulitan (mudah / sedang / sulit)", f"{diff_counts['mudah']} / {diff_counts['sedang']} / {diff_counts['sulit']}")
    table.add_row("Tool tercakup", f"{sum(1 for t in registry.names if tool_counts[t] > 0)} / {len(registry.names)}")
    table.add_row("Error struktural", str(len(errors)))
    table.add_row("Peringatan target §7.2", str(len(warnings)))
    console.print(table)

    if errors:
        console.print("\n[red]ERROR VALIDASI:[/red]")
        for e in errors:
            console.print(f"  - {e}")
        return 1

    if warnings:
        console.print("\n[yellow]CATATAN PROGRES TARGET §7.2:[/yellow]")
        for w in warnings:
            console.print(f"  - {w}")
        if args.strict_targets:
            console.print("[red][GAGAL][/red] Mode --strict-targets aktif.")
            return 1

    console.print("[green][OK][/green] Semua validasi skema, gold_call, varian, dan split lulus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
