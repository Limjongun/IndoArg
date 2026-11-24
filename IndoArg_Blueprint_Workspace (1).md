# IndoArg — Blueprint Workspace & Requirements

> **Eksperimen:** Dari bahasa Indonesia sehari-hari ke argumen *tool* yang bisa dieksekusi, pada LLM lokal (Ollama / llama.cpp).
> **Versi blueprint:** v1.0 — 23 Nov 2026
> **Aturan utama kuantisasi:** semua model di satu eksperimen **wajib memakai tipe kuantisasi yang sama** (default **Q4_K_M**). Kalau Qwen pakai Q4_K_M, Gemma, Llama dan SEA-LION juga Q4_K_M. Aturan ini ditegakkan otomatis oleh `scripts/01_verify_quant.py`.

---

## Daftar Isi

1. [Tujuan & Pertanyaan Riset](#1-tujuan--pertanyaan-riset)
2. [Struktur Workspace](#2-struktur-workspace)
3. [Dependency & Requirements](#3-dependency--requirements)
4. [Panel Model & Link (semua Q4_K_M)](#4-panel-model--link-semua-q4_k_m)
5. [Aturan Kuantisasi Seragam](#5-aturan-kuantisasi-seragam)
6. [Definisi Tool (10 tool)](#6-definisi-tool-10-tool)
7. [Data Pair Prompt (formal / informal / campur)](#7-data-pair-prompt-formal--informal--campur)
8. [Taksonomi Kategori Nilai](#8-taksonomi-kategori-nilai)
9. [Strategi S1–S4](#9-strategi-s1s4)
10. [Matriks Eksperimen A / B / C](#10-matriks-eksperimen-a--b--c)
11. [Parameter Inferensi (dikunci)](#11-parameter-inferensi-dikunci)
12. [Metrik & Statistik](#12-metrik--statistik)
13. [Format Log Hasil](#13-format-log-hasil)
14. [Pipeline & Perintah](#14-pipeline--perintah)
15. [Reproducibility Checklist](#15-reproducibility-checklist)
16. [Timeline](#16-timeline)
17. [Risiko & Mitigasi](#17-risiko--mitigasi)
18. [Referensi](#18-referensi)

---

## 1. Tujuan & Pertanyaan Riset

**Masalah.** Model kecil sering memilih tool yang benar, tapi gagal mengisi **nilai argumen** dengan benar ketika pengguna memakai bahasa sehari-hari:
"besok jam 7an malem", "transfer gocap ke Rina", "kirim 2 kilo ke Jaksel", "set reminder meeting lusa".

| Kode | Pertanyaan riset |
|---|---|
| **RQ1** | Kategori nilai mana yang paling sering gagal (waktu relatif, nominal slang, singkatan lokasi, satuan, enum)? |
| **RQ2** | Seberapa besar *register gap*, yaitu selisih akurasi eksekusi formal vs informal vs campur pada query yang isinya identik? |
| **RQ3** | Strategi mana (S1–S4) yang paling menutup gap tersebut pada model 3–9B lokal, dan apakah *grammar* justru menambah "schema valid tapi nilai salah"? |
| **RQ4** (Eksp. B) | Apakah query informal/campur rusak lebih cepat daripada formal saat bit kuantisasi diturunkan? |
| **RQ5** (Eksp. C) | Dengan file GGUF yang sama, seberapa besar selisih akurasi antar-runtime (Ollama vs llama.cpp)? |

**Klaim kebaruan (cek ulang sebelum submit):**
- Desain **berpasangan per register**: satu intent, tiga gaya bahasa, gold call yang sama.
- **Normalisasi nilai khas Indonesia** (slang angka Betawi, singkatan wilayah, jam informal).
- Interaksi register × *constraint tax* × kuantisasi pada **runtime lokal**.

---

## 2. Struktur Workspace

```
indoarg/
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── .env.example                  # HF_TOKEN, endpoint URL
├── Makefile                      # shortcut perintah pipeline
│
├── configs/
│   ├── models.yaml               # panel model + repo + quant (sumber kebenaran)
│   ├── experiment_A.yaml         # main: model × strategi @ Q4_K_M
│   ├── experiment_B.yaml         # kuantisasi × register
│   ├── experiment_C.yaml         # runtime variance
│   ├── inference.yaml            # parameter decoding yang dikunci
│   └── prompts/
│       ├── system_id.txt         # system prompt bahasa Indonesia (sama utk semua model)
│       ├── s3_stage1_id.txt      # prompt tahap-1 strategi dua tahap
│       └── s3_stage2_id.txt
│
├── data/
│   ├── tools/
│   │   ├── tools_v1.json         # 10 tool schema (OpenAI-style)
│   │   └── normalizer_tools.json # tool S4: parse_waktu, parse_nominal, cari_wilayah
│   ├── gazetteer/
│   │   ├── wilayah.csv           # kode wilayah resmi (Kemendagri/BPS) + alias
│   │   ├── alias_wilayah.csv     # "Jaksel" → 31.74 (Jakarta Selatan), dst.
│   │   ├── stasiun_krl.csv
│   │   └── slang_angka.csv       # gocap, cepek, gopek, seceng, goceng, ceban, ...
│   ├── seeds/
│   │   └── intents_seed.jsonl    # ide intent mentah sebelum ditulis 3 varian
│   ├── pairs/
│   │   ├── indoarg_v1.jsonl      # DATASET UTAMA (format di §7)
│   │   └── indoarg_v1.schema.json
│   ├── splits/
│   │   ├── dev.txt               # pair_id untuk tuning prompt (±20%)
│   │   └── test.txt              # pair_id beku untuk hasil (±80%)
│   └── smoke/
│       └── smoke_14.jsonl        # 14 kasus uji cepat per model/runtime
│
├── grammars/
│   ├── tools_v1.gbnf             # hasil generate dari tools_v1.json
│   └── README.md
│
├── models/                       # file GGUF (JANGAN di-commit, masuk .gitignore)
│   ├── Q4_K_M/
│   ├── Q8_0/
│   ├── Q6_K/
│   ├── Q3_K_M/
│   └── BF16/
│
├── src/indoarg/
│   ├── __init__.py
│   ├── config.py                 # load & validasi YAML (pydantic)
│   ├── data.py                   # loader pairs, ekspansi varian → item
│   ├── tools/
│   │   ├── registry.py
│   │   └── mock_executors.py     # executor deterministik + validator nilai
│   ├── normalizers/              # implementasi referensi (dipakai S4 & scoring)
│   │   ├── waktu.py
│   │   ├── nominal.py
│   │   ├── wilayah.py
│   │   └── satuan.py
│   ├── runners/
│   │   ├── base.py
│   │   ├── llamacpp_runner.py    # llama-server (OpenAI-compatible)
│   │   └── ollama_runner.py      # Ollama API
│   ├── strategies/
│   │   ├── s1_native.py
│   │   ├── s2_grammar.py
│   │   ├── s3_two_stage.py
│   │   └── s4_normalizer_tool.py
│   ├── eval/
│   │   ├── parse.py              # ekstrak tool call dari output mentah
│   │   ├── canonicalize.py       # samakan format nilai sebelum dibandingkan
│   │   ├── metrics.py
│   │   ├── taxonomy.py           # klasifikasi error
│   │   └── stats.py              # paired bootstrap, McNemar, Holm
│   └── utils/
│       ├── gguf_meta.py          # baca general.file_type dari GGUF
│       ├── hashing.py
│       └── sysinfo.py            # GPU, driver, versi runtime
│
├── scripts/
│   ├── 00_download_models.py
│   ├── 01_verify_quant.py        # GERBANG: gagal kalau kuantisasi tidak seragam
│   ├── 02_validate_data.py
│   ├── 03_build_grammar.py
│   ├── 04_smoke_test.py
│   ├── 05_run_matrix.py
│   ├── 06_score.py
│   └── 07_report.py
│
├── results/
│   ├── raw/                      # JSONL per run (format §13)
│   ├── scored/
│   ├── tables/
│   └── figures/
│
├── logs/
│   ├── manifest_<run_id>.json    # sha256 model, versi runtime, sysinfo
│   └── runtime/
│
├── docs/
│   ├── annotation_guide.md       # aturan menulis 3 varian + gold
│   ├── data_card.md
│   └── laporan/                  # draf laporan / naskah
│
└── tests/
    ├── test_normalizers.py
    ├── test_canonicalize.py
    └── test_metrics.py
```

---

## 3. Dependency & Requirements

### 3.1 Perangkat lunak sistem

| Komponen | Versi | Catatan |
|---|---|---|
| OS | Ubuntu 22.04/24.04 atau WSL2 | Windows native bisa, tapi path script disesuaikan |
| Python | 3.11.x | satu virtualenv untuk seluruh proyek |
| llama.cpp | **build terbaru, lalu dikunci** (catat nomor build `bXXXX` + commit) | runtime utama; `llama-server`, `llama-quantize`, `llama-imatrix` |
| Ollama | versi terbaru, lalu dikunci (`ollama --version`) | hanya untuk Eksperimen C |
| CUDA / ROCm / Metal | sesuai GPU | catat versi driver di manifest |
| Git + Git LFS | terbaru | opsional, untuk versioning data |

> **Kunci versi.** Setelah smoke test lulus, **jangan update** llama.cpp/Ollama sampai semua run selesai. Perubahan chat template atau parser antarversi bisa mengubah hasil tool calling.

### 3.2 `requirements.txt`

```txt
# --- klien runtime ---
openai>=1.40            # klien OpenAI-compatible untuk llama-server & Ollama /v1
ollama>=0.4             # klien native Ollama (Eksperimen C)
httpx>=0.27
tenacity>=8.2           # retry request

# --- model & GGUF ---
huggingface_hub>=0.24   # download GGUF
gguf>=0.10              # baca metadata GGUF (verifikasi kuantisasi)

# --- data & validasi ---
pydantic>=2.7
jsonschema>=4.22
pyyaml>=6.0
orjson>=3.10

# --- normalisasi (bantu anotator, BUKAN pengganti gold manual) ---
dateparser>=1.2         # mendukung bahasa Indonesia ("besok", "lusa")
rapidfuzz>=3.9          # fuzzy match alias wilayah / judul

# --- analisis ---
numpy>=1.26
pandas>=2.2
scipy>=1.13
statsmodels>=0.14       # McNemar, koreksi Holm
matplotlib>=3.9

# --- utilitas ---
tqdm>=4.66
rich>=13.7
psutil>=5.9
nvidia-ml-py>=12.535    # ukur VRAM (NVIDIA); hapus jika non-NVIDIA
python-dotenv>=1.0
```

### 3.3 `requirements-dev.txt`

```txt
pytest>=8.2
ruff>=0.5
jupyterlab>=4.2
```

### 3.4 Kebutuhan perangkat keras (perkiraan)

| Eksperimen | Minimum | Nyaman |
|---|---|---|
| A (semua model @ Q4_K_M) | GPU 8 GB VRAM atau RAM 16 GB (CPU, lambat) | GPU 12 GB |
| B (sampai BF16 untuk model ±4B) | GPU 12 GB | GPU 16–24 GB |
| C | sama dengan A | sama dengan A |

Ukuran file referensi: Qwen3.5-9B Q4_K_M sekitar 6,2 GB, Llama-3.2-3B Q4_K_M sekitar 2,0 GB, Apertus-SEA-LION-v4-8B Q4_K_M sekitar 5,1 GB. Cek ukuran pasti di halaman repo.

---

## 4. Panel Model & Link (semua Q4_K_M)

Prinsipnya: **satu quantizer untuk semua model bila memungkinkan** (bartowski, imatrix, pola nama file konsisten). SEA-LION dipakai dari repo resmi AI Singapore karena belum tentu tersedia di bartowski.

| ID | Model | Peran | Repo GGUF | Tag Q4_K_M |
|---|---|---|---|---|
| **M1** | Qwen3.5-4B | Keluarga A, kecil | https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF | `bartowski/Qwen_Qwen3.5-4B-GGUF:Q4_K_M` |
| **M2** | Qwen3.5-9B | Keluarga A, sedang | https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF | `bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M` |
| **M3** | Gemma 4 E4B-it | Keluarga B | https://huggingface.co/bartowski/google_gemma-4-E4B-it-GGUF | `bartowski/google_gemma-4-E4B-it-GGUF:Q4_K_M` |
| **M4** | Llama 3.2 3B Instruct | Keluarga C (baseline lama) | https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF | `bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M` |
| **M5** | Apertus-SEA-LION-v4-8B-IT | Regional (kuat bahasa Indonesia) | https://huggingface.co/collections/aisingapore/sea-lion-v4 → `aisingapore/Apertus-SEA-LION-v4-8B-IT-GGUF` | Ollama: `aisingapore/Apertus-SEA-LION-v4-8B-IT:q4_k_m` |

**Catatan per model:**
- **Qwen3.5 (M1, M2):** arsitekturnya hybrid (Gated DeltaNet + attention) dan aslinya multimodal; GGUF teks saja sudah cukup. Wajib `--jinja`. Matikan mode *thinking* (lihat §11).
- **Gemma 4 (M3):** format tool call native-nya **bukan JSON OpenAI** (`<|tool_call>call:nama{...}<tool_call|>`). Pernah ada bug parser di Ollama v0.20.0 (April 2026), dan GGUF lama bisa membawa template usang. **Wajib lulus smoke test** (§14) sebelum dimasukkan ke matriks. Kalau gagal, ganti dengan model lain lalu catat alasannya di laporan.
- **Llama 3.2 3B (M4):** generasi lama dan sengaja dipakai sebagai pembanding batas bawah.
- **SEA-LION (M5):** quantizer-nya berbeda dari bartowski, jadi ada variabel pengganggu. Lihat "Mode Ketat" di §5 untuk menghilangkannya.

**Cadangan bila salah satu gagal smoke test:** Qwen3.5-2B (bartowski/unsloth) atau Gemma-SEA-LION-v4-4B-VL (`aisingapore/Gemma-SEA-LION-v4-4B-VL:q4_k_m`).

### 4.1 `configs/models.yaml`

```yaml
# Sumber kebenaran panel model. Quant TIDAK ditulis per model,
# tetapi diambil dari experiment_*.yaml -> semua model otomatis sama.
quantizer_policy: same_quantizer_preferred   # atau: strict_self_quantize
models:
  - id: M1
    name: Qwen3.5-4B
    family: qwen
    params_b: 4
    hf_repo: bartowski/Qwen_Qwen3.5-4B-GGUF
    file_pattern: "*{QUANT}.gguf"
    chat_template: embedded      # pakai template di GGUF, jalankan dengan --jinja
    thinking_toggle: chat_template_kwargs.enable_thinking=false
  - id: M2
    name: Qwen3.5-9B
    family: qwen
    params_b: 9
    hf_repo: bartowski/Qwen_Qwen3.5-9B-GGUF
    file_pattern: "*{QUANT}.gguf"
    chat_template: embedded
    thinking_toggle: chat_template_kwargs.enable_thinking=false
  - id: M3
    name: Gemma-4-E4B-it
    family: gemma
    params_b: 4
    hf_repo: bartowski/google_gemma-4-E4B-it-GGUF
    file_pattern: "*{QUANT}.gguf"
    chat_template: embedded
    requires_smoke_pass: true
  - id: M4
    name: Llama-3.2-3B-Instruct
    family: llama
    params_b: 3
    hf_repo: bartowski/Llama-3.2-3B-Instruct-GGUF
    file_pattern: "*{QUANT}.gguf"
    chat_template: embedded
  - id: M5
    name: Apertus-SEA-LION-v4-8B-IT
    family: sealion
    params_b: 8
    hf_repo: aisingapore/Apertus-SEA-LION-v4-8B-IT-GGUF
    file_pattern: "*{QUANT}*.gguf"
    chat_template: embedded
    note: "quantizer berbeda; lihat strict_self_quantize"
```

---

## 5. Aturan Kuantisasi Seragam

### 5.1 Aturan

1. **Satu eksperimen = satu tipe kuantisasi untuk semua model.** Eksperimen A dan C memakai `Q4_K_M` untuk M1–M5 tanpa pengecualian.
2. Eksperimen B memakai **tangga kuantisasi yang sama** untuk semua model yang diuji: `BF16 → Q8_0 → Q6_K → Q4_K_M → Q3_K_M`.
3. Tipe `Q4_K_M` **tidak boleh diganti** dengan `Q4_K_L`, `Q4_K_S`, `IQ4_XS`, `UD-Q4_K_XL`, `Q4_0`, atau varian lain, walaupun ukurannya mirip. Namanya mirip, tapi resepnya berbeda.
4. Kalau satu model **tidak punya** tipe yang diminta, buat sendiri dari BF16 (lihat 5.3) atau keluarkan model tersebut dari eksperimen. Jangan memakai tipe lain.
5. Kebenaran ditentukan oleh **metadata GGUF** (`general.file_type`), bukan oleh nama file.

### 5.2 Gerbang verifikasi: `scripts/01_verify_quant.py`

```python
"""Gagal (exit 1) bila file GGUF dalam satu eksperimen tidak seragam."""
import sys, hashlib, json, pathlib, yaml
from gguf import GGUFReader

# Enum llama_ftype (llama.cpp). Verifikasi ulang dengan versi llama.cpp yang dipakai.
FTYPE = {1: "F16", 7: "Q8_0", 12: "Q3_K_M", 15: "Q4_K_M", 18: "Q6_K", 32: "BF16"}

def file_type(path):
    r = GGUFReader(str(path))
    f = r.fields["general.file_type"]
    return FTYPE.get(int(f.parts[f.data[0]][0]), f"UNKNOWN({int(f.parts[f.data[0]][0])})")

def sha256(path, buf=1 << 24):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(buf):
            h.update(chunk)
    return h.hexdigest()

def main(exp_cfg):
    cfg = yaml.safe_load(open(exp_cfg))
    expected = cfg["quant"]                       # contoh: "Q4_K_M"
    rows, bad = [], []
    for m in cfg["models"]:
        p = pathlib.Path(cfg["model_dir"]) / expected / f"{m}.gguf"
        ft = file_type(p)
        rows.append({"model": m, "file": str(p), "file_type": ft, "sha256": sha256(p)})
        if ft != expected:
            bad.append((m, ft))
    json.dump(rows, open(f"logs/quant_manifest_{cfg['name']}.json", "w"), indent=2)
    if bad:
        print(f"[GAGAL] kuantisasi tidak seragam, harus {expected}: {bad}")
        sys.exit(1)
    print(f"[OK] semua {len(rows)} model = {expected}")

if __name__ == "__main__":
    main(sys.argv[1])
```

`05_run_matrix.py` **wajib** memanggil gerbang ini dulu dan menolak berjalan kalau gerbang gagal.

### 5.3 Mode Ketat (opsional, paling rapi untuk publikasi)

Kuantisasi **semua** model sendiri dari BF16 dengan **build llama.cpp yang sama** dan **data kalibrasi imatrix yang sama**, berisi campuran teks Indonesia dan Inggris. Ini menghilangkan perbedaan quantizer antara bartowski dan AI Singapore. Bahasa kalibrasi juga terbukti berpengaruh pada model multibahasa.

```bash
# 1) imatrix dari teks kalibrasi campuran ID+EN (mis. 200k token, simpan di data/calib/)
llama-imatrix -m models/BF16/M1.gguf -f data/calib/calib_id_en.txt -o models/imatrix/M1.dat

# 2) kuantisasi ke semua tingkat dengan imatrix yang sama
for Q in Q8_0 Q6_K Q4_K_M Q3_K_M; do
  llama-quantize --imatrix models/imatrix/M1.dat models/BF16/M1.gguf models/$Q/M1.gguf $Q
done
```

Laporkan di bagian metode: *"Semua model dikuantisasi dengan llama.cpp build bXXXX, imatrix dari 200k token teks ID+EN yang sama."*

---

## 6. Definisi Tool (10 tool)

Semua tool adalah **mock deterministik**: tidak memanggil API sungguhan, hanya memvalidasi lalu mengembalikan respons tetap. Nama tool dan nama parameter memakai bahasa Indonesia yang konsisten, sedangkan nilainya wajib dalam format kanonik.

| # | Tool | Parameter wajib (format kanonik) | Kategori nilai yang diuji |
|---|---|---|---|
| 1 | `buat_pengingat` | `judul:str`, `waktu:ISO-8601+07:00` | waktu relatif, jam informal |
| 2 | `transfer_ewallet` | `penerima:str`, `nominal:int (rupiah)`, `platform:enum[gopay,ovo,dana,shopeepay]` | nominal slang, enum |
| 3 | `cek_ongkir` | `asal:kode_wilayah`, `tujuan:kode_wilayah`, `berat_gram:int`, `kurir:enum[jne,jnt,sicepat,pos]` | singkatan wilayah, satuan |
| 4 | `jadwal_krl` | `stasiun_asal:enum`, `stasiun_tujuan:enum`, `waktu:ISO-8601` | singkatan stasiun, waktu |
| 5 | `cek_cuaca` | `wilayah:kode_wilayah`, `tanggal:YYYY-MM-DD` | lokasi, tanggal relatif |
| 6 | `pesan_ojek` | `jemput:str`, `tujuan:str`, `layanan:enum[motor,mobil]` | enum informal ("ojol", "grabcar") |
| 7 | `konversi_kurs` | `jumlah:float`, `dari:ISO-4217`, `ke:ISO-4217` | angka kata, kode mata uang |
| 8 | `bayar_tagihan` | `jenis:enum[pln,pdam,bpjs,pulsa]`, `id_pelanggan:str`, `nominal:int` | enum, nominal |
| 9 | `buat_jadwal_rapat` | `judul:str`, `mulai:ISO-8601`, `durasi_menit:int`, `peserta:list[str]` | durasi ("sejam setengah"), waktu |
| 10 | `cari_dokumen` | `query:str`, `top_k:int` | (dipakai bila ingin ekstensi RAG) |

**Tool normalisasi khusus S4** (`data/tools/normalizer_tools.json`):
- `parse_waktu(teks, waktu_acuan)` → ISO-8601
- `parse_nominal(teks)` → int rupiah
- `cari_wilayah(teks)` → kode wilayah + nama resmi
- `parse_satuan(teks, target)` → angka dalam satuan target

Contoh skema (`tools_v1.json`, potongan):

```json
{
  "type": "function",
  "function": {
    "name": "transfer_ewallet",
    "description": "Mengirim uang lewat dompet digital.",
    "parameters": {
      "type": "object",
      "properties": {
        "penerima": {"type": "string", "description": "Nama atau nomor penerima"},
        "nominal":  {"type": "integer", "minimum": 1000, "description": "Jumlah dalam rupiah, bilangan bulat tanpa titik"},
        "platform": {"type": "string", "enum": ["gopay", "ovo", "dana", "shopeepay"]}
      },
      "required": ["penerima", "nominal", "platform"]
    }
  }
}
```

---

## 7. Data Pair Prompt (formal / informal / campur)

### 7.1 Prinsip desain

- **Satu `pair_id` = satu intent = satu gold call**, ditulis dalam **3 varian register**:
  - `formal`: bahasa baku ("pukul 19.00", "Rp50.000").
  - `informal`: bahasa sehari-hari/gaul ("jam 7an malem", "gocap", "Jaksel").
  - `campur`: campur Indonesia–Inggris ("set reminder meeting besok jam 7 malem").
- Ketiga varian harus **setara secara informasi**: varian informal tidak boleh membuang atau menambah informasi.
- `reference_time` dikunci per item supaya "besok" selalu punya jawaban tunggal.
- Setiap item ditulis oleh anotator A1 dan **diverifikasi** anotator A2. Catat kesepakatan antar-anotator.

### 7.2 Target jumlah

| Komponen | Jumlah |
|---|---|
| Pair *call* (3 varian masing-masing) | 200 pair → 600 item |
| Pair *no-call* (tidak ada tool yang cocok → harus menolak) | 20 pair → 60 item |
| **Total** | **220 pair / 660 item** |
| Split | dev 44 pair (20%), test 176 pair (80%) |

Sebaran: setiap tool minimal 15 pair, dan setiap kategori nilai (§8) minimal 20 kemunculan.

### 7.3 Format `data/pairs/indoarg_v1.jsonl`

Satu baris = satu pair.

```json
{
  "pair_id": "P0001",
  "split": "test",
  "tool_target": "buat_pengingat",
  "reference_time": "2026-11-23T18:00:00+07:00",
  "variants": {
    "formal":   "Tolong buatkan pengingat rapat besok pukul 19.00.",
    "informal": "ingetin aku rapat besok jam 7an malem ya",
    "campur":   "set reminder meeting besok jam 7 malem dong"
  },
  "gold_call": {
    "name": "buat_pengingat",
    "arguments": {"judul": "rapat", "waktu": "2026-11-24T19:00:00+07:00"}
  },
  "strict_keys": ["waktu"],
  "soft_keys": {"judul": {"method": "fuzzy", "threshold": 80, "aliases": ["meeting"]}},
  "value_categories": ["waktu_relatif", "jam_informal", "code_mix"],
  "difficulty": "sedang",
  "annotator": "A1",
  "verified_by": "A2",
  "notes": "'jam 7an' diterima sebagai 19:00 karena ada 'malem'"
}
```

Contoh lain:

```json
{"pair_id":"P0042","split":"test","tool_target":"transfer_ewallet","reference_time":"2026-11-23T18:00:00+07:00",
 "variants":{"formal":"Kirimkan Rp50.000 ke Rina melalui GoPay.",
             "informal":"tf gocap ke rina pake gopay",
             "campur":"transfer 50k ke Rina via gopay ya"},
 "gold_call":{"name":"transfer_ewallet","arguments":{"penerima":"Rina","nominal":50000,"platform":"gopay"}},
 "strict_keys":["nominal","platform"],"soft_keys":{"penerima":{"method":"casefold"}},
 "value_categories":["nominal_slang","enum_merek"],"difficulty":"sulit","annotator":"A1","verified_by":"A2"}
```

```json
{"pair_id":"P0107","split":"test","tool_target":"cek_ongkir","reference_time":"2026-11-23T18:00:00+07:00",
 "variants":{"formal":"Berapa ongkos kirim paket 2 kilogram dari Surabaya ke Jakarta Selatan dengan JNE?",
             "informal":"ongkir 2 kilo dr sby ke jaksel pake jne brp",
             "campur":"cek shipping cost 2 kg Surabaya ke Jaksel, kurir JNE"},
 "gold_call":{"name":"cek_ongkir","arguments":{"asal":"35.78","tujuan":"31.74","berat_gram":2000,"kurir":"jne"}},
 "strict_keys":["asal","tujuan","berat_gram","kurir"],"soft_keys":{},
 "value_categories":["lokasi_singkatan","satuan"],"difficulty":"sedang","annotator":"A2","verified_by":"A1"}
```

Contoh *no-call*:

```json
{"pair_id":"N0003","split":"test","tool_target":null,"reference_time":"2026-11-23T18:00:00+07:00",
 "variants":{"formal":"Apa ibu kota Provinsi Jawa Timur?",
             "informal":"ibukota jatim apaan sih",
             "campur":"capital city Jatim apa ya"},
 "gold_call":null,"value_categories":["no_call"],"difficulty":"mudah","annotator":"A1","verified_by":"A2"}
```

> Kode wilayah di contoh hanya ilustrasi format. Isi `wilayah.csv` dari sumber resmi (Kemendagri/BPS) dan periksa ulang setiap kode.

### 7.4 Skema validasi (`indoarg_v1.schema.json`, inti)

```json
{
  "type": "object",
  "required": ["pair_id","split","tool_target","reference_time","variants","gold_call","value_categories","annotator","verified_by"],
  "properties": {
    "pair_id": {"type":"string","pattern":"^[PN][0-9]{4}$"},
    "split": {"enum":["dev","test"]},
    "variants": {"type":"object","required":["formal","informal","campur"],
                 "additionalProperties": false,
                 "properties":{"formal":{"type":"string","minLength":5},
                               "informal":{"type":"string","minLength":3},
                               "campur":{"type":"string","minLength":3}}},
    "value_categories": {"type":"array","minItems":1}
  }
}
```

`scripts/02_validate_data.py` juga memeriksa empat hal:
1. `gold_call` lolos JSON schema tool-nya.
2. Tidak ada varian yang identik.
3. Semua `pair_id` unik dan dev/test tidak tumpang-tindih.
4. Sebaran tool dan kategori memenuhi target di §7.2.

### 7.5 Panduan anotasi (ringkas, lengkapnya di `docs/annotation_guide.md`)

1. Tulis varian **formal** dulu, lalu tentukan gold call.
2. Buat varian **informal** dengan minimal satu fenomena dari §8.
3. Buat varian **campur** dengan minimal satu kata/frasa Inggris yang wajar dipakai sehari-hari.
4. Hindari ambiguitas yang tidak bisa diselesaikan. Kalau "jam 7" bisa pagi atau malam, tambahkan petunjuk ("malem") atau tulis aturannya di `notes`.
5. Jangan memakai nama orang sungguhan atau nomor rekening/telepon asli. Pakai nama dan ID fiktif.

---

## 8. Taksonomi Kategori Nilai

| Kode | Fenomena | Contoh informal → nilai kanonik |
|---|---|---|
| `waktu_relatif` | hari relatif | besok, lusa, minggu depan, Senin depan → tanggal ISO |
| `jam_informal` | jam tidak baku | jam 7an malem, setengah 8, jam 3 sore → `19:00`, `07:30`/`19:30`, `15:00` |
| `tanggal_format` | format tanggal campur | 24/11, 24 Nov, tgl 24 → `2026-11-24` |
| `nominal_singkat` | singkatan uang | 50rb, 50k, 1,5jt, sejuta → `50000`, `1500000`, `1000000` |
| `nominal_slang` | slang angka Betawi | gocap, cepek, gopek, seceng, goceng, ceban → sesuai konteks |
| `angka_kata` | angka ditulis kata | dua ratus ribu, sejam setengah → `200000`, `90` menit |
| `lokasi_singkatan` | singkatan wilayah | Jaksel, Sby, Jogja, Bdg → kode wilayah |
| `satuan` | konversi satuan | 2 kilo, setengah kilo → `2000`, `500` gram |
| `enum_merek` | variasi penulisan enum | GoPay/gopay/"gopey", ojol → `gopay`, `motor` |
| `code_mix` | campur Inggris | reminder, meeting, transfer, shipping cost |
| `no_call` | tidak perlu tool | harus menolak memanggil tool |

**Taksonomi error** (`eval/taxonomy.py`), dihitung per item:

| Kode error | Arti |
|---|---|
| `E_PARSE` | output tidak bisa di-parse sebagai tool call |
| `E_SCHEMA` | bisa di-parse tapi melanggar JSON schema |
| `E_TOOL` | salah memilih tool |
| `E_MISSING` | argumen wajib hilang |
| `E_VALUE_FORMAT` | nilai benar maknanya, salah formatnya (mis. `"50rb"` bukan `50000`) |
| `E_VALUE_LANG` | nilai ditulis dalam bahasa/ejaan pengguna, bukan bentuk kanonik ("Jaksel" bukan kode) |
| `E_VALUE_WRONG` | nilai salah makna (mis. jam 7 pagi padahal malam) |
| `E_HALLUC_ARG` | menambah argumen yang tidak diminta |
| `E_OVERCALL` | memanggil tool pada item `no_call` |
| `E_UNDERCALL` | tidak memanggil tool padahal seharusnya |

---

## 9. Strategi S1–S4

| Kode | Strategi | Cara kerja | Mewakili |
|---|---|---|---|
| **S1** | Native tools | Tools dikirim lewat parameter `tools` API; model bebas | cara default Ollama/llama.cpp |
| **S2** | Grammar ketat | Tools ditulis di system prompt; output dipaksa JSON schema `{"name": enum, "arguments": ...}` lewat `response_format`/GBNF | *constrained decoding* |
| **S3** | Dua tahap | Tahap 1 bebas: "tuliskan nilai-nilai ternormalisasi". Tahap 2 dikunci grammar, dengan output tahap 1 ada di konteks | ruang berpikir dulu, format dikunci kemudian |
| **S4** | Tool normalisasi | Model boleh memanggil `parse_waktu`/`parse_nominal`/`cari_wilayah`/`parse_satuan` dulu (maks. 4 langkah), lalu tool target | normalisasi di luar model |

Aturan keadilan:
- System prompt dasar (`configs/prompts/system_id.txt`) **identik** untuk semua model dan semua strategi. Yang berubah hanya bagian khusus strategi.
- Tidak ada contoh few-shot di main run. Kalau ingin menguji few-shot, jadikan ablation terpisah.
- Prompt hanya boleh diubah memakai split **dev**. Split **test** disentuh sekali di run final.

---

## 10. Matriks Eksperimen A / B / C

### Eksperimen A: Utama (RQ1–RQ3)

```yaml
# configs/experiment_A.yaml
name: A_main
quant: Q4_K_M                 # SATU nilai untuk semua model
model_dir: models
models: [M1, M2, M3, M4, M5]
strategies: [S1, S2, S3, S4]
runtime: llamacpp_server
split: test
registers: [formal, informal, campur]
decoding: greedy              # lihat inference.yaml
robustness_seeds: [11, 22, 33] # hanya untuk sub-run T=0.7 (opsional)
```

Jumlah generasi greedy: 5 model × 4 strategi × 528 item test ≈ **10.560**, belum termasuk langkah tambahan S3/S4.

### Eksperimen B: Kuantisasi × Register (RQ4)

```yaml
name: B_quant_register
quant_ladder: [BF16, Q8_0, Q6_K, Q4_K_M, Q3_K_M]  # tangga SAMA untuk semua model
models: [M1, M3]              # satu kecil Qwen, satu Gemma (beda keluarga)
strategies: [S1, BEST_FROM_A] # S1 + strategi terbaik dari Eksp. A
runtime: llamacpp_server
split: test
```

Gerbang §5 dijalankan **per tingkat**. Semua model di tingkat `Q6_K`, misalnya, harus benar-benar `Q6_K`.

### Eksperimen C: Runtime variance (RQ5)

```yaml
name: C_runtime
quant: Q4_K_M
models: [M1, M5]              # Qwen + SEA-LION (template berbeda)
strategies: [S1]
runtimes:
  - ollama_native             # file GGUF yang SAMA, dibuat lewat Modelfile FROM ./models/Q4_K_M/M1.gguf
  - llamacpp_jinja            # llama-server --jinja (parser tool bawaan)
  - llamacpp_grammar          # llama-server + S2 grammar
split: test
```

Untuk Ollama, buat model dari **file lokal yang sama** (bukan `ollama pull` versi lain) supaya bobotnya identik. sha256 di manifest harus sama.

```
# models/modelfiles/M1.Modelfile
FROM ../Q4_K_M/M1.gguf
PARAMETER temperature 0
PARAMETER num_ctx 8192
```

---

## 11. Parameter Inferensi (dikunci)

```yaml
# configs/inference.yaml
main:
  temperature: 0.0
  top_p: 1.0
  top_k: 0            # nonaktif
  min_p: 0.0
  repeat_penalty: 1.0
  max_tokens: 512
  n_ctx: 8192
  stop: []            # pakai stop token dari template model
  thinking: off       # Qwen3.5: chat_template_kwargs.enable_thinking=false
                      # model lain: matikan sesuai template; jika tidak bisa, CATAT
robustness:           # opsional, sub-sampel 100 pair
  temperature: 0.7
  top_p: 0.95
  seeds: [11, 22, 33]
server:
  llamacpp: "--jinja -ngl 99 -c 8192 -fa on --parallel 1"
  batch_concurrency: 1   # 1 agar latensi terukur bersih
```

Catatan:
- Dengan `temperature 0`, satu run sudah cukup. Ketidakpastian dihitung dengan **bootstrap per item** (§12). Seed hanya relevan untuk run robustness.
- Kalau satu model tidak bisa mematikan *thinking*, jalankan dengan `max_tokens` lebih besar dan beri tanda `thinking_forced=true` di log. Bahas perbedaan ini di laporan.

---

## 12. Metrik & Statistik

### 12.1 Metrik per run

| Metrik | Definisi |
|---|---|
| **CVR**: Call Validity Rate | % output yang bisa di-parse **dan** lolos JSON schema |
| **TSA**: Tool Selection Accuracy | % item dengan nama tool benar |
| **EXA**: Executable Accuracy (**metrik utama**) | % item dengan tool benar **dan** semua `strict_keys` sama dengan gold setelah kanonisasi **dan** `soft_keys` lolos ambang |
| **WVS**: Wrong-Valid-Schema rate | % item yang lolos schema tapi EXA salah, dibagi item yang lolos schema |
| **VA[k]**: Value Accuracy per kategori | akurasi nilai untuk kategori k (§8) |
| **ABS**: Abstention Accuracy | % item `no_call` yang benar-benar tidak memanggil tool |
| **ΔReg**: Register Gap | `EXA_formal − EXA_informal` dan `EXA_formal − EXA_campur` (berpasangan per `pair_id`) |
| **Efisiensi** | latensi p50/p95, token/detik (prefill & decode), VRAM puncak, jumlah langkah (S3/S4) |

Untuk S4, nilai yang dibandingkan adalah argumen pada **panggilan tool target terakhir**. Panggilan tool normalisasi hanya dicatat jumlahnya.

### 12.2 Statistik

- **CI 95%:** *paired bootstrap* 10.000 resample di level `pair_id`, supaya tiga varian satu pair ikut ter-resample bersama.
- **Uji beda strategi/register:** McNemar (biner berpasangan) per model, dengan koreksi **Holm** untuk banyak perbandingan.
- **Eksp. B:** plot EXA vs bit per register, lalu uji interaksi register × kuantisasi dengan regresi logistik `EXA ~ register * quant + (1|pair_id)` (mixed effect) atau GEE di `statsmodels`.
- **Baseline floor check:** kalau EXA BF16 suatu model di bawah 20%, jangan tafsirkan penurunan kuantisasinya, karena model itu memang tidak mampu sejak awal.

### 12.3 Tabel & gambar wajib di laporan

1. Tabel utama: model × strategi → EXA (CI), CVR, WVS, ABS.
2. Heatmap: model × kategori nilai → VA.
3. Bar berpasangan: EXA formal/informal/campur per model (ΔReg).
4. Kurva Eksp. B: EXA vs tingkat kuantisasi, satu garis per register.
5. Tabel Eksp. C: runtime × model → EXA, CVR, latensi.
6. Distribusi error (§8) per strategi.

---

## 13. Format Log Hasil

`results/raw/<run_id>.jsonl`, satu baris per item per run:

```json
{
  "run_id": "A_main__M1__S2__Q4_K_M__20261125T1010",
  "experiment": "A_main",
  "model_id": "M1",
  "gguf_sha256": "…",
  "quant": "Q4_K_M",
  "runtime": "llamacpp_server",
  "runtime_version": "bXXXX",
  "strategy": "S2",
  "pair_id": "P0042",
  "register": "informal",
  "prompt_hash": "…",
  "request": {"messages": "…", "tools": "…", "params": "…"},
  "raw_output": "…",
  "steps": [{"tool": "parse_nominal", "args": {"teks": "gocap"}, "result": 50000}],
  "parsed_call": {"name": "transfer_ewallet", "arguments": {"penerima": "rina", "nominal": 50000, "platform": "gopay"}},
  "latency_ms": 812,
  "prompt_tokens": 734,
  "completion_tokens": 41,
  "tokens_per_s_decode": 38.2,
  "vram_peak_mb": 4210,
  "thinking_forced": false,
  "error": null,
  "timestamp": "2026-11-25T10:10:42+07:00"
}
```

`results/scored/` menambahkan kolom `cvr, tsa, exa, wvs, error_codes[], value_correct{}`.

`logs/manifest_<run_id>.json` berisi sha256 semua GGUF, versi llama.cpp/Ollama, GPU, versi driver, hash `inference.yaml` dan file prompt, serta commit git workspace.

---

## 14. Pipeline & Perintah

```bash
# 0) setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 1) download model (quant diambil dari config eksperimen, bukan diketik manual)
python scripts/00_download_models.py --exp configs/experiment_A.yaml
#   contoh manual setara:
#   hf download bartowski/Qwen_Qwen3.5-4B-GGUF --include "*Q4_K_M.gguf" --local-dir models/Q4_K_M/
#   lalu rename menjadi models/Q4_K_M/M1.gguf

# 2) GERBANG kuantisasi seragam
python scripts/01_verify_quant.py configs/experiment_A.yaml

# 3) validasi data
python scripts/02_validate_data.py data/pairs/indoarg_v1.jsonl

# 4) grammar untuk S2/S3
python scripts/03_build_grammar.py data/tools/tools_v1.json grammars/tools_v1.gbnf

# 5) jalankan server (satu model per waktu)
llama-server -m models/Q4_K_M/M1.gguf --jinja -ngl 99 -c 8192 -fa on --port 8080

# 6) smoke test (14 kasus; model yang gagal parse >2/14 ditandai dan diperiksa)
python scripts/04_smoke_test.py --model M1 --endpoint http://localhost:8080/v1

# 7) matriks penuh (memanggil ulang 01_verify_quant otomatis)
python scripts/05_run_matrix.py --exp configs/experiment_A.yaml

# 8) scoring + statistik + laporan
python scripts/06_score.py --exp A_main
python scripts/07_report.py --exp A_main --out results/tables/ results/figures/
```

`Makefile` cukup membungkus langkah 2–8: `make verify`, `make smoke`, `make run EXP=A`, `make report EXP=A`.

---

## 15. Reproducibility Checklist

- [ ] Build llama.cpp dan versi Ollama dicatat lalu tidak diubah selama run.
- [ ] Gerbang `01_verify_quant.py` lulus untuk setiap eksperimen/tingkat.
- [ ] sha256 setiap GGUF tercatat di manifest (dan sama antara llama.cpp dan Ollama di Eksp. C).
- [ ] Mode *thinking* dimatikan atau dicatat per model.
- [ ] System prompt identik untuk semua model; hash prompt dicatat.
- [ ] Split test hanya dipakai di run final.
- [ ] Gold diverifikasi 2 anotator; kesepakatan antar-anotator dilaporkan.
- [ ] CI bootstrap level `pair_id`; koreksi Holm.
- [ ] Data, kode, dan konfigurasi dirilis (dataset + `data_card.md`).
- [ ] Tidak ada data pribadi asli di dataset.

---

## 16. Timeline (±3 minggu)

| Minggu | Kegiatan | Output |
|---|---|---|
| 1 (hari 1–2) | Setup workspace, download model, gerbang kuantisasi, smoke test | panel model final |
| 1 (hari 3–7) | Tool schema, gazetteer, tulis 220 pair + verifikasi | `indoarg_v1.jsonl` |
| 2 (hari 8–9) | Implementasi S1–S4, scoring, unit test normalizer | pipeline lengkap |
| 2 (hari 10–11) | Tuning prompt di split dev, kunci konfigurasi | `inference.yaml` final |
| 2 (hari 12–14) | Eksperimen A | tabel utama |
| 3 (hari 15–17) | Eksperimen B dan C | kurva kuantisasi, tabel runtime |
| 3 (hari 18–21) | Analisis error, statistik, penulisan laporan | laporan/naskah |

---

## 17. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Template/parser tool Gemma 4 bermasalah di runtime | EXA anjlok karena parser, bukan karena model | smoke test wajib; pakai llama.cpp terbaru `--jinja`; ganti model cadangan bila gagal |
| Repo salah satu model tidak punya tipe kuantisasi yang sama | melanggar aturan seragam | Mode Ketat §5.3 (kuantisasi sendiri) atau keluarkan model |
| Quantizer berbeda (bartowski vs AI Singapore) | variabel pengganggu | Mode Ketat, atau sebutkan sebagai keterbatasan |
| Nilai ambigu ("jam 7") | gold tidak adil | aturan anotasi §7.5 + kolom `notes` |
| Data terlalu mudah ditebak model | efek tidak terlihat | pastikan ≥30% pair berlabel `sulit` |
| Kebocoran tuning ke test | hasil terlalu optimis | tuning hanya di dev; test sekali |
| VRAM tidak cukup untuk BF16 di Eksp. B | tangga tidak lengkap | pakai model kecil (M1, M3) untuk Eksp. B atau jalankan BF16 di CPU |
| Thinking tidak bisa dimatikan di satu model | perbandingan tidak setara | catat `thinking_forced`, laporkan terpisah |

---

## 18. Referensi

Penelitian terdekat (posisikan kebaruan terhadap ini):

- **MLCL**: *Lost in Execution: On the Multilingual Robustness of Tool Calling in LLMs* (ACL 2026): https://aclanthology.org/2026.acl-long.2039/
- **Constraint Tax**: *Measuring Validity–Correctness Tradeoffs in Structured Outputs for SLMs*: https://arxiv.org/abs/2605.26128
- *Same Quantization, Different Failures: Multi-Turn Tool-Calling in SLMs* (NeurIPS 2026): https://neurips.cc/virtual/2026/171271
- **PolAgentBench**: *Quantization Thresholds Replicate, Failure Modes Do Not* (Polandia): https://arxiv.org/pdf/2609.32042
- **MASSIVE-Agents**: *Multilingual Function-Calling in 52 Languages* (Findings EMNLP 2025): https://aclanthology.org/2025.findings-emnlp.1099/
- *How Does Quantization Affect Multilingual LLMs?*: https://arxiv.org/abs/2407.03211
- *Calibrating Beyond English: Language Diversity for Better Quantized Multilingual LLMs*: https://arxiv.org/abs/2601.18306
- *Repair, Not Improvement: Decomposing Constrained Decoding in Tool-Call Abstention*: https://arxiv.org/pdf/2608.13959

Model & tools:

- Qwen3.5-4B GGUF: https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF
- Qwen3.5-9B GGUF: https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF
- Gemma 4 E4B-it GGUF: https://huggingface.co/bartowski/google_gemma-4-E4B-it-GGUF
- Gemma 4 function calling (dokumentasi resmi): https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4
- Llama 3.2 3B Instruct GGUF: https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF
- SEA-LION v4 collection: https://huggingface.co/collections/aisingapore/sea-lion-v4
- Apertus-SEA-LION-v4-8B-IT (Ollama): https://ollama.com/aisingapore/Apertus-SEA-LION-v4-8B-IT
