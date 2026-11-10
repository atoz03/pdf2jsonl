# Release history

[`CHANGELOG.md`](../../CHANGELOG.md) is the curated record of every release. This directory keeps what is too
long for it: long-form release notes, and text retired from the READMEs. Files here describe the project as it
was when they were written and are not updated afterwards; for the current behaviour read the guides listed in
[`docs/README.md`](../README.md).

## Contract releases

Frozen, hash-verified releases live in [`releases/`](../../releases/) and are listed in
[`releases/index.json`](../../releases/index.json). 3.7.0 has a changelog entry but was never frozen on its own
and is not in the index; its changes are part of the frozen 3.8.0. Versioning rules: [`docs/versioning.md`](../versioning.md).

| Version | Date | Summary | Notes |
| --- | --- | --- | --- |
| 3.8.0 | 2026-10-27 | Entities, evidence and validation (AMB-045 – AMB-047): `common.qtn_names`, `agent.validated_by_record_ids` (link and workflow edge `validated_by`), `transform.claim_strength`, `validation_status`, `evidence_origin`, `agent.reported_citation_text`; vocabularies `claim_strength`, `validation_status`, `evidence_origin`; R038–R040; eight predicate codes (QTN association, active/passive suppression, upstream, controlled by, major effects, allelic/tight linkage, deletion) and `colocalizes`/`coincides`/`correlation between` cues; `supplied_items_not_found` and `SOURCE_PART_ITEM_NOT_FOUND`; dashboard counts strip, badge split and record badges; `pdf2jsonl` 0.6.0 | [CHANGELOG](../../CHANGELOG.md#380---2026-10-27) · [acceptance report](../acceptance_3.8.0.md) (zh) |
| 3.7.0 | 2026-10-27 | Relation resolution and part states (AMB-043, AMB-044): `transform.relation_resolution` (N) and vocabulary `relation_resolution`, codes `locus_correlated_with_trait` / `locus_overlaps_locus` / `model_predicts_trait`, `qtl_overlaps_qtl` deprecated, inflected cues, `relation_nature` derived from `predicate_code` too, non-blocking rules (`rules[].blocking`), deprecated vocabulary values, `counts` expanded with `count_definitions`, `source_parts.parts[]` states and `SOURCE_PART_NOT_PARSED` / `SOURCE_PART_UNREFERENCED`, `--supplement FILE:appendix`; `pdf2jsonl` 0.5.0 | [CHANGELOG](../../CHANGELOG.md#370---2026-10-27) · not frozen under `releases/` |
| 3.6.0 | 2026-10-19 | Relation semantics (AMB-042): `nature` on every `predicate_label` code, vocabularies `relation_nature` and `relation_assertion_mode`, `transform.relation_nature` (N, derived) and `transform.relation_assertion_mode` (D), R036–R037, the `relation_nature_from_predicate` fill rule; `bdc derive` statements, triples and graph edges carry the nature and the wording (`derive_format` 4), and the paper dashboard pages every long tab | [CHANGELOG](../../CHANGELOG.md#360---2026-10-19) · [3.6.0.md](3.6.0.md) (zh) |
| 3.5.0 | 2026-10-10 | Research workflow, verification and source parts (AMB-039 – AMB-041): 8 provisional fields (`agent.statement_role`, three workflow links, `agent.step_condition`, `common.source_part`, `common.verification_run_id`, `transform.ontology_id`), vocabularies `statement_role` and `source_part`, `review_status: model_verified`, four evidence-type codes, R035; `--supplement`, source completeness, `bdc verify`, `workflow.json` and lineage in `bdc derive` | [CHANGELOG](../../CHANGELOG.md#350---2026-10-10) |
| 3.4.0 | 2026-10-06 | Downstream hooks (AMB-038): `transform.predicate_mention` (D), `predicate_code` and predicate offsets (N), offsets and relation roles on `transform.entity_links`, cue lexicon on vocabulary `predicate_label`, R033–R034; `bdc derive` adds statements, a property graph and QA seeds | [CHANGELOG](../../CHANGELOG.md#340---2026-10-06) |
| 3.3.0 | 2026-10-06 | Three optional provisional sample fields from merged v2 (biological replicate, technical replicate, sampling time); merged input mapping and migration; the 397 existing field definitions remain unchanged | [CHANGELOG](../../CHANGELOG.md#330---2026-10-06) |
| 3.2.0 | 2026-09-30 | Key roles and functions on every field (`key_role`, `serves`, `card`, `argument_role`); 9 provisional fields for the evidence chain, derivation and Topic 1 fusion; R031–R032; vocabulary `conflict_resolution_status`; profile `record_links` | [CHANGELOG](../../CHANGELOG.md#320---2026-09-30) |
| 3.1.0 | 2026-09-28 | Merge of legacy v1 and omics v2: 129 provisional fields (legacy 17, omics 111, `schema_name`), 6 vocabularies, R027–R030, `pdf_extraction_omics`, mappings | [CHANGELOG](../../CHANGELOG.md#310---2026-09-28) |
| 3.0.0 | 2026-09-28 | Faithful import of the 259-field v3 baseline: rules, vocabularies, profiles `full` / `compact` / `pdf_extraction` | [CHANGELOG](../../CHANGELOG.md#300---2026-09-28) |

## Tooling releases

Releases of the `breeding_contract` tooling (`GENERATOR_VERSION`) that leave the contract unchanged.

| Version | Date | Summary | Notes |
| --- | --- | --- | --- |
| 1.1.0 | 2026-11-10 | Research view: per-paper phenotype–gene–population view and full-network toggle, evidence chains, article packages, cross-paper A/B/C confidence, human review applied with `bdc review apply`; contract stays 3.8.0 | [CHANGELOG](../../CHANGELOG.md#tooling-110---2026-11-10) · [tooling-1.1.0.md](tooling-1.1.0.md) |

Changes merged after the latest release are under [Unreleased](../../CHANGELOG.md#unreleased) in the changelog.

## Retired README text

- [`readme-highlights.md`](readme-highlights.md): the per-version sections (3.5.0 – 3.8.0, tooling 1.1.0) that
  both READMEs carried until 2026-11-10, verbatim in English and Chinese.
