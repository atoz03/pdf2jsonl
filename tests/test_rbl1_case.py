"""RBL1 case: exact primer sequences, context, missing reasons, aliases and field evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from breeding_contract.api import resolve_schema
from breeding_contract.rbl1_case import build_case


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_csv_only_case_builds_valid_records_and_tables(root, tmp_path):
    report = build_case(None, root / "examples/rbl1/primers.csv", tmp_path)
    assert report["counts"] == {"records": 10, "assets": 1, "sequences": 6, "associations": 3,
                                "field_evidence": 28, "triples": 18, "aliases": 2}
    assert all(value is True for key, value in report["checks"].items()
               if key not in {"pdf_hash_expected", "pdf_quotes_verified"})
    assert report["checks"]["pdf_hash_expected"] is None
    assert report["checks"]["pdf_quotes_verified"] is None
    records = rows(tmp_path / "records.jsonl")
    assert len(records) == 10
    sequence = [r for r in records if r["common"]["record_kind"] == "sequence"]
    assert len(sequence) == 6
    by_name = {r["common"]["primer_name"]: r for r in sequence}
    assert by_name["CAPS-RBL1-F"]["common"]["primer_sequence"] == "AAAAGGCGAGACAACCATAA"
    assert by_name["CAPS-RBL1-R"]["common"]["primer_sequence"] == "CACAACCAGCACCATCACTA"
    assert by_name["CoRBL1-F"]["common"]["primer_sequence"] == "TACGAATTCGAGCTCGGTACCTCCACCTTGTCACATCGG"
    assert by_name["CoRBL1-R"]["common"]["primer_sequence"] == "CAGGTCGACTCTAGAGGATCCATGGTTTGGAAAGGGACG"
    assert by_name["qRT-RBL1-F"]["common"]["primer_sequence"] == "ATGGGCCGTTTCCAATGGTT"
    assert by_name["qRT-RBL1-R"]["common"]["primer_sequence"] == "CTTCCTTCCAAGGGAACCCC"
    assert by_name["CAPS-RBL1-F"]["common"]["primer_source_locator"] == "Sheet1!A4:B4"
    assert by_name["CoRBL1-F"]["transform"]["entity_alias_status"] == "candidate"

    assoc = [r for r in records if r["common"]["record_kind"] == "association"]
    assert {a["common"]["association_kind"] for a in assoc} == {
        "linkage_mapping", "functional_complementation", "genome_editing"}
    original = next(a for a in assoc if "29 bp" in a["common"]["alternate_allele"])
    edited = next(a for a in assoc if "RBL1Δ12" in a["common"]["alternate_allele"])
    assert original["common"]["locus_id"] != edited["common"]["locus_id"]
    assert all("population_size" not in a["common"] for a in assoc)
    assert all(a["common"]["missing_fields"] for a in assoc)
    assert all(a["common"]["field_evidence"] for a in assoc)

    # Every record is valid under the released 4.0.0 association profile.
    validator = resolve_schema("4.0.0").validator("association_extraction")
    assert all(validator.validate(r).valid for r in records)
    bad = json.loads(json.dumps(assoc[0]))
    bad["common"].pop("study_id")
    bad_codes = {i.code for i in validator.validate(bad).errors}
    assert "RULE_R041" in bad_codes
    bad_seq = json.loads(json.dumps(sequence[0]))
    bad_seq["common"].pop("primer_sequence")
    assert "RULE_R043" in {i.code for i in validator.validate(bad_seq).errors}
    for name in ("associations.csv", "populations.csv", "materials.csv", "loci.csv", "sequences.csv",
                 "field_evidence.csv", "aliases.csv", "triples.jsonl", "source_manifest.json", "rbl1_case.json"):
        assert (tmp_path / name).is_file(), name


def test_triples_keep_the_association_context(tmp_path, root):
    build_case(None, root / "examples/rbl1/primers.csv", tmp_path)
    triples = rows(tmp_path / "triples.jsonl")
    linked = [t for t in triples if t["predicate"] == "studied_in_population"]
    assert linked and all(t["association_id"] and t["population_id"] and t["environment_id"] for t in linked)
    assert all(t["evidence_ids"] and all(e.startswith("ev_") for e in t["evidence_ids"]) for t in linked)


def test_xlsx_primer_table_reads_the_cell_locator(tmp_path):
    from openpyxl import Workbook

    from breeding_contract.rbl1_case import EXPECTED_PRIMERS

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "Supplementary Table 2"
    ws["A3"] = "Primer name"
    ws["B3"] = "Sequence (5'–3')"
    for row_no, (name, seq, _loc) in enumerate([
        ("CAPS-RBL1-F", "AAAAGGCGAGACAACCATAA", "Sheet1!A4:B4"),
        ("CAPS-RBL1-R", "CACAACCAGCACCATCACTA", "Sheet1!A5:B5"),
        ("CoRBL1-F", "TACGAATTCGAGCTCGGTACCTCCACCTTGTCACATCGG", "Sheet1!A6:B6"),
        ("CoRBL1-R", "CAGGTCGACTCTAGAGGATCCATGGTTTGGAAAGGGACG", "Sheet1!A7:B7"),
    ], start=4):
        ws.cell(row=row_no, column=1, value=name)
        ws.cell(row=row_no, column=2, value=seq)
    # The qRT rows are physically far apart in the original sheet; reproduce their locators.
    ws["A47"], ws["B47"] = "qRT-RBL1-F", "ATGGGCCGTTTCCAATGGTT"
    ws["A48"], ws["B48"] = "qRT-RBL1-R", "CTTCCTTCCAAGGGAACCCC"
    xlsx = tmp_path / "primers.xlsx"
    wb.save(xlsx)

    report = build_case(None, xlsx, tmp_path / "case")
    assert report["checks"]["sequences_expected"] is True
    assert report["checks"]["sequence_locators_exact"] is True
    seq = [r for r in rows(tmp_path / "case/records.jsonl") if r["common"]["record_kind"] == "sequence"]
    assert {r["common"]["primer_source_locator"] for r in seq} == {v[1] for v in EXPECTED_PRIMERS.values()}


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "qt2321j386.pdf").is_file(),
                    reason="real RBL1 PDF is not committed to the repository")
def test_real_pdf_hash_is_the_expected_one(root, tmp_path):
    report = build_case(root / "qt2321j386.pdf", root / "examples/rbl1/primers.csv", tmp_path)
    assert report["checks"]["pdf_hash_expected"] is True
    assert report["checks"]["pdf_quotes_verified"] is True
    assert report["paper"]["pdf_sha256"] == "323646482dd6a7536dbdcf8a23a3f61cbddd964c3bb15a65de90a4443aac3812"
