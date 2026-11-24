# Data Card — IndoArg v1

## Ringkasan Dataset

- **Nama:** IndoArg v1 (`data/pairs/indoarg_v1.jsonl`)
- **Tugas:** Pemanggilan tool (*tool calling*) dan normalisasi argumen dari bahasa Indonesia sehari-hari ke bentuk kanonik yang siap dieksekusi.
- **Bahasa:** Bahasa Indonesia (baku & kolokial/gaul) serta campur kode Indonesia–Inggris.
- **Status Saat Ini:** Korpus lengkap **220 pair / 660 item** lulus validasi ketat `scripts/02_validate_data.py --strict-targets` (`0` error struktural, `0` peringatan target §7.2). Seluruh pair baru berstatus `draft_A1` / `pending_A2` (kecuali 4 contoh blueprint `P0001`, `P0042`, `P0107`, `N0003`) dan siap menjalani tinjauan verifikasi manusia A2 sebelum rilis publikasi final.

## Komposisi & Split Terstratifikasi

| Komponen | Dev (20%) | Test (80%) | Total |
|---|---|---|---|
| Pair *call* (10 tool × 20 pair) | 40 pair (120 item) | 160 pair (480 item) | **200 pair (600 item)** |
| Pair *no-call* (umum + near-miss adversarial) | 4 pair (12 item) | 16 pair (48 item) | **20 pair (60 item)** |
| **Total** | **44 pair (132 item)** | **176 pair (528 item)** | **220 pair (660 item)** |

- **Sebaran kesulitan:** `mudah` = 58 (26,4%), `sedang` = 76 (34,5%), **`sulit` = 86 (39,1%, target ≥ 30%)**.
- **Sebaran kategori nilai (seluruh 11 kategori ≥ 20):** `waktu_relatif` (53), `jam_informal` (49), `tanggal_format` (27), `nominal_singkat` (42), `nominal_slang` (27), `angka_kata` (52), `lokasi_singkatan` (57), `satuan` (38), `enum_merek` (68), `code_mix` (219), `no_call` (20).
- **Smoke set terpisah:** `data/smoke/smoke_14.jsonl` (14 kasus uji cepat lintas 10 tool + `no_call`).

## Sumber Gazetteer

- `data/gazetteer/wilayah.csv`: kode wilayah kabupaten/kota standar Kemendagri (`XX.XX`).
- `data/gazetteer/alias_wilayah.csv`: pemetaan singkatan dan sebutan populer kota/kabupaten.
- `data/gazetteer/stasiun_krl.csv`: 50 kode stasiun KAI Commuter Jabodetabek beserta alias harian.
- `data/gazetteer/slang_angka.csv`: kosakata slang angka Betawi dan bilangan informal Indonesia.

## Privasi & Etika

- Seluruh entitas (nama penerima/peserta, ID pelanggan PLN/PDAM/BPJS, nomor ponsel `08xx0000xxxx`) bersifat sepenuhnya fiktif.
- Tidak ada data pribadi sungguhan (PII) di dalam dataset.

## Kesepakatan Antar-Anotator

- Status verifikasi saat ini: 4 pair acuan blueprint berlabel `A1`/`A2`; 216 pair korpus penuh berlabel `draft_A1`/`pending_A2`.
- Setelah tinjauan independen oleh anotator manusia A2 selesai, perbarui kolom `verified_by` dan laporkan *exact agreement* & Cohen's κ untuk `tool_target` dan `gold_call` di bagian ini.
