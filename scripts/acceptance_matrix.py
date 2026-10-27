"""The regression matrix the feedback asks for: run the same papers through the old and the new contract, with the
main text alone and with the supplementary files, and record the review queue item by item.

It is a library, not a test: ``scripts/acceptance_report.py`` writes the report from it and
``tests/test_acceptance.py`` asserts the criteria. Every cell is one in-process run of the pipeline, so the matrix
stays fast and needs no outside corpus.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pdf2jsonl_skill.pipeline import RunOptions, run

OLD_VERSION = "3.6.0"
NEW_VERSION = "3.8.0"
PRIMARY_VERSION = NEW_VERSION

FIXTURES = Path("tests/fixtures/acceptance")
HEAT = Path("examples/papers")

# One cell = a paper, an input configuration (main text only, or main text + supplements) and a contract version.
PAPERS = {
    # the repository's own paper with a supplement: the only one that can vary the input configuration
    "heat": {"text": HEAT / "synthetic_rice_heat.txt", "candidates": HEAT / "synthetic_rice_heat.candidates.json",
             "supplement": HEAT / "synthetic_rice_heat.supplement.pdf"},
    "gmoleo1": {"text": FIXTURES / "gmoleo1.txt", "candidates": FIXTURES / "gmoleo1.candidates.json"},
    "qtl_overlap": {"text": FIXTURES / "qtl_overlap.txt", "candidates": FIXTURES / "qtl_overlap.candidates.json"},
    "review": {"text": FIXTURES / "review.txt", "candidates": FIXTURES / "review.candidates.json"},
}

# The five cases the feedback names, by the quote that carries each one.
FOCUS = {
    "correlation": "GmOLEO1 was significantly correlated with seed oil content",
    "overexpression": "Overexpression of GmOLEO1 increased seed oil content",
    "overlap": "qSCN-1 overlapped with the QTL cluster",
    "colocalize": "qSCN-3 colocalized with",
    "candidate": "The candidate gene Glyma.16G123400",
    "validated": "Overexpression of GmOLEO1 increased seed oil content",
    "review_cited": "Zhang et al. (2019) reported that",
    "review_nocite": "In rice, Ghd7 is known to delay",
    "review_hedged": "Several studies have suggested that Dt1",
}


@dataclass
class Cell:
    paper: str
    version: str
    supplement: bool
    records: list
    counts: dict
    warnings: list
    validation: dict

    def record_for(self, quote: str):
        for r in self.records:
            if quote in ((r.get("common") or {}).get("source_quote") or ""):
                return r
        return None

    def pending(self) -> int:
        return (self.counts.get("by_review_status") or {}).get("pending_review", 0)


def run_cell(root: Path, paper: str, version: str, supplement: bool, out_root: Path) -> Cell:
    spec = PAPERS[paper]
    out = out_root / f"{paper}-{version}-{'sup' if supplement else 'main'}"
    opts = RunOptions(profile="pdf_extraction", schema_version=version, backend="candidates",
                      candidates_file=str(root / spec["candidates"]), out_dir=str(out),
                      run_id=f"acc_{paper}_{version}_{'sup' if supplement else 'main'}",
                      supplements=[str(root / spec["supplement"])] if supplement and spec.get("supplement") else [])
    res = run(root / spec["text"], opts)
    report = json.loads(Path(res.outputs["validation"]).read_text(encoding="utf-8"))
    warnings = [dict(w, record_id=row.get("record_id")) for row in report.get("records") or [] for w in (row.get("warnings") or [])]
    warnings += [{"code": w.get("code"), "part": w.get("part")} for w in ((report.get("source_parts") or {}).get("warnings") or [])]
    return Cell(paper, version, supplement, res.records, report["counts"], warnings, report)


def build_matrix(root: Path, out_root: Path, versions=(OLD_VERSION, NEW_VERSION)) -> list[Cell]:
    cells = []
    for version in versions:
        cells.append(run_cell(root, "heat", version, False, out_root))
        cells.append(run_cell(root, "heat", version, True, out_root))
        for paper in ("gmoleo1", "qtl_overlap", "review"):
            cells.append(run_cell(root, paper, version, False, out_root))
    return cells


def codes_by_family(cell: Cell) -> dict[str, int]:
    """The review queue grouped the way an operator works through it (docs/review.md), not by raw code."""
    fam = Counter()
    prefixes = {"RULE_": "rule", "VALUE": "value", "LINK": "link", "SOURCE": "source", "DOCUMENT": "document",
                "EVIDENCE": "evidence", "REVIEW": "review", "VERIFY": "verify", "ARGUMENT": "argument",
                "WORKFLOW": "workflow"}
    for w in cell.warnings:
        code = w.get("code") or ""
        key = next((v for k, v in prefixes.items() if code.startswith(k)), "other")
        fam[key] += 1
    return dict(sorted(fam.items()))


def _statement(cell: Cell, quote: str) -> dict:
    stmts = (cell.validation.get("counts") or {}).get("relation") or {}
    rec = cell.record_for(quote) or {}
    return {"record": rec, "counts": stmts}


def criteria(cells: list[Cell]) -> list[dict]:
    """Every acceptance criterion, computed from the matrix. ``ok`` is what the report prints."""
    by = {(c.paper, c.version, c.supplement): c for c in cells}
    out: list[dict] = []

    def add(name: str, ok: bool, detail: str, group: str = "验收项"):
        out.append({"name": name, "ok": bool(ok), "detail": detail, "group": group})

    new_heat = by[("heat", NEW_VERSION, False)]
    new_heat_sup = by[("heat", NEW_VERSION, True)]
    old_heat = by[("heat", OLD_VERSION, False)]
    old_heat_sup = by[("heat", OLD_VERSION, True)]

    # 0. the matrix itself ran. A candidate whose part was not supplied is refused by design, so "no rejection"
    #    is required only where the run was given every part the text cites.
    for cell in cells:
        complete = bool((cell.validation.get("source_parts") or {}).get("complete"))
        add(f"{cell.paper} / {cell.version} / {'正文+补充' if cell.supplement else '正文'}："
            f"{'未拒收候选' if complete else '缺材料时候选被拒（预期）'}",
            cell.counts["rejected"] == 0 if complete else cell.counts["rejected"] > 0,
            f"records={cell.counts['records']}, rejected={cell.counts['rejected']}, pending={cell.pending()}, "
            f"missing={(cell.validation.get('source_parts') or {}).get('missing')}",
            "矩阵")

    # 1. old vs new: the new contract writes the derived fields, the old one does not
    old_recs = old_heat.records
    new_recs = new_heat.records
    old_has = any((r.get("transform") or {}).get("relation_resolution") for r in old_recs)
    new_has = any((r.get("transform") or {}).get("relation_resolution") for r in new_recs)
    add("旧版 3.6.0 不写 relation_resolution / claim_strength / validation_status", not old_has and not any(
        (r.get("transform") or {}).get("claim_strength") for r in old_recs), "旧版记录里这些字段为空")
    add("新版 3.8.0 写出 relation_resolution 与 claim_strength", new_has and any(
        (r.get("transform") or {}).get("claim_strength") for r in new_recs),
        "新版记录带判定结果与结论强度")

    # 2. main text vs main + supplements
    add("正文输入：缺补充材料被记为 missing", "supplement" in ((new_heat.validation.get("source_parts") or {}).get("missing") or []),
        f"missing={(new_heat.validation.get('source_parts') or {}).get('missing')}")
    add("正文+补充：来源完整", not ((new_heat_sup.validation.get("source_parts") or {}).get("missing") or []),
        f"complete={(new_heat_sup.validation.get('source_parts') or {}).get('complete')}")

    # 3. GmOLEO1: a correlation stays an association
    corr = by[("gmoleo1", NEW_VERSION, False)].record_for(FOCUS["correlation"])
    code = (corr.get("transform") or {}).get("predicate_code") if corr else None
    add("GmOLEO1 相关性：谓词落为相关而非因果",
        code == "locus_correlated_with_trait"
        and (corr.get("transform") or {}).get("relation_nature") == "associational"
        and (corr.get("transform") or {}).get("claim_strength") == "associational",
        f"predicate_code={code}, nature={(corr.get('transform') or {}).get('relation_nature') if corr else None}, "
        f"strength={(corr.get('transform') or {}).get('claim_strength') if corr else None}")

    # 4. GmOLEO1 overexpression: causal wording, no evidence type yet -> causal_unverified, and the linked
    #    complementation marks it as experiment_reported
    over = by[("gmoleo1", NEW_VERSION, False)].record_for(FOCUS["overexpression"])
    t = (over.get("transform") or {}) if over else {}
    add("GmOLEO1 过表达：因果措辞 + 未给证据 → causal_unverified",
        t.get("predicate_code") == "locus_increases_trait" and t.get("claim_strength") == "causal_unverified",
        f"predicate_code={t.get('predicate_code')}, strength={t.get('claim_strength')}")
    add("GmOLEO1 过表达：链接到互补实验 → experiment_reported",
        t.get("validation_status") == "experiment_reported" and bool((over.get("agent") or {}).get("validated_by_record_ids")),
        f"validation_status={t.get('validation_status')}, link={(over.get('agent') or {}).get('validated_by_record_ids')}")

    # 5. the validated conclusion keeps its own association evidence: same quote + predicate still present
    add("验证实验不覆盖关联证据：结论记录仍保留自己的引文与谓词",
        bool(t.get("predicate_mention")) and "Overexpression of GmOLEO1" in ((over.get("common") or {}).get("source_quote") or "")
        and len(by[("gmoleo1", NEW_VERSION, False)].records) > 1,
        "结论记录与实验记录并存，链接只是引用")

    # 6. an unvalidated candidate gene stays a candidate
    cand = by[("gmoleo1", NEW_VERSION, False)].record_for(FOCUS["candidate"])
    add("无验证候选基因：validation_status = candidate",
        bool(cand) and (cand.get("transform") or {}).get("validation_status") == "candidate",
        f"validation_status={(cand.get('transform') or {}).get('validation_status') if cand else None}")

    # 7. QTL overlap is structural, never causal
    ov = by[("qtl_overlap", NEW_VERSION, False)].record_for(FOCUS["overlap"])
    co = by[("qtl_overlap", NEW_VERSION, False)].record_for(FOCUS["colocalize"])
    add("QTL 重叠：overlapped with → structural",
        bool(ov) and (ov.get("transform") or {}).get("predicate_code") == "locus_overlaps_locus"
        and (ov.get("transform") or {}).get("relation_nature") == "structural",
        f"code={(ov.get('transform') or {}).get('predicate_code') if ov else None}")
    add("QTL 共定位：colocalized with → structural",
        bool(co) and (co.get("transform") or {}).get("predicate_code") == "locus_overlaps_locus",
        f"code={(co.get('transform') or {}).get('predicate_code') if co else None}")

    # 8. review: every record is a paraphrase, and the missing lead is a warning, not silence
    review = by[("review", NEW_VERSION, False)]
    origins = Counter((r.get("transform") or {}).get("evidence_origin") for r in review.records)
    add("综述：全部记录标 review_report", origins.get("review_report", 0) == review.counts["records"],
        f"origins={dict(origins)}")
    r040 = [w for w in review.warnings if w.get("code") == "RULE_R040"]
    cited = review.record_for(FOCUS["review_cited"])
    nocite = review.record_for(FOCUS["review_nocite"])
    add("综述：有原始线索的记录不带 R040",
        bool(cited) and (cited.get("agent") or {}).get("reported_citation_text") and not any(
            w.get("record_id") == cited["common"]["record_id"] for w in r040),
        f"citation={(cited.get('agent') or {}).get('reported_citation_text') if cited else None}")
    add("综述：缺原始线索的记录触发 R040",
        bool(nocite) and not (nocite.get("agent") or {}).get("reported_citation_text") and any(
            w.get("record_id") == nocite["common"]["record_id"] for w in r040),
        f"R040 条数={len(r040)}")

    # 9. the review queue: the new version moves informational hints out of pending
    add("正文+补充：新版待审为 0（R018 只是非阻断提示）", new_heat_sup.pending() == 0,
        f"新版 pending={new_heat_sup.pending()}, 旧版 pending={old_heat_sup.pending()}")
    add("正文输入：新版待审 ≤ 旧版待审", new_heat.pending() <= old_heat.pending(),
        f"新版 pending={new_heat.pending()}, 旧版 pending={old_heat.pending()}")

    # 10. the qualifier is carried verbatim
    hedged = by[("review", NEW_VERSION, False)].record_for(FOCUS["review_hedged"])
    add("限定语逐字保留（suggested）",
        bool(hedged) and (hedged.get("agent") or {}).get("claim_qualifier_text") == "suggested",
        f"qualifier={(hedged.get('agent') or {}).get('claim_qualifier_text') if hedged else None}")
    return out


def matrix_rows(cells: list[Cell]) -> list[dict]:
    return [{"paper": c.paper, "version": c.version, "input": "正文+补充" if c.supplement else "正文",
             "candidates": c.counts["candidates"], "records": c.counts["records"],
             "rejected": c.counts["rejected"], "pending": c.pending(),
             "informational": (c.counts.get("warnings") or {}).get("informational", 0),
             "families": codes_by_family(c),
             "codes": dict(sorted(((c.counts.get("warnings") or {}).get("by_code") or {}).items()))}
            for c in cells]


def review_queue(cells: list[Cell]) -> list[dict]:
    """One row per pending record: what an operator has to look at, and why (the manual-time column is left to
    the person doing the review — this harness records the work, not the clock)."""
    rows = []
    for c in cells:
        for r in c.records:
            if (r.get("common") or {}).get("review_status") != "pending_review":
                continue
            codes = (r.get("common") or {}).get("qc_failure_codes") or []
            rows.append({"paper": c.paper, "version": c.version, "input": "正文+补充" if c.supplement else "正文",
                         "record": (r.get("common") or {}).get("record_id"),
                         "kind": (r.get("common") or {}).get("record_kind"), "codes": "、".join(codes),
                         "quote": re.sub(r"\s+", " ", ((r.get("common") or {}).get("source_quote") or ""))[:80]})
    return rows
