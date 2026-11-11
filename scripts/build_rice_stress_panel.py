#!/usr/bin/env python3
"""Build a real-paper rice stress panel from a curated CSV.

The CSV records one verified association per paper (gene/QTL -> trait, with the page-1 abstract quote and the
paper metadata).  The PDFs stay outside the repository; when ``--pdf-dir`` is given the file SHA256 and page
count are recorded, otherwise the record is marked with ``source_file_status=not_available``.  This is a
curated demo panel, not a claim of exhaustive extraction.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from breeding_contract.api import resolve_schema  # noqa: E402
from breeding_contract.association_aggregate import aggregate_associations  # noqa: E402
from breeding_contract.util import sha256_file  # noqa: E402

SCHEMA = "4.0.0"
PROFILE = "association_extraction"
RUN_ID = "run_rice_stress_panel"


def _stable(prefix: str, *parts) -> str:
    return prefix + hashlib.sha256("\x1f".join(map(str, parts)).encode()).hexdigest()[:32]


def _find_pdf(pdf_dir: Path, pattern: str) -> Path | None:
    matches = sorted(pdf_dir.glob(pattern))
    return matches[0] if matches else None


def build(panel_csv: Path, pdf_dir: Path | None, out_dir: Path, case_dir: Path | None = None) -> dict:
    panel_csv = Path(panel_csv)
    rows = list(csv.DictReader(panel_csv.open(encoding="utf-8-sig", newline="")))
    panel_records = []
    sources = []
    for row in rows:
        pdf = _find_pdf(Path(pdf_dir), row["file_glob"]) if pdf_dir else None
        pdf_sha = sha256_file(pdf) if pdf and pdf.is_file() else None
        doi = (row.get("doi") or "").strip()
        source_id = ("doi:" + doi) if doi else ("local:rice-stress/" + row["slug"])
        title = row["title"].strip()
        page = int(row.get("page") or 1)
        quote = row["quote"].strip()
        file_url = ("https://doi.org/" + doi) if doi else ("local:" + row["slug"])
        common = {
            "schema_name": "breeding-literature-record", "schema_version": SCHEMA,
            "record_kind": "association", "record_grain": "association_unit",
            "source_id": source_id, "source_type": "paper", "source_title": title,
            "source_year": int(row["year"]), "source_language": "en", "crop_name": "rice",
            "source_locator": f"page={page};section=Abstract", "source_page": page, "source_section": "Abstract",
            "source_quote": quote, "source_part": "main_text",
            "source_file_role": "main_text",
            "source_file_status": "parsed" if pdf_sha else "not_available",
            "source_file_url": file_url,
            "review_status": "auto_validated", "record_version": 1,
            "extraction_method": "rule", "extraction_profile": PROFILE,
            "qc_rule_set_version": f"breeding-literature-record@{SCHEMA}+rice-stress-panel@1.0.0",
            "study_id": "urn:rice:study:" + row["slug"],
            "population_id": "urn:rice:population:" + row["slug"],
            "population_name": row["population_name"],
            "population_type": row["population_type"],
            "material_id": "urn:rice:material:" + row["slug"],
            "germplasm_names": [x.strip() for x in row["material_names"].split("|") if x.strip()],
            "environment_id": row["environment_id"],
            "trait_id": row["trait_id"],
            "trait_names": [x.strip() for x in row["trait_names"].split("|") if x.strip()],
            "association_kind": row["association_kind"],
            "locus_id": "urn:rice:locus:" + row["slug"],
            "locus_type": row["locus_type"],
            "field_evidence": [
                {"field": "common.locus_id", "file_id": _stable("rec_", "source", source_id),
                 "locator": f"page={page};section=Abstract", "quote": row["locus"], "page": page},
                {"field": "common.trait_names", "file_id": _stable("rec_", "source", source_id),
                 "locator": f"page={page};section=Abstract", "quote": quote, "page": page},
                {"field": "common.population_name", "file_id": _stable("rec_", "source", source_id),
                 "locator": f"page={page};section=Abstract", "quote": row["population_name"], "page": page},
            ],
        }
        if doi:
            common["source_doi"] = doi
        if pdf_sha:
            common["source_file_sha256"] = pdf_sha
        else:
            common["missing_fields"] = {"common.source_file_sha256": "source_unavailable"}
        rec = {"common": common, "agent": {"finding_text": quote, "effect_direction": row["direction"]}}
        rec["common"]["record_id"] = _stable("rec_", "rice-stress", row["slug"], source_id)
        panel_records.append(rec)
        sources.append({"paper_id": source_id, "title": title, "year": int(row["year"]),
                        "doi": doi, "pdf": pdf.name if pdf else "", "sha256": pdf_sha,
                        "status": "parsed" if pdf_sha else "not_available"})

    rc = resolve_schema(SCHEMA)
    validator = rc.validator(PROFILE)
    errors = []
    for rec in panel_records:
        result = validator.validate(rec)
        if not result.valid:
            errors.append({"record_id": rec["common"]["record_id"],
                           "errors": [i.to_dict() for i in result.errors]})
    if errors:
        raise ValueError("panel records do not validate: " + json.dumps(errors, ensure_ascii=False)[:2000])

    combined = list(panel_records)
    if case_dir:
        case_records = [json.loads(line) for line in
                        (Path(case_dir) / "records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        combined = [r for r in case_records if (r.get("common") or {}).get("record_kind") == "association"] + combined
    aggregate = aggregate_associations(combined)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "panel_records.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in panel_records) + "\n", encoding="utf-8")
    (out_dir / "records.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in combined) + "\n", encoding="utf-8")
    (out_dir / "association_aggregate.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "panel_sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    (out_dir / "panel_summary.json").write_text(json.dumps({
        "panel": "rice-stress-real-papers", "papers": len(panel_records),
        "with_pdf": sum(1 for s in sources if s["sha256"]), "aggregate": aggregate["counts"],
        "note": "Curated page-1 associations for a demo panel; not exhaustive.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return aggregate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel-csv", default="examples/rice_stress_panel/panel.csv")
    ap.add_argument("--pdf-dir", default=os.environ.get("RICE_PDF_DIR"),
                    help="directory containing the 13 paper PDFs (or set RICE_PDF_DIR); omit for a hash-less build")
    ap.add_argument("--case-dir", default="out/rbl1_case_final")
    ap.add_argument("--out", default="out/rice_stress_panel")
    args = ap.parse_args(argv)
    agg = build(Path(args.panel_csv), Path(args.pdf_dir) if args.pdf_dir else None,
                Path(args.out), Path(args.case_dir) if args.case_dir else None)
    print(json.dumps(agg["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
