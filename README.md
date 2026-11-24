# IndoArg

Benchmark dan pipeline eksperimen untuk mengevaluasi ketangguhan *tool calling* LLM lokal (llama.cpp & Ollama) dari bahasa Indonesia sehari-hari (**formal / informal / campur**) menjadi argumen tool yang dapat dieksekusi.

Referensi spesifikasi lengkap: `IndoArg_Blueprint_Workspace (1).md`.

Dokumentasi lengkap proyek (ringkasan, landasan teori, alur eksperimen, petunjuk operasional, panduan data/anotasi, dan daftar pustaka/sitasi): [`dokumen/README.md`](dokumen/README.md).

## Prinsip Utama

1. **Kuantisasi Seragam (§5):** Semua model dalam satu eksperimen wajib memakai tipe kuantisasi GGUF yang persis sama (`Q4_K_M` untuk Eksp. A & C; tangga `BF16 → Q8_0 → Q6_K → Q4_K_M → Q3_K_M` untuk Eksp. B), diverifikasi lewat metadata `general.file_type` oleh `scripts/01_verify_quant.py`.
2. **Desain Berpasangan per Register (§7):** Satu `pair_id` = satu intent = satu `gold_call`, ditulis dalam 3 register (`formal`, `informal`, `campur`).
3. **Kunci Versi Runtime (§3.1):** Setelah smoke test lulus, jangan perbarui versi `llama.cpp` maupun `Ollama` sampai seluruh eksperimen selesai.

## Setup Cepat (Windows PowerShell)

```powershell
# Aktivasi virtual environment
.\.venv\Scripts\Activate.ps1

# Validasi data & bangun grammar GBNF
python scripts/02_validate_data.py data/pairs/indoarg_v1.jsonl
python scripts/03_build_grammar.py data/tools/tools_v1.json grammars/tools_v1.gbnf

# Jalankan unit test
pytest -q
```

## Menjalankan Server Model Lokal

Jika memakai biner terpadu `llama.exe` (build `b11379`, CUDA aktif):

```powershell
llama serve -m models/Q4_K_M/M1.gguf --jinja -ngl 99 -c 8192 -fa on --parallel 1 --port 8080
```

Atau dengan `llama-server`:

```powershell
llama-server -m models/Q4_K_M/M1.gguf --jinja -ngl 99 -c 8192 -fa on --parallel 1 --port 8080
```

> **Catatan GPU 6 GB VRAM (RTX 4050 Laptop):** Model 3B–4B Q4_K_M (`M1`, `M3`, `M4`) muat penuh di VRAM dengan `-ngl 99`. Untuk model 8B–9B (`M2`, `M5`) atau tingkat `BF16` pada Eksperimen B, gunakan `llama fit-params` atau turunkan `-ngl` (offload sebagian ke RAM 24 GB) sambil tetap menjaga seluruh parameter decoding di `configs/inference.yaml` terkunci.

## Alur Pipeline

1. `python scripts/00_download_models.py --exp configs/experiment_A.yaml`
2. `python scripts/01_verify_quant.py configs/experiment_A.yaml`
3. `python scripts/02_validate_data.py data/pairs/indoarg_v1.jsonl`
4. `python scripts/03_build_grammar.py data/tools/tools_v1.json grammars/tools_v1.gbnf`
5. `python scripts/04_smoke_test.py --model M1 --endpoint http://127.0.0.1:8080/v1`
6. `python scripts/05_run_matrix.py --exp configs/experiment_A.yaml --model M1 --endpoint http://127.0.0.1:8080/v1`
7. `python scripts/06_score.py --exp A_main`
8. `python scripts/07_report.py --exp A_main --out results/tables results/figures`
