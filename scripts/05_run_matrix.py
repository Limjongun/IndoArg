"""Jalankan matriks eksperimen IndoArg (wajib lolos gerbang 01_verify_quant.py)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from rich.console import Console
from tqdm import tqdm

from indoarg.config import (
    load_experiment_config,
    load_inference_config,
    load_models_config,
    load_prompt_text,
    repo_root,
)
from indoarg.data import expand_pairs, load_pairs
from indoarg.runners import LlamaCppRunner, OllamaRunner
from indoarg.strategies import run_strategy
from indoarg.tools.registry import ToolRegistry
from indoarg.utils.hashing import sha256_file, sha256_text
from indoarg.utils.sysinfo import collect_sysinfo, detect_llamacpp_binary

# Import quantization verification gate directly
sys.path.insert(0, str(Path(__file__).resolve().parent))
_verify_mod = import_module("01_verify_quant")

console = Console()
WIB = timezone(timedelta(hours=7))


def _load_done_keys(jsonl_path: Path) -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if not jsonl_path.exists():
        return done
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            done.add((rec["pair_id"], rec["register"]))
    return done


def _start_managed_llamacpp(
    model_path: Path,
    *,
    port: int,
    n_ctx: int,
    ngl: int | None,
    use_fit: bool,
    log_path: Path,
) -> tuple[subprocess.Popen[Any], Any]:
    _, base_cmd = detect_llamacpp_binary()
    if not base_cmd:
        raise RuntimeError("Biner llama / llama-server tidak ditemukan di PATH.")

    cmd = [
        *base_cmd,
        "-m",
        str(model_path),
        "--jinja",
        "-c",
        str(n_ctx),
        "-fa",
        "on",
        "--parallel",
        "1",
        "--port",
        str(port),
    ]
    if use_fit:
        cmd.extend(["--fit", "on"])
    elif ngl is not None:
        cmd.extend(["-ngl", str(ngl)])
    else:
        cmd.extend(["-ngl", "99"])

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("w", encoding="utf-8")
    console.print(f"[cyan]Menyalakan server otomatis:[/cyan] {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT)

    health_url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + 180.0
    with httpx.Client(trust_env=False, timeout=2.0) as health_client:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                log_fh.close()
                raise RuntimeError(
                    f"Server llama.cpp berhenti dengan kode {proc.returncode}. Cek log: {log_path}"
                )
            try:
                r = health_client.get(health_url)
                if r.status_code == 200:
                    console.print(f"[green][SERVER SIAP][/green] http://127.0.0.1:{port} (log: {log_path})")
                    return proc, log_fh
            except Exception:
                pass
            time.sleep(1.0)

    proc.terminate()
    log_fh.close()
    raise TimeoutError(f"Server llama.cpp tidak siap dalam 180 detik. Cek log: {log_path}")


def main() -> int:
    load_dotenv(repo_root() / ".env")
    parser = argparse.ArgumentParser(description="Eksekusi matriks eksperimen IndoArg.")
    parser.add_argument("--exp", required=True, help="Path ke configs/experiment_*.yaml")
    parser.add_argument("--model", required=True, help="Model ID yang sedang aktif di server (misal M1)")
    parser.add_argument("--quant", help="Tingkat kuantisasi aktif (default: dari experiment YAML)")
    parser.add_argument("--strategies", nargs="*", help="Subset strategi (default: dari experiment YAML)")
    parser.add_argument("--runtime", choices=["llamacpp_server", "llamacpp_jinja", "llamacpp_grammar", "ollama_native"])
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--ollama-model", help="Nama tag model Ollama (untuk runtime ollama_native)")
    parser.add_argument("--pairs", default="data/pairs/indoarg_v1.jsonl")
    parser.add_argument("--split", choices=["dev", "test"], help="Override split (default: dari experiment YAML)")
    parser.add_argument("--tag", help="Override prefix nama eksperimen output (default: <name> untuk test, <name>_dev untuk dev)")
    parser.add_argument("--grammar", default="grammars/tools_v1.gbnf")
    parser.add_argument("--limit", type=int, help="Batasi jumlah item (untuk uji coba)")
    parser.add_argument("--resume", help="Path file results/raw/<run_id>.jsonl untuk melanjutkan 1 strategi")
    parser.add_argument("--auto-resume", action="store_true", help="Otomatis lanjutkan file raw terbaru per strategi jika sudah ada")
    parser.add_argument("--auto-server", action="store_true", help="Nyalakan dan matikan server llama.cpp otomatis untuk model ini")
    parser.add_argument("--port", type=int, default=8080, help="Port server saat memakai --auto-server")
    parser.add_argument("--ngl", type=int, default=None, help="Jumlah GPU layers (-ngl) untuk --auto-server")
    parser.add_argument("--fit", action="store_true", help="Gunakan --fit on pada --auto-server (otomatis aktif jika GGUF > 4 GB)")
    args = parser.parse_args()

    exp_cfg = load_experiment_config(args.exp)
    models_cfg = load_models_config()
    inf_cfg = load_inference_config()

    quant = args.quant or exp_cfg.all_quants()[0]
    if args.model not in exp_cfg.models:
        console.print(f"[red]Model '{args.model}' tidak terdaftar pada {args.exp} ({exp_cfg.models})[/red]")
        return 1

    # MANDATORY QUANTIZATION GATE (§5.2)
    gate_ok, quant_rows, bad = _verify_mod.verify_experiment_quant(args.exp, quant_filter=quant)
    if not gate_ok:
        console.print(f"[red][GERBANG GAGAL][/red] Kuantisasi tidak seragam untuk {quant}: {bad}")
        console.print("Eksperimen ditolak berjalan demi aturan kuantisasi seragam (§5).")
        return 1

    gguf_sha_map = {r["model"]: r["sha256"] for r in quant_rows if r["expected_quant"] == quant}
    gguf_sha = gguf_sha_map.get(args.model, "")

    spec = models_cfg.by_id(args.model)
    split = args.split or exp_cfg.split
    exp_tag = args.tag or (f"{exp_cfg.name}_dev" if split == "dev" else exp_cfg.name)
    strategies = args.strategies or exp_cfg.strategies
    runtime_name = args.runtime or exp_cfg.all_runtimes()[0]

    sys_prompt = load_prompt_text("system_id.txt")
    st1_prompt = load_prompt_text("s3_stage1_id.txt")
    st2_prompt = load_prompt_text("s3_stage2_id.txt")
    target_reg = ToolRegistry.default_target_tools()
    norm_reg = ToolRegistry.default_normalizer_tools()
    grammar_text = Path(args.grammar).read_text(encoding="utf-8") if Path(args.grammar).exists() else None

    pairs = load_pairs(args.pairs)
    items = expand_pairs(pairs, split=split, registers=exp_cfg.registers)
    if args.limit:
        items = items[: args.limit]

    managed_proc: subprocess.Popen[Any] | None = None
    managed_log_fh: Any = None
    endpoint = args.endpoint

    try:
        if args.auto_server and runtime_name != "ollama_native":
            gguf_path = Path(exp_cfg.model_dir) / quant / f"{spec.id}.gguf"
            auto_fit = args.fit or (gguf_path.stat().st_size > 4_000_000_000)
            srv_log = Path("logs/runtime") / f"{exp_tag}_{spec.id}_{quant}.log"
            managed_proc, managed_log_fh = _start_managed_llamacpp(
                gguf_path,
                port=args.port,
                n_ctx=inf_cfg.main.n_ctx,
                ngl=args.ngl,
                use_fit=auto_fit if args.ngl is None else False,
                log_path=srv_log,
            )
            endpoint = f"http://127.0.0.1:{args.port}/v1"

        if runtime_name == "ollama_native":
            if not args.ollama_model:
                console.print("[red]--ollama-model wajib diisi untuk runtime ollama_native[/red]")
                return 1
            runner = OllamaRunner(model_tag=args.ollama_model, host=endpoint, inference_cfg=inf_cfg)
            server_model_info: dict[str, Any] = {"ollama_model": args.ollama_model}
        else:
            runner = LlamaCppRunner(
                base_url=endpoint,
                model_spec=spec,
                inference_cfg=inf_cfg,
                runtime_name=runtime_name,
            )
            ok_model, server_model_info = runner.verify_loaded_model(spec.id)
            if not ok_model:
                console.print(
                    f"[red][GAGAL VERIFIKASI MODEL SERVER][/red] Endpoint {endpoint} tidak memuat {spec.id}.gguf!\n"
                    f"  Terdeteksi di server: {server_model_info}\n"
                    "  Hentikan proses llama.exe lama (Stop-Process -Name llama -Force) lalu jalankan ulang server."
                )
                return 1
            console.print(f"[dim]Model terverifikasi di server: {server_model_info}[/dim]")

        runtime_ver = runner.get_runtime_version()
        raw_dir = Path("results/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = Path("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)

        for strat in strategies:
            effective_strat = "S2" if runtime_name == "llamacpp_grammar" else strat
            out_path: Path | None = None
            if args.resume and len(strategies) == 1:
                out_path = Path(args.resume)
                run_id = out_path.stem
            elif args.auto_resume:
                prefix = f"{exp_tag}__{spec.id}__{effective_strat}__{quant}__{runtime_name}__"
                matches = sorted(raw_dir.glob(f"{prefix}*.jsonl"))
                if matches:
                    out_path = matches[-1]
                    run_id = out_path.stem

            if out_path is None:
                ts_id = datetime.now(WIB).strftime("%Y%m%dT%H%M")
                run_id = f"{exp_tag}__{spec.id}__{effective_strat}__{quant}__{runtime_name}__{ts_id}"
                out_path = raw_dir / f"{run_id}.jsonl"

            done_keys = _load_done_keys(out_path)

            # Write reproducibility manifest (§13)
            manifest = {
                "run_id": run_id,
                "experiment": exp_tag,
                "model_id": spec.id,
                "model_name": spec.name,
                "server_model_info": server_model_info,
                "quant": quant,
                "gguf_sha256": gguf_sha,
                "runtime": runtime_name,
                "runtime_version": runtime_ver,
                "strategy": effective_strat,
                "split": split,
                "inference_yaml_sha256": sha256_file("configs/inference.yaml"),
                "system_prompt_sha256": sha256_text(sys_prompt),
                "quant_manifest": quant_rows,
                "sysinfo": collect_sysinfo(repo_root()),
            }
            (logs_dir / f"manifest_{run_id}.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            console.print(
                f"[cyan]Menjalankan[/cyan] {run_id} ({len(items)} item, selesai={len(done_keys)}) -> {out_path}"
            )
            with out_path.open("a", encoding="utf-8") as fh:
                for item in tqdm(items, desc=f"{spec.id}/{effective_strat}"):
                    if (item.pair_id, item.register_name) in done_keys:
                        continue
                    res = run_strategy(
                        effective_strat,
                        runner=runner,
                        prompt=item.prompt,
                        reference_time=item.reference_time,
                        system_prompt=sys_prompt,
                        target_registry=target_reg,
                        normalizer_registry=norm_reg,
                        grammar_text=grammar_text,
                        stage1_prompt=st1_prompt,
                        stage2_prompt=st2_prompt,
                    )
                    record: dict[str, Any] = {
                        "run_id": run_id,
                        "experiment": exp_tag,
                        "model_id": spec.id,
                        "gguf_sha256": gguf_sha,
                        "quant": quant,
                        "runtime": runtime_name,
                        "runtime_version": runtime_ver,
                        "strategy": effective_strat,
                        "pair_id": item.pair_id,
                        "register": item.register_name,
                        "prompt_hash": res.prompt_hash,
                        "request": res.request,
                        "raw_output": res.raw_output,
                        "steps": res.steps,
                        "parsed_call": res.parsed_call,
                        "latency_ms": res.latency_ms,
                        "prompt_tokens": res.prompt_tokens,
                        "completion_tokens": res.completion_tokens,
                        "tokens_per_s_decode": res.tokens_per_s_decode,
                        "vram_peak_mb": res.vram_peak_mb,
                        "thinking_forced": res.thinking_forced,
                        "error": res.error,
                        "timestamp": datetime.now(WIB).isoformat(),
                    }
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    fh.flush()

        console.print("[green][SELESAI][/green] Eksekusi matriks selesai.")
        return 0
    finally:
        if managed_proc is not None:
            console.print("[dim]Menghentikan server llama.cpp otomatis...[/dim]")
            managed_proc.terminate()
            try:
                managed_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                managed_proc.kill()
        if managed_log_fh is not None:
            managed_log_fh.close()


if __name__ == "__main__":
    sys.exit(main())
