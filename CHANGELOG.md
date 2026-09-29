# Changelog — breeding-literature-record contract

All notable changes to the **data contract** (field catalog, vocabularies, profiles, rules) are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow semantic versioning
(see `docs/versioning.md`):

- **MAJOR**: a field is removed or renamed, a type or meaning changes, a vocabulary code is removed, or an
  existing rule is tightened to error.
- **MINOR**: new fields, codes, profiles or warning-level rules are added, or `provisional` is promoted to
  `verified`.
- **PATCH**: wording, documentation and source references change with no effect on validation.

Each heading `## [X.Y.Z] - YYYY-MM-DD` provides the release date that `bdc release` records.

## [3.1.0] - 2026-09-28

The merge release adds the legacy v1 document-level design and the omics 2.0.0 candidate template. Every
added field is `provisional`, and the existing 259 v3 fields are unchanged.

### Added
- `common.schema_name` (AMB-013). It is optional in the catalog and required by the extraction profiles,
  which fill it automatically.
- Fields from **legacy_v1** (17):
  - document metadata: document type (A-1 codes), journal, volume, issue, publication page range (never the
    physical page, AMB-029), abstract, keywords, funding, affiliations;
  - cM interval bounds;
  - marker type and primers;
  - variety approval number;
  - pedigree text;
  - effect type.
- Fields from **omics_v2** (111):
  - 68 in the new `omics` group: experiment, feature, cross-species, transcriptomics, single-cell,
    epigenomics, proteomics and metabolomics;
  - 43 in `common` / `agent` / `skills` / `transform`: sample, tissue, treatment, reference system, variant,
    statistics and tool I/O.
  - The template gives names only, so definitions are literal renderings and types are assigned by the
    repository (AMB-026).
- Vocabularies:
  - `document_type` (error);
  - `trait_category` (warning, proposed codes);
  - `crop_name` (open; also drives automatic crop detection);
  - `predicate_label` (open);
  - `omics_type` (open);
  - `candidate_gene_status` (warning; codes from the omics template).
  - `population_type` and `method_category` are extended with legacy A-4 and A-9 codes.
- Rules:
  - R027: cM start ≤ end;
  - R028: peak start ≤ end;
  - R029: positions should name the assembly (warning);
  - R030: the effect allele should be ref or alt (warning).
- Profile `pdf_extraction_omics` (extends `pdf_extraction` with the omics group).
- Ambiguities AMB-013 and AMB-026 … AMB-031.
- Source mappings `mappings/legacy_to_current.yaml` (713 leaves) and `mappings/omics_to_current.yaml`
  (252 leaves), with issue registers LEG-001 … LEG-012 and OMX-001 … OMX-010.

### Changed
- `pdf_extraction`:
  - new document-level fields;
  - `schema_name` is system-filled and required;
  - `source_abstract` is excluded from per-row records;
  - `source_language` is exempt from the literal value-presence check.
- `compact`: includes `common.schema_name`.
- `common.crop_name`, `agent.candidate_gene_status` and `transform.predicate_label` are bound to the new
  vocabularies. All three are open or warning level, so records that were valid do not become invalid.

## [3.0.0] - 2026-09-28

Faithful import of the v3.0.0 field baseline (`sources/fields_v3/`). It adds no new breeding semantics.

### Added
- 259 logical fields in four groups: `common` 127, `agent` 46, `skills` 46, `transform` 40. They keep the
  source definitions, D/N/I/G/F availability and Y/C/N requirement codes, and every field has a source line
  reference.
- Record kinds and their grains from the source "记录粒度" section. The grain of `analysis_result` stays
  unresolved (AMB-007).
- 26 cross-field rules. Rules taken from explicit source statements are errors. Rules that are only implied by
  the source are warnings (`basis: inferred`).
- 25 vocabularies:
  - code lists given by the source are enforced as errors;
  - proposed codes for Chinese-only closed lists are warnings;
  - open lists are suggestions;
  - a deterministic unit-conversion table.
- Profiles:
  - `full`: every active field;
  - `compact`: the 157-field first production set from the source;
  - `pdf_extraction`: D fields for models, N fields computed by named pipeline rules, and I/G/F fields never
    exposed.
- Repository conventions for stable record IDs, locators and spans (AMB-011), and the omit-don't-null
  missing-value policy.
- Ambiguity register: AMB-001 … AMB-025, with AMB-013 reserved.
