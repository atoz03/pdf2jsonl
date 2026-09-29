"""Derived views (document_bundle, legacy v1 projection) and reproducibility of the checked-in examples."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from breeding_contract.bundle import bundle_records, legacy_bundle, legacy_projection
from breeding_contract.runtime_schemas import runtime_errors

from conftest import read_jsonl


def test_bundle_groups_records_without_changing_them(root):
    recs = read_jsonl(root / "examples/output/synthetic_rice_qtl.jsonl")
    b = bundle_records(recs)
    assert not runtime_errors("document_bundle", b)
    [doc] = b["documents"]
    assert doc["records"] == recs
    assert doc["counts"]["records"] == len(recs)
    assert doc["document"]["common.source_doi"] == "10.0000/synthetic.2026.001"
    assert "qPH7.1" in doc["entities"]["qtl_names"]
    ids = {r["common"]["record_id"] for r in recs}
    assert {rid for ev in doc["evidence_index"] for rid in ev["record_ids"]} <= ids


def test_bundle_splits_documents_and_rejects_mixed_versions(root):
    import pytest

    from breeding_contract import ContractError
    a = read_jsonl(root / "examples/records/tool_spec.jsonl")
    b = read_jsonl(root / "examples/records/genotype_observation.jsonl")
    assert len(bundle_records(a + b)["documents"]) == 2
    old = json.loads(json.dumps(a[0]))
    old["common"]["schema_version"] = "3.0.0"
    with pytest.raises(ContractError):
        bundle_records(a + [old])


def test_legacy_projection_of_migrated_records_is_schema_valid(root):
    recs = read_jsonl(root / "examples/migration/legacy_v1/breeding_jsonl_example.migrated.jsonl")
    out = legacy_bundle(bundle_records(recs), root)
    [doc] = out["documents"]
    assert doc["valid_against_legacy_schema"], doc["legacy_schema_errors"]
    legacy = doc["legacy_v1"]
    assert all(g["entity_id"].startswith("gene:") for g in legacy["breed_entities"].get("genes", []))
    assert all(c["conclusion_id"].startswith("clu:") for c in legacy["conclusions"])
    # relations without a predicate code are skipped and reported, never given an invented type
    assert all(r["relation_type"] for r in legacy["relations"])
    assert all("predicate_label" in s for s in doc["skipped"] if "relation" in s)


def test_legacy_projection_maps_extraction_methods():
    doc = {"source_id": "x", "document": {"common.source_title": "T"}, "entities": {}, "evidence_index": [],
           "records": [{"common": {"record_id": "r1", "record_kind": "claim", "extraction_method": "model"}},
                       {"common": {"record_id": "r2", "record_kind": "claim", "extraction_method": "rule"}}]}
    legacy, skipped = legacy_projection(doc, created_at="2026-01-01T00:00:00Z")
    assert legacy["provenance"]["extraction"]["method"] == "混合(LLM+规则)"
    doc["records"] = [{"common": {"record_id": "r1", "record_kind": "claim", "extraction_method": "etl"}}]
    legacy, skipped = legacy_projection(doc, created_at="2026-01-01T00:00:00Z")
    assert legacy["provenance"]["extraction"] == {} and any("provenance" in s for s in skipped)


def test_examples_regenerate_identically(root, repo_copy):
    """scripts/make_examples.py is deterministic: regenerated records, errors and reports match the repo."""
    env = {**os.environ, "BDC_PYTHON": sys.executable}
    env.pop("PYTHONPATH", None)
    subprocess.run([sys.executable, str(repo_copy / "scripts/make_examples.py")], check=True, env=env,
                   capture_output=True, cwd=repo_copy)
    skip_suffixes = (".manifest.json",)  # manifests record the local environment
    for p in sorted((root / "examples").rglob("*")):
        if p.is_file() and p.suffix in (".jsonl", ".json") and not p.name.endswith(skip_suffixes):
            q = repo_copy / p.relative_to(root)
            assert q.read_bytes() == p.read_bytes(), p.relative_to(root)
