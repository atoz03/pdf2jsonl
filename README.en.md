# 🌾 pdf2jsonl

[简体中文](README.md) | **English**

![Cartoon rice plants, a sprouting PDF and a JSONL card: breeding papers become traceable data](docs/assets/readme-hero.en.svg)

A data contract and extraction toolkit for **breeding literature**. Turn papers into atomic JSONL records with
traceable evidence, explicit field definitions, and versioned validation rules.

<table>
<tr>
<td align="center" width="25%">
<a href="dashboard.html"><img src="docs/assets/icons/paper.svg" width="54" height="54" alt="Paper dashboard"><br><strong>Paper dashboard</strong></a><br><sub>Papers & run history</sub>
</td>
<td align="center" width="25%">
<a href="FIELD_DEFINITIONS.md"><img src="docs/assets/icons/fields.svg" width="54" height="54" alt="Field guide"><br><strong>Field guide</strong></a><br><sub>Definitions & examples</sub>
</td>
<td align="center" width="25%">
<a href="docs/diagrams/pipeline.html"><img src="docs/assets/icons/pipeline.svg" width="54" height="54" alt="Pipeline map"><br><strong>Pipeline map</strong></a><br><sub>From PDF to records</sub>
</td>
<td align="center" width="25%">
<a href="#quick-start"><img src="docs/assets/icons/extract.svg" width="54" height="54" alt="Start extracting"><br><strong>Start extracting</strong></a><br><sub>Run your first paper</sub>
</td>
</tr>
</table>

> 🌱 The repository maintains the data contract; the Skill runs extraction; every record keeps its source.

**Paper dashboard:** open the root-level [dashboard.html](dashboard.html) in a local browser to inspect PDF evidence,
records, review issues and exports. Run `make dashboard` to collect new papers and runs. The dashboard UI is in Chinese.

**Field guide:** [FIELD_DEFINITIONS.md](FIELD_DEFINITIONS.md) covers all **400 fields**, with meanings,
multi-select function tags, types, JSON examples and filling requirements.

## 🧬 Data pipeline overview

[![Breeding literature pipeline: versioned contract, PDF extraction, evidence checks, structured-data imports, JSONL outputs and derived views](docs/diagrams/pipeline.en.svg)](docs/diagrams/pipeline.en.svg)

[HTML source](docs/diagrams/pipeline.html) · [Full-size SVG](docs/diagrams/pipeline.en.svg) · [Architecture](docs/architecture.md)

The diagram covers PDF extraction, legacy/omics/merged imports, rejection and manual review paths, and exports to
relational tables, graph triples, evidence corpora and document bundles. Open the HTML locally to switch languages
or download SVG. Run `make diagram` to regenerate both README images after editing the source.

**Live demo:** https://atoz03.github.io/pdf2jsonl/ — field catalog browser with key roles and functions, PDF → JSONL
walk-through with the evidence-chain audit, record examples, vocabularies and rules, generated from the latest release
by `scripts/make_site.py`.

## 📚 Inside the repository

| Path | What it is |
| --- | --- |
| [`dashboard.html`](dashboard.html) | **Paper dashboard**: search papers, inspect evidence and records, review issues, switch runs and download outputs |
| [`FIELD_DEFINITIONS.md`](FIELD_DEFINITIONS.md) | **Start here**: every field's meaning, type, JSON example, and filling requirements |
| `field_catalog/field_catalog.yaml` | **Canonical catalog**: every field, type, availability code, rule and ambiguity |
| `vocabularies/` | Controlled vocabularies and the deterministic unit table |
| `profiles/` | Field selections for one use case (`full`, `compact`, `pdf_extraction`, `pdf_extraction_omics`) |
| `releases/` | Frozen, hash-verified contract versions and `index.json` (`latest` pointer) |
| `schemas/meta/` | JSON Schemas for the source files themselves (catalog, vocabulary, profile, mapping) |
| `schemas/runtime/` | JSON Schemas for run outputs (manifest, validation report, error records, bundle, migration report) |
| `mappings/` | Legacy v1, omics v2 and merged v2 → current contract mappings, with issue registers |
| `sources/` | Immutable original inputs (see `sources/SOURCES.md`) |
| `src/breeding_contract/` | Contract tooling: compile, release, resolve, validate, migrate, bundle, derive, audit (`bdc` CLI) |
| `skills/pdf2jsonl/` | The Skill: `SKILL.md`, extraction brief template, runtime (`scripts/pdf2jsonl`) |
| `docs/` | Architecture, versioning, source analysis, migration, key roles and functions; `docs/generated/` is built from the catalog |
| `docs/field_examples.yaml` | Curated illustrative values used to generate and validate the field reference |
| `docs/field_classification.yaml` | Per-field multi-select tags: Research Content 1, Research Content 2, future iteration, and general-purpose fields |
| `scripts/make_dashboard.py` / `site/dashboard.template.html` | Paper index builder and dashboard template; scans PDFs, manifests and prepared extraction tasks |
| `examples/` | Synthetic paper, curated records, pipeline output, migration output, invalid cases |
| `tests/` | pytest suite (catalog fidelity, releases, validation, pipeline, Skill sync, migrations, bundles, functions and evidence chain) |

## 🔬 Contract at a glance (3.3.0)

- 400 fields in five groups: `common` 177, `agent` 57, `skills` 53, `transform` 45, `omics` 68.
  The 259 v3.0.0 fields are `verified` and verbatim; the 141 fields added in 3.1.0–3.3.0 are `provisional`.
- **Multi-select functional tags**: Research Content 1, Research Content 2, future iteration, and general-purpose fields.
- Every key states **what it does** (`key_role`, 25 roles with their projection into graph, tables, triples and
  QA/corpora) and **which function it serves** (`serves`): Topic 2 agent, Topic 3 skills, derivation into
  KG / relational DB / QA / corpus / triples, and our own iteration (Topic 1). Topic 2/3 fields also name their
  card, and evidence-chain fields their Toulmin/Flavell element (after TRACE). Functions stated by the source
  are kept apart from repository additions. See `docs/field_functions.md`.
- Nested records: the field `common.record_id` is `{"common": {"record_id": ...}}`.
- Availability codes are semantics, not quality: **D** direct extraction, **N** normalized by rules,
  **I** human judgement, **G** generated later, **F** future source. Requirement codes **Y / C / N**.
- Missing information is **omitted**: no `null`, no empty string, no empty array or object.
- Every record carries `common.schema_name` and `common.schema_version`, a stable `common.record_id`
  (`rec_` + 32 hex), provenance (`source_id`, `source_locator`, page and verbatim quote for paper evidence),
  and a `review_status`.
- 32 cross-field rules (20 errors, 12 warnings): explicit source statements are errors, inferred ones are warnings only.
- 37 ambiguities are registered in the catalog (`AMB-001` … `AMB-037`) instead of being silently decided.

See [field definitions and examples](FIELD_DEFINITIONS.md), the
[detailed dictionary](docs/generated/field_dictionary.md) (also [CSV](docs/generated/field_dictionary.csv);
`bdc generate --xlsx out.xlsx` for Excel), and
[field functions](docs/generated/field_functions.md) (every key by function, with its role and facets).

<a id="quick-start"></a>

## 🌱 Quick start

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e '.[dev]'   # or: pip install -e '.[dev]'
make check        # bdc check --strict
make test         # pytest
```

### 🧪 Extract a paper (agent mode)

```bash
skills/pdf2jsonl/scripts/pdf2jsonl paper.pdf --profile pdf_extraction --schema-version latest --out-dir out/
# exit 3: out/paper.work/ holds brief.md, pages.txt, candidate.schema.json, request.json
# write out/paper.work/candidates.json following brief.md, then run the same command again:
skills/pdf2jsonl/scripts/pdf2jsonl paper.pdf --profile pdf_extraction --schema-version latest --out-dir out/
```

Outputs: `paper.jsonl` (records), `paper.validation.json`, `paper.errors.jsonl` (rejected candidates, never
written as records), `paper.manifest.json` (contract identity, input hash, backend, environment, output hashes);
`--bundle` adds `paper.bundle.json`. The validation report includes `argument_structure`, the evidence-chain audit
(which statements are linked to data and methods, and which hedges or links are missing). Other backends: `--candidates file.json`, `--backend mock`,
`--backend module:callable`.

To make the Skill available to Claude Code in this repository, `.claude/skills/pdf2jsonl` links to
`skills/pdf2jsonl`; for a user-level install, symlink `~/.claude/skills/pdf2jsonl` to the same directory.

### Python API

```python
from breeding_contract import resolve_schema, load_profile, load_field_catalog, validate_record

rc = resolve_schema("latest")                  # or "3.0.0", or "dev" (unreleased working tree)
profile = load_profile("pdf_extraction", "latest")
catalog = load_field_catalog("3.3.0")
result = validate_record(record)               # validates against the version the record declares
result.valid, [i.to_dict() for i in result.errors]
```

### `bdc` CLI

| Command | Purpose |
| --- | --- |
| `bdc check [--strict]` | Consistency gate: catalog, profiles, releases, freshness, docs, examples, mappings, Skill |
| `bdc generate [--xlsx F]` | Rebuild `FIELD_DEFINITIONS.md` and `docs/generated/` from the catalog and documentation examples |
| `bdc release` | Freeze the working tree as `releases/<VERSION>` (needs a CHANGELOG entry) |
| `bdc resolve [--schema-version V] [--profile P]` | Print a version's identity (default `latest`) |
| `bdc validate FILE.jsonl` | Validate records (each against its declared version) plus dataset rules |
| `bdc diff A B` | Field-level diff between two versions |
| `bdc migrate legacy F --out DIR --page-offset N` / `bdc migrate omics F --out DIR` | Convert legacy v1 documents / omics template instances |
| `bdc bundle F.jsonl [--legacy-v1]` | Derive the per-document view (or the legacy v1 layout) from records |
| `bdc derive F.jsonl --out DIR` | Function 3: relational tables (CSV), knowledge-graph triples and an evidence corpus, driven by `key_role` |
| `bdc audit F.jsonl [--json]` | Evidence-chain audit (Toulmin/Flavell elements, link closure, review flags; no score) |

## 🌿 Evolving the contract

1. Edit `field_catalog/field_catalog.yaml` (and vocabularies/profiles). Keep source references; mark new
   semantics `provisional` and register open questions as ambiguities.
2. Bump `VERSION` per `docs/versioning.md` and add a `CHANGELOG.md` entry.
3. Add or update illustrative values in `docs/field_examples.yaml` and functional tags in `docs/field_classification.yaml`; contract name and version examples are generated automatically.
4. `bdc generate && bdc release && bdc check --strict && pytest`. Generation checks that every field has an example and that examples match field schemas.
5. The Skill needs no edit: its next run resolves `latest` and renders the brief from the new release.
   `bdc check` fails if the Skill hard-codes field paths or versions, or if a profile needs a fill rule the
   Skill does not implement.

## 🌾 Import merged v2 data

The merged archive adds sample replicate metadata and observation/asset import support; see the
[integration review](docs/merged_v2_review.md) (Chinese).

```bash
bdc migrate merged sources/merged_v2/breeding_jsonl_example_v2.json --out out/merged --page-offset 2220
```

Offset `2220` applies only to this example. Supply the actual source-page offset for other data,
or `0` for physical PDF pages. Outputs include valid records, rejected candidates, unconverted
source content and a traceable migration report.

## 🗂 Documentation

- [Field definitions and JSON examples](FIELD_DEFINITIONS.md) — root-level reference for all fields
- `docs/architecture.md` — components, data flow, pipeline stages, invariants
- `docs/versioning.md` — semantic versioning of the contract, releases, `latest`/`dev`, compatibility
- `docs/source_analysis.md` — the three source designs, their inconsistencies and the merge decisions
- `docs/migration.md` — legacy v1 / omics v2 migration and the derived views (`document_bundle`, `bdc derive`)
- `docs/field_functions.md` — what every key is for: roles, the four functions, cards, the evidence chain (TRACE),
  derived views and the audit
