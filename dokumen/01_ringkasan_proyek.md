# 01. Ringkasan Proyek IndoArg

## 1.1 Identitas & Ruang Lingkup

- **Nama Proyek:** IndoArg
- **Fokus Riset:** Evaluasi kemampuan model bahasa besar lokal (*Small/Local LLMs*, 3B–9B parameter) pada runtime **llama.cpp** dan **Ollama** dalam menerjemahkan perintah bahasa Indonesia sehari-hari (*formal*, *informal*, dan *campur kode*) menjadi argumen *function/tool calling* yang valid dan **dapat dieksekusi secara deterministik**.
- **Versi Blueprint:** v1.0 (23 November 2026)
- **Prinsip Pengendalian Utama:** **Kuantisasi seragam wajib** dalam satu eksperimen (default `Q4_K_M` untuk Eksperimen A & C; tangga `BF16 → Q8_0 → Q6_K → Q4_K_M → Q3_K_M` untuk Eksperimen B), ditegakkan otomatis lewat metadata GGUF (`general.file_type`) oleh [`scripts/01_verify_quant.py`](../scripts/01_verify_quant.py).

---

## 1.2 Rumusan Masalah

Model lokal berukuran 3B–9B sering kali sudah mampu **memilih nama tool yang benar** (*Tool Selection Accuracy* tinggi), tetapi gagal **mengisi nilai argumen dalam format kanonik yang siap dieksekusi** ketika pengguna memakai gaya bahasa Indonesia sehari-hari. Contoh nyata:

| Ungkapan Pengguna (Informal / Campur) | Tool Target | Argumen Kanonik yang Harus Dihasilkan |
|---|---|---|
| `"ingetin aku rapat besok jam 7an malem ya"` | `buat_pengingat` | `waktu = "2026-11-24T19:00:00+07:00"` |
| `"tf gocap ke rina pake gopay"` | `transfer_ewallet` | `nominal = 50000`, `platform = "gopay"` |
| `"ongkir 2 kilo dr sby ke jaksel pake jne brp"` | `cek_ongkir` | `asal = "35.78"`, `tujuan = "31.74"`, `berat_gram = 2000`, `kurir = "jne"` |
| `"schedule meeting Review Q4 besok jam 3 sore selama sejam setengah"` | `buat_jadwal_rapat` | `mulai = "2026-11-24T15:00:00+07:00"`, `durasi_menit = 90` |

Kegagalan semacam ini tidak selalu tertangkap oleh validasi JSON schema biasa — sebuah output dapat 100% valid secara skema (`{"nominal": 5000, ...}` atau `{"waktu": "2026-11-24T07:00:00+07:00"}`), namun **keliru secara semantik** sehingga berbahaya bila dieksekusi langsung.

---

## 1.3 Pertanyaan Riset (RQ1–RQ5)

| Kode | Eksperimen | Pertanyaan Riset |
|---|---|---|
| **RQ1** | Eksp. A | Kategori nilai mana yang paling sering gagal dinormalisasi oleh LLM lokal (waktu relatif, jam informal, nominal slang Betawi, singkatan lokasi, satuan, atau enum merek)? |
| **RQ2** | Eksp. A | Seberapa besar ***register gap*** ($\Delta\text{Reg}$), yaitu selisih akurasi eksekusi antara perintah **formal vs informal** dan **formal vs campur kode** pada intent yang isinya identik? |
| **RQ3** | Eksp. A | Strategi mana (**S1–S4**) yang paling efektif menutup *register gap* pada model 3–9B lokal, dan apakah *constrained decoding* berbasis grammar (**S2**) justru memicu fenomena *constraint tax* (skema valid tetapi nilai salah)? |
| **RQ4** | Eksp. B | Apakah perintah **informal / campur kode** mengalami degradasi akurasi lebih cepat daripada perintah **formal** ketika presisi bit kuantisasi diturunkan (`BF16 → Q8_0 → Q6_K → Q4_K_M → Q3_K_M`)? |
| **RQ5** | Eksp. C | Dengan **file GGUF yang identik (SHA-256 sama)**, seberapa besar perbedaan akurasi dan validitas panggilan tool antar-runtime (**Ollama native** vs **llama.cpp `--jinja`** vs **llama.cpp + grammar**)? |

---

## 1.4 Klaim Kebaruan (*Novelty*)

Tiga kontribusi utama yang membedakan IndoArg dari benchmark *multilingual tool calling* yang sudah ada (seperti MASSIVE-Agents, MLCL, dan PolAgentBench):

1. **Desain Berpasangan Lintas Register (*Paired Register Design*):** Satu `pair_id` merepresentasikan tepat satu intent dan satu `gold_call` kanonik yang ditulis dalam 3 register setara informasi (`formal`, `informal`, `campur`). Desain ini memungkinkan uji berpasangan (*paired bootstrap* & *McNemar*) yang menghilangkan variabel pengganggu perbedaan topik.
2. **Normalisasi Nilai Khas Indonesia:** Menguji secara sistematis fenomena sehari-hari bahasa Indonesia yang jarang tercakup pada benchmark global: slang angka Betawi (`gocap`, `ceban`, `noban`, `cepek`, `gopek`), jam informal (`setengah 8`, `jam 7an malem`), singkatan wilayah Kemendagri (`Jaksel`, `Sby`, `Jogja`, `Tangsel`), singkatan stasiun KRL (`Tenabang`, `Pocin`), serta satuan kolokial (`sejam setengah`, `setengah kilo`, `3 ons`).
3. **Interaksi Tiga Arah pada Runtime Lokal:** Mengukur secara simultan interaksi antara **register bahasa × *constraint tax* (S1–S4) × kuantisasi GGUF seragam** serta varians runtime lokal (llama.cpp vs Ollama) memakai bobot GGUF yang benar-benar identik secara kriptografis.

---

## 1.5 Panel Model (M1–M5)

Semua model pada Eksperimen A dan C wajib memakai kuantisasi **`Q4_K_M`**. Quantizer disamakan (`bartowski`, imatrix) sejauh tersedia, dengan opsi **Mode Ketat** (kuantisasi mandiri dari BF16 dengan *imatrix* ID+EN yang sama) untuk menghilangkan perbedaan quantizer pada M5.

| ID | Model | Keluarga | Ukuran | Peran Eksperimen | Sumber GGUF | Catatan Khusus |
|---|---|---|---|---|---|---|
| **M1** | Qwen3.5-4B | Qwen (hybrid DeltaNet + attention) | 4B | Model kecil modern | `bartowski/Qwen_Qwen3.5-4B-GGUF` | Wajib `--jinja`; matikan mode *thinking* (`enable_thinking=false`) |
| **M2** | Qwen3.5-9B | Qwen | 9B | Model menengah modern | `bartowski/Qwen_Qwen3.5-9B-GGUF` | Wajib `--jinja`; matikan *thinking*; ~6,2 GB di `Q4_K_M` |
| **M3** | Gemma 4 E4B-it | Gemma | 4B | Pembanding keluarga lintas arsitektur | `bartowski/google_gemma-4-E4B-it-GGUF` | Format tool call native non-OpenAI (`<\|tool_call>call:nama{...}<tool_call\|>`); **wajib lulus smoke test** |
| **M4** | Llama 3.2 3B Instruct | Llama | 3B | Baseline generasi lama / batas bawah | `bartowski/Llama-3.2-3B-Instruct-GGUF` | ~2,0 GB di `Q4_K_M`; cepat untuk pengujian awal |
| **M5** | Apertus-SEA-LION-v4-8B-IT | SEA-LION (AI Singapore) | 8B | Model regional kuat bahasa Indonesia | `aisingapore/Apertus-SEA-LION-v4-8B-IT-GGUF` | Quantizer berbeda dari bartowski; catat sebagai keterbatasan atau gunakan Mode Ketat |

**Model Cadangan** (bila ada model gagal *smoke test*): `Qwen3.5-2B` (`bartowski`/`unsloth`) atau `Gemma-SEA-LION-v4-4B-VL` (`aisingapore/Gemma-SEA-LION-v4-4B-VL:q4_k_m`).

---

## 1.6 Peta Arsitektur Workspace

```text
D:\Indoarg\
├── configs/        # YAML sumber kebenaran: models, experiment A/B/C, inference, & prompt ID
├── data/           # 10 tool schema, 4 tool normalizer S4, gazetteer, pairs, splits, smoke_14
├── grammars/       # Grammar GBNF hasil kompilasi otomatis dari tools_v1.json (untuk S2 & S3)
├── models/         # Penyimpanan GGUF terpisah per tingkat quant (Q4_K_M, Q8_0, Q6_K, Q3_K_M, BF16) + Modelfiles
├── src/indoarg/    # Paket Python inti: config, data, normalizers, tools, runners, strategies, eval, utils
├── scripts/        # 8 skrip pipeline terurut (00_download_models.py s.d. 07_report.py)
├── results/        # Keluaran mentah (raw/), skor per item (scored/), tabel (tables/), grafik (figures/)
├── logs/           # Manifest sha256, log smoke test, quant_manifest, log runtime
├── docs/           # Panduan anotasi ringkas, data card, dan ruang draf laporan
├── dokumen/        # Dokumentasi proyek komprehensif, teori, alur eksperimen, & sitasi (folder ini)
└── tests/          # Unit test pytest (normalizers, canonicalize/parse/taxonomy, metrics/stats)
```
