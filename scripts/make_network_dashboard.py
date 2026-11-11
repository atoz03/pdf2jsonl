#!/usr/bin/env python3
"""Write the simplified phenotype–gene–population dashboard.

The page is a *view*: it reads the latest run of each paper through ``scripts/make_dashboard.build_data`` and
filters the derived statements to the three layers.  No record, contract version or pipeline output changes.

    python scripts/make_network_dashboard.py --out dashboard.html
    python scripts/make_network_dashboard.py --scan out/network_demo --scan examples/papers
    python scripts/make_network_dashboard.py --rbl1-case out/rbl1_case_final --out dashboard.html

``--scan`` is repeatable and limits the scan to those subdirectories, which is what the demo uses to keep the
snapshot small.  Without it the whole repository is scanned, exactly like ``make dashboard``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import make_dashboard, network_view  # noqa: E402


def _payload(data: dict) -> str:
    """JSON safe to embed in a <script> element."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return (text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render(data: dict, *, papers_link: str = "") -> str:
    template = (ROOT / "site/pages/network.html").read_text(encoding="utf-8")
    css = (ROOT / "site/kit/kit.css").read_text(encoding="utf-8")
    js = (ROOT / "site/pages/network.js").read_text(encoding="utf-8")
    version = str(data.get("version") or "dev")
    values = {
        "/*__KIT_CSS__*/": css,
        "/*__NETWORK_JS__*/": js,
        "<!--__NETWORK_DATA__-->": _payload(data),
        "<!--__VERSION__-->": version,
        "<!--__PAPERS_LINK__-->": papers_link,
    }
    for key, value in values.items():
        if template.count(key) != 1:
            raise ValueError(f"site/pages/network.html must contain {key!r} exactly once")
        template = template.replace(key, value)
    return template


def build(root: Path = ROOT, out: Path | None = None, scan=None,
          json_out: Path | None = None) -> tuple[Path, dict]:
    root = root.resolve()
    data = make_dashboard.build_data(root, scan=scan)
    view = network_view.build_network(data)
    destination = out or root / "dashboard.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    papers = destination.parent / "papers.html"
    papers_link = ('<a href="papers.html">完整论文看板</a>' if papers.is_file() else "")
    destination.write_text(render(view, papers_link=papers_link), encoding="utf-8")
    if json_out is not None:
        json_out = json_out if json_out.is_absolute() else root / json_out
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(view, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    return destination, view


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository to scan")
    parser.add_argument("--out", type=Path, help="HTML output; defaults to dashboard.html in the repository root")
    parser.add_argument("--scan", action="append", metavar="DIR",
                        help="only scan this subdirectory (repeatable; relative to --root)")
    parser.add_argument("--json-out", type=Path,
                        help="also write the derived per-paper/aggregate JSON (for another front end)")
    parser.add_argument("--rbl1-case", type=Path,
                        help="render the RBL1 association/sequence dashboard from this case directory "
                             "(instead of scanning paper runs)")
    parser.add_argument("--rbl1-aggregate", type=Path,
                        help="JSONL with additional association records for the RBL1 multi-paper aggregate view")
    args = parser.parse_args(argv)
    if args.rbl1_case:
        from scripts.make_rbl1_dashboard import build as build_rbl1
        destination, payload = build_rbl1(args.rbl1_case, args.out or ROOT / "dashboard.html",
                                          args.rbl1_aggregate)
        counts = payload["report"]["counts"]
        agg = payload["aggregate"]["counts"]
        print(f"{destination}: {counts['associations']} associations, {counts['sequences']} sequences, "
              f"{counts['field_evidence']} field evidence, {agg['relations']} aggregate relations, "
              f"{agg['conflicts']} conflicts")
        return 0
    destination, view = build(args.root, args.out, args.scan, args.json_out)
    s = view["summary"]
    print(f"{destination}: {s['papers']} papers, {s['nodes']} nodes, {s['edges']} relations, "
          f"{s['evidence']} evidence items, {s['hidden']} hidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
