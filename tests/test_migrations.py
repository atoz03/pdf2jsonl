"""Legacy v1 and omics v2 migrations: nothing inferred, nothing silently dropped, nothing un-evidenced."""
from __future__ import annotations

import json

import pytest

from breeding_contract import resolve_schema, validate_record
from breeding_contract.legacy import _leaves, _norm, migrate_legacy_file
from breeding_contract.mappings import TRANSFER_STATUSES, coverage_summary, match_entry
from breeding_contract.omics import migrate_omics_file
from breeding_contract.runtime_schemas import runtime_errors
from breeding_contract.util import load_json, load_yaml

from conftest import LEGACY_EXAMPLE, LEGACY_PAGE_OFFSET, read_jsonl


@pytest.fixture(scope="module")
def legacy(tmp_path_factory):
    out = tmp_path_factory.mktemp("legacy")
    migrate_legacy_file(LEGACY_EXAMPLE, out, page_offset=LEGACY_PAGE_OFFSET)
    stem = out / "breeding_jsonl_example"
    return {"records": read_jsonl(out / "breeding_jsonl_example.migrated.jsonl"),
            "errors": read_jsonl(out / "breeding_jsonl_example.migrated.errors.jsonl"),
            "residue": load_json(stem.with_name(stem.name + ".residue.json")),
            "report": load_json(stem.with_name(stem.name + ".migration.json"))}


@pytest.fixture(scope="module")
def source_doc():
    return json.loads(LEGACY_EXAMPLE.read_text(encoding="utf-8").splitlines()[0])


def test_legacy_records_valid_and_flagged_for_review(legacy):
    assert legacy["records"]
    for r in legacy["records"]:
        assert validate_record(r).valid
        c = r["common"]
        assert c["review_status"] == "pending_review"
        assert "LEGACY_MIGRATED" in c["qc_failure_codes"]
        assert isinstance(c["source_page"], int) and 1 <= c["source_page"] <= 15  # physical pages
        assert c["source_quote"]
    assert not runtime_errors("migration_report", legacy["report"])
    assert all(not runtime_errors("error_record", e) for e in legacy["errors"])


def test_consumed_leaves_come_from_transfer_entries(root, legacy):
    entries = load_yaml(root / "mappings/legacy_to_current.yaml")["entries"]
    for path in legacy["report"]["consumed_leaf_paths"]:
        e = match_entry(entries, path)
        assert e is not None and e["status"] in TRANSFER_STATUSES | {"control"}, (path, e and e["status"])


def test_every_nonempty_leaf_is_consumed_or_residue(legacy, source_doc):
    consumed = set(legacy["report"]["consumed_leaf_paths"])
    residue = {r["path"] for r in legacy["residue"]["unconsumed"]}
    for path, value in _leaves(source_doc):
        from breeding_contract.legacy import _concrete
        assert _norm(path) in consumed or _concrete(path) in residue, path


def test_inferred_relations_are_never_migrated(legacy, source_doc):
    inferred = {f"relations[{i}]" for i, r in enumerate(source_doc["relations"]) if r.get("is_inferred")}
    assert inferred
    produced = {s["source_path"] for s in legacy["report"]["record_sources"].values()}
    produced |= {e.get("source_path") for e in legacy["errors"]}
    produced |= {c["source"] for c in legacy["residue"]["review_candidates"].values()}
    assert not (produced & inferred)


def test_interpretive_values_become_review_candidates_not_fields(root, legacy):
    rc = resolve_schema("latest", root)
    avail = {f["path"]: f["availability"] for f in rc.fields}
    for r in legacy["records"]:
        for g, fields in r.items():
            for name in fields:
                assert avail[f"{g}.{name}"] != "I" or name == "review_note", f"{g}.{name}"
    cands = legacy["residue"]["review_candidates"]
    assert cands and all(avail.get(p) in ("I", "D", "N") for c in cands.values() for p in c["values"])


def test_gwas_significance_is_not_stored_as_lod(legacy):
    qtl_records = [rid for rid, s in legacy["report"]["record_sources"].items()
                   if s["source_path"] == "breed_entities.qtls[0]"]
    assert qtl_records
    for r in legacy["records"]:
        if r["common"]["record_id"] in qtl_records:
            flat = {f"{g}.{k}" for g, v in r.items() for k in v}
            assert not any("lod" in p for p in flat), flat


def test_no_page_offset_means_no_evidence_records(tmp_path):
    migrate_legacy_file(LEGACY_EXAMPLE, tmp_path)
    assert read_jsonl(tmp_path / "breeding_jsonl_example.migrated.jsonl") == []
    errors = read_jsonl(tmp_path / "breeding_jsonl_example.migrated.errors.jsonl")
    assert errors and all(any(i["rule_id"] == "R001" for i in e["issues"] if "rule_id" in i) for e in errors
                          if e["stage"] == "migration")


def test_legacy_mapping_covers_every_schema_leaf(root):
    mapping = load_yaml(root / "mappings/legacy_to_current.yaml")
    cov = coverage_summary(root, mapping)
    assert "uncovered" not in cov["by_status"] and cov["leaves"] > 700


def test_omics_mapping_covers_every_template_leaf(root):
    mapping = load_yaml(root / "mappings/omics_to_current.yaml")
    cov = coverage_summary(root, mapping)
    assert "uncovered" not in cov["by_status"] and cov["leaves"] == 252


def test_omics_template_of_nulls_produces_nothing(root, tmp_path):
    migrate_omics_file(root / "sources/omics_v2/omics_metadata_template.json", tmp_path, record_kind="analysis_result")
    assert read_jsonl(tmp_path / "omics_metadata_template.migrated.jsonl") == []
    [err] = read_jsonl(tmp_path / "omics_metadata_template.migrated.errors.jsonl")
    assert err["code"] == "RECORD_INVALID"  # required values are absent, and nothing is invented


def test_omics_instance_migrates(root, tmp_path):
    src = root / "examples/migration/omics_v2/synthetic_deg_instance.json"
    migrate_omics_file(src, tmp_path)
    [rec] = read_jsonl(tmp_path / "synthetic_deg_instance.migrated.jsonl")
    assert validate_record(rec).valid
    assert rec["common"]["record_kind"] == "analysis_result"
    assert rec["omics"]["omics_type"] == "transcriptomics" and rec["omics"]["log2_fold_change"] == 2.3
    assert rec["common"]["source_record_id"] == "deg-0001"
    assert rec["common"]["review_status"] == "pending_review"
    assert load_json(tmp_path / "synthetic_deg_instance.residue.json")["unconsumed"] == []


def test_omics_needs_a_record_kind(root, tmp_path):
    inst = load_json(root / "examples/migration/omics_v2/synthetic_deg_instance.json")
    inst["basic_identity"]["record_type"] = "DEG table row"
    p = tmp_path / "x.json"
    p.write_text(json.dumps(inst), encoding="utf-8")
    migrate_omics_file(p, tmp_path / "a")
    assert [e["code"] for e in read_jsonl(tmp_path / "a/x.migrated.errors.jsonl")] == ["RECORD_KIND_UNKNOWN"]
    migrate_omics_file(p, tmp_path / "b", record_kind="analysis_result")
    [rec] = read_jsonl(tmp_path / "b/x.migrated.jsonl")
    residue = load_json(tmp_path / "b/x.residue.json")["unconsumed"]
    assert any(r["path"] == "basic_identity.record_type" for r in residue)
