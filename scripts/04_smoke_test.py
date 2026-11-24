"""Smoke test 14 kasus per model/runtime sebelum dimasukkan ke matriks eksperimen (§14)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from indoarg.config import load_inference_config, load_models_config, load_prompt_text
from indoarg.data import load_smoke
from indoarg.eval.taxonomy import classify_errors
from indoarg.runners import LlamaCppRunner, OllamaRunner
from indoarg.strategies import run_strategy
from indoarg.tools.registry import ToolRegistry

console = Console()
WIB = timezone(timedelta(hours=7))


def main() -> int:
    parser = argparse.ArgumentParser(description="Jalankan 14 kasus smoke test IndoArg.")
    parser.add_argument("--model", required=True, help="Model ID (misal M1, M3)")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1", help="Base URL llama-server / Ollama")
    parser.add_argument("--runtime", choices=["llamacpp", "ollama"], default="llamacpp")
    parser.add_argument("--ollama-model", help="Nama tag model Ollama (wajib jika --runtime ollama)")
    parser.add_argument("--strategy", default="S1", choices=["S1", "S2", "S3", "S4"])
    parser.add_argument("--smoke-file", default="data/smoke/smoke_14.jsonl")
    parser.add_argument("--grammar", default="grammars/tools_v1.gbnf")
    args = parser.parse_args()

    models_cfg = load_models_config()
    spec = models_cfg.by_id(args.model)
    inf_cfg = load_inference_config()
    sys_prompt = load_prompt_text("system_id.txt")
    target_reg = ToolRegistry.default_target_tools()
    norm_reg = ToolRegistry.default_normalizer_tools()
    grammar_text = Path(args.grammar).read_text(encoding="utf-8") if Path(args.grammar).exists() else None
    smoke_items = load_smoke(args.smoke_file)

    if args.runtime == "ollama":
        if not args.ollama_model:
            console.print("[red]--ollama-model wajib diisi untuk --runtime ollama[/red]")
            return 1
        runner = OllamaRunner(model_tag=args.ollama_model, host=args.endpoint, inference_cfg=inf_cfg)
        server_model_info = {"ollama_model": args.ollama_model}
    else:
        runner = LlamaCppRunner(base_url=args.endpoint, model_spec=spec, inference_cfg=inf_cfg)
        ok_model, server_model_info = runner.verify_loaded_model(spec.id)
        if not ok_model:
            console.print(
                f"[red][GAGAL VERIFIKASI MODEL SERVER][/red] Endpoint {args.endpoint} tidak memuat {spec.id}.gguf!\n"
                f"  Terdeteksi di server: {server_model_info}\n"
                "  Kemungkinan proses llama.exe lama masih berjalan di port yang sama. "
                "Hentikan proses lama (Stop-Process -Name llama -Force) lalu jalankan ulang server."
            )
            return 1
        console.print(f"[dim]Model terverifikasi di server: {server_model_info}[/dim]")

    rows = []
    parse_failures = 0
    cvr_hits = 0
    tsa_hits = 0
    exa_hits = 0

    table = Table(title=f"Smoke Test: {spec.id} ({spec.name}) | {args.runtime} | {args.strategy}")
    table.add_column("ID")
    table.add_column("Target")
    table.add_column("CVR")
    table.add_column("TSA")
    table.add_column("EXA")
    table.add_column("Errors")
    table.add_column("Latency (ms)")

    for item in smoke_items:
        res = run_strategy(
            args.strategy,
            runner=runner,
            prompt=item.prompt,
            reference_time=item.reference_time,
            system_prompt=sys_prompt,
            target_registry=target_reg,
            normalizer_registry=norm_reg,
            grammar_text=grammar_text,
        )
        errs, val_ok, cvr, tsa, exa = classify_errors(
            raw_output=res.raw_output,
            parsed_call=res.parsed_call,
            gold_call=item.gold_call,
            strict_keys=item.strict_keys,
            soft_keys=item.soft_keys,
            reference_time=item.reference_time,
            registry=target_reg,
        )
        if "E_PARSE" in errs or res.error:
            parse_failures += 1
        cvr_hits += int(cvr)
        tsa_hits += int(tsa)
        exa_hits += int(exa)

        rows.append(
            {
                "id": item.id,
                "tool_target": item.tool_target,
                "raw_output": res.raw_output,
                "parsed_call": res.parsed_call,
                "cvr": cvr,
                "tsa": tsa,
                "exa": exa,
                "error_codes": errs,
                "value_correct": val_ok,
                "latency_ms": res.latency_ms,
                "thinking_forced": res.thinking_forced,
                "error": res.error,
            }
        )
        table.add_row(
            item.id,
            str(item.tool_target or "no_call"),
            "OK" if cvr else "X",
            "OK" if tsa else "X",
            "OK" if exa else "X",
            ",".join(errs) if errs else "-",
            f"{res.latency_ms:.0f}",
        )

    console.print(table)
    n = len(smoke_items)
    passed = parse_failures <= 2
    console.print(
        f"Ringkasan: Parse gagal={parse_failures}/{n} | CVR={cvr_hits}/{n} | TSA={tsa_hits}/{n} | EXA={exa_hits}/{n}"
    )

    ts = datetime.now(WIB).strftime("%Y%m%dT%H%M")
    out_path = Path("logs") / f"smoke_{spec.id}_{args.strategy}_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "model_id": spec.id,
                "model_name": spec.name,
                "server_model_info": server_model_info,
                "runtime": runner.runtime_name,
                "runtime_version": runner.get_runtime_version(),
                "strategy": args.strategy,
                "passed": passed,
                "parse_failures": parse_failures,
                "cvr": cvr_hits,
                "tsa": tsa_hits,
                "exa": exa_hits,
                "total": n,
                "items": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    console.print(f"Log smoke test disimpan di {out_path}")

    if not passed:
        console.print("[red][GAGAL SMOKE TEST][/red] Gagal parse > 2/14; periksa chat template/parser model.")
        return 1
    console.print("[green][LULUS SMOKE TEST][/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
