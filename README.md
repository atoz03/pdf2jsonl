# breeding-data-contract

The single source of truth for the **breeding-literature JSONL data contract**: field definitions, schema
constraints, vocabularies, versioning, validation, and the `pdf2jsonl` Skill that turns papers into
contract-conformant atomic records.

> The repository owns the data contract; the Skill is the operational entry point.

```
field_catalog/field_catalog.yaml  ─┐
vocabularies/*.yaml               ─┼─ bdc release ──► releases/<X.Y.Z>/ (immutable) ──► resolve_schema("latest")
profiles/*.yaml                   ─┘                   contract.json, record.schema.json,        │
                                                       profiles/*.json|*.schema.json             ▼
                                                                             skills/pdf2jsonl (brief, repair,
                                                                             validation, outputs)
```

**Live demo:** https://atoz03.github.io/pdf2jsonl/ — field catalog browser with key roles and functions, PDF → JSONL
walk-through with the evidence-chain audit, record examples, vocabularies and rules, generated from the latest release
by `scripts/make_site.py`.

## Contents

| Path | What it is |
| --- | --- |
| `field_catalog/field_catalog.yaml` | **Canonical catalog**: every field, type, availability code, rule and ambiguity |
| `vocabularies/` | Controlled vocabularies and the deterministic unit table |
| `profiles/` | Field selections for one use case (`full`, `compact`, `pdf_extraction`, `pdf_extraction_omics`) |
| `releases/` | Frozen, hash-verified contract versions and `index.json` (`latest` pointer) |
| `schemas/meta/` | JSON Schemas for the source files themselves (catalog, vocabulary, profile, mapping) |
| `schemas/runtime/` | JSON Schemas for run outputs (manifest, validation report, error records, bundle, migration report) |
| `mappings/` | Legacy v1 and omics v2 → current contract mappings, with issue registers |
| `sources/` | Immutable original inputs (see `sources/SOURCES.md`) |
| `src/breeding_contract/` | Contract tooling: compile, release, resolve, validate, migrate, bundle, derive, audit (`bdc` CLI) |
| `skills/pdf2jsonl/` | The Skill: `SKILL.md`, extraction brief template, runtime (`scripts/pdf2jsonl`) |
| `docs/` | Architecture, versioning, source analysis, migration, key roles and functions; `docs/generated/` is built from the catalog |
| `examples/` | Synthetic paper, curated records, pipeline output, migration output, invalid cases |
| `tests/` | pytest suite (catalog fidelity, releases, validation, pipeline, Skill sync, migrations, bundles, functions and evidence chain) |

## Contract at a glance (3.2.0)

- 397 fields in five groups: `common` 174, `agent` 57, `skills` 53, `transform` 45, `omics` 68.
  The 259 v3.0.0 fields are `verified` and verbatim; the 138 fields added in 3.1.0 and 3.2.0 are `provisional`.
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
- 36 ambiguities are registered in the catalog (`AMB-001` … `AMB-036`) instead of being silently decided.

See `docs/generated/field_dictionary.md` (also `.csv`; `bdc generate --xlsx out.xlsx` for Excel) and
`docs/generated/field_functions.md` (every key by function, with its role and facets).

## Quick start

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e '.[dev]'   # or: pip install -e '.[dev]'
make check        # bdc check --strict
make test         # pytest
```

### Extract a paper (agent mode: Claude is the extraction model)

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
catalog = load_field_catalog("3.2.0")
result = validate_record(record)               # validates against the version the record declares
result.valid, [i.to_dict() for i in result.errors]
```

### `bdc` CLI

| Command | Purpose |
| --- | --- |
| `bdc check [--strict]` | Consistency gate: catalog, profiles, releases, freshness, docs, examples, mappings, Skill |
| `bdc generate [--xlsx F]` | Rebuild `docs/generated/` from the catalog |
| `bdc release` | Freeze the working tree as `releases/<VERSION>` (needs a CHANGELOG entry) |
| `bdc resolve [--schema-version V] [--profile P]` | Print a version's identity (default `latest`) |
| `bdc validate FILE.jsonl` | Validate records (each against its declared version) plus dataset rules |
| `bdc diff A B` | Field-level diff between two versions |
| `bdc migrate legacy F --out DIR --page-offset N` / `bdc migrate omics F --out DIR` | Convert legacy v1 documents / omics template instances |
| `bdc bundle F.jsonl [--legacy-v1]` | Derive the per-document view (or the legacy v1 layout) from records |
| `bdc derive F.jsonl --out DIR` | Function 3: relational tables (CSV), knowledge-graph triples and an evidence corpus, driven by `key_role` |
| `bdc audit F.jsonl [--json]` | Evidence-chain audit (Toulmin/Flavell elements, link closure, review flags; no score) |

## Changing the contract

1. Edit `field_catalog/field_catalog.yaml` (and vocabularies/profiles). Keep source references; mark new
   semantics `provisional` and register open questions as ambiguities.
2. Bump `VERSION` per `docs/versioning.md` and add a `CHANGELOG.md` entry.
3. `bdc generate && bdc release && bdc check --strict && pytest`.
4. The Skill needs no edit: its next run resolves `latest` and renders the brief from the new release.
   `bdc check` fails if the Skill hard-codes field paths or versions, or if a profile needs a fill rule the
   Skill does not implement.

## Documentation

- `docs/architecture.md` — components, data flow, pipeline stages, invariants
- `docs/versioning.md` — semantic versioning of the contract, releases, `latest`/`dev`, compatibility
- `docs/source_analysis.md` — the three source designs, their inconsistencies and the merge decisions
- `docs/migration.md` — legacy v1 / omics v2 migration and the derived views (`document_bundle`, `bdc derive`)
- `docs/field_functions.md` — what every key is for: roles, the four functions, cards, the evidence chain (TRACE),
  derived views and the audit
