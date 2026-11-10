"""Human review: only the review fields move, and an expert approval is never produced by a model."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from breeding_contract.api import resolve_schema
from breeding_contract.human_review import apply_decisions
from breeding_contract.util import ContractError


def example_records(root: Path) -> list[dict]:
    return [json.loads(line) for line in (root / "examples/output/synthetic_rice_qtl.jsonl")
            .read_text(encoding="utf-8").splitlines() if line.strip()]


def decisions(status="expert_approved", note="checked"):
    return {"review_format": 1, "reviewer": {"name": "Reviewer A", "role": "breeder"},
            "created_at": "2026-11-09T00:00:00Z",
            "decisions": [{"record_id": "rec_f14cf35540cd343ba197afdbb0d1be2b", "status": status, "note": note}]}


def test_approval_moves_the_review_status_and_keeps_the_record_content(root):
    records = example_records(root)
    rc = resolve_schema("3.8.0", root)
    out, report = apply_decisions(records, decisions(), rc, input_name="paper.jsonl", input_sha256="a" * 64)
    changed = next(r for r in out if r["common"]["record_id"] == "rec_f14cf35540cd343ba197afdbb0d1be2b")
    assert changed["common"]["review_status"] == "expert_approved"
    assert changed["common"]["review_note"] == "checked"
    assert report["counts"]["applied"] == 1
    assert report["counts"]["records"] == len(records)
    # no other record changed
    before = next(r for r in records if r["common"]["record_id"] == changed["common"]["record_id"])
    assert changed["agent"] == before["agent"]
    assert changed["common"]["source_quote"] == before["common"]["source_quote"]


def test_rejection_needs_a_note(root):
    records = example_records(root)
    rc = resolve_schema("3.8.0", root)
    doc = decisions("rejected", note="")
    with pytest.raises(ContractError):
        apply_decisions(records, doc, rc)


def test_reviewer_is_required(root):
    records = example_records(root)
    rc = resolve_schema("3.8.0", root)
    doc = decisions()
    doc["reviewer"] = {"name": ""}
    with pytest.raises(ContractError):
        apply_decisions(records, doc, rc)


def test_unknown_ids_are_reported_not_silently_dropped(root):
    records = example_records(root)
    rc = resolve_schema("3.8.0", root)
    doc = decisions()
    doc["decisions"][0]["record_id"] = "rec_missing"
    out, report = apply_decisions(records, doc, rc)
    assert report["counts"]["unknown"] == 1
    assert report["counts"]["applied"] == 0
    assert out == records


def test_duplicate_decisions_are_refused(root):
    records = example_records(root)
    rc = resolve_schema("3.8.0", root)
    doc = decisions()
    doc["decisions"].append(dict(doc["decisions"][0]))
    with pytest.raises(ContractError):
        apply_decisions(records, doc, rc)


def test_wrong_input_hash_is_refused(root):
    records = example_records(root)
    rc = resolve_schema("3.8.0", root)
    doc = decisions()
    doc["input_sha256"] = "a" * 64
    with pytest.raises(ContractError):
        apply_decisions(records, doc, rc, input_sha256="b" * 64)
