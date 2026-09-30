# What every key is for: roles, functions and the evidence chain

A record is metadata with four jobs. The data owner stated them in `sources/project/record_functions.md`:

1. serve the data needs of **Topic 2** (the breeding scientific agent);
2. serve the data needs of **Topic 3** (model and tool skills);
3. make it easy to turn records into **knowledge graphs, relational databases, QA pairs, corpora and triples**,
   which needs some extra fields;
4. support **our own future iterations**.

The research contents of Topics 1–3 (`sources/project/research_contents.md`) turn these four jobs into concrete
facets. Function 4 is Topic 1, the team that maintains this repository: data standards and quality evaluation, ontology
construction, and knowledge fusion (confirmed by the data owner, AMB-032).
This page explains how the catalog records which key serves which job and why, what the repository added
for functions 2–4, and how to use the derived views and the evidence-chain audit.

The generated reference, with one row per key, is `docs/generated/field_functions.md`. The CSV dictionary
`docs/generated/field_dictionary.csv` carries the same information as columns.

## Annotations on every field

Every field in `field_catalog/field_catalog.yaml` carries:

| Annotation | Required | Meaning |
| --- | --- | --- |
| `key_role` | yes | What the key does in a record. It is one of 25 roles in 6 families (`codes.key_role`). Each role declares its projection into a knowledge graph, relational tables, triples and QA/corpora, plus the facets it feeds for each function. |
| `serves` | yes | Which of the four functions the key serves (`codes.function`): `topic2`, `topic3`, `derivation`, `iteration`. |
| `card` | when stated | The Topic 2/3 card the field flows into: `hypothesis`, `experiment_design` or `result_analysis` (`codes.card`). |
| `argument_role` | when it applies | The field's element in an argument, after TRACE (see below): claim, data, warrant, backing, qualifier, rebuttal, monitoring or evaluation. |

The facets a field feeds are **not** stored per field. They are computed as the facets of its `key_role`,
restricted to the functions in `serves`. Changing a role therefore changes every field with that role
consistently.

### Functions and their facets

| Function | Facets (taken from the research contents) |
| --- | --- |
| `topic2` Topic 2: scientific agent | `reasoning` (knowledge state, hypothesis generation, causal inference), `planning` (task decomposition, experiment scheduling), `memory` (long-range knowledge, mid-range experiment state, short-range context), `execution` (tool calls, result verification, strategy correction) |
| `topic3` Topic 3: skills | `interface` (standard inputs, outputs, parameter semantics), `orchestration` (workflow composition), `output` (results and visualisation), `registry` (skill registration centre), `cards` (hypothesis → experiment design → result analysis card flow) |
| `derivation` Function 3 | `kg`, `rdb`, `triple`, `qa`, `corpus` |
| `iteration` Topic 1 / our iteration | `standard` (data standards, metadata specification), `quality` (quality evaluation), `ontology` (gene–trait–environment–variety ontology), `fusion` (extraction, entity alignment, conflict resolution, dynamic update), `traceability` (every value traceable to its source and contract version) |

### Source statements versus repository additions

The v3 baseline names consumers in two places:

- each group's description, recorded as the group's `serves` (`agent` → `topic2`, `skills` → `topic3`,
  `transform` → `derivation`);
- each field's `downstream_zh` column.

`codes.function.*.downstream_labels` lists the labels that map the column to functions. For example,
`课题二` maps to `topic2`, `图谱`, `GraphRAG`, `语料` and `问答` map to `derivation`, and `课题一` and `数据治理` map to
`iteration`. `全部` maps to all four functions and `全部转化` maps to `derivation`. Labels are matched longest
first, so `全部转化` is not read as `全部`.

Functions derived this way are **source functions**. `bdc check` enforces the following:

- a field's `serves` must contain every source function, so the repository can add functions but never drop
  one the source states;
- a field's `card` must equal the card named by `downstream_zh`, if the column names one;
- every served function must receive at least one facet from the field's role;
- every `verified` field must map to at least one source function.

Functions that are not source functions are **repository additions**. The generated reference marks them
with ⁺, and the CSV lists them in `serves_added`. Fields added since 3.1.0 have no `downstream_zh`, so all their
functions are additions. AMB-032 records this split for the data owner to confirm.

`derivation` marks only the keys that shape a derived structure: nodes, edges, qualifiers, evidence IDs,
source location, training split and licence. Every field still travels with its record into a table row or a
node property.

## Function 3 in practice: `bdc derive`

```bash
bdc derive out/paper.jsonl --out derived/
# derived/paper.tables/{records,sources,record_entities,record_links,record_values}.csv
# derived/paper.triples.jsonl   derived/paper.corpus.jsonl   derived/paper.derive.json
```

The exporter (`src/breeding_contract/derive.py`) reads no field list from code. Each field lands where its
`key_role` says:

| Output | Built from | Notes |
| --- | --- | --- |
| `records.csv` | every scalar field except source metadata | one row per record |
| `sources.csv` | `source_identity` and `bibliographic` roles | one row per `common.source_id` |
| `record_entities.csv` | `entity_mention` and `entity_id` roles, plus `transform.entity_links` | the entity type comes from the field name, e.g. `gene_names` → `gene`. The exporter never pairs `*_names` with `*_ids` by position (AMB-034); explicit pairs come only from `entity_links`. |
| `record_links.csv` | `record_link` array fields | each link keeps its `argument_role`: `data` for evidence links, `warrant` for method links |
| `record_values.csv` | remaining arrays | one row per item |
| `triples.jsonl` | all of the above | see the list below |
| `corpus.jsonl` | `common.source_quote` | one chunk per distinct (source, page, quote), with the IDs of every record it supports, plus licence and access level |

How `triples.jsonl` is built:

- Each record is a node `rec:<record_id>` with an `rdf:type`.
- Entity mentions become typed nodes `ent:<type>/<normalised mention>`.
- Identifiers are typed `iri` only when they already are one (a scheme or CURIE, e.g. `doi:…`). Bare accessions,
  DOIs and hashes are typed `id`, so the consumer applies its own namespace policy.
- `transform` subject/predicate/object becomes a statement that carries polarity, qualifiers and evidence type.
  A statement end without a reviewed type takes its type from the record's own entity fields when exactly one
  of them lists the same mention. For example, `qPH7.1` in `common.qtl_names` gives `ent:qtl/qph7.1`, which
  joins the statement to the entity graph.
- A statement without a reviewed predicate is written as `bdc:unlabelled_relation` rather than guessed.

QA pairs are not generated. The `transform.qa_*` fields are availability G, produced downstream. The corpus
gives them citable units, and `support_ids` gives them the records a question may cite.

## Function 2 and the evidence chain (after TRACE)

TRACE (Kim & Yang, ICML 2026, arXiv:2605.29656; code at github.com/hyyangkisti/trace) evaluates reasoning by
labelling each step with Toulmin's six elements (claim, data, warrant, backing, qualifier, rebuttal) and
Flavell's two metacognitive elements (monitoring, evaluation). It then checks which combinations and transitions
form sound structure.

Topic 2 needs the same structure in its inputs. A hypothesis or result-analysis card is only as good as the
chain from a claim to the data and methods behind it, including the author's hedges and stated limitations.

We reviewed the contract through this lens. Records are already structured, so the elements are annotations
on fields (`argument_role`, AMB-033); they are not labels predicted by a model. The review found four gaps, and
3.2.0 closes them:

| Gap | Addition |
| --- | --- |
| A hedge such as "suggesting a possible pleiotropic effect that requires validation" was lost: downstream, a hypothesis read as a fact | `agent.claim_qualifier_text` (D, verbatim) and rule R032 (warning): a claim whose quote hedges should keep the qualifier. The hedge lexicon is a repository proposal (AMB-035). |
| Limitations stated by the authors had no verbatim field, only the extractor's `agent.uncertainty_note` (I) | `agent.stated_limitations` (D, rebuttal) |
| A result could not point to the method that produced it | `skills.method_record_ids` (N, warrant) |
| Evidence links could dangle silently | rule R031 (warning, new dataset rule kind `references_resolve`) |

### Links between candidates

The extraction model cannot know record IDs, which the pipeline computes. The profile therefore declares
`record_links` (`profiles/pdf_extraction.yaml`), and candidates carry a local `ref` plus `links`:

```json
{"ref": "a_lod", "record_kind": "analysis_result", "links": {"method": ["m_icim"]}, ...}
{"ref": "c_pve", "record_kind": "claim", "links": {"evidence": ["a_lod"]}, ...}
```

The pipeline resolves references to record IDs after every candidate has passed evidence checks. A reference
to a rejected candidate (e.g. one whose quote is not found), to itself, or to the wrong kind (a method link that
does not point at a method) is dropped. The linking record gets a warning (`CANDIDATE_LINK_*`) and
`pending_review`. Nothing is invented for it.

### The audit: `bdc audit` and `argument_structure`

`bdc audit records.jsonl`, and the `argument_structure` block of every pdf2jsonl validation report, list each
record that asserts something:

- the elements it states itself;
- the elements reachable through its links, up to three hops. A linked record contributes its data, warrant
  and backing, and is itself data (or, for a method link, a warrant).

Flags are review hints:

| Flag | Meaning |
| --- | --- |
| `NO_DATA` | no quote, observation, statistic or linked record |
| `NO_WARRANT` | no statistical test, evidence type or linked method anywhere in the chain |
| `QUALIFIER_NOT_CAPTURED` | the quote hedges but the qualifier text is missing (R032) |
| `HEDGED_STATEMENT_USED_AS_DATA` | a hedged claim supports another claim, so uncertainty compounds. Scope qualifiers such as `applicable_population` narrow a claim without weakening it and do not count. |
| `UNRESOLVED_LINK` | a link points outside the record set |

The audit produces **no score**. TRACE itself notes that fluent structure can rest on wrong premises. The audit
says what is present and connected, never whether a conclusion is true.

In the synthetic example, the effect claim ("increased plant height by 8.6 cm") is flagged `NO_WARRANT`. The
paper does report the method, but the candidate does not link it, so a reviewer sees the gap. The abstract's
variance claim reaches a warrant through LOD result → ICIM method.

## Function 4 / Topic 1: iteration and knowledge fusion

| Need (research contents) | Fields |
| --- | --- |
| Metadata specification, quality evaluation | `lifecycle` role (run IDs, QC codes, missing-field audit, review status). `common.extraction_profile` records which profile the record was extracted under, so "not asked for" can be told apart from "not found". |
| Conflict resolution | `common.conflict_record_ids` (v3) plus `common.conflict_resolution_status` (I, vocabulary `conflict_resolution_status`: `unresolved`, `context_dependent`, `retained`, `superseded`; codes proposed) |
| Dynamic update | `common.record_version` (v3), `common.record_updated_at` (N, ISO 8601 UTC), and `common.replaces_record_ids` (N): a re-extraction whose anchor changed points to the records it replaces, so graph, QA and table references can be migrated. Old records are never deleted (AMB-036). |
| Entity alignment, ontology | `entity_alignment` role; `transform.entity_links` (per-mention ID, type, status and source) |

Record IDs are now independent of candidate order and of the section heading. The anchor is page, table/figure,
row key and column key; duplicates are numbered by canonical field order. A re-run that only reorders
candidates or respells a heading therefore keeps every ID (see `docs/architecture.md`).

## Changing annotations

- A new field needs `key_role` and `serves`. `bdc check` rejects unknown codes, a source function missing from
  `serves`, a card that contradicts `downstream_zh`, and a served function for which the field's role names no
  facet.
- Adding or changing annotations is a MINOR change: it does not affect validation of existing records.
- A new role, function or facet is added under `codes` in the catalog. The generated reference and the site
  pick it up.

## Open points for the data owners

| ID | Question |
| --- | --- |
| AMB-032 | Iteration = Topic 1 is confirmed: this repository is Topic 1's. Still open: the functions and cards the repository added to each field. |
| AMB-033 | Confirm the TRACE element of each field. |
| AMB-034 | Confirm the `entity_links` item structure. |
| AMB-035 | Confirm the hedge lexicon used by R032. |
| AMB-036 | Confirm the conflict-resolution codes and the replace-don't-delete policy. |
