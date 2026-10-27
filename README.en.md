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

**Everything is shown in one site:** [https://atoz03.github.io/pdf2jsonl](https://atoz03.github.io/pdf2jsonl/), built by `scripts/make_site.py` from the
latest release and the checked-in examples, and deployed from `main`.

| Page | What it shows |
| --- | --- |
| [Home](https://atoz03.github.io/pdf2jsonl/) | How a paper becomes traceable data: the whole project, its four kinds of downstream use, a tour of the site |
| [Pipeline](https://atoz03.github.io/pdf2jsonl/pipeline.html) | Every stage from contract, extraction, checks, assembly and validation to verification, derivation and review; how each candidate of the example paper fares; the poster (SVG, Chinese and English) |
| [Walk-through](https://atoz03.github.io/pdf2jsonl/demo.html) | The synthetic paper end to end: candidates, evidence checks, repairs, a rejection, the evidence-chain audit |
| [Outputs](https://atoz03.github.io/pdf2jsonl/outputs.html) | Statements, knowledge graph, research workflow, annotated corpus, QA seeds and tables derived from the same records |
| [Papers](https://atoz03.github.io/pdf2jsonl/papers.html) | Paper dashboard: the PDF, the records of each run, their evidence on the page, verification, review issues, downloads |
| [Importers](https://atoz03.github.io/pdf2jsonl/importers.html) | The legacy, omics and merged importers: mapping coverage, example runs, issue registers |
| [Fields](https://atoz03.github.io/pdf2jsonl/fields.html) | All **421 fields**: meaning, type, JSON example, key role, functions, multi-select tags, origin |
| [Contract](https://atoz03.github.io/pdf2jsonl/contract.html) | Record kinds, profiles, vocabularies, rules, the ambiguity register and the release history; records from every source (curated, pdf2jsonl, the three importers) side by side |

Preview locally with `make site` and open `_site/index.html`. `make dashboard` also writes an untracked
`dashboard.html` that includes papers and runs from local directories such as `out/`.

## 🧭 Extract once, consume many times

```
paper (PDF) ── pdf2jsonl ───┐                            ┌─► statements · triples · graph   (knowledge graph)
(main text + supplements)   ├─► records (JSONL, hooks) ──┼─► research workflow (question → hypothesis → step → result)
existing data ─ bdc migrate ┘        bdc derive          ├─► corpus with entity offsets
                                                         ├─► cloze QA seeds
                                                         └─► relational tables (CSV)
```

A record is not a container for extraction results; it is the intermediate form every consumer shares. A
knowledge graph needs triples, so a record has an explicit subject, predicate and object. A corpus and a QA set
need to know where an entity stands in the text, so a record has the character offsets of every entity mention
and its role in the relation. No consumer parses the text a second time:

- **The model copies**: the three verbatim parts of a statement (`transform.subject_mention`,
  `predicate_mention`, `object_mention`).
- **The pipeline computes**: entity types, the offsets of entities and predicate in the quote, subject/object
  roles (`transform.entity_links`, `predicate_start_offset` / `predicate_end_offset`), and a relation code derived
  deterministically from a cue lexicon (`predicate_code`).
- **Reviewers and later stages add**: the reviewed predicate, entity alignment, natural-language QA. Each has
  its own field and is never mixed with extraction output.

Where a record has no hook, the derived output has no row: nothing is guessed. Design notes:
[`docs/downstream.md`](docs/downstream.md).

3.6.0 records the semantic nature of a relation; both additions are provisional:

- **Every predicate code carries a nature**: `causal` / `associational` / `structural` / `descriptive`, mapped at
  compile time to `transform.relation_nature` (N, derived from the contract, never judged by the model), while
  `transform.relation_assertion_mode` (D) keeps the source's own wording. Only a causal relation can directly
  guide an experiment, so R036 / R037 flag a flat association with no evidence and a causal relation with no
  evidence type. See [`docs/relation_semantics.md`](docs/relation_semantics.md).
- **The derived views and the dashboard carry it**: `bdc derive` statements, triples and graph edges include
  `relation_nature` and `relation_assertion_mode` (`derive_format` = 4), and the paper dashboard gained a 关系 tab
  that lists every statement with its nature and filters by it.

3.8.0 makes "what makes a conclusion hold" a field (provisional):

- **A causal wording is no longer decided by the verb alone**: `transform.claim_strength` reads the predicate's
  nature together with the relation evidence type — `causal_supported` (functional validation, genetic
  interaction, biochemical assay, localization imaging, pharmacological perturbation),
  `causal_expression_supported`, `causal_statistical_only`, `causal_unverified`; R038 asks for a validation
  method when a causal claim has statistical evidence only. Evidence never upgrades an association, and missing
  evidence never downgrades the wording.
- **The four relation classes the trial needed**: `qtn_associated_with_trait`, `gene_suppresses_gene` /
  `gene_suppressed_by_gene` (active and passive kept apart), `gene_upstream_of_gene`,
  `trait_controlled_by_gene`, `locus_affects_trait`, `locus_linked_to_locus`, `gene_absent_in_germplasm`, and
  `colocalizes with` / `coincides with` for overlap. On the six trial papers relation coverage rose from 41.7%
  to 69.4%.
- **Entities and validation state**: `common.qtn_names` keeps QTN apart from QTL and candidate genes;
  `agent.validated_by_record_ids` links the validation experiment the paper reports and
  `transform.validation_status` turns that into `candidate` / `experiment_reported`, with association and
  validation evidence kept side by side.
- **Review paraphrase**: `transform.evidence_origin` marks `review_report`, `agent.reported_citation_text`
  keeps the lead the review prints, and R040 asks for it.
- **The dashboard explains its own numbers**: the run header shows 候选 → 生成 → 接收 / 拒收 / 待审 with the
  definitions, and the paper badge separates pending records from structural hints.
- **The display contract lives in the repository**: `docs/presentation.md` requires every list view to show the
  entity beside its type, the validation status as its own column, the author's qualifier verbatim and the claim
  strength; `bdc check` enforces it through `check_presentation`, so deleting one of those columns fails CI. The
  dashboard's record table therefore has 实体 / 验证 / 限定语 / 结论强度 columns, and the relations table types
  both ends.
- **The regression is re-runnable**: `scripts/acceptance_report.py` runs the same papers with the main text and
  with the supplements, on 3.6.0 and 3.8.0, and writes every review-queue item and verdict to
  [`docs/acceptance_3.8.0.md`](docs/acceptance_3.8.0.md); `tests/test_acceptance.py` asserts the same matrix and
  `make acceptance` re-runs it (the human review-time column is left to the reviewer, the script does not time).

3.7.0 records *why* a relation has no code, and writes the state of a source part as data (both provisional):

- **The resolution is visible**: `transform.relation_resolution` (`coded` / `ambiguous` / `no_cue` / `negated`)
  says why `predicate_code` has a value or not — a vocabulary gap (fix the vocabulary) and a tie between two
  codes (register the entity mention) need different actions; `counts.relation.coverage` is the coverage read-out.
  The nature is derived from `predicate_code` when no human `predicate_label` exists, so a fresh record carries
  causal / associational itself. See [`docs/relation_semantics.md`](docs/relation_semantics.md).
- **The cue lexicon covers four classes**: statistical correlation (`locus_correlated_with_trait`), interval
  overlap and co-localisation (`locus_overlaps_locus`, structural), prediction and model comparison
  (`model_predicts_trait`, never causal) and functional effects backed by intervention (`locus_increases_trait`
  …); verb cues include the third person, the past tense and the passive, and the old `qtl_overlaps_qtl` is
  deprecated with a replacement.
- **Warnings are blocking or informational**: a rule may set `blocking: false` (R018, R036, R037). Such a warning
  is counted, written to `qc_failure_codes` and shown, but does not by itself put the record in `pending_review`
  — a value only the operator can supply, or one only a human can judge, cannot be cleared by the extraction.
- **The counts say what they count**: `counts.system_records` (one asset manifest per input file), `counts.warnings`
  (by code, by family, blocking versus informational) and `counts.relation`, with `count_definitions` in the
  report; `pending_review` is a subset of the accepted records, not another bucket.
- **Part states and the appendix**: `source_parts.parts[]` gives the state of every part (parsed, supplied
  without a text layer, supplied but never cited, cited but not supplied), `--supplement FILE:appendix` makes the
  appendix a part of its own, and the new `SOURCE_PART_NOT_PARSED` / `SOURCE_PART_UNREFERENCED` keep the two
  "we cannot read it" cases apart. See [`docs/downstream.md`](docs/downstream.md).

Three things were added in 3.5.0 for the agent that plans research (Topic 2); all are provisional:

- **The research workflow of a paper** as links between records: the role of a statement (background,
  question, objective, hypothesis, design, result, conclusion) and the links *tests*, *addresses* and
  *prerequisite* next to *evidence* and *method*. `bdc derive` writes `workflow.json` with step order, branch
  points, one trace per hypothesis and structural flags. See [`docs/workflow.md`](docs/workflow.md).
- **Semantic verification by a second model**: `bdc verify` asks, record by record and link by link, whether
  the quote really states the value. It can send a record back to review and promote one to `model_verified`,
  never to expert approval. See [`docs/review.md`](docs/review.md).
- **Papers in several files, and incomplete papers**: `--supplement` adds the supplementary file as a part of
  the same source; a main text that cites "fig. S2" without the supplement is reported as incomplete and the
  affected records are flagged instead of being filled in.

## 🧬 Data pipeline overview

[![Breeding literature pipeline: versioned contract, PDF extraction, evidence checks, structured-data imports, JSONL outputs and derived views](docs/diagrams/pipeline.en.svg)](docs/diagrams/pipeline.en.svg)

[HTML source](docs/diagrams/pipeline.html) · [Full-size SVG](docs/diagrams/pipeline.en.svg) · [Architecture](docs/architecture.md)

The diagram covers PDF extraction, imports of existing data, rejection and manual review paths, and the outputs:
relational tables, a knowledge graph, an evidence corpus with QA seeds, and document bundles. The HTML switches
languages and downloads the SVG. Run `make diagram` to regenerate both README images after editing the source.

## 📚 Inside the repository

| Path | What it is |
| --- | --- |
| `field_catalog/field_catalog.yaml` | **Canonical catalog**: every field, type, availability code, rule and ambiguity |
| `vocabularies/` | Controlled vocabularies and the deterministic unit table |
| `profiles/` | Field selections for one use case (`full`, `compact`, `pdf_extraction`, `pdf_extraction_omics`) |
| `releases/` | Frozen, hash-verified contract versions and `index.json` (`latest` pointer) |
| `schemas/meta/` | JSON Schemas for the source files themselves (catalog, vocabulary, profile, mapping) |
| `schemas/runtime/` | JSON Schemas for run outputs (manifest, validation report, error records, bundle, migration report, verification report) |
| `mappings/` | Leaf-by-leaf mappings from existing data formats to the contract, with issue registers; used by `bdc migrate` |
| `sources/` | Immutable original inputs (see `sources/SOURCES.md`) |
| `src/breeding_contract/` | Contract tooling: compile, release, resolve, validate, import, bundle, derive, audit, verify (`bdc` CLI) |
| `skills/pdf2jsonl/` | The Skill: `SKILL.md`, extraction brief template, runtime (`scripts/pdf2jsonl`) |
| `docs/` | Architecture, versioning, source analysis, importers, downstream outputs, key roles and functions; `docs/generated/` is built from the catalog (including the [field reference](docs/generated/field_definitions.md)) |
| `docs/field_examples.yaml` | Curated illustrative values used to generate and validate the field reference |
| `docs/field_classification.yaml` | Per-field multi-select tags: Research Content 1, Research Content 2, future iteration, and general-purpose fields |
| `scripts/make_site.py` / `site/` | Site builder and page templates: contract browser, paper dashboard (`scripts/make_dashboard.py`), downstream outputs, importers |
| `examples/` | Two synthetic papers (one in two files), curated records, pipeline output (also for the paper without its supplement), a verification pass, derived views, importer output, invalid cases |
| `tests/` | pytest suite (catalog fidelity, releases, validation, pipeline, Skill sync, importers, bundles, functions, evidence chain, downstream hooks, workflow, verification, source parts, site) |

## 🔬 Contract at a glance (3.8.0)

- 421 fields in five groups: `common` 180, `agent` 64, `skills` 53, `transform` 56, `omics` 68.
  The 259 v3.0.0 fields are `verified` and verbatim; the 162 fields added since are `provisional`.
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
- 37 cross-field rules (20 errors, 17 warnings): explicit source statements are errors, inferred ones are warnings only.
- 42 ambiguities are registered in the catalog (`AMB-001` … `AMB-042`) instead of being silently decided.
- `review_status` is a ladder: `pending_review` → `auto_validated` (deterministic checks) → `model_verified`
  (an independent verifier) → `expert_approved` / `rejected` (a person).

See the [online field catalog](https://atoz03.github.io/pdf2jsonl/fields.html), [field definitions and examples](docs/generated/field_definitions.md), the
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
(which statements are linked to data and methods, and which hedges or links are missing), `workflow_structure`
(untested hypotheses, results without a method, dependency cycles) and `source_parts` (parts of the paper the text
cites but that were not supplied). Other backends: `--candidates file.json`, `--backend mock`,
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

### `bdc` CLI

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
| `bdc derive F.jsonl --out DIR` | Function 3: relational tables (CSV), statements, triples and a property graph, the research workflow, an annotated corpus and QA seeds, with their lineage |
| `bdc audit F.jsonl [--json]` | Evidence-chain audit (Toulmin/Flavell elements, link closure, review flags; no score) and workflow structure |
| `bdc verify tasks\|apply F.jsonl [VERDICTS] --out DIR` | Semantic verification by an independent verifier: build the tasks, then apply its verdicts to the review fields |

## 🌿 Evolving the contract

1. Edit `field_catalog/field_catalog.yaml` (and vocabularies/profiles). Keep source references; mark new
   semantics `provisional` and register open questions as ambiguities.
2. Bump `VERSION` per `docs/versioning.md` and add a `CHANGELOG.md` entry.
3. Add or update illustrative values in `docs/field_examples.yaml` and functional tags in `docs/field_classification.yaml`; contract name and version examples are generated automatically.
4. `bdc generate && bdc release && bdc check --strict && pytest`. Generation checks that every field has an example and that examples match field schemas.
5. The Skill needs no edit: its next run resolves `latest` and renders the brief from the new release.
   `bdc check` fails if the Skill hard-codes field paths or versions, or if a profile needs a fill rule the
   Skill does not implement.

<a id="import"></a>

## 🌾 Import existing data

Data that already exists in another shape enters the same contract through an importer, not through a second
schema. Each importer follows a leaf-by-leaf mapping (`mappings/`) and produces the same atomic records as
extraction, validated the same way.

| Command | Input | Example |
| --- | --- | --- |
| `bdc migrate legacy` | Document-level JSONL, one paper per line | `sources/legacy_v1/breeding_jsonl_example.jsonl` |
| `bdc migrate omics` | Filled instances of the multi-omics metadata template | `examples/migration/omics_v2/synthetic_deg_instance.json` |
| `bdc migrate merged` | Documents with observation, sample, assay and asset arrays joined by explicit IDs | `sources/merged_v2/breeding_jsonl_example_v2.json` |

```bash
bdc migrate merged sources/merged_v2/breeding_jsonl_example_v2.json --out out/merged --page-offset 2220
```

`--page-offset` converts journal pages to physical PDF pages; `2220` applies only to this example, and `0` means
the pages are already physical. All three importers write the same outputs: valid records, rejected candidates
with reasons, unconverted source content (residue) and a hashed migration report. Nothing is dropped silently
and nothing is invented to fill a required field. Imported records start as `pending_review`. See
`docs/migration.md` for the importers and `docs/source_analysis.md` for how the sources differ.

## 🗂 Documentation

- `docs/downstream.md` — the record as a hub: the hooks consumers need, every output of `bdc derive`, source
  parts and incomplete papers, how the representations trace back to each other
- `docs/workflow.md` — the research workflow of a paper as roles and links between records
- `docs/review.md` — the three layers of checking, `bdc verify`, what experts decide
- [Field definitions and JSON examples](docs/generated/field_definitions.md) — generated reference for all fields
- `docs/architecture.md` — components, data flow, pipeline stages, invariants
- `docs/versioning.md` — semantic versioning of the contract, releases, `latest`/`dev`, compatibility
- `docs/source_analysis.md` — the source designs, their inconsistencies and the merge decisions
- `docs/migration.md` — the three importers, the mapping files and the derived views (`document_bundle`, `bdc derive`)
- `docs/field_functions.md` — what every key is for: roles, the four functions, cards, the evidence chain (TRACE),
  derived views and the audit
