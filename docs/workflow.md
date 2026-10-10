# The research workflow of a paper: question → hypothesis → experiment → result → conclusion

```
 background ◄─ research question ◄─ objective ◄─ hypothesis ◄──────────── conclusion
                    addresses         addresses      ▲   addresses            │ evidence
                                                     │ tests                  ▼
                                    step ◄──────── step ◄──── method ──── result / observation
                                       prerequisite
```

An agent that plans research (Topic 2) needs more than the facts of a paper. It needs to know which question
the authors asked, which hypothesis each experiment was run to test, what each step used and produced, and
which results a conclusion rests on. This document describes how the contract states that, from 3.5.0 on. The
additions are provisional (AMB-039).

## Design: a view over the records, not a second format

The workflow is **not** extracted as a separate document. Every element of it is already an atomic record
with a page and a verbatim quote. What was missing are the roles and the links:

- A **node** is a record. Its stage is the role the paper gives the statement (`agent.statement_role`) or,
  without one, its record kind.
- An **edge** is a link between two records of the same paper, stored as record IDs.
- `bdc derive` builds the workflow from them (`paper.workflow.json`) and never adds a node or an edge of its
  own.

This keeps one source of truth. A step that is corrected in the records is corrected in the knowledge graph,
the corpus and the workflow at once, and every node of the workflow can be checked against its quote.

### Stages

| Stage | Comes from | Typical wording in a paper |
| --- | --- | --- |
| `background` | `agent.statement_role` | what is known and why it matters |
| `research_question` | `agent.statement_role` | "… remains unknown", "whether … is unclear" |
| `objective` | `agent.statement_role` | "the objective of this study was …", "we aimed to …" |
| `hypothesis` | `agent.statement_role` | "we hypothesized that …", "to test whether …" |
| `design` | `agent.statement_role` | replicates, controls, randomisation, the statistical test |
| `step` | record kind `method` | what was done: a cross, a treatment, an assay, an analysis |
| `observation` | observation record kinds | a measured value, a table cell |
| `result` | `agent.statement_role`, or record kind `analysis_result` | "… showed higher survival than …", a mapped interval |
| `conclusion` | `agent.statement_role` | "these results indicate that …" |
| `statement` | record kind `claim` without a role | any other statement of the paper |

The role is filled by the extraction model (availability D) from vocabulary `statement_role`, and only when
the wording or the position of the statement shows it. A statement without a clear role has none.

### Edges

| Edge | Field (filled by the pipeline from candidate `links`) | From → to | Meaning |
| --- | --- | --- | --- |
| `evidence` | `agent.evidence_record_ids` | conclusion, hypothesis → result, observation | the statement rests on that result |
| `method` | `skills.method_record_ids` | result, observation → step | the result was produced by that step |
| `tests` | `agent.tests_record_ids` | step, result, observation → hypothesis, question, objective | the experiment was run to test it. The link does not say whether the test supported or refuted it |
| `addresses` | `agent.addresses_record_ids` | hypothesis, objective, question, conclusion → background, question, objective, hypothesis | the statement answers or narrows that one |
| `prerequisite` | `agent.prerequisite_record_ids` | step, result → step, observation, result | the step uses the output of that record |

`evidence` and `method` exist since 3.2.0; the other three are new. Which field makes which edge is an
annotation in the catalog (`workflow_edge`), so the exporter contains no field list. Rule `R035` reports a
workflow link that points to no record of the file.

**Steps** are `method` records, one per step, each with its own quote. **Order** is not stored: it follows
from the `prerequisite` links. A record that several steps depend on is a **branch point**. A precondition or
branching rule that the paper states ("only recombinant plants that survived were advanced") is kept verbatim
in `agent.step_condition`. Inputs and outputs of a step are the existing fields of the method record
(materials, treatment groups, indicators) plus the records it is linked to.

## What the extraction model writes

Candidates carry a local `ref` and `links` to other candidates; the pipeline turns them into record IDs. The
example is the synthetic two-file paper `examples/papers/synthetic_rice_heat.pdf` (abridged):

```json
{"record_kind": "claim", "ref": "h_under",
 "fields": {"agent.statement_role": "hypothesis", "agent.hypothesis_stated": "HTR1 underlies qHT3"},
 "links": {"addresses": ["obj"]},
 "evidence": {"page": 2, "quote": "To test whether HTR1 underlies qHT3, we generated knockout lines of HTR1 in WY by CRISPR/Cas9."}}

{"record_kind": "method", "ref": "m_ko",
 "fields": {"skills.method_name": "CRISPR/Cas9"},
 "links": {"tests": ["h_under"]},
 "evidence": {"page": 2, "quote": "To test whether HTR1 underlies qHT3, we generated knockout lines of HTR1 in WY by CRISPR/Cas9."}}

{"record_kind": "observation", "ref": "r_ko",
 "fields": {"agent.statement_role": "result",
            "agent.actual_observation": "The knockout lines of HTR1 showed lower survival than WY after heat treatment"},
 "links": {"method": ["m_ko", "m_heat"], "tests": ["h_under"]},
 "evidence": {"page": 2, "quote": "The knockout lines of HTR1 showed lower survival than WY after heat treatment (fig. S2)."}}

{"record_kind": "method", "ref": "m_heat",
 "fields": {"agent.treatment_groups": ["42 C for 14 h"]},
 "evidence": {"part": "supplement", "page": 1,
              "quote": "Twelve-day-old seedlings were treated at 42 C for 14 h and survival was scored after 7 days of recovery."}}
```

One sentence can yield two records, here the hypothesis and the step that tests it. The treatment protocol is
in the supplementary file, so its evidence names that part (see `docs/downstream.md`, "Source parts").

Three rules apply, and the extraction brief states them:

- **A hypothesis is recorded only when the authors state one.** A hypothesis that a reader could infer from
  the experimental design is not extracted. If induced hypotheses are wanted, they are a later, separate
  generation step, marked by `agent.hypothesis_origin`; how that step runs is open (AMB-039).
- **A link is written only where the paper connects the two statements.** "To test this, we …" is a `tests`
  link. Two sentences that follow each other are not.
- **Order of presentation is not a dependency.** A `prerequisite` link needs a stated use: "using plants from
  this population", "the lines generated above".

## The view: `paper.workflow.json`

```bash
bdc derive out/paper.jsonl --out derived/
```

| Key | Content |
| --- | --- |
| `nodes` | one per record that has a stage or a workflow link: `id`, `stage`, `record_kind`, `label`, `source_part`, `source_page`, `condition`, `flags` |
| `edges` | `{s, type, o, field}`; `unresolved: true` when the target is not in the file |
| `step_order` | the records joined by `prerequisite` links, in dependency order |
| `branch_points` | records that more than one record depends on |
| `hypotheses` | one trace per hypothesis: what it `addresses`, what it is `tested_by`, its `evidence`, what it is `addressed_by` |
| `stages`, `edges_by_type`, `flags` | counts |

For the example paper (`examples/derived/synthetic_rice_heat.verified.workflow.json`):

```json
"hypotheses": [
  {"hypothesis": "rec_4dab0ec5…", "label": "HTR1 underlies qHT3",
   "addresses": ["rec_79044e3e…"],
   "tested_by": ["rec_6427ec70…", "rec_0944532b…"]},
  {"hypothesis": "rec_996ddd2f…", "label": "HTR1 might recruit HTR2 precursors to endosomes for degradation",
   "addresses": ["rec_78858b93…"]}
]
```

The first hypothesis is tested by the knockout step and by its result. The second has no `tested_by`: the
paper states the hypothesis and reports an interaction assay next to it, but never says that the assay was run
to test it. The view shows the gap instead of closing it.

### Structural flags

The validation report (`workflow_structure`), `bdc audit` and the view list gaps in the structure:

| Flag | Meaning |
| --- | --- |
| `HYPOTHESIS_UNTESTED` | a hypothesis that no step, observation or result is linked to as its test |
| `QUESTION_UNADDRESSED` | a research question or objective that no hypothesis, test or conclusion points to |
| `CONCLUSION_WITHOUT_EVIDENCE` | a conclusion that links no observation or result as its grounds |
| `RESULT_WITHOUT_METHOD` | a result with no link to the step that produced it or that it builds on |
| `STEP_WITHOUT_OUTPUT` | a step that no result cites as its method and no later step depends on |
| `DEPENDENCY_CYCLE` | `prerequisite` links that form a cycle |
| `UNRESOLVED_LINK` | a workflow link points to a record that is not in the file |

A flag is a **review hint**, not an error. It means one of three things: the paper leaves the gap, the
extraction missed a link, or the linked part of the paper was not supplied (a methods section in a missing
supplement). The flags say nothing about whether an experiment is sound; that is a question for the
verification pass and for experts (`docs/review.md`).

## Reading a hand-built workflow against the contract

Topic 2 analysed one paper by hand into a single JSON document (background, question, hypotheses, workflows
with steps, results, conclusions, conflicts). Every part of that document has a place in the records:

| Part of the hand-built document | In the contract |
| --- | --- |
| research background; question and objective | `claim` records with `agent.statement_role` `background`, `research_question`, `objective`; the text in `agent.finding_text`, `agent.knowledge_gap`, `agent.experiment_objective` |
| hypotheses, numbered, each with its basis | `claim` records with role `hypothesis` and `agent.hypothesis_stated`; `addresses` links to the question |
| "nature of the statement" of a hypothesis (stated or induced) | `agent.hypothesis_origin` (human judgment); only stated hypotheses are extracted |
| workflow → hypothesis ("对应假设") | `tests` links from the steps and results to the hypothesis |
| steps with input, tool or method, operation, output | one `method` record per step; `prerequisite` links for what a step uses; `method` links from the results it produced |
| key conditions | condition fields of the step (`agent.treatment_groups` …) and `agent.step_condition` |
| statistical configuration (replicates, unit, test, error bars) | `method` records with role `design`: `agent.replicate_count`, `agent.statistical_test`, `agent.control_groups` |
| results, each with its hypothesis | `observation` / `analysis_result` records with role `result`; `tests` and `method` links |
| conclusions and their mechanism chain | `claim` records with role `conclusion`; `evidence` links; the chain is the subject–predicate–object statements of those records |
| evidence hierarchy | `transform.relation_evidence_type` and `agent.evidence_strength`, both human judgment; the rubric is open (AMB-040) |
| boundaries of the conclusions | `agent.claim_qualifier_text`, `agent.stated_limitations`, `agent.knowledge_gap` |
| conflicts and unclear points inside the paper | conflict candidates of the verification report; once reviewed, `common.conflict_record_ids` and `common.conflict_resolution_status` |
| page lists per item | every record: part, physical page, verbatim quote, character span |
| paths of the source files | never stored (rule R020): `common.source_id` plus one `asset_manifest` record per file with its hash and `common.source_part` |

Two differences are deliberate. The hand-built document cites pages; a record cites a quote that the pipeline
has found on that page, so a wrong citation is rejected instead of passing unnoticed. And the document groups
steps into numbered workflows; here a workflow is the set of steps that reach a hypothesis through `tests` and
`prerequisite` links, so a step shared by two lines of work appears once.

## Open points for the data owners (AMB-039)

- The role vocabulary, the three link types and the flag codes are repository proposals.
- Whether hypotheses induced from the design should be produced at all, by which step, and how they are kept
  apart from stated ones.
- `agent.workflow_steps` (an embedded array on one record) stays for a procedure that a single passage
  describes as a whole. Steps that are linked, tested or cited individually are `method` records. Whether the
  array should be retired is not decided.
- Controls are a field of the step today. If Topic 2 needs to link a control to the comparison it serves, that
  needs a further link type.
