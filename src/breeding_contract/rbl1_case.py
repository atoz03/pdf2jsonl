"""RBL1 case: a real paper + primer table as a reproducible association package.

This is the manual-attachment phase of the 4.0.0 association work.  It does not fetch from the web and it does
not pretend the PDF is redistributable: the caller supplies the paper and the primer table, and gets

* source-file records (role / status / URL / SHA256),
* six ``sequence`` records with the cell locator and 5'->3' text from the table,
* three ``association`` records with study/population/trait/locus context and field-level evidence,
* the five downstream tables plus triples and an RBL1 validation report.

The records validate against contract 4.0.0 and the ``association_extraction`` profile.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .api import resolve_schema
from .util import get_path, sha256_file

CASE_VERSION = "1.0.0"
SCHEMA_VERSION = "4.0.0"
PROFILE = "association_extraction"
DOI = "10.1038/s41586-023-06205-2"
TITLE = "Genome editing of a rice CDP-DAG synthase confers multipathogen resistance"
PAPER_URL = "https://escholarship.org/content/qt2321j386/qt2321j386.pdf"
XLSX_URL = ("https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-023-06205-2/"
            "MediaObjects/41586_2023_6205_MOESM4_ESM.xlsx")
EXPECTED_PDF_SHA256 = "323646482dd6a7536dbdcf8a23a3f61cbddd964c3bb15a65de90a4443aac3812"
EXPECTED_PRIMERS = {
    "CAPS-RBL1-F": ("AAAAGGCGAGACAACCATAA", "Sheet1!A4:B4"),
    "CAPS-RBL1-R": ("CACAACCAGCACCATCACTA", "Sheet1!A5:B5"),
    "CoRBL1-F": ("TACGAATTCGAGCTCGGTACCTCCACCTTGTCACATCGG", "Sheet1!A6:B6"),
    "CoRBL1-R": ("CAGGTCGACTCTAGAGGATCCATGGTTTGGAAAGGGACG", "Sheet1!A7:B7"),
    "qRT-RBL1-F": ("ATGGGCCGTTTCCAATGGTT", "Sheet1!A47:B47"),
    "qRT-RBL1-R": ("CTTCCTTCCAAGGGAACCCC", "Sheet1!A48:B48"),
}

ROLE = {
    "CAPS-RBL1-F": ("pcr_forward_primer", "forward", "CAPS marker"),
    "CAPS-RBL1-R": ("pcr_reverse_primer", "reverse", "CAPS marker"),
    "CoRBL1-F": ("pcr_forward_primer", "forward", "complementation construct"),
    "CoRBL1-R": ("pcr_reverse_primer", "reverse", "complementation construct"),
    "qRT-RBL1-F": ("qrt_forward_primer", "forward", "qRT-PCR"),
    "qRT-RBL1-R": ("qrt_reverse_primer", "reverse", "qRT-PCR"),
}

ASSOCIATIONS = (
    {
        "ref": "A_RBL1_01",
        "association_kind": "linkage_mapping",
        "locus_id": "urn:rbl1:gene:RBL1",
        "locus_type": "gene",
        "trait_names": ["lesion mimic", "disease resistance"],
        "trait_id": "urn:rbl1:trait:lesion-mimic",
        "population_id": "urn:rbl1:population:M3-segregants",
        "population_name": "rbl1 M3 segregating population",
        "population_type": "M3",
        "germplasm_names": ["FN398", "KitaakeX"],
        "material_id": "urn:rbl1:material:FN398",
        "environment_id": "urn:rbl1:environment:greenhouse",
        "alternate_allele": "rbl1 (29 bp deletion)",
        "page": 4,
        "section": "Results",
        "quote": ("We then whole-genome-sequenced pooled DNA from three lesioned M3 segregants using Illumina "
                  "and identified a 29-base-pair (bp) deletion in RBL1 (LOC_Os01g55360) (Fig. 1j)."),
        "sequence_names": ["CAPS-RBL1-F", "CAPS-RBL1-R"],
        "validation_status": "candidate",
        "effect_direction": "increase",
        "missing": {
            "common.sample_size": "not_verified",
            "common.population_size": "not_reported",
            "common.locus_interval_start_bp": "not_verified",
            "common.locus_interval_end_bp": "not_verified",
            "common.genome_assembly": "not_verified",
        },
        "evidence": (
            ("common.locus_id", 4, "Results", "RBL1 (LOC_Os01g55360)"),
            ("common.alternate_allele", 4, "Results", "29-base-pair (bp) deletion"),
            ("common.population_name", 4, "Results", "pooled DNA from three lesioned M3 segregants"),
            ("common.trait_names", 4, "Results", "lesioned M3 segregants"),
        ),
    },
    {
        "ref": "A_RBL1_02",
        "association_kind": "functional_complementation",
        "locus_id": "urn:rbl1:gene:RBL1",
        "locus_type": "gene",
        "trait_names": ["disease resistance", "lesion mimic"],
        "trait_id": "urn:rbl1:trait:lesion-mimic",
        "population_id": "urn:rbl1:population:complementation",
        "population_name": "genetic complementation experiment",
        "population_type": "transgenic",
        "germplasm_names": ["KitaakeX", "rbl1"],
        "material_id": "urn:rbl1:material:RBL1-complemented-line",
        "environment_id": "urn:rbl1:environment:greenhouse",
        "alternate_allele": "RBL1",
        "page": 5,
        "section": "Results",
        "quote": ("Genetic complementation assays confirmed that RBL1 is the causative gene "
                  "(Fig. 1m–p and Extended Data Fig. 2f–g)."),
        "sequence_names": ["CoRBL1-F", "CoRBL1-R"],
        "validation_status": "experiment_reported",
        "effect_direction": "increase",
        "missing": {"common.sample_size": "not_verified"},
        "evidence": (
            ("common.locus_id", 5, "Results", "Genetic complementation assays confirmed that RBL1 is the causative gene"),
            ("common.alternate_allele", 5, "Results", "RBL1"),
            ("common.population_name", 5, "Results", "Genetic complementation assays"),
        ),
    },
    {
        "ref": "A_RBL1_03",
        "association_kind": "genome_editing",
        "locus_id": "urn:rbl1:allele:RBL1-delta12",
        "locus_type": "allele",
        "trait_names": ["multipathogen resistance", "yield"],
        "trait_id": "urn:rbl1:trait:multipathogen-resistance",
        "population_id": "urn:rbl1:population:edited-lines",
        "population_name": "RBL1Δ12 edited lines",
        "population_type": "T1/T2 edited lines",
        "germplasm_names": ["Kitaake", "rbl1Δ12"],
        "material_id": "urn:rbl1:material:RBL1-delta12",
        "environment_id": "urn:rbl1:environment:field-trial",
        "alternate_allele": "RBL1Δ12 (12 bp deletion)",
        "page": 6,
        "section": "Results",
        "quote": ("Notably, the rbl1Δ12 line with a 12-bp deletion, which showed only tiny hypersensitive "
                  "response-like lesions starting at the booting stage (Fig. 4c, Extended Data Figs. 7a and 8), "
                  "produced a normal seed set (Fig. 4d)."),
        "sequence_names": ["qRT-RBL1-F", "qRT-RBL1-R"],
        "validation_status": "candidate",
        "effect_direction": "increase",
        "missing": {
            "common.sample_size": "not_verified",
            "common.locus_interval_start_bp": "not_verified",
            "common.locus_interval_end_bp": "not_verified",
            "common.genome_assembly": "not_verified",
        },
        "evidence": (
            ("common.locus_id", 6, "Results", "RBL1Δ12"),
            ("common.alternate_allele", 6, "Results", "12-bp deletion"),
            ("common.trait_names", 6, "Results", "conferred resistance to 10 M. oryzae field strains"),
        ),
    },
)


def _stable(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256("\x1f".join(map(str, parts)).encode()).hexdigest()[:32]


def _norm_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", value).strip()


def _pdf_page_texts(pdf: Path | None) -> list[str] | None:
    if not pdf or not pdf.is_file():
        return None
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    return [_norm_text(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]


def _quote_check(records: list[dict], pages: list[str] | None) -> bool | None:
    if pages is None:
        return None
    for rec in records:
        for item in rec["common"].get("field_evidence") or []:
            page = item.get("page")
            quote = _norm_text(item.get("quote") or "")
            if page is None or not quote:
                continue
            if page > len(pages) or quote not in pages[page - 1]:
                return False
    return True


def _read_primers(path: Path) -> list[dict]:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return _read_primers_xlsx(path)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"{path}: empty primer table")
    required = {"primer_name", "sequence_5to3", "locator"}
    if set(rows[0]) != required:
        raise ValueError(f"{path}: header must be {sorted(required)}")
    out = []
    seen = set()
    for n, row in enumerate(rows, 2):
        name = (row.get("primer_name") or "").strip()
        seq = (row.get("sequence_5to3") or "").strip()
        locator = (row.get("locator") or "").strip()
        if not name or not seq or not locator:
            raise ValueError(f"{path}:{n}: empty primer name/sequence/locator")
        if name in seen:
            raise ValueError(f"{path}:{n}: duplicate primer name {name!r}")
        seen.add(name)
        out.append({"primer_name": name, "sequence_5to3": seq, "locator": locator, "line": n})
    return out


def _read_primers_xlsx(path: Path) -> list[dict]:
    """Read the original Supplementary Table 2 sheet, deriving Sheet1!A4:B4 locators from cell coordinates."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - exercised only without the xlsx extra
        raise ValueError("reading .xlsx primers needs the optional dependency: pip install '.[xlsx]'") from exc
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.active
        rows = list(ws.iter_rows(min_row=1, max_col=2))
        header = None
        for idx, row in enumerate(rows):
            vals = [str(c.value or "").strip().lower() for c in row[:2]]
            if any(("primer" in v) or ("引物" in v) for v in vals) and \
                    any(("sequence" in v) or ("序列" in v) for v in vals):
                header = idx
                break
        if header is None:
            raise ValueError(f"{path}: could not find a primer-name/sequence header in the first two columns")
        out, seen = [], set()
        for row in rows[header + 1:]:
            name = str(row[0].value or "").strip()
            seq = str(row[1].value or "").strip()
            if not name and not seq:
                continue
            if not name or not seq:
                raise ValueError(f"{path}:{row[0].row}: empty primer name/sequence")
            if name in seen:
                raise ValueError(f"{path}:{row[0].row}: duplicate primer name {name!r}")
            seen.add(name)
            locator = f"{ws.title}!A{row[0].row}:B{row[0].row}"
            out.append({"primer_name": name, "sequence_5to3": seq, "locator": locator,
                        "line": row[0].row})
        if not out:
            raise ValueError(f"{path}: empty primer table")
        return out
    finally:
        wb.close()


def _common(kind: str, grain: str, *, quote: str, locator: str, part: str,
            page: int | None = None, section: str | None = None,
            table_figure: str | None = None, file_sha256: str | None = None,
            file_role: str | None = None, file_status: str | None = None,
            file_url: str | None = None, review: str = "auto_validated", **extra) -> dict:
    common = {
        "schema_name": "breeding-literature-record", "schema_version": SCHEMA_VERSION,
        "record_kind": kind, "record_grain": grain,
        "source_id": "doi:" + DOI, "source_type": "paper", "source_title": TITLE,
        "source_doi": DOI, "source_year": 2023, "source_language": "en", "crop_name": "rice",
        "source_locator": locator, "source_quote": quote, "source_part": part,
        "review_status": review, "record_version": 1, "extraction_run_id": "run_rbl1_case",
        "extraction_method": "rule", "extraction_profile": PROFILE,
        "qc_rule_set_version": f"breeding-literature-record@{SCHEMA_VERSION}+rbl1-case@{CASE_VERSION}",
        **extra,
    }
    if page is not None:
        common["source_page"] = page
    if section:
        common["source_section"] = section
    if table_figure:
        common["source_table_figure"] = table_figure
    if file_sha256:
        common["source_file_sha256"] = file_sha256
    if file_role:
        common["source_file_role"] = file_role
    if file_status:
        common["source_file_status"] = file_status
    if file_url:
        common["source_file_url"] = file_url
    record = {"common": common}
    record["common"]["record_id"] = _stable("rec_", kind, locator, quote, common.get("primer_name", ""))
    return record


def _evidence(field: str, file_id: str, locator: str, quote: str, *, page: int | None = None,
              sheet: str | None = None, cell: str | None = None) -> dict:
    item = {"field": field, "file_id": file_id, "locator": locator, "quote": quote}
    if page is not None:
        item["page"] = page
    if sheet:
        item["sheet"] = sheet
    if cell:
        item["cell"] = cell
    return item


def build_case(pdf: Path | None, primers: Path, out_dir: Path, *, schema_version: str = SCHEMA_VERSION) -> dict:
    """Build the records/tables for the RBL1 case.  ``pdf`` may be None for a CSV-only smoke test."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    primers = Path(primers)
    rows = _read_primers(primers)
    pdf = Path(pdf) if pdf else None
    primer_sha = sha256_file(primers)
    pdf_sha = sha256_file(pdf) if pdf and pdf.is_file() else None
    pdf_size = pdf.stat().st_size if pdf and pdf.is_file() else None
    if pdf_sha and pdf_sha != EXPECTED_PDF_SHA256:
        raise ValueError(f"{pdf}: SHA256 {pdf_sha} is not the RBL1 case PDF "
                         f"({EXPECTED_PDF_SHA256})")

    pdf_file_id = _stable("rec_", "asset", "pdf", pdf_sha or "missing")
    csv_file_id = _stable("rec_", "asset", "primers", primer_sha)

    records: list[dict] = []
    assets: list[dict] = []
    if pdf is not None and pdf.is_file():
        asset = _common("asset_manifest", "asset_unit", quote=pdf.name, locator="document",
                        part="main_text", file_sha256=pdf_sha, file_role="main_text",
                        file_status="parsed", file_url=PAPER_URL, review="auto_validated")
        asset["common"].update({
            "asset_kind": "raw_pdf", "asset_format": "PDF", "asset_size_bytes": pdf_size,
            "asset_sha256": pdf_sha, "source_uri": "https://doi.org/" + DOI,
            "missing_fields": {"common.license_id": "requires_review"},
        })
        asset["common"]["record_id"] = pdf_file_id
        assets.append(asset)
        records.append(asset)
    asset_csv = _common("asset_manifest", "asset_unit", quote=primers.name, locator="document",
                        part="supplement", file_sha256=primer_sha, file_role="primer_table",
                        file_status="parsed", file_url=XLSX_URL, review="auto_validated")
    asset_csv["common"].update({
        "asset_kind": "table", "asset_format": primers.suffix.lstrip(".").upper(),
        "asset_size_bytes": primers.stat().st_size,
        "asset_sha256": primer_sha, "source_uri": "https://doi.org/" + DOI,
        "missing_fields": {"common.license_id": "requires_review"},
    })
    asset_csv["common"]["record_id"] = csv_file_id
    assets.append(asset_csv)
    records.append(asset_csv)

    sequences: dict[str, dict] = {}
    for row in rows:
        name, seq, loc = row["primer_name"], row["sequence_5to3"], row["locator"]
        role, direction, use = ROLE.get(name, ("other", "unknown", ""))
        rec = _common("sequence", "sequence_unit",
                      quote=f"{name}\t{seq}", locator=f"part=supplement;table=Supplementary Table 2;row={row['line']};col=1",
                      part="supplement", table_figure="Supplementary Table 2", file_sha256=primer_sha,
                      file_role="primer_table", file_status="extracted", file_url=XLSX_URL,
                      review="auto_validated")
        rec["common"].update({
            "primer_name": name, "primer_role": role, "primer_sequence": seq,
            "primer_direction": direction, "primer_use": use,
            "primer_source_locator": loc, "primer_status": "verbatim",
            "field_evidence": [_evidence("common.primer_name", csv_file_id, loc, name,
                                         sheet="Sheet1", cell=loc.split("!")[-1]),
                               _evidence("common.primer_sequence", csv_file_id, loc, seq,
                                         sheet="Sheet1", cell=loc.split("!")[-1]),
                               _evidence("common.primer_source_locator", csv_file_id, loc, loc,
                                         sheet="Sheet1", cell=loc.split("!")[-1])],
        })
        if name.startswith("CoRBL1"):
            rec["transform"] = {
                "entity_synonyms": [name.replace("-", "").upper()],
                "entity_alias_status": "candidate",
                "entity_alias_of": name,
            }
        rec["common"]["record_id"] = _stable("rec_", "sequence", name, seq, loc)
        sequences[name] = rec
        records.append(rec)

    associations: list[dict] = []
    for spec in ASSOCIATIONS:
        page = spec["page"]
        rec = _common("association", "association_unit", quote=spec["quote"],
                      locator=f"page={page};section={spec['section']}", part="main_text",
                      page=page, section=spec["section"],
                      file_sha256=pdf_sha, file_role="main_text", file_status="extracted",
                      file_url=PAPER_URL, review="pending_review" if spec["missing"] else "auto_validated")
        rec["common"].update({
            "study_id": "urn:rbl1:study:Sha-2023",
            "population_id": spec["population_id"], "population_name": spec["population_name"],
            "population_type": spec["population_type"], "material_id": spec["material_id"],
            "germplasm_names": spec["germplasm_names"], "environment_id": spec["environment_id"],
            "trait_names": spec["trait_names"], "trait_id": spec["trait_id"],
            "association_kind": spec["association_kind"], "locus_id": spec["locus_id"],
            "locus_type": spec["locus_type"], "alternate_allele": spec["alternate_allele"],
            "sequence_record_ids": [sequences[n]["common"]["record_id"] for n in spec["sequence_names"]],
            "missing_fields": spec["missing"],
            "field_evidence": [_evidence(field, pdf_file_id, f"page={p};section={sec}", q, page=p)
                               for field, p, sec, q in spec["evidence"]],
        })
        rec["agent"] = {"finding_text": spec["quote"], "effect_direction": spec["effect_direction"]}
        if spec["validation_status"]:
            rec["transform"] = {"validation_status": spec["validation_status"]}
        rec["common"]["record_id"] = _stable("rec_", "association", spec["ref"], spec["locus_id"],
                                             spec["population_id"])
        spec["association_id"] = rec["common"]["record_id"]
        associations.append(rec)
        records.append(rec)

    # Validate every record against the released 4.0.0 profile.
    rc = resolve_schema(schema_version)
    validator = rc.validator(PROFILE)
    errors = []
    for rec in records:
        result = validator.validate(rec)
        if not result.valid:
            errors.append({"record_id": rec["common"]["record_id"],
                           "errors": [i.to_dict() for i in result.errors]})
    if errors:
        raise ValueError(f"RBL1 case records do not validate: {json.dumps(errors, ensure_ascii=False)[:2000]}")

    tables = _tables(records)
    _assign_evidence_ids(records)
    evidence_rows = _field_evidence_rows(records)
    triples = _triples(records, associations,
                       {r["common"]["record_id"]: r for r in records if r["common"]["record_kind"] == "sequence"})
    aliases = _alias_rows(sequences)
    quote_ok = _quote_check(records, _pdf_page_texts(pdf))
    checks = _checks(rows, sequences, associations, assets, pdf_sha, errors, quote_ok)
    report = {
        "case_format": 1, "case_version": CASE_VERSION, "contract": {"schema_name": rc.name, "schema_version": rc.version},
        "paper": {"doi": DOI, "title": TITLE, "pdf_available": bool(pdf_sha), "pdf_sha256": pdf_sha,
                  "pdf_url": PAPER_URL, "primer_file": primers.name, "primer_sha256": primer_sha,
                  "primer_url": XLSX_URL},
        "counts": {"records": len(records), "assets": len(assets), "sequences": len(sequences),
                   "associations": len(associations), "field_evidence": len(evidence_rows),
                   "triples": len(triples), "aliases": len(aliases)},
        "checks": checks,
        "associations": [{"association_id": a["common"]["record_id"], "ref": s["ref"],
                          "locus_id": s["locus_id"], "population_id": s["population_id"],
                          "association_kind": s["association_kind"]}
                         for a, s in zip(associations, ASSOCIATIONS)],
    }
    # Write files.
    (out_dir / "records.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                                            encoding="utf-8")
    (out_dir / "associations.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in associations) + "\n",
                                                encoding="utf-8")
    (out_dir / "sequences.jsonl").write_text("\n".join(json.dumps(sequences[k], ensure_ascii=False) for k in
                                                      sorted(sequences)) + "\n", encoding="utf-8")
    (out_dir / "sources.jsonl").write_text("\n".join(json.dumps(a, ensure_ascii=False) for a in assets) + "\n",
                                           encoding="utf-8")
    _write_csv(out_dir / "source_files.csv", _source_rows(assets))
    (out_dir / "source_manifest.json").write_text(json.dumps({
        "source_manifest_format": 1, "paper": report["paper"], "files": _source_rows(assets),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(out_dir / "associations.csv", tables["associations"])
    _write_csv(out_dir / "populations.csv", tables["populations"])
    _write_csv(out_dir / "materials.csv", tables["materials"])
    _write_csv(out_dir / "loci.csv", tables["loci"])
    _write_csv(out_dir / "sequences.csv", tables["sequences"])
    _write_csv(out_dir / "field_evidence.csv", evidence_rows)
    _write_csv(out_dir / "aliases.csv", aliases)
    (out_dir / "triples.jsonl").write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in triples) + "\n",
                                           encoding="utf-8")
    (out_dir / "rbl1_case.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _source_rows(assets: list[dict]) -> list[dict]:
    return [{"file_id": a["common"]["record_id"], "role": a["common"].get("source_file_role"),
             "status": a["common"].get("source_file_status"), "format": a["common"].get("asset_format"),
             "sha256": a["common"].get("asset_sha256"), "url": a["common"].get("source_file_url"),
             "name": a["common"].get("source_quote"), "license": a["common"].get("license_id", ""),
             "license_status": (a["common"].get("missing_fields") or {}).get("common.license_id", "unknown")}
            for a in assets]


def _assign_evidence_ids(records: list[dict]) -> None:
    for rec in records:
        for item in rec["common"].get("field_evidence") or []:
            if not item.get("evidence_id"):
                item["evidence_id"] = _stable("ev_", rec["common"]["record_id"], item.get("field"),
                                              item.get("file_id"), item.get("locator"))


def _field_evidence_rows(records: list[dict]) -> list[dict]:
    rows = []
    for rec in records:
        for e in get_path(rec, "common.field_evidence", None) or []:
            rows.append({"record_id": rec["common"]["record_id"], "evidence_id": e.get("evidence_id"),
                         "field": e.get("field"),
                         "file_id": e.get("file_id"), "locator": e.get("locator"),
                         "quote": e.get("quote"), "page": e.get("page", ""),
                         "sheet": e.get("sheet", ""), "cell": e.get("cell", "")})
    return rows


def _tables(records: list[dict]) -> dict:
    assoc = []
    pops, mats, loci, seqs = {}, {}, {}, {}
    for rec in records:
        c = rec["common"]
        if c["record_kind"] == "association":
            assoc.append({
                "association_id": c["record_id"], "study_id": c.get("study_id", ""),
                "population_id": c.get("population_id", ""), "population_name": c.get("population_name", ""),
                "population_type": c.get("population_type", ""), "material_id": c.get("material_id", ""),
                "germplasm_names": ";".join(c.get("germplasm_names") or []),
                "environment_id": c.get("environment_id", ""),
                "trait_names": ";".join(c.get("trait_names") or []), "trait_id": c.get("trait_id", ""),
                "locus_id": c.get("locus_id", ""), "locus_type": c.get("locus_type", ""),
                "association_kind": c.get("association_kind", ""), "alternate_allele": c.get("alternate_allele", ""),
                "sequence_record_ids": ";".join(c.get("sequence_record_ids") or []),
                "missing_fields": json.dumps(c.get("missing_fields") or {}, ensure_ascii=False),
                "field_evidence_count": len(c.get("field_evidence") or []),
                "source_locator": c.get("source_locator", ""),
                "review_status": c.get("review_status", ""),
                "validation_status": rec.get("transform", {}).get("validation_status", ""),
            })
            if c.get("population_id"):
                pops[c["population_id"]] = {"population_id": c["population_id"],
                                            "population_name": c.get("population_name", ""),
                                            "population_type": c.get("population_type", ""),
                                            "environment_id": c.get("environment_id", "")}
            if c.get("material_id"):
                mats[c["material_id"]] = {"material_id": c["material_id"],
                                          "material_names": ";".join(c.get("germplasm_names") or [])}
            if c.get("locus_id"):
                loci[c["locus_id"]] = {"locus_id": c["locus_id"], "locus_type": c.get("locus_type", ""),
                                       "trait_ids": c.get("trait_id", ""),
                                       "assembly": c.get("genome_assembly", ""),
                                       "missing_fields": json.dumps(c.get("missing_fields") or {}, ensure_ascii=False)}
        elif c["record_kind"] == "sequence":
            seqs[c["record_id"]] = {
                "sequence_id": c["record_id"], "primer_name": c.get("primer_name", ""),
                "primer_role": c.get("primer_role", ""), "sequence_5to3": c.get("primer_sequence", ""),
                "direction": c.get("primer_direction", ""), "use": c.get("primer_use", ""),
                "source_locator": c.get("primer_source_locator", ""), "status": c.get("primer_status", ""),
                "alias_status": rec.get("transform", {}).get("entity_alias_status", ""),
                "alias_of": rec.get("transform", {}).get("entity_alias_of", ""),
            }
    return {"associations": assoc, "populations": list(pops.values()), "materials": list(mats.values()),
            "loci": list(loci.values()), "sequences": list(seqs.values())}


def _triples(records: list[dict], associations: list[dict], sequences: dict[str, dict]) -> list[dict]:
    out = []
    for rec in associations:
        c = rec["common"]
        aid = c["record_id"]
        for trait in c.get("trait_names") or []:
            out.append({"association_id": aid, "subject": aid, "predicate": "associated_with_trait",
                        "object": trait, "object_type": "trait", "population_id": c.get("population_id"),
                        "environment_id": c.get("environment_id"),
                        "evidence_ids": [e.get("evidence_id") for e in c.get("field_evidence") or []]})
        out.append({"association_id": aid, "subject": aid, "predicate": "studies_locus",
                    "object": c.get("locus_id"), "object_type": c.get("locus_type"),
                    "population_id": c.get("population_id"), "environment_id": c.get("environment_id"),
                    "evidence_ids": [e.get("evidence_id") for e in c.get("field_evidence") or []]})
        out.append({"association_id": aid, "subject": aid, "predicate": "studied_in_population",
                    "object": c.get("population_id"), "object_type": "population",
                    "population_id": c.get("population_id"), "environment_id": c.get("environment_id"),
                    "evidence_ids": [e.get("evidence_id") for e in c.get("field_evidence") or []]})
        for sid in c.get("sequence_record_ids") or []:
            seq = sequences.get(sid, {}).get("common", {})
            seq_ev = [e.get("evidence_id") for e in sequences.get(sid, {}).get("common", {}).get("field_evidence") or []]
            out.append({"association_id": aid, "subject": aid, "predicate": "uses_sequence",
                        "object": seq.get("primer_name", sid), "object_id": sid, "object_type": "sequence",
                        "population_id": c.get("population_id"),
                        "environment_id": c.get("environment_id"), "evidence_ids": seq_ev})
    return out


def _alias_rows(sequences: dict[str, dict]) -> list[dict]:
    rows = []
    for rec in sequences.values():
        t = rec.get("transform") or {}
        if t.get("entity_alias_status"):
            rows.append({"record_id": rec["common"]["record_id"], "entity": rec["common"].get("primer_name"),
                         "alias": ";".join(t.get("entity_synonyms") or []),
                         "alias_of": t.get("entity_alias_of"), "status": t.get("entity_alias_status")})
    return rows


def _checks(rows, sequences, associations, assets, pdf_sha, errors, quote_ok=None) -> dict:
    by_name = {r["common"].get("primer_name"): r for r in sequences.values()}
    exact = all(by_name.get(row["primer_name"], {}).get("common", {}).get("primer_sequence") == row["sequence_5to3"]
                for row in rows)
    expected = all(EXPECTED_PRIMERS.get(row["primer_name"]) == (row["sequence_5to3"], row["locator"])
                   for row in rows) and set(EXPECTED_PRIMERS) == {row["primer_name"] for row in rows}
    locators = all(by_name.get(row["primer_name"], {}).get("common", {}).get("primer_source_locator") == row["locator"]
                   for row in rows)
    iupac = set("ACGTURYSWKMBDHVN")
    iupac_ok = all(set((row["sequence_5to3"] or "").upper()) <= iupac for row in rows)
    original = next((a for a in associations if "29 bp" in (a["common"].get("alternate_allele") or "")), None)
    edited = next((a for a in associations if "RBL1Δ12" in (a["common"].get("alternate_allele") or "")), None)
    alias_ok = any((r.get("transform") or {}).get("entity_alias_status") == "candidate" for r in sequences.values())
    missing_ok = all(("locus_interval_start_bp" not in a["common"]) for a in associations) and \
        any("not_verified" in (a["common"].get("missing_fields") or {}).values() for a in associations)
    return {
        "six_sequences": len(rows) == 6 and len(sequences) == 6,
        "sequences_exact": exact,
        "sequences_expected": expected,
        "sequences_iupac": iupac_ok,
        "sequence_locators_exact": locators,
        "associations_three": len(associations) == 3,
        "original_and_edited_separate": bool(original and edited and
                                             original["common"]["locus_id"] != edited["common"]["locus_id"]),
        "population_size_not_filled": all("population_size" not in a["common"] for a in associations),
        "missing_reason_not_verified": missing_ok,
        "alias_candidate": alias_ok,
        "field_evidence_present": all(len(a["common"].get("field_evidence") or []) > 0 for a in associations),
        "pdf_hash_expected": (pdf_sha == EXPECTED_PDF_SHA256) if pdf_sha else None,
        "pdf_quotes_verified": quote_ok,
        "records_valid": not errors,
    }
