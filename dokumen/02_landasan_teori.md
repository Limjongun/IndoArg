# 02. Landasan Teori, Taksonomi, Metrik & Statistik

Dokumen ini memaparkan fondasi teoretis yang mendasari desain eksperimen **IndoArg**, lengkap dengan definisi formal taksonomi nilai, taksonomi error, formulasi matematis metrik evaluasi, serta metode inferensi statistik yang dipakai.

---

## 2.1 *Tool Calling* pada LLM Lokal

*Tool calling* (atau *function calling*) mengubah LLM dari generator teks bebas menjadi komponen perangkat lunak yang menghasilkan panggilan fungsi terstruktur $(f, \mathbf{a})$, di mana $f \in \mathcal{F} \cup \{\varnothing\}$ adalah nama fungsi target (atau $\varnothing$ untuk abstensi / `no_call`) dan $\mathbf{a} = \{(k_1, v_1), \dots, (k_m, v_m)\}$ adalah pasangan argumen–nilai yang tunduk pada skema JSON $\mathcal{S}_f$.

Pada model lokal (*Small Language Models*, 3B–9B parameter), eksekusi tool calling yang andal menuntut empat kapabilitas berurutan:
1. **Keputusan pemanggilan (*Invocation / Abstention Decision*):** menentukan apakah permintaan memerlukan tool atau cukup dijawab langsung tanpa tool (*abstention*).
2. **Pemilihan tool (*Tool Selection*):** memetakan intent pengguna ke tepat satu tool $f \in \mathcal{F}$.
3. **Kepatuhan sintaks & skema (*Structural / Schema Compliance*):** memproduksi struktur serialisasi (JSON atau format native seperti `<|tool_call>call:...`) yang dapat di-parse dan mematuhi tipe data, `required`, `enum`, serta pola regex pada $\mathcal{S}_f$.
4. **Normalisasi nilai argumen (*Semantic Argument Grounding & Normalization*):** mengonversi ungkapan alami, relatif, implisit, atau kolokial di dalam prompt menjadi representasi nilai kanonik yang dapat dieksekusi oleh API/executor hilir.

Literatur *multilingual tool calling* seperti **MASSIVE-Agents** (2025) dan **MLCL** (ACL 2026) menunjukkan bahwa penurunan performa lintas bahasa paling tajam tidak selalu terjadi pada langkah (2), melainkan pada langkah (4) — *lost in execution* — ketika argumen gagal dipetakan ke format eksekusi yang tepat.

---

## 2.2 Variasi Register Bahasa Indonesia & *Register Gap*

Dalam sosiolinguistik, **register** merujuk pada variasi bahasa yang bergantung pada situasi komunikasi (tingkat keformalan, media, dan relasi penutur). Pengguna aplikasi percakapan di Indonesia secara rutin berganti antara tiga register utama:

1. **Formal (baku):** mengikuti EYD/KBBI, penulisan waktu 24 jam (`pukul 19.00`), nominal berformat (`Rp50.000`), dan nama geografis resmi (`Kota Surabaya`, `Jakarta Selatan`).
2. **Informal (sehari-hari / kolokial):** ditandai oleh pemendekan morfologis (`ingetin`, `pesenin`, `dr`, `brp`), sistem jam 12-jam dengan idiom pengurangan (`setengah 8` = 07:30, `jam 7an malem` = 19:00), slang angka serapan Hokkien/Betawi (`gocap`, `ceban`, `noban`, `goceng`, `cepek`), singkatan wilayah populer (`Jaksel`, `Sby`, `Jogja`, `Tangsel`, `Tenabang`), dan satuan percakapan (`2 kilo`, `sejam setengah`).
3. **Campur kode (*code-mixing* Indonesia–Inggris):** mencampurkan kata kerja atau frasa domain teknis berbahasa Inggris ke dalam sintaks Indonesia sehari-hari (`set reminder meeting besok jam 7 malem`, `transfer 50k via gopay`, `cek shipping cost`).

**Hipotesis *Register Gap*:** Karena data pelatihan *instruction-tuning* dan *function-calling* didominasi bahasa Inggris serta teks Indonesia formal, model lokal cenderung menunjukkan selisih akurasi eksekusi yang signifikan ($\Delta\text{Reg} > 0$) antara varian `formal` melawan `informal` dan `campur` meskipun kandungan informasinya 100% identik.

---

## 2.3 *Constrained Decoding* & *Constraint Tax*

Untuk mengatasi kegagalan parsing JSON (`E_PARSE`) dan pelanggaran skema (`E_SCHEMA`), runtime lokal menyediakan *constrained decoding* berbasis grammar **GBNF** (*GGML BNF*) atau *JSON Schema masking* (diwakili strategi **S2**). Pada setiap langkah decoding token $t$, logit semua token yang melanggar transisi automaton grammar di-mask ke $-\infty$:

$$P_{\text{constrained}}(y_t \mid y_{<t}, x) = \frac{\mathbb{I}(y_t \in \mathcal{V}_{\text{valid}}(y_{<t})) \cdot \exp(z_t)}{\sum_{v \in \mathcal{V}_{\text{valid}}(y_{<t})} \exp(z_v)}$$

Namun penelitian **Constraint Tax** (2026) dan **Repair, Not Improvement** (2026) mengungkap efek samping penting:
- **Memperbaiki sintaks, tidak selalu memperbaiki penalaran:** Pemaksaan grammar mendorong *Call Validity Rate* (CVR) mendekati 100%, tetapi memotong ruang penalaran bebas model sehingga model terpaksa "menebak" nilai yang sah secara tipe/pola namun **salah secara makna** (misal memilih `"2026-11-24T07:00:00+07:00"` alih-alih `19:00`, atau menebak kode wilayah `"31.71"` alih-alih `"31.74"`). Fenomena ini diukur oleh metrik **WVS (*Wrong-Valid-Schema rate*)**.
- **Dampak terhadap abstensi:** Constrained decoding juga berisiko mengganggu keputusan *no-call* apabila format output memaksa pemanggilan tool atau mengubah distribusi probabilitas antara `no_call` dan tool aktif.

Sebagai perbandingan langsung terhadap *constraint tax*, IndoArg menguji dua alternatif mekanisme:
- **S3 (*Two-Stage Decoding*):** memisahkan ruang penalaran & normalisasi teks bebas (Tahap 1) dari penguncian grammar JSON (Tahap 2), sehingga beban normalisasi tidak terganggu oleh pemaksaan struktur token awal.
- **S4 (*External Normalizer Tool*):** mendelegasikan komputasi normalisasi deterministik (kalender, slang angka, gazetteer wilayah, konversi satuan) keluar dari bobot LLM ke 4 tool bantu (`parse_waktu`, `parse_nominal`, `cari_wilayah`, `parse_satuan`).

---

## 2.4 Kuantisasi GGUF, *Imatrix*, dan Ketahanan Multibahasa

Kuantisasi pasca-pelatihan (*Post-Training Quantization*) pada format **GGUF** (`llama.cpp`) memetakan bobot presisi tinggi (`BF16`/`F16`, 16-bit) ke representasi *k-quants* berbit rendah (`Q8_0`, `Q6_K`, `Q4_K_M`, `Q3_K_M`) menggunakan blok skala bertingkat (*super-blocks*).

Tiga prinsip teoretis yang mendasari **Aturan Kuantisasi Seragam (§5)** dan **Eksperimen B (RQ4)**:
1. **Ketidaksetaraan antar-resep kuantisasi:** Varian yang tampak mirip secara ukuran seperti `Q4_K_M`, `Q4_K_S`, `Q4_K_L`, `IQ4_XS`, dan `Q4_0` memiliki alokasi bit per tensor (terutama *attention value*, *FFN down-proj*, dan *output head*) yang berbeda. Oleh sebab itu, membandingkan model A di `Q4_K_M` dengan model B di `IQ4_XS` melanggar validitas internal eksperimen. Sumber kebenaran harus dibaca dari header biner GGUF `general.file_type`, bukan dari nama file.
2. **Degradasi tidak merata lintas bahasa & register:** Riset kuantisasi multibahasa (2024–2026, termasuk *PolAgentBench* dan *Same Quantization, Different Failures*) menunjukkan bahwa pengetahuan ekor panjang (*long-tail*), idiom regional, dan pemanggilan tool multi-langkah lebih rentan rusak pada presisi rendah dibanding bahasa Inggris baku. Eksperimen B menguji apakah pola yang sama berlaku untuk **register informal/campur vs formal** dalam satu bahasa (Indonesia).
3. **Pengaruh bahasa kalibrasi *Importance Matrix* (`imatrix`):** Matriks kepentingan aktivasi membantu menjaga bobot kritis saat kuantisasi bit rendah. Kalibrasi yang hanya memakai teks Inggris dapat merugikan representasi token bahasa Indonesia (*Calibrating Beyond English*, 2026). Oleh karena itu, blueprint menyediakan **Mode Ketat (§5.3)** dengan teks kalibrasi campuran ID+EN yang identik untuk semua model.

---

## 2.5 Varians Runtime (*Runtime Variance*)

Meskipun dua runtime lokal memuat **file bobot GGUF yang identik bit-per-bit (SHA-256 sama)**, hasil *tool calling* tetap dapat berbeda signifikan karena:
- Perbedaan mesin render **chat template** (Jinja template bawaan GGUF pada `llama-server --jinja` vs Go template/renderer pada `Ollama`).
- Perbedaan **parser tool call** pasca-generasi (terutama untuk format khusus seperti Gemma 4 `<|tool_call>call:...` atau Qwen `<tool_call>`).
- Perbedaan penanganan *stop token*, token *thinking* (`enable_thinking=false` vs `think=false`), dan implementasi *constrained grammar*.

**Eksperimen C (RQ5)** mengisolasi efek runtime secara bersih dengan memaksa Ollama memakai `Modelfile` yang menunjuk langsung ke file lokal `models/Q4_K_M/<M>.gguf` yang sama dengan `llama.cpp`.

---

## 2.6 Taksonomi Kategori Nilai & Taksonomi Error

### A. 11 Kategori Nilai (`value_categories`)

| Kode | Fenomena Linguistik / Format | Contoh Informal → Nilai Kanonik |
|---|---|---|
| `waktu_relatif` | Referensi hari relatif terhadap `reference_time` | `besok`, `lusa`, `Senin depan`, `minggu depan` → tanggal ISO |
| `jam_informal` | Penulisan jam 12-jam & idiom waktu Indonesia | `jam 7an malem`, `setengah 8 pagi`, `jam 3 sore` → `19:00`, `07:30`, `15:00` |
| `tanggal_format` | Format tanggal singkat / campur | `24/11`, `24 Nov`, `tgl 24` → `2026-11-24` |
| `nominal_singkat` | Singkatan satuan uang | `50rb`, `50k`, `1,5jt`, `sejuta` → `50000`, `1500000`, `1000000` |
| `nominal_slang` | Slang angka Betawi / Hokkien | `gocap`, `cepek`, `gopek`, `seceng`, `goceng`, `ceban`, `noban` → int rupiah |
| `angka_kata` | Bilangan tertulis dalam kata | `dua ratus ribu`, `sejam setengah` → `200000`, `90` |
| `lokasi_singkatan` | Singkatan kota/kabupaten & stasiun KRL | `Jaksel`, `Sby`, `Jogja`, `Bdg`, `Tenabang` → `31.74`, `35.78`, `34.71`, `32.73`, `THB` |
| `satuan` | Konversi besaran ke satuan kanonik | `2 kilo`, `setengah kilo`, `3 ons` → `2000`, `500`, `300` gram |
| `enum_merek` | Variasi ejaan & merek kolokial | `GoPay`/`gopey`, `ojol`, `grabcar` → `gopay`, `motor`, `mobil` |
| `code_mix` | Campur kode Indonesia–Inggris | `set reminder meeting`, `transfer 50k`, `shipping cost` |
| `no_call` | Permintaan di luar cakupan 10 tool | Abstensi (tidak memanggil tool) |

### B. 10 Kode Taksonomi Error (`src/indoarg/eval/taxonomy.py`)

| Kode Error | Definisi Diagnostik |
|---|---|
| `E_PARSE` | Keluaran tampak berupaya memanggil tool namun gagal di-parse menjadi `{name, arguments}` valid |
| `E_SCHEMA` | Dapat di-parse, tetapi melanggar JSON schema tool (tipe data salah, pola regex/enum salah, dll.) |
| `E_TOOL` | Memilih nama tool yang salah dibanding `gold_call.name` |
| `E_MISSING` | Satu atau lebih argumen wajib (`required`) hilang |
| `E_VALUE_FORMAT` | Makna nilai benar (cocok bila dinormalisasi ulang), tetapi formatnya tidak kanonik (mis. `"50rb"` bukan `50000`, `"2 kilo"` bukan `2000`) |
| `E_VALUE_LANG` | Nilai masih dalam bahasa/alias pengguna, bukan kode/enum kanonik (mis. `"Jaksel"` bukan `"31.74"`, `"ojol"` bukan `"motor"`) |
| `E_VALUE_WRONG` | Nilai keliru secara makna/semantik (mis. `07:00` padahal seharusnya `19:00`, atau nominal `5000` padahal `50000`) |
| `E_HALLUC_ARG` | Menambahkan kunci argumen yang tidak ada dalam definisi skema tool |
| `E_OVERCALL` | Memanggil tool pada item `no_call` |
| `E_UNDERCALL` | Menjawab teks biasa tanpa memanggil tool padahal item membutuhkan pemanggilan tool |

---

## 2.7 Formulasi Matematis Metrik & Uji Statistik

Misalkan $\mathcal{D} = \mathcal{D}_{\text{call}} \cup \mathcal{D}_{\text{nocall}}$ adalah himpunan item uji, di mana setiap item $i$ berasal dari pasangan $p \in \mathcal{P}$ dan register $r \in \{\text{formal}, \text{informal}, \text{campur}\}$.

### A. Metrik Utama (`src/indoarg/eval/metrics.py`)

1. **Call Validity Rate (CVR):** persentase item *call* yang berhasil di-parse dan lulus validasi JSON Schema:
   $$\text{CVR} = \frac{1}{|\mathcal{D}_{\text{call}}|} \sum_{i \in \mathcal{D}_{\text{call}}} \mathbb{I}(\text{valid\_schema}_i)$$

2. **Tool Selection Accuracy (TSA):** persentase item *call* dengan nama tool sesuai gold:
   $$\text{TSA} = \frac{1}{|\mathcal{D}_{\text{call}}|} \sum_{i \in \mathcal{D}_{\text{call}}} \mathbb{I}(\hat{f}_i = f_i^*)$$

3. **Executable Accuracy (EXA — metrik utama):** item dianggap benar ($\text{EXA}_i = 1$) bila:
   - Untuk item *call*: skema valid, tool tepat, tidak ada argumen hilang/halusinasi, semua `strict_keys` identik dengan gold setelah kanonisasi, dan semua `soft_keys` lulus aturan `casefold` / `fuzzy` ($\ge \tau$) / `set_casefold`.
   - Untuk item *no-call*: model tidak memanggil tool ($\hat{f}_i = \varnothing$).
   $$\text{EXA} = \frac{1}{|\mathcal{D}|} \sum_{i \in \mathcal{D}} \text{EXA}_i$$

4. **Wrong-Valid-Schema Rate (WVS — pengukur *Constraint Tax*):** proporsi panggilan valid secara skema yang gagal secara eksekusi:
   $$\text{WVS} = \frac{\sum_{i \in \mathcal{D}_{\text{call}}} \mathbb{I}(\text{valid\_schema}_i \land \neg \text{EXA}_i)}{\sum_{i \in \mathcal{D}_{\text{call}}} \mathbb{I}(\text{valid\_schema}_i)}$$

5. **Value Accuracy per Kategori ($\text{VA}[k]$):** rata-rata $\text{EXA}_i$ pada subset item yang mengandung kategori nilai $k$.

6. **Abstention Accuracy (ABS):**
   $$\text{ABS} = \frac{1}{|\mathcal{D}_{\text{nocall}}|} \sum_{i \in \mathcal{D}_{\text{nocall}}} \mathbb{I}(\hat{f}_i = \varnothing)$$

7. **Register Gap ($\Delta\text{Reg}$ berpasangan per `pair_id`):**
   $$\Delta\text{Reg}_{\text{inf}} = \frac{1}{|\mathcal{P}|} \sum_{p \in \mathcal{P}} \left(\text{EXA}_{p,\text{formal}} - \text{EXA}_{p,\text{informal}}\right), \qquad \Delta\text{Reg}_{\text{mix}} = \frac{1}{|\mathcal{P}|} \sum_{p \in \mathcal{P}} \left(\text{EXA}_{p,\text{formal}} - \text{EXA}_{p,\text{campur}}\right)$$

8. **Metrik Efisiensi:** latensi persentil $p_{50}$ & $p_{95}$ (ms), kecepatan decode (token/detik), puncak VRAM (MiB), dan rata-rata jumlah langkah (*steps*) untuk S3/S4.

### B. Inferensi Statistik (`src/indoarg/eval/stats.py`)

1. **Interval Kepercayaan 95% (*Clustered Paired Bootstrap*):** Resampling dilakukan $B = 10.000$ kali pada **level `pair_id`** (bukan level item independen) sehingga ketiga register dalam satu pair selalu ditarik bersamaan. Pendekatan ini menjaga struktur korelasi intra-pair.
2. **Uji Beda Berpasangan (*McNemar's Test* + Koreksi Holm):** Untuk membandingkan dua strategi $(S_a, S_b)$ atau dua register pada model yang sama, dipakai uji McNemar pada tabel kontingensi biner $(n_{11}, n_{10}, n_{01}, n_{00})$ (eksak binomial bila $n_{10}+n_{01} < 25$; chi-square terkoreksi kontinuitas bila $\ge 25$). Nilai-$p$ seluruh perbandingan majemuk dikoreksi dengan prosedur **Holm–Bonferroni** ($\alpha = 0{,}05$) untuk mengendalikan *Family-Wise Error Rate* (FWER).
3. **Uji Interaksi Kuantisasi × Register (Eksperimen B — GEE Binomial):** Memodelkan probabilitas keberhasilan eksekusi dengan *Generalized Estimating Equations* (keluarga Binomial, link logit, klaster `pair_id`):
   $$\operatorname{logit}\big(P(\text{EXA}_{p,r,q} = 1)\big) = \beta_0 + \beta_1 \text{register}_r + \beta_2 \text{quant\_bits}_q + \beta_3 (\text{register}_r \times \text{quant\_bits}_q)$$
   Koefisien interaksi $\beta_3$ yang signifikan menunjukkan bahwa penurunan bit kuantisasi merusak register informal/campur dengan laju berbeda dibanding register formal.
4. ***Baseline Floor Check*:** Apabila $\text{EXA}_{\text{BF16}} < 20\%$ pada suatu model, kurva degradasi kuantisasinya **tidak boleh ditafsirkan** sebagai efek kuantisasi karena model tersebut sudah tidak mampu sejak presisi penuh.
