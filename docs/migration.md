# Importers and derived views

Three other designs have data in circulation: **legacy v1** (one paper per JSONL line), the **omics v2
template**, and the **merged v2** document with observation, sample, assay and asset arrays. None is a second
schema in this repository. Each is a *mapping* onto the current contract (`mappings/*.yaml`), plus an importer
(`bdc migrate legacy | omics | merged`) that produces ordinary atomic records validated like any other.

All three write the same four outputs: `*.migrated.jsonl` (records), `*.migrated.errors.jsonl` (rejected
candidates with the reason), `*.residue.json` (every nonempty source value that was not migrated) and
`*.migration.json` (contract version, source and mapping hashes, counts). The site shows them side by side
under "Importers".

## Mapping files

`mappings/legacy_to_current.yaml` covers all 713 leaves of the legacy JSON Schema.
`mappings/omics_to_current.yaml` covers all 252 fields of the omics template. Each entry maps a source path
(exact, or a `prefix.**` pattern) to a status:

| Status | Meaning |
| --- | --- |
| `mapped` | Same meaning; the value is copied as is |
| `merged` | The value lands in a field shared with other origins (the field's `origin` lists this source) |
| `partial` | Only values that satisfy the target definition are copied (e.g. only verbatim snippets become `source_quote`); the rest go to the residue |
| `transformed` | The value is restructured; `transform` names how (`wrap_array`, `single_value_measurement`, `relation_claim`, `compose`, `resolve_reference`, `structure`, `split_records`) |
| `control` | The migrator reads the value to route, filter or resolve references (e.g. `is_inferred`, `section_id`, `relation_id`); no value is copied |
| `view_only` | Reconstructed only in the legacy projection |
| `unmapped` | Not migrated (pipeline state, governance, scores, translations); the value goes to the residue |
| `forbidden` | Must never be migrated (e.g. local paths, R020) |

Matching precedence: an exact entry wins; otherwise the longest covering entry. That is either a `prefix.**`
pattern or an exact entry for a free-form ancestor object (for example, `analyses[].key_results` covers its
data-defined keys). `bdc check` fails if a source leaf is uncovered, an entry is stale, a target field does not
exist, or a `merged` target does not list the source in its `origin`. Issue registers (`LEG-001` … `LEG-012`,
`OMX-001` … `OMX-010`, `MRG-001` … `MRG-004`) document each judgement call.

## Legacy v1 → records

```bash
bdc migrate legacy corpus.jsonl --out out/ --page-offset 2220 [--dataset-id D] [--source-file-sha256 H]
```

| Output | Content |
| --- | --- |
| `<stem>.migrated.jsonl` | Valid atomic records (`review_status: pending_review`, `qc_failure_codes` include `LEGACY_MIGRATED`) |
| `<stem>.migrated.errors.jsonl` | Items that could not become valid records (typically R001: no physical page or verbatim quote) |
| `<stem>.residue.json` | `unconsumed`: every non-empty leaf that was not migrated, with its mapping status and note; `review_candidates`: values of human-judgement (I) fields |
| `<stem>.migration.json` | Contract identity, mapping hash, options, counts, `consumed_leaf_paths`, `record_sources` (record ID → legacy path and legacy item ID) |

Routing: `relations[]` become claims with subject, predicate and object mentions (AMB-012). `conclusions[]`
become claims, with evidence taken from their supporting relations (`LEGACY_INDIRECT_EVIDENCE`).
`breed_entities.qtls[]` become observations (interval, PVE, LOD), and additive or dominance effects become
`analysis_result` records. Genes and traits with their own evidence become observations, and heritability
becomes an `analysis_result`. Each software tool in `analyses[]` becomes a method record, and each key result
an `analysis_result`.

Invariants (tested in `tests/test_migrations.py`):

- **Physical pages only.** Legacy pages are journal pages. Without `--page-offset`, no `source_page` is written,
  so every evidence record is rejected by R001 instead of being given a wrong page (AMB-029). With the offset,
  physical page = journal page − offset.
- **Verbatim only.** A snippet containing `...` or `…` is not verbatim (`LEGACY_SNIPPET_NOT_VERBATIM`). All
  migrated quotes are marked `LEGACY_QUOTE_UNVERIFIED` until they are checked against the PDF.
- **Never infer.** `is_inferred: true` relations are skipped. Predicate labels, polarity, mechanisms and entity
  types are human-judgement fields, so they go to `review_candidates` and never into records. GWAS statistics are
  never stored as LOD (LEG-004): LOD is taken only when the producing analysis is QTL or linkage mapping.
- **Exact unit conversion.** cM goes to `*_cm`; bp, kb and Mb are converted exactly to integer bp
  (`LEGACY_INTERVAL_UNIT_CONVERTED`); anything else goes to the residue (LEG-011).
- **Nothing silently dropped.** Every non-empty leaf is either consumed (through a transfer or `control` entry)
  or listed in the residue.

The example `sources/legacy_v1/breeding_jsonl_example.jsonl`, migrated with offset 2220, is checked in under
`examples/migration/legacy_v1/`. It yields 13 valid records. 12 items are rejected: legacy `analyses[]`
carry no evidence spans, so their method and key-result records fail R001; `relations[1]` has no resolvable
verbatim evidence; and one cross-validation fold count is below the schema minimum. It also yields 7
review candidates, and the remaining leaves are listed in the residue.

## Omics v2 → records

```bash
bdc migrate omics instances.jsonl --out out/ [--record-kind analysis_result] [--dataset-id D]
```

Input is one filled template instance per line (or a JSON array or object). `null` values are omitted
(OMX-008). `record_kind` comes from `basic_identity.record_type` when it is a valid code; otherwise it comes from
`--record-kind`, or the instance is rejected (OMX-002). `mapped`, `merged` and `partial` entries, and
`transformed` entries with `wrap_array` or `single_value_measurement`, are copied when the value fits the target
field. Anything else goes to the residue. If two source leaves compete for one field with different values,
the result is `OMICS_FIELD_CONFLICT`. The template itself, being all `null`, migrates to nothing. That is correct
behaviour, not a failure to fix. `examples/migration/omics_v2/` shows a filled synthetic instance.

## Merged v2 → records

```bash
bdc migrate merged sources/merged_v2/breeding_jsonl_example_v2.json --out out/merged --page-offset 2220
# Other inputs: a JSON document, JSON array, or JSONL. For physical pages, explicitly use --page-offset 0.
```

`mappings/merged_to_current.yaml` accounts for all 1,022 leaves of the archived schema. This mapping includes
retained/unmapped data: coverage does not mean every source field can be emitted. The findings about the
source and the scope of the import are in `docs/source_analysis.md` (section 2.4 and merge decision 7).

The existing paper-content routes are reused. `observations[]` produces phenotype, environment, genotype or
omics observations. Explicit `sample_ref` / `assay_ref` values resolve sample and assay metadata, including
biological/technical replicate IDs and verbatim sampling time. Each observation uses its own evidence;
sample evidence and document-level source locations cannot replace the observation's quote. `assets[]`
produces asset manifests. Truncated checksums fail target validation rather than being silently removed.

Unit rows require a unique valid parent document **in the same input file**, before or after the row.
Only document metadata and referenced sample/assay context are inherited; parent observations and assets
are not copied into the child. Derived `transform` rows and skill-runtime `tool_spec` rows are retained and
reported as unsupported, since source references and runtime state cannot be treated as paper evidence.
Unresolved external sample/assay references retain their IDs and receive a review flag; ambiguous local
references, conflicting values, and explicit assay/sample membership mismatches reject the candidate.

Timestamp conversion to UTC is restricted to explicit time zones. Sampling time remains verbatim and
separate from observation time. Single-element string arrays may be unwrapped for scalar fields; multi-value
omics annotations are retained instead of arbitrarily choosing or joining values. All accepted records remain
`pending_review`, and unverified quotes are flagged `MERGED_QUOTE_UNVERIFIED`.

The four outputs use the same suffixes as other migrators. `migration.json` adds concrete `consumed_paths`
with input instance numbers and source/parent IDs in `record_sources`; `residue.json` retains all nonempty
unconsumed source values and review candidates. Invalid source rows are preserved whole in the residue and
error detail. The complete input file is loaded to resolve parents; use bounded batches for large collections.

The archived synthetic example produces **18 accepted records and 14 rejected candidates** with offset 2220:
13 existing paper-content records, four new observations, and one asset manifest. Two of the rejections are
assets with truncated SHA-256 strings; the other 12 arise from the inherited paper-content routes (missing
usable evidence or invalid values). These are structural validation results, not verification against a PDF.
The generated artifacts are checked in under `examples/migration/merged_v2/` and regenerated by `make examples`.

## Derived views: `document_bundle`, the legacy projection and `bdc derive`

```bash
bdc bundle paper.jsonl                 # -> paper.bundle.json   (schemas/runtime/document_bundle.schema.json)
bdc bundle paper.jsonl --legacy-v1     # -> paper.legacy_v1.json (validated against the legacy JSON Schema)
pdf2jsonl paper.pdf ... --bundle       # writes the bundle next to the pipeline outputs
```

A **document_bundle** groups records by `source_id` and holds the following. It is a view and is never
written back:

- document-level values shared by all of the source's records;
- record IDs by kind;
- an entity name index;
- an evidence index (page / section / table / quote → record IDs);
- the records themselves, unchanged.

The **legacy v1 projection** rebuilds the old one-line-per-paper layout from records, for consumers that still
read it. It is lossy by design. Entity and relation IDs are regenerated in the legacy formats (`gene:1`,
`rel:<record_id>`, `clu:<record_id>`, …). Pages are physical pages. Items whose legacy-required values do not
exist in the records are skipped and listed in `skipped` rather than invented; for example, a relation without
a predicate code, or a document type the paper does not state. Every projection states
`valid_against_legacy_schema` and the legacy schema errors, if any.

The bundle's document-level fields and entity index are chosen by `key_role` (`source_identity`,
`bibliographic` and document-level `entity_mention` fields), so a new catalog field lands in the right place
without a code change.

**`bdc derive`** turns records into the Function 3 targets: relational tables (CSV), explicit statements,
knowledge-graph triples and a property graph, an entity-annotated corpus and cloze QA seeds. Like the bundle it
is a view. It places every field by its `key_role`, never pairs name and ID arrays by position, and reads
statements and anchors from the hooks the records carry instead of parsing text. Imported records derive the
same way; they simply carry fewer hooks until a reviewer or a re-extraction adds them. See `docs/downstream.md`.

```bash
bdc derive paper.jsonl --out derived/
# -> derived/paper.tables/*.csv, paper.triples.jsonl, paper.graph.json, paper.corpus.jsonl, paper.qa.jsonl
```
