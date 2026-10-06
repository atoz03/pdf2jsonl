# The record as a hub: paper → JSON → knowledge graph, corpus, QA, tables

```
                                            ┌─► statements.csv, triples.jsonl, graph.json   knowledge graph
 paper ──► records (JSONL, this contract) ──┼─► corpus.jsonl                                retrieval / training corpus
            one fact per line, with hooks   ├─► qa.jsonl                                    QA seeds
                                            └─► tables/*.csv                                relational tables
```

A record is the common intermediate form. It is extracted once and consumed many times, so it has to carry
what each consumer needs **as fields**, not as text the consumer parses again. This document lists those
fields, the "hooks", says who fills each one, and shows what `bdc derive` builds from them. The hooks added in
3.4.0 are provisional (AMB-038).

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
| **Typed, aligned ends** | `transform.subject_type` / `object_type` (I), `subject_id` / `object_id` and `entity_links[].entity_id` (N) | reviewers and entity alignment (Topic 1) | graph node identity |
| **Qualifiers** | fields of role `condition` and `context_key` (population, environment, year, stage, treatment …), `transform.relation_qualifiers` | the model (D) / the pipeline (N) | statement qualifiers, QA answer scope |
| **Hedge and limits** | `agent.claim_qualifier_text`, `agent.stated_limitations` | the model (D), verbatim | every consumer: a hedged statement is not a finding |
| **Record links** | `agent.evidence_record_ids`, `skills.method_record_ids` | the pipeline (N), from candidate `links` | graph edges between records, multi-hop QA |
| **Evidence** | `common.source_id`, `source_page`, `source_quote`, `source_span`, `source_locator` | the pipeline (N) and the model (D) | provenance of every derived row |
| **Stable IDs** | `common.record_id`, `common.source_id` | the pipeline (N) | joins; chunk, statement and QA IDs are hashes of these |

Three rules keep the hooks honest:

- **The model copies, the pipeline computes.** The model adds three verbatim strings. Offsets, entity types,
  relation roles and the predicate code are deterministic functions of the record and the quote
  (`src/breeding_contract/relations.py`, fill rule `relation_anchors`), so re-running them never changes the
  meaning of a record.
- **Never infer.** A mention that does not occur literally in the quote gets a marker without offsets. A
  predicate that matches no cue, or more than one code, gets no `predicate_code`. A record whose quote relates
  nothing has no statement.
- **Checked, not trusted.** `R034` verifies that every offset points at its mention; `R033` flags a statement
  that has both ends but no predicate.

### The predicate ladder

A statement keeps every level it has reached, and `bdc derive` reports the highest one as `predicate_status`:

| `predicate_status` | Predicate written | Comes from |
| --- | --- | --- |
| `ontology` | `transform.predicate_id` | alignment to a relation ontology |
| `reviewed` | `bdc:<transform.predicate_label>` | a reviewer chose the code |
| `lexicon` | `bdc:<transform.predicate_code>` | cue words + entity types of both ends match exactly one code of vocabulary `predicate_label` |
| `verbatim` | `bdc:stated_relation`, with `predicate_mention` | only the words of the paper |
| `unlabelled` | `bdc:unlabelled_relation` | subject and object without any predicate (flagged by R033) |

A consumer chooses its own threshold, e.g. load `reviewed` and above into the published graph and keep
`lexicon` and `verbatim` as candidates. The lexicon lives in `vocabularies/predicate_label.yaml` (`cues`,
`subject_types`, `object_types`). It is deliberately narrow: "was associated with" between a QTL and a trait is
coded, "increased" between an allele and a trait is not, because no code fits without interpretation.

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
| `paper.derive.json` | — | row counts and the contract the views were built with |

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

## What stays downstream

The hooks make these steps mechanical or reviewable; they do not perform them.

| Step | Why it is not in the record | Where it lands |
| --- | --- | --- |
| Natural-language questions, multi-hop and unanswerable QA | generation, availability G | `transform.qa_*`, starting from the cloze seeds and the record links |
| Entity alignment to ontologies and databases | Topic 1 fusion, needs external sources | `entity_links[].entity_id`, `transform.subject_id` / `object_id` |
| Entity types of ends that no entity field lists | human judgment (I) | `transform.subject_type` / `object_type` |
| Reviewed predicate, polarity, evidence type | human judgment (I) | `transform.predicate_label`, `relation_polarity`, `relation_evidence_type` |
| Train / validation / test split | a dataset decision | `transform.corpus_split`, one split per `leakage_group_id` |

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
