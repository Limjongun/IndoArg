# 04. Petunjuk Operasional Workspace

Panduan teknis langkah demi langkah untuk menjalankan seluruh pipeline **IndoArg** pada mesin Windows (PowerShell) maupun Linux/WSL2.

---

## 4.1 Lingkungan Terverifikasi di Mesin Ini

- **Workspace:** `D:\Indoarg`
- **Virtual Environment:** `D:\Indoarg\.venv` (Python `3.11.9`, paket `indoarg` terpasang *editable*)
- **GPU:** NVIDIA GeForce RTX 4050 Laptop GPU (`6141 MiB` VRAM, Driver `616.56`, CUDA `13.4`)
- **RAM:** `23,3 GB` | **Ruang Disk `D:`:** `145,5 GB` kosong
- **Runtime llama.cpp:** `llama.exe` (`version 0.5.0-dev, build 11379, commit 1537a0a8b`, backend `CUDA0` aktif)
- **Runtime Ollama:** `ollama 0.40.17`

---

## 4.2 Aktivasi & Konfigurasi Awal

```powershell
# 1. Masuk ke folder workspace dan aktifkan virtual environment
cd D:\Indoarg
.\.venv\Scripts\Activate.ps1

# 2. (Opsional) Siapkan .env jika perlu HF_TOKEN atau custom endpoint
Copy-Item .env.example .env
```

Pastikan semua unit test dan linter hijau sebelum memulai eksperimen:

```powershell
make test
make lint
```

---

## 4.3 Prosedur Pipeline Langkah demi Langkah

### Langkah 1 — Unduh Model GGUF (Eksperimen A @ `Q4_K_M`)

Cek rencana unduhan terlebih dahulu (*dry run*) agar tidak salah file:

```powershell
python scripts/00_download_models.py --exp configs/experiment_A.yaml --dry-run
```

Unduh seluruh model Eksp. A (atau satu per satu dengan `--models M1`):

```powershell
python scripts/00_download_models.py --exp configs/experiment_A.yaml
# atau satu model dulu untuk smoke test:
python scripts/00_download_models.py --exp configs/experiment_A.yaml --models M1
```

File otomatis disimpan sebagai `models/Q4_K_M/M1.gguf`, `M2.gguf`, ..., `M5.gguf` dan langsung diverifikasi header `general.file_type`-nya.

### Langkah 2 — Jalankan Gerbang Verifikasi Kuantisasi Seragam

```powershell
python scripts/01_verify_quant.py configs/experiment_A.yaml
# atau lewat Makefile:
make verify EXP=A
```

- **Exit code `0`:** seluruh model di eksperimen terkonfirmasi memiliki `general.file_type` identik dan SHA-256 dicatat ke `logs/quant_manifest_A_main.json`.
- **Exit code `1`:** ada file hilang atau tipe kuantisasi tidak seragam; eksperimen akan diblokir.

Untuk Eksperimen B (per tingkat tangga atau seluruh tangga):

```powershell
python scripts/01_verify_quant.py configs/experiment_B.yaml --quant Q6_K
python scripts/01_verify_quant.py configs/experiment_B.yaml
```

### Langkah 3 — Validasi Dataset & Bangun Grammar GBNF

```powershell
# Validasi skema, gold_call, duplikasi varian, dan split
python scripts/02_validate_data.py data/pairs/indoarg_v1.jsonl

# Gunakan --strict-targets saat korpus 220 pair sudah lengkap
python scripts/02_validate_data.py data/pairs/indoarg_v1.jsonl --strict-targets

# Kompilasi grammars/tools_v1.gbnf dari data/tools/tools_v1.json
python scripts/03_build_grammar.py data/tools/tools_v1.json grammars/tools_v1.gbnf
```

### Langkah 4 — Menjalankan Server Model Lokal (Satu Model per Waktu)

**A. Via `llama serve` (biner `llama.exe` yang terpasang):**

```powershell
# Model 3B-4B @ Q4_K_M (M1, M3, M4) — muat penuh di GPU RTX 4050 6 GB
llama serve -m models/Q4_K_M/M1.gguf --jinja -ngl 99 -c 8192 -fa on --parallel 1 --port 8080
```

> **Penyesuaian Khusus GPU 6 GB VRAM (RTX 4050):**
> Untuk model **M2 (Qwen3.5-9B, ~6,2 GB)**, **M5 (SEA-LION-8B, ~5,1 GB + KV cache 8K)**, atau tingkat **`BF16` / `Q8_0`** di Eksperimen B:
> 1. Jalankan `llama fit-params -m models/Q4_K_M/M2.gguf -c 8192` untuk melihat rekomendasi jumlah layer GPU (`-ngl`) yang aman tanpa OOM.
> 2. Mulai server dengan `-ngl` hasil rekomendasi (misal `-ngl 24` atau `-ngl 0` untuk CPU murni pada BF16), sambil menjaga `--jinja -c 8192 -fa on --parallel 1` tetap identik.

**B. Via Ollama (khusus Eksperimen C — memakai file GGUF lokal yang SAMA):**

```powershell
# Buat model Ollama langsung dari file GGUF lokal agar SHA-256 bobot identik
ollama create indoarg-m1-q4km -f models/modelfiles/M1.Modelfile
ollama create indoarg-m5-q4km -f models/modelfiles/M5.Modelfile
```

### Langkah 5 — Jalankan Smoke Test (14 Kasus)

Buka terminal PowerShell baru (aktifkan `.venv`) sementara server model berjalan di terminal pertama:

```powershell
python scripts/04_smoke_test.py --model M1 --endpoint http://127.0.0.1:8080/v1 --strategy S1
# atau lewat Makefile:
make smoke MODEL=M1
```

Kriteria kelulusan: **gagal parse ≤ 2 dari 14 kasus**. Hasil tersimpan di `logs/smoke_<model>_<strategy>_<timestamp>.json`.

### Langkah 6 — Eksekusi Matriks Eksperimen

**Tuning prompt (split `dev` saja):**

```powershell
python scripts/05_run_matrix.py --exp configs/experiment_A.yaml --model M1 --split dev --strategies S1 S2 S3 S4 --endpoint http://127.0.0.1:8080/v1
```

**Run final (split `test`):**

```powershell
python scripts/05_run_matrix.py --exp configs/experiment_A.yaml --model M1 --endpoint http://127.0.0.1:8080/v1
```

**Melanjutkan run yang terputus (`--resume`):**

```powershell
python scripts/05_run_matrix.py --exp configs/experiment_A.yaml --model M1 --resume results/raw/A_main__M1__S1__Q4_K_M__llamacpp_server__20261125T1010.jsonl
```

**Eksperimen C via Ollama native:**

```powershell
python scripts/05_run_matrix.py --exp configs/experiment_C.yaml --model M1 --runtime ollama_native --ollama-model indoarg-m1-q4km --endpoint http://127.0.0.1:11434
```

### Langkah 7 — Skoring, Statistik, dan Pembuatan Laporan

```powershell
python scripts/06_score.py --exp A_main
python scripts/07_report.py --exp A_main --out results/tables results/figures
```

Keluaran otomatis:
- `results/scored/A_main__*.jsonl` & `results/scored/A_main_summary.json`
- `results/tables/A_main_main_table.csv`, `A_main_main_table.md`, `A_main_mcnemar_holm.csv`
- `results/figures/A_main_register_gap.png`, `A_main_va_heatmap.png`, `A_main_error_taxonomy.png`

---

## 4.4 Ringkasan Perintah `Makefile`

| Perintah | Fungsi |
|---|---|
| `make help` | Menampilkan semua target shortcut |
| `make download EXP=A` | Mengunduh model GGUF untuk `configs/experiment_A.yaml` |
| `make verify EXP=A` | Menjalankan gerbang kuantisasi seragam |
| `make validate` | Memvalidasi `data/pairs/indoarg_v1.jsonl` |
| `make grammar` | Membangun ulang `grammars/tools_v1.gbnf` |
| `make smoke MODEL=M1` | Menjalankan 14 kasus smoke test ke `ENDPOINT` |
| `make run EXP=A MODEL=M1` | Menjalankan matriks eksperimen untuk model aktif |
| `make score EXP_NAME=A_main` | Menjalankan skoring + bootstrap CI + McNemar/Holm |
| `make report EXP_NAME=A_main` | Menghasilkan tabel CSV/MD dan grafik PNG |
| `make test` / `make lint` | Menjalankan `pytest` / `ruff check` |

---

## 4.5 Troubleshooting Umum

| Gejala | Penyebab Umum | Solusi |
|---|---|---|
| `01_verify_quant.py` keluar dengan `exit 1` | Model belum diunduh atau varian quant keliru (mis. `Q4_K_S` / `IQ4_XS`) | Unduh ulang file exact `Q4_K_M` via `00_download_models.py` atau kuantisasi mandiri (§3.4) |
| Server `llama serve` crash / OOM CUDA | VRAM 6 GB penuh pada model 8B–9B atau `BF16` | Jalankan `llama fit-params` lalu kurangi `-ngl` |
| Qwen3.5 mengeluarkan `<think>...</think>` panjang | Template model mengaktifkan mode *thinking* | Pastikan flag `--jinja` aktif; `llamacpp_runner.py` sudah mengirim `chat_template_kwargs.enable_thinking=false` dan menandai `thinking_forced=true` jika model tetap berpikir |
| Gemma 4 gagal parse tool call | Parser runtime versi lama atau tanpa `--jinja` | Wajib pakai `--jinja` pada `llama.exe` build `11379`; periksa log `logs/smoke_M3_*.json` |
| Error `ollama: model not found` di Eksp. C | Modelfile belum didaftarkan ke daemon Ollama | Jalankan `ollama create indoarg-m1-q4km -f models/modelfiles/M1.Modelfile` dari root `D:\Indoarg` |

---

## 4.6 Reproducibility Checklist (§15)

- [ ] Versi build `llama.cpp` (`b11379`) dan `Ollama` (`0.40.17`) tercatat dan tidak diperbarui selama run.
- [ ] Gerbang `01_verify_quant.py` lulus untuk setiap eksperimen dan setiap tingkat tangga kuantisasi.
- [ ] SHA-256 setiap file GGUF tercatat di `logs/manifest_<run_id>.json` (dan identik antara `llama.cpp` dan `Ollama` di Eksp. C).
- [ ] Mode *thinking* dimatikan atau dicatat eksplisit melalui kolom `thinking_forced`.
- [ ] `configs/prompts/system_id.txt` identik untuk semua model; `system_prompt_sha256` tercatat di manifest.
- [ ] Split `test` hanya dijalankan sekali pada run final (tidak pernah dipakai untuk tuning prompt).
- [ ] Seluruh 220 pair diverifikasi oleh 2 anotator (A1 & A2) dengan kesepakatan antar-anotator dilaporkan.
- [ ] CI 95% dihitung lewat *paired bootstrap* level `pair_id` (10.000 resample); uji perbandingan majemuk memakai koreksi Holm.
- [ ] Dataset, kode, konfigurasi, dan `docs/data_card.md` dirilis bersih tanpa data pribadi asli (PII).
