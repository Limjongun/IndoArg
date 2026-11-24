# Panduan Anotasi IndoArg

Dokumen ini menjadi pedoman baku bagi anotator (**A1** penulis, **A2** verifikator) dalam menyusun pasangan prompt `data/pairs/indoarg_v1.jsonl`.

## 1. Struktur Satu Pair

Setiap baris JSONL mewakili tepat satu intent (`pair_id` berpola `P0001`..`P0200` untuk *call*, `N0001`..`N0020` untuk *no-call*) dengan:
- Tiga varian register:
  1. **`formal`**: bahasa Indonesia baku (mis. `"pukul 19.00"`, `"Rp50.000"`, `"Kota Surabaya"`).
  2. **`informal`**: bahasa sehari-hari/gaul dengan minimal satu fenomena normalisasi dari §2 (mis. `"jam 7an malem"`, `"gocap"`, `"sby"`, `"jaksel"`).
  3. **`campur`**: campur kode Indonesia–Inggris yang alami dipakai sehari-hari (mis. `"set reminder meeting"`, `"transfer 50k via gopay"`, `"check shipping cost"`).
- Satu **`gold_call`** kanonik yang identik untuk ketiga varian (atau `null` untuk `no_call`).
- Satu **`reference_time`** terkunci dalam format ISO-8601 WIB (`+07:00`) agar keterangan waktu relatif selalu punya satu jawaban pasti.

## 2. Fenomena Kategori Nilai (`value_categories`)

| Kode | Fenomena | Contoh Informal → Kanonik |
|---|---|---|
| `waktu_relatif` | hari relatif | besok, lusa, minggu depan, Senin depan → tanggal ISO |
| `jam_informal` | jam tidak baku | jam 7an malem, setengah 8 pagi, jam 3 sore → `19:00`, `07:30`, `15:00` |
| `tanggal_format` | format tanggal campur | 24/11, 24 Nov, tgl 24 → `2026-11-24` |
| `nominal_singkat` | singkatan uang | 50rb, 50k, 1,5jt, sejuta → `50000`, `1500000`, `1000000` |
| `nominal_slang` | slang angka Betawi | gocap, cepek, gopek, seceng, goceng, ceban, noban → rupiah bulat |
| `angka_kata` | angka ditulis kata | dua ratus ribu, sejam setengah → `200000`, `90` |
| `lokasi_singkatan` | singkatan wilayah / stasiun | Jaksel, Sby, Jogja, Bdg, Tenabang → kode Kemendagri / KRL |
| `satuan` | konversi satuan | 2 kilo, setengah kilo, 3 ons → `2000`, `500`, `300` gram |
| `enum_merek` | variasi merek/enum | GoPay/gopey, ojol, grabcar → `gopay`, `motor`, `mobil` |
| `code_mix` | campur Inggris | reminder, meeting, transfer, shipping cost |
| `no_call` | tidak perlu tool | menolak memanggil tool |

## 3. Aturan Kesetaraan & Anti-Ambiguitas

1. **Tulis varian `formal` terlebih dahulu**, lalu kunci `gold_call`, baru tulis `informal` dan `campur`.
2. **Kesetaraan informasi:** varian informal/campur tidak boleh menambah ataupun menghilangkan informasi penting dibandingkan varian formal.
3. **Hindari ambiguitas tak terselesaikan:**
   - Selalu sertakan penanda waktu (`pagi`, `siang`, `sore`, `malem`) bila memakai jam 12-jam (`jam 7` → `jam 7 malem`).
   - Pastikan istilah slang uang jelas konteks mata uangnya (catat di kolom `notes` bila perlu).
4. **Privasi (PII):** Dilarang keras memakai nama asli orang pribadi, nomor rekening, nomor KTP, atau nomor telepon asli. Gunakan nama fiktif dan pola nomor fiktif (`08120000xxxx`, `512345678901`).
5. **Distribusi target (§7.2 & §17):**
   - Total **220 pair** (200 call + 20 no-call) = 660 item.
   - Split: **dev 44 pair (20%)**, **test 176 pair (80%)**.
   - Setiap tool minimal **15 pair**; setiap kategori nilai minimal **20 kemunculan**; minimal **30%** berlabel `sulit`.

## 4. Protokol Verifikasi Antar-Anotator

- A1 menyusun pair + gold call.
- A2 memverifikasi kesetaraan tiga varian, kebenaran `gold_call` terhadap gazetteer (`data/gazetteer/`) dan skema tool (`data/tools/tools_v1.json`), serta melabeli `verified_by`.
- Catat persentase kesepakatan awal (Cohen's kappa / exact agreement) sebelum rekonsiliasi untuk dilaporkan di `data_card.md`.
