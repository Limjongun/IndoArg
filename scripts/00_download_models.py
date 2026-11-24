"""Download GGUF models for an experiment config while enforcing exact quantization names."""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from indoarg.config import load_experiment_config, load_models_config
from indoarg.utils.gguf_meta import read_file_type

console = Console()


def _configure_disk_d_cache(model_dir: Path) -> Path:
    """Force all Hugging Face, Xet, and temp directories inside model_dir (disk D), never disk C."""
    hf_home = (model_dir / "_hf_cache").resolve()
    tmp_dir = (model_dir / "_tmp").resolve()
    hf_home.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HF_HUB_CACHE", str(Path(os.environ["HF_HOME"]) / "hub"))
    os.environ.setdefault("HF_XET_CACHE", str(Path(os.environ["HF_HOME"]) / "xet"))
    os.environ.setdefault("HF_ASSETS_CACHE", str(Path(os.environ["HF_HOME"]) / "assets"))
    os.environ.setdefault("TMP", str(tmp_dir))
    os.environ.setdefault("TEMP", str(tmp_dir))
    return hf_home


def _pick_gguf_file(files: list[str], pattern: str, quant: str) -> str | None:
    """Select exact matching GGUF filename for quant, rejecting lookalike quant suffixes."""
    target_pat = pattern.replace("{QUANT}", quant).lower()
    candidates = [
        f for f in files
        if f.lower().endswith(".gguf") and fnmatch.fnmatch(Path(f).name.lower(), target_pat)
    ]
    # Avoid mmproj or imatrix auxiliary files
    candidates = [f for f in candidates if "mmproj" not in f.lower()]
    if not candidates:
        return None
    # Prefer exact -{QUANT}.gguf suffix over loose wildcard matches
    exact_suffix = f"-{quant.lower()}.gguf"
    for c in candidates:
        if c.lower().endswith(exact_suffix):
            return c
    return sorted(candidates, key=len)[0]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    parser = argparse.ArgumentParser(description="Download GGUF models defined in experiment YAML.")
    parser.add_argument("--exp", required=True, help="Path ke configs/experiment_*.yaml")
    parser.add_argument("--models-cfg", default="configs/models.yaml", help="Path ke configs/models.yaml")
    parser.add_argument("--models", nargs="*", help="Filter subset model ID (misal M1 M4)")
    parser.add_argument("--quant", help="Filter satu tingkat kuantisasi (untuk experiment_B.yaml)")
    parser.add_argument("--dry-run", action="store_true", help="Tampilkan rencana unduhan tanpa mengunduh")
    args = parser.parse_args()

    exp = load_experiment_config(args.exp)
    models_cfg = load_models_config(args.models_cfg)
    hf_home = _configure_disk_d_cache(Path(exp.model_dir))
    console.print(f"[dim]Cache Hugging Face & temp dikunci ke: {hf_home}[/dim]")

    # Import huggingface_hub SETELAH env cache diatur agar konstanta HF_HOME/HF_XET_CACHE mengarah ke disk D.
    from huggingface_hub import HfApi, hf_hub_download

    quants = [args.quant] if args.quant else exp.all_quants()
    model_ids = args.models if args.models else exp.models
    token = os.getenv("HF_TOKEN") or None
    api = HfApi(token=token)

    failures: list[str] = []
    for quant in quants:
        dest_dir = Path(exp.model_dir) / quant
        dest_dir.mkdir(parents=True, exist_ok=True)
        for mid in model_ids:
            spec = models_cfg.by_id(mid)
            dest_path = dest_dir / f"{mid}.gguf"
            if dest_path.exists():
                ft = read_file_type(dest_path)
                console.print(f"[green][SKIP][/green] {dest_path} sudah ada (file_type={ft})")
                continue

            console.print(f"[cyan]Mencari[/cyan] {spec.hf_repo} untuk {mid} @ {quant}...")
            try:
                repo_files = api.list_repo_files(repo_id=spec.hf_repo, token=token)
            except Exception as exc:
                failures.append(f"{mid}@{quant}: gagal daftar file ({exc})")
                console.print(f"[red][GAGAL][/red] {mid}@{quant}: {exc}")
                continue

            matched = _pick_gguf_file(repo_files, spec.file_pattern, quant)
            if not matched:
                failures.append(f"{mid}@{quant}: tidak ditemukan pola '{spec.file_pattern}' di {spec.hf_repo}")
                console.print(
                    f"[yellow][TIDAK ADA][/yellow] {mid}@{quant} di {spec.hf_repo}. "
                    "Gunakan Mode Ketat (§5.3) untuk kuantisasi mandiri dari BF16."
                )
                continue

            if args.dry_run:
                console.print(f"[blue][DRY-RUN][/blue] {spec.hf_repo}/{matched} -> {dest_path}")
                continue

            console.print(f"[cyan]Mengunduh[/cyan] {matched} -> {dest_path}")
            dl_dir = dest_dir / "_dl_tmp"
            dl_dir.mkdir(parents=True, exist_ok=True)
            cached_file = hf_hub_download(
                repo_id=spec.hf_repo,
                filename=matched,
                token=token,
                local_dir=str(dl_dir),
            )
            shutil.move(cached_file, dest_path)
            ft = read_file_type(dest_path)
            if ft != quant:
                failures.append(f"{mid}@{quant}: metadata GGUF={ft} (diharapkan {quant})")
                console.print(f"[red][MISMATCH][/red] {dest_path}: file_type={ft} != {quant}")
            else:
                console.print(f"[green][OK][/green] {dest_path} terverifikasi ({ft})")

    if failures:
        console.print("\n[red]Ringkasan kegagalan:[/red]")
        for msg in failures:
            console.print(f"  - {msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
