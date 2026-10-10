"""3.5.0: a paper in several files, and a paper whose supplement is missing (AMB-041)."""
from __future__ import annotations

import json
import shutil

import pytest

from breeding_contract import resolve_schema, validate_record
from breeding_contract.derive import derive_file
from breeding_contract.ids import build_locator, build_span, normalize_text
from breeding_contract.runtime_schemas import runtime_errors
from breeding_contract.util import sha256_file
from pdf2jsonl_skill.completeness import cited_items, source_completeness, unavailable_items
from pdf2jsonl_skill.pdf_parse import parse_document
from pdf2jsonl_skill.pipeline import PipelineError, RunOptions, finalize, prepare, run

from conftest import (EXAMPLE_CANDIDATES, EXAMPLE_PDF, HEAT_CANDIDATES, HEAT_PDF, HEAT_SUPPLEMENT, read_jsonl,
                      records_by_ref, run_skill)

SUPPLEMENT_REFS = {"m_heat", "m_rep", "m_stat", "m_luc", "o_s1"}


def main_only_candidates(tmp_path):
    """What an extractor writes when it is given the main text only."""
    doc = json.loads(HEAT_CANDIDATES.read_text(encoding="utf-8"))
    kept = [c for c in doc["candidates"] if c["ref"] not in SUPPLEMENT_REFS]
    for c in kept:
        c["links"] = {k: [r for r in v if r not in SUPPLEMENT_REFS] for k, v in (c.get("links") or {}).items()}
        c["links"] = {k: v for k, v in c["links"].items() if v}
    path = tmp_path / "main_only.candidates.json"
    path.write_text(json.dumps({**doc, "candidates": kept}, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    out = tmp_path_factory.mktemp("parts_full")
    return run(HEAT_PDF, RunOptions(candidates_file=str(HEAT_CANDIDATES), supplements=[str(HEAT_SUPPLEMENT)],
                                    out_dir=str(out), run_id="run_parts"))


@pytest.fixture(scope="module")
def partial(tmp_path_factory):
    out = tmp_path_factory.mktemp("parts_main")
    return run(HEAT_PDF, RunOptions(candidates_file=str(main_only_candidates(out)), out_dir=str(out),
                                    run_id="run_parts_main"))


# ------------------------------------------------------------------ several files, one source

def test_parts_share_one_source_and_name_their_part(full):
    recs = read_jsonl(full.outputs["records"])
    assert full.counts["rejected"] == 0 and full.counts["pages"] == 4
    assert {r["common"]["source_id"] for r in recs} == {"doi:10.0000/synthetic.2026.002"}
    by_ref = records_by_ref(full, HEAT_CANDIDATES)
    for ref, rec in by_ref.items():
        c = rec["common"]
        assert validate_record(rec).valid
        if ref in SUPPLEMENT_REFS:
            assert c["source_part"] == "supplement"
            assert c["source_locator"].startswith(f"part=supplement;page={c['source_page']}")
            assert c["source_span"].startswith(f"part=supplement;page={c['source_page']};char=")
            assert c["source_file_sha256"] == sha256_file(HEAT_SUPPLEMENT)
        else:
            assert c["source_part"] == "main_text"
            assert c["source_locator"].startswith(f"page={c['source_page']}") and "part=" not in c["source_span"]
            assert c["source_file_sha256"] == sha256_file(HEAT_PDF)


def test_supplement_pages_are_numbered_per_file(full):
    """Page 1 of the supplement is not page 3 of the paper, and its quote is looked up in the supplement."""
    by_ref = records_by_ref(full, HEAT_CANDIDATES)
    assert by_ref["m_heat"]["common"]["source_page"] == 1 and by_ref["bg"]["common"]["source_page"] == 1
    supplement = parse_document(HEAT_SUPPLEMENT)
    span = by_ref["m_heat"]["common"]["source_span"]
    start, end = map(int, span.rsplit("char=", 1)[1].split("-"))
    assert normalize_text(supplement.pages[0].text[start:end]) == \
        normalize_text(by_ref["m_heat"]["common"]["source_quote"])


def test_each_file_gets_an_asset_record(full):
    assets = [r["common"] for r in read_jsonl(full.outputs["records"]) if r["common"]["record_kind"] == "asset_manifest"]
    assert {(a["source_part"], a["asset_sha256"]) for a in assets} == \
        {("main_text", sha256_file(HEAT_PDF)), ("supplement", sha256_file(HEAT_SUPPLEMENT))}
    assert len({a["record_id"] for a in assets}) == 2
    assert full.manifest["input"]["supplements"][0]["part"] == "supplement"
    assert full.manifest["input"]["supplements"][0]["sha256"] == sha256_file(HEAT_SUPPLEMENT)


def test_reports_match_runtime_schemas(full, partial):
    for res in (full, partial):
        assert not runtime_errors("manifest", json.loads(res.outputs["manifest"].read_text()))
        assert not runtime_errors("validation_report", json.loads(res.outputs["validation"].read_text()))


def test_adding_the_supplement_keeps_main_text_record_ids(full, partial):
    """The supplement arrives later: the paper is extracted again and no existing record changes its ID."""
    before = {r["common"]["record_id"]: r for r in read_jsonl(partial.outputs["records"])}
    after = {r["common"]["record_id"]: r for r in read_jsonl(full.outputs["records"])}
    assert set(before) < set(after)
    for rid, rec in before.items():
        assert rec["common"]["source_locator"] == after[rid]["common"]["source_locator"]


def test_locator_and_span_omit_the_main_part():
    assert build_locator(page=3, section="Results") == "page=3;section=Results"
    assert build_locator(page=1, part="supplement") == "part=supplement;page=1"
    assert build_span(2, 5, 9) == "page=2;char=5-9"
    assert build_span(2, 5, 9, part="supplement_2") == "part=supplement_2;page=2;char=5-9"


def test_evidence_in_a_part_that_was_not_given_is_rejected(tmp_path):
    res = run(HEAT_PDF, RunOptions(candidates_file=str(HEAT_CANDIDATES), out_dir=str(tmp_path), run_id="run_nopart"))
    errors = read_jsonl(res.outputs["errors"])
    assert {e["code"] for e in errors} == {"EVIDENCE_PART_UNKNOWN"} and len(errors) == len(SUPPLEMENT_REFS)
    # links to the rejected candidates are dropped and flagged, never guessed
    report = json.loads(res.outputs["validation"].read_text())
    assert any(w["code"].startswith("CANDIDATE_LINK_") for r in report["records"] for w in r["warnings"])


def test_a_file_cannot_be_its_own_supplement(tmp_path):
    with pytest.raises(PipelineError):
        run(HEAT_PDF, RunOptions(candidates_file=str(HEAT_CANDIDATES), supplements=[str(HEAT_PDF)],
                                 out_dir=str(tmp_path)))


def test_older_contracts_are_untouched(tmp_path, epoch):
    """A contract without the part role refuses supplements and writes exactly what it wrote before."""
    with pytest.raises(PipelineError, match="supplement"):
        run(HEAT_PDF, RunOptions(schema_version="3.4.0", candidates_file=str(HEAT_CANDIDATES),
                                 supplements=[str(HEAT_SUPPLEMENT)], out_dir=str(tmp_path)))
    res = run(EXAMPLE_PDF, RunOptions(schema_version="3.4.0", candidates_file=str(EXAMPLE_CANDIDATES),
                                      out_dir=str(tmp_path), run_id="run_340"))
    report = json.loads(res.outputs["validation"].read_text())
    assert "source_parts" not in report and "workflow_structure" not in report
    assert "source_parts" not in res.manifest
    assert all("source_part" not in r["common"] for r in res.records)
    assert not runtime_errors("validation_report", report)


# ------------------------------------------------------------------ incomplete papers

def test_cited_items_are_normalised_and_ranges_expanded():
    assert cited_items("see fig. S1 and Table S2") == ["Fig. S1", "Table S2"]
    assert cited_items("(figs. S1 to S3)") == ["Fig. S1", "Fig. S2", "Fig. S3"]
    assert cited_items("Figures S2A, S4 and Supplementary Table S1") == ["Fig. S2", "Fig. S4", "Table S1"]
    assert cited_items("附图S2与附表 S1") == ["Fig. S2", "Table S1"]
    # a marker or sample name is not a supplementary item, and neither is a figure of the main text
    assert cited_items("marker S7_1203 in Fig. 2 and Table 1") == []


def test_missing_supplement_is_reported(partial):
    report = json.loads(partial.outputs["validation"].read_text())
    parts = report["source_parts"]
    assert parts["complete"] is False and parts["missing"] == ["supplement"]
    assert parts["items_not_found"] == ["Fig. S1", "Fig. S2", "Fig. S3"]
    assert parts["referenced"]["supplement"]["pages"] == [2]
    assert [p["source_part"] for p in parts["provided"]] == ["main_text"]
    assert partial.manifest["source_parts"] == {"missing": ["supplement"], "complete": False}


def test_complete_source_reports_nothing_missing(full):
    parts = json.loads(full.outputs["validation"].read_text())["source_parts"]
    assert parts["complete"] is True and parts["missing"] == [] and parts["items_not_found"] == []
    assert [p["part"] for p in parts["provided"]] == ["main", "supplement"]
    assert full.manifest["source_parts"] == {"missing": [], "complete": True}


def test_records_citing_a_missing_part_go_to_review(partial, tmp_path):
    report = json.loads(partial.outputs["validation"].read_text())
    flagged = {r["record_id"] for r in report["records"]
               if any(w["code"] == "SOURCE_PART_UNAVAILABLE" for w in r["warnings"])}
    by_ref = records_by_ref(partial, main_only_candidates(tmp_path))
    assert flagged == {by_ref[ref]["common"]["record_id"] for ref in ("r_sl14", "r_ko", "r_luc")}
    for ref in ("r_sl14", "r_ko", "r_luc"):
        c = by_ref[ref]["common"]
        assert c["review_status"] == "pending_review" and "SOURCE_PART_UNAVAILABLE" in c["qc_failure_codes"]
    assert by_ref["m_bc"]["common"]["review_status"] == "auto_validated"


def test_with_the_supplement_nothing_is_flagged(full):
    report = json.loads(full.outputs["validation"].read_text())
    assert not any(w["code"] == "SOURCE_PART_UNAVAILABLE" for r in report["records"] for w in r["warnings"])


def test_missing_field_of_such_a_record_names_the_reason(tmp_path):
    """A value that may stand in the part we do not have is not `not_located`."""
    doc = json.loads(HEAT_CANDIDATES.read_text(encoding="utf-8"))
    quote = next(c for c in doc["candidates"] if c["ref"] == "r_sl14")["evidence"]["quote"]
    doc["candidates"] = [{"record_kind": "phenotype_observation", "fields": {"common.germplasm_names": ["SL14"]},
                          "evidence": {"page": 2, "quote": quote}}]
    cand = tmp_path / "c.json"
    cand.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    res = run(HEAT_PDF, RunOptions(candidates_file=str(cand), out_dir=str(tmp_path), run_id="run_reason"))
    rec = next(r for r in res.records if r["common"]["record_kind"] == "phenotype_observation")
    assert rec["common"]["missing_fields"]["common.measurement_name"] == "source_part_unavailable"
    again = run(HEAT_PDF, RunOptions(candidates_file=str(cand), supplements=[str(HEAT_SUPPLEMENT)],
                                     out_dir=str(tmp_path / "full"), run_id="run_reason_full"))
    rec = next(r for r in again.records if r["common"]["record_kind"] == "phenotype_observation")
    assert rec["common"]["missing_fields"]["common.measurement_name"] == "not_located"


def test_supplement_inside_the_same_file_is_not_missing(tmp_path):
    text = ("Results\nLine SL14 showed higher survival (fig. S1). Details are in the supplementary materials.\n\f"
            "Supplementary Materials\nFig. S1 Survival of SL14 and WY after heat treatment.\n")
    one = tmp_path / "one.txt"
    one.write_text(text, encoding="utf-8")
    doc = parse_document(one)
    assert doc.page_count == 2
    parts = source_completeness(doc)
    assert parts["complete"] and parts["referenced"]["supplement"]["items"] == ["Fig. S1"]
    two = tmp_path / "two.txt"
    two.write_text(text.split("\f")[0], encoding="utf-8")
    parts = source_completeness(parse_document(two))
    assert parts["missing"] == ["supplement"] and parts["items_not_found"] == ["Fig. S1"]
    assert unavailable_items("survival (fig. S1)", parts) == ["Fig. S1"]
    assert unavailable_items("survival (Fig. 1)", parts) == []


def test_appendix_reference_is_reported(tmp_path):
    paper = tmp_path / "p.txt"
    paper.write_text("Methods\nPrimer sequences are listed in the Appendix.\n", encoding="utf-8")
    parts = source_completeness(parse_document(paper))
    assert parts["missing"] == ["appendix"] and parts["complete"] is False


# ------------------------------------------------------------------ agent mode and lineage

def test_agent_mode_shows_the_parts_and_pins_them(tmp_path):
    work = prepare(HEAT_PDF, RunOptions(supplements=[str(HEAT_SUPPLEMENT)], out_dir=str(tmp_path)))
    pages = (work / "pages.txt").read_text(encoding="utf-8")
    assert "=== supplement page 1 ===" in pages and "Twelve-day-old seedlings" in pages
    brief = (work / "brief.md").read_text(encoding="utf-8")
    assert "Research workflow" in brief and "`part`" in brief
    for link in ("tests", "addresses", "prerequisite"):
        assert f"`links.{link}`" in brief
    request = json.loads((work / "request.json").read_text())
    assert request["input"]["supplements"][0]["sha256"] == sha256_file(HEAT_SUPPLEMENT)
    schema = json.loads((work / "candidate.schema.json").read_text())
    assert "part" in json.dumps(schema)
    shutil.copy(HEAT_CANDIDATES, work / "candidates.json")
    res = finalize(work)
    assert res.counts["rejected"] == 0 and res.manifest["source_parts"]["complete"]


def test_rerun_with_other_supplements_is_refused(tmp_path):
    pdf = tmp_path / HEAT_PDF.name
    shutil.copy(HEAT_PDF, pdf)
    repo = HEAT_PDF.parents[2]
    first = run_skill(repo, str(pdf), "--out-dir", str(tmp_path / "out"))
    assert first.returncode == 3, first.stderr
    shutil.copy(main_only_candidates(tmp_path), tmp_path / "out" / "synthetic_rice_heat.work" / "candidates.json")
    second = run_skill(repo, str(pdf), "--out-dir", str(tmp_path / "out"), "--supplement", str(HEAT_SUPPLEMENT))
    assert second.returncode != 0 and "supplement" in second.stderr
    third = run_skill(repo, str(pdf), "--out-dir", str(tmp_path / "out"))
    assert third.returncode == 0, third.stderr


def test_derived_views_record_their_lineage(full, tmp_path, root):
    rc = resolve_schema("latest", root)
    report = derive_file(full.outputs["records"], tmp_path, rc)
    assert report["derive_format"] == 3
    lineage = report["lineage"]
    assert lineage["derived_from"]["sha256"] == sha256_file(full.outputs["records"])
    assert lineage["derived_from"]["source_ids"] == ["doi:10.0000/synthetic.2026.002"]
    stem = full.outputs["records"].name[:-6]
    assert f"{stem}.workflow.json" in lineage["outputs"]
    for rel, digest in lineage["outputs"].items():
        assert sha256_file(tmp_path / rel) == digest
    corpus = read_jsonl(tmp_path / f"{stem}.corpus.jsonl")
    ids = {r["common"]["record_id"] for r in read_jsonl(full.outputs["records"])}
    assert all(set(c["chunk_support_ids"]) <= ids for c in corpus)
