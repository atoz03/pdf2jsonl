# RBL1 案例：真实论文 + 引物附件

本文件说明 4.0.0 的 RBL1 参考案例，以及它如何把 11.06 反馈中的“关联事件、字段级证据、序列、上下文、缺失语义、别名”落成数据。

## 输入

| 文件 | 角色 | 说明 |
|---|---|---|
| `qt2321j386.pdf` | 正文 | eScholarship 公开存档版，37 页；SHA256 `323646482dd6a7536dbdcf8a23a3f61cbddd964c3bb15a65de90a4443aac3812` |
| `examples/rbl1/primers.csv` | 引物表 | Supplementary Table 2 的 6 行转写；每行带 `Sheet1!A4:B4` 这类单元格定位。也支持直接传入原始 `.xlsx`，由 `openpyxl` 按单元格坐标生成 locator。 |

原 XLSX 链接、PDF 链接和哈希写入 `source_manifest.json`。PDF 不随仓库分发；测试在有 PDF 时校验哈希，没有时跳过 PDF 专项检查。

## 运行

```bash
bdc rbl1 --pdf /path/to/qt2321j386.pdf --primers examples/rbl1/primers.csv --out out/rbl1_case_final
```

只跑序列/记录的 smoke test 可以省略 `--pdf`。输出：

- `source_manifest.json`、`source_files.csv`
- `records.jsonl`、`associations.jsonl`、`sequences.jsonl`、`sources.jsonl`
- `associations.csv`、`populations.csv`、`materials.csv`、`loci.csv`、`sequences.csv`
- `field_evidence.csv`、`aliases.csv`、`triples.jsonl`
- `rbl1_case.json`：校验结果与计数

生成自包含的 HTML 预览（无外部依赖，可直接双击打开）：

```bash
python scripts/make_network_dashboard.py --rbl1-case out/rbl1_case_final --out dashboard.html
# 或：make dashboard-rbl1
```

页面包含关联事件卡片（可展开字段级证据）、引物序列表、字段证据过滤、图谱边、来源清单和校验结果。

## 多文聚合 demo

```bash
make rbl1-aggregate     # 在 RBL1 之外加入 4 篇明确标注的合成论文
make dashboard-rbl1     # 生成带独立“多文聚合”入口的 dashboard.html
```

聚合按 **trait + locus** 合并：同一关系跨论文保留所有上下文和证据；只有明确方向相反才登记冲突。
合成论文用于测试 A/B/C 置信和冲突，不冒充真实论文：

- RBL1–lesion mimic：原论文 + 独立重复 + 冲突报告 → **C**（存在方向冲突）
- RBL1Δ12–multipathogen resistance：原论文 + 独立重复 → **A**
- RBL1–plant height：单篇完整上下文 → **B**

`bdc aggregate-associations` 也可以直接对任意 4.0.0 association JSONL 生成
`association_aggregate.json`。

真实论文面板见 [examples/rice_stress_panel/README.md](../examples/rice_stress_panel/README.md)：
13 篇水稻抗逆/抗病论文，`make dashboard-panel` 生成论文—性状关系图和多文聚合。

## 记录模型

- `association`：一行一个研究上下文。RBL1 案例有 3 行：
  - `A_RBL1_01` 连锁/混池测序（M3 分离材料；原 29 bp 缺失）
  - `A_RBL1_02` 功能互补（RBL1 为因果基因）
  - `A_RBL1_03` 基因编辑（RBL1Δ12；田间/多病原）
- `sequence`：一行一条引物；6 条分别带名称、角色、5′→3′ 原文、方向、用途和附件单元格。
- `field_evidence`：每个字段值到 PDF 页/段落或 CSV 单元格的逐项证据。
- `asset_manifest`：正文/引物表的角色、状态、URL、哈希。

## 关键语义

| 要求 | 实现 |
|---|---|
| 原始突变 vs 编辑等位基因 | `A_RBL1_01` 的 `locus_id=urn:rbl1:gene:RBL1` + `alternate_allele=rbl1 (29 bp deletion)`；`A_RBL1_03` 的 `locus_id=urn:rbl1:allele:RBL1-delta12` + `alternate_allele=RBL1Δ12 (12 bp deletion)`，两条关联不合并 |
| 3 株混池 ≠ 群体总量 | 关联只写 `population_name` / `population_type`，不写 `population_size`；缺失原因 `not_reported` |
| 坐标未核实 | 不填 `locus_interval_*` / `genome_assembly`；`missing_fields` 使用 `not_verified` |
| 引物方向 | `CAPS-RBL1-R` 等反向引物保留原文 5′→3′，不做逆互补 |
| 别名 | `CoRBL1-F/R` 带 `transform.entity_synonyms`（如 `CORBL1F`）和 `entity_alias_status: candidate`；不自动合并 |
| 字段级证据 | `common.field_evidence` 每条包含 field、file_id、locator、quote；PDF 有 page，CSV 有 sheet/cell |
| 下游上下文 | `triples.jsonl` 每条边带 `association_id`、`population_id`、`environment_id`、`evidence_ids` |

## 校验

`rbl1_case.json` 的 `checks` 包含：

- 6 条序列数量、逐字符一致与 IUPAC 字符合法；
- 6 个单元格定位一致；
- 3 条关联；
- 原始/编辑等位基因分开；
- 未填 `population_size`；
- 坐标缺失使用 `not_verified`；
- 别名候选存在；
- 每条关联都有字段级证据；
- PDF 页码与字段证据片段可回查（有 PDF 时）；
- PDF 哈希（有 PDF 时）；
- 所有记录通过 4.0.0 `association_extraction` 画像校验。

## 边界

- 本阶段附件获取是**手工/半自动**：调用者提供 PDF 和 CSV，模块登记来源、哈希和状态；不从出版社自动下载。
- 真实 PDF 的引用和页码由人工核对；`field_evidence` 的 quote 是定位片段，不是全文摘录。
- 该案例是垂直切片，不覆盖所有论文类型；QTL/GWAS、自然群体和多环境效应需要在同一模型上继续扩充。
