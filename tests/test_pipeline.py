"""pdf2jsonl end to end: evidence verification, repairs, outputs, agent mode and version pinning."""
from __future__ import annotations

import json
import shutil

import pytest

from breeding_contract import validate_record
from breeding_contract.runtime_schemas import runtime_errors
from pdf2jsonl_skill.pipeline import PipelineError, RunOptions, finalize, prepare, run

from conftest import EXAMPLE_CANDIDATES, EXAMPLE_PDF, read_jsonl, run_skill


@pytest.fixture()
def result(tmp_path, epoch):
    opts = RunOptions(backend="candidates", candidates_file=str(EXAMPLE_CANDIDATES), out_dir=str(tmp_path),
                      run_id="run_test", bundle=True)
    return run(EXAMPLE_PDF, opts)


def test_outputs_exist_and_match_runtime_schemas(result):
    out = result.outputs
    assert set(out) == {"records", "errors", "validation", "manifest", "bundle"}
    assert not runtime_errors("manifest", json.loads(out["manifest"].read_text()))
    assert not runtime_errors("validation_report", json.loads(out["validation"].read_text()))
    assert not runtime_errors("document_bundle", json.loads(out["bundle"].read_text()))
    for e in read_jsonl(out["errors"]):
        assert not runtime_errors("error_record", e)


def test_every_record_is_valid_atomic_and_carries_provenance(result):
    recs = read_jsonl(result.outputs["records"])
    manifest = json.loads(result.outputs["manifest"].read_text())
    version = manifest["contract"]["schema_version"]
    assert len({r["common"]["record_id"] for r in recs}) == len(recs)
    for r in recs:
        c = r["common"]
        assert c["schema_version"] == version and c["schema_name"] == manifest["contract"]["schema_name"]
        assert validate_record(r).valid
        if c["record_kind"] != "asset_manifest":
            assert isinstance(c["source_page"], int) and c["source_quote"]
            assert c["source_locator"].startswith(f"page={c['source_page']}")
        # omit-missing: no null / empty values anywhere
        for group in r.values():
            assert all(v not in (None, "", [], {}) for v in group.values())


def test_fabricated_quote_is_rejected_not_written(result):
    errors = read_jsonl(result.outputs["errors"])
    assert [(e["stage"], e["code"], e["candidate_index"]) for e in errors] == \
        [("evidence", "EVIDENCE_QUOTE_NOT_FOUND", 8)]
    written = " ".join(json.dumps(r, ensure_ascii=False) for r in read_jsonl(result.outputs["records"]))
    assert "gibberellin oxidase" not in written


def test_structural_repairs_are_logged(result):
    report = json.loads(result.outputs["validation"].read_text())
    actions = {(r["where"], r["action"]) for r in report["repairs"]}
    assert ("candidates[9]", "normalized_record_kind") in actions
    assert ("candidates[9]", "dropped_empty_value") in actions
    assert ("candidates[9]", "dropped_field") in actions
    assert ("candidates[0]", "coerced_type") in actions
    assert report["counts"]["records"] == result.counts["records"]


def test_raw_and_normalized_values_stay_separate(result):
    report = json.loads(result.outputs["validation"].read_text())
    norm = [n for r in report["records"] for n in (r.get("notes") or {}).get("normalization", [])]
    assert norm and all("raw_value" in n and "result" in n for n in norm)


def test_page_correction_forces_review(result):
    recs = read_jsonl(result.outputs["records"])
    report = json.loads(result.outputs["validation"].read_text())
    corrected = {r["record_id"] for r in report["records"]
                 if any(w["code"] == "EVIDENCE_PAGE_CORRECTED" for w in r["warnings"])}
    assert corrected
    for r in recs:
        if r["common"]["record_id"] in corrected:
            assert r["common"]["review_status"] == "pending_review"


def test_rerun_is_deterministic(tmp_path, epoch):
    def once(d):
        opts = RunOptions(backend="candidates", candidates_file=str(EXAMPLE_CANDIDATES), out_dir=str(d),
                          run_id="run_same")
        return run(EXAMPLE_PDF, opts).outputs
    a, b = once(tmp_path / "a"), once(tmp_path / "b")
    for k in ("records", "errors", "validation"):
        assert a[k].read_bytes() == b[k].read_bytes(), k


def test_explicit_older_version(tmp_path, epoch):
    opts = RunOptions(schema_version="3.0.0", backend="mock", out_dir=str(tmp_path), run_id="run_300")
    res = run(EXAMPLE_PDF, opts)
    assert res.manifest["contract"]["schema_version"] == "3.0.0"
    for r in res.records:
        assert r["common"]["schema_version"] == "3.0.0"
        assert "schema_name" not in r["common"]  # the field does not exist in 3.0.0


def test_mock_backend_is_grounded(tmp_path, epoch):
    res = run(EXAMPLE_PDF, RunOptions(backend="mock", out_dir=str(tmp_path), run_id="run_mock"))
    assert res.counts["records"] >= 2 and res.counts["rejected"] == 0
    assert all(r["common"]["crop_name"] == "rice" for r in res.records)


def test_unreleased_requires_opt_in(tmp_path):
    with pytest.raises(PipelineError):
        run(EXAMPLE_PDF, RunOptions(schema_version="9.9.9", backend="mock", out_dir=str(tmp_path)))


def test_agent_mode_prepare_then_finalize(tmp_path):
    pdf = tmp_path / EXAMPLE_PDF.name
    shutil.copy(EXAMPLE_PDF, pdf)
    first = run_skill(EXAMPLE_PDF.parents[2], str(pdf),
                      "--out-dir", str(tmp_path / "out"))
    assert first.returncode == 3, first.stderr
    work = tmp_path / "out" / "synthetic_rice_qtl.work"
    for name in ("brief.md", "pages.txt", "candidate.schema.json", "candidates.template.json", "request.json"):
        assert (work / name).is_file(), name
    brief = (work / "brief.md").read_text()
    assert "{{" not in brief and "common.source_quote" in brief  # rendered from the resolved profile
    shutil.copy(EXAMPLE_CANDIDATES, work / "candidates.json")
    second = run_skill(EXAMPLE_PDF.parents[2], str(pdf), "--out-dir", str(tmp_path / "out"), "--fail-on-reject")
    assert second.returncode == 2, second.stderr  # finalized, one candidate rejected
    assert (tmp_path / "out/synthetic_rice_qtl.jsonl").is_file()


def test_finalize_refuses_a_different_version(tmp_path, epoch):
    work = prepare(EXAMPLE_PDF, RunOptions(schema_version="3.0.0", out_dir=str(tmp_path)), tmp_path / "w")
    assert json.loads((work / "request.json").read_text())["contract"]["schema_version"] == "3.0.0"
    shutil.copy(EXAMPLE_CANDIDATES, work / "candidates.json")
    with pytest.raises(PipelineError):
        finalize(work, RunOptions(out_dir=str(tmp_path)), requested_version="3.1.0")
    res = finalize(work, RunOptions(out_dir=str(tmp_path)), requested_version="3.0.0")
    assert res.manifest["contract"]["schema_version"] == "3.0.0"


def test_finalize_detects_changed_input(tmp_path, epoch):
    pdf = tmp_path / "paper.pdf"
    shutil.copy(EXAMPLE_PDF, pdf)
    work = prepare(pdf, RunOptions(out_dir=str(tmp_path)), tmp_path / "w")
    shutil.copy(EXAMPLE_CANDIDATES, work / "candidates.json")
    pdf.write_bytes(pdf.read_bytes() + b"\n%tampered\n")
    with pytest.raises(PipelineError, match="changed"):
        finalize(work)


def test_cli_validate_and_bundle(tmp_path, result, root):
    v = run_skill(root, "validate", str(result.outputs["records"]))
    assert v.returncode == 0 and "0 errors" in v.stdout
    b = run_skill(root, "bundle", str(result.outputs["records"]), "--legacy-v1", "-o", str(tmp_path / "l.json"))
    assert b.returncode == 0, b.stderr
    doc = json.loads((tmp_path / "l.json").read_text())["documents"][0]
    # the synthetic paper states no document type: the lossy projection reports it instead of inventing one
    assert doc["legacy_schema_errors"] == ["record_info: 'doc_type' is a required property"]
    assert any(s.startswith("record_info.doc_type") for s in doc["skipped"])
