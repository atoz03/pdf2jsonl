PY      ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
BDC     := PYTHONPATH=src $(PY) -m breeding_contract.cli

.PHONY: help venv check test generate release examples sample-pdf all

help:
	@echo "make venv       create .venv with dev dependencies (uv, else venv+pip)"
	@echo "make check      bdc check --strict (CI gate)"
	@echo "make test       pytest"
	@echo "make generate   rebuild docs/generated from the catalog"
	@echo "make release    freeze VERSION as releases/<VERSION> (needs a CHANGELOG entry)"
	@echo "make examples   regenerate examples/ (records, pipeline output, migrations)"

venv:
	@if command -v uv >/dev/null; then uv venv .venv && uv pip install --python .venv/bin/python -e '.[dev]'; \
	else python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'; fi

check:
	$(BDC) check --strict

test:
	$(PY) -m pytest

generate:
	$(BDC) generate

release: generate
	$(BDC) release
	$(BDC) check --strict

examples:
	PYTHONPATH=src $(PY) scripts/make_examples.py

sample-pdf:
	$(PY) scripts/make_sample_pdf.py examples/papers/synthetic_rice_qtl.txt examples/papers/synthetic_rice_qtl.pdf

all: generate check test
