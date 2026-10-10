"""Semantic verification of records by an independent verifier (AMB-040).

Format validation, quote verification and link closure are deterministic. They cannot tell whether a field
value is what the quote says, or whether two linked records really belong together. That takes reading, so it
is a second pass by a verifier that is *not* the extractor: another model, or a person.

    bdc verify tasks  paper.jsonl --out review/            # what to judge, one task per record and per link
    (the verifier writes paper.verify.verdicts.json)
    bdc verify apply  paper.jsonl paper.verify.verdicts.json --out review/

The verifier reads; it never writes records. ``apply`` only moves the review fields:

* every task of a record judged ``supported`` and the record ``auto_validated``  ->  ``model_verified``
* any task ``not_supported`` or ``uncertain``  ->  ``pending_review`` with a ``VERIFY_*`` quality code
* a record an expert has approved or rejected is never touched; nothing is ever promoted to expert approval
* a record with unanswered tasks is not promoted
* a record that an earlier run sent back is not cleared by a later run that objects to nothing

Content is not corrected here: a wrong value goes back to extraction or to a reviewer. The verifier may also
report records of one source that contradict each other and statements the extraction missed; both are listed
in the report as review candidates and written to no record.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .util import ContractError, dumps_json, dumps_jsonl, get_path, iter_fields, set_path, sha256_file, utc_now

VERIFY_FORMAT = 1
VERDICTS = ("supported", "not_supported", "uncertain")
RUN_ID_PATH = "common.verification_run_id"
STATUS_PATH = "common.review_status"
QC_PATH = "common.qc_failure_codes"
CODE_FIELD, CODE_LINK, CODE_UNCERTAIN = "VERIFY_FIELD_NOT_SUPPORTED", "VERIFY_LINK_NOT_SUPPORTED", "VERIFY_UNCERTAIN"
VERIFY_CODES = (CODE_FIELD, CODE_LINK, CODE_UNCERTAIN)
PROMOTE_FROM, PROMOTED, DEMOTED = "auto_validated", "model_verified", "pending_review"
EXPERT_STATUSES = ("expert_approved", "rejected")
# Roles a quote cannot support or refute: where the evidence is, and what the document as a whole is.
SKIP_ROLES = frozenset({"record_identity", "source_identity", "bibliographic", "evidence_locator", "lifecycle",
                        "asset", "governance"})

INSTRUCTIONS = """\
You are verifying extracted records against the paper. You are not the extractor: judge, do not repair.

Task kind `record`: the record's quote is verbatim text of the paper. For every entry of `fields`, decide
whether the quote states that value for that field (the definition says what the field means). A value is
supported when the quote states it literally or by an unambiguous restatement, with the same direction,
negation, unit and scope. It is not supported when it comes from background knowledge, from another passage,
or when the quote hedges what the field asserts. Verdict `supported` only if every field is supported;
otherwise `not_supported` and list the offending paths in `unsupported_fields`.

Task kind `link`: two records of the same paper and the relation the link claims (`meaning`). Decide whether
the paper itself connects them in that way: the conclusion rests on that result, the result was produced by
that method, the experiment was run to test that hypothesis, the step uses the output of that earlier step.
Use the two quotes and, when you need context, the cited pages. Order of presentation is not a dependency.

Use `uncertain` when the quote or pages do not let you decide. Give a one-sentence `reason` for every verdict
that is not `supported`.

Also report, without changing any verdict:
- `conflicts`: records of the same source that contradict each other (the same quantity under the same
  conditions with different values, a figure label against its legend). Give the `record_ids` and a `reason`.
- `omissions`: statements of the paper that matter (a hypothesis, a control, a condition, a result) and that no
  record captures. Give `page`, a verbatim `quote` and a short `note`.
"""


def _tid(*parts) -> str:
    return "vt_" + hashlib.sha256("\x1f".join(map(str, parts)).encode("utf-8")).hexdigest()[:20]


def _document_fields(rc, rec: dict) -> set[str]:
    """Fields the extraction profile fills once per document: they are repeated on every record and are not
    statements of the record's quote."""
    name = get_path(rec, "common.extraction_profile", None)
    try:
        return set(rc.profile(name).get("document_fields") or []) if name else set()
    except ContractError:
        return set()


def build_tasks(records: list[dict], rc) -> list[dict]:
    """One `record` task per record with a quote and directly extracted values, one `link` task per resolved
    record link. Task IDs are content hashes, so `apply` recomputes them from the records."""
    fields = {f["path"]: f for f in rc.contract["fields"]}
    edge_labels = (rc.contract.get("codes") or {}).get("workflow_edge") or {}
    arg_labels = (rc.contract.get("codes") or {}).get("argument_role") or {}
    by_id = {get_path(r, "common.record_id", None): r for r in records}
    tasks: list[dict] = []

    def where(rec: dict) -> dict:
        w = {"quote": get_path(rec, "common.source_quote", None), "page": get_path(rec, "common.source_page", None),
             "source_part": get_path(rec, "common.source_part", None)}
        return {k: v for k, v in w.items() if v is not None}
    for rec in records:
        rid = get_path(rec, "common.record_id", None)
        quote = get_path(rec, "common.source_quote", None)
        if not rid:
            continue
        doc_fields = _document_fields(rc, rec)
        values = {p: v for p, v in iter_fields(rec)
                  if p in fields and fields[p]["availability"] == "D" and p not in doc_fields
                  and fields[p].get("key_role") not in SKIP_ROLES}
        if quote and values:
            tasks.append({"task_id": _tid(rid, "record"), "kind": "record", "record_id": rid,
                          "record_kind": get_path(rec, "common.record_kind", None), **where(rec),
                          "fields": [{"path": p, "value": v, "definition": fields[p]["definition_zh"]}
                                     for p, v in values.items()]})
        for p, v in iter_fields(rec):
            f = fields.get(p) or {}
            if f.get("key_role") != "record_link" or f.get("type") != "array_string":
                continue
            edge = f.get("workflow_edge")
            meaning = (edge_labels.get(edge) or {}).get("description_zh") or \
                (arg_labels.get(f.get("argument_role")) or {}).get("description_zh") or f["definition_zh"]
            if not edge and f.get("argument_role") not in ("data", "warrant"):
                continue  # bookkeeping links (replaces, provenance of derived rows) are not claims of the paper
            for target in v:
                t = by_id.get(target)
                if t is None:
                    continue  # an unresolved link is already flagged by the dataset rules
                tasks.append({"task_id": _tid(rid, "link", p, target), "kind": "link", "record_id": rid,
                              "field": p, **({"edge": edge} if edge else {}), "meaning": meaning,
                              "source": where(rec), "target": {"record_id": target, **where(t)}})
    return tasks


def tasks_file(path: Path | str, out_dir: Path | str, rc) -> dict:
    """Write <stem>.verify.tasks.json and <stem>.verify.verdicts.template.json."""
    path, out_dir = Path(path), Path(out_dir)
    records = _read(path)
    tasks = build_tasks(records, rc)
    stem = _stem(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {"verify_format": VERIFY_FORMAT, "input": {"file": path.name, "sha256": sha256_file(path)},
           "contract": rc.identity(), "verdicts": list(VERDICTS), "instructions": INSTRUCTIONS, "tasks": tasks}
    (out_dir / f"{stem}.verify.tasks.json").write_text(dumps_json(doc), encoding="utf-8")
    template = {"verifier": {"method": "model", "model": "<verifier model id; not the extraction model>"},
                "input_sha256": doc["input"]["sha256"],
                "verdicts": [{"task_id": t["task_id"], "verdict": "<supported|not_supported|uncertain>"}
                             for t in tasks[:2]],
                "conflicts": [], "omissions": []}
    (out_dir / f"{stem}.verify.verdicts.template.json").write_text(dumps_json(template), encoding="utf-8")
    return {"tasks": len(tasks), "by_kind": _count(t["kind"] for t in tasks), "records": len(records),
            "outputs": [f"{stem}.verify.tasks.json", f"{stem}.verify.verdicts.template.json"]}


def apply_verdicts(records: list[dict], verdicts_doc: dict, rc, run_id: str,
                   extraction_model: str | None = None) -> tuple[list[dict], dict]:
    """-> (records with updated review fields, report). Records are copied, never edited in place."""
    paths = {f["path"] for f in rc.contract["fields"]}
    if RUN_ID_PATH not in paths:
        raise ContractError(f"contract {rc.version} has no {RUN_ID_PATH}: verification needs records of a "
                            "contract version that defines it; re-extract or migrate the records first")
    verifier = verdicts_doc.get("verifier") or {}
    if verifier.get("method", "model") != "model" or not verifier.get("model"):
        raise ContractError("verdicts need verifier.method = model and verifier.model (expert review is recorded "
                            "by reviewers as expert_approved / rejected, not through bdc verify)")
    same_model = bool(extraction_model) and verifier["model"] == extraction_model
    tasks = build_tasks(records, rc)
    by_task = {t["task_id"]: t for t in tasks}
    given: dict[str, dict] = {}
    unknown, findings = [], []
    for v in verdicts_doc.get("verdicts") or []:
        if not isinstance(v, dict) or v.get("verdict") not in VERDICTS:
            raise ContractError(f"verdict must be one of {', '.join(VERDICTS)}: {json.dumps(v, ensure_ascii=False)[:200]}")
        if v.get("task_id") not in by_task:
            unknown.append(v.get("task_id"))
            continue
        given[v["task_id"]] = v
    per_record: dict[str, list[dict]] = {}
    for t in tasks:
        per_record.setdefault(t["record_id"], []).append(t)
    now = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    validator = rc.validator()
    out, before, after = [], [], []
    outcome = {"promoted": 0, "demoted": 0, "confirmed_pending": 0, "partially_verified": 0, "unchanged": 0,
               "withheld_same_model": 0, "unverified": 0, "skipped_expert_reviewed": 0, "no_tasks": 0}
    for rec in records:
        rid = get_path(rec, "common.record_id", None)
        status = get_path(rec, STATUS_PATH, None)
        before.append(status)
        mine = per_record.get(rid, [])
        answered = [(t, given[t["task_id"]]) for t in mine if t["task_id"] in given]
        if not mine:
            outcome["no_tasks"] += 1
        elif status in EXPERT_STATUSES:
            outcome["skipped_expert_reviewed"] += 1
        elif not answered:
            outcome["unverified"] += 1
        if not mine or status in EXPERT_STATUSES or not answered:
            out.append(rec)
            after.append(status)
            continue
        codes = set()
        for t, v in answered:
            if v["verdict"] == "supported":
                continue
            codes.add(CODE_UNCERTAIN if v["verdict"] == "uncertain" else CODE_LINK if t["kind"] == "link" else CODE_FIELD)
            findings.append({k: x for k, x in {
                "task_id": t["task_id"], "record_id": rid, "kind": t["kind"], "field": t.get("field"),
                "target_record_id": (t.get("target") or {}).get("record_id"), "verdict": v["verdict"],
                "unsupported_fields": v.get("unsupported_fields"), "reason": v.get("reason")}.items() if x})
        new = copy.deepcopy(rec)
        if codes:
            new_status = DEMOTED
            outcome["demoted" if status != DEMOTED else "confirmed_pending"] += 1
        elif len(answered) < len(mine):
            new_status = status
            outcome["partially_verified"] += 1
        elif status == PROMOTE_FROM and not same_model:
            new_status = PROMOTED
            outcome["promoted"] += 1
        elif status == PROMOTE_FROM:  # a verifier that is the extraction model confirms nothing
            new_status = status
            outcome["withheld_same_model"] += 1
        else:  # pending_review keeps its deterministic warnings; other statuses are left as they are
            new_status = status
            outcome["confirmed_pending" if status == DEMOTED else "unchanged"] += 1
        # The codes of this run replace those of an earlier one. A run that objects to nothing leaves an earlier
        # objection standing: only a reviewer or a corrected extraction clears it.
        existing = get_path(rec, QC_PATH, None) or []
        kept = [c for c in existing if c not in VERIFY_CODES] if codes else existing
        qc = sorted(set(kept) | codes)
        if qc:
            set_path(new, QC_PATH, qc)
        elif get_path(new, QC_PATH, None) is not None:
            del new[QC_PATH.split(".")[0]][QC_PATH.split(".")[1]]
        if new_status:
            set_path(new, STATUS_PATH, new_status)
        set_path(new, RUN_ID_PATH, run_id)
        set_path(new, "common.record_version", int(get_path(rec, "common.record_version", None) or 1) + 1)
        set_path(new, "common.record_updated_at", now)
        errors = validator.validate(new).errors
        if errors:
            raise ContractError(f"record {rid} is invalid after verification: "
                                f"{[f'{i.code} {i.path}' for i in errors][:5]}")
        out.append(new)
        after.append(new_status)
    known = {get_path(r, "common.record_id", None) for r in records}
    conflicts = [c for c in verdicts_doc.get("conflicts") or []
                 if isinstance(c, dict) and len(c.get("record_ids") or []) >= 2 and set(c["record_ids"]) <= known]
    report = {
        "verification_format": VERIFY_FORMAT, "run_id": run_id, "created_at": now, "contract": rc.identity(),
        "verifier": {k: verifier[k] for k in ("method", "model", "notes") if verifier.get(k)} | {"method": "model"},
        "independent_of_extractor": None if not extraction_model else not same_model,
        "counts": {"records": len(records), "tasks": len(tasks), "by_kind": _count(t["kind"] for t in tasks),
                   "verdicts": len(given), "by_verdict": _count(v["verdict"] for v in given.values()),
                   "review_status_before": _count(before), "review_status_after": _count(after), **outcome},
        "findings": findings,
        "conflict_candidates": conflicts,
        "omission_candidates": [o for o in verdicts_doc.get("omissions") or [] if isinstance(o, dict)],
        "unknown_task_ids": unknown,
    }
    return out, report


def apply_file(path: Path | str, verdicts: Path | str, out_dir: Path | str, rc, run_id: str | None = None,
               manifest: Path | str | None = None) -> dict:
    """Write <stem>.verified.jsonl and <stem>.verification.json."""
    path, verdicts, out_dir = Path(path), Path(verdicts), Path(out_dir)
    records = _read(path)
    doc = json.loads(verdicts.read_text(encoding="utf-8"))
    digest = sha256_file(path)
    if doc.get("input_sha256") and doc["input_sha256"] != digest:
        raise ContractError(f"{verdicts.name} was written for another version of {path.name} "
                            "(input_sha256 differs); build the tasks again")
    model = None
    if manifest:
        model = ((json.loads(Path(manifest).read_text(encoding="utf-8")).get("backend")) or {}).get("model")
    run_id = run_id or "ver_{}_{}".format(utc_now().strftime("%Y%m%dT%H%M%SZ"),
                                          hashlib.sha256((digest + sha256_file(verdicts)).encode()).hexdigest()[:8])
    out, report = apply_verdicts(records, doc, rc, run_id, model)
    stem = _stem(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{stem}.verified.jsonl"
    target.write_text(dumps_jsonl(out), encoding="utf-8")
    report["input"] = {"file": path.name, "sha256": digest, "verdicts_file": verdicts.name,
                       "verdicts_sha256": sha256_file(verdicts)}
    report["output"] = {"file": target.name, "sha256": sha256_file(target)}
    (out_dir / f"{stem}.verification.json").write_text(dumps_json(report), encoding="utf-8")
    return report


def _read(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _stem(path: Path) -> str:
    return path.name[:-6] if path.name.endswith(".jsonl") else path.stem


def _count(values) -> dict:
    out: dict = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))
