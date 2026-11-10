# 研究视图：逐篇删减 + 全库大网 + 证据链 + 文章包 + 聚合

这一层不改变抽取契约和 `pdf2jsonl` 管线；它从已有记录派生研究人员用的视图。三个后端模块：

| 模块 | 作用 | 产物 |
|---|---|---|
| `breeding_contract.evidence_chain` | 从结论沿 `agent.evidence_record_ids` 走到结果，再沿 `skills.method_record_ids` 走到实验/方法；缺链直接标出 | 每个关系的证据链 |
| `breeding_contract.article_package` | 一篇论文 = 正文 + 图 + 表 + Supplement + 数据/代码声明 + 许可；给出 `complete / partial / unverified / not_submitted` | 文章包清单 |
| `breeding_contract.aggregate` | 跨文按规范实体 + 谓语聚类，保留全部证据；识别方向冲突；给 A/B/C 置信和依据 | 关系总表、冲突表、证据表 |

`scripts/network_view.py` 把三者组合成页面数据；`scripts/make_network_dashboard.py` 生成 `dashboard.html`。

## 视图模式

- **逐篇查看（默认）**：左侧选论文，右侧只显示该论文的“表型—基因—种群”关系，不显示基因—基因等其他关系（只计数）。每条关系展示完整证据链：结论 → 数据/结果 → 实验/方法；每条节点带原文引文、章节、页码、图/表、Supplement 和统计量。
- **展开全库大网**：跨论文合并同一关系；同一关系在多篇论文中出现时，证据逐条保留，不重复计数；表格显示置信 A/B/C、证据链状态和冲突数。

## 人工复核

逐篇视图页头的 **人工复核（N）** 按钮打开复核面板，列出这篇论文所有 `pending_review` 记录，包括不在三元关系里的记录（会标注“其他关系”）。流程：

1. 填写复核人姓名（保存在本机浏览器）。
2. 每条记录选择 **通过 / 驳回 / 退回补证**；驳回和退回必须填写复核意见。
3. 决定先保存在浏览器 localStorage；点“导出复核决定”下载 JSON。
4. 由后端应用到记录：

```bash
bdc review apply out/paper.jsonl paper.review_decisions.json --out out/reviewed
```

后端只移动 `common.review_status` 和 `common.review_note`，内容、证据和 `qc_failure_codes` 原样保留；`expert_approved` / `rejected` 只能由此入口写入，模型复核不会产生专家结论。输出为 `<stem>.reviewed.jsonl` 和 `<stem>.review.json`。

## 文章包状态

| 状态 | 条件 |
|---|---|
| `complete` | 正文解析成功；正文引用的 Supplement 条目在已提供文件中找到；没有缺失的 part，也没有“有文件但没有文本层”的 part |
| `partial` | 正文/引用项缺失、Supplement 未提供、或已提供但无文本层 |
| `unverified` | 正文没有可检索文本，无法判断 |
| `not_submitted` | 没有输入文件 |

数据/代码可用性、引用/许可字段是**建议项**：未检测到只写入 `notes`，不把文章包降为 `partial`。`cited_not_detected` 表示“正文引用了但文本层没有检测到图注/表注”，不是“不存在”。

## 置信与冲突

置信规则是确定性的：

- **A**：至少 2 篇独立论文、每条证据链都有结果和实验/方法、没有未消解冲突、文章包完整；
- **B**：论文数不足 2，但证据链完整、文章包完整、无冲突；
- **C**：存在方向冲突，或证据链不完整，或证据来自不完整文章包。

方向冲突只在记录明确给出相反方向时报告（如 `locus_increases_trait` 与 `locus_decreases_trait`，或 `relation_polarity` / `effect_direction` 相反）。不同群体、环境、统计口径本身不是冲突，保留为上下文。

## 生成

```bash
# 当前仓库有运行目录时
python scripts/make_network_dashboard.py

# 同时导出派生 JSON，供另一个前端或分析脚本使用
python scripts/make_network_dashboard.py --json-out out/research_view.json

# 四篇合成论文的 demo（含一篇复现论文，用来演示跨文去重）
python scripts/make_network_demo.py
```

`dashboard.html` 是本地快照，链接到仓库内 PDF；页面不写回任何记录。
