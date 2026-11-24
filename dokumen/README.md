# Dokumentasi Proyek IndoArg

Folder `dokumen/` berisi seluruh dokumentasi konseptual, landasan teori, alur eksperimen, petunjuk operasional, panduan anotasi data, serta daftar pustaka & sitasi untuk proyek riset **IndoArg** (*Dari Bahasa Indonesia Sehari-hari ke Argumen Tool yang Bisa Dieksekusi pada LLM Lokal*).

## Peta Bacaan

| No | Dokumen | Isi Utama | Untuk Siapa |
|---|---|---|---|
| 1 | [01_ringkasan_proyek.md](./01_ringkasan_proyek.md) | Latar belakang masalah, pertanyaan riset (RQ1–RQ5), klaim kebaruan, panel model M1–M5, dan peta struktur workspace | Peneliti, pembimbing, kolaborator |
| 2 | [02_landasan_teori.md](./02_landasan_teori.md) | Teori *tool calling* LLM lokal, *register gap* bahasa Indonesia, *constraint tax*, kuantisasi GGUF & *imatrix*, *runtime variance*, taksonomi 11 kategori nilai & 10 kode error, serta formulasi matematis metrik & statistik | Penulisan bab Tinjauan Pustaka & Metodologi |
| 3 | [03_alur_eksperimen.md](./03_alur_eksperimen.md) | Diagram alur eksperimen *end-to-end*, rincian Eksperimen A / B / C, strategi S1–S4, aturan gerbang kuantisasi seragam, parameter decoding terkunci, format log/manifest, timeline 3 minggu, dan mitigasi risiko | Pelaksana eksperimen |
| 4 | [04_petunjuk_operasional.md](./04_petunjuk_operasional.md) | Petunjuk teknis instalasi & eksekusi di Windows PowerShell / WSL2, perintah `llama serve` & `Ollama`, penyesuaian GPU 6 GB VRAM (RTX 4050), shortcut `Makefile`, troubleshooting, dan checklist reprodusibilitas | Operator & developer |
| 5 | [05_panduan_data_dan_anotasi.md](./05_panduan_data_dan_anotasi.md) | Spesifikasi 10 tool target + 4 tool normalisasi S4, kamus gazetteer (Kemendagri, KRL, slang Betawi), skema `indoarg_v1.jsonl`, SOP penulisan 3 register & verifikasi A1–A2 | Anotator A1 & verifikator A2 |
| 6 | [06_daftar_pustaka_dan_sitasi.md](./06_daftar_pustaka_dan_sitasi.md) | Daftar pustaka lengkap (§18), matriks posisi kebaruan terhadap literatur 2024–2026, daftar rujukan model/runtime resmi, dan templat sitasi APA & BibTeX | Penulisan makalah / naskah publikasi |
| 7 | [07_hasil_smoketest.md](./07_hasil_smoketest.md) | Rekap metrik smoke test 14 kasus (`M1`–`M5` @ `Q4_K_M`, `S1`): CVR, TSA, EXA, WVS, ABS, taksonomi error, latensi, grafik PNG, dan temuan metodologis | Laporan kemajuan & verifikasi panel model |

## Dokumen Sumber & Terkait di Workspace

- Blueprint spesifikasi utama: [`../IndoArg_Blueprint_Workspace (1).md`](../IndoArg_Blueprint_Workspace%20%281%29.md)
- Panduan cepat root: [`../README.md`](../README.md)
- Panduan anotasi ringkas & data card: [`../docs/annotation_guide.md`](../docs/annotation_guide.md), [`../docs/data_card.md`](../docs/data_card.md)
- Konfigurasi sumber kebenaran: [`../configs/models.yaml`](../configs/models.yaml), [`../configs/inference.yaml`](../configs/inference.yaml), [`../configs/experiment_A.yaml`](../configs/experiment_A.yaml), [`../configs/experiment_B.yaml`](../configs/experiment_B.yaml), [`../configs/experiment_C.yaml`](../configs/experiment_C.yaml)
