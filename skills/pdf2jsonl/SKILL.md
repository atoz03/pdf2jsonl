---
name: pdf2jsonl
description: Extract atomic, evidence-anchored JSONL records from breeding / plant-genetics literature PDFs under the versioned data contract of this repository (field catalog, profiles, vocabularies, rules). Use when asked to convert papers (PDF) into JSONL, to extract QTL/GWAS/phenotype/method facts with provenance, or to validate/bundle such JSONL.
---

# pdf2jsonl

This Skill is the operational entry point to the **breeding data contract**. The repository owns the contract
(field catalog → schema, profiles, vocabularies, rules, releases). This file only describes the workflow. It
deliberately lists **no fields and no versions**: both are resolved at runtime from `releases/`. Everything you
need for one paper is written into a generated brief.

Launcher: `scripts/pdf2jsonl` in this skill directory. It works through a symlink, and uses the repository
`.venv` when present. Run `scripts/pdf2jsonl --help` for all options.

## Workflow (agent mode — you are the extraction model)

1. **Resolve the contract.** Say which version and profile you will use:
   `scripts/pdf2jsonl resolve --schema-version latest --profile pdf_extraction`
   Use `latest` unless the user names a version. For reproducing an earlier run, pass the exact version
   recorded in its `*.manifest.json`. Other profiles (see the output of `resolve`) are chosen with `--profile`.
2. **Prepare.**
   `scripts/pdf2jsonl paper.pdf --profile pdf_extraction --schema-version latest --out-dir out/`
   The command exits with status 3 and creates `out/paper.work/`, containing `brief.md`, `pages.txt`,
   `candidate.schema.json` and `request.json`. The request pins the resolved version.
   For scanned PDFs, pass an OCR/MinerU text layer with `--text-layer paper.pages.jsonl`.
3. **Extract.** Read `brief.md` completely, then `pages.txt`, page by page. Write
   `out/paper.work/candidates.json` exactly as the brief and `candidate.schema.json` describe. Long papers can
   be done in page batches that are appended to the same `candidates` array.
   When the paper itself connects statements (a conclusion rests on a result, a result was produced by a
   method), give the target candidate a short `ref` and list it under the source candidate's `links`. The
   brief names the link types the profile allows. Keep the author's hedging words and stated limitations
   verbatim in the fields the brief lists under "Evidence chain".
   When a quote relates two entities, state the relation as subject, verbatim predicate and object in the
   fields the brief lists under "Relations". Do not leave it inside the finding text and do not choose a
   relation code: the pipeline anchors the mentions in the quote and derives the code.
4. **Finalize.** Run the same command as in step 2 again (or `scripts/pdf2jsonl finalize out/paper.work`).
   The pipeline then:
   - verifies every quote against the PDF text;
   - assembles records: identifiers, locators, schema version, normalized values and review fields are
     computed, never taken from you;
   - validates the records against the pinned contract;
   - turns `links` into record IDs; a link to a rejected candidate is dropped and flagged, never guessed;
   - writes `paper.jsonl`, `paper.validation.json` (including the evidence-chain audit `argument_structure`),
     `paper.errors.jsonl` and `paper.manifest.json`.
5. **Repair and re-run.** Read `paper.errors.jsonl` and the warnings in `paper.validation.json`. Fix
   `candidates.json` and finalize again; outputs are overwritten deterministically.
   - `EVIDENCE_QUOTE_NOT_FOUND`: copy the quote verbatim from the page, or drop the candidate if the paper does
     not say it.
   - `RECORD_INVALID`: follow the issue messages (wrong type, vocabulary code, missing paired field, …).
   - Value-presence warnings: a value is not literally on the evidence page. Correct it, or accept that the
     record stays `pending_review`.
   - `CANDIDATE_LINK_*` warnings: fix the `ref` / `links`, or remove a link the paper does not state.
   - Audit flags in `argument_structure` (for example `NO_WARRANT`, `QUALIFIER_NOT_CAPTURED`) are review hints.
     Add a link or a hedge only when the paper states it.
   Never "fix" a record by inventing content.
6. **Report** to the user:
   - the resolved contract version and profile;
   - records accepted / rejected / pending review;
   - the evidence-chain summary (statements, unresolved links, audit flags);
   - the output paths;
   - any ambiguity you left unresolved.

## Invariants

- **Provenance is mandatory.** Every model-produced record has a physical page number and a minimal verbatim
  quote; table values also carry the table/figure label and row/column keys. Unverifiable quotes are rejected,
  not repaired.
- **Atomic records.** One statement, observation, method or result per record. One table row with three traits
  becomes three observations.
- **Never infer.** Missing information is omitted (no `null`, no empty strings, no guesses, no background
  knowledge). Association is never upgraded to causation. Fields that the contract marks as human judgement,
  later generation or future sources are not exposed to you and are never fabricated.
- **Raw and normalized stay separate.** You copy raw values and units as printed. Normalization is
  deterministic, uses the repository unit table, and is done by the pipeline.
- **Records are consumed downstream without a second parse.** Knowledge-graph edges, corpus annotations and QA
  items are built from fields, so a relation that is only prose in a finding does not exist for them. You
  write the three verbatim parts of a statement; offsets, entity types and relation codes are computed.
- **Contract-driven.** Use only the fields, record kinds and vocabulary codes listed in the brief for the
  resolved version. Never reuse an old brief or field list: after a new contract release, the next run follows
  it automatically.
- **Production data is released data.** Outputs always carry the explicit resolved version. `--schema-version dev`
  (the unreleased working tree) needs `--allow-unreleased` and is for contract development only.

## Other modes

- `--backend candidates --candidates file.json`: finalize candidates that were produced elsewhere.
- `--backend module:callable`: plug in your own extractor (for example an LLM API client). It receives
  `(doc, profile, rc, options)` and returns the candidates document. The same verification and validation apply.
- `--backend mock`: a deterministic rule-based smoke test with no model.
- `scripts/pdf2jsonl validate out/paper.jsonl`: validates each record against the version it declares.
- `scripts/pdf2jsonl bundle out/paper.jsonl [--legacy-v1]`: derives the per-paper `document_bundle` view.
- `bdc derive out/paper.jsonl --out derived/` and `bdc audit out/paper.jsonl` (repository CLI): relational tables,
  statements, triples, a property graph, an entity-annotated corpus and QA seeds, and the evidence-chain audit
  on any record set.
