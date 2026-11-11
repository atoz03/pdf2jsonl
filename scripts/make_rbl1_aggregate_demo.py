#!/usr/bin/env python3
"""Build a small multi-paper association demo from the RBL1 case.

The real RBL1 paper supplies one paper.  To exercise cross-paper aggregation we add two explicitly synthetic
papers: an independent replication and a conflicting report.  They are marked as synthetic in their titles and
are not represented as real findings.  The script writes the records and the aggregate view; it does not alter
the RBL1 case.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from breeding_contract.association_aggregate import aggregate_associations  # noqa: E402
from breeding_contract.rbl1_case import _stable  # noqa: E402


def _synthetic(base: dict, *, suffix: str, title: str, doi: str, population: str,
               direction: str, page: int) -> dict:
    rec = copy.deepcopy(base)
    c = rec["common"]
    c["source_id"] = "doi:" + doi
    c["source_doi"] = doi
    c["source_title"] = title
    c["source_year"] = 2026
    c["source_locator"] = f"page={page};section=Synthetic results"
    c["source_page"] = page
    c["source_section"] = "Synthetic results"
    c["source_quote"] = f"Synthetic demo sentence for {suffix}; not a real paper."
    c["review_status"] = "auto_validated"
    c["population_id"] = f"urn:rbl1:population:{suffix}"
    c["population_name"] = population
    c["population_type"] = "synthetic panel"
    c["study_id"] = f"urn:rbl1:study:{suffix}"
    c["material_id"] = f"urn:rbl1:material:{suffix}"
    c["germplasm_names"] = [population]
    c["environment_id"] = f"urn:rbl1:environment:{suffix}"
    c["source_file_url"] = f"https://example.org/{suffix}"
    c.pop("missing_fields", None)
    c["field_evidence"] = [
        {"field": "common.locus_id", "locator": f"page={page};section=Synthetic results",
         "quote": "RBL1 synthetic demo", "page": page},
        {"field": "common.trait_names", "locator": f"page={page};section=Synthetic results",
         "quote": "lesion mimic / disease resistance synthetic demo", "page": page},
        {"field": "common.population_name", "locator": f"page={page};section=Synthetic results",
         "quote": population, "page": page},
    ]
    rec.setdefault("agent", {})["finding_text"] = c["source_quote"]
    rec["agent"]["effect_direction"] = direction
    c["record_id"] = _stable("rec_", "association", suffix, c["locus_id"], c["population_id"])
    return rec


def build(case_dir: Path, out_dir: Path) -> dict:
    records = [json.loads(line) for line in (case_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    originals = [copy.deepcopy(r) for r in records
                 if (r.get("common") or {}).get("record_kind") == "association"]
    base = next(r for r in originals if "29 bp" in (r["common"].get("alternate_allele") or ""))
    base_delta = next(r for r in originals if "RBL1Δ12" in (r["common"].get("alternate_allele") or ""))
    replication = _synthetic(base, suffix="replication", title=(
        "Synthetic independent replication of RBL1–lesion mimic association (demo only)"),
        doi="10.0000/rbl1.synthetic.replication", population="synthetic independent RIL panel",
        direction="increase", page=2)
    conflict = _synthetic(base, suffix="conflict", title=(
        "Synthetic conflicting report on RBL1–lesion mimic association (demo only)"),
        doi="10.0000/rbl1.synthetic.conflict", population="synthetic conflicting panel",
        direction="decrease", page=3)
    delta_replication = _synthetic(base_delta, suffix="delta12-replication", title=(
        "Synthetic independent replication of RBL1Δ12–multipathogen resistance (demo only)"),
        doi="10.0000/rbl1.synthetic.delta12", population="synthetic RBL1Δ12 panel",
        direction="increase", page=4)
    height = _synthetic(base_delta, suffix="height", title=(
        "Synthetic single-paper RBL1–plant height report (demo only)"),
        doi="10.0000/rbl1.synthetic.height", population="synthetic height panel",
        direction="increase", page=5)
    height["common"].update({
        "locus_id": "urn:rbl1:locus:RBL1-height-synthetic",
        "trait_id": "urn:rbl1:trait:plant-height",
        "trait_names": ["plant height"],
        "alternate_allele": "RBL1",
    })
    height["common"]["field_evidence"][1] = {
        "field": "common.trait_names", "locator": "page=5;section=Synthetic results",
        "quote": "plant height synthetic demo", "page": 5,
    }
    height["common"]["record_id"] = _stable("rec_", "association", "height",
                                            height["common"]["locus_id"], height["common"]["population_id"])
    multi = records + [replication, conflict, delta_replication, height]
    aggregate = aggregate_associations(multi)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "records.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in multi) + "\n", encoding="utf-8")
    (out_dir / "association_aggregate.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "multi_paper.json").write_text(json.dumps({
        "case": "rbl1-multi-paper-demo",
        "synthetic_papers": 4,
        "note": "Four explicitly synthetic papers exercise A/B/C confidence, replication and conflict; "
                "not real findings.",
        "aggregate_counts": aggregate["counts"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return aggregate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-dir", default="out/rbl1_case_final")
    ap.add_argument("--out", default="out/rbl1_multi")
    args = ap.parse_args(argv)
    agg = build(Path(args.case_dir), Path(args.out))
    print(json.dumps(agg["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
