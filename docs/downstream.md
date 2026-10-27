# The record as a hub: paper → JSON → knowledge graph, workflow, corpus, QA, tables

```
                                            ┌─► statements.csv, triples.jsonl, graph.json   knowledge graph
 paper ──► records (JSONL, this contract) ──┼─► workflow.json                               research workflow
 (one or several files)                     ├─► corpus.jsonl                                retrieval / training corpus
            one fact per line, with hooks   ├─► qa.jsonl                                    QA seeds
                                            └─► tables/*.csv                                relational tables
```

A record is the common intermediate form. It is extracted once and consumed many times, so it has to carry
what each consumer needs **as fields**, not as text the consumer parses again. This document lists those
fields, the "hooks", says who fills each one, and shows what `bdc derive` builds from them. It also says how
the forms of the same knowledge (source files, records, graph, workflow, corpus, ontology) trace back to each
other, and what happens when a paper is incomplete. The hooks added in 3.4.0 (AMB-038) and 3.5.0 (AMB-039,
AMB-041) are provisional.

## Container versus hub

Before 3.4.0 a claim record looked like this to a graph builder:

```json
{"agent":  {"finding_text": "qPH7.1 … was significantly associated with plant height in both environments."},
 "common": {"qtl_names": ["qPH7.1"], "trait_names": ["plant height"], "source_quote": "qPH7.1 explained 23.5% …"}}
```

The facts are all there, but a consumer still had to work out the rest itself:

- which of the listed entities is the subject and which the object;
- what the relation is. The only predicate fields were `transform.predicate_label` (human judgment, never
  shown to the model) and `transform.predicate_id` (ontology ID), so an extracted statement had none;
- where in the quote each entity stands, which a corpus needs for entity annotation and a QA set needs for
  answer spans.

That is a second extraction pass over free text, with a different tool and different errors for every
consumer. The same record now states all of it:

```json
{"transform": {
   "subject_mention":   "qPH7.1",
   "predicate_mention": "was significantly associated with",
   "object_mention":    "plant height",
   "predicate_code":    "qtl_associated_with_trait",
   "relation_nature":   "associational",
   "relation_resolution": "coded",
   "predicate_start_offset": 54, "predicate_end_offset": 87,
   "entity_links": [
     {"mention": "qPH7.1",       "source_field": "common.qtl_names",   "entity_type": "qtl",
      "start": 0,  "end": 6,   "relation_role": "subject"},
     {"mention": "plant height", "source_field": "common.trait_names", "entity_type": "trait",
      "start": 88, "end": 100, "relation_role": "object"}]}}
```

## The hooks

| Hook | Fields | Filled by | Read by |
| --- | --- | --- | --- |
| **Statement** | `transform.subject_mention`, `transform.predicate_mention`, `transform.object_mention` | the model (D), verbatim from the quote | graph edges, QA |
| **Entity markers** | `transform.entity_links[]`: `mention`, `source_field`, `entity_type`, `start`, `end`, `relation_role` | the pipeline (N), from the entity fields and the quote | graph nodes, corpus annotation, QA answer spans |
| **Relation anchor** | `transform.predicate_start_offset`, `transform.predicate_end_offset` | the pipeline (N) | corpus annotation, relation-extraction training data |
| **Normalised predicate** | `transform.predicate_code` → `transform.predicate_label` → `transform.predicate_id` | lexicon (N) → reviewer (I) → ontology alignment (N) | graph edge type |
| **Resolution** | `transform.relation_resolution` (`coded` / `ambiguous` / `no_cue` / `negated`) | the pipeline (N) | review queue, vocabulary-coverage reports (`counts.relation`) |
| **Nature** | `transform.relation_nature` | the pipeline (N): the reviewed `predicate_label`, else the matched `predicate_code` | whether an edge may guide an intervention |
| **Claim strength** | `transform.claim_strength` (`causal_supported` … `causal_unverified`, `associational`, `structural`, `descriptive`) | the pipeline (N): nature × `transform.relation_evidence_type` | whether a causal wording is backed by intervention-level evidence (R038) |
| **Validation status** | `transform.validation_status` (`candidate` / `experiment_reported`) | the pipeline (N): presence of `agent.validated_by_record_ids` | review queue, "is this still a candidate?" |
| **Evidence origin** | `transform.evidence_origin` (`review_report` for a review) and `agent.reported_citation_text` (D, the lead the review prints) | the pipeline (N) / the model (D) | keeping a paraphrase apart from a primary experiment |
| **Cited source items** | `transform.cited_source_items` (`Fig. S2`, `Table S1` …) | the pipeline (N), literal scan of the quote | tying a record to the supplementary part, and to `source_parts` |
| **Typed, aligned ends** | `transform.subject_type` / `object_type` (I), `subject_id` / `object_id` and `entity_links[].entity_id` (N) | reviewers and entity alignment (Topic 1) | graph node identity |
| **Qualifiers** | fields of role `condition` and `context_key` (population, environment, year, stage, treatment …), `transform.relation_qualifiers` | the model (D) / the pipeline (N) | statement qualifiers, QA answer scope |
| **Hedge and limits** | `agent.claim_qualifier_text`, `agent.stated_limitations` | the model (D), verbatim | every consumer: a hedged statement is not a finding |
| **Record links** | `agent.evidence_record_ids`, `skills.method_record_ids`, `agent.tests_record_ids`, `agent.addresses_record_ids`, `agent.prerequisite_record_ids`, `agent.validated_by_record_ids` | the pipeline (N), from candidate `links` | graph edges between records, the workflow, multi-hop QA |
| **Workflow role** | `agent.statement_role`, `agent.step_condition` | the model (D) | the stage of a node in the workflow (`docs/workflow.md`) |
| **Evidence** | `common.source_id`, `source_part`, `source_page`, `source_quote`, `source_span`, `source_locator` | the pipeline (N) and the model (D) | provenance of every derived row |
| **Stable IDs** | `common.record_id`, `common.source_id` | the pipeline (N) | joins; chunk, statement and QA IDs are hashes of these |

Three rules keep the hooks honest:

- **The model copies, the pipeline computes.** The model adds three verbatim strings. Offsets, entity types,
  relation roles, the predicate code and the resolution are deterministic functions of the record and the quote
  (`src/breeding_contract/relations.py`, fill rule `relation_anchors`), so re-running them never changes the
  meaning of a record.
- **Never infer.** A mention that does not occur literally in the quote gets a marker without offsets. A
  predicate that matches no cue, or more than one code, gets no `predicate_code` — and since 3.7.0 the record
  says which of the two it was (`transform.relation_resolution`, AMB-043), so the queue can tell "the vocabulary
  misses this verb" from "register the entity mention and the tie resolves". Neither does a negated one: a
  negation word in the predicate, or in the quote between the two ends, leaves the statement verbatim
  (`relation_resolution: negated`), so "was not associated with" never becomes `qtl_associated_with_trait`. A
  record whose quote relates nothing has no statement and no resolution.
- **Checked, not trusted.** `R034` verifies that every offset points at its mention; `R033` flags a statement
  that has both ends but no predicate.

### The predicate ladder

A statement keeps every level it has reached, and `bdc derive` reports the highest one as `predicate_status`:

| `predicate_status` | Predicate written | Comes from |
| --- | --- | --- |
| `ontology` | `transform.predicate_id` | alignment to a relation ontology |
| `reviewed` | `bdc:<transform.predicate_label>` | a reviewer chose the code |
| `lexicon` | `bdc:<transform.predicate_code>` | a cue of exactly one code occurs in the predicate, and neither end's type contradicts the code |
| `verbatim` | `bdc:stated_relation`, with `predicate_mention` | only the words of the paper |
| `unlabelled` | `bdc:unlabelled_relation` | subject and object without any predicate (flagged by R033) |

A consumer chooses its own threshold, e.g. load `reviewed` and above into the published graph and keep
`lexicon` and `verbatim` as candidates. The lexicon lives in `vocabularies/predicate_label.yaml` (`cues`,
`subject_types`, `object_types`). It is deliberately narrow: "was associated with" between a QTL and a trait is
coded, "increased" between an allele and a trait is not, because no code fits without interpretation. A cue
therefore names the words the relation is *stated* with, not the bare verb: "decreased the chalkiness" is coded,
"decreased" alone is not. The codes name positive relations only. Whether a statement is negative is recorded by
a reviewer in `transform.relation_polarity`; until then the negation is in `predicate_mention`, in the words of
the paper.

The ladder says how far a predicate has been resolved, not what it asserts. Whether the relation is causal or
merely associational is a third axis, recorded separately (AMB-042): `transform.relation_nature` derives from the
`nature` of the code, and `transform.relation_assertion_mode` (D) keeps the source's own wording. Only a causal
relation can directly guide an experiment, so R036 flags an associational relation stated flat with no evidence
and R037 flags a causal one with no evidence type. See [relation semantics](relation_semantics.md); a consumer
that filters edges by the ladder should filter by nature as well, or it will promote association to causation.

## What `bdc derive` builds

```bash
bdc derive out/paper.jsonl --out derived/
```

| Output | One row per | Built from |
| --- | --- | --- |
| `paper.tables/records.csv` | record | every scalar field except source metadata |
| `paper.tables/sources.csv` | source | roles `source_identity`, `bibliographic` |
| `paper.tables/record_entities.csv` | entity mention | roles `entity_mention`, `entity_id`; markers add type, offsets, relation role and aligned ID |
| `paper.tables/record_links.csv` | link between records | role `record_link`, with its `argument_role` |
| `paper.tables/record_values.csv` | array item | remaining arrays |
| `paper.tables/statements.csv` | statement | the statement hook: typed ends, predicate and its status, polarity, qualifiers, hedge, evidence, anchors |
| `paper.triples.jsonl` | triple | all of the above; a statement triple carries `statement`, `predicate_status`, `predicate_mention`, `qualifiers`, `hedge` |
| `paper.graph.json` | — | `{nodes, edges}`: entities, records and sources; statement, mention, link and provenance edges |
| `paper.corpus.jsonl` | distinct (source, page, quote) | the quote, the records it supports, entity offsets, statement IDs, licence, leakage group |
| `paper.qa.jsonl` | answer span | cloze seeds: the quote with one anchored answer masked |
| `paper.workflow.json` | — | the research workflow: records as stages, record links as edges, step order, branch points, one trace per hypothesis, structural flags (`docs/workflow.md`) |
| `paper.derive.json` | — | row counts, the contract the views were built with, and their lineage: name and hash of the records file, its sources, the hash of every file written |

The exporter (`src/breeding_contract/derive.py`) reads no field list from code: every field lands where its
`key_role` says. The views are lossless for the values they carry and add none.

**Statements and graph.** A statement end resolves to the reviewed ID if there is one, else to the typed node
`ent:<type>/<normalised mention>` of its marker, else to a generic `ent:entity/…` node. The statement ID is
`transform.graph_statement_id` when set, otherwise a hash of source, ends, predicate and qualifiers, so the
same statement under different conditions stays two statements. Entity nodes are keyed by type and mention; an
aligned ID is a node property. Merging nodes is a fusion decision and is left to the consumer.

**Corpus.** Each chunk is keyed by the `transform.chunk_*` field names and carries `entities`
(`start`, `end`, `mention`, `entity_type`, `entity_id`), so it is an annotated sentence as it stands.
`leakage_group_id` is one group per source: chunks and QA items of one paper must fall into the same split.

**QA seeds.** A record that states a relation or makes an assertion yields one cloze item per anchored entity
and per numeric statistic printed in its quote:

```json
{"qa_id": "qa_…", "qa_form": "cloze", "qa_slot": "object",
 "qa_seed_question": "qPH7.1 explained 23.5% of the phenotypic variance and was significantly associated with ____ in both environments.",
 "qa_seed_answer": "plant height", "answer_type": "trait", "answer_start": 88, "answer_end": 100,
 "qa_support_ids": ["rec_…"], "qa_reasoning_path_ids": ["stm_…"], "qa_difficulty": "single_hop",
 "qa_review_status": "candidate", "chunk_id": "chk_…", "leakage_group_id": "lkg_…"}
```

The answer is always a span of the quote and the supporting records are always cited, so an item can be
checked without the paper. Keys are the `transform.qa_*` field names: a reviewed item can be stored as those
fields.

## Source parts and incomplete papers

A paper is often several files: the main text, supplementary materials, an appendix. A library may hold only
some of them, and the missing part may be the one with the materials and methods.

**Several files, one source.** Further files are given with `--supplement` (repeatable). All parts share one
`common.source_id`. Evidence names its part and the physical page within that file:

```json
{"evidence": {"part": "supplement", "page": 1, "quote": "Twelve-day-old seedlings were treated at 42 C for 14 h …"}}
```

The record carries `common.source_part` (`main_text`, `supplement`, `appendix`, `other`), and its locator and
span start with `part=supplement;`. Each file gets its own `asset_manifest` record with its hash. Records of
the main text keep the locators and the IDs they had before parts existed, so adding a supplement later
changes no existing ID. A further file is a supplement by default; `--supplement FILE:appendix` labels a 附录 or
an author appendix instead, and the part labels follow the kind (`supplement`, `supplement_2` … `appendix`,
`appendix_2` …), so `source_part: appendix` is reachable from a run (3.7.0, AMB-044).

**Missing parts are detected, not guessed.** The pipeline scans the main text for references to supplementary
items ("fig. S2", "Table S1", "supplementary materials", "appendix") and compares them with what was supplied:

```json
"source_parts": {
  "provided":   [{"part": "main", "source_part": "main_text", "file_name": "paper.pdf", "page_count": 2, …}],
  "referenced": {"supplement": {"mentions": 4, "pages": [2], "items": ["Fig. S1", "Fig. S2", "Fig. S3"]}},
  "parts": [
    {"part": "supplement", "source_part": "supplement", "supplied": false, "files": [], "page_count": 0,
     "text_pages": 0, "text_chars": 0, "state": "referenced_not_supplied", "state_label_zh": "正文引用但未提供",
     "referenced": {"mentions": 4, "pages": [2], "items": ["Fig. S1", "Fig. S2", "Fig. S3"]}},
    {"part": "appendix", "source_part": "appendix", "supplied": false, "files": [], "page_count": 0,
     "text_pages": 0, "text_chars": 0, "state": "not_referenced", "state_label_zh": "未引用"}],
  "missing":    ["supplement"],
  "items_not_found": ["Fig. S1", "Fig. S2", "Fig. S3"],
  "warnings":   [],
  "complete":   false}
```

`parts` gives every part kind the text references or the run supplies one of seven states — `supplied_parsed`,
`supplied_no_text` (the file is here but has no text layer to search), `supplied_not_referenced` (given, never
cited), `supplied_items_not_found` (the file is here and readable, but an item the text cites is not in it),
`referenced_not_supplied`, `in_main_pages` (the cited items carry captions in the pages supplied: it is the same
file) and `not_referenced` — with its files, page count and how many pages carry text. A run-level `warnings`
entry marks a supplied part without text (`SOURCE_PART_NOT_PARSED`), one the text never cites
(`SOURCE_PART_UNREFERENCED`) or one whose cited item was not located (`SOURCE_PART_ITEM_NOT_FOUND`); none of them
is a per-record problem, so none of them puts a record in review. Missing parts are judged per part: supplying a
supplement no longer hides a missing appendix, and vice versa.

This block is in the validation report; the manifest repeats `missing`, `complete` and the state of each part.
Item labels ("Fig. S2") are one pool for all further files, because a quoted label cannot be attributed to the
supplement or to the appendix; an item is therefore reported only when no further file was supplied, or when a
supplied file has no text. Three things follow from an incomplete source:

- A record whose quote cites an item of the missing part is marked `SOURCE_PART_UNAVAILABLE` and stays
  `pending_review`: its statement rests on data nobody has seen. If the part was supplied without a text
  layer, the code is `SOURCE_PART_NOT_PARSED` instead — the remedy is a text layer (`--text-layer`), not the
  file, and the reviewer should not be told to look for a file that is already there.
- A field that a rule expects and such a record lacks is audited in `common.missing_fields` with the reason
  `source_part_unavailable` instead of `not_located`, so "not found in the paper" and "possibly in a part we
  do not have" stay apart.
- Workflow flags such as a result without a method are expected, and the report says why.
- A field that a rule expects and such a record lacks is audited in `common.missing_fields` with the reason
  `source_part_unavailable` instead of `not_located`, so "not found in the paper" and "possibly in a part we
  do not have" stay apart.
- Workflow flags such as a result without a method are expected, and the report says why.

Nothing is filled in for the missing part. When the supplement arrives, the paper is extracted again with both
files; records of the main text keep their IDs and the new records join them. The example shows both runs of
one paper: `examples/output/incomplete/` (main text only) and `examples/output/` (with the supplement).

## Representations and how they trace back

The same knowledge exists in several forms. Three relations connect them, and each is carried by fields or by
a report, never by a naming convention:

```
 raw data / datasets ◄──────────┐
 source files (PDF parts) ◄──── records ◄──── views: graph, statements, workflow, corpus, QA, tables
        derived from               │   derived from
                                   ├── generated by ──► run, contract version, profile, verifier
                                   └── aligned to ────► ontology (ID and version), external databases
```

| Relation | From → to | Carried by |
| --- | --- | --- |
| **derived from** | record → source file and place | `common.source_id`, `source_part`, `source_page`, `source_quote`, `source_span`, `source_file_sha256`; one `asset_manifest` record per file |
| | view row → record | `record_id` on every table row, triple, graph edge, corpus chunk (`chunk_support_ids`), QA item (`qa_support_ids`) and workflow node |
| | view file → records file | `lineage` in `paper.derive.json`: file name and hash of the records, source IDs, hash of every output |
| | record → earlier record | `common.record_version`, `common.replaces_record_ids` |
| **generated by** | record → run | `common.extraction_run_id`, `extraction_profile`, `extraction_method`, `schema_version`; the run manifest (input hashes, contract hash, model, pipeline version) |
| | record → verification | `common.verification_run_id`; the verification report |
| | view → contract | `contract` in `paper.derive.json` |
| **aligned to** | entity, predicate → ontology | `transform.subject_id` / `predicate_id` / `object_id`, `entity_links[].entity_id`, with `transform.ontology_id` and `transform.ontology_version` |

Two consequences:

- **Records are the only editable layer.** A graph, a workflow or a corpus is never corrected by hand: the
  record is corrected (or re-extracted) and the views are derived again. The lineage hashes show whether a
  view still belongs to its records.
- **An ontology is a reference frame, not a container.** A domain ontology and one built for a single class of
  papers can both be used: an alignment names the ontology it used (`transform.ontology_id`) and its version.
  Records do not change when an ontology does; only the alignment fields are filled again.

One link is still missing. A record that reports a result of a dataset (a genotype matrix, a phenotype table)
cannot yet point at that dataset as an asset: `skills.input_asset_refs` and the dataset ID fields are reserved
for future sources (AMB-041).

## What stays downstream

The hooks make these steps mechanical or reviewable; they do not perform them.

| Step | Why it is not in the record | Where it lands |
| --- | --- | --- |
| Natural-language questions, multi-hop and unanswerable QA | generation, availability G | `transform.qa_*`, starting from the cloze seeds and the record links |
| Entity alignment to ontologies and databases | Topic 1 fusion, needs external sources | `entity_links[].entity_id`, `transform.subject_id` / `object_id` |
| Entity types of ends that no entity field lists | human judgment (I) | `transform.subject_type` / `object_type` |
| Reviewed predicate, polarity, evidence type | human judgment (I) | `transform.predicate_label`, `relation_polarity`, `relation_evidence_type` |
| Train / validation / test split | a dataset decision | `transform.corpus_split`, one split per `leakage_group_id` |
| Hypotheses induced from the design | generation, not extraction | a separate step, marked by `agent.hypothesis_origin` (AMB-039) |
| Evidence strength, soundness of a design | expert judgment (I) | `agent.evidence_strength`; see `docs/review.md` |

## Adding a hook

A new consumer need becomes a field, never a parser in the consumer:

1. Add the field to `field_catalog/field_catalog.yaml` with the `key_role` that says where it projects.
2. If the model can copy it from the paper, it is availability D and reaches the brief through the profile.
   If it is computable from the record, add a named fill rule and declare it under the profile's `normalizers`.
3. If it has an invariant, add a rule so the validator checks it.
4. `bdc derive` picks the field up by its role. Only a new output form needs code.

## Open points for the data owners (AMB-038)

- The cue words and the subject/object types of each `predicate_label` code are repository proposals.
- `predicate_code` and `predicate_label` share one vocabulary on purpose, so a reviewer confirms or corrects a
  code instead of translating between two lists. Confirm that this is acceptable.
- One record carries one statement. A sentence relating several pairs becomes several records, which matches
  "one fact per line" but repeats the quote.
- Offsets count Unicode characters of `common.source_quote`, start inclusive, end exclusive.
- The negation words that block a predicate code (`NEGATION` in `src/breeding_contract/relations.py`) are a
  short list in code. It errs towards no code: "不同" is excluded, but any "not" between the two ends blocks.
