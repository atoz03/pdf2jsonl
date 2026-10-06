# 生物育种 AI-Ready JSONL 规范 v2.0.0（merged）

> 面向"生物育种智能化"三大研究内容的**统一 JSONL 字段规范**，由三份项目内既有字段方案合并而成：
> **cyx v1.0.0**（文档行主记录 + 五类字段体系 + Schema/模板/示例闭环）为骨架，
> 吸收 **lyy v3.0.0**（稀疏单位行、精确定位、观测/资产/图谱转换、许可治理、TB 级实践）与 **d v2.0.0**（多组学样本与六大组学专块、统计结果、受控词表）的差异化优势。

---

## 一、合并模型：三层语义

| 层 | 载体 | 说明 |
|----|------|------|
| **L1 文档主记录** | `record_kind=document` 的 JSONL 行 | 一行=一篇文献，15 顶层块全量：文献元数据、育种实体、实验/分析/结论、观测/资产/转换、治理/溯源、智能体/技能 |
| **L2 单位行** | `record_kind ∈ {claim, observation, asset_manifest, analysis_result, tool_spec, transform}` | 稀疏行，只填本行相关块，通过顶层 `record_parent_id` + `source_locations[]` 回链 L1；**非空即入**，不做深嵌套固定行 |
| **L3 受控语义** | 枚举词表附录 A + 本体映射 | 多组学/候选基因/证据层级/许可/防泄漏等受控词表，保证跨团队可对齐 |

**16 顶层块**：`record_id · schema_version · record_kind` ＋ `record_info, doc_meta, breed_entities, relations, experiments, analyses, conclusions, observations★, assets★, transform★, pipeline, governance, provenance, agent, skill`（★=合并新增块）。

---

## 二、三方优势落位（合并对齐）

| 能力 | cyx 提供 | lyy 提供 | d 提供 |
|------|----------|----------|--------|
| **结构** | 12 块文档行骨架、实体基元、C1–C5 五类字段 | 单位行 `record_kind` 契约、稀疏/分片实践 | 样本·组织·发育、组学文库块 |
| **溯源** | `document_sections` 全局锚点、`evidence_spans` | 页码/表图/行键/列键/原句细定位 `source_locations` | `evidence_span`、验证与复制状态 |
| **知识本体** | 基因/性状/种质/品种/群体/环境/标记/QTL/病害实体 + 本体对齐 | 等位链（ref/alt/dosage/ploidy）、性状与变异 ID 映射 | 跨物种直系同源、跨组学关系 |
| **观测** | 实验内 `trait_measurements` | `observations[]`：phenotype/environment/genotype 单值观测 + normalized 值 | 统一特征接口 `feature_*` + `statistic`（contrast/效应/CI） |
| **分析建模** | 分析块（模型/参数/输入输出/拟合/验证） | `skill.method_profile`/`validation`（训练/测试/折数/防泄漏） | 统计结果块（效应方向/SE/q 值/区间） |
| **智能体** | state/hypotheses/causal/planning/memory/tool | `scientific_reasoning`（问题/发现/证据/可证伪/适用边界） | 科学发现/知识缺口/育种意义 |
| **技能化** | 卡片/工作流/工具绑定/I-O/模型画像/可视化 | `skill_registry`（接口 schema 引用、运行环境、资产引用） | 工具 I/O、验证规则、失败模式 |
| **治理质量** | governance 状态机、quality_grade、curation | license/access_level、QC 规则集、missing_fields、record_version | data_files/checksum/availability |
| **图谱与 AI-Ready** | pipeline（kg 节点、融合、更新链） | `transform`（SPO 图谱、Chunk、QA、leakage/split、许可派生） | 受控词表 |

---

## 三、五类字段 × 三研究适配

| 类别 | 主要承载 | 研究一 数据底座 | 研究二 智能体 | 研究三 技能化 |
|------|----------|----------------|----------------|----------------|
| C1 核心基础 | record_info/doc_meta/breed_entities/relations/experiments/analyses/conclusions/**observations** | 本体实例化、实体对齐、入库 | 知识状态、检索依据 | 任务卡命中、输入材料 |
| C2 知识治理 | governance/pipeline/**transform** | 图谱节点、版本演化、融合 | 记忆检索索引 | 流程版本、接口版本 |
| C3 智能体关联 | agent + **scientific_reasoning** | 抽取知识反哺 | ✔ 推理/规划/记忆/执行 | 下发工具调用 |
| C4 工具技能化 | skill + **method_profile/validation/skill_registry** | 结构化卡片沉淀 | 工具调用反馈 | ✔ 封装/编排/可视化 |
| C5 溯源质量 | provenance（+各块 evidence_spans/confidence/quality_flag） | 可信标签、质量评价 | 推理置信度加权 | 结果可信度回传 |

---

## 四、使用边界（重要约定）

1. **记录粒度**：默认产出 `document` 主记录；观测/资产/顾问/技能走单位行，不主张单行塞满全部字段。
2. **稀疏原则**：论文未报告字段省略，不用空串/`null`/猜值；`record_kind` 分支自动约束必填，缺失即不填。
3. **高维数据不内嵌**：VCF/表达矩阵/代谢物全表 → `assets[]` + `asset_schema_ref`；显著差异 feature → `observations[]`。
4. **证据分层**：GWAS/QTL/BSA-seq/表达/功能验证分级保存；关联证据不自动升级为因果（`causal_flag`）。
5. **TB 级分片**：按 `dataset_version/crop/record_kind/year` 分片；`dataset_id/dataset_version` 用于跨分片聚合。
6. **许可不推断**：`license_id`/`derivative_license_id` 不猜测版权。
7. **防泄漏**：同一 `leakage_group_id` 只落入一个 `corpus_split`。

---

## 五、文件索引

| 文件 | 说明 |
|------|------|
| `README.md` | 本文件：合并模型、优势落位、适配矩阵、使用边界 |
| `breeding_jsonl_spec_v2.md` | **master 字段字典**：16 块逐字段（路径/类型/必填/类别/来源/释义）+ 单位行契约 + 枚举词表 |
| `to_merged_mapping.md` | lyy 259 字段 & d 模板 → merged 路径**全量映射**（含取舍记录），脚本可平移 |
| `breeding_jsonl_schema_v2.json` | JSON Schema v2020-12：`record_kind` 条件必填自动约束文档行/单位行 |
| `breeding_jsonl_template_v2.json` | 全字段空模板（含数组骨架）；⚠ 骨架含空占位，过 Schema 校验报未填项属**预期** |
| `breeding_jsonl_example_v2.jsonl` | 1 条水稻 GWAS **完整填充示例**（多组学/观测/资产/转换覆盖，机器可用单行 JSONL） |
| `breeding_jsonl_example_v2.json` | 同上示例可读多行版（供人工审阅） |

原三版目录 `cyx/` `lyy/` `d/` 保持不动；v1 记录天然兼容 v2 规范（新增块均可选、Schema 半开放）。

---

## 六、快速开始

```bash
# 校验示例（0 错误为通过）
python -m jsonschema -i breeding_jsonl_example_v2.jsonl breeding_jsonl_schema_v2.json \
  --instance-format jsonl
# 或
python - <<'PY'
import json, jsonschema
schema = json.load(open('breeding_jsonl_schema_v2.json'))
for line in open('breeding_jsonl_example_v2.jsonl'):
    rec = json.loads(line)
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(rec))
    print(rec['record_id'], rec['record_kind'], 'errors=', len(errs))
PY
```

> v2.0.0 由三研究内容共用，覆盖文献解析 → 知识抽取 → 图谱/语料/QA → 训练集 → 智能体 → 工具技能化的完整链路。
