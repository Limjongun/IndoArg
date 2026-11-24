# IndoArg Pipeline Makefile (Windows & POSIX compatible)
ifeq ($(OS),Windows_NT)
  PYTHON := .venv/Scripts/python.exe
  PYTEST := .venv/Scripts/pytest.exe
  RUFF   := .venv/Scripts/ruff.exe
else
  PYTHON := .venv/bin/python
  PYTEST := .venv/bin/pytest
  RUFF   := .venv/bin/ruff
endif

EXP      ?= A
EXP_NAME ?= A_main
MODEL    ?= M1
ENDPOINT ?= http://127.0.0.1:8080/v1

.PHONY: help download verify validate grammar smoke run score report test lint

help:
	@echo "Target tersedia:"
	@echo "  make download EXP=A          Unduh model GGUF sesuai configs/experiment_<EXP>.yaml"
	@echo "  make verify EXP=A            Jalankan gerbang verifikasi kuantisasi seragam"
	@echo "  make validate                Validasi data/pairs/indoarg_v1.jsonl"
	@echo "  make grammar                 Bangun grammars/tools_v1.gbnf dari tools_v1.json"
	@echo "  make smoke MODEL=M1          Jalankan 14 kasus smoke test ke ENDPOINT"
	@echo "  make run EXP=A MODEL=M1      Jalankan matriks eksperimen"
	@echo "  make score EXP_NAME=A_main   Hitung metrik & uji statistik"
	@echo "  make report EXP_NAME=A_main  Hasilkan tabel & grafik laporan"
	@echo "  make test                    Jalankan unit test pytest"
	@echo "  make lint                    Jalankan linter ruff"

download:
	$(PYTHON) scripts/00_download_models.py --exp configs/experiment_$(EXP).yaml

verify:
	$(PYTHON) scripts/01_verify_quant.py configs/experiment_$(EXP).yaml

validate:
	$(PYTHON) scripts/02_validate_data.py data/pairs/indoarg_v1.jsonl

grammar:
	$(PYTHON) scripts/03_build_grammar.py data/tools/tools_v1.json grammars/tools_v1.gbnf

smoke:
	$(PYTHON) scripts/04_smoke_test.py --model $(MODEL) --endpoint $(ENDPOINT)

run:
	$(PYTHON) scripts/05_run_matrix.py --exp configs/experiment_$(EXP).yaml --model $(MODEL) --endpoint $(ENDPOINT)

score:
	$(PYTHON) scripts/06_score.py --exp $(EXP_NAME)

report:
	$(PYTHON) scripts/07_report.py --exp $(EXP_NAME) --out results/tables results/figures

test:
	$(PYTEST) -q

lint:
	$(RUFF) check src scripts tests
