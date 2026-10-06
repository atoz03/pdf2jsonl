# 生物育种 AI-Ready JSONL 字段字典（merged master v2.0.0）

> 三版合并规范：**cyx v1.0.0**（文档行锚 + 五类字段体系 + 实体/溯源/智能体/技能深结构）为骨架；**lyy v3.0.0**（稀疏单位行 + 精确定位 + 观测/资产/图谱转换 + 许可治理）与 **d v2.0.0**（多组学样本/文库/六大组学专块/统计结果/受控词表）为扩展。
> 配套文件：`breeding_jsonl_template_v2.json`（空模板，含数组骨架）、`breeding_jsonl_example_v2.jsonl/.json`（水稻 GWAS 扩展示例，已 `jsonschema` 0 错误过检）、`breeding_jsonl_schema_v2.json`（JSON Schema v2020-12）、`to_merged_mapping.md`（lyy/d → merged 全量映射）、`README.md`（总览）。

**约定**
- **类别**：`C1` 核心基础 · `C2` 知识治理 · `C3` 智能体关联 · `C4` 模型工具技能化 · `C5` 溯源质量。
- **适配**：`R1`=研究一（数据治理/本体/融合）· `R2`=研究二（科学智能体）· `R3`=研究三（工具技能化）。
- **必填**：`Y` 必填 · `N` 可选 · `C` 条件必填（该块/该场景存在即必须）；单位行另有 `record_kind` 级条款。
- **来源**：`cyx` / `lyy` / `d` / `★`（合并新增或整合）。
- **类型**：`string / int / float / bool / array<T> / object / enum / null`。
- **通用 ID 规范**：`record_id` 用 UUIDv4 或 `sha256(normalized(doi||title||year))[:16]`；实体 ID `{命名空间}:{物种}:{名称}` 全局可回引；单位行以顶层 `record_parent_id` 回链文档主记录。
- **通用溯源**：实体/关系/结论/观测/资产均携带 `evidence_spans[]`（`{section_id, block_type, block_id, page, line_range, char_span, table_row_key, table_column_key, text_snippet}`）与 `confidence`(0–1)。
- **单位行最小必填**：`record_id + schema_version + record_kind + record_parent_id` + 对应内容块。

---

## 1 顶层结构速查（文档主记录 `record_kind=document`）

```jsonc
{
  "record_id": "…",
  "schema_version": "v2.0.0",   // ★ const
  "record_kind": "document",     // ★ 枚举见 §3
  "record_info":     { … },      // C1 记录标识
  "doc_meta":        { … },      // C1 文献元数据（+lyy 来源/模态/数据集键）
  "breed_entities":  {           // C1 育种实体（10 原块 + d 多组学三块）
    "genes":[], "traits":[], "germplasm":[], "varieties":[], "populations":[],
    "environments":[], "markers":[], "qtls":[], "disease_pests":[], "other_entities":[],
    "omics_samples":[], "omics_experiments":[], "cross_species":[]      // ★ d
  },
  "relations":     [ … ],        // C1（+跨组学-调控 关系类型）
  "experiments":   [ … ],        // C1
  "analyses":      [ … ],        // C1
  "conclusions":   [ … ],        // C1
  "observations":  [ … ],        // ★ lyy/d 观测行（phenotype/environment/genotype/omics_feature）
  "assets":        [ … ],        // ★ lyy 资产清单（VCF/Parquet/Zarr…）
  "transform":     { … },        // ★ lyy 图谱/语料/QA/防泄漏/许可派生
  "pipeline":      { … },        // C2 上下游任务关联
  "governance":    { … },        // C2（+access_level）
  "provenance":    { … },        // C5（+细定位/运行批次/QC 键）
  "agent":         { … },        // C3（+scientific_reasoning）
  "skill":         { … }         // C4（+method_profile/validation/skill_registry）
}
```

---

## 2 `record_info` · 记录标识（C1）

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义与约束 |
|---|----------|------|------|------|------|-----------|
| R-01 | `record_id` | string | Y | C1 | cyx/lyy | 全库唯一主键；图谱节点与跨记录引用回指 |
| R-02 | `schema_version` | string | Y | C1 | cyx/lyy | 固定 `v2.0.0`；升级需 governance 记录迁移 |
| R-03 | `record_kind` | enum | Y | C1 | lyy ★ | `document/claim/observation/asset_manifest/analysis_result/tool_spec/transform` |
| R-04 | `record_parent_id` | string | C`unit` | C5 | lyy ★ | 单位行回链的文档主记录 `record_id` |
| R-05 | `record_info.doc_type` | enum | Y | C1 | cyx | 文献类型，见附录 A-1 |
| R-06 | `record_info.lang` | enum | Y | C1 | cyx/lyy | `zh/en/zh_en`（双语 zh_en） |
| R-07 | `record_info.created_at` | string(dt) | Y | C5 | cyx | 记录生成时间 ISO8601 |
| R-08 | `record_info.updated_at` | string(dt) | N | C5 | cyx | 最近更新 |

---

## 3 文档主记录与单位行契约

| record_kind | 内容块（必填） | 定位 | 来源 |
| --- | --- | --- | --- |
| `document` | 15 顶层块全量 | 一行一篇文献，知识抽取主产出 | cyx |
| `claim` | `conclusions` | 单条可独立引用的论文结论/观测结论 | lyy |
| `observation` | `observations` | 单一样本×环境×位点×测量 的单值观测 | lyy/d |
| `asset_manifest` | `assets` | 不可变大文件/矩阵/媒体索引 | lyy/d |
| `analysis_result` | `analyses` | 单次分析运行结果 | cyx/lyy |
| `tool_spec` | `skill` | 工具/技能说明（接口/参数/验证/注册） | lyy/d/cyx |
| `transform` | `transform` | 图谱语句/语料块/QA/训练划分派生 | lyy |

抽样与分片建议（TB 级）：`common` 系按 `dataset_version/crop/record_kind/year` 分片；高维矩阵与媒体用 `assets[]` 引用，不内嵌 Base64。

---

## 4 `doc_meta` · 基础文献元数据（C1/C5）

> 列新增 `来源`；`cyx` 行为基线，`lyy/d/★` 为并入或新增。

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义与约束 |
|---|----------|------|------|------|------|-----------|
| D-01 | `title` | string | Y | C1 | cyx | 原语题名 |
| D-02 | `title_zh` / `title_en` | string | N | C1 | cyx | 译名/英译名 |
| D-03 | `authors` | array\<obj> | Y | C1 | cyx | `[{rank,name,name_id(ORCID),affiliation_name,affiliation_id,corresponding}]` |
| D-04 | `affiliations` | array\<obj> | N | C1 | cyx | 机构-地市-国家 |
| D-05 | `journal` | string | N | C1 | cyx | 期刊/学位授予单位/平台 |
| D-06 | `journal_meta` | object | N | C1 | cyx | `{issn,category,sci_quarter,cas_zone}` |
| D-07 | `year` | int | Y | C1 | cyx/lyy | 发表年份 |
| D-08 | `volume/issue/pages` | string | N | C1 | cyx | 卷期页码 |
| D-09 | `doi` | string | N | C1 | cyx/lyy | 去重键之一；缺失用 source_id 兜底 |
| D-10 | `url` / `pdf_path` | string | N | C1/C5 | cyx | 在线地址与本地相对路径 |
| D-11 | `abstract` | string | N | C1 | cyx | 摘要原文，抽取与语义向量源 |
| D-12 | `keywords` | array\<string> | N | C1 | cyx | 关键词，去重小写归一 |
| D-13 | `funding` | array\<string> | N | C1 | cyx | 资助项目号 |
| D-14 | `species_list` | array\<obj> | C | C1 | cyx | `[{name,name_zh,ncbi_tax_id,crop_group}]` |
| D-15 | `field` | array\<enum> | N | C1 | cyx | 育种细分领域，见附录 A-2 |
| D-16 | `sources` | array\<string> | N | C5 | cyx | 采集来源渠道 |
| D-17 | `document_sections` | array\<obj> | Y | C5 | cyx | **全局溯源锚点**：`[{section_id,heading,block_type,block_id,page,line_range,char_span,text_snippet}]` |
| D-18 | `section_vectors` | array\<obj> | N | C3 | cyx | 段落级语义向量 |
| D-19 | `citation_count` / `cited_by` | int / array | N | C1 | cyx | 被引数与关键被引 |
| D-20 | `related_docs` | array\<string> | N | C1 | cyx | 互补文献 ID |
| D-21 | `source_id` | string | N | C5 | lyy ★ | 跨机构稳定带命名空间的来源 ID（`doi:/sra:/urn:`） |
| D-22 | `source_type` | string | N | C1 | lyy ★ | `paper/experiment_record/tool_description…` |
| D-23 | `source_uri` | string | N | C5 | lyy ★ | 持久 URI；禁止本地路径/file: |
| D-24 | `dataset_id` / `dataset_version` | string | N | C2 | lyy ★ | TB 级分片聚合 ID 与不可变快照版本 |
| D-25 | `record_version` | int | N | C2 | lyy ★ | 同 record_id 修订序号（从 1 递增） |
| D-26 | `study_id` / `trial_id` | string | N | C2 | lyy ★ | 研究项目/地点季节组合试验 ID |
| D-27 | `data_modality` | string | N | C2 | lyy ★ | `paper/genotype/phenotype/environment/omics/image/tool` |
| D-28 | `linked_modalities` | array\<string> | N | C2 | lyy ★ | 显式关联模态代码（跨模态需可追溯） |
| D-29 | `crop_primary` | string | N | C1 | lyy ★ | 顶层作物名（映射到 species_list） |

---

## 5 `breed_entities` · 育种实体数据（C1/C2/C5）

### 5.0 实体基元（每个实体共用）

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| E-01 | `entity_id` | string | Y | C1 | cyx | 持久 ID（`命名空间:物种:名称`） |
| E-02 | `name` / `canonical_name` | string | Y | C2 | cyx | 展示名与本体对齐后规范名 |
| E-03 | `aliases` | array\<string> | N | C2 | cyx | 别名词表（同实异名治理） |
| E-04 | `ontology_id` | array\<obj> | N | C2 | cyx | `[{ontology,term_id,term_label,match_score}]`（TO/PO/GRO/GO/NCBITaxon…） |
| E-05 | `description` | string | N | C1 | cyx | 一句话描述 |
| E-06 | `confidence` | float | N | C5 | cyx | 抽取置信度 0–1 |
| E-07 | `evidence_spans` | array\<obj> | C(core) | C5 | cyx | 溯源锚点回指 `document_sections[].section_id`（§1 通用溯源含表行列键） |

### 5.1 十类核心子块（继承 cyx，字段全量保留）

| 子块 | 核心字段（示例） | 必填 | 类别 |
|------|----------------|------|------|
| `genes[]` | G-01~G-11 | `entity_id`+`gene_symbol` | C1/C2/C3/C5 |
| `traits[]` | T-01~T-11 | `entity_id`+`trait_name` | C1/C2/C3/C4/C5 |
| `germplasm[]` | GR-01~GR-12 | `entity_id` | C1/C2/C5 |
| `varieties[]` | V-01~V-10 | `entity_id`+`variety_name` | C1/C2/C5 |
| `populations[]` | P-01~P-08 | `entity_id`+`pop_type` | C1/C4/C5 |
| `environments[]` | EN-01~EN-11 | `entity_id`+`env_name`+`location`+`year` | C1/C3/C5 |
| `markers[]` | M-01~M-10 | `entity_id`+`marker_name` | C1/C2/C4/C5 |
| `qtls[]` | Q-01~Q-13 | `entity_id`+`qtl_name`+`chromosome` | C1/C2/C3/C5 |
| `disease_pests[]` | DS-01~DS-05 | `entity_id`+`disease_pest_name` | C1/C2/C5 |
| `other_entities[]` | O-01~O-04 | `entity_id`+`entity_type`+`name` | C1 |

> 全字段行级定义（含各专有字段、枚举与抽取规则）见 `cyx/breeding_jsonl_spec.md` §4.2–4.11，merged 与之一致；
> 补充两处：`genes[].candidate_status`（d 受控词表，见附录 A-13）、`qtls[].ref_genome` 与 `qtls[].interval.label`（lyy `genome_assembly`/`locus_interval_label`）。

### 5.2 `omics_samples[]` ★（d 样本/组织/发育）

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| OS-01 | `sample_id` | string | Y | C1 | d | `命名空间:sample:…` |
| OS-02 | `sample_name` / `sample_type` | string | Y | C1 | d | 样本名与类型（RNA material/DNA/单细胞…） |
| OS-03 | `biological_replicate` / `technical_replicate` | string | N | C5 | d | 重复结构 |
| OS-04 | `batch_id` | string | N | C5 | d | 批次（批次效应治理） |
| OS-05 | `sex` / `ploidy` | string | N | C1 | d | 性别/倍性 |
| OS-06 | `organ` / `tissue` / `cell_type` / `cell_state` | string | N | C1 | d | 组织与细胞背景 |
| OS-07 | `development_stage` | string | N | C1 | d | 发育阶段（生育期/细胞谱系） |
| OS-08 | `sampling_time` / `sampling_time_relative` | string | N | C5 | d | 采样时间点（UTC / 相对处理） |
| OS-09 | `material_ref` / `treatment_ref` | string | C | C1 | d/lyy | 回链 germplasm / experiments.treatments |

### 5.3 `omics_experiments[]` ★（d 组学实验/文库/参考系）

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| OE-01 | `omics_experiment_id` | string | Y | C1 | d | `命名空间:omics-exp:…` |
| OE-02 | `omics_type` | enum | Y | C1 | d | 见附录 A-7b（genomics/transcriptomics/single_cell/epigenomics/proteomics/metabolomics） |
| OE-03 | `assay_type` | string | N | C1 | d | RNA-seq/WGS/ATAC-seq/MS… |
| OE-04 | `design` | string | N | C1 | d | 组学实验设计（合并入 experiments.experimental_design 亦可） |
| OE-05 | `library_strategy/selection/layout` | string | N | C4 | d | 文库参数（可复现） |
| OE-06 | `platform` / `instrument_model` | string | N | C4 | d | 平台与机型 |
| OE-07 | `sequencing_depth` / `read_length` | string | N | C4 | d | 测序深度/读长 |
| OE-08 | `reference_genome(_version)` / `annotation_version` | string | N | C1 | d | 参考基因组与注释 |
| OE-09 | `gene_id_system` / `coordinate_system` | string | N | C1 | d | ID 体系与坐标制 |
| OE-10 | `sample_ids` | array\<string> | N | C1 | d | 引用 omics_samples |
| OE-11 | `experiment_ref` | string | N | C1 | ★ | 回链 experiments[].experiment_id |

### 5.4 `cross_species[]` ★（d 跨物种）

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| CS-01 | `ortholog_id` | string | Y | C1 | d | 直系同源关系 ID |
| CS-02 | `ortholog_species` | string | N | C1 | d | 模式种 |
| CS-03 | `orthology_type` | string | N | C2 | d | one-to-one/one-to-many… |
| CS-04 | `synteny_support` | string | N | C2 | d | 共线性支持 |
| CS-05 | `cross_species_evidence` / `ortholog_gene_ref` | string | N | C5 | d | 证据与回链基因 |

> 注：跨组学/跨物种**关系边**统一走 `relations[]`（`relation_type` 增补 `跨组学-调控`）或 `transform.graph_statements[]`。

---

## 6 `relations[]` · 实体关系数据（C1/C2/C5）

继承 cyx REL-01~REL-12（`relation_id`、`subject/object{entity_id,entity_type}`、`relation_type`、`relation_mechanism`、`effect_direction`、`relation_confidence`、`evidence_spans`、`supporting_method`、`ontology_relation_mapping`、`is_inferred`、`inferred_from`、`source_section`）。**增补**：

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| REL-13 | `relation_qualifiers` | object | N | C2 | lyy ★ | 群体/环境/时间/处理限定（关系三元组上下文） |
| REL-14 | `relation_polarity` | enum | N | C1 | lyy ★ | `增加/降低/无显著效应/未知` |
| REL-15 | `relation_evidence_type` | string | N | C5 | lyy ★ | 统计定位/表达支持/功能验证 的分级 |
| ★ | `relation_type` 新增枚举 | enum | - | C1 | d ★ | 追加 `跨组学-调控`（附录 A-5） |

---

## 7 `experiments[]` · 实验过程数据（C1/C4/C5）

继承 cyx EX-01~EX-15 全量（实验设计、处理、环境、测定、步骤流、田间布局、数据集链接、卡片回引）。合并吸收：
- lyy `sample_size`→`experiments[].materials_used[].sample_size`（可选项）
- lyy `treatment`/`control_groups`/`replicate_count`→`treatments[]` / `experimental_design.control` / `experimental_design.replicates`（结构已完备）
- lyy `observation_indicators`→`trait_measurements[]`（已完备）
- d `treatment_and_environment.*`→`environments[]` + `treatments[]`（结构化并入）

---

## 8 `analyses[]` · 分析方法数据（C1/C4/C5）

继承 cyx AN-01~AN-18 全量。双向回填兼容：
- `analyses[].parameters`（C4，R3 接口参数 Schema 直接来源）与 `skill.method_profile.parameters` **同构**（`array_parameter`）。
- `analyses[].validation_design` 与 `skill.validation` **双落**（strategy/folds/metric）。
- lyy `software_name/version`→`software_tools[]`、`significance_threshold`→`significance_thresholds[]`、`feature_count`→`skill.method_profile.feature_count`。

---

## 9 `conclusions[]` · 科研结论数据（C1/C2/C3/C5）

继承 cyx CL-01~CL-14 全量（结论类型、claim、逻辑类型、证据链、置信/新颖度、作用域、因果标志、冲突、育种建议、假设回引）。合并吸收：
- lyy `claim_id`→`conclusion_id`、`finding_text`→`claim_text`、`evidence_record_ids`→`evidence_list[].reference_id` + `supporting_relations`、`external_validity_scope`→`scope_constraints`、`conflict_record_ids`→`contradiction_note`/`pipeline.conflict_statements`。
- 单位行 `record_kind=claim` 时该块为必填内容块。

---

## 10 `observations[]` ★ · 观测数据（C1/C5，单位行 observation 内容块）

> lyy 观测测量模型 + d 统一特征/统计结果的合并接口。**高维数据不内嵌矩阵**，显著差异 feature 以行模式记录；全表走 `assets[]`。

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| OB-01 | `observation_id` | string | Y | C1 | ★ | 观测行主键 |
| OB-02 | `observation_type` | enum | Y | C1 | lyy ★ | `phenotype/environment/genotype/omics_feature` |
| OB-03 | `trait_ref` / `material_ref` / `environment_ref` | string | C | C1 | lyy | 回链 traits/germplasm/environments |
| OB-04 | `sample_ref` / `assay_ref` / `experiment_ref` / `treatment_ref` | string | N | C1 | lyy/d | 回链 omics_samples / assays / experiments |
| OB-05 | `stage` / `observation_time` | string | N | C1/C5 | lyy | 生育阶段 / 测量时间(UTC，非入库时间) |
| OB-06 | `replicate_id` / `plot_id` / `sample_size` | string/int | N | C5 | lyy | 重复/小区/样本量 |
| OB-07 | `measurement` | object | C`观测` | C1 | lyy | `{name,value,text,unit,quality_flag}`；**value/text 二选一，缺失不填 0** |
| OB-08 | `original_value` / `original_unit` | string | N | C1 | lyy | 原文原样值与单位 |
| OB-09 | `normalized_value` / `normalized_min_value` / `normalized_max_value` / `normalized_unit` | number | N | C1 | lyy | 规范化数/范围上下界/单位（范围成对） |
| OB-10 | `feature_type` / `feature_id` / `feature_name` / `feature_value` / `feature_unit` | string/number | C`omics` | C1 | d ★ | **统一特征接口**（d 核心贡献） |
| OB-11 | `statistic` | object | N | C5 | d ★ | `{contrast,effect_direction,effect_size,effect_unit,standard_error,p_value,q_value,confidence_interval,replication_status,cross_doc_support_count}` |
| OB-12 | `variant` | object | C`genotype` | C1 | d/lyy | `{chromosome,position,start_position,end_position,variant_id,variant_type,ref_allele,alt_allele,effect_allele,genotype_call,allele_frequency,minor_allele_frequency,genotype_quality,read_depth,haplotype_id,structural_variant_type,genome_assembly}` |
| OB-13 | `genotype` | object | C`genotype` | C1 | lyy | `{ploidy,call,dosage,ref_allele,alt_allele,dosage_allele,quality_flag}`；倍性以样本为准 |
| OB-14 | `omics_type` | enum | C`omics_feature` | C1 | d | 见附录 A-7b |
| OB-15 | `omics_feature` | object | N | C1 | d ★ | 组学专块细节（见下）：基因/转录/单细胞/表观/蛋白/代谢 |
| OB-16 | `confidence` / `quality_flag` | float/enum | N | C5 | cyx/lyy | 0–1 / `accepted|suspect|rejected|unreviewed` |
| OB-17 | `evidence_spans` | array\<obj> | N | C5 | cyx | 支持 §1 通用溯源规范 |

**`omics_feature`（按 omics_type 取用）**：

| omics_type | 专有键（非穷尽） | 来源 |
| --- | --- | --- |
| `transcriptomics` | gene_id, transcript_id, expression_value/unit, raw_count, log2_fold_change, base_mean, deg_status, deg_threshold, coexpression_module, gene_set, pathway_id, go_term | d |
| `single_cell` | cell_id, cell_type, cell_state, cluster_id, cell_type_annotation_method, marker_genes, n_counts, n_genes, mitochondrial_fraction, doublet_status, batch, integration_method, trajectory_method, pseudotime, cell_cell_interaction_method | d |
| `epigenomics` | epigenomic_assay, chromatin_region_id, peak_start/end, peak_signal, histone_mark, methylation_context, methylation_level, motif_id, tf_binding_candidate, linked_regulatory_gene, differential_peak_status | d |
| `proteomics` | protein_id, peptide_id, protein_abundance, protein_fold_change, protein_q_value, mass_spectrometer, proteomics_method, protein_identification_score, post_translational_modification, interaction_partner | d |
| `metabolomics` | metabolite_id, metabolite_name, database_id, chemical_formula, mz, retention_time, metabolite_abundance, metabolite_fold_change, metabolite_q_value, annotation_level, metabolic_pathway, metabolite_trait_relation | d |

---

## 11 `assets[]` ★ · 资产清单（C1/C5，单位行 asset_manifest 内容块）

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| AS-01 | `asset_id` | string | Y | C1 | lyy ★ | 资产稳定 ID |
| AS-02 | `asset_uri` | string | Y | C5 | lyy | 持久 URI；不含临时签名 |
| AS-03 | `asset_kind` | string | N | C1 | lyy | genotype_matrix/phenotype_table/image/raw_pdf/omics_matrix… |
| AS-04 | `asset_format` / `asset_compression` | string | N | C4 | lyy | VCF/BCF/Parquet/Zarr/TIFF/PDF + gzip/bgzip/zstd… |
| AS-05 | `asset_size_bytes` | int | N | C5 | lyy | 原始字节数 |
| AS-06 | `asset_sha256` | string | C`注册` | C5 | lyy | 内容校验和 |
| AS-07 | `asset_row_count` / `asset_column_count` | int | N | C2 | lyy | 第一维记录数/字段数 |
| AS-08 | `asset_schema_ref` | string | N | C4 | lyy | 高维文件字段/单位/坐标/缺失值定义的版本化引用 |
| AS-09 | `asset_accession` | array\<string> | N | C5 | d | 外部库登录号（SRA/ENA/GEO…） |
| AS-10 | `data_availability` | string | N | C2 | d/lyy | public/upon_request/restricted |
| AS-11 | `related_dataset_id` / `related_record_ids` | string/array | N | C2 | lyy | 分片聚合与回链记录 |

---

## 12 `transform` ★ · 图谱/语料/QA/防泄漏（C2，单位行 transform 内容块）

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| TR-01 | `graph_statements[]` | array | N | C2 | lyy | 三元组：`{graph_statement_id, subject_{mention,type,id}, predicate_{label,id}, object_{mention,type,id}, relation_polarity, relation_qualifiers, graph_status, entity_alignment_{status,source}, external_graph_ids, provenance_record_ids, relation_evidence_type}` |
| TR-02 | `corpus_chunks[]` | array | N | C2 | lyy | 检索块：`{chunk_id, chunk_text, chunk_page, chunk_section, chunk_start_offset, chunk_end_offset, chunk_keywords, chunk_support_ids}` |
| TR-03 | `qa_pairs[]` | array | N | C2 | lyy | 问答种子：`{qa_id, seed_question, seed_answer, answerable, support_ids, reasoning_path_ids, difficulty, answer_scope, unanswerable_reason, review_status}` |
| TR-04 | `corpus_split` | enum | N | C2 | lyy | `train/validation/test`；**同一 leakage_group 只能落入一个集合** |
| TR-05 | `leakage_group_id` | string | N | C2 | lyy | 同论文同群体聚类防泄漏分组 |
| TR-06 | `dedup_group_id` | string | N | C2 | lyy | 近重复片段聚类 |
| TR-07 | `ontology_version` | string | N | C2 | lyy/d | SPO 规范 ID 依赖的本体版本 |
| TR-08 | `derivative_license_id` | string | N | C2 | lyy | 派生许可；**不从论文公开性推断** |
| TR-09 | `transform_review_status` | string | N | C2 | lyy | 转化产物审核状态 |

---

## 13 `pipeline` · 上下游任务关联（C2）

继承 cyx PL-01~PL-12 全量（upstream/downstream、ontology_mapping、kg 节点、融合、冲突、规范链接、更新链、任务关联）。补充：`ontology_mapping[].mapping_status` 对齐 d `ontology_mapping.mapping_type/confidence/synonyms`（映射表中已并）。

---

## 14 `governance` · 知识治理字段（C2）

继承 cyx GV-01~GV-13 全量（ontology_ref、knowledge_units、curation_status 状态机、domain_tags、technical_scope、quality_grade、consistency_checks、duplicates_group、freshness_level、retention_policy、next_review_date、pending_updates）。**增补**：

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| GV-14 | `access_level` | enum | N | C2 | lyy ★ | `open/controlled/restricted` |

---

## 15 `provenance` · 数据质量溯源（C5）

继承 cyx PV-01~PV-10 全量（extraction、source_locations、field_level_confidence、quality_scores、verification、conflicts、corrections、data_license、integrity、provenance_chain）。**增补**：

| # | 字段路径 | 类型 | 必填 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|------|
| PV-11 | `source_record_id` | string | N | C5 | lyy ★ | 源系统原始行/对象 ID（幂等导入），与 record_parent_id 不混用 |
| PV-12 | `source_version` | string | N | C5 | lyy ★ | PDF 版本/数据库发布号/工具说明版本 |
| PV-13 | `extraction_run_id` | string | N | C5 | lyy ★ | 可复现抽取任务的运行 ID |
| PV-14 | `extraction.confidence` | number | N | C5 | lyy ★ | 抽取置信度 0–1 |
| PV-15 | `ingest_batch_id` / `ingested_at` | string(dt) | N | C5 | lyy ★ | 批次 ID / 首次入库时间(UTC) |
| PV-16 | `qc_rule_set_version` / `qc_failure_codes` | string/array | N | C5 | lyy ★ | 质控规则版本 / 未通过代码（不静默删除数据） |
| PV-17 | `missing_fields` | object | N | C5 | lyy ★ | `{字段→原因代码}` 缺失审计 |
| PV-18 | `source_file_asset_id` | string | N | C5 | lyy ★ | 指向来源数字版本的资产 ID（配 `assets[]`） |
| ★ | `source_locations[]` 扩展 | object | - | C5 | lyy ★ | 元素增补 `locator/table_row_key/table_column_key` 细定位 |

---

## 16 `agent` · 智能体关联字段（C3）

继承 cyx AG-01~AG-09（agent_state、hypotheses、causal_model、reasoning_premises、planning、memory、tool_calls、feedback_loop、knowledge_state_hash）。**增补 `agent.scientific_reasoning`**（吸收 lyy agent 扁平字段为结构化子对象）：

| # | 字段路径 | 类型 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|
| AR-01 | `scientific_question` | string | C3 | lyy | 论文要回答的可检验科学问题 |
| AR-02 | `finding_text` / `finding_kind` | string | C3 | lyy | 单一结果独立陈述 / `关联|预测|功能验证|机制发现` |
| AR-03 | `evidence_type` / `evidence_strength` | string | C5 | lyy | 证据类型与级别 |
| AR-04 | `supporting_evidence[]` / `contradictory_evidence[]` | array | C5 | lyy | 支持/反例证据及定位 |
| AR-05 | `hypothesis_stated` / `hypothesis_origin` | string | C3 | lyy | 作者原假设；`作者提出|抽取者归纳`（不得混同） |
| AR-06 | `candidate_mechanism` / `mechanism_entities[]` | string/array | C3 | lyy | 生物学机制与路径实体 |
| AR-07 | `causal_direction` / `association_vs_causation` | string | C3 | lyy | 作用方向；关联与因果明确区分 |
| AR-08 | `assumption_conditions[]` / `applicable_population` / `applicable_environment` | array/string | C3 | lyy | 成立前提与适用边界 |
| AR-09 | `expected_observation` / `actual_observation` | string | C3 | lyy | 预期与实际观测 |
| AR-10 | `alternative_explanations[]` / `uncertainty_note` | array/string | C3 | lyy | 竞争解释与不确定性 |
| AR-11 | `falsification_test` | string | C3 | lyy | 可证伪对照组/追加试验 |
| AR-12 | `experiment_objective` / `result_interpretation` / `breeding_relevance` / `followup_experiment` / `knowledge_gap` | string | C3 | lyy | 设计目标/解释/育种意义/后续/知识缺口 |
| AR-13 | `task_tags[]` | array | C3 | lyy | 假设生成、材料评价等任务标签 |
| AR-14 | `candidate_gene_status` | enum | C5 | lyy/d | 受控词表见附录 A-13 |
| AR-15 | `statistical_test` / `lod_score` / `pve_percent` / `effect_estimate` / `effect_unit` | string/number | C5 | lyy | 统计支撑（与 analyses/qtls 双落） |
| AR-16 | `environment_stability` / `validation_methods[]` | string/array | C5 | lyy | 跨环境稳定性与独立验证方式 |
| AR-17 | `claim_id` / `evidence_record_ids[]` | string/array | C5 | lyy | 证据链闭合检查 |
| AR-18 | `external_validity_scope` | string | C3 | lyy | 外推边界及其依据 |

---

## 17 `skill` · 模型工具技能化字段（C4）

继承 cyx SK-01~SK-11（skill 标识、三类卡片、workflow_orchestration、tool_bindings、io_adapter、model_profiles、result_visualizations、execution_feedback）。**增补三个子对象**：

### 17.1 `skill.method_profile` ★（lyy skills 方法类）

| # | 字段路径 | 类型 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|
| MP-01 | `analysis_task` / `method_category` | string | C4 | lyy | 分析任务 / 方法类别 |
| MP-02 | `method_name` / `algorithm_name` | string | C4 | lyy | 论文方法原文/实际算法 |
| MP-03 | `software_name` / `software_version` | string | C4 | lyy | 软件与版本（未报告省略） |
| MP-04 | `input_modalities[]` / `{genotype,phenotype,environment}_data_format` | array/string | C4 | lyy | 输入模态与文件格式 |
| MP-05 | `preprocessing_steps[]` / `qc_filters[]` | array | C4 | lyy | 清洗步骤与过滤规则原文 |
| MP-06 | `parameters[]` | array | C4 | lyy | `array_parameter`：与 `analyses[].parameters` 同构 |
| MP-07 | `population_structure_control` / `kinship_control` | string | C4 | lyy | 结构/亲缘修正方法 |
| MP-08 | `feature_count` | int | C4 | lyy | 实际进入模型的标记/特征数 |
| MP-09 | `significance_threshold` / `threshold_calibration` | string | C4 | lyy | 阈值表达式与确定方法 |
| MP-10 | `method_assumptions[]` / `applicability_limit` | array/string | C4 | lyy | 统计假设与适用边界 |
| MP-11 | `reproducibility_assets[]` | array | C5 | lyy | 代码/数据/补充材料（引用 assets[]） |
| MP-12 | `genotyping_method` / `phenotyping_method` / `target_variable` | string | C4 | lyy | 分型/表型方法；目标性状 |
| MP-13 | `output_artifacts[]` / `output_fields[]` | array | C4 | lyy | 输出产物与关键列 |
| MP-14 | `workflow_steps[]` | array | C4 | lyy | 有序分析步骤（与 skill.workflow_orchestration 互用） |

### 17.2 `skill.validation` ★（lyy 验证/防泄漏）

| # | 字段路径 | 类型 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|
| SV-01 | `training_population` / `training_set_size` / `test_set_size` | string/int | C4 | lyy | 训练群体与集大小 |
| SV-02 | `strategy` / `folds` | string/int | C4 | lyy | 交叉/外部验证，折数 |
| SV-03 | `split_basis` | string | C4 | lyy | 按年份/群体/环境分割原则（防泄漏） |
| SV-04 | `random_seed` | int | C4 | lyy | 论文报告种子 |
| SV-05 | `metrics[]` | array | C4 | lyy | `[{name,value,unit}]` 指标 |

### 17.3 `skill.skill_registry` ★（lyy 技能注册/接口）

| # | 字段路径 | 类型 | 类别 | 来源 | 释义 |
|---|----------|------|------|------|------|
| SR-01 | `skill_spec_id` / `skill_spec_version` | string | C4 | lyy | 可调用技能规范 ID/接口版本 |
| SR-02 | `tool_description_uri` | string | C4 | lyy | 工具 Markdown 说明引用 |
| SR-03 | `input_schema_ref` / `output_schema_ref` / `parameter_schema_ref` | string | C4 | lyy | 正式 I/O/参数结构引用 |
| SR-04 | `input_asset_refs[]` / `output_asset_refs[]` | array | C4 | lyy | 运行输入/输出资产（引用 assets[]） |
| SR-05 | `runtime_environment_ref` | string | C5 | lyy | 容器镜像摘要或环境锁定文件 |

---

## 18 AI-Ready 校验规则（入库前）

1. **Schema 校验**：每条记录对 `breeding_jsonl_schema_v2.json`（Draft 2020-12）执行 validate。
2. **record_kind 分支**：document 必须含 15 顶层块；单位行必须含 `record_parent_id` 与对应内容块（Schema allOf 自动 enforce）。
3. **ID 引用完整性**：`relations/experiments/observations` 引用的实体 ID 须在 `breed_entities` 存在；单位行 `record_parent_id` 须指向已有 document `record_id`。
4. **证据链闭合**：`conclusions.evidence_list[].reference_id`、`transform.graph_statements[].provenance_record_ids` 指向的记录须存在。
5. **数值合规**：`measurement.value` 缺失不得填 0；`normalized_min/max_value` 成对；`dosage ≤ ploidy`。
6. **许可不推断**：`license_id`/`derivative_license_id` 不从论文公开性猜测。
7. **防泄漏**：同一 `leakage_group_id` 只落入一个 `corpus_split`。

---

## 附录 A · 枚举词表（与 Schema 同步维护）

- **A-1 `doc_type`**：`journal_paper`/`conference_paper`/`dissertation`/`experiment_report`/`review`/`patent`/`dataset_paper`/`technical_report`/`book_chapter`/`other`
- **A-2 `field`**：水稻/玉米/小麦/大麦/高粱/大豆/油菜/花生/棉花/马铃薯/番茄/蔬菜作物/果树/牧草/猪/牛/羊/鸡/鸭/鱼/虾/其他
- **A-3 `trait_category`**：产量性状/品质性状(加工·营养)/农艺性状/生育期性状/形态性状/生理性状/抗生物胁迫(病·虫·草)/抗非生物胁迫(旱·盐·温·涝)/适应性/其他
- **A-4 `pop_type`**：`natural_pop`/`F2`/`BC`/`RIL`/`DH`/`NIL`/`BIL`/`CSSL`/`MAGIC`/`NAM`/`TIL`/异源群体/其他
- **A-5 `relation_type`**（cyx 23 项 + 跨组学-调控）：
  基因-控制-性状(`genotype_controls_trait`)/基因-关联-性状/基因-互作-基因(含上位性)/QTL-关联-性状/标记-连锁-QTL/标记-定位-位点/种质-携带-基因/品种-源于-亲本/种质-组成-群体/环境-影响-性状(G×E)/环境-调节-基因表达/基因-表达于-组织/基因-定位于-区段/性状-构成-上位性状/品种-适应于-环境/材料-抗-病害/基因-介导-抗病性/方法-基于-群体/分析-产出-结论/结论-支持-假设/材料-登记于-数据库/同义-实体 **/跨组学-调控**（d）
- **A-6 `source_section`**：摘要/引言/材料与方法/结果/讨论/图表/补充材料/正文
- **A-7 `experiment_type`**：cyx 22 项（田间产量试验/区试/温室/大棚/盆栽/MAS/群体构建/杂交配组/自交纯化/回交转育/诱变/基因编辑/转基因/离体培养/品质测定/逆境筛选/代谢组感测/根系试验/人工接种抗性鉴定/表型自动化平台/动物选育核心群/发酵饲料试验）
- **A-7b `omics_type`** ★(d)：`genomics/transcriptomics/single_cell/epigenomics/proteomics/metabolomics`
- **A-8 `design_type`**：RCBD/CRD/split_plot/strip_plot/alpha_lattice/augmented/incomplete_block/lattice/row_column/三因素交互/嵌套区组/无重复/其他
- **A-9 `analysis_type`**：cyx 23 项（GWAS/QTL/连锁/GS/全基因组预测/群体遗传/遗传力/遗传相关/ANOVA/AMMI/GGE/LD/单倍型/选择信号/驯化/差异表达/富集/网络/代谢路径/表型组学/亲子鉴定/亲缘/荟萃/聚类）
- **A-10 `model_name`**：cyx 候选表（MLM/MLMM/FarmCPU/BLINK/SUPER/GEMMA/EMMAX；RRBLUP/GBLUP/Bayes 族/弹性网络/Lasso/随机森林/XGBoost/神经网络；STRUCTURE/ADMIXTURE/PCA…）
- **A-11 `conclusion_type`**：基因-性状关联/遗传效应/QTL定位/预测模型精度/品种适应性/育种策略建议/种质多样性/驯化进化/抗逆性/品质/生理机理/综述归纳/方法学/可重复性
- **A-12 `effect_direction` / `relation_polarity`** ★(lyy/d)：`增加/降低/无显著效应/未知`
- **A-13 `candidate_gene_status`** ★(d 受控词表)：`proximity_only`(仅邻近)/`author_proposed`(作者提出)/`expression_supported`(表达支持)/`fine_mapped`(精细定位)/`functional_validated`(功能验证)/`field_validated`(田间验证)
- **A-14 `quality_flag`** ★(lyy)：`accepted/suspect/rejected/unreviewed`
- **A-15 `variant_type`**：SNP/InDel/缺失/SV/CNV/其他（与 cyx marker_type 互补）

> 枚举为 v2.0.0 主干；扩展按 minor 升级，同步改 `breeding_jsonl_schema_v2.json` 对应 enum，历史记录不受破坏。

---

## 附录 B · 三类字段体系与三研究适配（与 README 详表相映）

- **C1 核心基础**：record_info/doc_meta/breed_entities/relations/experiments/analyses/conclusions/**observations**（研究一）
- **C2 知识治理**：governance/pipeline/**transform**（研究一；图谱/语料/QA/防泄漏）
- **C3 智能体关联**：agent + scientific_reasoning（研究二）
- **C4 模型工具技能化**：skill + method_profile/validation/skill_registry（研究三）
- **C5 溯源质量**：provenance（含各块内嵌 evidence_spans/confidence/quality_flag）（研究一数据治理底座）

**研究适配**
- 研究一（数据底座）：doc_meta/breed_entities/relations + governance/pipeline + provenance + transform 图谱
- 研究二（智能体）：agent（state/hypothesis/causal/planning/memory/tool）+ scientific_reasoning + observations 证据
- 研究三（技能化）：skill（cards/workflow/tool/io/model + method_profile/validation/registry）+ analyses 参数 + assets I/O
- 横切：assets 供 I/O、licensing、TB 分片；observations 供下游建模与 QA；transform 供 GraphRAG/训练集。

---

*merged master v2.0.0 字段字典。字段归属最终以 `breeding_jsonl_schema_v2.json` 与 `to_merged_mapping.md` 为准。*
