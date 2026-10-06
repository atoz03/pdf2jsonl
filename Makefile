PY      ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
BDC     := PYTHONPATH=src $(PY) -m breeding_contract.cli

.PHONY: help venv check test generate diagram site dashboard readme-art release examples sample-pdf all

help:
	@echo "make venv       create .venv with dev dependencies (uv, else venv+pip)"
	@echo "make check      bdc check --strict (CI gate)"
	@echo "make test       pytest"
	@echo "make generate   rebuild docs/generated from the catalog"
	@echo "make diagram    export Chinese/English pipeline SVGs from the HTML diagram"
	@echo "make site       build the Pages site into _site/ (contract browser, papers, pipeline, downstream outputs)"
	@echo "make dashboard  write an untracked dashboard.html that also covers local run directories"
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
	$(PY) scripts/make_dashboard.py

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
