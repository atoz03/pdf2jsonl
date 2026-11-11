# 4.0.0 — 关联事件、字段级证据与 RBL1 案例

4.0.0 是数据契约的 4.0.0 发布，不是 UI 版本号。它把 RBL1 反馈里的“关联事件 + 上下文 + 字段级证据 +
序列 + 来源清单”落成契约字段、记录类型、词表、画像、规则和一个可运行的案例命令。

## 新增

- 记录类型 `association`、`sequence`。
- 字段：`association_kind`、`locus_id`、`locus_type`、`sequence_record_ids`、`primer_name`、
  `primer_role`、`primer_sequence`、`primer_direction`、`primer_use`、`primer_source_locator`、
  `primer_status`、`field_evidence`、`source_file_role`、`source_file_status`、`source_file_url`、
  `transform.entity_alias_status`、`transform.entity_alias_of`。
- 词表：`association_kind`、`locus_type`、`sequence_role`、`sequence_direction`、`sequence_status`、
  `source_file_role`、`source_file_status`、`entity_alias_status`；缺失原因新增 `source_unavailable`、
  `parse_failed`、`not_verified`、`ambiguous`。
- 规则 R041–R043：关联事件必须带研究、群体、位点、类型、性状、字段级证据；序列必须带名称、5′→3′
  原文、角色、方向和附件定位。
- 画像 `association_extraction`。
- `bdc rbl1`：手工附件阶段的可复现案例，读取 PDF + CSV/XLSX，输出 6 条引物序列、3 条关联、五张表、
  字段级证据、triples 和校验报告。说明见 `docs/rbl1_case.md`。
- 多文聚合：`bdc aggregate-associations` 和 `association_aggregate.py` 按 trait + locus 跨论文合并
  association 事件，保留群体/环境上下文，只在明确方向相反时登记冲突，并给出 A/B/C 置信与依据。
- `dashboard-rbl1` 的 dashboard 增加独立的“多文聚合”入口；点击展开全库论文—性状图，并解释不同论文
  为什么能共享同一性状、位点是否相同。`make rbl1-aggregate` 生成 4 篇明确标注的合成论文，用来测试
  独立重复、方向冲突和 A/B/C。
- 真实论文面板：`examples/rice_stress_panel/` 收录 13 篇水稻抗逆/抗病论文的 page-1 curated association；
  `make dashboard-panel` 生成论文—性状关系图，并按 trait + locus 聚合。

## 未做

- 附件自动下载/发现：本阶段要求调用者提供 PDF 和引物表；自动发现下一阶段再做。
- 真实论文的自动关联抽取：案例模块接受已核对的关联定义；通用模型抽取仍需在同一画像上继续补
  candidate prompt/评测。
- 复杂 QTL/GWAS 坐标、单倍型和多环境效应的完整规则：现有字段和 `locus_type` 已保留入口，规则待
  真实论文批次扩充。

## 兼容性

新增字段、记录类型和词表是 additive；3.x 记录仍按声明的 3.x 契约校验。Skill runtime 支持 3.x 和
4.x。没有字段或代码被删除。
