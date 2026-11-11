PY      ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
BDC     := PYTHONPATH=src $(PY) -m breeding_contract.cli

.PHONY: help venv check test acceptance generate diagram site dashboard dashboard-full network-demo rbl1 rbl1-aggregate rice-panel dashboard-rbl1 dashboard-panel reproduce readme-art release examples sample-pdf all

help:
	@echo "make venv       create .venv with dev dependencies (uv, else venv+pip)"
	@echo "make check      bdc check --strict (CI gate)"
	@echo "make test       pytest"
	@echo "make acceptance regenerate docs/acceptance_3.8.0.md, failing when a criterion does"
	@echo "make generate   rebuild docs/generated from the catalog"
	@echo "make diagram    export Chinese/English pipeline SVGs from the HTML diagram"
	@echo "make site       build the eight-page Pages site into _site/ (overview, pipeline, walk-through, outputs, papers, importers, fields, contract)"
	@echo "make dashboard  write the simplified phenotype-gene-population dashboard.html"
	@echo "make dashboard-full  write the full paper dashboard.html (all records and tabs)"
	@echo "make network-demo  run the four-paper demo and rebuild dashboard.html"
	@echo "make rbl1       build the RBL1 association/sequence case (PDF=path/to/qt2321j386.pdf)"
	@echo "make rbl1-aggregate  add synthetic replication/conflict papers for the aggregate demo"
	@echo "make rice-panel  build the 13-paper rice stress panel (RICE_PDF_DIR=...)"
	@echo "make dashboard-rbl1  render dashboard.html from the RBL1 case (with aggregate when built)"
	@echo "make dashboard-panel render dashboard.html from the real rice stress panel"
	@echo "make reproduce  one-command full reproduction (RBL1_PDF=... RICE_PDF_DIR=...)"
	@echo "make readme-art regenerate the breeding-themed README banner and icons"
	@echo "make release    freeze VERSION as releases/<VERSION> (needs a CHANGELOG entry)"
	@echo "make examples   regenerate examples/ (records, pipeline output, migrations)"

venv:
	@if command -v uv >/dev/null; then uv venv .venv && uv pip install --python .venv/bin/python -e '.[dev]'; \
	else python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'; fi

check:
	$(BDC) check --strict
	$(PY) scripts/export_pipeline_diagram.py --check
	$(PY) scripts/make_readme_art.py --check

test:
	$(PY) -m pytest

generate:
	$(BDC) generate

diagram:
	$(PY) scripts/export_pipeline_diagram.py

site:
	PYTHONPATH=src $(PY) scripts/make_site.py --out _site

dashboard:
	$(PY) scripts/make_network_dashboard.py

dashboard-full:
	$(PY) scripts/make_dashboard.py

network-demo:
	$(PY) scripts/make_network_demo.py

rbl1:
	PYTHONPATH=src $(PY) -m breeding_contract.cli rbl1 --pdf $(PDF) --primers examples/rbl1/primers.csv --out out/rbl1_case_final

rbl1-aggregate:
	$(PY) scripts/make_rbl1_aggregate_demo.py --case-dir out/rbl1_case_final --out out/rbl1_multi

RICE_PDF_DIR ?=
RBL1_PDF ?=
rice-panel:
	$(PY) scripts/build_rice_stress_panel.py --panel-csv examples/rice_stress_panel/panel.csv \
		$(if $(RICE_PDF_DIR),--pdf-dir "$(RICE_PDF_DIR)",) --case-dir out/rbl1_case_final --out out/rice_stress_panel

dashboard-rbl1:
	$(PY) scripts/make_network_dashboard.py --rbl1-case out/rbl1_case_final \
		--rbl1-aggregate out/rbl1_multi/records.jsonl --out dashboard.html

dashboard-panel: rice-panel
	$(PY) scripts/make_network_dashboard.py --rbl1-case out/rbl1_case_final \
		--rbl1-aggregate out/rice_stress_panel/records.jsonl --out dashboard.html

reproduce:
	@test -n "$(RBL1_PDF)" || (echo "set RBL1_PDF=/path/to/qt2321j386.pdf"; exit 1)
	@test -n "$(RICE_PDF_DIR)" || (echo "set RICE_PDF_DIR=/path/to/水稻-抗逆抗病性状"; exit 1)
	$(PY) scripts/reproduce_dashboard.py --rbl1-pdf "$(RBL1_PDF)" \
		--rice-pdf-dir "$(RICE_PDF_DIR)" --out out/reproduce

readme-art:
	$(PY) scripts/make_readme_art.py

release: generate
	$(BDC) release
	$(BDC) check --strict

examples:
	PYTHONPATH=src $(PY) scripts/make_examples.py

sample-pdf:
	$(PY) scripts/make_sample_pdf.py examples/papers/synthetic_rice_qtl.txt examples/papers/synthetic_rice_qtl.pdf

all: generate check test

acceptance:
	$(PY) scripts/acceptance_report.py --check
