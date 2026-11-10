#!/usr/bin/env python3
"""Build a small, self-contained demo for the simplified research dashboard.

It uses the two checked-in synthetic papers plus a third synthetic paper written here.  The third paper exists
only to exercise the two edges the current contract cannot yet code (gene–population, phenotype–population):
the pipeline stores them as verbatim predicates, and the view shows them with an "未编码" badge.  It also gives
every relation a complete evidence chain (claim -> result -> experiment/method), so the demo shows what the
front end is meant to display.

    python scripts/make_network_demo.py
    # -> out/network_demo/** and dashboard.html
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "skills/pdf2jsonl/scripts", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.make_sample_pdf import build_pdf  # noqa: E402
from scripts import make_network_dashboard  # noqa: E402

DEMO_TEXT = """A synthetic rice triad for phenotype, gene and population relations

Abstract

Grain yield is a key trait in rice breeding.
qGY3.1 was significantly associated with grain yield in the RIL population R1.
OsGY1 controls grain yield in rice.

Results

The OsGY1 allele segregated in the RIL population R1.
A CRISPR/Cas9 knockout of OsGY1 was generated in the R1 background.
The OsGY1 knockout lines showed lower grain yield than the wild type in R1.
\f
qGY3.1 segregated in the RIL population R1 and explained 18.6% of the phenotypic variance.
qGY3.1 was detected with a LOD score of 8.4.
QTL analysis used QTL IciMapping 4.2 with inclusive composite interval mapping.
The R1 population was grown in two environments and grain yield was measured at maturity.
Grain yield was measured in the RIL population R1 across two environments.
Genotyping was performed with 1,536 SNP markers.
"""

DEMO_CANDIDATES = {
    "extraction": {
        "method": "model",
        "model": "example-agent",
        "backend": "agent",
        "notes": "Synthetic demo for the research dashboard. The gene-population and phenotype-population "
                 "predicates have no vocabulary code in 3.8.0 and are intentionally shown as verbatim "
                 "predicates.",
    },
    "document": {
        "common.source_title": "A synthetic rice triad for phenotype, gene and population relations",
        "common.source_doi": "10.0000/synthetic.2026.003",
        "common.source_year": 2026,
        "common.source_authors": ["Synthetic Author E"],
        "common.source_language": "en",
        "common.crop_name": "rice",
    },
    "candidates": [
        # ------------------------------------------------------------------ relations
        {
            "record_kind": "claim", "ref": "qtl_trait",
            "fields": {
                "agent.finding_text": "qGY3.1 was significantly associated with grain yield in the RIL population R1.",
                "common.qtl_names": ["qGY3.1"], "common.trait_names": ["grain yield"],
                "common.population_name": "R1", "common.population_type": "RIL",
                "agent.lod_score": 8.4, "agent.pve_percent": 18.6,
                "agent.effect_estimate": 3.2, "agent.effect_unit": "g/plant", "agent.effect_direction": "increase",
                "transform.subject_mention": "qGY3.1",
                "transform.predicate_mention": "was significantly associated with",
                "transform.object_mention": "grain yield",
            },
            "evidence": {"page": 1, "section": "Abstract",
                         "quote": "qGY3.1 was significantly associated with grain yield in the RIL population R1."},
            "links": {"evidence": ["a_qtl"]},
        },
        {
            "record_kind": "claim", "ref": "gene_trait",
            "fields": {
                "agent.finding_text": "OsGY1 controls grain yield in rice.",
                "common.gene_names": ["OsGY1"], "common.trait_names": ["grain yield"],
                "common.population_name": "R1",
                "agent.validation_methods": ["CRISPR/Cas9 knockout"],
                "transform.subject_mention": "OsGY1", "transform.predicate_mention": "controls",
                "transform.object_mention": "grain yield",
            },
            "evidence": {"page": 1, "section": "Abstract", "quote": "OsGY1 controls grain yield in rice."},
            "links": {"evidence": ["o_gene"]},
        },
        {
            "record_kind": "claim", "ref": "qtl_pop",
            "fields": {
                "agent.finding_text": "qGY3.1 segregated in the RIL population R1.",
                "common.qtl_names": ["qGY3.1"], "common.population_name": "R1",
                "common.population_type": "RIL", "common.population_size": 180,
                "common.trait_names": ["grain yield"], "agent.pve_percent": 18.6,
                "transform.subject_mention": "qGY3.1", "transform.predicate_mention": "segregated in",
                "transform.object_mention": "R1",
            },
            "evidence": {"page": 2, "section": "Results",
                         "quote": "qGY3.1 segregated in the RIL population R1 and explained 18.6% of the phenotypic variance."},
            "links": {"evidence": ["o_seg"]},
        },
        {
            "record_kind": "claim", "ref": "gene_pop",
            "fields": {
                "agent.finding_text": "The OsGY1 allele segregated in the RIL population R1.",
                "common.gene_names": ["OsGY1"], "common.population_name": "R1",
                "common.population_type": "RIL",
                "transform.subject_mention": "OsGY1", "transform.predicate_mention": "segregated in",
                "transform.object_mention": "R1",
            },
            "evidence": {"page": 1, "section": "Results",
                         "quote": "The OsGY1 allele segregated in the RIL population R1."},
            "links": {"evidence": ["o_seg_gene"]},
        },
        {
            "record_kind": "observation", "ref": "trait_pop",
            "fields": {
                "agent.finding_text": "Grain yield was measured in the RIL population R1 across two environments.",
                "common.trait_names": ["grain yield"], "common.population_name": "R1",
                "common.population_type": "RIL", "common.population_size": 180,
                "agent.environment_count": 2,
                "transform.subject_mention": "grain yield", "transform.predicate_mention": "was measured in",
                "transform.object_mention": "R1",
            },
            "evidence": {"page": 2, "section": "Results",
                         "quote": "Grain yield was measured in the RIL population R1 across two environments."},
            "links": {"evidence": ["o_trial"]},
        },
        # ------------------------------------------------------------------ evidence records
        {
            "record_kind": "analysis_result", "ref": "a_qtl",
            "fields": {"common.qtl_names": ["qGY3.1"], "common.population_name": "R1",
                       "agent.lod_score": 8.4, "agent.pve_percent": 18.6},
            "evidence": {"page": 2, "section": "Results",
                         "quote": "qGY3.1 was detected with a LOD score of 8.4."},
            "links": {"method": ["m_icim"]},
        },
        {
            "record_kind": "observation", "ref": "o_seg",
            "fields": {"common.qtl_names": ["qGY3.1"], "common.population_name": "R1",
                       "agent.actual_observation": "qGY3.1 segregated in the RIL population R1"},
            "evidence": {"page": 2, "section": "Results",
                         "quote": "qGY3.1 segregated in the RIL population R1 and explained 18.6% of the phenotypic variance."},
            "links": {"method": ["m_geno"]},
        },
        {
            "record_kind": "observation", "ref": "o_trial",
            "fields": {"common.trait_names": ["grain yield"], "common.population_name": "R1",
                       "agent.actual_observation": "grain yield was measured in R1 across two environments"},
            "evidence": {"page": 2, "section": "Results",
                         "quote": "Grain yield was measured in the RIL population R1 across two environments."},
            "links": {"method": ["m_pop"]},
        },
        {
            "record_kind": "observation", "ref": "o_seg_gene",
            "fields": {"common.gene_names": ["OsGY1"], "common.population_name": "R1",
                       "agent.actual_observation": "the OsGY1 allele segregated in R1"},
            "evidence": {"page": 1, "section": "Results",
                         "quote": "The OsGY1 allele segregated in the RIL population R1."},
            "links": {"method": ["m_geno"]},
        },
        {
            "record_kind": "observation", "ref": "o_gene",
            "fields": {"common.gene_names": ["OsGY1"], "common.population_name": "R1",
                       "common.trait_names": ["grain yield"],
                       "agent.actual_observation": "OsGY1 knockout lines showed lower grain yield than the wild type"},
            "evidence": {"page": 1, "section": "Results",
                         "quote": "The OsGY1 knockout lines showed lower grain yield than the wild type in R1."},
            "links": {"method": ["m_crispr"]},
        },
        # ------------------------------------------------------------------ methods
        {
            "record_kind": "method", "ref": "m_icim",
            "fields": {"skills.method_name": "inclusive composite interval mapping",
                       "skills.software_name": "QTL IciMapping", "skills.software_version": "4.2"},
            "evidence": {"page": 2, "section": "Results",
                         "quote": "QTL analysis used QTL IciMapping 4.2 with inclusive composite interval mapping."},
        },
        {
            "record_kind": "method", "ref": "m_geno",
            "fields": {"skills.method_name": "SNP genotyping"},
            "evidence": {"page": 2, "section": "Results",
                         "quote": "Genotyping was performed with 1,536 SNP markers."},
        },
        {
            "record_kind": "method", "ref": "m_pop",
            "fields": {"skills.method_name": "field trial"},
            "evidence": {"page": 2, "section": "Results",
                         "quote": "The R1 population was grown in two environments and grain yield was measured at maturity."},
        },
        {
            "record_kind": "method", "ref": "m_crispr",
            "fields": {"skills.method_name": "CRISPR/Cas9"},
            "evidence": {"page": 1, "section": "Results",
                         "quote": "A CRISPR/Cas9 knockout of OsGY1 was generated in the R1 background."},
        },
    ],
}


DEMO_REPLICATION_TEXT = DEMO_TEXT.replace(
    "A synthetic rice triad for phenotype, gene and population relations",
    "A replication of the synthetic rice triad for phenotype, gene and population relations",
)
DEMO_REPLICATION_CANDIDATES = json.loads(json.dumps(DEMO_CANDIDATES))
DEMO_REPLICATION_CANDIDATES["extraction"]["notes"] = (
    "A second synthetic paper reporting the same triad relations; used to demonstrate cross-paper deduplication."
)
DEMO_REPLICATION_CANDIDATES["document"].update({
    "common.source_title": "A replication of the synthetic rice triad for phenotype, gene and population relations",
    "common.source_doi": "10.0000/synthetic.2026.004",
    "common.source_authors": ["Synthetic Author F"],
})


def _run(args: list[str]) -> None:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT / "skills/pdf2jsonl/scripts")])}
    result = subprocess.run([sys.executable, "-m", "pdf2jsonl_skill.cli", *args],
                            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    print(result.stdout.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "out/network_demo",
                        help="run directory (default: out/network_demo)")
    parser.add_argument("--dashboard", type=Path, default=ROOT / "dashboard.html",
                        help="HTML output (default: dashboard.html)")
    parser.add_argument("--keep", action="store_true", help="do not clear an existing run directory")
    args = parser.parse_args(argv)

    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    if out_dir.exists() and not args.keep:
        if out_dir.resolve() == ROOT.resolve():
            raise SystemExit("refusing to clear the repository root; pass --keep or another --out-dir")
        shutil.rmtree(out_dir)
    src = out_dir / "src"
    src.mkdir(parents=True, exist_ok=True)

    (src / "synthetic_rice_triad.txt").write_text(DEMO_TEXT, encoding="ascii")
    (src / "synthetic_rice_triad.pdf").write_bytes(build_pdf([p for p in DEMO_TEXT.split("\f") if p.strip()]))
    (src / "synthetic_rice_triad.candidates.json").write_text(
        json.dumps(DEMO_CANDIDATES, ensure_ascii=False, indent=1), encoding="utf-8")
    (src / "synthetic_rice_replication.txt").write_text(DEMO_REPLICATION_TEXT, encoding="ascii")
    (src / "synthetic_rice_replication.pdf").write_bytes(
        build_pdf([p for p in DEMO_REPLICATION_TEXT.split("\f") if p.strip()]))
    (src / "synthetic_rice_replication.candidates.json").write_text(
        json.dumps(DEMO_REPLICATION_CANDIDATES, ensure_ascii=False, indent=1), encoding="utf-8")

    common = ["--profile", "pdf_extraction", "--schema-version", "latest", "--out-dir", str(out_dir)]
    _run(["run", str(ROOT / "examples/papers/synthetic_rice_qtl.pdf"), *common, "--backend", "candidates",
          "--candidates", str(ROOT / "examples/papers/synthetic_rice_qtl.candidates.json")])
    _run(["run", str(ROOT / "examples/papers/synthetic_rice_heat.pdf"), *common, "--backend", "candidates",
          "--candidates", str(ROOT / "examples/papers/synthetic_rice_heat.candidates.json"),
          "--supplement", str(ROOT / "examples/papers/synthetic_rice_heat.supplement.pdf")])
    _run(["run", str(src / "synthetic_rice_triad.pdf"), *common, "--backend", "candidates",
          "--candidates", str(src / "synthetic_rice_triad.candidates.json")])
    _run(["run", str(src / "synthetic_rice_replication.pdf"), *common, "--backend", "candidates",
          "--candidates", str(src / "synthetic_rice_replication.candidates.json")])

    destination, view = make_network_dashboard.build(
        ROOT, args.dashboard, scan=["out/network_demo", "examples/papers"],
        json_out=out_dir / "research_view.json")
    s = view["summary"]
    print(f"\n{destination}: {s['papers']} papers, {s['nodes']} nodes, {s['edges']} relations, "
          f"{s['evidence']} evidence items, {s['hidden']} hidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
