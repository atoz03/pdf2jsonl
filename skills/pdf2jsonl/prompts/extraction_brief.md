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

## Cross-field rules checked by the validator

{{rules_block}}

## Computed by the pipeline — never output these

{{system_fields_list}}
