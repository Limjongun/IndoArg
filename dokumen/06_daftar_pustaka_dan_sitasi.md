# 06. Daftar Pustaka, Pemetaan Kebaruan & Sitasi

Dokumen ini mengompilasi seluruh referensi ilmiah, model, dan dokumentasi runtime dari Blueprint IndoArg (§18), lengkap dengan pemetaan relevansi terhadap pertanyaan riset (RQ1–RQ5) serta templat sitasi (APA & BibTeX).

> **Catatan integritas bibliografi:** Entri di bawah mempertahankan judul, tempat publikasi, tahun, dan tautan resmi persis sebagaimana tercatat pada blueprint. Sebelum pengumpulan naskah final, lengkapi daftar nama penulis lengkap dari halaman publikasi masing-masing tautan.

---

## 6.1 Pemetaan Literatur terhadap Pertanyaan Riset & Kebaruan IndoArg

| Kunci | Publikasi | Tahun / Venue | Fokus Utama | Keterkaitan & Posisi Kebaruan IndoArg |
|---|---|---|---|---|
| `[MLCL26]` | *Lost in Execution: On the Multilingual Robustness of Tool Calling in LLMs* | 2026 / ACL | Mengungkap kegagalan eksekusi *tool calling* lintas bahasa meski pemilihan tool tampak baik | Dasar langsung **RQ1 & RQ2**; IndoArg memperdalam dari level antar-bahasa ke level **antar-register berpasangan** dalam bahasa Indonesia sehari-hari |
| `[MASSIVE25]` | *MASSIVE-Agents: Multilingual Function-Calling in 52 Languages* | 2025 / Findings EMNLP | Benchmark *function calling* multibahasa pada 52 bahasa | Pembanding benchmark multibahasa; IndoArg menambahkan normalisasi nilai khas Indonesia (slang Betawi, Kemendagri, KRL, jam informal) |
| `[CTAX26]` | *Constraint Tax: Measuring Validity–Correctness Tradeoffs in Structured Outputs for SLMs* | 2026 / arXiv | Mengukur trade-off antara validitas skema dan kebenaran isi saat *constrained decoding* diterapkan pada SLM | Landasan langsung **RQ3** dan metrik **WVS** (*Wrong-Valid-Schema rate*) untuk membandingkan S1 vs S2 vs S3 vs S4 |
| `[REPAIR26]` | *Repair, Not Improvement: Decomposing Constrained Decoding in Tool-Call Abstention* | 2026 / arXiv | Mengurai efek *constrained decoding* terhadap kemampuan abstensi (*no-call*) | Menjadi dasar desain 20 pair `no_call`, metrik **ABS**, dan error `E_OVERCALL` pada strategi berbasis grammar (S2/S3) |
| `[SAMEQ26]` | *Same Quantization, Different Failures: Multi-Turn Tool-Calling in SLMs* | 2026 / NeurIPS | Menunjukkan pola kegagalan *tool calling* yang berbeda antarmodel meski pada tingkat kuantisasi yang sama | Landasan **Aturan Kuantisasi Seragam (§5)** dan komparasi lintas keluarga model (Qwen, Gemma, Llama, SEA-LION) |
| `[POLAG26]` | *PolAgentBench: Quantization Thresholds Replicate, Failure Modes Do Not* | 2026 / arXiv | Analisis dampak kuantisasi terhadap *tool calling* pada bahasa non-Inggris (Polandia) | Inspirasi langsung **RQ4 (Eksperimen B)** untuk menguji kurva degradasi kuantisasi `BF16..Q3_K_M` berinteraksi dengan register bahasa Indonesia |
| `[QMULTI24]` | *How Does Quantization Affect Multilingual LLMs?* | 2024 / arXiv | Dampak kuantisasi bobot terhadap performa model multibahasa secara umum | Landasan teoretis ketimpangan degradasi kuantisasi pada bahasa non-Inggris |
| `[CALIB26]` | *Calibrating Beyond English: Language Diversity for Better Quantized Multilingual LLMs* | 2026 / arXiv | Menunjukkan keberagaman bahasa data kalibrasi kuantisasi (*imatrix*) memengaruhi kualitas model multibahasa | Landasan **Mode Ketat (§5.3)**: kalibrasi `llama-imatrix` dengan korpus campuran ID+EN yang identik untuk semua model |

---

## 6.2 Daftar Pustaka Ilmiah (Format Referensi)

1. **MLCL (ACL 2026).** *Lost in Execution: On the Multilingual Robustness of Tool Calling in LLMs*. Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (ACL 2026). https://aclanthology.org/2026.acl-long.2039/
2. **Constraint Tax (2026).** *Measuring Validity–Correctness Tradeoffs in Structured Outputs for SLMs*. arXiv preprint arXiv:2605.26128. https://arxiv.org/abs/2605.26128
3. **Same Quantization, Different Failures (NeurIPS 2026).** *Same Quantization, Different Failures: Multi-Turn Tool-Calling in SLMs*. Advances in Neural Information Processing Systems (NeurIPS 2026). https://neurips.cc/virtual/2026/171271
4. **PolAgentBench (2026).** *Quantization Thresholds Replicate, Failure Modes Do Not*. arXiv preprint arXiv:2609.32042. https://arxiv.org/pdf/2609.32042
5. **MASSIVE-Agents (Findings EMNLP 2025).** *Multilingual Function-Calling in 52 Languages*. Findings of the Association for Computational Linguistics: EMNLP 2025. https://aclanthology.org/2025.findings-emnlp.1099/
6. **Quantization & Multilingual LLMs (2024).** *How Does Quantization Affect Multilingual LLMs?* arXiv preprint arXiv:2407.03211. https://arxiv.org/abs/2407.03211
7. **Calibrating Beyond English (2026).** *Calibrating Beyond English: Language Diversity for Better Quantized Multilingual LLMs*. arXiv preprint arXiv:2601.18306. https://arxiv.org/abs/2601.18306
8. **Repair, Not Improvement (2026).** *Repair, Not Improvement: Decomposing Constrained Decoding in Tool-Call Abstention*. arXiv preprint arXiv:2608.13959. https://arxiv.org/pdf/2608.13959

---

## 6.3 Rujukan Model, Runtime & Dokumentasi Teknis

| Kategori | Nama Sumber | Tautan Resmi |
|---|---|---|
| Model M1 | Qwen3.5-4B GGUF (bartowski) | https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF |
| Model M2 | Qwen3.5-9B GGUF (bartowski) | https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF |
| Model M3 | Gemma 4 E4B-it GGUF (bartowski) | https://huggingface.co/bartowski/google_gemma-4-E4B-it-GGUF |
| Dokumentasi M3 | Gemma 4 Function Calling (Google AI) | https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4 |
| Model M4 | Llama 3.2 3B Instruct GGUF (bartowski) | https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF |
| Model M5 | Koleksi SEA-LION v4 (AI Singapore) | https://huggingface.co/collections/aisingapore/sea-lion-v4 |
| Model M5 (Ollama) | Apertus-SEA-LION-v4-8B-IT (Ollama) | https://ollama.com/aisingapore/Apertus-SEA-LION-v4-8B-IT |
| Standar Wilayah | Kode Wilayah Administrasi Pemerintahan (Kemendagri / BPS) | Digunakan sebagai acuan `data/gazetteer/wilayah.csv` |
| Standar Stasiun | Kode Stasiun KAI Commuter Jabodetabek | Digunakan sebagai acuan `data/gazetteer/stasiun_krl.csv` |

---

## 6.4 Templat BibTeX (Siap Lengkapi Nama Penulis untuk Naskah LaTeX)

```bibtex
@inproceedings{mlcl2026lost,
  title     = {Lost in Execution: On the Multilingual Robustness of Tool Calling in LLMs},
  author    = {{[Lengkapi daftar penulis dari halaman ACL Anthology]}},
  booktitle = {Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (ACL)},
  year      = {2026},
  url       = {https://aclanthology.org/2026.acl-long.2039/}
}

@article{constrainttax2026,
  title   = {Constraint Tax: Measuring Validity--Correctness Tradeoffs in Structured Outputs for SLMs},
  author  = {{[Lengkapi daftar penulis dari halaman arXiv]}},
  journal = {arXiv preprint arXiv:2605.26128},
  year    = {2026},
  url     = {https://arxiv.org/abs/2605.26128}
}

@inproceedings{samequant2026neurips,
  title     = {Same Quantization, Different Failures: Multi-Turn Tool-Calling in SLMs},
  author    = {{[Lengkapi daftar penulis dari halaman NeurIPS]}},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year      = {2026},
  url       = {https://neurips.cc/virtual/2026/171271}
}

@article{polagentbench2026,
  title   = {PolAgentBench: Quantization Thresholds Replicate, Failure Modes Do Not},
  author  = {{[Lengkapi daftar penulis dari halaman arXiv]}},
  journal = {arXiv preprint arXiv:2609.32042},
  year    = {2026},
  url     = {https://arxiv.org/pdf/2609.32042}
}

@inproceedings{massiveagents2025,
  title     = {MASSIVE-Agents: Multilingual Function-Calling in 52 Languages},
  author    = {{[Lengkapi daftar penulis dari halaman ACL Anthology]}},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2025},
  year      = {2025},
  url       = {https://aclanthology.org/2025.findings-emnlp.1099/}
}

@article{quantmultilingual2024,
  title   = {How Does Quantization Affect Multilingual LLMs?},
  author  = {{[Lengkapi daftar penulis dari halaman arXiv]}},
  journal = {arXiv preprint arXiv:2407.03211},
  year    = {2024},
  url     = {https://arxiv.org/abs/2407.03211}
}

@article{calibratingbeyond2026,
  title   = {Calibrating Beyond English: Language Diversity for Better Quantized Multilingual LLMs},
  author  = {{[Lengkapi daftar penulis dari halaman arXiv]}},
  journal = {arXiv preprint arXiv:2601.18306},
  year    = {2026},
  url     = {https://arxiv.org/abs/2601.18306}
}

@article{repairnotimprovement2026,
  title   = {Repair, Not Improvement: Decomposing Constrained Decoding in Tool-Call Abstention},
  author  = {{[Lengkapi daftar penulis dari halaman arXiv]}},
  journal = {arXiv preprint arXiv:2608.13959},
  year    = {2026},
  url     = {https://arxiv.org/pdf/2608.13959}
}
```
