# 05. Panduan Data, Spesifikasi Tool, Gazetteer & Anotasi

Dokumen ini menjadi acuan teknis untuk seluruh skema tool, kamus referensi (*gazetteer*), struktur korpus `indoarg_v1.jsonl`, dan prosedur standar anotasi dua tahap (A1 & A2).

---

## 5.1 Spesifikasi 10 Tool Target (`data/tools/tools_v1.json`)

Seluruh tool target bersifat **mock deterministik** ([`src/indoarg/tools/mock_executors.py`](../src/indoarg/tools/mock_executors.py)): tidak memanggil layanan eksternal, hanya memvalidasi argumen terhadap skema JSON dan mengembalikan respons tetap. Semua skema mengunci `additionalProperties: false`.

| # | Nama Tool | Parameter Wajib & Format Kanonik | Kategori Nilai yang Diuji |
|---|---|---|---|
| 1 | `buat_pengingat` | `judul: str`, `waktu: YYYY-MM-DDTHH:MM:SS+07:00` | `waktu_relatif`, `jam_informal`, `code_mix` |
| 2 | `transfer_ewallet` | `penerima: str`, `nominal: int (>=1000)`, `platform: enum[gopay, ovo, dana, shopeepay]` | `nominal_slang`, `nominal_singkat`, `enum_merek` |
| 3 | `cek_ongkir` | `asal: XX.XX`, `tujuan: XX.XX`, `berat_gram: int (>=1)`, `kurir: enum[jne, jnt, sicepat, pos]` | `lokasi_singkatan`, `satuan`, `enum_merek` |
| 4 | `jadwal_krl` | `stasiun_asal: enum[50 kode KRL]`, `stasiun_tujuan: enum[50 kode KRL]`, `waktu: ISO-8601+07:00` | `lokasi_singkatan`, `waktu_relatif`, `jam_informal`, `tanggal_format` |
| 5 | `cek_cuaca` | `wilayah: XX.XX`, `tanggal: YYYY-MM-DD` | `lokasi_singkatan`, `waktu_relatif`, `tanggal_format` |
| 6 | `pesan_ojek` | `jemput: str`, `tujuan: str`, `layanan: enum[motor, mobil]` | `enum_merek` (`ojol`, `gocar`, `grabcar`), `code_mix` |
| 7 | `konversi_kurs` | `jumlah: number (>0)`, `dari: ^[A-Z]{3}$`, `ke: ^[A-Z]{3}$` | `angka_kata`, `nominal_slang`, kode ISO-4217 |
| 8 | `bayar_tagihan` | `jenis: enum[pln, pdam, bpjs, pulsa]`, `id_pelanggan: str (>=4)`, `nominal: int (>=1000)` | `enum_merek`, `nominal_slang`, `nominal_singkat` |
| 9 | `buat_jadwal_rapat` | `judul: str`, `mulai: ISO-8601+07:00`, `durasi_menit: int (>=5)`, `peserta: list[str] (>=1)` | `waktu_relatif`, `jam_informal`, `angka_kata`, `satuan` |
| 10 | `cari_dokumen` | `query: str`, `top_k: int (1..50)` | `code_mix` (juga mendukung ekstensi RAG) |

### 4 Tool Normalisasi Khusus Strategi S4 (`data/tools/normalizer_tools.json`)

| Tool Normalisasi | Input | Output Kanonik | Implementasi Referensi |
|---|---|---|---|
| `parse_waktu` | `teks: str`, `waktu_acuan: ISO-8601+07:00` | `{"iso": "...", "date": "YYYY-MM-DD", "has_time": bool}` | [`src/indoarg/normalizers/waktu.py`](../src/indoarg/normalizers/waktu.py) |
| `parse_nominal` | `teks: str` | `{"nominal": int}` | [`src/indoarg/normalizers/nominal.py`](../src/indoarg/normalizers/nominal.py) |
| `cari_wilayah` | `teks: str` | `{"kode": "XX.XX", "nama_resmi": "...", "provinsi": "..."}` | [`src/indoarg/normalizers/wilayah.py`](../src/indoarg/normalizers/wilayah.py) |
| `parse_satuan` | `teks: str`, `target: enum[gram, menit, meter, mililiter]` | `{"nilai": int/float, "target": "..."}` | [`src/indoarg/normalizers/satuan.py`](../src/indoarg/normalizers/satuan.py) |

---

## 5.2 Kamus Gazetteer (`data/gazetteer/`)

1. **[`wilayah.csv`](../data/gazetteer/wilayah.csv):** Kode wilayah resmi kabupaten/kota standar Kemendagri (`XX.XX`), misal `31.74` (Jakarta Selatan), `35.78` (Surabaya), `32.73` (Bandung), `34.71` (Yogyakarta), `33.74` (Semarang), `36.74` (Tangerang Selatan). Setiap penambahan kota baru wajib diverifikasi ulang terhadap daftar resmi Kemendagri/BPS.
2. **[`alias_wilayah.csv`](../data/gazetteer/alias_wilayah.csv):** Pemetaan singkatan/sebutan populer (`jaksel`, `jakpus`, `tangsel`, `sby`, `bdg`, `jogja`, `smg`, `solo`, `mlg`, `mdn`, `mks`, `dps`, dst.) ke kode Kemendagri.
3. **[`stasiun_krl.csv`](../data/gazetteer/stasiun_krl.csv):** 50 kode stasiun KAI Commuter Jabodetabek (lintas Bogor, Cikarang, Rangkasbitung, Tangerang, Tanjung Priok, Nambo) beserta alias kolokial (`tenabang` → `THB`, `pocin` → `POC`, `beos`/`jakot` → `JAKK`, `debar` → `DPB`, `parpang` → `PRP`).
4. **[`slang_angka.csv`](../data/gazetteer/slang_angka.csv):** Kamus slang angka Betawi & bilangan informal dengan dua kolom nilai eksplisit (`nilai_dasar` vs `nilai_rupiah_konteks_uang`), sehingga konteks mata uang asing (`cepek dolar singapura` = `100`) terpisah tegas dari konteks rupiah (`tf gocap` = `50000`, `bayar cepek` = `100000`).

---

## 5.3 Skema Dataset & Target Komposisi (§7)

### Format Baris JSONL (`data/pairs/indoarg_v1.jsonl`)

Skema validasi formal tersimpan di [`data/pairs/indoarg_v1.schema.json`](../data/pairs/indoarg_v1.schema.json):

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

### Komposisi Korpus v1 Saat Ini vs Target Publikasi (§7.2 & §17)

| Komponen | Status Korpus v1 Saat Ini (`indoarg_v1.jsonl`) | Target Final Publikasi |
|---|---|---|
| Pair *call* (`P0001`..`P0200`) | **200 pair (600 item)** | **200 pair (600 item)** |
| Pair *no-call* (`N0001`..`N0020`) | **20 pair (60 item)** | **20 pair (60 item)** |
| **Total** | **220 pair (660 item)** — lulus `--strict-targets` | **220 pair (660 item)** |
| Split `dev` / `test` | **44 (20%) / 176 (80%)** (terstratifikasi 4/16 per tool) | **44 (20%) / 176 (80%)** |
| Sebaran minimum per tool | **20 pair / tool** (10/10 tool tercakup) | **≥ 15 pair / tool** |
| Sebaran minimum per kategori nilai | **Seluruh 11 kategori ≥ 20** (20 s.d. 219) | **≥ 20 kemunculan / kategori** |
| Proporsi kesulitan `sulit` | **39,1% (86/220)** | **≥ 30%** |

---

## 5.4 SOP Penulisan & Verifikasi Anotator (A1 & A2)

1. **Tulis `formal` terlebih dahulu**, lalu kunci `gold_call` dan verifikasi terhadap skema tool & gazetteer.
2. **Tulis `informal`** dengan memasukkan minimal satu fenomena dari 10 kategori nilai non-`no_call` (§2.6), tanpa mengurangi atau menambah fakta apa pun dari `formal`.
3. **Tulis `campur`** dengan memasukkan minimal satu frasa/kata Inggris alami yang lazim dipakai pengguna Indonesia sehari-hari.
4. **Selesaikan ambiguitas sejak penulisan:**
   - Tambahkan penanda waktu (`pagi`, `siang`, `sore`, `malem`) untuk setiap jam 12-jam.
   - Catat keputusan interpretasi di kolom `notes` (mis. hari Senin pada `reference_time` sehingga `"Senin depan"` = +7 hari).
5. **Klasifikasikan `strict_keys` vs `soft_keys`:**
   - Nilai kanonik (waktu, tanggal, nominal, kode wilayah, kode stasiun, enum, berat/durasi, kode kurs, `top_k`, `id_pelanggan`) **wajib masuk `strict_keys`**.
   - Teks bebas (`judul`, `penerima`, `jemput`, `tujuan`, `query`, `peserta`) boleh memakai `soft_keys` (`casefold`, `fuzzy` dengan `threshold` & `aliases`, atau `set_casefold`).
6. **Jaga privasi (bebas PII):** dilarang mencantumkan nama lengkap orang asli, nomor telepon sungguhan, atau nomor rekening/pelanggan nyata.
7. **Verifikasi silang A2:** anotator A2 meninjau seluruh pair secara independen; catat tingkat kesepakatan awal sebelum rekonsiliasi di [`docs/data_card.md`](../docs/data_card.md).
8. **Validasi otomatis:** setiap batch tambahan wajib lulus `python scripts/02_validate_data.py data/pairs/indoarg_v1.jsonl` (dan `--strict-targets` saat genap 220 pair) serta sinkron dengan `data/splits/dev.txt` dan `data/splits/test.txt`.
