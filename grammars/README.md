# Grammars (GBNF)

Direktori ini berisi grammar GBNF yang dihasilkan dari `data/tools/tools_v1.json` untuk strategi **S2 (Grammar ketat)** dan **S3 (Tahap 2)**.

Cara membangun ulang grammar:

```bash
python scripts/03_build_grammar.py data/tools/tools_v1.json grammars/tools_v1.gbnf
```

Aturan:
- Seluruh 10 tool target + sentinel `no_call` tercakup dalam satu aturan `root`.
- Jangan edit `tools_v1.gbnf` secara manual; ubah `data/tools/tools_v1.json` lalu jalankan ulang `03_build_grammar.py`.
