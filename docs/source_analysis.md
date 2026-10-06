# Source analysis

This analysis covers the designs that were supplied, where they disagree, and how the contract resolved each
point. The first three were analysed before the repository was built; the fourth arrived with 3.3.0 and was
handled the same way. The original files are kept byte-identical in `sources/` (see `sources/SOURCES.md` for
the hashes). Every unresolved point is registered as an ambiguity (`AMB-*`) in the catalog, or as a mapping
issue (`LEG-*`, `OMX-*`, `MRG-*`) in `mappings/`. The generated register is `docs/generated/ambiguities.md`.

## 1. The sources

| Source | Files | Shape | Status in the repository |
| --- | --- | --- | --- |
| **fields_v3** (v3.0.0) | `sources/fields_v3/breeding_fields_259_{final,intro}.md`, `…_compact_{final,intro}.md` | Flat field dictionary: 259 unique logical fields in four groups (`common` 127, `agent` 46, `skills` 46, `transform` 40), each with type, availability D/N/I/G/F, requirement Y/C/N, data source, downstream use, definition. Sparse atomic records (one claim, observation, method, result or asset per line). The 157-field compact set is a hand-picked subset. | **Authoritative baseline.** Imported verbatim as release 3.0.0 (`maturity: verified`, per-field source line references; `tests/test_catalog_fidelity.py` compares the catalog with the markdown). |
| **legacy_v1** (v1.0.0) | `sources/legacy_v1/` spec, JSON Schema, template, example, README | Document-centric: **one paper per JSONL line** with 12–14 top-level blocks (`record_info`, `doc_meta`, `breed_entities`, `relations`, `experiments`, `analyses`, `conclusions`, `pipeline`, `governance`, `provenance`, `agent`, `skill`); 713 schema leaves. | Superseded design. Content fields merged as 17 provisional fields (3.1.0); the rest is covered by `mappings/legacy_to_current.yaml`. Converted by `bdc migrate legacy`, and re-derivable as a view with `bdc bundle --legacy-v1`. |
| **omics_v2** (2.0.0) | `sources/omics_v2/omics_metadata_template.json` | A template of 27 groups and 252 field names, all values `null`. It has no definitions, types, units or requirements. | Candidate extension. Merged as 111 provisional fields (68 in the new `omics` group), plus `mappings/omics_to_current.yaml`. Converted by `bdc migrate omics`. |
| **merged_v2** (v2.0.0) | `sources/merged_v2/` README, spec, JSON Schema, template, JSON/JSONL example, mapping note | A combined design over the three above: the legacy document line extended with observation, sample, assay and asset arrays, plus unit rows that point at a parent document; 1,022 schema leaves (317 more than legacy v1; the count includes attributes repeated across entity, evidence and observation objects). | An input format, not a second schema. Three sample fields added as provisional (AMB-037), plus `mappings/merged_to_current.yaml`. Converted by `bdc migrate merged`. |

Two project documents were added later, in 3.2.0. They define what the records are for rather than new fields.
They are also kept verbatim, under `sources/project/`:

| Source | File | Used for |
| --- | --- | --- |
| **record_functions** | `sources/project/record_functions.md` | The data owner's four record functions: Topic 2, Topic 3, derivation into KG / relational DB / QA / corpus / triples, and our own iteration. They became `codes.function` and the `serves` annotation (AMB-032). |
| **research_contents** | `sources/project/research_contents.md` | The research contents of Topics 1–3. They supply the facets of each function: reasoning, planning, memory and execution layers; interfaces, orchestration, registry and card flow; standards, quality, ontology and fusion. Topic 1 fusion needs (conflict resolution, dynamic update) motivated AMB-036. |

The two uploaded archives were named `jsonl.zip` and `Jsonl.zip`. The names differ only by case and collide on
case-insensitive filesystems, so they are stored as `sources/archives/fields_v3__jsonl.zip` and
`legacy_v1__Jsonl.zip`.

## 2. Inconsistencies found

### 2.1 Inside v3 (the baseline)

| Finding | Register |
| --- | --- |
| Fields are named `group.field` but no record instance is given, so the layout (flat or nested) is undefined. `workflow_steps` exists in both `agent` and `skills`, which rules out a flat layout. | AMB-001 |
| The missing-value policy is stated only in the compact intro ("omit; no empty string, null or guesses"). The other sources use `null` and empty placeholders. | AMB-003 |
| The item structures of `array_evidence`, `array_step` and `array_parameter` are undefined. | AMB-004 … 006 |
| `analysis_result` shares one grain sentence with `tool_spec`, so its grain is undetermined. | AMB-007 |
| Most `C` (conditional) fields do not state their condition. | AMB-008 |
| Interval fields must be used with an assembly, yet `genome_assembly` is omitted when unreported. | AMB-009 |
| Closed vocabularies are given only as Chinese labels (review_status, extraction_method, …). | AMB-010 |
| The stable-ID rule and the locator and span syntax are not defined. | AMB-011 |
| There is no `relation` record kind, while subject/predicate/object live in `transform` and `predicate_label` is `I`. | AMB-012 |
| Records carry `schema_version` but no contract name. | AMB-013 |
| Whether `finding_text` is verbatim or a paraphrase is not stated. | AMB-014 |
| Normalization target units are not defined, and the "measurements vocabulary" is referenced but not supplied. | AMB-015, AMB-016 |
| `extraction_confidence` is `G` but is produced during extraction. | AMB-017 |
| Whether table values need a quote, and when a title may be omitted, is unclear. | AMB-019, AMB-020 |
| `crop_name` is required and single-valued, but multi-crop papers are not addressed. | AMB-022 |
| The checksum algorithm and the `association_vs_causation` values are unspecified. | AMB-023, AMB-024 |

### 2.2 Inside legacy v1

| Finding | Register |
| --- | --- |
| Page numbers are **journal pages** (the example runs 2221–2235), while v3 `source_page` is the physical PDF page. | LEG-002, AMB-029 |
| The example stores a GWAS `-log10(P)=8.7` snippet as `qtls[].lod`. | LEG-004 |
| `interval.unit` is specified as cM/bp, but the example uses `Mb`. | LEG-011 |
| The spec lists `document_sections.heading`, which the schema lacks. The example carries fields the schema does not define (`heading`, `output_name`), and `disease_pests` has no structure. | LEG-006 |
| The spec's quick reference shows `provenance` as an array; the schema and the example use an object. | covered by LEG-006 (schema leaves are the baseline) |
| An evidence snippet in the example refers to a dangling section (`sec-result`), and several snippets contain `...`, so they are not verbatim. | LEG-009 (flags `LEGACY_SECTION_REF_DANGLING`, `LEGACY_SNIPPET_NOT_VERBATIM`) |
| `doc_meta.pdf_path` stores a local path. | LEG-003 (forbidden, R020) |
| Relations can be `is_inferred: true`, and hypotheses can be model-generated. | LEG-005 |
| The `agent` and `skill` blocks hold pipeline and runtime state; in v3 the same group names hold paper-derived content. | LEG-001 |
| Translations (`title_zh`, `claim_zh`) sit next to the original text. | LEG-010 |
| Missing values appear as `null`, `""` and `[]`. | LEG-007 |
| Version strings are written as `v1.0.0`. | LEG-012, AMB-002 |

### 2.3 Inside omics v2

| Finding | Register |
| --- | --- |
| There are names only: no definitions, types, units or ranges. For example, whether a fold change is log2, or a fraction is 0–1, is not stated. | AMB-026, OMX-001 |
| `record_type` has no value list. | OMX-002 |
| `cell_type`, `cell_state` and batch fields are duplicated across groups. | OMX-010 |
| The `null` convention contradicts omit-missing. | OMX-008 |
| Units of `qtl_start` / `qtl_end` are unstated. | OMX-009 |

### 2.4 Inside merged v2

Passing the source schema only shows that the input has the structure of that source. The archived example
passes it; the empty template produces 56 errors.

| Finding | Resolution | Issue |
| --- | --- | --- |
| Document state mixed with atomic facts: agent run state, governance scores, skill registry status, translations, vectors and derived views sit next to paper content. | The atomic record stays the format. Values without a stated meaning or evidence binding go to the residue file with a reason. | MRG-001 |
| `source_locations` and evidence objects carry journal pages (2221–2234), not physical PDF pages. | Converted only with an explicit `--page-offset`; without one no physical page is written. | MRG-002 |
| Some quotes contain `...`; `sec-result` has no section definition in the document. | An incomplete quote never becomes `source_quote`; a dangling section is flagged for review. Every imported quote awaits verification against the PDF. | MRG-002 |
| Two asset digests are truncated strings (`f6e0ba80c14e...`, `7c3d...`). | The two asset candidates are rejected with the original value and the reason; nothing is patched. | MRG-002 |
| Observations reach their context through `sample_ref` / `assay_ref`, and the input does not enforce referential integrity. | Joined by explicit ID only. Duplicate IDs, conflicting values and a sample that does not belong to the named assay reject the candidate; a reference defined outside the input keeps its ID and gets a review flag. | MRG-003 |
| Observation times use `+08:00`; the contract's `observation_time` is UTC. | Converted deterministically when the zone is explicit; a string without a zone is never assigned one. | MRG-003 |
| `omics_feature` is an open object and the example's `go_term` is an array; some statistics lack range constraints. | Fields with the same name as a contract field are used; a single-element array may be unwrapped, several values are kept in the residue rather than joined. Probability, dosage and ploidy rules of the contract still apply. | MRG-004 |
| Document-level locations, reasoning notes and QA / graph references are not bound to individual facts. | Not broadcast to records. They stay in the residue until a binding and an ID rewrite are defined. | MRG-001 |
| The source README says v1 inputs are compatible as they are; the legacy example does not pass the new schema. | The source version is checked (`v2.0.0`) and never guessed from a file name. | MRG-001 |

### 2.5 Across sources

| Finding | Resolution |
| --- | --- |
| Granularity: one document per line (legacy) vs one atomic fact per line (v3) | v3 wins. The legacy layout becomes a migration mapping plus the derived `document_bundle` view. |
| Version formats `v3.0.0` / `v1.0.0` / `2.0.0` | Bare semver in records; a `v` prefix is accepted on input (AMB-002). |
| legacy `doc_type` (journal paper, thesis, review, …) vs v3 `source_type` (paper, experiment_record, tool_description) | New `common.source_document_type` refines `source_type=paper` (AMB-028). |
| legacy crop list (Chinese, includes livestock) vs v3 free-text `crop_name` | Open `crop_name` vocabulary with aliases; free text is still allowed (AMB-030). |
| omics raw fields vs v3 normalized or judgement fields (`treatment` vs `treatment_type`, `effect_direction` vs `relation_polarity`, `data_accessions` D vs `sequence_accessions` F) | Kept side by side and never merged or converted automatically (AMB-027). |
| omics per-assay value fields (`expression_value`, `protein_abundance`, …) | Mapped to v3 single-value measurements `measurement_value/unit/name` (AMB-031). |
| omics and legacy both specify quality scores | Not imported: D/N/I/G/F is not a quality score, and v3 has no score field. |

## 3. Merge decisions

1. **v3 is the semantic baseline.** Its 259 definitions are copied verbatim and not reinterpreted (`verified`).
   Where v3 is silent, the repository adds the minimum needed to operate (a layout, a missing-value rule, ID
   and locator syntax, units) and registers each such decision as an ambiguity marked `decided`, `provisional`
   or `open`.
2. **Nothing from legacy or omics is `verified`.** All 129 added fields are `provisional`, `since: 3.1.0`, and
   record their `origin` and `origin_paths`. Definitions of omics fields are literal renderings of the field
   names, and types are assigned by the repository (AMB-026).
3. **Rule strength follows evidence.** Only explicit source statements become error rules. Anything inferred is
   a warning (`basis: inferred`; `bdc check` enforces this). Proposed English codes for Chinese-only lists are
   warning-level until they are confirmed.
4. **No new breeding semantics.** No relation record kind (relations are claims, AMB-012). Association is never
   upgraded to causation. Journal pages never become physical pages without an explicit offset.
5. **Legacy is a migration, not a second schema.** Every legacy and omics leaf is covered by a mapping entry with
   a status (`mapped`, `partial`, `transformed`, `merged`, `control`, `view_only`, `unmapped`, `forbidden`).
   `bdc check` fails if a source leaf is uncovered, a target field does not exist, or a `merged` target does not
   record the origin. See `docs/migration.md`.
6. **Profiles select; they do not define.** `compact` keeps the exact 157-field list (AMB-025).
   `pdf_extraction` exposes only D fields to models. `pdf_extraction_omics` adds the omics group.
7. **A later source is another importer.** The merged design reorganises material the contract already holds, so
   it added three optional D fields that were missing (biological replicate ID, technical replicate ID and
   verbatim sampling time, AMB-037) and an importer for its observation, sample, assay and asset arrays. The 397
   field definitions that existed before it are unchanged. Cross-paper confidence scores, agent run state, skill
   registry status, translations and vectors are not mixed into paper facts; they remain in the source files
   and in the residue. Standalone `transform` rows and runtime `tool_spec` rows are reported as unsupported.
   Still open for this source: an ID rewrite for its QA and graph references, per-fact evidence for
   document-level reasoning, and source definitions for entity kinds such as pests and diseases.

## 4. Open questions for the data owners

Decisions that need a domain owner's confirmation are listed with status `open` or `provisional` in
`docs/generated/ambiguities.md`. The most consequential are:

- AMB-004 … 006: the item structures of evidence, step and parameter arrays.
- AMB-007: the grain of `analysis_result`.
- AMB-008: the conditions for the `C` fields.
- AMB-010: English codes for the Chinese-only vocabularies.
- AMB-022: `crop_name` for multi-crop papers.
- AMB-026 / AMB-027: definitions of the omics fields, and whether overlapping raw and normalized pairs should
  be consolidated.
- AMB-032 … 036: the function assignment of every key (source statement versus repository addition), the TRACE
  argument roles, the entity-link structure, the hedge lexicon, and the conflict-resolution codes.
- AMB-037: the namespace of replicate IDs taken from the merged source.
- AMB-038: the hooks for downstream derivation (verbatim predicate, entity and predicate offsets, the cue
  lexicon behind `predicate_code`); see `docs/downstream.md`.

Confirming a provisional field (`provisional` → `verified`) is a MINOR release. Changing its meaning is a
MAJOR release (`docs/versioning.md`).
