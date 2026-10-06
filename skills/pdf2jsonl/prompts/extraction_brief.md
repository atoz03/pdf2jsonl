# Extraction brief — {{contract_name}} {{schema_version}} · profile `{{profile_name}}` ({{profile_title}})

> Generated at runtime from the contract repository (release status: **{{release_status}}**).
> It is valid only for this contract version and profile. Never copy field lists from an older brief.

{{profile_description}}

## Task

Read the numbered page texts in `{{pages_file}}` and write `{{candidates_file}}`, a single JSON document that
validates against `{{candidate_schema_file}}`:

```json
{"extraction": {"method": "model", "model": "<your model id>", "backend": "agent"},
 "document":   { "<document field path>": "<value>" },
 "candidates": [ {"record_kind": "<kind>", "fields": { "<field path>": "<value>" },
                  "evidence": {"page": 3, "quote": "<verbatim text from page 3>"}} ]}
```

## Invariants (the validator rejects violations)

1. **Evidence or nothing.** Every candidate carries `evidence.page` (physical page from the page markers) and
   `evidence.quote`, copied verbatim from that page. Quotes that cannot be found in the PDF text are rejected.
2. **Atomic records.** One candidate = one independently reviewable statement, observation, method or result.
   A table row with several measured values becomes several single-value observations.
3. **Never infer.** Fill a field only when the paper states it. Omit everything else — no `null`, no `""`,
   no guesses, no values from background knowledge. Association is never upgraded to causation.
4. **Raw first.** Keep numbers and units exactly as printed in the raw-value fields; do not convert units or
   split ranges yourself — normalization is deterministic and done by the pipeline.
5. **Stay inside the profile.** Use only the field paths listed below, with the stated types. Fields not listed
   (identifiers, versions, locators, review status, normalized values, generated or externally sourced fields)
   are computed by the pipeline or by later stages and must not appear in your output.
6. Values from a controlled vocabulary must use the listed codes.
7. **State relations explicitly.** A relation between two entities is written as subject, verbatim predicate and
   object (see "Relations"), never left inside the finding text for later parsing.
8. **Keep the evidence chain.** A conclusion travels downstream (agent reasoning, knowledge-graph edges, QA
   answers) with its grounds, its hedges and its stated exceptions. Link it to the candidates it rests on, copy
   hedging words verbatim, and never drop or add a hedge (see the sections below).

## Record kinds you may produce

{{record_kinds_table}}

## Document-level fields (fill once under `document`)

{{document_fields_table}}

## Evidence keys (under `evidence`, required: `page`, `quote`)

{{evidence_roles_table}}

## Fields you may fill under `fields` ({{field_count}} fields; keys are the dotted paths)

{{extract_fields_table}}

## Controlled vocabularies

{{vocabularies_block}}

## Evidence chain (Toulmin elements, after TRACE)

Capture each element the paper states, in these fields, and nothing it does not state:

{{argument_block}}

- If the quote hedges the conclusion (may, suggests, possible, putative, requires validation, 可能, 推测), copy
  the hedging words verbatim into the Qualifier field that is listed for text. A hedged statement is not a finding.
- Limitations, exceptions or alternative explanations that the authors state go into the Rebuttal fields.
  Your own doubts do not; they belong to reviewers.
- Structure is not correctness: a complete chain does not make a claim true, so never complete a chain by
  inference.

## Relations (the hooks of knowledge-graph edges, corpora and QA)

When the quote itself relates two entities (a QTL and a trait, a gene and a tissue, a variety and its parent),
state the relation as one statement in the same candidate:

{{relation_block}}

- All three are copied from the quote. Also list each entity in its own entity field (the QTL among the QTL
  names, the trait among the trait names), spelled exactly as in the statement, so the pipeline can type it.
- One candidate carries one statement. A sentence that relates several pairs becomes several candidates.
- A negation is part of the predicate: copy "was not associated with", never only "associated with".
- Do not normalize the predicate and do not choose a relation code: the pipeline anchors every mention in the
  quote and derives the code from the verbatim words. A relation the quote does not state is not a statement.

## Linking candidates

{{record_links_block}}

## Cross-field rules checked by the validator

{{rules_block}}

## Computed by the pipeline — never output these

{{system_fields_list}}
