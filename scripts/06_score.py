"""Scoring, taksonomi error, CI bootstrap level pair_id, dan uji McNemar + Holm."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from indoarg.data import expand_pairs, load_jsonl, load_pairs
from indoarg.eval import (
    aggregate_metrics,
    holm_correction,
    mcnemar_test,
    paired_bootstrap_ci,
    paired_register_gap_ci,
    score_item,
)
from indoarg.tools.registry import ToolRegistry

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(description="Skoring hasil eksperimen IndoArg.")
    parser.add_argument("--exp", required=True, help="Prefix nama eksperimen (misal A_main)")
    parser.add_argument("--raw-dir", default="results/raw")
    parser.add_argument("--scored-dir", default="results/scored")
    parser.add_argument("--pairs", default="data/pairs/indoarg_v1.jsonl")
    parser.add_argument("--n-bootstrap", type=int, default=10_000)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    scored_dir = Path(args.scored_dir)
    scored_dir.mkdir(parents=True, exist_ok=True)

    raw_files = sorted(raw_dir.glob(f"{args.exp}__*.jsonl"))
    if not raw_files:
        console.print(f"[yellow]Tidak ada file hasil mentah untuk '{args.exp}' di {raw_dir}[/yellow]")
        return 1

    pairs = load_pairs(args.pairs)
    gold_lookup = {
        (it.pair_id, it.register_name): it
        for it in expand_pairs(pairs)
    }
    registry = ToolRegistry.default_target_tools()

    summaries: list[dict[str, Any]] = []
    scored_by_model_strat: dict[str, dict[str, dict[tuple[str, str], int]]] = defaultdict(dict)

    table = Table(title=f"Ringkasan Skor Eksperimen: {args.exp}")
    table.add_column("Run ID")
    table.add_column("Model")
    table.add_column("Strat")
    table.add_column("Quant")
    table.add_column("CVR")
    table.add_column("TSA")
    table.add_column("EXA (95% CI)")
    table.add_column("WVS")
    table.add_column("ABS")

    for raw_path in raw_files:
        raw_rows = load_jsonl(raw_path)
        scored_rows: list[dict[str, Any]] = []
        for rec in raw_rows:
            key = (rec["pair_id"], rec["register"])
            gold = gold_lookup.get(key)
            if gold is None:
                continue
            scored_rows.append(score_item(rec, gold, registry))

        if not scored_rows:
            continue

        out_scored = scored_dir / raw_path.name
        with out_scored.open("w", encoding="utf-8") as fh:
            for srow in scored_rows:
                fh.write(json.dumps(srow, ensure_ascii=False) + "\n")

        agg = aggregate_metrics(scored_rows)

        # Pair-level bootstrap CI for EXA and register gaps
        pair_exa: dict[str, list[float]] = defaultdict(list)
        pair_reg: dict[str, dict[str, int]] = defaultdict(dict)
        for srow in scored_rows:
            pair_exa[srow["pair_id"]].append(1.0 if srow["exa"] else 0.0)
            pair_reg[srow["pair_id"]][srow["register"]] = 1 if srow["exa"] else 0

        exa_ci = paired_bootstrap_ci(pair_exa, n_resamples=args.n_bootstrap)
        gap_inf_ci = paired_register_gap_ci(pair_reg, "formal", "informal", n_resamples=args.n_bootstrap)
        gap_mix_ci = paired_register_gap_ci(pair_reg, "formal", "campur", n_resamples=args.n_bootstrap)

        meta = scored_rows[0]
        summary_entry = {
            "run_id": meta["run_id"],
            "experiment": meta["experiment"],
            "model_id": meta["model_id"],
            "strategy": meta["strategy"],
            "quant": meta["quant"],
            "runtime": meta["runtime"],
            "metrics": agg,
            "exa_bootstrap_ci": exa_ci,
            "delta_reg_ci": {
                "formal_minus_informal": gap_inf_ci,
                "formal_minus_campur": gap_mix_ci,
            },
        }
        summaries.append(summary_entry)
        scored_by_model_strat[meta["model_id"]][meta["strategy"]] = {
            (r["pair_id"], r["register"]): int(r["exa"]) for r in scored_rows
        }

        def fmt(v: Any) -> str:
            return f"{v:.3f}" if isinstance(v, (int, float)) else "-"

        table.add_row(
            meta["run_id"],
            meta["model_id"],
            meta["strategy"],
            meta["quant"],
            fmt(agg.get("CVR")),
            fmt(agg.get("TSA")),
            f"{exa_ci['mean']:.3f} [{exa_ci['ci_low']:.3f}, {exa_ci['ci_high']:.3f}]",
            fmt(agg.get("WVS")),
            fmt(agg.get("ABS")),
        )

    # Pairwise McNemar tests across strategies within each model + Holm correction
    pairwise_tests: list[dict[str, Any]] = []
    for mid, strat_map in sorted(scored_by_model_strat.items()):
        strat_names = sorted(strat_map.keys())
        for i in range(len(strat_names)):
            for j in range(i + 1, len(strat_names)):
                sa, sb = strat_names[i], strat_names[j]
                common_keys = sorted(set(strat_map[sa].keys()) & set(strat_map[sb].keys()))
                if not common_keys:
                    continue
                res = mcnemar_test(
                    [strat_map[sa][k] for k in common_keys],
                    [strat_map[sb][k] for k in common_keys],
                )
                pairwise_tests.append({"model_id": mid, "strategy_a": sa, "strategy_b": sb, **res})

    if pairwise_tests:
        holm = holm_correction([t["p_value"] for t in pairwise_tests])
        for t, padj, rej in zip(pairwise_tests, holm["p_adjusted"], holm["reject"], strict=True):
            t["p_holm"] = round(padj, 6)
            t["significant_holm_05"] = rej

    summary_out = scored_dir / f"{args.exp}_summary.json"
    summary_out.write_text(
        json.dumps(
            {"experiment": args.exp, "runs": summaries, "mcnemar_holm": pairwise_tests},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    console.print(table)
    console.print(f"[green][OK][/green] Ringkasan skor & statistik disimpan ke {summary_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
