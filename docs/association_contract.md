# 关联事件与序列契约（4.0.0）

本文件是 4.0.0 新增字段与记录类型的定义来源。它把“一篇论文抽一条结论”推进为：

- **association**：一行一个研究上下文（study / population / material / environment / trait / locus），携带字段级证据和缺失原因；
- **sequence**：一行一条引物、探针、扩增子或等位基因序列，保留名称、方向、用途、5′→3′ 原文和附件单元格；
- **field_evidence**：每个字段值到 PDF 页码/段落/图注或附件工作表/单元格的逐项证据；
- **source file**：正文、补充材料、引物表的文件级清单与解析状态；
- **alias candidate**：写法差异先成为候选，人工确认后才合并。

版本规则：新增记录类型、字段、词表和字段级证据属于契约新增；本仓库按项目决定发布为 **4.0.0**。旧 3.x 记录仍可由兼容的 Skill 运行时读取；新流水线以 4.0.0 解析。

## 硬规则

1. 关联事件必须带 study、population、trait、locus 和至少一条证据；缺项进入 `common.missing_fields`，不猜。
2. 不同试验、不同群体、不同环境不能合并成一个总体效应；同一 association 只描述一个研究上下文。
3. 每个关键字段值都应有 `field_evidence`；记录级 `source_quote` 不能替代字段级证据。
4. 引物/探针/扩增子/等位基因序列是独立 `sequence` 记录；不得把引物自动逆互补，也不得把引物当作育种选择标记或等位基因。
5. 序列保留原文大小写、5′→3′方向和附件单元格；只允许空白/排版规范化，并在 `primer_status` 标记。
6. `not_reported`（论文确实未报告）、`not_located`（来源中没有定位到）、`not_verified`（有但未核实）、`source_unavailable`（附件未取得）、`parse_failed`（解析失败）、`ambiguous`（来源本身有歧义）不能混用。
7. 原始突变、编辑等位基因、候选基因、QTL、QTN 分开记录；不因名称相似自动合并。
8. 别名先写 `transform.entity_alias_status: candidate`，人工确认后才可合并。
9. 3 株混池是样本/测序子样本，不是群体总量；`population_size` 只能来自明确报告。
10. 只有明确方向相反的效应才登记为冲突；不同群体、环境、处理或统计口径是上下文，不是冲突。
