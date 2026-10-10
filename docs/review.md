# Quality, verification and review: who checks what

A record passes several checks before anyone relies on it. They differ in what they can decide, and that
decides who performs them. This document describes the three layers, the status a record carries after each,
and the verification pass added in 3.5.0. The division of labour and the evidence-strength rubric are open
points for the data owners and the breeding experts (AMB-040).

## Three layers

| Layer | Decides | Performed by | Cannot decide |
| --- | --- | --- | --- |
| **1. Deterministic checks** | Is the record well formed? Does the quote stand on the stated page? Is each value literally on that page? Do links point at existing records? Is the structure complete (evidence chain, workflow)? Was a cited part of the paper not supplied? | the pipeline and the validator, on every run | whether a value is what the quote *says* |
| **2. Independent verification** | Does the quote state this value for this field? Does the paper connect these two records in the claimed way? Do two records of one paper contradict each other? Did the extraction miss a statement that matters? | a verifier that is **not** the extractor: another model, through `bdc verify` | whether the science is sound, how strong the evidence is |
| **3. Expert review** | Fields of human judgment (evidence strength and type, hypothesis origin, polarity, conflict resolution); soundness of a design; final approval | breeding experts, on a risk-based sample | — |

**Experts or a model?** Both, for different questions. Whether a sentence states a value is a reading task:
a model does it for every record, cheaply and repeatably. Whether a split-luciferase assay is enough to claim a
mechanism is a judgment that needs a breeder or a molecular geneticist. A model that verifies can send a record
back; it can never approve one in an expert's place. Experts then spend their time on the records the first
two layers could not settle, and on a sample of those they passed, which also measures how far the verifier
can be trusted.

## Review status

| `common.review_status` | Set by | Means |
| --- | --- | --- |
| `pending_review` | pipeline, or verification | a check left a warning; `common.qc_failure_codes` says which |
| `auto_validated` | pipeline | all deterministic checks passed |
| `model_verified` | `bdc verify apply` | an independent verifier judged every field and link of the record supported by the paper |
| `expert_approved` / `rejected` | a reviewer | a person decided |

A consumer chooses its threshold: a candidate graph may load `auto_validated`, a published one
`model_verified` or `expert_approved` only.

## Layer 1: what is checked on every run

- **Schema and rules** of the contract (`bdc validate`).
- **Evidence.** The quote must occur on the stated page of the stated part, otherwise the candidate is
  rejected. Values that are not literally on the page raise a warning.
- **Link closure.** A link to a rejected, missing or wrong-kind candidate is dropped and flagged.
- **Evidence chain** (`argument_structure`): which Toulmin/Flavell elements a statement has, own and through
  its links.
- **Workflow structure** (`workflow_structure`, `docs/workflow.md`): an untested hypothesis, a conclusion
  without evidence, a dependency cycle.
- **Source completeness** (`source_parts`, `docs/downstream.md`): a record whose quote cites a figure or table
  of a part that was not supplied is marked `SOURCE_PART_UNAVAILABLE`.

These checks are literal. A value that stands on the page passes even when it belongs to another sentence.

## Layer 2: `bdc verify`

```bash
bdc verify tasks out/paper.jsonl --out review/
# → review/paper.verify.tasks.json              what to judge, with instructions
# → review/paper.verify.verdicts.template.json  the format of the answer

# the verifier (a model that is not the extraction model) writes review/paper.verify.verdicts.json

bdc verify apply out/paper.jsonl review/paper.verify.verdicts.json --out review/ \
    --manifest out/paper.manifest.json
# → review/paper.verified.jsonl      the records with updated review fields
# → review/paper.verification.json   the report
```

**Tasks.** One task per record: the quote, and every value the extraction model filled, each with the
definition of its field. One task per link: the two quotes and what the link claims. Fields the model did not
fill (identifiers, locators, document metadata, computed values) are not tasks.

```json
{"task_id": "vt_132c4294fdadbb35e908", "kind": "record", "record_kind": "observation",
 "quote": "The knockout lines of HTR1 showed lower survival than WY after heat treatment (fig. S2).", "page": 2,
 "fields": [{"path": "common.germplasm_names", "value": ["SL14"], "definition": "…"}, …]}

{"task_id": "vt_c584974b9426897093bd", "kind": "link", "edge": "prerequisite", "meaning": "…",
 "source": {"quote": "To test whether HTR1 underlies qHT3, we generated knockout lines of HTR1 in WY by CRISPR/Cas9.", "page": 2},
 "target": {"record_id": "rec_3a0f62bc…", "quote": "Using 1,614 BC4F3 plants from this population, qHT3 was narrowed …", "page": 2}}
```

**Verdicts.** `supported`, `not_supported` or `uncertain` per task, with a one-sentence reason for the last
two. The verifier may also list `conflicts` (records of the paper that contradict each other) and `omissions`
(statements that matter and that no record captures).

```json
{"verifier": {"method": "model", "model": "<verifier model>"},
 "input_sha256": "<hash of paper.jsonl, copied from the task file>",
 "verdicts": [
   {"task_id": "vt_132c4294fdadbb35e908", "verdict": "not_supported",
    "unsupported_fields": ["common.germplasm_names"],
    "reason": "The sentence compares the HTR1 knockout lines with WY. SL14 is named on the same page, not in this quote."},
   {"task_id": "vt_c584974b9426897093bd", "verdict": "uncertain",
    "reason": "The knockout follows the fine mapping in the text, but the paper does not say that it used the mapped interval."}],
 "conflicts": [{"record_ids": ["rec_eb88edbd…", "rec_4347364e…"],
                "reason": "Duration of the heat treatment: 12 h in the Results, 14 h in the Materials and Methods."}],
 "omissions": [{"page": 2, "source_part": "supplement", "quote": "WY 21.3 %",
                "note": "The survival of the recurrent parent has no record."}]}
```

**Apply.** The verifier reads; it never writes records. `apply` moves the review fields only:

| Verdicts of a record | Effect |
| --- | --- |
| every task `supported`, record was `auto_validated` | `model_verified` |
| any task `not_supported` or `uncertain` | `pending_review`, with `VERIFY_FIELD_NOT_SUPPORTED`, `VERIFY_LINK_NOT_SUPPORTED` or `VERIFY_UNCERTAIN` in `common.qc_failure_codes` |
| some tasks unanswered | status unchanged: partial coverage promotes nothing |
| record is `expert_approved` or `rejected` | untouched |
| the verifier is the extraction model (read from the manifest) | nothing is promoted; demotions still apply |
| record was sent back by an earlier verification, now every task `supported` | stays `pending_review` with the earlier codes: a second verifier does not clear the objection of the first, a reviewer or a corrected extraction does |

Every judged record gets `common.verification_run_id`, a new `common.record_version` and
`common.record_updated_at`. Its ID and its content stay as they were: a wrong value is corrected by fixing the
candidates and running the extraction again, or by a reviewer. Conflicts and omissions go to the report as
candidates for review and are written to no record.

In the example (`examples/output/review/`), 41 tasks are judged for 21 records. Seventeen records become
`model_verified`. Two are sent back: the observation whose line name is not in its quote, and the step whose
dependency on the fine mapping the paper does not state. Both had passed every deterministic check.

### Is the logic of a procedure verified?

In parts, by different layers:

- **Structure** is checked deterministically: cycles, steps that lead nowhere, hypotheses nothing tests.
- **Each link** is a verification task: was this experiment run to test that hypothesis, does this step use
  the output of that one. The instructions say that order of presentation is not a dependency.
- **Soundness** (are the controls adequate, does the statistic fit the design, does the conclusion follow) is
  not decided by any automatic step. The records carry what an expert needs to judge it: design, replicates,
  test, hedge, stated limitations.

## Layer 3: experts

Experts own what the contract marks as human judgment (availability I) and the final status:

- `agent.evidence_strength`, `agent.evidence_type`, `transform.relation_evidence_type`,
  `transform.relation_polarity`, `agent.hypothesis_origin`;
- `common.conflict_record_ids` and `common.conflict_resolution_status`, starting from the conflict candidates;
- `expert_approved` / `rejected`.

### Evidence strength: a rubric is needed

`agent.evidence_strength` is defined as "assessed by predefined rules", and the rules do not exist yet. Until
the experts set them, the field stays empty. The records already carry the inputs such a rubric would use, so
a proposal can be tested on real data:

| Input | Where it is |
| --- | --- |
| kind of evidence | `transform.relation_evidence_type`: statistical localisation, expression support, functional validation, and from 3.5.0 genetic interaction, localisation imaging, biochemical assay, pharmacological perturbation |
| direct test of the hypothesis | a `tests` link from a step or result |
| independent lines of evidence | the number and kinds of records behind the `evidence` links |
| replication and statistics | `agent.replicate_count`, `agent.statistical_test`, effect size and significance fields |
| authors' own caution | `agent.claim_qualifier_text`, `agent.stated_limitations` |
| contradiction within the paper | conflict candidates |

The four new evidence-type codes are repository proposals; mechanism papers could not be described with the
three codes that existed.

### Sampling and calibration (proposal)

- Review **every** record that verification sent back, and every conflict candidate.
- Review a **sample** of `model_verified` records, stratified by record kind and by flag, with a higher rate
  for conclusions and hypotheses than for table cells.
- Keep a **calibration set**: records that experts have judged independently. Run each verifier model on it
  before it is used, and again when the model or the instructions change. Agreement on that set is what
  justifies trusting `model_verified`.

Rates and set sizes are for the data owners to decide.

## Open points (AMB-040)

- The evidence-strength rubric and the four new evidence-type codes.
- Sampling rates, the size of the calibration set and the agreement a verifier must reach.
- Whether one verifier model is enough or two must agree.
- Omission candidates are only reported. Whether they should feed a second extraction pass automatically.
- Expert decisions are written into records by a reviewer tool that does not exist yet; `bdc verify` records
  model verification only.
