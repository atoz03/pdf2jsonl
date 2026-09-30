#!/usr/bin/env python3
"""Regenerate everything under examples/ that is derived (records, pipeline output, migrations).

    PYTHONPATH=src python scripts/make_examples.py            # against the latest release

Outputs are reproducible: SOURCE_DATE_EPOCH and fixed run IDs pin every timestamp. Manifests still record the
local environment (python/platform/package versions), so they may differ between machines; records do not.
`bdc check` validates all of it (records against their declared contract version, envelopes against
schemas/runtime/). All example content is synthetic.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from breeding_contract.api import resolve_schema  # noqa: E402
from breeding_contract.bundle import bundle_file  # noqa: E402
from breeding_contract.ids import build_locator, stable_record_id  # noqa: E402
from breeding_contract.legacy import migrate_legacy_file  # noqa: E402
from breeding_contract.omics import migrate_omics_file  # noqa: E402
from breeding_contract.util import set_path  # noqa: E402

EPOCH = "1790000000"  # 2026-09-21T14:13:20Z
EX = ROOT / "examples"

# One curated record per kind that the extraction example does not produce. Values are synthetic.
TRIAL = {"common.source_id": "urn:example:synthetic-trial-2025", "common.source_type": "experiment_record",
         "common.source_title": "Synthetic multi-environment rice trial 2025 (example data)",
         "common.crop_name": "rice", "common.species_name": "Oryza sativa", "common.trial_id": "T2025-01",
         "common.trial_year": 2025, "common.extraction_method": "etl", "common.review_status": "auto_validated"}
CURATED = [
    ("environment_observation", {
        **TRIAL, "common.environment_id": "E1", "common.location_name": "Synthetic Station North",
        "common.measurement_name": "mean air temperature", "common.measurement_value": 27.4,
        "common.measurement_unit": "°C",
        "_locator": {"table": "weather", "row": "E1/2025-07", "col": "tmean"}}),
    ("phenotype_observation", {
        **TRIAL, "common.environment_id": "E1", "common.material_id": "RIL-017", "common.germplasm_names": ["RIL-017"],
        "common.trait_names": ["plant height"], "common.measurement_name": "plant height",
        "common.measurement_value": 1184, "common.measurement_unit": "mm",
        "common.original_value": "1184", "common.original_unit": "mm",
        "common.normalized_value": 118.4, "common.normalized_unit": "cm",
        "_locator": {"table": "phenotypes", "row": "RIL-017/E1", "col": "PH_mm"}}),
    ("genotype_observation", {
        **TRIAL, "common.material_id": "RIL-017", "common.sample_id": "S-017", "common.variant_id": "SYN_chr07_1234567",
        "common.genome_assembly": "IRGSP-1.0", "common.chromosome": "7", "common.variant_position_bp": 1234567,
        "common.reference_allele": "G", "common.alternate_allele": "A", "common.genotype_call": "G/A",
        "common.ploidy": 2, "common.dosage_allele": "A", "common.genotype_dosage": 1,
        "_locator": {"table": "genotypes", "row": "S-017", "col": "SYN_chr07_1234567"}}),
    ("tool_spec", {
        "common.source_id": "urn:example:tool-gwas-lmm", "common.source_type": "tool_description",
        "common.source_title": "Example GWAS mixed-model tool card", "common.crop_name": "rice",
        "common.extraction_method": "manual", "common.review_status": "expert_approved",
        "skills.method_name": "mixed linear model GWAS", "skills.method_category": "GWAS",
        "skills.software_name": "GEMMA", "skills.software_version": "0.98.5",
        "skills.tool_input_formats": ["PLINK bed", "phenotype TSV"], "skills.tool_output_formats": ["assoc TSV"],
        # Topic 3: standard inputs, outputs and parameter semantics of a skill
        "skills.input_modalities": ["genotype", "phenotype"],
        "skills.genotype_data_format": "PLINK bed", "skills.phenotype_data_format": "TSV",
        "skills.output_fields": ["chr", "rs", "ps", "beta", "se", "p_wald"],
        "skills.parameters": [
            {"name": "lmm", "value": 1, "value_kind": "categorical", "constraint": "1 = Wald test",
             "source": "tool manual"},
            {"name": "maf", "value": 0.01, "value_kind": "threshold", "constraint": "0 <= maf <= 0.5",
             "source": "tool manual"}],
        "skills.workflow_steps": [
            {"step_no": 1, "step_name": "kinship", "tool_name": "GEMMA", "step_desc": "estimate the relatedness matrix",
             "inputs": ["PLINK bed"], "outputs": ["kinship matrix"]},
            {"step_no": 2, "step_name": "association", "tool_name": "GEMMA",
             "step_desc": "fit the univariate linear mixed model", "inputs": ["PLINK bed", "kinship matrix"],
             "outputs": ["assoc TSV"]}],
        "_locator": {"section": "Usage"}}),
]


def curated_records(version: str) -> dict[str, dict]:
    rc = resolve_schema(version, ROOT)
    kinds = rc.contract["record_kinds"]
    validator = rc.validator()
    out = {}
    for kind, spec in CURATED:
        spec = dict(spec)
        locator = build_locator(**spec.pop("_locator"))
        rec: dict = {}
        for path, value in spec.items():
            set_path(rec, path, value)
        system = {"common.schema_name": rc.name, "common.schema_version": rc.version, "common.record_kind": kind,
                  "common.record_id": stable_record_id(spec["common.source_id"], kind, locator, None),
                  "common.source_locator": locator, "common.record_version": 1}
        if kinds[kind].get("grain"):
            system["common.record_grain"] = kinds[kind]["grain"]
        for path, value in system.items():
            set_path(rec, path, value)
        res = validator.validate(rec)
        if not res.valid:
            raise SystemExit(f"curated {kind} record is invalid: {[i.to_dict() for i in res.errors]}")
        out[kind] = rec
    return out


def main() -> None:
    os.environ["SOURCE_DATE_EPOCH"] = EPOCH
    version = resolve_schema("latest", ROOT).version

    # 1. curated records, one file per kind
    for kind, rec in curated_records(version).items():
        (EX / "records" / f"{kind}.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. pdf2jsonl on the synthetic paper with the checked-in candidates (one fabricated quote -> rejected)
    out = EX / "output"
    shutil.rmtree(out, ignore_errors=True)
    subprocess.run([str(ROOT / "skills/pdf2jsonl/scripts/pdf2jsonl"), "run", str(EX / "papers/synthetic_rice_qtl.pdf"),
                    "--candidates", str(EX / "papers/synthetic_rice_qtl.candidates.json"), "--out-dir", str(out),
                    "--schema-version", version, "--run-id", "run_example", "--bundle"],
                   check=True, env={**os.environ, "BREEDING_CONTRACT_HOME": str(ROOT)}, stdout=subprocess.DEVNULL)

    # 3. legacy v1 migration (journal pages 2221.. -> physical pages: offset 2220) + derived views
    leg = EX / "migration/legacy_v1"
    for p in leg.glob("breeding_jsonl_example.*"):
        p.unlink()
    migrate_legacy_file(ROOT / "sources/legacy_v1/breeding_jsonl_example.jsonl", leg, version, page_offset=2220, root=ROOT)
    bundle_file(leg / "breeding_jsonl_example.migrated.jsonl", root=ROOT)
    bundle_file(leg / "breeding_jsonl_example.migrated.jsonl", legacy_v1=True, root=ROOT)

    # 4. omics v2 migration of a filled synthetic instance of the template
    om = EX / "migration/omics_v2"
    for p in om.glob("synthetic_deg_instance.*"):
        if p.suffix != ".json" or p.name.count(".") > 1:
            p.unlink()
    migrate_omics_file(om / "synthetic_deg_instance.json", om, version, root=ROOT)
    print(f"examples regenerated against {version}")


if __name__ == "__main__":
    main()
