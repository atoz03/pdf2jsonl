#!/usr/bin/env python3
"""One-command reproduction of the rice stress dashboard.

Inputs are external by design: the RBL1 PDF and the 13-paper rice stress directory are not redistributed.
Everything else (contract, curated panel CSV, scripts, tests) is in the repository.

    python scripts/reproduce_dashboard.py \
      --rbl1-pdf /path/to/qt2321j386.pdf \
      --rice-pdf-dir /path/to/水稻-抗逆抗病性状 \
      --out out/reproduce

It builds the RBL1 case, the real-paper panel, and dashboard.html, then checks the same invariants the tests use.
The final JSON records git commit/dirty state, input hashes, counts and checks so another person can compare.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from breeding_contract.rbl1_case import EXPECTED_PDF_SHA256, build_case  # noqa: E402
from breeding_contract.util import sha256_file  # noqa: E402
from scripts.build_rice_stress_panel import build as build_panel  # noqa: E402
from scripts.make_rbl1_dashboard import build as build_dashboard  # noqa: E402


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def _require(path: Path, label: str) -> Path:
    if not path.exists():
        raise SystemExit(f"missing {label}: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rbl1-pdf", required=True, type=Path)
    ap.add_argument("--rice-pdf-dir", required=True, type=Path)
    ap.add_argument("--primers", default="examples/rbl1/primers.csv", type=Path)
    ap.add_argument("--panel-csv", default="examples/rice_stress_panel/panel.csv", type=Path)
    ap.add_argument("--out", default="out/reproduce", type=Path)
    args = ap.parse_args(argv)

    rbl1_pdf = _require(args.rbl1_pdf, "RBL1 PDF")
    rice_dir = _require(args.rice_pdf_dir, "rice stress PDF directory")
    primers = _require(args.primers, "primer CSV")
    panel_csv = _require(args.panel_csv, "panel CSV")
    out = args.out if args.out.is_absolute() else ROOT / args.out
    case_dir = out / "rbl1_case"
    panel_dir = out / "rice_stress_panel"
    dashboard = out / "dashboard.html"

    case = build_case(rbl1_pdf, primers, case_dir)
    bad = {k: v for k, v in case["checks"].items() if v is not True}
    if bad:
        raise SystemExit("RBL1 checks failed: " + json.dumps(bad, ensure_ascii=False))
    if case["paper"]["pdf_sha256"] != EXPECTED_PDF_SHA256:
        raise SystemExit("RBL1 PDF hash does not match the expected case PDF")

    aggregate = build_panel(panel_csv, rice_dir, panel_dir, case_dir)
    expected = {"papers": 14, "relations": 15, "associations": 16, "evidence": 49,
                "conflicts": 0, "confidence": {"B": 15}}
    if aggregate["counts"] != expected:
        raise SystemExit(f"panel aggregate differs: {aggregate['counts']} != {expected}")

    path, payload = build_dashboard(case_dir, dashboard, panel_dir / "records.jsonl")
    html = path.read_text(encoding="utf-8")
    for needle in ("多文聚合", "论文—性状关系图", "为什么能指向同一个性状", "paper-graph"):
        if needle not in html:
            raise SystemExit(f"dashboard is missing {needle!r}")

    report = {
        "reproduction_format": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git": {"commit": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain")),
                "branch": _git("branch", "--show-current")},
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
        "contract": case["contract"],
        "inputs": {
            "rbl1_pdf": {"path": str(rbl1_pdf), "sha256": sha256_file(rbl1_pdf),
                         "expected_sha256": EXPECTED_PDF_SHA256},
            "primers": {"path": str(primers), "sha256": sha256_file(primers)},
            "panel_csv": {"path": str(panel_csv), "sha256": sha256_file(panel_csv)},
            "rice_pdf_dir": {"path": str(rice_dir), "pdf_count": len(list(rice_dir.glob("*.pdf")))},
        },
        "outputs": {"rbl1_case": str(case_dir), "panel": str(panel_dir), "dashboard": str(dashboard)},
        "checks": {"rbl1": case["checks"], "aggregate_counts": aggregate["counts"],
                   "dashboard_contains": ["多文聚合", "论文—性状关系图", "为什么能指向同一个性状", "paper-graph"]},
        "commands": {
            "rbl1": "python -m breeding_contract.cli rbl1 --pdf <rbl1.pdf> --primers examples/rbl1/primers.csv --out out/rbl1_case_final",
            "panel": "python scripts/build_rice_stress_panel.py --panel-csv examples/rice_stress_panel/panel.csv --pdf-dir <rice-dir> --case-dir out/rbl1_case_final --out out/rice_stress_panel",
            "dashboard": "python scripts/make_network_dashboard.py --rbl1-case out/rbl1_case_final --rbl1-aggregate out/rice_stress_panel/records.jsonl --out dashboard.html",
        },
    }
    (out / "reproduction.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    print(json.dumps({"dashboard": str(dashboard), "counts": aggregate["counts"],
                      "rbl1_checks": len(case["checks"]), "report": str(out / "reproduction.json")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
