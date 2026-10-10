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
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from breeding_contract.api import resolve_schema  # noqa: E402
from breeding_contract.bundle import bundle_file  # noqa: E402
from breeding_contract.derive import derive_file  # noqa: E402
from breeding_contract.ids import build_locator, stable_record_id  # noqa: E402
from breeding_contract.legacy import migrate_legacy_file  # noqa: E402
from breeding_contract.merged import migrate_merged_file  # noqa: E402
from breeding_contract.omics import migrate_omics_file  # noqa: E402
from breeding_contract.util import dumps_json, set_path  # noqa: E402
from breeding_contract.verify import apply_file, tasks_file  # noqa: E402

EPOCH = "1790000000"  # 2026-09-21T14:13:20Z
EX = ROOT / "examples"
PDF2JSONL = str(ROOT / "skills/pdf2jsonl/scripts/pdf2jsonl")

# The two-file paper (main text + supplement) and what a verifier model returns for its records, keyed by the
# `ref` of the candidates (examples/papers/synthetic_rice_heat.candidates.json). The verdicts are hand-written
# like the candidates: they stand in for a model so that the example is reproducible.
HEAT = "synthetic_rice_heat"
VERIFIER = {"method": "model", "model": "example-verifier",
            "notes": "Hand-written verdicts that stand in for a second model (not the extractor)."}
RECORD_VERDICTS = {
    "r_ko": ("not_supported", ["common.germplasm_names"],
             "The sentence compares the HTR1 knockout lines with WY. SL14 is named on the same page, not in this quote."),
}
LINK_VERDICTS = {
    ("m_ko", "prerequisite", "a_map"): (
        "uncertain", "The knockout follows the fine mapping in the text, but the paper does not say that it used "
                     "the mapped interval; order of presentation is not a dependency."),
}
CONFLICTS = [(("r_sl14", "m_heat"), "Duration of the heat treatment: 12 h in the Results, 14 h in the Materials and "
                                    "Methods of the supplement.")]
OMISSIONS = [{"page": 2, "source_part": "supplement", "quote": "WY 21.3 %",
              "note": "The survival of the recurrent parent, the control of the comparison in Fig. S1, has no record."}]

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


def pdf2jsonl(paper: Path, candidates: Path, out: Path, version: str, run_id: str, *extra: str,
              epoch: str = EPOCH) -> None:
    subprocess.run([PDF2JSONL, "run", str(paper), "--candidates", str(candidates), "--out-dir", str(out),
                    "--schema-version", version, "--run-id", run_id, *extra],
                   check=True, env={**os.environ, "BREEDING_CONTRACT_HOME": str(ROOT), "SOURCE_DATE_EPOCH": epoch},
                   stdout=subprocess.DEVNULL)


def main_text_candidates(doc: dict) -> dict:
    """The candidates an extractor writes when it is given the main text only: nothing that cites another part,
    and no link to such a candidate."""
    kept = [c for c in doc["candidates"] if not c["evidence"].get("part")]
    refs = {c["ref"] for c in kept}
    out = []
    for c in kept:
        links = {k: [r for r in v if r in refs] for k, v in (c.get("links") or {}).items()}
        links = {k: v for k, v in links.items() if v}
        out.append({k: v for k, v in {**c, "links": links}.items() if v})
    notes = "The candidates of the two-file example without those that cite the supplement (made by make_examples.py)."
    return {**doc, "extraction": {**doc["extraction"], "notes": notes}, "candidates": out}


def example_verdicts(candidates: dict, out: Path, review: Path) -> dict:
    """The verdicts file of the example: every task `supported` except those listed at the top of this script."""
    report = json.loads((out / f"{HEAT}.validation.json").read_text(encoding="utf-8"))
    refs = [c["ref"] for c in candidates["candidates"]]
    rid = {refs[r["candidate_index"]]: r["record_id"] for r in report["records"] if r.get("candidate_index") is not None}
    ref_of = {v: k for k, v in rid.items()}
    tasks = json.loads((review / f"{HEAT}.verify.tasks.json").read_text(encoding="utf-8"))
    verdicts, used = [], set()
    for t in tasks["tasks"]:
        if t["kind"] == "record":
            key, spec = ref_of.get(t["record_id"]), RECORD_VERDICTS.get(ref_of.get(t["record_id"]))
            row = {"task_id": t["task_id"], "verdict": "supported"} if spec is None else \
                {"task_id": t["task_id"], "verdict": spec[0], "unsupported_fields": spec[1], "reason": spec[2]}
        else:
            key = (ref_of.get(t["record_id"]), t["edge"], ref_of.get(t["target"]["record_id"]))
            spec = LINK_VERDICTS.get(key)
            row = {"task_id": t["task_id"], "verdict": "supported"} if spec is None else \
                {"task_id": t["task_id"], "verdict": spec[0], "reason": spec[1]}
        if spec is not None:
            used.add(key)
        verdicts.append(row)
    unused = (set(RECORD_VERDICTS) | set(LINK_VERDICTS)) - used
    if unused:
        raise SystemExit(f"example verdicts name tasks that do not exist: {sorted(map(str, unused))}")
    return {"verifier": VERIFIER, "input_sha256": tasks["input"]["sha256"], "verdicts": verdicts,
            "conflicts": [{"record_ids": [rid[r] for r in pair], "reason": reason} for pair, reason in CONFLICTS],
            "omissions": OMISSIONS}


def main() -> None:
    os.environ["SOURCE_DATE_EPOCH"] = EPOCH
    version = resolve_schema("latest", ROOT).version

    # 1. curated records, one file per kind
    for kind, rec in curated_records(version).items():
        (EX / "records" / f"{kind}.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. pdf2jsonl on the synthetic paper with the checked-in candidates (one fabricated quote -> rejected)
    out = EX / "output"
    shutil.rmtree(out, ignore_errors=True)
    shutil.rmtree(EX / "derived", ignore_errors=True)
    pdf2jsonl(EX / "papers/synthetic_rice_qtl.pdf", EX / "papers/synthetic_rice_qtl.candidates.json", out, version,
              "run_example", "--bundle")

    # 2b. a paper in two files. With the supplement its methods and Fig. S1 are evidence; the same paper as a
    #     library holds it without the supplement comes first (an earlier run of the same input).
    heat_paper = EX / f"papers/{HEAT}.pdf"
    candidates = json.loads((EX / f"papers/{HEAT}.candidates.json").read_text(encoding="utf-8"))
    main_only = main_text_candidates(candidates)
    with tempfile.TemporaryDirectory() as tmp:
        partial = Path(tmp) / f"{HEAT}.main_only.candidates.json"
        partial.write_text(json.dumps(main_only, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        pdf2jsonl(heat_paper, partial, out / "incomplete", version, "run_example_heat_main_only",
                  epoch=str(int(EPOCH) - 3600))
    pdf2jsonl(heat_paper, EX / f"papers/{HEAT}.candidates.json", out, version, "run_example_heat",
              "--supplement", str(EX / f"papers/{HEAT}.supplement.pdf"))

    # 2c. verification by a second model (bdc verify), then the derived views of the verified records
    rc = resolve_schema(version, ROOT)
    review = out / "review"
    tasks_file(out / f"{HEAT}.jsonl", review, rc)
    (review / f"{HEAT}.verify.verdicts.template.json").unlink()
    verdicts = example_verdicts(candidates, out, review)
    (review / f"{HEAT}.verify.verdicts.json").write_text(dumps_json(verdicts), encoding="utf-8")
    apply_file(out / f"{HEAT}.jsonl", review / f"{HEAT}.verify.verdicts.json", review, rc, run_id="ver_example_heat",
               manifest=out / f"{HEAT}.manifest.json")
    derive_file(review / f"{HEAT}.verified.jsonl", EX / "derived", rc)

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
    # 5. merged document: existing paper content plus observations, sample/assay links and assets.
    migrate_merged_file(ROOT / "sources/merged_v2/breeding_jsonl_example_v2.json",
                        EX / "migration/merged_v2", version, page_offset=2220, root=ROOT)
    print(f"examples regenerated against {version}")


if __name__ == "__main__":
    main()
