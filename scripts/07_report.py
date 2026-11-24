"""Hasilkan tabel (CSV/MD) dan grafik wajib (§12.3) dari hasil scoring IndoArg."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rich.console import Console

console = Console()


def _df_to_markdown(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = ["-" if pd.isna(v) else str(v) for v in row]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def _save_main_table(runs: list[dict], tables_dir: Path, exp: str) -> pd.DataFrame:
    rows = []
    for r in runs:
        m = r["metrics"]
        ci = r["exa_bootstrap_ci"]
        eff = m.get("efficiency", {})
        rows.append(
            {
                "model_id": r["model_id"],
                "strategy": r["strategy"],
                "quant": r["quant"],
                "runtime": r["runtime"],
                "EXA": m.get("EXA"),
                "EXA_ci_low": ci.get("ci_low"),
                "EXA_ci_high": ci.get("ci_high"),
                "CVR": m.get("CVR"),
                "TSA": m.get("TSA"),
                "WVS": m.get("WVS"),
                "ABS": m.get("ABS"),
                "delta_formal_informal": m.get("delta_register", {}).get("formal_minus_informal"),
                "delta_formal_campur": m.get("delta_register", {}).get("formal_minus_campur"),
                "latency_p50_ms": eff.get("latency_p50_ms"),
                "tokens_per_s": eff.get("mean_tokens_per_s"),
                "vram_peak_mb": eff.get("vram_peak_mb"),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(tables_dir / f"{exp}_main_table.csv", index=False)
    (tables_dir / f"{exp}_main_table.md").write_text(_df_to_markdown(df), encoding="utf-8")
    return df


def _plot_register_bars(runs: list[dict], figures_dir: Path, exp: str) -> None:
    reg_rows = []
    for r in runs:
        by_reg = r["metrics"].get("EXA_by_register", {})
        reg_rows.append(
            {
                "label": f"{r['model_id']}-{r['strategy']}",
                "formal": by_reg.get("formal", 0.0),
                "informal": by_reg.get("informal", 0.0),
                "campur": by_reg.get("campur", 0.0),
            }
        )
    if not reg_rows:
        return
    df = pd.DataFrame(reg_rows)
    x = np.arange(len(df))
    w = 0.25
    fig, ax = plt.subplots(figsize=(max(7, len(df) * 1.1), 4.5))
    ax.bar(x - w, df["formal"], width=w, label="Formal")
    ax.bar(x, df["informal"], width=w, label="Informal")
    ax.bar(x + w, df["campur"], width=w, label="Campur")
    ax.set_xticks(x)
    ax.set_xticklabels(df["label"], rotation=30, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("EXA")
    ax.set_title(f"{exp}: EXA per Register (Formal / Informal / Campur)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / f"{exp}_register_gap.png", dpi=180)
    plt.close(fig)


def _plot_category_heatmap(runs: list[dict], figures_dir: Path, exp: str) -> None:
    cats = sorted({c for r in runs for c in r["metrics"].get("VA_by_category", {})})
    if not cats:
        return
    labels = [f"{r['model_id']}-{r['strategy']}" for r in runs]
    mat = np.array(
        [[r["metrics"].get("VA_by_category", {}).get(c, np.nan) for c in cats] for r in runs],
        dtype=float,
    )
    fig, ax = plt.subplots(figsize=(max(8, len(cats) * 0.9), max(4, len(labels) * 0.6)))
    im = ax.imshow(mat, aspect="auto", vmin=0.0, vmax=1.0, cmap="RdYlGn")
    ax.set_xticks(np.arange(len(cats)))
    ax.set_xticklabels(cats, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(cats)):
            if not np.isnan(mat[i, j]):
                ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="VA (EXA per kategori)")
    ax.set_title(f"{exp}: Value Accuracy per Kategori Nilai")
    fig.tight_layout()
    fig.savefig(figures_dir / f"{exp}_va_heatmap.png", dpi=180)
    plt.close(fig)


def _plot_error_distribution(runs: list[dict], figures_dir: Path, exp: str) -> None:
    err_codes = sorted({e for r in runs for e in r["metrics"].get("error_counts", {})})
    if not err_codes:
        return
    labels = [f"{r['model_id']}-{r['strategy']}" for r in runs]
    bottom = np.zeros(len(runs))
    x = np.arange(len(runs))
    fig, ax = plt.subplots(figsize=(max(7, len(runs) * 1.1), 4.5))
    for code in err_codes:
        vals = np.array([r["metrics"].get("error_counts", {}).get(code, 0) for r in runs], dtype=float)
        ax.bar(x, vals, bottom=bottom, label=code)
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Jumlah Error")
    ax.set_title(f"{exp}: Distribusi Taksonomi Error")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / f"{exp}_error_taxonomy.png", dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Buat tabel dan grafik laporan IndoArg.")
    parser.add_argument("--exp", required=True, help="Nama eksperimen (misal A_main)")
    parser.add_argument("--scored-dir", default="results/scored")
    parser.add_argument("--out", nargs=2, default=["results/tables", "results/figures"], metavar=("TABLES_DIR", "FIGURES_DIR"))
    args = parser.parse_args()

    summary_path = Path(args.scored_dir) / f"{args.exp}_summary.json"
    if not summary_path.exists():
        console.print(f"[red]File ringkasan tidak ditemukan: {summary_path}. Jalankan scripts/06_score.py dahulu.[/red]")
        return 1

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    runs = data.get("runs", [])
    tables_dir, figures_dir = Path(args.out[0]), Path(args.out[1])
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    _save_main_table(runs, tables_dir, args.exp)
    _plot_register_bars(runs, figures_dir, args.exp)
    _plot_category_heatmap(runs, figures_dir, args.exp)
    _plot_error_distribution(runs, figures_dir, args.exp)

    if data.get("mcnemar_holm"):
        pd.DataFrame(data["mcnemar_holm"]).to_csv(
            tables_dir / f"{args.exp}_mcnemar_holm.csv",
            index=False,
        )

    console.print(f"[green][OK][/green] Tabel disimpan ke {tables_dir} dan grafik ke {figures_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
