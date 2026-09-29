# Architecture

## Principle

The repository owns the data contract; the Skill is the operational entry point. Field definitions exist in
exactly one place, `field_catalog/field_catalog.yaml`. Everything else is either generated from it (JSON
Schema, dictionaries, releases) or resolved against it at runtime (profiles, the extraction brief, validation,
repair, migration).

```
             editable sources                         frozen artifacts                    consumers
 ┌─────────────────────────────────┐   bdc release   ┌────────────────────────┐
 │ field_catalog/field_catalog.yaml│ ──────────────► │ releases/<X.Y.Z>/      │ ◄── resolve_schema("latest"|"X.Y.Z")
 │ vocabularies/*.yaml             │   (hash-pinned) │   contract.json        │        │
 │ profiles/*.yaml                 │                 │   record.schema.json   │        ├── pdf2jsonl Skill
 │ VERSION, CHANGELOG.md           │                 │   profiles/*.json      │        ├── bdc validate / migrate / bundle
 └─────────────────────────────────┘                 │   RELEASE.json         │        └── downstream (Python API / JSON Schema)
          │ bdc generate                            └────────────────────────┘
          ▼                                          releases/index.json (latest)
 docs/generated/ (dictionary .md/.csv, rules, vocabularies, profiles, ambiguities)
```

`resolve_schema("dev")` compiles the working tree on the fly and stamps the version `<VERSION>-dev.<digest8>`
with status `unreleased`, so development output can never claim to be a release.

## Components

| Component | Location | Responsibility |
| --- | --- | --- |
| Catalog | `field_catalog/field_catalog.yaml` | Groups, types, fields (definition, availability, requirement, `since`, `maturity`, `origin`, source line), record kinds, rules, ambiguity register |
| Vocabularies | `vocabularies/` | Code lists with `enforcement` (error / warning / open) and `code_status` (source / proposed); `units.yaml` conversion table |
| Profiles | `profiles/` | Field selection (`all_active` + filters, or explicit), roles, fill rules, evidence policy, required fields, `extends` |
| Compiler | `src/breeding_contract/compile.py` | Sources → self-contained `contract.json`; profile resolution (`extends`, roles, fill-rule inventory) |
| Schema generator | `schema_gen.py`, `rules.py` | Record / profile / candidate JSON Schemas; error rules that JSON Schema can express are embedded, the rest are listed as `x-validator-only-rules` |
| Validator | `validate.py` | JSON Schema structure + all catalog rules + warning vocabularies + deprecation + dataset rules |
| Releases | `release.py` | Immutable `releases/<v>/` with per-file sha256 in `RELEASE.json`; `index.json` records the release hash |
| API | `api.py` | `resolve_schema`, `load_profile`, `load_field_catalog`, `validate_record`, `declared_version` |
| Checks | `check.py` | The CI gate (`bdc check --strict`) |
| Migration | `legacy.py`, `omics.py`, `mappings.py` | Mapping-driven conversion of legacy v1 documents and omics v2 instances |
| Views | `bundle.py` | `document_bundle` and the legacy v1 projection (derived, never a source of truth) |
| Runtime schemas | `schemas/runtime/`, `runtime_schemas.py` | Formats of manifests, validation reports, error records, bundles, migration reports |
| Skill | `skills/pdf2jsonl/` | Workflow (`SKILL.md`), brief template (`prompts/`), runtime (`scripts/pdf2jsonl_skill/`) |

## The pdf2jsonl pipeline

```
paper.pdf
  │ 1. resolve contract + profile       resolve_contract(): name, supported major, released (or --allow-unreleased),
  │                                     profile is an extraction profile, every fill rule is implemented
  │ 2. parse layout                     pypdf text layer per physical page (or --text-layer for OCR output);
  │                                     sections, table/figure captions, char offsets
  │ 3. candidates                       backend: agent (brief → candidates.json), candidates file, mock, module:callable
  │ 4. structural repair                repair.py: flatten nested groups, resolve bare leaf names, coerce types,
  │                                     map vocabulary labels/aliases, drop empties and pipeline-owned fields — logged
  │ 5. evidence verification            quote must occur on the stated page (±1 page → EVIDENCE_PAGE_CORRECTED);
  │                                     otherwise EVIDENCE_QUOTE_NOT_FOUND → rejected; value-presence warnings
  │ 6. assemble atomic records          document values, provenance roles, extracted fields, normalizers
  │                                     (raw kept, normalized added), generated and system fields via named fill rules
  │ 7. validate → review fields         validation outcome drives review_status / qc_failure_codes; re-validate
  │ 8. system records, dataset rules    asset_manifest for the input; uniqueness / leakage rules over the file
  ▼ 9. write outputs                    paper.jsonl · paper.errors.jsonl · paper.validation.json · paper.manifest.json
```

**Agent mode** splits the run at step 3. `prepare` writes `brief.md` (rendered from the resolved profile:
record kinds, fields with definitions, vocabularies, applicable rules), `pages.txt`, `candidate.schema.json`,
`candidates.template.json` and `request.json`, which pins the contract version. The agent writes
`candidates.json`, and `finalize` (or re-running the same command) completes steps 4–9 under the pinned
version. A release published in between cannot silently change the contract the candidates were written for.

**Fill rules.** Profiles never contain code. They name rules such as `stable_record_id`, `evidence_locator`,
`evidence_span`, `resolved_schema_version`, `unit_normalization`, `validation_outcome` or `missing_audit`, with
parameters. The Skill implements each rule once (`fill_rules.py`), and `bdc check` fails when a profile names a
rule the Skill does not implement. Adding a field to the catalog therefore needs no Skill change. Adding a new
*kind* of computation needs a new rule, reviewed like any code.

## Invariants and where they are enforced

| Invariant | Enforcement |
| --- | --- |
| No field definitions outside the catalog | `check_skill`: no field paths or version literals in `SKILL.md`, prompts or Skill code; the brief is rendered from the release |
| Records are atomic and provenance-bearing | profile roles + R001 (page + quote for paper evidence) + evidence verification |
| Never infer | model sees only D fields; I/G/F never exposed (`check_profiles`); unverifiable quotes rejected; migrators skip inferred relations and route I values to review candidates |
| Omit missing values | JSON Schema (`minLength`, `minItems`, `minProperties`, no `null` types); repair drops empties with a log entry |
| Raw vs normalized | normalizers only add `normalized_*` (R015/R016 require the originals); unknown units are not converted |
| D/N/I/G/F semantics preserved | catalog codes are verbatim from v3; profile roles are checked against availability |
| Every record declares its contract | `resolved_schema_name` / `resolved_schema_version` fill rules; `const` in the schema; `declared_version()` routing |
| Releases are immutable | per-file sha256 in `RELEASE.json`, verified on every load; source digest freshness check |
| Rejections are visible | `*.errors.jsonl` and the validation report; nothing is dropped silently |

## Checks run by CI (`bdc check --strict`)

`meta` (source files against `schemas/meta/`), `catalog` (paths, types, vocabularies, rules, ambiguities,
policy: inferred rules must be warnings), `profiles` (no G/F exposed to models, review codes exist),
`version` (CHANGELOG entry, VERSION not older than latest), `releases` (integrity, index, `latest`),
`freshness` (working tree equals the release of VERSION; strict mode fails on an unreleased VERSION), `skill`
(supported range, fill rules, no hard-coded paths or versions, known placeholders), `mappings` (every source
leaf covered, targets exist, merged targets record the origin), `docs` (generated docs current), `examples`
(records valid against their declared version, outputs valid against the runtime schemas, invalid cases fail as
expected).

## Identifier and locator conventions (AMB-011)

Implemented in `src/breeding_contract/ids.py` and shared by every ingestion path (pipeline, migrations,
curated examples):

| Item | Convention | Example |
| --- | --- | --- |
| `common.record_id` | `rec_` + first 32 hex of sha256 over `source_id ␟ record_kind ␟ locator core ␟ normalized quote ␟ ordinal` | `rec_828955fbf1c3d2acf5c43230fa88afc7` |
| `common.source_id` | `doi:<lower-case DOI>`, else `urn:sha256:<file hash>`; migrations keep `urn:legacy-v1:<id>` when no DOI exists | `doi:10.0000/synthetic.2026.001` |
| `common.source_locator` | `key=value` pairs joined by `;`, keys in order `page, section, table, row, col`; `%`, `;`, `=` are percent-escaped | `page=3;section=Results;table=Table 2;row=RIL-017;col=PH` |
| `common.source_span` | `page=<n>;char=<start>-<end>` offsets into the parsed page text | `page=1;char=377-499` |
| run IDs | `run_<UTC timestamp>_<sha8 of input>` (pipeline), `mig_<UTC timestamp>_<sha8>` (migration); `--run-id` overrides | `run_20260921T141320Z_73754bef` |

The normalized quote is NFKC-folded, de-hyphenated across line breaks, typography-folded and whitespace-collapsed,
so record IDs do not depend on the PDF parser's whitespace. `SOURCE_DATE_EPOCH` pins every timestamp for
reproducible runs.
