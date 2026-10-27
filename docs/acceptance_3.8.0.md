# 验收报告：3.8.0 回归验证

生成时间：2026-10-27 16:33　|　被测版本：3.6.0（旧）× 3.8.0（新）

按《pdf2jsonl Skill 使用反馈》的回归验证建议执行：同一批论文，分别以**正文**与**正文+补充材料**输入，对比新旧版本的抽取结果与待审项。测试夹具在 `tests/fixtures/acceptance/`，矩阵实现见 `scripts/acceptance_matrix.py`，可复跑：`python scripts/acceptance_report.py --check`。

## 一、结论：27/27 项通过

全部验收项通过。

## 二、矩阵：版本 × 输入配置

| 论文 | 版本 | 输入 | 候选 | 记录 | 拒收 | 待审 | 非阻断提示 | 待审项（按类） |
|---|---|---|---:|---:|---:|---:|---:|---|
| heat | 3.6.0 | 正文 | 19 | 14 | 5 | 4 | 0 | other ×7、source ×3 |
| heat | 3.6.0 | 正文+补充 | 19 | 20 | 0 | 1 | 0 | rule ×1 |
| gmoleo1 | 3.6.0 | 正文 | 5 | 5 | 0 | 0 | 0 | — |
| qtl_overlap | 3.6.0 | 正文 | 2 | 2 | 0 | 0 | 0 | — |
| review | 3.6.0 | 正文 | 3 | 3 | 0 | 0 | 0 | — |
| heat | 3.8.0 | 正文 | 19 | 14 | 5 | 4 | 2 | other ×7、rule ×2、source ×3 |
| heat | 3.8.0 | 正文+补充 | 19 | 20 | 0 | 0 | 3 | rule ×3 |
| gmoleo1 | 3.8.0 | 正文 | 5 | 5 | 0 | 0 | 2 | rule ×2 |
| qtl_overlap | 3.8.0 | 正文 | 2 | 2 | 0 | 0 | 0 | — |
| review | 3.8.0 | 正文 | 3 | 3 | 0 | 0 | 4 | rule ×4 |

数据来源：每格一次 `run()`，与 `pdf2jsonl` 命令行同一管线；`待审` 是 `pending_review` 记录数，`非阻断提示` 是 `counts.warnings.informational`。

## 三、验收项

| 验收项 | 结果 | 证据 |
|---|---|---|
| heat / 3.6.0 / 正文：缺材料时候选被拒（预期） | 通过 | records=14, rejected=5, pending=4, missing=['supplement'] |
| heat / 3.6.0 / 正文+补充：未拒收候选 | 通过 | records=20, rejected=0, pending=1, missing=[] |
| gmoleo1 / 3.6.0 / 正文：未拒收候选 | 通过 | records=5, rejected=0, pending=0, missing=[] |
| qtl_overlap / 3.6.0 / 正文：未拒收候选 | 通过 | records=2, rejected=0, pending=0, missing=[] |
| review / 3.6.0 / 正文：未拒收候选 | 通过 | records=3, rejected=0, pending=0, missing=[] |
| heat / 3.8.0 / 正文：缺材料时候选被拒（预期） | 通过 | records=14, rejected=5, pending=4, missing=['supplement'] |
| heat / 3.8.0 / 正文+补充：未拒收候选 | 通过 | records=20, rejected=0, pending=0, missing=[] |
| gmoleo1 / 3.8.0 / 正文：未拒收候选 | 通过 | records=5, rejected=0, pending=0, missing=[] |
| qtl_overlap / 3.8.0 / 正文：未拒收候选 | 通过 | records=2, rejected=0, pending=0, missing=[] |
| review / 3.8.0 / 正文：未拒收候选 | 通过 | records=3, rejected=0, pending=0, missing=[] |
| 旧版 3.6.0 不写 relation_resolution / claim_strength / validation_status | 通过 | 旧版记录里这些字段为空 |
| 新版 3.8.0 写出 relation_resolution 与 claim_strength | 通过 | 新版记录带判定结果与结论强度 |
| 正文输入：缺补充材料被记为 missing | 通过 | missing=['supplement'] |
| 正文+补充：来源完整 | 通过 | complete=True |
| GmOLEO1 相关性：谓词落为相关而非因果 | 通过 | predicate_code=locus_correlated_with_trait, nature=associational, strength=associational |
| GmOLEO1 过表达：因果措辞 + 未给证据 → causal_unverified | 通过 | predicate_code=locus_increases_trait, strength=causal_unverified |
| GmOLEO1 过表达：链接到互补实验 → experiment_reported | 通过 | validation_status=experiment_reported, link=['rec_4c9345ac778422e50117cd97668ffd62'] |
| 验证实验不覆盖关联证据：结论记录仍保留自己的引文与谓词 | 通过 | 结论记录与实验记录并存，链接只是引用 |
| 无验证候选基因：validation_status = candidate | 通过 | validation_status=candidate |
| QTL 重叠：overlapped with → structural | 通过 | code=locus_overlaps_locus |
| QTL 共定位：colocalized with → structural | 通过 | code=locus_overlaps_locus |
| 综述：全部记录标 review_report | 通过 | origins={'review_report': 3} |
| 综述：有原始线索的记录不带 R040 | 通过 | citation=Zhang et al. (2019) |
| 综述：缺原始线索的记录触发 R040 | 通过 | R040 条数=2 |
| 正文+补充：新版待审为 0（R018 只是非阻断提示） | 通过 | 新版 pending=0, 旧版 pending=1 |
| 正文输入：新版待审 ≤ 旧版待审 | 通过 | 新版 pending=4, 旧版 pending=4 |
| 限定语逐字保留（suggested） | 通过 | qualifier=suggested |

## 四、待审项明细

| 论文 | 版本 | 输入 | 记录 | 类型 | 待审原因 | 原文（截断） | 实际人工复核耗时 |
|---|---|---|---|---|---|---|---|
| heat | 3.6.0 | 正文 | `rec_eb88edbd3cdd…` | observation | CANDIDATE_LINK_UNRESOLVED、SOURCE_PART_UNAVAILABLE | A chromosome segment substitution line, SL14, showed higher survival than the re | |
| heat | 3.6.0 | 正文 | `rec_69945ca262a0…` | method | CANDIDATE_LINK_UNRESOLVED | Only recombinant plants that survived the heat treatment were advanced to the ne | |
| heat | 3.6.0 | 正文 | `rec_0944532bb7d5…` | observation | CANDIDATE_LINK_UNRESOLVED、SOURCE_PART_UNAVAILABLE | The knockout lines of HTR1 showed lower survival than WY after heat treatment (f | |
| heat | 3.6.0 | 正文 | `rec_2d21f963dafe…` | observation | CANDIDATE_LINK_UNRESOLVED、SOURCE_PART_UNAVAILABLE | HTR1 interacted with HTR2 in a split-luciferase assay (fig. S3). | |
| heat | 3.6.0 | 正文+补充 | `rec_c679c3c2c134…` | asset_manifest | RULE_R018 |  | |
| heat | 3.8.0 | 正文 | `rec_eb88edbd3cdd…` | observation | CANDIDATE_LINK_UNRESOLVED、SOURCE_PART_UNAVAILABLE | A chromosome segment substitution line, SL14, showed higher survival than the re | |
| heat | 3.8.0 | 正文 | `rec_69945ca262a0…` | method | CANDIDATE_LINK_UNRESOLVED | Only recombinant plants that survived the heat treatment were advanced to the ne | |
| heat | 3.8.0 | 正文 | `rec_0944532bb7d5…` | observation | CANDIDATE_LINK_UNRESOLVED、SOURCE_PART_UNAVAILABLE | The knockout lines of HTR1 showed lower survival than WY after heat treatment (f | |
| heat | 3.8.0 | 正文 | `rec_2d21f963dafe…` | observation | CANDIDATE_LINK_UNRESOLVED、RULE_R037、SOURCE_PART_UNAVAILABLE | HTR1 interacted with HTR2 in a split-luciferase assay (fig. S3). | |

最后一列是给复核人的：本脚本不做计时（工时需要人在屏幕前记录）。

## 五、重点复测项对照（反馈点 → 结果）

| 反馈要求复测的案例 | 夹具 | 观察到的字段 | 结论 |
|---|---|---|---|
| GmOLEO1 的相关陈述 | `gmoleo1` | `predicate_code=locus_correlated_with_trait`，nature/causal_strength=`associational` | 相关没有被升级为因果 |
| GmOLEO1 的过表达陈述 | `gmoleo1` | `locus_increases_trait`，`claim_strength=causal_unverified`，`validation_status=experiment_reported` | 因果措辞按证据分档，并链到互补实验 |
| QTL 重叠 | `qtl_overlap` | `locus_overlaps_locus`，nature=`structural` | 重叠是结构关系，不进入因果 |
| 无验证候选基因 | `gmoleo1` | `validation_status=candidate` | 候选保持候选，未被表述成已验证 |
| 带验证实验的结论 | `gmoleo1` | `agent.validated_by_record_ids` 指向方法记录，两条记录并存 | 验证证据不覆盖关联证据 |
| 综述转述 | `review` | `evidence_origin=review_report`；缺线索时 `RULE_R040` | 转述被标出，缺原始线索会提示 |

## 六、方法与限制

- 矩阵与 CLI 走同一条管线（`pdf2jsonl_skill.pipeline.run`），每格独立运行、独立输出目录；`tests/test_acceptance.py` 复用同一矩阵，所以报告与 CI 不会各说各话。
- 夹具是仓库内的合成短文（`tests/fixtures/acceptance/`），不是试点语料；它们的作用是让五个重点案例各自可断言。真实六篇论文的对照数字见 `dashboard.html`，两者互补而非替代。
- 旧版本取仓库里可解析的上一版 3.6.0（3.7.0 未进入发布索引）：它没有 `relation_resolution`、`claim_strength`、`validation_status` 与 `evidence_origin`，正好用来验证新版确实多出了这些判断。
- **人工复核耗时不在本报告内**：计时需要人在屏幕前完成，第四节的最后一列留给复核人填写；脚本只记录待审项本身（数量、类别、原因、原文），这些是可复跑的。
- 复跑：`python scripts/acceptance_report.py --check`（或 `make acceptance`）；只跑断言：`pytest tests/test_acceptance.py`。
