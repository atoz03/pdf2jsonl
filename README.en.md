# 🌾 pdf2jsonl

[简体中文](README.md) | **English**

![Cartoon rice plants, a sprouting PDF and a JSONL card: breeding papers become traceable data](docs/assets/readme-hero.en.svg)

A data contract and extraction toolkit for **breeding literature**. Turn papers into atomic JSONL records with
traceable evidence, explicit field definitions, and versioned validation rules, then derive a knowledge graph,
a corpus, QA seeds and relational tables from the same records.

<table>
<tr>
<td align="center" width="25%">
<a href="https://atoz03.github.io/pdf2jsonl/papers.html"><img src="docs/assets/icons/paper.svg" width="54" height="54" alt="Paper dashboard"><br><strong>Paper dashboard</strong></a><br><sub>Papers & run history</sub>
</td>
<td align="center" width="25%">
<a href="https://atoz03.github.io/pdf2jsonl/fields.html"><img src="docs/assets/icons/fields.svg" width="54" height="54" alt="Field guide"><br><strong>Field guide</strong></a><br><sub>Definitions & examples</sub>
</td>
<td align="center" width="25%">
<a href="https://atoz03.github.io/pdf2jsonl/pipeline.html"><img src="docs/assets/icons/pipeline.svg" width="54" height="54" alt="Pipeline map"><br><strong>Pipeline map</strong></a><br><sub>From PDF to records</sub>
</td>
<td align="center" width="25%">
<a href="#quick-start"><img src="docs/assets/icons/extract.svg" width="54" height="54" alt="Start extracting"><br><strong>Start extracting</strong></a><br><sub>Run your first paper</sub>
</td>
</tr>
</table>

> 🌱 The repository maintains the data contract; the Skill runs extraction; every record keeps its source.

## ✨ What it does

- **Extract papers into evidence-anchored records.** The `pdf2jsonl` Skill turns a paper (main text plus
  supplements) into atomic JSONL records. Every value carries its page and verbatim quote; a candidate that
  fails the checks is rejected with a reason, never written as a record.
- **Validate against a versioned contract.** Fields, vocabularies, profiles and cross-field rules are defined in
  one catalog and frozen as hash-verified releases; each record is validated against the version it declares.
- **Import existing data.** `bdc migrate` brings legacy, omics and merged datasets into the same records, with
  rejections and unconverted content reported instead of dropped.
- **Derive downstream views.** `bdc derive` builds relational tables, statements, triples and a property graph,
  the research workflow, an annotated corpus and QA seeds from the same records.
- **Grade relations by what supports them.** A relation carries its nature (causal, associational, …) and a claim
  strength that reads the evidence type; wording alone never upgrades an association into a cause.
- **Review on a clear ladder.** Deterministic checks, an independent verifier (`bdc verify`) and human decisions
  (`bdc review apply`) move `review_status` from `pending_review` to `expert_approved` or `rejected`.
- **Explore the results.** A static site shows the contract, the fields and every example run; a per-paper
  research view shows evidence chains, article packages and cross-paper confidence.

**Current versions:** data contract **3.8.0** · `bdc` tooling **1.1.0** · Skill runtime **0.6.0**.
What changed and when: [CHANGELOG](CHANGELOG.md) · [release history](docs/releases/README.md).

## 🧭 Extract once, consume many times

```
paper (PDF) ── pdf2jsonl ───┐                            ┌─► statements · triples · graph   (knowledge graph)
(main text + supplements)   ├─► records (JSONL, hooks) ──┼─► research workflow (question → hypothesis → step → result)
existing data ─ bdc migrate ┘        bdc derive          ├─► corpus with entity offsets
                                                         ├─► cloze QA seeds
                                                         └─► relational tables (CSV)
```

A record is the intermediate form every consumer shares, so no consumer parses the text a second time. **The
model copies** the verbatim subject, predicate and object of a statement; **the pipeline computes** entity
types, offsets, roles and a relation code from a cue lexicon; **reviewers and later stages add** the reviewed
predicate, entity alignment and QA in fields of their own. Where a record has no hook, the derived output has
no row: nothing is guessed. Design notes: [`docs/downstream.md`](docs/downstream.md).

[![Breeding literature pipeline: versioned contract, PDF extraction, evidence checks, structured-data imports, JSONL outputs and derived views](docs/diagrams/pipeline.en.svg)](docs/diagrams/pipeline.en.svg)

[HTML source](docs/diagrams/pipeline.html) · [Full-size SVG](docs/diagrams/pipeline.en.svg) · [Architecture](docs/architecture.md)

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

Outputs: `paper.jsonl` (records), `paper.validation.json` (validation report, with the evidence-chain audit,
workflow structure and source completeness), `paper.errors.jsonl` (rejected candidates, never written as
records) and `paper.manifest.json` (contract identity, input hash, backend, environment, output hashes);
`--bundle` adds `paper.bundle.json`. Other backends: `--candidates file.json`, `--backend mock`,
`--backend module:callable`.

A paper in several files is one run: add `--supplement paper_supplement.pdf` (repeatable); an appendix is
labelled with `--supplement appendix.pdf:appendix`. Evidence then names its part, and each file gets its own
asset record.

To make the Skill available to Claude Code in this repository, `.claude/skills/pdf2jsonl` links to
`skills/pdf2jsonl`; for a user-level install, symlink `~/.claude/skills/pdf2jsonl` to the same directory.

### Python API

```python
from breeding_contract import resolve_schema, load_profile, load_field_catalog, validate_record

rc = resolve_schema("latest")                  # or "3.0.0", or "dev" (unreleased working tree)
profile = load_profile("pdf_extraction", "latest")
catalog = load_field_catalog("3.8.0")
result = validate_record(record)               # validates against the version the record declares
result.valid, [i.to_dict() for i in result.errors]
```

## 🔁 Core workflows

<a id="import"></a>

### Import existing data

Data that already exists in another shape enters the same contract through an importer, not through a second
schema. Each importer follows a leaf-by-leaf mapping (`mappings/`), produces the same atomic records as
extraction and is validated the same way.

| Command | Input | Example |
| --- | --- | --- |
| `bdc migrate legacy` | Document-level JSONL, one paper per line | `sources/legacy_v1/breeding_jsonl_example.jsonl` |
| `bdc migrate omics` | Filled instances of the multi-omics metadata template | `examples/migration/omics_v2/synthetic_deg_instance.json` |
| `bdc migrate merged` | Documents with observation, sample, assay and asset arrays joined by explicit IDs | `sources/merged_v2/breeding_jsonl_example_v2.json` |

```bash
bdc migrate merged sources/merged_v2/breeding_jsonl_example_v2.json --out out/merged --page-offset 2220
```

`--page-offset` converts journal pages to physical PDF pages (`2220` applies only to this example; `0` means the
pages are already physical). Imported records start as `pending_review`. See [`docs/migration.md`](docs/migration.md)
and [`docs/source_analysis.md`](docs/source_analysis.md).

### Derive, verify and review

```bash
bdc derive out/paper.jsonl --out derived/                       # tables, triples, graph, workflow, corpus, QA
bdc verify tasks out/paper.jsonl --out review/                  # tasks for an independent verifier
bdc verify apply out/paper.jsonl review/paper.verify.verdicts.json --out review/
bdc review apply out/paper.jsonl decisions.json --out out/reviewed   # human decisions
```

Verification and review move only the review fields, never the content. See [`docs/review.md`](docs/review.md)
and [`docs/workflow.md`](docs/workflow.md).

### Browse the results

The [site](https://atoz03.github.io/pdf2jsonl/) is built by `scripts/make_site.py` from the latest release and
the checked-in examples and deployed from `main`: the pipeline, a walk-through of a synthetic paper, derived
outputs, the paper dashboard, the importers, all fields and the contract with its release history. Preview it
with `make site` and open `_site/index.html`.

`make dashboard` writes `dashboard.html`, the **research view**: per paper, only the phenotype–gene–population
relations with their complete evidence chains and the article package, plus a full-network toggle with
cross-paper deduplication and A/B/C confidence. Its 人工复核 (N) panel exports review decisions for
`bdc review apply`. `make dashboard-full` writes the full paper dashboard; `make network-demo` runs a four-paper
demo. See [`docs/research_view.md`](docs/research_view.md).

### Change the contract

Edit the catalog, bump `VERSION`, add a `CHANGELOG.md` entry, then:

```bash
bdc generate && bdc release && bdc check --strict && pytest
```

The full checklist is in [`docs/versioning.md`](docs/versioning.md#changing-the-contract). The Skill needs no
edit: its next run resolves `latest`.

## 🛠 `bdc` CLI

| Command | Purpose |
| --- | --- |
| `bdc check [--strict]` | Consistency gate: catalog, profiles, releases, freshness, docs, examples, mappings, Skill |
| `bdc generate [--xlsx F]` | Rebuild `docs/generated/` from the catalog and documentation examples |
| `bdc release` | Freeze the working tree as `releases/<VERSION>` (needs a CHANGELOG entry) |
| `bdc resolve [--schema-version V] [--profile P]` | Print a version's identity (default `latest`) |
| `bdc validate FILE.jsonl` | Validate records (each against its declared version) plus dataset rules |
| `bdc diff A B` | Field-level diff between two versions |
| `bdc migrate legacy\|omics\|merged F --out DIR [--page-offset N]` | Import existing data as atomic records, see [Import existing data](#import) |
| `bdc bundle F.jsonl [--legacy-v1]` | Derive the per-document view (or the legacy v1 layout) from records |
| `bdc derive F.jsonl --out DIR` | Relational tables (CSV), statements, triples and a property graph, the research workflow, an annotated corpus and QA seeds, with their lineage |
| `bdc audit F.jsonl [--json]` | Evidence-chain audit (Toulmin/Flavell elements, link closure, review flags; no score) and workflow structure |
| `bdc verify tasks\|apply F.jsonl [VERDICTS] --out DIR` | Semantic verification by an independent verifier: build the tasks, then apply its verdicts to the review fields |
| `bdc review apply F.jsonl DECISIONS --out DIR` | Apply human/expert decisions (approve / reject / return for evidence); only `review_status` and `review_note` move |

`make help` lists the Makefile targets.

## 🔬 Contract at a glance (3.8.0)

- 422 fields in five groups (`common`, `agent`, `skills`, `transform`, `omics`). The 259 v3.0.0 fields are
  `verified` and verbatim; fields added since are `provisional`.
- Records are nested: the field `common.record_id` is `{"common": {"record_id": ...}}`.
- Missing information is **omitted**: no `null`, no empty string, no empty array or object.
- Every record carries `common.schema_name` and `common.schema_version`, a stable `common.record_id`
  (`rec_` + 32 hex), provenance (`source_id`, `source_locator`, page and verbatim quote for paper evidence),
  and a `review_status`.
- Availability codes are semantics, not quality: **D** direct extraction, **N** normalized by rules,
  **I** human judgement, **G** generated later, **F** future source.
- Every key states its role (`key_role`) and the functions it serves (`serves`); see
  [`docs/field_functions.md`](docs/field_functions.md).
- Open questions are registered as ambiguities (`AMB-…`) in the catalog instead of being silently decided.

Field reference: the [online field catalog](https://atoz03.github.io/pdf2jsonl/fields.html),
[field definitions and examples](docs/generated/field_definitions.md), the
[detailed dictionary](docs/generated/field_dictionary.md) ([CSV](docs/generated/field_dictionary.csv);
`bdc generate --xlsx out.xlsx` for Excel) and [field functions](docs/generated/field_functions.md).

## 📚 Inside the repository

| Path | What it is |
| --- | --- |
| `field_catalog/field_catalog.yaml` | **Canonical catalog**: every field, type, availability code, rule and ambiguity |
| `vocabularies/`, `profiles/` | Controlled vocabularies (and the unit table); field selections per use case |
| `releases/` | Frozen, hash-verified contract versions and `index.json` (`latest` pointer) |
| `schemas/` | JSON Schemas for the source files (`meta/`) and for run outputs (`runtime/`) |
| `mappings/`, `sources/` | Importer mappings with issue registers; immutable original inputs ([`sources/SOURCES.md`](sources/SOURCES.md)) |
| `src/breeding_contract/` | Contract tooling and the `bdc` CLI |
| `skills/pdf2jsonl/` | The Skill: `SKILL.md`, extraction brief template, runtime (`scripts/pdf2jsonl`) |
| `scripts/`, `site/` | Site, dashboard, diagram and example generators; page templates |
| `examples/` | Synthetic papers, curated records, pipeline output, verification, derived views, importer output, invalid cases |
| `docs/`, `tests/` | Guides and generated reference; the pytest suite |

## 🗂 Documentation

- [**Documentation map**](docs/README.md): every guide and reference file, and where new writing belongs.
- Guides: [architecture](docs/architecture.md) · [versioning](docs/versioning.md) ·
  [downstream outputs](docs/downstream.md) · [research workflow](docs/workflow.md) · [quality and review](docs/review.md) ·
  [importers](docs/migration.md) · [field functions](docs/field_functions.md) · [source analysis](docs/source_analysis.md) ·
  [relation semantics](docs/relation_semantics.md) (zh) · [research view](docs/research_view.md) (zh)
- History: [CHANGELOG](CHANGELOG.md) for what each release changed; [release history](docs/releases/README.md)
  for dates, long-form notes and text retired from this README.

This README describes the project as it is now. Per-version detail goes in the CHANGELOG, design detail in
`docs/` (see [where things go](docs/README.md#where-things-go)).
