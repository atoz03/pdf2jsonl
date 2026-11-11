#!/usr/bin/env python3
"""Render a self-contained dashboard.html for the RBL1 association/sequence case.

    python scripts/make_rbl1_dashboard.py --case-dir out/rbl1_case_final --out dashboard.html

This is the RBL1 mode of the project dashboard entry point:
``python scripts/make_network_dashboard.py --rbl1-case out/rbl1_case_final --out dashboard.html``.
The existing network view remains the default; this mode is separate because it shows record kinds
(association, sequence, field evidence) that the three-layer network intentionally hides.

The page is dependency-free (vanilla HTML/CSS/JS) and reads the generated case files, not the source PDF.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from breeding_contract.association_aggregate import aggregate_associations


def load_case(case_dir: Path, aggregate_records: Path | None = None) -> dict:
    def read_jsonl(name: str) -> list[dict]:
        path = case_dir / name
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def read_csv(name: str) -> list[dict]:
        with (case_dir / name).open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))

    report = json.loads((case_dir / "rbl1_case.json").read_text(encoding="utf-8"))
    records = read_jsonl("records.jsonl")
    evidence = read_csv("field_evidence.csv")
    kinds = {r["common"]["record_id"]: r["common"]["record_kind"] for r in records}
    # Association/PDF evidence first; sequence/attachment evidence second.
    evidence.sort(key=lambda e: (0 if kinds.get(e["record_id"]) == "association" else 1, e["record_id"], e["field"]))
    aggregate_source = records
    if aggregate_records:
        aggregate_source = [json.loads(line) for line in Path(aggregate_records).read_text(encoding="utf-8").splitlines()
                            if line.strip()]
    aggregate = aggregate_associations(aggregate_source)
    has_synthetic = any("Synthetic" in ((c.get("paper") or {}).get("title") or "")
                        for r in aggregate["relations"] for c in r["contexts"])
    if aggregate_records:
        aggregate_note = ("含合成多文演示（独立重复、冲突、A/B/C 置信）；合成论文在标题中明确标注，不作为真实结论。"
                          if has_synthetic else
                          "真实论文面板：13 篇水稻抗逆/抗病论文的 page-1 curated association；用于聚合与关系图测试，"
                          "不是穷尽抽取。")
    else:
        aggregate_note = "当前仅 RBL1 单篇案例；多文聚合需要额外的论文记录。"
    sources = read_csv("source_files.csv")
    seen_sources = {s.get("file_id") for s in sources}
    for relation in aggregate["relations"]:
        for context in relation["contexts"]:
            paper = context.get("paper") or {}
            pid = paper.get("id")
            if pid and pid not in seen_sources:
                seen_sources.add(pid)
                sources.append({"file_id": pid, "role": "paper", "status": "curated", "format": "PDF",
                                "sha256": "", "url": ("https://doi.org/" + paper["doi"]) if paper.get("doi") else "",
                                "name": paper.get("title") or pid, "license": "",
                                "license_status": "not_verified"})
    return {
        "report": report,
        "records": records,
        "all_records": list({r["common"]["record_id"]: r for r in records + aggregate_source}.values()),
        "sources": sources,
        "evidence": evidence,
        "aliases": read_csv("aliases.csv"),
        "triples": read_jsonl("triples.jsonl"),
        "aggregate": aggregate,
        "aggregate_note": aggregate_note,
        "refs": {a["association_id"]: a["ref"] for a in report.get("associations", [])},
    }


def render(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = "RBL1 · 关联事件与引物证据"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  --ink:#edf5f7; --ink-2:#c3d1d9; --muted:#8c9ca8; --line:#24313b; --line-soft:#1b252e;
  --blue:#20c997; --blue-deep:#9bf2d8; --blue-soft:#102b25;
  --orange:#e8a35e; --orange-soft:#2a2118;
  --green:#38dfae; --green-soft:#112b23;
  --bg:#0a0f14; --card:#111820; --card-2:#0d141a;
  --shadow:0 10px 30px rgba(0,0,0,.3); color-scheme:dark;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font-family:"Microsoft YaHei UI","Microsoft YaHei","PingFang SC","Noto Sans SC",Arial,sans-serif;
  font-size:14px; line-height:1.6; }}
a {{ color:#62e0bc; }}
.wrap {{ width:min(1320px, calc(100% - 56px)); margin:0 auto; position:relative; z-index:1; }}
.eyebrow {{ font-size:12px; letter-spacing:.16em; text-transform:uppercase; opacity:.78; }}
.source-pills {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }}
.pill {{ display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px;
  font-size:12px; text-decoration:none; }}
.pill:hover {{ background:#eaf1fb; }}
.topbar {{ position:sticky; top:0; z-index:50; background:rgba(255,255,255,.94); backdrop-filter:blur(12px);
  border-bottom:1px solid var(--line); }}.topbar .wrap {{ display:flex; align-items:center; gap:18px; height:58px; }}
.brand {{ display:inline-flex; align-items:center; gap:9px; color:var(--ink); text-decoration:none; }}
.brand .mark {{ width:26px; height:26px; border-radius:8px; background:var(--blue); color:#041b14; display:grid;
  place-items:center; font-weight:700; font-size:12px; }}
.brand b {{ display:block; line-height:1.1; font-size:15px; }}
.brand small {{ display:block; color:var(--muted); font-size:10px; }}
.topnav {{ display:flex; gap:4px; margin-left:8px; }}
.topnav a {{ color:#40526b; font-size:13px; padding:6px 10px; border-radius:8px; text-decoration:none; }}
.topnav a:hover, .topnav a.active {{ color:var(--blue-deep); background:var(--blue-soft); }}
.topright {{ margin-left:auto; display:flex; align-items:center; gap:8px; }}
.ver-pill {{ border:1px solid var(--line); background:#f7faff; color:var(--muted); border-radius:999px;
  padding:3px 9px; font-size:11px; }}
.hero {{ background:#fbfdff; color:var(--ink); padding:26px 0 20px; position:relative; overflow:hidden;
  border-bottom:1px solid var(--line); }}
.hero:after {{ display:none; }}
.hero .eyebrow {{ color:var(--blue); }}
.hero h1 {{ color:var(--blue-deep); font-size:30px; margin:5px 0 6px; }}
.hero p {{ color:var(--muted); max-width:980px; }}
.pill {{ background:#f3f7fd; border:1px solid var(--line); color:#40526b; }}
.pill:hover {{ background:#eaf1fb; }}
main {{ padding:24px 0 40px; }}
.stats {{ display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:12px; margin-top:-2px; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px 12px;
  box-shadow:var(--shadow); }}
.stat .num {{ font-size:28px; font-weight:700; line-height:1.1; color:var(--blue-deep); }}
.stat .label {{ color:var(--muted); font-size:12px; margin-top:2px; }}
.stat.good .num {{ color:var(--green); }}
.tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin:24px 0 16px; }}
.workspace {{ display:grid; grid-template-columns:286px minmax(0,1fr); gap:16px; align-items:start; margin-top:16px; }}
.paper-sidebar {{ position:sticky; top:74px; }}
.paper-list-card {{ background:#fff; border:1px solid var(--line); border-radius:12px; box-shadow:var(--shadow);
  overflow:hidden; }}
.paper-list-head {{ display:flex; justify-content:space-between; align-items:center; padding:11px 12px;
  border-bottom:1px solid var(--line); }}
.paper-list-head b {{ color:var(--blue-deep); font-size:14px; }}
.paper-search {{ width:calc(100% - 20px); margin:10px; border:1px solid var(--line); border-radius:8px;
  padding:7px 9px; font:inherit; font-size:12px; background:#fbfdff; }}
.paper-list {{ max-height:620px; overflow:auto; padding:0 8px 8px; }}
.paper-item {{ width:100%; text-align:left; border:1px solid transparent; background:none; border-radius:9px;
  padding:8px 9px; cursor:pointer; font:inherit; color:var(--ink); display:block; }}
.paper-item:hover {{ background:#f5f8fd; }}
.paper-item.active {{ background:var(--blue-soft); border-color:#d4e2fb; }}
.paper-item .t {{ font-size:12px; font-weight:650; line-height:1.35; display:-webkit-box;
  -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
.paper-item .m {{ color:var(--muted); font-size:10.5px; margin-top:3px; }}
.paper-side-note {{ margin:9px 4px 0; line-height:1.5; }}
.paper-main {{ min-width:0; }}
.paper-head {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 14px;
  box-shadow:var(--shadow); }}
.paper-head h2 {{ margin:0 0 3px; color:var(--blue-deep); font-size:18px; line-height:1.35; }}
.paper-head .meta {{ color:var(--muted); font-size:12px; display:flex; flex-wrap:wrap; gap:6px 12px; }}
.paper-head .badges {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:7px; }}
.empty-inline {{ background:#fff; border:1px dashed var(--line); border-radius:10px; padding:18px; color:var(--muted); }}
.tabs button {{ border:1px solid var(--line); background:#fff; color:#40526b; border-radius:999px;
  padding:7px 14px; cursor:pointer; font:inherit; font-size:13px; }}
.tabs button.active {{ background:var(--blue); border-color:var(--blue); color:#041b14; font-weight:700; box-shadow:0 3px 10px rgba(32,201,151,.22); }}
.tab-panel {{ display:none; }}
.tab-panel.active {{ display:block; }}
.section-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin:4px 0 12px; }}
.section-head h2 {{ margin:0; font-size:20px; color:var(--blue-deep); }}
.section-head p {{ margin:0; color:var(--muted); font-size:13px; }}
.assoc-grid {{ display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:14px; }}
.assoc-card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px;
  box-shadow:var(--shadow); display:flex; flex-direction:column; gap:10px; }}
.assoc-top {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
.ref {{ font-weight:700; color:var(--blue-deep); letter-spacing:.02em; font-size:14px; }}
.badge {{ display:inline-flex; align-items:center; border-radius:999px; padding:2px 8px; font-size:11px;
  border:1px solid transparent; white-space:nowrap; }}
.badge.kind {{ background:var(--blue-soft); color:var(--blue-deep); border-color:#d4e2fb; }}
.badge.review {{ background:var(--orange-soft); color:var(--orange); border-color:#f5dcc7; }}
.badge.ok {{ background:var(--green-soft); color:var(--green); border-color:#cfe9d9; }}
.assoc-card h3 {{ margin:2px 0 0; font-size:17px; line-height:1.35; color:var(--ink); }}
.context {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.context div {{ background:#f7faff; border:1px solid #e6edf8; border-radius:8px; padding:7px 9px; min-width:0; }}
.context small {{ display:block; color:var(--muted); font-size:11px; }}
.context b {{ display:block; font-size:13px; overflow-wrap:anywhere; }}
.missing {{ display:flex; flex-wrap:wrap; gap:5px; }}
.missing span {{ background:#fff8ef; color:#8a5a22; border:1px solid #f1dfc9; border-radius:6px;
  padding:3px 6px; font-size:11px; }}
details {{ border-top:1px dashed var(--line); padding-top:8px; }}
summary {{ cursor:pointer; color:var(--blue); font-weight:600; font-size:13px; }}
.evidence-list {{ display:flex; flex-direction:column; gap:8px; margin-top:8px; }}
.evidence-row {{ background:#f8faff; border-left:3px solid #9bb8e6; padding:7px 9px; border-radius:0 6px 6px 0; }}
.evidence-row code {{ color:var(--blue-deep); font-size:11px; }}
.evidence-row .locator {{ color:var(--muted); font-size:11px; margin-left:6px; }}
.evidence-row q {{ display:block; margin-top:2px; color:#40526b; font-size:12px; quotes:"“" "”"; }}
.table-card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow);
  overflow:hidden; }}
.table-tools {{ display:flex; justify-content:space-between; gap:12px; align-items:center; padding:12px 14px;
  border-bottom:1px solid var(--line); background:#fbfdff; }}
.table-tools input {{ border:1px solid var(--line); border-radius:8px; padding:7px 10px; font:inherit;
  min-width:260px; background:#fff; }}
.table-wrap {{ overflow:auto; max-height:620px; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th {{ position:sticky; top:0; z-index:1; background:#f2f6fc; color:#40526b; text-align:left;
  font-weight:600; padding:9px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }}
td {{ padding:9px 12px; border-bottom:1px solid #edf2f9; vertical-align:top; }}
tr:hover td {{ background:#fafcff; }}
code.seq {{ font-family:Consolas,"Cascadia Mono",monospace; font-size:12px; letter-spacing:.2px;
  overflow-wrap:anywhere; color:#173b6d; }}
.copy {{ border:1px solid #cfe0f8; color:var(--blue); background:#f4f8ff; border-radius:6px;
  padding:2px 7px; font:inherit; font-size:11px; cursor:pointer; margin-left:6px; }}
.copy:hover {{ background:#e8f1ff; }}
.small {{ color:var(--muted); font-size:11px; }}
.mono {{ font-family:Consolas,"Cascadia Mono",monospace; font-size:11px; overflow-wrap:anywhere; }}
.alias-box {{ margin-top:14px; background:var(--orange-soft); border:1px solid #f0d8c2; border-radius:12px;
  padding:12px 14px; display:flex; gap:12px; align-items:flex-start; }}
.alias-box strong {{ color:var(--orange); white-space:nowrap; }}
.agg-summary {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-bottom:12px; }}
.agg-summary .item {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:10px 12px;
  box-shadow:var(--shadow); }}
.agg-summary .n {{ font-size:22px; font-weight:700; color:var(--blue-deep); }}
.agg-summary .l {{ color:var(--muted); font-size:12px; }}
.agg-list {{ display:flex; flex-direction:column; gap:12px; }}
.agg-card {{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px;
  box-shadow:var(--shadow); }}
.agg-card h3 {{ margin:4px 0 4px; font-size:17px; }}
.agg-meta {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
.agg-basis {{ color:var(--muted); font-size:12px; margin:6px 0 8px; }}
.agg-basis span {{ display:inline-block; background:#f7faff; border:1px solid #e6edf8; border-radius:999px;
  padding:1px 7px; margin:2px 4px 2px 0; }}
.conflict {{ background:#fff3f0; border:1px solid #f1cdc4; color:#9a3f2b; border-radius:8px; padding:7px 9px;
  font-size:12px; margin:6px 0; }}
.confidence {{ font-weight:700; }}
.confidence.A {{ background:var(--green-soft); color:var(--green); border-color:#cfe9d9; }}
.confidence.B {{ background:var(--blue-soft); color:var(--blue-deep); border-color:#d4e2fb; }}
.confidence.C {{ background:var(--orange-soft); color:var(--orange); border-color:#f5dcc7; }}
.agg-card table {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }}
.agg-card th, .agg-card td {{ text-align:left; padding:6px 8px; border-bottom:1px solid #edf2f9; vertical-align:top; }}
.graph-card {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 14px;
  box-shadow:var(--shadow); margin-bottom:12px; }}
.graph-head {{ display:flex; justify-content:space-between; gap:12px; align-items:baseline; margin-bottom:6px; }}
.graph-head b {{ color:var(--blue-deep); font-size:14px; }}
.graph-head span {{ text-align:right; max-width:720px; }}
#paper-graph {{ width:100%; height:auto; min-height:300px; display:block; }}
.graph-line {{ stroke-width:1.3; opacity:.38; }}
.graph-line:hover {{ stroke:var(--orange) !important; opacity:1; stroke-width:2.5; }}
.graph-paper {{ fill:#2f5fa8; }}
.graph-trait {{ fill:#c4641a; }}
.graph-label {{ font-size:11px; fill:#40526b; }}
.graph-label.paper {{ text-anchor:end; }}
.graph-label.trait {{ fill:#8a4b13; }}
.graph-year {{ font-size:9px; fill:#8a99ad; text-anchor:end; }}
.graph-legend {{ display:flex; gap:16px; color:var(--muted); font-size:11px; margin-top:4px; }}
.graph-legend i {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:4px; }}
.checks {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:8px; }}
.check {{ background:#fff; border:1px solid var(--line); border-radius:9px; padding:8px 10px;
  display:flex; gap:8px; align-items:center; font-size:12px; }}
.check .dot {{ width:8px; height:8px; border-radius:50%; background:var(--green); box-shadow:0 0 0 3px var(--green-soft); }}
.footer {{ color:var(--muted); font-size:12px; padding:0 0 28px; }}
.btn {{ display:inline-flex; align-items:center; gap:6px; border:1px solid var(--line); background:#fff;
  color:var(--ink); border-radius:9px; padding:8px 12px; font:inherit; font-size:13px; cursor:pointer; }}
.btn:hover {{ background:#f5f8fd; }}
.btn.primary {{ background:var(--blue); border-color:var(--blue); color:#fff; margin-top:14px; }}
.btn.primary:hover {{ background:var(--blue-deep); }}
.overlay {{ position:fixed; inset:0; z-index:100; background:rgba(15,27,45,.55); padding:22px;
  overflow:auto; }}
.overlay[hidden] {{ display:none; }}
.overlay-shell {{ max-width:1400px; margin:0 auto; background:var(--bg); border-radius:16px;
  box-shadow:0 24px 80px rgba(10,25,50,.35); overflow:hidden; }}
.overlay-head {{ position:sticky; top:0; z-index:3; background:#fff; border-bottom:1px solid var(--line);
  padding:16px 20px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }}
.overlay-head h2 {{ margin:2px 0 3px; color:var(--blue-deep); font-size:22px; }}
.overlay-head p {{ margin:0; }}
.overlay-close {{ border:1px solid var(--line); background:#f7faff; color:var(--ink-2); width:34px; height:34px;
  border-radius:9px; font-size:22px; line-height:1; cursor:pointer; }}
.overlay-close:hover {{ background:var(--blue-soft); color:var(--blue-deep); }}
.overlay-body {{ padding:16px 20px 24px; }}
.trait-head {{ margin-top:18px; }}
.trait-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
.trait-card {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 14px;
  box-shadow:var(--shadow); }}
.trait-card h4 {{ margin:0 0 2px; color:var(--orange); font-size:15px; }}
.trait-card .why {{ color:#40526b; font-size:12px; margin:5px 0 8px; }}
.trait-card table {{ width:100%; border-collapse:collapse; font-size:11.5px; }}
.trait-card th, .trait-card td {{ text-align:left; padding:5px 6px; border-bottom:1px solid #edf2f9; vertical-align:top; }}
.trait-card th {{ color:var(--muted); font-weight:600; }}
@media (max-width: 900px) {{
  .trait-grid {{ grid-template-columns:1fr; }}
  .overlay {{ padding:8px; }}
}}
.note {{ background:#f7faff; border:1px solid var(--line); border-radius:10px; padding:10px 12px; color:var(--muted);
  font-size:12px; margin-top:12px; }}
@media (max-width: 980px) {{
  .workspace {{ grid-template-columns:1fr; }}
  .paper-sidebar {{ position:static; }}
  .paper-list {{ max-height:240px; }}
}}
@media (max-width: 1100px) {{
  .stats {{ grid-template-columns:repeat(3, minmax(0,1fr)); }}
  .assoc-grid {{ grid-template-columns:1fr 1fr; }}
  .checks {{ grid-template-columns:1fr 1fr; }}
  .agg-summary {{ grid-template-columns:1fr 1fr; }}
}}
@media (max-width: 740px) {{
  .wrap {{ width:calc(100% - 28px); }}
  .hero h1 {{ font-size:24px; }}
  .stats, .assoc-grid, .checks, .agg-summary {{ grid-template-columns:1fr; }}
  .context {{ grid-template-columns:1fr; }}
  .table-tools {{ flex-direction:column; align-items:stretch; }}
  .table-tools input {{ min-width:0; width:100%; }}
}}
/* dark theme overrides */
body {{ background:var(--bg); color:var(--ink); }}
.topbar {{ background:rgba(14,19,26,.94); border-bottom-color:var(--line); }}
.brand {{ color:var(--ink); }}
.brand small {{ color:var(--muted); }}
.topnav a {{ color:var(--ink-2); }}
.topnav a:hover, .topnav a.active {{ color:#a9f3dc; background:var(--blue-soft); }}
.ver-pill {{ background:#101c18; color:#9cc9ba; border-color:#234a3d; }}
.hero {{ background:#0d151a; border-bottom-color:var(--line); }}
.hero h1 {{ color:var(--ink); }}
.hero p {{ color:var(--muted); }}
.eyebrow {{ color:#35d6a6; }}
.pill {{ background:#101c1a; border-color:#223a33; color:#bfe1d6; }}
.pill:hover {{ background:#163128; }}
.paper-list-card, .paper-head, .tabs button, .empty-inline, .agg-summary .item, .agg-card,
.graph-card, .check, .btn, .overlay-head, .trait-card {{ background:var(--card); }}
.paper-search, .table-tools input {{ background:#0f151e; color:var(--ink); }}
.paper-item:hover {{ background:#1a2432; }}
.paper-item.active {{ background:#12352b; border-color:#235c4b; }}
.tabs button {{ color:var(--ink-2); }}
.context div, .evidence-row, .agg-basis span {{ background:#0d1716; border-color:#20322c; }}
.evidence-row q, .trait-card .why {{ color:var(--ink-2); }}
.missing span {{ background:#2b2117; color:#f0b87c; border-color:#4a3420; }}
.badge.kind {{ border-color:#235c4b; }}
.badge.review {{ border-color:#5a4026; }}
.badge.ok {{ border-color:#25624d; }}
.table-tools {{ background:#0e1719; }}
th {{ background:#101c1c; color:#a7c4bc; }}
td {{ border-bottom-color:var(--line-soft); }}
tr:hover td {{ background:#101f1b; }}
code.seq {{ color:#8ff0d0; }}
.copy {{ border-color:#235b4b; background:#10241f; color:#8ff0d0; }}
.copy:hover {{ background:#173a2f; }}
.alias-box {{ border-color:#4a3520; }}
.agg-basis span {{ border-color:#243044; }}
.conflict {{ background:#2a1715; border-color:#5a2d25; color:#f0a08b; }}
.confidence.A {{ border-color:#25624d; }}
.confidence.B {{ border-color:#235c4b; }}
.confidence.C {{ border-color:#5a4026; }}
.agg-card th, .agg-card td, .trait-card th, .trait-card td {{ border-bottom-color:var(--line-soft); }}
.graph-paper {{ fill:#45d6a2; }}
.graph-trait {{ fill:#e8a35e; }}
.graph-label {{ fill:#c3d6d0; }}
.graph-label.trait {{ fill:#f0b87c; }}
.graph-year {{ fill:#7f9a90; }}
.overlay {{ background:rgba(5,8,12,.72); }}
.overlay-head {{ border-bottom-color:var(--line); }}
.overlay-head h2 {{ color:var(--ink); }}
.overlay-close {{ background:#1a2330; color:var(--ink-2); }}
.overlay-close:hover {{ background:var(--blue-soft); color:#cfe0ff; }}
.note {{ background:#131a23; border-color:var(--line); }}
.btn {{ color:var(--ink); }}
.btn:hover {{ background:#1d2735; }}
.btn.primary {{ background:var(--blue); border-color:var(--blue); color:#041b14; font-weight:700; }}
.btn.primary:hover {{ background:#46dfb3; }}
@media (max-width: 900px) {{ .overlay {{ padding:8px; }} }}
</style>
</head>
<body>
<div class="topbar"><div class="wrap">
  <a class="brand" href="#main"><span class="mark">p2j</span><span><b>pdf2jsonl</b><small>育种文献数据契约</small></span></a>
  <nav class="topnav"><a class="active" href="#main">研究视图</a><a href="#" data-top-tab="evidence">证据</a><a href="#" data-open-aggregate>多文聚合</a><a href="#" data-top-tab="sources">来源</a></nav>
  <div class="topright"><span class="ver-pill">v4.0.0 · RBL1</span></div>
</div></div>
<header class="hero">
  <div class="wrap">
    <div class="eyebrow">breeding-literature-record · contract 4.0.0 · RBL1 case</div>
    <h1>水稻抗逆抗病：关联事件与多文聚合</h1>
    <p>同一篇论文的 3 个研究上下文分开记录；6 条引物保留 5′→3′ 原文与附件单元格；每条关联的每个关键值都能回到 PDF 页或 XLSX/CSV 单元格。右侧聚合页连接真实论文面板与性状。</p>
    <div class="source-pills">
      <span class="pill">DOI 10.1038/s41586-023-06205-2</span>
      <span class="pill">PDF SHA256 3236…3812</span>
      <span class="pill" id="hero-count">RBL1 case + 真实论文面板</span>
      <span class="pill" id="check-pill">checks: —</span>
    </div>
    <button type="button" class="btn primary" data-open-aggregate>多文聚合 · <span id="agg-btn-count">—</span> 篇论文</button>
  </div>
</header>
<main class="wrap" id="main">
  <section class="stats" id="stats"></section>
  <div class="workspace">
    <aside class="paper-sidebar">
      <div class="paper-list-card">
        <div class="paper-list-head"><b>论文</b><span class="small" id="paper-count"></span></div>
        <input id="paper-search" class="paper-search" placeholder="搜索题名 / DOI / 基因…">
        <div class="paper-list" id="paper-list"></div>
      </div>
      <div class="small muted paper-side-note">左侧是本次聚合的论文；点选后，右侧标签只看这篇论文。多文聚合页始终看全库。</div>
    </aside>
    <div class="paper-main">
      <div class="paper-head" id="paper-head"></div>
      <nav class="tabs" id="tabs">
    <button data-tab="associations" class="active">关联事件 <span id="tab-a"></span></button>
    <button data-tab="sequences">引物序列 <span id="tab-s"></span></button>
    <button data-tab="evidence">字段证据 <span id="tab-e"></span></button>
    <button data-tab="triples">图谱边 <span id="tab-t"></span></button>
    <button data-tab="sources">来源清单</button>
    <button data-tab="checks">校验</button>
  </nav>

  <section class="tab-panel active" id="panel-associations">
    <div class="section-head">
      <div><h2>关联事件</h2><p>一行一个研究上下文；不同群体/环境/等位基因不合并。</p></div>
      <span class="small">点击卡片底部展开字段级证据</span>
    </div>
    <div class="assoc-grid" id="assoc-grid"></div>
    <div class="alias-box" id="alias-box"></div>
  </section>

  <section class="tab-panel" id="panel-sequences">
    <div class="section-head">
      <div><h2>引物序列</h2><p>逐字符保留原文；引物不是标记等位基因，反向引物不自动逆互补。</p></div>
      <span class="small">locator = 附件工作表/单元格</span>
    </div>
    <div class="table-card">
      <div class="table-tools"><span class="small" id="seq-count"></span>
        <input id="seq-filter" placeholder="过滤名称 / 用途 / 方向…">
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>名称</th><th>角色</th><th>5′→3′ 序列</th><th>方向</th><th>用途</th><th>附件定位</th><th>别名</th></tr></thead>
        <tbody id="seq-body"></tbody>
      </table></div>
    </div>
  </section>

  <section class="tab-panel" id="panel-evidence">
    <div class="section-head">
      <div><h2>字段级证据</h2><p>每个字段值独立定位；记录级 quote 不能替代这里的逐项证据。</p></div>
      <span class="small" id="ev-count"></span>
    </div>
    <div class="table-card">
      <div class="table-tools"><span class="small">PDF 证据有 page；附件证据有 sheet/cell。</span>
        <input id="ev-filter" placeholder="过滤字段 / 定位 / 原文…">
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>记录</th><th>字段</th><th>定位</th><th>原文片段</th></tr></thead>
        <tbody id="ev-body"></tbody>
      </table></div>
    </div>
  </section>

  <section class="tab-panel" id="panel-triples">    <div class="section-head">
      <div><h2>图谱边</h2><p>从关联事件派生，每条边带 association / population / environment / evidence。</p></div>
      <span class="small" id="tr-count"></span>
    </div>
    <div class="table-card"><div class="table-wrap"><table>
      <thead><tr><th>subject</th><th>predicate</th><th>object</th><th>population</th><th>evidence</th></tr></thead>
      <tbody id="tr-body"></tbody>
    </table></div></div>
  </section>

  <section class="tab-panel" id="panel-sources">
    <div class="section-head">
      <div><h2>来源清单</h2><p>正文与引物表分开登记角色、状态、哈希和 URL；许可未猜，标为待确认。</p></div>
      <span class="small">手工附件阶段</span>
    </div>
    <div class="table-card"><div class="table-wrap"><table>
      <thead><tr><th>file_id</th><th>角色</th><th>状态</th><th>格式</th><th>SHA256</th><th>URL</th><th>许可</th></tr></thead>
      <tbody id="src-body"></tbody>
    </table></div></div>
  </section>

  <section class="tab-panel" id="panel-checks">
    <div class="section-head">
      <div><h2>校验结果</h2><p>真实 PDF 哈希、字段证据回查、序列逐字符、上下文分离等。</p></div>
      <span class="small" id="check-count"></span>
    </div>
    <div class="checks" id="checks"></div>
    <div class="note">本页由 <code>scripts/make_rbl1_demo.py</code> 从 <code>out/rbl1_case_final</code> 生成；PDF 未随仓库分发，页面只展示可回查的定位与片段。</div>
  </section>

  <div class="footer">水稻抗逆抗病 dashboard · contract 4.0.0 · 真实论文面板 + RBL1 案例</div>
    </div>
  </div>
</main>

<div class="overlay" id="aggregate-overlay" hidden role="dialog" aria-modal="true" aria-labelledby="agg-title">
  <div class="overlay-shell">
    <div class="overlay-head">
      <div><div class="eyebrow">cross-paper aggregate</div><h2 id="agg-title">多文聚合 · 论文—性状关系图</h2>
        <p id="agg-subtitle" class="small">左侧论文，右侧性状；连线表示论文报告了该性状的关联。共享性状不等于共享位点。</p></div>
      <button type="button" class="overlay-close" id="close-aggregate" aria-label="关闭">×</button>
    </div>
    <div class="overlay-body">
      <div class="section-head"><div><h3>聚合概览</h3><p>同一 trait + locus 跨论文合并；群体/环境作为上下文保留，方向相反才登记冲突。</p></div><span class="small" id="agg-count"></span></div>
      <div class="agg-summary" id="agg-summary"></div>
      <div class="graph-card">
        <div class="graph-head"><b>论文—性状关系图</b><span class="small">左侧论文，右侧性状；一条线表示该论文报告了该性状的关联。同一性状可连接多篇论文。</span></div>
        <svg id="paper-graph" role="img" aria-label="论文与性状关系图"></svg>
        <div class="graph-legend"><span><i style="background:#45d6a2"></i>论文</span>
          <span><i style="background:#e8a35e"></i>性状</span><span>连线 = 论文报告该性状的关联</span></div>
      </div>
      <div class="section-head trait-head"><div><h3>为什么能指向同一个性状</h3><p>共享的是“性状概念”，不是基因或位点；每张卡列出该性状下的论文、位点、群体和证据。</p></div></div>
      <div class="trait-grid" id="trait-groups"></div>
      <div class="section-head trait-head"><div><h3>按 trait + locus 聚合的关系</h3><p>位点不同则保持独立关系；只有同一 trait + locus 才合并。</p></div></div>
      <div class="agg-list" id="agg-list"></div>
      <div class="note" id="agg-note"></div>
    </div>
  </div>
</div>
<script id="data" type="application/json">{data}</script>
<script>
const data = JSON.parse(document.getElementById('data').textContent);
const kindLabels = {{
  linkage_mapping:'连锁/图位克隆', qtl_mapping:'QTL 定位', gwas:'GWAS', candidate_gene:'候选基因',
  functional_complementation:'功能互补', genome_editing:'基因编辑', colocalization:'共定位',
  expression_support:'表达证据', other:'其他'
}};
const roleLabels = {{
  pcr_forward_primer:'PCR 正向', pcr_reverse_primer:'PCR 反向',
  qrt_forward_primer:'qRT 正向', qrt_reverse_primer:'qRT 反向',
  sequencing_primer:'测序引物', probe:'探针', amplicon:'扩增子', allele:'等位基因', gene:'基因', other:'其他'
}};
const dirLabels = {{forward:'正向', reverse:'反向', not_applicable:'不适用', unknown:'未说明'}};
const effectLabels = {{increase:'增加 / 抗性增强', decrease:'降低 / 抗性减弱'}};
const validationLabels = {{candidate:'候选 / 待验证', experiment_reported:'已报告验证实验'}};
const locusShort = (s) => String(s || '').split(':').pop();
const envShort = (s) => String(s || '').split(':').pop();
const missingLabels = {{
  not_reported:'论文未报告', not_located:'未定位到', not_verified:'有值但未核实',
  source_unavailable:'附件不可得', parse_failed:'解析失败', ambiguous:'来源有歧义',
  requires_review:'需人工判断', requires_external_source:'需外部来源'
}};
const predLabels = {{
  associated_with_trait:'关联性状', studies_locus:'研究位点', studied_in_population:'研究群体', uses_sequence:'使用序列'
}};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const short = (s, n=16) => (String(s ?? '').length > n ? String(s).slice(0,n) + '…' : String(s ?? ''));
const allAssoc = (data.all_records || data.records).filter(r => r.common.record_kind === 'association');
const seqs = (data.all_records || data.records).filter(r => r.common.record_kind === 'sequence');
const agg = data.aggregate || {{ relations: [], conflicts: [], counts: {{}} }};
const aggCounts = agg.counts || {{}};
const evByRecord = {{}};
for (const e of data.evidence) (evByRecord[e.record_id] ||= []).push(e);
const paperMap = new Map();
const paperKey = (r) => r.common.source_id || r.common.source_doi || r.common.source_title;
for (const r of allAssoc) {{
  const c = r.common, key = paperKey(r);
  let p = paperMap.get(key);
  if (!p) {{ p = {{id:key, title:c.source_title || key, year:c.source_year, doi:c.source_doi, url:c.source_file_url,
    associations: [], sequences: [], evidence: 0}}; paperMap.set(key, p); }}
  p.associations.push(r);
  p.evidence += (c.field_evidence || []).length;
}}
for (const r of seqs) {{
  const c = r.common, key = paperKey(r);
  let p = paperMap.get(key);
  if (!p) {{ p = {{id:key, title:c.source_title || key, year:c.source_year, doi:c.source_doi, url:c.source_file_url,
    associations: [], sequences: [], evidence: 0}}; paperMap.set(key, p); }}
  p.sequences.push(r);
}}
const papers = [...paperMap.values()].sort((a,b) => (b.year||0)-(a.year||0) || a.title.localeCompare(b.title));
let currentPaper = papers.find(p => (p.doi || '').includes('10.1038/s41586-023-06205-2')) || papers[0];
function assocForPaper() {{ return currentPaper ? currentPaper.associations : []; }}
function seqsForPaper() {{ return currentPaper ? currentPaper.sequences : []; }}
function recordIdsForPaper() {{ return new Set(assocForPaper().map(r => r.common.record_id)); }}
function paperEvidence() {{
  const out = [];
  for (const r of [...assocForPaper(), ...seqsForPaper()]) {{
    const fromCsv = evByRecord[r.common.record_id] || [];
    if (fromCsv.length) out.push(...fromCsv);
    else for (const e of r.common.field_evidence || []) out.push({{...e, record_id:r.common.record_id}});
  }}
  return out;
}}
for (const r of allAssoc) {{
  if (evByRecord[r.common.record_id] && evByRecord[r.common.record_id].length) continue;
  evByRecord[r.common.record_id] = (r.common.field_evidence || []).map(e => ({{...e, record_id:r.common.record_id}}));
}}
for (const p of papers) {{
  p.evidence = [...p.associations, ...p.sequences].reduce((n, r) => n + ((evByRecord[r.common.record_id] || []).length), 0);
}}
const checks = Object.entries(data.report.checks || {{}});
const passed = checks.filter(([,v]) => v === true).length;
const totalChecks = checks.filter(([,v]) => v !== null).length;


document.getElementById('check-pill').textContent = `checks: ${{passed}} / ${{totalChecks}}`;
document.getElementById('hero-count').textContent = `${{allAssoc.length}} associations · ${{papers.length}} papers · ${{aggCounts.relations || 0}} relations`;
document.getElementById('agg-btn-count').textContent = papers.length;
const evidenceTotal = Object.values(evByRecord).reduce((n, rows) => n + rows.length, 0);
const stats = [
  [allAssoc.length, '关联事件', `${{allAssoc.length}} 个研究上下文`],
  [papers.length, '论文', 'RBL1 + 真实论文面板'],
  [aggCounts.relations || 0, '聚合关系', `${{aggCounts.conflicts || 0}} 个冲突 · B${{(aggCounts.confidence||{{}}).B || 0}}`],
  [evidenceTotal, '字段证据', 'PDF 页 / 附件单元格'],
  [`${{passed}}/${{totalChecks}}`, '校验通过', `${{totalChecks}} 项硬检查`],
];
document.getElementById('stats').innerHTML = stats.map(([n,l,s],i) =>
  `<div class="stat ${{i===4?'good':''}}"><div class="num">${{n}}</div><div class="label">${{l}}</div><div class="small">${{s}}</div></div>`
).join('');

function evidenceHtml(recordId) {{
  const items = evByRecord[recordId] || [];
  if (!items.length) return '<div class="small">无字段级证据</div>';
  return `<div class="evidence-list">${{items.map(e => `
    <div class="evidence-row">
      <code>${{esc(e.field)}}</code><span class="locator">${{esc(e.locator)}}</span>
      <q>${{esc(e.quote)}}</q>
      <div class="small mono">${{esc(e.evidence_id)}} · ${{esc(e.file_id)}}</div>
    </div>`).join('')}}</div>`;
}}

function updateTabCounts() {{
  const ids = recordIdsForPaper();
  document.getElementById('tab-a').textContent = assocForPaper().length;
  document.getElementById('tab-s').textContent = seqsForPaper().length;
  document.getElementById('tab-e').textContent = paperEvidence().length;
  document.getElementById('tab-t').textContent = data.triples.filter(t => ids.has(t.association_id)).length;
}}

function renderPaperList(filter='') {{
  const q = filter.trim().toLowerCase();
  const items = papers.filter(p => !q || [p.title, p.doi, ...p.associations.map(a => a.common.locus_id)]
    .join(' ').toLowerCase().includes(q));
  document.getElementById('paper-count').textContent = `${{items.length}} / ${{papers.length}}`;
  document.getElementById('paper-list').innerHTML = items.map(p => `
    <button class="paper-item ${{p.id === currentPaper?.id ? 'active' : ''}}" data-paper="${{esc(p.id)}}">
      <span class="t">${{esc(p.title)}}</span>
      <span class="m">${{esc(p.year || '')}} · ${{p.associations.length}} 关联 · ${{p.sequences.length}} 序列</span>
    </button>`).join('');
  document.querySelectorAll('[data-paper]').forEach(btn => btn.onclick = () => {{
    currentPaper = papers.find(p => p.id === btn.dataset.paper) || currentPaper;
    renderPaperHead(); renderPaperList(document.getElementById('paper-search').value);
    renderAssoc(); renderSeq(document.getElementById('seq-filter').value);
    renderEvidence(document.getElementById('ev-filter').value); renderTriples(); updateTabCounts();
  }});
}}

function renderPaperHead() {{
  if (!currentPaper) {{ document.getElementById('paper-head').innerHTML = ''; return; }}
  const p = currentPaper;
  document.getElementById('paper-head').innerHTML = `
    <h2>${{esc(p.title)}}</h2>
    <div class="meta"><span>${{esc(p.year || '')}}</span><span>${{esc(p.doi || p.id)}}</span>
      <span>关联 ${{p.associations.length}}</span><span>序列 ${{p.sequences.length}}</span></div>
    <div class="badges"><span class="badge kind">${{p.associations.length}} 个研究上下文</span>
      <span class="badge review">${{p.evidence}} 条字段证据</span>
      <span class="badge ok">${{p.sequences.length ? '含引物附件' : '无引物附件'}}</span></div>`;
}}

function renderAssoc() {{
  const list = assocForPaper();
  document.getElementById('assoc-grid').innerHTML = list.length ? list.map(r => {{
    const c = r.common, ref = data.refs[c.record_id] || short(c.record_id, 12);
    const missing = Object.entries(c.missing_fields || {{}}).map(([k,v]) =>
      `<span title="${{esc(k)}}">${{esc(missingLabels[v] || v)}} · ${{esc(k.split('.').pop())}}</span>`).join('');
    const ev = evByRecord[c.record_id] || [];
    return `<article class="assoc-card">
      <div class="assoc-top"><span class="ref">${{esc(ref)}}</span>
        <span class="badge kind">${{esc(kindLabels[c.association_kind] || c.association_kind)}}</span>
        <span class="badge review">${{esc(c.review_status === 'pending_review' ? '待复核' : c.review_status)}}</span>
      </div>
      <h3>${{esc((c.trait_names || []).join(' / '))}}</h3>
      <div class="context">
        <div><small>位点</small><b title="${{esc(c.locus_id)}}">${{esc(locusShort(c.locus_id))}}</b><span class="small">${{esc(c.locus_type)}}</span></div>
        <div><small>群体</small><b>${{esc(c.population_name)}}</b><span class="small">${{esc(c.population_type)}}</span></div>
        <div><small>材料</small><b>${{esc((c.germplasm_names || []).join(' / '))}}</b></div>
        <div><small>环境</small><b title="${{esc(c.environment_id)}}">${{esc(envShort(c.environment_id))}}</b></div>
        <div><small>等位基因</small><b>${{esc(c.alternate_allele || '—')}}</b></div>
        <div><small>验证状态</small><b>${{esc(validationLabels[(r.transform || {{}}).validation_status] || (r.transform || {{}}).validation_status || '—')}}</b></div>
      </div>
      <div class="missing">${{missing || '<span>无缺失字段</span>'}}</div>
      <details><summary>查看 ${{ev.length}} 条字段级证据</summary>${{evidenceHtml(c.record_id)}}</details>
    </article>`;
  }}).join('') : '<div class="empty-inline">这篇论文没有关联事件。</div>';
  const showAliases = list.some(r => (r.common.source_doi || '').includes('10.1038/s41586-023-06205-2'));
  document.getElementById('alias-box').innerHTML = showAliases && data.aliases.length
    ? `<strong>别名候选</strong><div>${{data.aliases.map(a => `<div><code>${{esc(a.entity)}}</code> ↔ <code>${{esc(a.alias)}}</code>
        <span class="badge review">${{esc(a.status)}}</span> <span class="small">需人工确认，未自动合并</span></div>`).join('')}}</div>`
    : '';
}}

renderPaperList();
renderPaperHead();
renderAssoc();
updateTabCounts();
document.getElementById('paper-search').oninput = e => renderPaperList(e.target.value);

function renderSeq(filter='') {{
  const q = filter.trim().toLowerCase();
  const all = seqsForPaper();
  const rows = all.filter(r => !q || [r.common.primer_name,r.common.primer_use,r.common.primer_direction,r.common.primer_role]
    .join(' ').toLowerCase().includes(q));
  document.getElementById('seq-count').textContent = `${{rows.length}} / ${{all.length}} 条`;
  document.getElementById('seq-body').innerHTML = rows.length ? rows.map((r,i) => {{
    const c = r.common, t = r.transform || {{}};
    const alias = t.entity_alias_status ? `<span class="badge review">${{esc(t.entity_alias_status)}}</span>
      <div class="small">↔ ${{esc((t.entity_synonyms || []).join(', '))}}</div>` : '—';
    return `<tr>
      <td><strong>${{esc(c.primer_name)}}</strong></td>
      <td>${{esc(roleLabels[c.primer_role] || c.primer_role)}}</td>
      <td><code class="seq">${{esc(c.primer_sequence)}}</code>
        <button class="copy" data-seq="${{esc(c.primer_sequence)}}">复制</button></td>
      <td><span class="badge kind">${{esc(dirLabels[c.primer_direction] || c.primer_direction)}}</span></td>
      <td>${{esc(c.primer_use)}}</td>
      <td><span class="mono">${{esc(c.primer_source_locator)}}</span></td>
      <td>${{alias}}</td>
    </tr>`;
  }}).join('') : '<tr><td colspan="7"><div class="empty-inline">这篇论文没有引物附件记录。</div></td></tr>';
  document.querySelectorAll('.copy').forEach(b => b.onclick = async () => {{
    try {{ await navigator.clipboard.writeText(b.dataset.seq); b.textContent='已复制'; setTimeout(()=>b.textContent='复制',1200); }}
    catch(e) {{ b.textContent='选择复制'; }}
  }});
}}
renderSeq();
document.getElementById('seq-filter').oninput = e => renderSeq(e.target.value);

function renderEvidence(filter='') {{
  const q = filter.trim().toLowerCase();
  const all = paperEvidence();
  const rows = all.filter(e => !q || [e.record_id,e.field,e.locator,e.quote].join(' ').toLowerCase().includes(q));
  document.getElementById('ev-count').textContent = `${{rows.length}} / ${{all.length}} 条`;
  document.getElementById('ev-body').innerHTML = rows.length ? rows.map(e => `<tr>
    <td><span class="mono">${{esc(short(e.record_id, 14))}}</span></td>
    <td><code>${{esc(e.field)}}</code></td>
    <td><span class="mono">${{esc(e.locator)}}</span></td>
    <td>${{esc(e.quote)}}<div class="small mono">${{esc(e.evidence_id)}}</div></td>
  </tr>`).join('') : '<tr><td colspan="4"><div class="empty-inline">这篇论文没有字段级证据。</div></td></tr>';
}}
renderEvidence();
document.getElementById('ev-filter').oninput = e => renderEvidence(e.target.value);

function renderPaperGraph() {{
  const papers = new Map(), traits = new Map(), links = [];
  for (const r of (agg.relations || [])) {{
    const tid = r.trait_id || r.key;
    traits.set(tid, {{id: tid, label: (r.trait_names || [r.key])[0]}});
    for (const c of (r.contexts || [])) {{
      const p = c.paper || {{}};
      const pid = p.id || p.title || c.association_id;
      if (!papers.has(pid)) papers.set(pid, {{id: pid, title: p.title || pid, year: p.year}});
      links.push({{p: pid, t: tid}});
    }}
  }}
  const pn = [...papers.values()].sort((a, b) => (b.year || 0) - (a.year || 0) || a.title.localeCompare(b.title));
  const tn = [...traits.values()];
  const W = 1120, row = 42, H = Math.max(320, pn.length * row + 56);
  const leftX = 300, rightX = W - 300;
  const py = new Map(), ty = new Map();
  pn.forEach((p, i) => py.set(p.id, 34 + i * row));
  tn.forEach((t, i) => ty.set(t.id, 34 + (i + 0.5) * (H - 56) / Math.max(tn.length, 1)));
  const palette = ['#42d6a4', '#e8b86a', '#6ed0c0', '#e59a67', '#8fd6b8', '#78c9b7', '#c9a6d8', '#a9c97a'];
  const traitColor = new Map(tn.map((t, i) => [t.id, palette[i % palette.length]]));
  const shortText = (s, n) => s.length > n ? s.slice(0, n - 1) + '…' : s;
  const parts = [];
  for (const l of links) {{
    const x1 = leftX + 8, y1 = py.get(l.p), x2 = rightX - 8, y2 = ty.get(l.t);
    const pTitle = (papers.get(l.p) || {{}}).title || l.p;
    const tTitle = (traits.get(l.t) || {{}}).label || l.t;
    parts.push(`<line class="graph-line" x1="${{x1}}" y1="${{y1}}" x2="${{x2}}" y2="${{y2}}" stroke="${{traitColor.get(l.t)}}" data-paper="${{esc(l.p)}}" data-trait="${{esc(l.t)}}"><title>${{esc(pTitle)}} → ${{esc(tTitle)}}</title></line>`);
  }}
  for (const p of pn) {{
    const y = py.get(p.id);
    parts.push(`<circle class="graph-paper" cx="${{leftX}}" cy="${{y}}" r="5"><title>${{esc(p.title)}}</title></circle>`);
    parts.push(`<text class="graph-label paper" x="${{leftX - 12}}" y="${{y + 4}}">${{esc(shortText(p.title, 40))}}</text>`);
    parts.push(`<text class="graph-year" x="${{leftX - 12}}" y="${{y + 16}}">${{esc(p.year || '')}}</text>`);
  }}
  for (const t of tn) {{
    const y = ty.get(t.id);
    parts.push(`<circle class="graph-trait" cx="${{rightX}}" cy="${{y}}" r="6"><title>${{esc(t.label)}}</title></circle>`);
    parts.push(`<text class="graph-label trait" x="${{rightX + 12}}" y="${{y + 4}}">${{esc(shortText(t.label, 34))}}</text>`);
  }}
  const svg = document.getElementById('paper-graph');
  svg.setAttribute('viewBox', `0 0 ${{W}} ${{H}}`);
  svg.innerHTML = parts.join('');
}}
renderPaperGraph();

function renderAggregate() {{
  const c = aggCounts;
  document.getElementById('agg-count').textContent = `${{c.relations || 0}} 关系 / ${{c.papers || 0}} 篇论文`;
  const conf = c.confidence || {{}};
  document.getElementById('agg-summary').innerHTML = `
    <div class="item"><div class="n">${{c.papers || 0}}</div><div class="l">参与聚合的论文</div></div>
    <div class="item"><div class="n">${{c.relations || 0}}</div><div class="l">合并后的关系</div></div>
    <div class="item"><div class="n">${{c.associations || 0}}</div><div class="l">关联事件（上下文）</div></div>
    <div class="item"><div class="n">${{c.conflicts || 0}}</div><div class="l">方向冲突 · A${{conf.A || 0}} / B${{conf.B || 0}} / C${{conf.C || 0}}</div></div>`;
  document.getElementById('agg-note').textContent = data.aggregate_note || '';
  document.getElementById('agg-list').innerHTML = (agg.relations || []).map(r => {{
    const cs = (agg.conflicts || []).filter(x => x.relation_id === r.relation_id);
    const contexts = (r.contexts || []).map(x => `<tr>
      <td>${{esc(x.paper.title)}}<div class="small">${{esc(x.paper.doi)}}</div></td>
      <td>${{esc(x.population_name)}}<div class="small">${{esc(x.environment_id)}}</div></td>
      <td>${{esc(kindLabels[x.association_kind] || x.association_kind)}}</td>
      <td>${{esc(effectLabels[x.effect_direction] || x.effect_direction || '—')}}</td>
      <td>${{x.evidence_count}} evidence<div class="small">${{esc(x.validation_status || '')}}</div></td>
    </tr>`).join('');
    return `<article class="agg-card">
      <div class="agg-top">
        <h3>${{esc((r.trait_names || []).join(' / '))}} · <span class="mono">${{esc(r.locus_id)}}</span></h3>
        <div class="agg-meta">
          <span class="badge confidence ${{esc(r.confidence)}}">${{esc(r.confidence)}}</span>
          <span class="badge kind">${{r.paper_count}} 篇论文</span>
          <span class="badge kind">${{r.association_count}} 个上下文</span>
          <span class="badge kind">${{r.evidence_count}} 条证据</span>
        </div>
      </div>
      <div class="agg-basis">${{(r.confidence_basis || []).map(b => `<span>${{esc(b)}}</span>`).join('')}}</div>
      ${{cs.map(x => `<div class="conflict"><strong>冲突</strong> ${{esc(x.message)}} · 方向：${{esc((x.directions || []).join(' / '))}}</div>`).join('')}}
      <details><summary>展开 ${{(r.contexts || []).length}} 个研究上下文</summary>
        <table><thead><tr><th>论文</th><th>群体 / 环境</th><th>关联类型</th><th>方向</th><th>证据</th></tr></thead>
        <tbody>${{contexts}}</tbody></table>
      </details>
    </article>`;
  }}).join('');
}}
renderAggregate();

function renderTraitGroups() {{
  const groups = new Map();
  for (const r of (agg.relations || [])) {{
    const tid = r.trait_id || r.key;
    const label = (r.trait_names || [r.key])[0];
    if (!groups.has(tid)) groups.set(tid, {{label, papers: new Map(), loci: new Set()}});
    const g = groups.get(tid);
    g.loci.add(r.locus_id);
    for (const c of (r.contexts || [])) {{
      const p = c.paper || {{}}, key = p.id || p.title || c.association_id;
      if (!g.papers.has(key)) g.papers.set(key, {{paper: p, loci: new Set(), kinds: new Set(),
        populations: new Set()}});
      const row = g.papers.get(key);
      row.loci.add(r.locus_id);
      row.kinds.add(kindLabels[c.association_kind] || c.association_kind);
      row.populations.add(c.population_name);
    }}
  }}
  const items = [...groups.values()].sort((a, b) => b.papers.size - a.papers.size || a.label.localeCompare(b.label));
  document.getElementById('trait-groups').innerHTML = items.map(g => {{
    const loci = [...g.loci];
    let why;
    if (g.papers.size === 1) {{
      why = `目前只有 1 篇论文报告「${{g.label}}」，它连接到该性状节点；没有跨文合并。`;
    }} else if (loci.length > 1) {{
      why = `这 ${{g.papers.size}} 篇论文都把「${{g.label}}」作为性状报告，但位点分别为 ${{loci.map(x => locusShort(x)).join('、')}}。共享的是性状概念，不是同一位点；因此论文—性状图把它们连到同一性状节点，而 trait + locus 关系聚合仍保持独立。`;
    }} else {{
      why = `这 ${{g.papers.size}} 篇论文报告的是同一性状「${{g.label}}」，且位点相同（${{locusShort(loci[0])}}）；论文—性状图共享节点，trait + locus 聚合也合并为一条关系。`;
    }}
    const rows = [...g.papers.values()].map(x => `<tr>
      <td>${{esc(x.paper.title)}}<div class="small">${{esc(x.paper.year || '')}}</div></td>
      <td>${{esc([...x.loci].map(locusShort).join(', '))}}</td>
      <td>${{esc([...x.kinds].join(', '))}}</td>
      <td>${{esc([...x.populations].join(' / '))}}</td>
    </tr>`).join('');
    return `<article class="trait-card">
      <h4>${{esc(g.label)}}</h4>
      <div class="small">${{g.papers.size}} 篇论文 · ${{loci.length}} 个位点</div>
      <p class="why">${{esc(why)}}</p>
      <table><thead><tr><th>论文</th><th>位点</th><th>关联类型</th><th>群体</th></tr></thead>
      <tbody>${{rows}}</tbody></table>
    </article>`;
  }}).join('');
}}
renderTraitGroups();

const overlay = document.getElementById('aggregate-overlay');
function openAggregate() {{
  overlay.hidden = false;
  document.body.style.overflow = 'hidden';
  if (location.hash !== '#aggregate') history.replaceState(null, '', '#aggregate');
}}
function closeAggregate() {{
  overlay.hidden = true;
  document.body.style.overflow = '';
  if (location.hash === '#aggregate') history.replaceState(null, '', location.pathname + location.search);
}}
document.querySelectorAll('[data-open-aggregate]').forEach(el => el.onclick = (ev) => {{
  ev.preventDefault(); openAggregate();
}});
document.getElementById('close-aggregate').onclick = closeAggregate;
overlay.addEventListener('click', ev => {{ if (ev.target === overlay) closeAggregate(); }});
document.addEventListener('keydown', ev => {{ if (ev.key === 'Escape' && !overlay.hidden) closeAggregate(); }});
if (new URLSearchParams(location.search).get('view') === 'aggregate' || location.hash === '#aggregate') openAggregate();

function renderTriples() {{
  const ids = recordIdsForPaper();
  const triples = data.triples.filter(t => ids.has(t.association_id));
  document.getElementById('tr-count').textContent = `${{triples.length}} 条`;
  document.getElementById('tr-body').innerHTML = triples.length ? triples.map(t => `<tr>
    <td><span class="mono">${{esc(short(t.subject, 18))}}</span><div class="small">${{esc(data.refs[t.association_id] || '')}}</div></td>
    <td><span class="badge kind">${{esc(predLabels[t.predicate] || t.predicate)}}</span></td>
    <td>${{esc(t.object)}}<div class="small">${{esc(t.object_id || t.object_type)}}</div></td>
    <td class="small">${{esc(t.population_id)}}<br>${{esc(t.environment_id)}}</td>
    <td><span class="small">${{(t.evidence_ids || []).length}} evidence</span></td>
  </tr>`).join('') : '<tr><td colspan="5"><div class="empty-inline">这篇论文没有派生的图谱边。</div></td></tr>';
}}
renderTriples();

document.getElementById('src-body').innerHTML = data.sources.map(s => `<tr>
  <td class="mono">${{esc(s.file_id)}}</td><td>${{esc(s.role)}}</td><td><span class="badge ok">${{esc(s.status)}}</span></td>
  <td>${{esc(s.format)}}</td><td class="mono">${{esc(short(s.sha256, 22))}}</td>
  <td><a href="${{esc(s.url)}}" target="_blank" rel="noreferrer">${{esc(short(s.url, 42))}}</a></td>
  <td><span class="badge review">${{esc(s.license_status || '未确认')}}</span></td>
</tr>`).join('');

document.getElementById('check-count').textContent = `${{passed}} / ${{totalChecks}} 通过`;
document.getElementById('checks').innerHTML = checks.map(([k,v]) => `<div class="check">
  <span class="dot" style="background:${{v ? 'var(--green)' : 'var(--orange)'}}"></span>
  <span><code>${{esc(k)}}</code><div class="small">${{v === true ? '通过' : v === null ? '未运行（无 PDF）' : '未通过'}}</div></span>
</div>`).join('');

document.querySelectorAll('#tabs button').forEach(btn => btn.onclick = () => {{
  document.querySelectorAll('#tabs button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
}});

// Deep links for screenshots/review: ?tab=sequences&open=1
const params = new URLSearchParams(location.search);
const startTab = params.get('tab') || location.hash.replace('#', '');
if (startTab) {{
  const btn = document.querySelector(`#tabs button[data-tab="${{startTab}}"]`);
  if (btn) btn.click();
}}
if (params.get('open') === '1') document.querySelectorAll('details').forEach(d => d.open = true);
document.querySelectorAll('[data-top-tab]').forEach(a => a.onclick = (ev) => {{
  ev.preventDefault();
  const btn = document.querySelector(`#tabs button[data-tab="${{a.dataset.topTab}}"]`);
  if (btn) btn.click();
  document.getElementById('tabs').scrollIntoView({{behavior:'smooth', block:'start'}});
}});
</script>
</body>
</html>
"""


def build(case_dir: Path, out: Path, aggregate_records: Path | None = None) -> tuple[Path, dict]:
    payload = load_case(case_dir, aggregate_records)
    html_text = render(payload)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8", newline="\n")
    return out, payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-dir", default="out/rbl1_case_final")
    ap.add_argument("--aggregate-records", type=Path,
                    help="JSONL with extra association records for the aggregate view")
    ap.add_argument("--out", default="dashboard.html")
    args = ap.parse_args(argv)
    out, payload = build(Path(args.case_dir), Path(args.out), args.aggregate_records)
    counts = payload["report"]["counts"]
    agg = payload["aggregate"]["counts"]
    print(f"{out}: {counts['associations']} associations, {counts['sequences']} sequences, "
          f"{counts['field_evidence']} field evidence, {agg['relations']} aggregate relations, "
          f"{agg['conflicts']} conflicts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
