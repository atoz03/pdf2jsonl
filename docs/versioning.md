# Versioning

The **contract** is versioned, not the code. A contract version identifies one exact set of fields,
vocabularies, rules and profiles. The Python tooling (`breeding_contract`, `GENERATOR_VERSION`) and the Skill
runtime (`PIPELINE_VERSION`) have their own versions, and both are recorded in every manifest.

## Identity carried by every record

| Field | Value |
| --- | --- |
| `common.schema_name` | contract family, `breeding-literature-record` (since 3.1.0, AMB-013) |
| `common.schema_version` | exact resolved version, `MAJOR.MINOR.PATCH` without a `v` prefix (AMB-002) |

`validate_record(record)` validates each record against the version it declares, so files that mix versions
stay valid. A record never carries `latest`: the pipeline resolves the request first and writes the concrete
version. Development output carries `X.Y.Z-dev.<digest8>`, which can never be mistaken for a release.

## Semantic versioning rules

| Bump | When | Examples |
| --- | --- | --- |
| **MAJOR** | A record valid under the old version may become invalid or change meaning | field removed or renamed; type or availability changed; requirement tightened to `Y`; constraint added or tightened; code removed from an error-enforced vocabulary; enforcement raised to `error`; a new error rule (or warning → error) over existing fields; record kind or profile removed |
| **MINOR** | Additive changes | new fields, groups, vocabularies, codes, record kinds, profiles; warning rules; error rules over *new* fields only; `provisional` → `verified`; deprecation (with `replaced_by`) |
| **PATCH** | No effect on validation | wording, source references, ambiguity notes, documentation |

`bdc check` enforces the table mechanically (`src/breeding_contract/compat.py`). It compares every pair of
consecutive releases, and the working tree against the latest release. It fails when the declared bump is
smaller than the change set requires. Two things cannot be detected mechanically: a definition rewrite is
reported as `patch` with a reminder to confirm that the meaning is unchanged, and profile-internal changes
(roles, fill rules) are reviewed by hand.

Deprecation instead of removal: set `status: deprecated`, `deprecated_in`, and optionally `replaced_by`. The
validator then emits `FIELD_DEPRECATED` warnings. The field can be removed at the next major version.

## Releases

```
edit sources ─► bump VERSION ─► CHANGELOG "## [X.Y.Z] - YYYY-MM-DD" ─► bdc generate ─► bdc release ─► bdc check --strict
```

- `bdc release` compiles the working tree and writes `releases/X.Y.Z/`: `contract.json`, `record.schema.json`,
  and for each profile `profiles/<name>.json` and `<name>.schema.json` (plus `<name>.candidate.schema.json` for
  extraction profiles). It then writes `RELEASE.json`, which holds each file's sha256, the source digest, the
  generator version and the date. Finally it appends the release to `releases/index.json` and moves `latest`.
- **Releases are immutable.** Every load re-verifies the file hashes, and a tampered release fails to resolve.
  Re-running `bdc release` on an unchanged tree reports `unchanged`. If the sources behind a released `VERSION`
  change, `bdc check` fails with a freshness error; the fix is a new version, never an edit.
- The **source digest** covers only the contract (VERSION, catalog, vocabularies, profiles, all parsed rather
  than taken as bytes). Mappings, docs, code and formatting do not affect it.
- A release may be withdrawn by setting `"status": "withdrawn"` in `index.json`. It stays on disk for audit,
  cannot be resolved, and `latest` moves to the newest active release.

## Resolution

| Request | Resolves to |
| --- | --- |
| `latest` (default) | `releases/index.json` → `latest` |
| `3.1.0` or `v3.1.0` | that release; unknown or withdrawn versions are errors (no fallback) |
| `dev` | the working tree, compiled on the fly: the release itself if the tree equals the release of VERSION, otherwise `VERSION-dev.<digest8>` with status `unreleased` |

The pdf2jsonl Skill refuses unreleased contracts unless `--allow-unreleased` is given. It also refuses contract
majors it does not support (`SUPPORTED_MAJORS`), and profiles that name fill rules it does not implement. In
agent mode, `prepare` pins the resolved version in `request.json`, and `finalize` refuses a different version.

## Compatibility promise

- Within a major version, records produced under `X.a.b` remain valid under `X.a.b` forever (releases are
  immutable). Additive minors mean an older record is normally also valid under a newer minor, but records are
  always validated against the version they declare.
- Moving data to a new version is a migration: re-run extraction under the new version, or transform the
  records and re-validate them. Never rewrite `schema_version` in place.

## History

| Version | Summary |
| --- | --- |
| 3.0.0 | Faithful import of the 259-field v3 baseline: rules, vocabularies, profiles `full` / `compact` / `pdf_extraction` |
| 3.1.0 | Merge of legacy v1 and omics v2: 129 provisional fields (legacy 17, omics 111, `schema_name`), 6 vocabularies, R027–R030, `pdf_extraction_omics`, mappings |
| 3.2.0 | Key roles and functions on every field (`key_role`, `serves`, `card`, `argument_role`); 9 provisional fields for the evidence chain, derivation and Topic 1 fusion; R031–R032; vocabulary `conflict_resolution_status`; profile `record_links` |
| 3.3.0 | Three optional provisional sample fields from merged v2 (biological replicate, technical replicate, sampling time); merged input mapping and migration; the 397 existing field definitions remain unchanged |
| 3.4.0 | Downstream hooks (AMB-038): `transform.predicate_mention` (D), `predicate_code` and predicate offsets (N), offsets and relation roles on `transform.entity_links`, cue lexicon on vocabulary `predicate_label`, R033–R034; `bdc derive` adds statements, a property graph and QA seeds |
| 3.5.0 | Research workflow, verification and source parts (AMB-039 – AMB-041): 8 provisional fields (`agent.statement_role`, three workflow links, `agent.step_condition`, `common.source_part`, `common.verification_run_id`, `transform.ontology_id`), vocabularies `statement_role` and `source_part`, `review_status: model_verified`, four evidence-type codes, R035; `--supplement`, source completeness, `bdc verify`, `workflow.json` and lineage in `bdc derive` |

See `CHANGELOG.md` for details.
