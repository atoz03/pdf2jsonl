# Migration and derived views

Two earlier designs have data in circulation: **legacy v1** (one paper per JSONL line) and the **omics v2
template**. Neither is a second schema in this repository. Each is a *mapping* onto the current contract
(`mappings/*.yaml`), plus a converter that produces ordinary atomic records validated like any other.

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
`OMX-001` … `OMX-010`) document each judgement call.

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

**`bdc derive`** turns records into the Function 3 targets: relational tables (CSV), knowledge-graph triples
(JSONL) and an evidence corpus (JSONL). Like the bundle it is a view. It places every field by its `key_role`,
never pairs name and ID arrays by position, and writes a statement without a reviewed predicate as
`bdc:unlabelled_relation` rather than guessing. See `docs/field_functions.md` for the layout.

```bash
bdc derive paper.jsonl --out derived/  # -> derived/paper.tables/*.csv, paper.triples.jsonl, paper.corpus.jsonl
```
