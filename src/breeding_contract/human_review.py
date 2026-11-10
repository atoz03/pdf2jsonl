"""Human / expert review: apply reviewer decisions to the review fields.

The extraction pipeline and the independent model verifier never write ``expert_approved`` or ``rejected``.
This module is the one place that does, and it only moves the review fields:

* ``common.review_status`` -> ``expert_approved`` / ``rejected`` / ``pending_review`` (returned for evidence)
* ``common.review_note`` -> the reviewer's note

Content, evidence and quality codes are kept as they are: an expert can approve a record that still carries a
warning, and the warning remains visible.  A rejection or a return needs a note; an approval does not.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from .util import ContractError, dumps_jsonl, get_path, sha256_file, utc_now

REVIEW_FORMAT = 1
DECISION_STATUSES = ("expert_approved", "rejected", "pending_review")
NOTE_REQUIRED = ("rejected", "pending_review")


def _read_records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def apply_decisions(records: list[dict], doc: dict, rc, *, input_name: str = "", input_sha256: str = "") -> tuple[list[dict], dict]:
    """Return (copied records with review fields moved, report)."""
    if doc.get("review_format") != REVIEW_FORMAT:
        raise ContractError(f"review_format must be {REVIEW_FORMAT}")
    reviewer = doc.get("reviewer") or {}
    if not isinstance(reviewer, dict) or not str(reviewer.get("name") or "").strip():
        raise ContractError("review needs reviewer.name (the person making the decision)")
    decisions = doc.get("decisions") or []
    if not isinstance(decisions, list) or not decisions:
        raise ContractError("review needs at least one decision")
    if doc.get("input_sha256") and input_sha256 and doc["input_sha256"] != input_sha256:
        raise ContractError("the decision file was written for another version of the records (input_sha256 differs)")

    by_id = {str(get_path(r, "common.record_id", "")): r for r in records}
    seen: set[str] = set()
    unknown: list[dict] = []
    invalid: list[dict] = []
    applied: list[dict] = []
    before = Counter(get_path(r, "common.review_status", "unknown") for r in records)
    after = Counter()
    out: list[dict] = []
    decision_by_id: dict[str, dict] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ContractError("every decision must be an object")
        rid = str(decision.get("record_id") or "")
        status = decision.get("status")
        note = str(decision.get("note") or "").strip()
        if not rid:
            raise ContractError("every decision needs record_id")
        if status not in DECISION_STATUSES:
            raise ContractError(f"decision status must be one of {', '.join(DECISION_STATUSES)}: {status!r}")
        if status in NOTE_REQUIRED and not note:
            raise ContractError(f"{status} needs a review note for {rid}")
        if rid in seen:
            raise ContractError(f"duplicate decision for {rid}")
        seen.add(rid)
        if rid not in by_id:
            unknown.append({"record_id": rid, "status": status})
            continue
        decision_by_id[rid] = {"record_id": rid, "status": status, "note": note,
                               "previous_status": get_path(by_id[rid], "common.review_status", None)}
    for record in records:
        rid = str(get_path(record, "common.record_id", ""))
        decision = decision_by_id.get(rid)
        if not decision:
            out.append(record)
            after[get_path(record, "common.review_status", "unknown")] += 1
            continue
        new = copy.deepcopy(record)
        common = new.setdefault("common", {})
        decided_at = doc.get("created_at") or utc_now().isoformat().replace("+00:00", "Z")
        common["review_status"] = decision["status"]
        common["record_version"] = int(common.get("record_version") or 1) + 1
        common["record_updated_at"] = decided_at
        if decision["note"]:
            common["review_note"] = decision["note"]
        else:
            common.pop("review_note", None)
        result = rc.validator(None).validate(new)
        if not result.valid:
            invalid.append({"record_id": rid, "errors": [i.to_dict() for i in result.errors]})
            out.append(record)
            after[get_path(record, "common.review_status", "unknown")] += 1
            continue
        decision["decided_at"] = decided_at
        decision["reviewer"] = reviewer.get("name")
        applied.append(decision)
        out.append(new)
        after[decision["status"]] += 1
    report = {
        "review_format": REVIEW_FORMAT,
        "reviewer": reviewer,
        "created_at": doc.get("created_at") or utc_now().isoformat().replace("+00:00", "Z"),
        "input": {"file": input_name, "sha256": input_sha256},
        "counts": {"records": len(records), "decisions": len(decisions), "applied": len(applied),
                   "unknown": len(unknown), "invalid": len(invalid),
                   "before": dict(before), "after": dict(after)},
        "unknown": unknown,
        "invalid": invalid,
        "applied": applied,
        "output": {"file": "", "sha256": ""},
    }
    return out, report


def apply_file(path, decisions, out_dir, rc) -> dict:
    path, decisions, out_dir = Path(path), Path(decisions), Path(out_dir)
    records = _read_records(path)
    doc = json.loads(decisions.read_text(encoding="utf-8"))
    digest = sha256_file(path)
    out, report = apply_decisions(records, doc, rc, input_name=path.name, input_sha256=digest)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.name[:-6] if path.name.endswith(".jsonl") else path.stem
    target = out_dir / f"{stem}.reviewed.jsonl"
    target.write_text(dumps_jsonl(out), encoding="utf-8")
    report["output"] = {"file": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (out_dir / f"{stem}.review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
