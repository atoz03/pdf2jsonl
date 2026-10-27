# Changelog — breeding-literature-record contract

All notable changes to the **data contract** (field catalog, vocabularies, profiles, rules) are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow semantic versioning
(see `docs/versioning.md`):

- **MAJOR**: a field is removed or renamed, a type or meaning changes, a vocabulary code is removed, or an
  existing rule is tightened to error.
- **MINOR**: new fields, codes, profiles or warning-level rules are added, or `provisional` is promoted to
  `verified`.
- **PATCH**: wording, documentation and source references change with no effect on validation.

Each heading `## [X.Y.Z] - YYYY-MM-DD` provides the release date that `bdc release` records.

## [3.8.0] - 2026-10-27

A trial of 3.7.0 on six real papers (236 records) left three gaps that the data itself exposed. The relation
layer named the nature of a relation but never said *what makes the causal claim hold*: `causal` was still
decided by the verb alone, and 16 of 36 statements had no code at all (41.7% coverage) because real papers say
"suppressed", "is upstream of", "co-localizes with", "is mainly controlled by". A candidate gene and a validated
one looked the same, QTN statements had to be filed under QTL names, and a review's paraphrase sat in the same
table as a primary experiment. The same trial also showed that "the file is there but the table it cites is not"
had no state of its own.

This release makes each of those a field, a rule or a visible badge — and keeps the line the contract already
draws: the pipeline never upgrades a wording into evidence.

### Added
- **`transform.claim_strength`** (N, vocabulary `claim_strength`): reads the predicate's nature together with
  the relation evidence type — `causal_supported` (functional validation, genetic interaction, biochemical
  assay, localization imaging, pharmacological perturbation), `causal_expression_supported`,
  `causal_statistical_only`, `causal_unverified`, plus `associational` / `structural` / `descriptive`. A causal
  wording is never settled by the verb alone, and never silently downgraded either (AMB-046).
- **`common.qtn_names`** (D, entity mention, entity type `qtn`): QTN, QTL and candidate gene are three entities
  and are recorded separately; a candidate gene is not renamed a QTN (AMB-045).
- **`agent.validated_by_record_ids`** (N, record link, workflow edge `validated_by`) and the profile link type:
  the records of the validation experiment the paper reports, linked from the conclusion. Association and
  validation keep their own evidence; neither replaces the other.
- **`transform.validation_status`** (N, vocabulary `validation_status`: `candidate` / `experiment_reported`):
  derived from that link only, for claims, analysis results and relational records.
- **`transform.evidence_origin`** (N, vocabulary `evidence_origin`) and **`agent.reported_citation_text`** (D):
  a review's records are marked `review_report` and keep the original-study lead the text prints (AMB-047).
- **`transform.cited_source_items`** (N): the supplementary figures/tables a record's own quote cites, detected
  with the same literal rules as source completeness, so a record is tied to the part of the paper outside the
  main text instead of leaving the item only inside prose.
- **Rules R038–R040** (warning, inferred, non-blocking): a causal claim whose only evidence type is statistical
  mapping should name a validation method; a gene marked `functional_validated` should carry a validation
  record; a `review_report` record should carry its citation text.
- **Eight `predicate_label` codes for the classes the trial hit**: `qtn_associated_with_trait`,
  `gene_suppresses_gene`, `gene_suppressed_by_gene` (active and passive kept apart), `gene_upstream_of_gene`,
  `trait_controlled_by_gene`, `locus_affects_trait`, `locus_linked_to_locus`, `gene_absent_in_germplasm`.
- Ambiguities **AMB-045** (entity and validation status), **AMB-046** (nature vs evidence), **AMB-047**
  (review paraphrase).

### Changed
- **Cues for the phrasings real papers use**: `locus_overlaps_locus` gains `colocalizes with`, `colocalize
  with`, `coincides with`, `coincide with`; the correlation codes gain `correlation between` and
  `correlation was observed between`; `locus_correlated_with_trait`, `locus_overlaps_locus` and
  `model_predicts_trait` accept a `qtn` end. Direction is never guessed: an active cue is not reused for the
  passive code (`suppressed` vs `suppressed by`), and `affects` stays with the environment code so the two do
  not tie on an untyped subject.
- **The paper dashboard explains its numbers**: a run's detail header shows 候选 → 生成（含系统记录）→ 接收 /
  拒收 / 待审 with the `count_definitions`, the paper badge separates pending records from structural hints,
  and records carry badges for validation status, claim strength and review paraphrase; a supplied part whose
  cited items were not found gets its own state.
- **`docs/presentation.md` is a display contract, checked by `bdc check`** (`check_presentation`): a record list
  must show every entity mention with its type (QTN / QTL / 基因 / 标记 / 性状 …), the validation status as a
  column of its own (候选 / 已提供验证实验), the author's qualifier verbatim, and the claim strength beside the
  nature. The dashboard's record table now has 实体 / 验证 / 限定语 / 结论强度 columns and the relations table
  types both ends; removing one of them fails CI, so the rule lives in the repository rather than in a habit.
- **`pdf2jsonl` 0.6.0**: the three new fill rules, the `validated_by` link type, and the review/validation
  guidance in the brief.
- `source_parts` gains `supplied_items_not_found` — the file is supplied but a cited item cannot be located in
  it — with the run-level notice `SOURCE_PART_ITEM_NOT_FOUND`, distinct from "not supplied" and "no text".
- `docs/relation_semantics.md`, `docs/downstream.md`, `docs/review.md` and `docs/versioning.md` describe the new
  layers; the READMEs gain the 3.8.0 section.

## [3.7.0] - 2026-10-27

A trial round of feedback on 3.6.0 showed three problems that no single field could fix. First, a relation the
pipeline could not code was indistinguishable from one it would not code: "was significantly correlated with",
"increased", "conferred / mediated" and "co-located with" all came back as 未判定 with no reason, and the reason
itself — a vocabulary gap versus two codes of equal cue length that only the entity types could separate —
decides whether the reviewer fixes the vocabulary or registers the entity mention. Second, the causal /
associational nature reached only the derived views: `transform.relation_nature` is derived from the curated
`predicate_label`, which a fresh extraction never has, so R036/R037 could not fire on extracted records at all.
Third, nobody could reconcile the counts: one round reported 8 candidates and 13 records for five papers, and
2624 accepted records with 450 "pending" beside them, because the records the pipeline writes itself (one asset
manifest per input file) and the fact that `pending_review` is a subset of the accepted records were both
invisible. The same round asked for the states of a citable part ("not supplied", "not cited", "supplied but
not parsed") and for the appendix to be a part of its own instead of a second supplement.

### Added
- **`transform.relation_resolution`** (N, vocabulary `relation_resolution`: `coded` / `ambiguous` / `no_cue` /
  `negated`): why a record has or has no `predicate_code`, so "未判定" becomes actionable and countable
  (AMB-043). `ambiguous` is the case a reviewer clears by registering the entity mention, `no_cue` the case that
  needs the vocabulary. `relations.predicate_match` returns the code and the reason; `predicate_code` keeps its
  signature.
- **`predicate_label` codes for the classes the trial needed** (AMB-043): `locus_correlated_with_trait`
  (a gene/QTL/marker correlated with a trait, nature `associational`), `locus_overlaps_locus` (interval overlap
  or co-localisation, nature `structural`), `model_predicts_trait` (prediction and model comparison, nature
  `associational`, never causal).
- **`--supplement FILE:appendix`** and the part labels `appendix`, `appendix_2` … (`pdf_parse.PART_KINDS`): the
  vocabulary already carried `source_part: appendix`, but no run could produce it (AMB-044).
- **`source_parts.parts[]`**: one entry per part kind with its state — `supplied_parsed`, `supplied_no_text`,
  `supplied_not_referenced`, `referenced_not_supplied`, `in_main_pages`, `not_referenced` — with files, pages,
  text pages and characters; run-level `source_parts.warnings` carry `SOURCE_PART_NOT_PARSED` and
  `SOURCE_PART_UNREFERENCED` (AMB-044).
- **`SOURCE_PART_NOT_PARSED`**: a record citing an item of a supplied part without a text layer gets this code
  instead of `SOURCE_PART_UNAVAILABLE`, because the remedy is a text layer (`--text-layer`), not the file.
- **Counts that say what they count**: `counts.system_records`, `counts.model_records`, `counts.warnings`
  (by code and by family) and `counts.relation` (statements, resolution breakdown, `coverage`), plus the report's
  `count_definitions`; the manifest repeats the part states (AMB-043).
- Ambiguities **AMB-043** (relation resolution) and **AMB-044** (part states and the appendix).

### Changed
- **`transform.relation_nature` reads `predicate_code` when the record has no reviewed `predicate_label`.** The
  nature is the same contract data either way, so a fresh extraction carries causal/associational/structural
  instead of nothing and R036/R037 finally see extracted records (AMB-042, AMB-043); the curated label still
  wins when it is there.
- **A rule can be non-blocking** (`rules[].blocking`, default true): its warning is reported, counted and listed
  in `common.qc_failure_codes`, but does not by itself put the record in `pending_review`. R018 (a missing
  `common.asset_uri`, which only the operator can supply), R036 and R037 are marked non-blocking — every run used
  to end with one pending asset record that no action could clear, and a rule the extraction cannot satisfy only
  teaches reviewers to ignore the queue.
- **`predicate_label` cues cover the inflected forms** of the verbs they name (`increased`, `increases`,
  `conferred`, `mediated`, `harboring`, `co-localized`, …). A cue is still a literal phrase; the vocabulary notes
  now state the rule: give the third person, the past tense and the passive where a paper may use them.
- **`qtl_overlaps_qtl` is deprecated** (`status: deprecated`, `replaced_by: locus_overlaps_locus`,
  `deprecated_in: 3.7.0`) and carries no cues any more: positional overlap is structural, and a code whose nature
  says `associational` cannot be fixed in place without changing the meaning of existing records. A record that
  still uses it gets `VOCAB_CODE_DEPRECATED` (new warning code) naming the replacement.
- **Missing parts are judged per part** (AMB-044): a supplied supplement no longer suppresses a missing appendix.
  Item labels remain one pool for all further files, so a quoted "Fig. S2" is reported only when no further file
  was supplied, or when the supplied file has no text.
- **The dashboard compares a re-run with the run before it** when the two were given different parts: records
  added or removed, warning codes that disappeared or appeared, and the review counts on both sides — so "we added
  the appendix and these SOURCE_PART_UNAVAILABLE warnings went away" is visible without diffing files
  (AMB-044). The page also lists the state of every supplied part, and no longer claims that every warning
  drops a record to review.
- **Vocabulary values can be deprecated** (`status`, `replaced_by`, `deprecated_in` in the vocabulary format);
  the validator warns on a deprecated code, and `bdc check` docs list it.
- **`transform.relation_nature` no longer carries `argument_role: warrant`.** Filling the field on every
  relational statement would otherwise satisfy the evidence-chain audit's `NO_WARRANT` flag with a derived
  label and no statistical basis: the nature says what the predicate asserts, not what grounds it (AMB-043).
- **`pdf2jsonl` 0.5.0**: `--supplement FILE:appendix`, part states in the report and manifest
  (`input.supplements[].kind`, `source_parts.parts`), `relation_resolution`, blocking-aware review status and the
  extended counts.
- `docs/relation_semantics.md`, `docs/downstream.md`, `docs/review.md` and `docs/versioning.md` describe the new
  fields and the count definitions; the dashboard's 填写规则 family text no longer claims rules stop at R035.

## [3.6.0] - 2026-10-19

The contract states relations as subject–predicate–object, but said nothing about *what the predicate asserts*.
`predicate_label` is an open list of Chinese relation names, so a record could not be read to tell whether an edge
is causal or merely correlational, and the two fields that do draw the line (`agent.causal_direction`,
`agent.association_vs_causation`) are availability `I`, unstaked values (AMB-024) and invisible to the extraction
model. Only a causal relation can directly guide an experiment; an association written as a flat conclusion
silently authorises one it does not support. This release records the nature of a relation as data, in three
layers that do not substitute for one another.

### Added
- **`predicate_label` values carry `nature`** (AMB-042): `causal` / `associational` / `structural` / `descriptive` /
  `unknown`. The nature belongs to the predicate, not to the evidence: an `associational` predicate can sit at
  functional-validation evidence and still be associational. Repository-proposed, like `cues` (AMB-038).
- **`vocabularies/relation_nature.yaml`** (warning, closed) and **`relation_assertion_mode.yaml`** (warning,
  closed, `stated` / `hedged` / `unclear`).
- **`transform.relation_nature`** (N): derived at compile time from the predicate vocabulary
  (`contract["relation_natures"]`), never judged by the extraction model.
- **`transform.relation_assertion_mode`** (D): how the source words the relation, so a `may`-hedged claim is not
  mistaken for an assertion. The verbatim predicate is `transform.predicate_mention` (AMB-038).
- **Rules R036, R037** (warning, inferred): an associational predicate asserted flat with no relation evidence
  (neither `transform.relation_evidence_type` nor `agent.supporting_evidence`) is flagged; a causal predicate
  without `transform.relation_evidence_type` is flagged.
- Skill fill rule **`relation_nature_from_predicate`**, wired as a `pdf_extraction` normalizer so the nature comes
  from the contract rather than from a reading of the record.
- `predicate_label` code **`cross_omics_regulates`** (`跨组学-调控`, merged v2 appendix A-5), `nature: causal`.
- Ambiguity **AMB-042**; narrative in `docs/relation_semantics.md`.

### Changed
- `schemas/meta/vocabulary.meta.schema.json` accepts a per-value `nature` and the `merged_v2` origin.
- **`bdc derive` carries the nature and the wording.** A derived statement (and the matching triples and graph
  edges) now includes `relation_nature` and `relation_assertion_mode`, so the causal/associational line the
  contract draws is visible in the derived views, not only in the record. When a record has no reviewed
  `predicate_label`, the nature falls back to the `nature` of the code `predicate_code` matched — the same
  deterministic judgement, never a second reading. `derive_format` is **4**.
- **The paper dashboard gains a 关系 tab** (`site/pages/papers.html`): every statement is listed as
  subject – predicate – object with its 因果 / 相关 / 结构 / 描述 / 未知 label and a filter by nature, so a reader
  can separate the relations that can guide an experiment from those that only co-vary.
- `predicate_label` cues extended so verbatim predicates of a real paper (`was correlated with`,
  `decreased the …`, `regulated by`, `overlapped with`, `involved in`) resolve to a code; new codes
  `trait_correlated_with_trait`, `qtl_overlaps_qtl`, `locus_decreases_trait`, `locus_increases_trait`,
  `locus_regulated_by_gene`, `gene_involved_in_process`. The new codes name the subject and object the paper
  actually states: `locus_regulated_by_gene` carries the locus as subject and the gene as object, because
  "the QTLs … are likely regulated by a single gene" says nothing about which gene regulates which trait.
  A code's declared `subject_types` / `object_types` filter only ends that have a type — an end no entity field
  lists carries none, and is not evidence against the code (`relations.predicate_code`). `variety_derived_from`
  now also accepts a `population` / `parent` subject and a `population` object.
- **A predicate keeps its direction.** A cue counts only where it is used in its own voice: an active cue used
  passively ("plant height was controlled by qPH7.1", "受…调控") would put the trait at the causing end, and an
  untyped end leaves no type check to catch it, so it no longer matches. In English the participle is followed by
  "by" (an adverb may sit between); in Chinese 受 / 被 precede the verb (not 受体, nor 被认为 / 被发现 …). A "by"
  that only modifies the object ("decreased the transparency values conferred by") leaves the verb active. The
  passive code `locus_regulated_by_gene` carries the passive cue `regulated by` only, so an active "A regulates
  B" never matches it.
- **Every long list pages.** Only `抽取记录` used to paginate; the lists under 关系 / 研究流程 / 语义校验 / 校验与审计 /
  运行历史 rendered every row and the page grew without bound. Each now pages through the shared pager, on a key of
  its own, so paging one list never moves another.

## [3.5.1] - 2026-10-13

A trial extraction of two papers showed that the verbatim value-presence check dominated the review queue: of
191 warnings it raised, 149 came from fields whose value the paper states in its own words (`agent.finding_text`
alone accounted for 99), and they were the sole reason 98 records sat in `pending_review`. The check is now
scoped to fields whose value is a fact of the paper, so it reports the values that must appear verbatim instead
of the writing that never will.

The same release closes the loop on 3.5.0's semantic verification in the paper dashboard: the page now reads a
run's verification report and shows the run under its post-verification statuses, gains 研究流程 (workflow) and
语义校验 (verify) detail tabs, and groups a run's record warnings into families — the value family carrying the
run's `value_presence_roles` so warning counts are only compared between runs that checked the same fields.

### Changed
- **`evidence_policy.value_presence_roles`** (new profile key, `profiles/pdf_extraction.yaml`): the
  `VALUE_NOT_ON_EVIDENCE_PAGE` / `VALUE_NOT_IN_SOURCE` check now runs only for fields whose `key_role` is one of
  `entity_mention`, `entity_id`, `entity_attribute`, `reference_frame`, `context_key`, `measurement`, `statistic`.
  A field the paper states in its own words (`assertion`, `method_spec`, `condition`, `interface_spec`,
  `study_design`) is a paraphrase by definition, so a value-presence warning about it flagged the writing, not an
  error (AMB-014). Omitting the key keeps the previous behaviour: every field is checked. The check's severity
  (`warning`) and the rest of `evidence_policy` are unchanged, and no field, vocabulary or rule changes — this is
  a profile-internal change with no effect on a record's validity (hence PATCH).
  - `schemas/meta/profile.meta.schema.json` accepts the key (a non-empty array of `key_role` codes, no `enum`);
    `compile.resolve_profile` rejects a profile naming an unknown `key_role`.
  - `skills/pdf2jsonl/scripts/pdf2jsonl_skill/pipeline.py` gates the per-field check on
    `Assembler.presence_roles` (`None` = check every field). `check_document` (`DOCUMENT_VALUE_NOT_IN_SOURCE`)
    is not gated by the key.

### Added
- **Dashboard reads the verification report** (`scripts/make_dashboard.py`, `site/dashboard.template.html`). When
  `<stem>.verification.json` (and `<stem>.verified.jsonl`) sits next to a run's records — or in a `review/`
  directory beside them, where `bdc verify apply … --out review/` writes — the page shows that run under its
  post-verification statuses and lists the findings, conflict candidates and omission candidates, with the report
  and the verified records downloadable. It only displays; it changes no record. A `review/` subdirectory is
  searched as well as the records' own directory, and tampering is surfaced: if the verified records' `sha256`
  no longer matches the report, the page says so.
- **研究流程 and 语义校验 detail tabs.** A run's detail dialog goes from
  `[records, 原文与证据, 校验与审计, 运行历史, 导出文件]` to
  `[records, 研究流程, 原文与证据, 语义校验, 校验与审计, 运行历史, 导出文件]`; the 研究流程 tab renders the
  derived workflow view (or an empty state noting it needs contract 3.5.0 and `statement_role`), the 语义校验 tab
  shows the verification findings.
- **Warning families.** A run's record warnings are grouped for the page and its filter as 取值核验 (`VALUE_*`,
  `DOCUMENT_VALUE_*`, `EVIDENCE_PAGE_CORRECTED`, `EVIDENCE_TABLE_NOT_ON_PAGE`, `EVIDENCE_CELL_KEY_NOT_ON_PAGE`),
  填写规则 (`RULE_*`), 记录链接 (`CANDIDATE_LINK_*`, `UNRESOLVED_LINK`, `LINK_*`), 来源完整性 (`SOURCE_PART_*`)
  and 输出完整性 (`OUTPUT_INTEGRITY`); records can be filtered by family.
- **Comparability flag.** The value family carries the run's `evidence_policy`: a run whose profile has
  `value_presence_roles` is marked as having checked those `key_role`s, a run without it (or before 3.5.1) as
  having checked every field — the two runs' value-warning counts are not comparable, and the page says so.
- **Dashboard guide gains the verification step** (`site/dashboard.template.html`). The "添加论文与更新看板"
  dialog goes from three steps to four, inserting **3 （可选）运行语义校验**
  (`bdc verify tasks out/paper.jsonl --out review/ && bdc verify apply out/paper.jsonl --verdicts
  review/paper.verify.verdicts.json --out review/`) before **4 重新生成，然后刷新页面** (`make dashboard`);
  step 1 also notes 补充材料 / `--supplement`.

### Fixed
- **Checked-in artifacts are byte-identical on every platform.** `bdc derive` records its lineage output paths,
  and `scripts/make_site.py` its file links, with `/` on Windows too (they used the OS separator). A new
  `.gitattributes` marks `examples/**` and `releases/**` as `-text`, so a Windows checkout with `core.autocrlf`
  no longer rewrites the CRLF that Python's `csv` writer emits or the LF of JSON whose `sha256` a manifest, a
  verification report or `RELEASE.json` records.
- `evidence_policy.value_presence_roles` must be non-empty (`minItems: 1`); an explicit list is taken literally by
  the pipeline and the dashboard. To turn the check off, use `value_presence_check: off`.
- The dashboard's `counts.expert_approved` counts `expert_approved` records only; it also counted `rejected`,
  which the 语义校验 card's 已提升 figure does not mean.

### Docs
- `docs/review.md` rewrites the Layer-1 Evidence paragraph (role-scoped value check, AMB-014) and documents the
  dashboard's verification report, warning families and comparability flag. `README.md` enlarges the 论文看板 row
  with 研究流程、语义校验 and the warning-family grouping.

### Tests
- `tests/test_pipeline.py::test_value_presence_is_checked_only_for_value_bearing_roles`,
  `tests/test_normalize_profiles.py::test_pdf_extraction_scopes_value_presence_to_value_bearing_roles`, and eight
  `tests/test_dashboard.py` cases (verified-run ingestion, a run without verification, warning families, the
  presence policy, the example run's filter, verification under `review/`, and tamper detection).
- `tests/test_normalize_profiles.py::test_value_presence_roles_cannot_be_empty`, and
  `tests/test_source_parts.py::test_derived_views_record_their_lineage` asserts POSIX lineage paths.

## [3.5.0] - 2026-10-10

This release answers three questions raised by Topic 2 after a trial extraction of a mechanism paper: how a
paper's **research workflow** is represented, how extraction is **verified** beyond format and quote checks,
and how the forms of the same knowledge **trace back** to each other, including papers whose supplement is
missing. All additions are provisional (AMB-039, AMB-041) or open (AMB-040). No existing field changes type,
availability or meaning; records of earlier versions stay valid, and record IDs of main-text records do not
change.

### Added
- **Research workflow** (`docs/workflow.md`, AMB-039). The workflow is a view over the atomic records, not a
  second extraction format:
  - `agent.statement_role` (D, vocabulary `statement_role`): background, research question, objective,
    hypothesis, design, result or conclusion, as the wording of the paper shows it.
  - `agent.tests_record_ids`, `agent.addresses_record_ids`, `agent.prerequisite_record_ids` (N): which
    experiment was run to test which hypothesis, which statement answers which question, which step uses the
    output of which. They are resolved from candidate `links` like the existing evidence and method links.
  - `agent.step_condition` (D): a precondition or branching rule of a step, verbatim.
  - Field attribute `workflow_edge` (codes `evidence`, `method`, `tests`, `addresses`, `prerequisite`) marks
    the link fields that are edges of the workflow; `agent.evidence_record_ids` and `skills.method_record_ids`
    carry it too.
  - Rule `R035` (warning, definitional): a workflow link must point at a record of the file.
- **Semantic verification** (`docs/review.md`, AMB-040):
  - `review_status` code `model_verified`, between `auto_validated` and `expert_approved`: an independent
    verifier judged every field and link of the record supported by the paper.
  - `common.verification_run_id` (N).
  - Four codes in vocabulary `relation_evidence_type` for mechanism evidence: `genetic_interaction`,
    `localization_imaging`, `biochemical_assay`, `pharmacological_perturbation` (repository proposals).
- **Source parts and incomplete papers** (`docs/downstream.md`, AMB-041):
  - `common.source_part` (N, vocabulary `source_part`: main text, supplement, appendix, other). All parts of a
    paper share one `source_id`; the page is the physical page within the part's file.
  - `missing_reason` code `source_part_unavailable`.
  - `transform.ontology_id` (N), paired with `transform.ontology_version`, so that an alignment names the
    ontology it used (a domain ontology or one built for a class of papers).
- **Profile `pdf_extraction`**: provenance role `part`, semantic roles `statement_role` and `step_condition`,
  record links `tests`, `addresses` and `prerequisite`, fill rule `evidence_source_part`. The extraction brief
  gains a "Research workflow" section and the invariant that a paper may come in several files.

### Tooling (pdf2jsonl 0.4.0, no effect on validation)
- `pdf2jsonl … --supplement FILE` (repeatable): further files of the same paper are parsed as parts. Evidence
  names its part (`evidence.part`), locators and spans of supplement records start with `part=…;`, and each
  file gets its own `asset_manifest` record.
- **Source completeness.** The pipeline scans the main text for references to supplementary items and parts
  and reports those that were not supplied (`source_parts` in the validation report and the manifest). A
  record whose quote cites an item of a missing part gets the warning `SOURCE_PART_UNAVAILABLE` and stays
  `pending_review`. Nothing is filled in for a missing part.
- `bdc derive` writes `<stem>.workflow.json` (nodes, edges, step order, branch points, one trace per
  hypothesis, structural flags) and records the **lineage** of every view in `<stem>.derive.json`: name and
  hash of the records file, its source IDs, the hash of each file written.
- `bdc audit` and the validation report add `workflow_structure`: stages, link types and flags
  (`HYPOTHESIS_UNTESTED`, `QUESTION_UNADDRESSED`, `CONCLUSION_WITHOUT_EVIDENCE`, `RESULT_WITHOUT_METHOD`,
  `STEP_WITHOUT_OUTPUT`, `DEPENDENCY_CYCLE`, `UNRESOLVED_LINK`). Flags are review hints.
- `bdc verify tasks` builds one task per record and per link for a verifier that is not the extractor;
  `bdc verify apply` moves the review fields according to its verdicts (`model_verified`, or `pending_review`
  with `VERIFY_FIELD_NOT_SUPPORTED`, `VERIFY_LINK_NOT_SUPPORTED`, `VERIFY_UNCERTAIN`) and reports conflict and
  omission candidates. Content is never edited, expert decisions are never overwritten, and a verifier that
  is the extraction model promotes nothing.
- Runtime schemas: `verification_report`; `source_parts` and `workflow_structure` in the validation report;
  `input.supplements` and `source_parts` in the manifest.
- Examples: a second synthetic paper in two files (`examples/papers/synthetic_rice_heat.*`) with its run, the
  same paper without its supplement (`examples/output/incomplete/`), a verification pass
  (`examples/output/review/`) and the derived views of the verified records (`examples/derived/`).

### Changed
- `bdc derive` report: `derive_format` is 3 (adds `lineage` and the workflow counts).
- `common.source_locator` and `common.source_span` may start with `part=<label>;`. Records of the main text
  are written exactly as before.

### Open (for the data owners and breeding experts)
- The rubric behind `agent.evidence_strength`, sampling rates for expert review and the calibration of
  verifier models (AMB-040).
- Whether and how hypotheses induced from an experimental design are generated (AMB-039).
- The link from a record to the raw dataset it reports on (AMB-041).

## [3.4.0] - 2026-10-06

This release makes the record a **hub** rather than a container: a record now carries the hooks that a
knowledge graph, a corpus and a QA set are built from, so no consumer has to parse the quote a second time
(`docs/downstream.md`, AMB-038). All additions are provisional. No existing field changes type, availability
or meaning, and records of earlier versions stay valid.

### Added
- **4 fields** (group `transform`, role `relation`):
  - `transform.predicate_mention` (D): the words of the quote that connect subject and object, verbatim. With
    `subject_mention` and `object_mention` it makes the statement explicit at extraction time. Until now the
    only predicate fields were human judgment (`predicate_label`) or ontology IDs (`predicate_id`), so an
    extracted statement had no predicate at all.
  - `transform.predicate_code` (N): a code of vocabulary `predicate_label`, set only when the cue words and the
    entity types of both ends match exactly one code, and never for a negated relation ("was not associated
    with" stays verbatim). It never replaces the reviewed `predicate_label`.
  - `transform.predicate_start_offset`, `transform.predicate_end_offset` (N): where the predicate stands in
    `common.source_quote`.
- **Type `array_entity_link`** (`transform.entity_links`) gains optional `start`, `end` (character offsets of
  the mention in `common.source_quote`) and `relation_role` (`subject` / `object`). The pipeline now writes one
  marker per entity mention of a record, typed by the field that lists it.
- **Vocabulary `predicate_label`**: every code gains `cues`, `subject_types` and `object_types`, the lexicon
  that `predicate_code` is derived from. These are repository proposals (AMB-038).
- **Rules** (both warnings):
  - `R033` (inferred): a statement with subject and object should give a predicate.
  - `R034` (definitional; new rule kind `offsets_match_text`): the offsets of markers and of the predicate must
    point at their mention in the quote.
- **Profile `pdf_extraction`**: semantic roles `relation_subject` / `relation_predicate` / `relation_object`
  and the normalizer `relation_anchors`. The extraction brief gains a "Relations" section built from them.
- **`bdc derive`** reads the hooks and writes four more outputs: `statements.csv` (one typed, anchored
  subject–predicate–object row per statement, with `predicate_status`, qualifiers and hedge),
  `graph.json` (property graph), `qa.jsonl` (cloze QA seeds that cite their records) and entity offsets plus
  statement IDs on every corpus chunk. Corpus and QA rows are keyed by the `transform.chunk_*` / `qa_*` field
  names.

### Changed
- `bdc derive` corpus keys follow the catalog: `text` → `chunk_text`, `support_ids` → `chunk_support_ids`,
  `page` → `chunk_page`, `section` → `chunk_section`. A statement whose only predicate is verbatim is written
  as `bdc:stated_relation` with `predicate_mention`; `bdc:unlabelled_relation` remains for statements with no
  predicate at all. The statement ID is a content hash (`stm_…`) instead of the record node.
- The generated field reference moved from the repository root (`FIELD_DEFINITIONS.md`) to
  `docs/generated/field_definitions.md`, next to the other generated documents.

## [3.3.0] - 2026-10-06

### Added
- Three optional provisional sample fields from merged v2: biological replicate ID, technical replicate ID, and verbatim sampling time.
- Archived merged v2 sources, mapping coverage and a migration command for document/unit inputs, observations, linked omics samples/assays and assets, with rejected records and loss accounting.
- Integration audit and regression tests for evidence, references, UTC conversion and conflicting values.

## [3.2.0] - 2026-09-30

This release records **what every key is for**. It follows the data owner's four record functions
(`sources/project/record_functions.md`) and the research contents of Topics 1–3
(`sources/project/research_contents.md`). It also adds the fields and rules that the evidence chain and the
derived views were missing, reviewed through the TRACE argument lens (Toulmin + Flavell, arXiv:2605.29656).
All additions are provisional. No existing field changes type, availability or meaning.

### Added
- **Annotations on every field** (AMB-032):
  - `key_role`: what the key does. There are 25 roles in 6 families. Each role states how it projects into a
    knowledge graph, relational tables, triples and QA/corpora, and which function facets it feeds.
  - `serves`: which of the four functions the key serves:
    - `topic2` — Topic 2 scientific agent;
    - `topic3` — Topic 3 skills;
    - `derivation` — KG / relational tables / QA / corpus / triples;
    - `iteration` — our own iteration, i.e. Topic 1 (confirmed by the data owner: this repository is Topic 1's).
  - `card`: for Topic 2/3 fields, the hypothesis, experiment-design or result-analysis card the field feeds.
  - `argument_role`: the Toulmin/Flavell element of the field (AMB-033).
  - `bdc check` guarantees that functions and cards stated by the v3 downstream column are never dropped or
    rewritten. Functions added by the repository are listed separately in `docs/generated/field_functions.md`.
- **Catalog codes**: `codes.function` (with facets taken from the research contents), `codes.key_role`,
  `codes.key_role_family`, `codes.card` and `codes.argument_role`. Groups `agent`, `skills` and `transform`
  declare the function they serve.
- **9 fields**:
  - Topic 2 evidence chain:
    - `agent.claim_qualifier_text` (D): the verbatim hedge;
    - `agent.stated_limitations` (D): limitations stated by the authors;
    - `skills.method_record_ids` (N): the result → method link.
  - Derivation:
    - `transform.entity_links` (type `array_entity_link`): mention → entity ID pairs (AMB-034);
    - `transform.qa_id` (G).
  - Iteration / Topic 1:
    - `common.extraction_profile` (N);
    - `common.replaces_record_ids` (N);
    - `common.conflict_resolution_status` (I, new vocabulary `conflict_resolution_status`);
    - `common.record_updated_at` (N) (AMB-036).
- **Rules**:
  - `R031` (warning, definitional; new dataset rule kind `references_resolve`): evidence-chain references
    must resolve within the dataset.
  - `R032` (warning, inferred; new condition `matches`): a claim whose quote hedges should keep the qualifier
    text (AMB-035).
- **Profile `pdf_extraction`**:
  - `record_links` (`evidence` → `agent.evidence_record_ids`, `method` → `skills.method_record_ids`);
    candidates may now carry `ref` and `links`;
  - system field `common.extraction_profile`.
- **Ambiguities**: AMB-032 … AMB-036.

## [3.1.0] - 2026-09-28

The merge release adds the legacy v1 document-level design and the omics 2.0.0 candidate template. Every
added field is `provisional`, and the existing 259 v3 fields are unchanged.

### Added
- `common.schema_name` (AMB-013). It is optional in the catalog and required by the extraction profiles,
  which fill it automatically.
- Fields from **legacy_v1** (17):
  - document metadata: document type (A-1 codes), journal, volume, issue, publication page range (never the
    physical page, AMB-029), abstract, keywords, funding, affiliations;
  - cM interval bounds;
  - marker type and primers;
  - variety approval number;
  - pedigree text;
  - effect type.
- Fields from **omics_v2** (111):
  - 68 in the new `omics` group: experiment, feature, cross-species, transcriptomics, single-cell,
    epigenomics, proteomics and metabolomics;
  - 43 in `common` / `agent` / `skills` / `transform`: sample, tissue, treatment, reference system, variant,
    statistics and tool I/O.
  - The template gives names only, so definitions are literal renderings and types are assigned by the
    repository (AMB-026).
- Vocabularies:
  - `document_type` (error);
  - `trait_category` (warning, proposed codes);
  - `crop_name` (open; also drives automatic crop detection);
  - `predicate_label` (open);
  - `omics_type` (open);
  - `candidate_gene_status` (warning; codes from the omics template).
  - `population_type` and `method_category` are extended with legacy A-4 and A-9 codes.
- Rules:
  - R027: cM start ≤ end;
  - R028: peak start ≤ end;
  - R029: positions should name the assembly (warning);
  - R030: the effect allele should be ref or alt (warning).
- Profile `pdf_extraction_omics` (extends `pdf_extraction` with the omics group).
- Ambiguities AMB-013 and AMB-026 … AMB-031.
- Source mappings `mappings/legacy_to_current.yaml` (713 leaves) and `mappings/omics_to_current.yaml`
  (252 leaves), with issue registers LEG-001 … LEG-012 and OMX-001 … OMX-010.

### Changed
- `pdf_extraction`:
  - new document-level fields;
  - `schema_name` is system-filled and required;
  - `source_abstract` is excluded from per-row records;
  - `source_language` is exempt from the literal value-presence check.
- `compact`: includes `common.schema_name`.
- `common.crop_name`, `agent.candidate_gene_status` and `transform.predicate_label` are bound to the new
  vocabularies. All three are open or warning level, so records that were valid do not become invalid.

## [3.0.0] - 2026-09-28

Faithful import of the v3.0.0 field baseline (`sources/fields_v3/`). It adds no new breeding semantics.

### Added
- 259 logical fields in four groups: `common` 127, `agent` 46, `skills` 46, `transform` 40. They keep the
  source definitions, D/N/I/G/F availability and Y/C/N requirement codes, and every field has a source line
  reference.
- Record kinds and their grains from the source "记录粒度" section. The grain of `analysis_result` stays
  unresolved (AMB-007).
- 26 cross-field rules. Rules taken from explicit source statements are errors. Rules that are only implied by
  the source are warnings (`basis: inferred`).
- 25 vocabularies:
  - code lists given by the source are enforced as errors;
  - proposed codes for Chinese-only closed lists are warnings;
  - open lists are suggestions;
  - a deterministic unit-conversion table.
- Profiles:
  - `full`: every active field;
  - `compact`: the 157-field first production set from the source;
  - `pdf_extraction`: D fields for models, N fields computed by named pipeline rules, and I/G/F fields never
    exposed.
- Repository conventions for stable record IDs, locators and spans (AMB-011), and the omit-don't-null
  missing-value policy.
- Ambiguity register: AMB-001 … AMB-025, with AMB-013 reserved.
