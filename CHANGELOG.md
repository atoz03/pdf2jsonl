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

## [3.4.0] - 2026-10-06

This release makes the record a **hub** rather than a container: a record now carries the hooks that a
knowledge graph, a corpus and a QA set are built from, so no consumer has to parse the quote a second time
(`docs/downstream.md`, AMB-038). All additions are provisional. No existing field changes type, availability
or meaning, and records of earlier versions stay valid.

### Added
- **4 fields** (group `transform`, role `relation`):
  - `transform.predicate_mention` (D): the words of the quote that connect subject and object, verbatim. With
    `subject_mention` and `object_mention` it makes the statement explicit at extraction time. Until now the
    only predicate fields were human judgment (`predicate_label`) or ontology IDs (`predicate_id`), so an
    extracted statement had no predicate at all.
  - `transform.predicate_code` (N): a code of vocabulary `predicate_label`, set only when the cue words and the
    entity types of both ends match exactly one code, and never for a negated relation ("was not associated
    with" stays verbatim). It never replaces the reviewed `predicate_label`.
  - `transform.predicate_start_offset`, `transform.predicate_end_offset` (N): where the predicate stands in
    `common.source_quote`.
- **Type `array_entity_link`** (`transform.entity_links`) gains optional `start`, `end` (character offsets of
  the mention in `common.source_quote`) and `relation_role` (`subject` / `object`). The pipeline now writes one
  marker per entity mention of a record, typed by the field that lists it.
- **Vocabulary `predicate_label`**: every code gains `cues`, `subject_types` and `object_types`, the lexicon
  that `predicate_code` is derived from. These are repository proposals (AMB-038).
- **Rules** (both warnings):
  - `R033` (inferred): a statement with subject and object should give a predicate.
  - `R034` (definitional; new rule kind `offsets_match_text`): the offsets of markers and of the predicate must
    point at their mention in the quote.
- **Profile `pdf_extraction`**: semantic roles `relation_subject` / `relation_predicate` / `relation_object`
  and the normalizer `relation_anchors`. The extraction brief gains a "Relations" section built from them.
- **`bdc derive`** reads the hooks and writes four more outputs: `statements.csv` (one typed, anchored
  subject–predicate–object row per statement, with `predicate_status`, qualifiers and hedge),
  `graph.json` (property graph), `qa.jsonl` (cloze QA seeds that cite their records) and entity offsets plus
  statement IDs on every corpus chunk. Corpus and QA rows are keyed by the `transform.chunk_*` / `qa_*` field
  names.

### Changed
- `bdc derive` corpus keys follow the catalog: `text` → `chunk_text`, `support_ids` → `chunk_support_ids`,
  `page` → `chunk_page`, `section` → `chunk_section`. A statement whose only predicate is verbatim is written
  as `bdc:stated_relation` with `predicate_mention`; `bdc:unlabelled_relation` remains for statements with no
  predicate at all. The statement ID is a content hash (`stm_…`) instead of the record node.
- The generated field reference moved from the repository root (`FIELD_DEFINITIONS.md`) to
  `docs/generated/field_definitions.md`, next to the other generated documents.

## [3.3.0] - 2026-10-06

### Added
- Three optional provisional sample fields from merged v2: biological replicate ID, technical replicate ID, and verbatim sampling time.
- Archived merged v2 sources, mapping coverage and a migration command for document/unit inputs, observations, linked omics samples/assays and assets, with rejected records and loss accounting.
- Integration audit and regression tests for evidence, references, UTC conversion and conflicting values.

## [3.2.0] - 2026-09-30

This release records **what every key is for**. It follows the data owner's four record functions
(`sources/project/record_functions.md`) and the research contents of Topics 1–3
(`sources/project/research_contents.md`). It also adds the fields and rules that the evidence chain and the
derived views were missing, reviewed through the TRACE argument lens (Toulmin + Flavell, arXiv:2605.29656).
All additions are provisional. No existing field changes type, availability or meaning.

### Added
- **Annotations on every field** (AMB-032):
  - `key_role`: what the key does. There are 25 roles in 6 families. Each role states how it projects into a
    knowledge graph, relational tables, triples and QA/corpora, and which function facets it feeds.
  - `serves`: which of the four functions the key serves:
    - `topic2` — Topic 2 scientific agent;
    - `topic3` — Topic 3 skills;
    - `derivation` — KG / relational tables / QA / corpus / triples;
    - `iteration` — our own iteration, i.e. Topic 1 (confirmed by the data owner: this repository is Topic 1's).
  - `card`: for Topic 2/3 fields, the hypothesis, experiment-design or result-analysis card the field feeds.
  - `argument_role`: the Toulmin/Flavell element of the field (AMB-033).
  - `bdc check` guarantees that functions and cards stated by the v3 downstream column are never dropped or
    rewritten. Functions added by the repository are listed separately in `docs/generated/field_functions.md`.
- **Catalog codes**: `codes.function` (with facets taken from the research contents), `codes.key_role`,
  `codes.key_role_family`, `codes.card` and `codes.argument_role`. Groups `agent`, `skills` and `transform`
  declare the function they serve.
- **9 fields**:
  - Topic 2 evidence chain:
    - `agent.claim_qualifier_text` (D): the verbatim hedge;
    - `agent.stated_limitations` (D): limitations stated by the authors;
    - `skills.method_record_ids` (N): the result → method link.
  - Derivation:
    - `transform.entity_links` (type `array_entity_link`): mention → entity ID pairs (AMB-034);
    - `transform.qa_id` (G).
  - Iteration / Topic 1:
    - `common.extraction_profile` (N);
    - `common.replaces_record_ids` (N);
    - `common.conflict_resolution_status` (I, new vocabulary `conflict_resolution_status`);
    - `common.record_updated_at` (N) (AMB-036).
- **Rules**:
  - `R031` (warning, definitional; new dataset rule kind `references_resolve`): evidence-chain references
    must resolve within the dataset.
  - `R032` (warning, inferred; new condition `matches`): a claim whose quote hedges should keep the qualifier
    text (AMB-035).
- **Profile `pdf_extraction`**:
  - `record_links` (`evidence` → `agent.evidence_record_ids`, `method` → `skills.method_record_ids`);
    candidates may now carry `ref` and `links`;
  - system field `common.extraction_profile`.
- **Ambiguities**: AMB-032 … AMB-036.

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
