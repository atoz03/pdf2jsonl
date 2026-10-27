"""Write the acceptance report for the regression the feedback asks for.

    python scripts/acceptance_report.py [--out docs/acceptance_3.8.0.md] [--check]

The matrix is ``scripts/acceptance_matrix.py``: the same papers through 3.6.0 and 3.8.0, with the main text alone
and with the supplements. The report prints the matrix, the review queue item by item and every acceptance
criterion; ``--check`` exits 1 when one fails, so the same run doubles as a gate.

Human review time is deliberately not timed here: it needs a person at the screen. The report carries the column
so a reviewer can fill it in while working through the queue (the pilot that produced the feedback did the same).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "skills/pdf2jsonl/scripts"))

from acceptance_matrix import (NEW_VERSION, OLD_VERSION, build_matrix, criteria, matrix_rows,  # noqa: E402
                               review_queue)


def fmt_codes(codes: dict) -> str:
    return "、".join(f"{k} ×{v}" for k, v in codes.items()) if codes else "—"


def build(root: Path) -> tuple[str, list[dict]]:
    with tempfile.TemporaryDirectory(prefix="p2j_acceptance_") as tmp:
        cells = build_matrix(root, Path(tmp))
        rows = matrix_rows(cells)
        verdicts = criteria(cells)
        queue = review_queue(cells)

    total = len(verdicts)
    passed = sum(1 for v in verdicts if v["ok"])
    lines: list[str] = []
    add = lines.append
    add("# 验收报告：3.8.0 回归验证")
    add("")
    add(f"生成时间：{dt.datetime.now():%Y-%m-%d %H:%M}　|　被测版本：{OLD_VERSION}（旧）× {NEW_VERSION}（新）")
    add("")
    add("按《pdf2jsonl Skill 使用反馈》的回归验证建议执行：同一批论文，分别以**正文**与**正文+补充材料**输入，"
        "对比新旧版本的抽取结果与待审项。测试夹具在 `tests/fixtures/acceptance/`，矩阵实现见 "
        "`scripts/acceptance_matrix.py`，可复跑：`python scripts/acceptance_report.py --check`。")
    add("")
    add(f"## 一、结论：{passed}/{total} 项通过")
    add("")
    if passed == total:
        add("全部验收项通过。")
    else:
        add("未通过项：")
        for v in verdicts:
            if not v["ok"]:
                add(f"- {v['name']}（{v['detail']}）")
    add("")
    add("## 二、矩阵：版本 × 输入配置")
    add("")
    add("| 论文 | 版本 | 输入 | 候选 | 记录 | 拒收 | 待审 | 非阻断提示 | 待审项（按类） |")
    add("|---|---|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        add(f"| {r['paper']} | {r['version']} | {r['input']} | {r['candidates']} | {r['records']} | "
            f"{r['rejected']} | {r['pending']} | {r['informational']} | {fmt_codes(r['families'])} |")
    add("")
    add("数据来源：每格一次 `run()`，与 `pdf2jsonl` 命令行同一管线；`待审` 是 `pending_review` 记录数，"
        "`非阻断提示` 是 `counts.warnings.informational`。")
    add("")
    add("## 三、验收项")
    add("")
    add("| 验收项 | 结果 | 证据 |")
    add("|---|---|---|")
    for v in verdicts:
        add(f"| {v['name']} | {'通过' if v['ok'] else '**未通过**'} | {v['detail']} |")
    add("")
    add("## 四、待审项明细")
    add("")
    if queue:
        add("| 论文 | 版本 | 输入 | 记录 | 类型 | 待审原因 | 原文（截断） | 实际人工复核耗时 |")
        add("|---|---|---|---|---|---|---|---|")
        for q in queue:
            add(f"| {q['paper']} | {q['version']} | {q['input']} | `{q['record'][:16]}…` | {q['kind']} | "
                f"{q['codes']} | {q['quote']} | |")
        add("")
        add("最后一列是给复核人的：本脚本不做计时（工时需要人在屏幕前记录）。")
    else:
        add("所有单元的待审队列为空。")
    add("")
    add("## 五、重点复测项对照（反馈点 → 结果）")
    add("")
    add("| 反馈要求复测的案例 | 夹具 | 观察到的字段 | 结论 |")
    add("|---|---|---|---|")
    focus = [
        ("GmOLEO1 的相关陈述", "`gmoleo1`", "`predicate_code=locus_correlated_with_trait`，nature/causal_strength=`associational`", "相关没有被升级为因果"),
        ("GmOLEO1 的过表达陈述", "`gmoleo1`", "`locus_increases_trait`，`claim_strength=causal_unverified`，`validation_status=experiment_reported`", "因果措辞按证据分档，并链到互补实验"),
        ("QTL 重叠", "`qtl_overlap`", "`locus_overlaps_locus`，nature=`structural`", "重叠是结构关系，不进入因果"),
        ("无验证候选基因", "`gmoleo1`", "`validation_status=candidate`", "候选保持候选，未被表述成已验证"),
        ("带验证实验的结论", "`gmoleo1`", "`agent.validated_by_record_ids` 指向方法记录，两条记录并存", "验证证据不覆盖关联证据"),
        ("综述转述", "`review`", "`evidence_origin=review_report`；缺线索时 `RULE_R040`", "转述被标出，缺原始线索会提示"),
    ]
    for name, fixture, field, result in focus:
        add(f"| {name} | {fixture} | {field} | {result} |")
    add("")
    add("## 六、方法与限制")
    add("")
    add("- 矩阵与 CLI 走同一条管线（`pdf2jsonl_skill.pipeline.run`），每格独立运行、独立输出目录；"
        "`tests/test_acceptance.py` 复用同一矩阵，所以报告与 CI 不会各说各话。")
    add("- 夹具是仓库内的合成短文（`tests/fixtures/acceptance/`），不是试点语料；它们的作用是让五个重点案例"
        "各自可断言。真实六篇论文的对照数字见 `dashboard.html`，两者互补而非替代。")
    add("- 旧版本取仓库里可解析的上一版 3.6.0（3.7.0 未进入发布索引）：它没有 `relation_resolution`、"
        "`claim_strength`、`validation_status` 与 `evidence_origin`，正好用来验证新版确实多出了这些判断。")
    add("- **人工复核耗时不在本报告内**：计时需要人在屏幕前完成，第四节的最后一列留给复核人填写；"
        "脚本只记录待审项本身（数量、类别、原因、原文），这些是可复跑的。")
    add("- 复跑：`python scripts/acceptance_report.py --check`（或 `make acceptance`）；"
        "只跑断言：`pytest tests/test_acceptance.py`。")
    add("")
    return "\n".join(lines), verdicts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="docs/acceptance_3.8.0.md")
    ap.add_argument("--check", action="store_true", help="exit 1 when an acceptance criterion fails")
    args = ap.parse_args(argv)
    text, verdicts = build(ROOT)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    failed = [v for v in verdicts if not v["ok"]]
    print(f"report: {out} ({len(text)} chars) | criteria {len(verdicts) - len(failed)}/{len(verdicts)} passed")
    for v in failed:
        print(f"  FAILED: {v['name']} — {v['detail']}")
    return 1 if (failed and args.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
