# 生物育种文献知识提取 JSONL 字段字典（master 规范）

> 配套文件：`breeding_jsonl_template.json`（空模板）、`breeding_jsonl_example.jsonl`（填充示例）、`breeding_jsonl_schema.json`（Schema）、`README.md`（总览）。

**约定**
- **类别**：`C1` 核心基础字段 · `C2` 知识治理字段 · `C3` 智能体关联字段 · `C4` 模型工具技能化字段 · `C5` 溯源质量字段。
- **适配模块**：`R1`＝研究内容一（数据治理/本体/融合）· `R2`＝研究内容二（智能体）· `R3`＝研究内容三（技能化）。标注所有直接受益模块。
- **必填**：`Y`＝必填（每记录必须有合法值）· `N`＝可选 · `C`＝条件必填（该块存在即必须）。
- **类型**：`string / int / float / number / boolean / array<T> / object / enum / any / null`。
- **通用 ID 规范**：`record_id` 使用 UUIDv4 或 `sha256(source_id+title+year)` 前 16 位；所有实体均需 `{entity_type}_id`，格式建议 `GE:2025:rice:XXX` 等带命名空间的持久标识；图谱节点 `kg_node_id` 由实体 ID 派生。
- **通用溯源**：所有实体/关系/结论均须携带 `evidence_spans[]`（数组元素：`{section_id, block_type, block_id, page, line_range, text_snippet}`）与 `confidence`（0–1），供 C5 溯源链路闭合。

---

## 1 顶层结构速查

```jsonc
{
  "record_id": "…",              // 必须
  "schema_version": "v1.0.0",    // 必须
  "record_info":  { … },         // 记录标识（类别 C1）
  "doc_meta":     { … },         // 基础文献元数据（C1）
  "breed_entities": {           // 育种实体数据（C1，多数实体嵌套 C5 溯源）
    "genes":[], "traits":[], "germplasm":[], "varieties":[], "populations":[],
    "environments":[], "markers":[], "qtls":[], "disease_pests":[], "other_entities":[]
  },
  "relations":    [ … ],         // 实体关系数据（C1）
  "experiments":  [ … ],         // 实验过程数据（C1）
  "analyses":     [ … ],         // 分析方法数据（C1）
  "conclusions":  [ … ],         // 科研结论数据（C1）
  "pipeline":     { … },         // 上下游任务关联数据（C2 为主）
  "governance":   { … },         // 知识治理字段（C2）
  "provenance":   [ … ],         // 数据质量溯源数据（C5）
  "agent":        { … },         // 智能体关联字段（C3）
  "skill":        { … }          // 模型工具技能化字段（C4）
}
```

---

## 2 `record_info` · 记录标识（C1）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 / 约束 |
|---|----------|------|------|------|------|-----------|-----------------|
| R-01 | `record_id` | string | Y | C1 | R1/R2/R3 | 全库唯一记录主键，图谱节点、跨记录引用（pipeline、fusion、conflicts）均回指此 ID | UUIDv4；或 `sha256(normalized(doi||title||year))[:16]`。去重时先归一化 |
| R-02 | `schema_version` | string | Y | C1 | R1 | 字段体系语义化版本号，支撑 Schema 演化校验 | 固定 `v1.0.0`；升级需在 governance 记录迁移 |
| R-03 | `doc_type` | enum | Y | C1 | R1 | 文献类型，决定抽取管线与卡片模板选择 | 枚举见附录 A-1；规则识别关键词（学位论文/综述/report）或 PDF 结构 |
| R-04 | `lang` | enum | Y | C1 | R1/R2 | 源文语言，决定 NLP 抽取 tokenizer 与术语词典 | `zh/en/zh_en`（双语混杂用 zh_en） |
| R-05 | `created_at` | string(datetime) | Y | C5 | R1 | 记录生成时间（ISO8601） | 管线运行时间戳 |
| R-06 | `updated_at` | string(datetime) | N | C5 | R1 | 最近一次更新（重抽/更正/融合后） | 每次写操作自动刷新 |

---

## 3 `doc_meta` · 基础文献元数据（C1）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 / 约束 |
|---|----------|------|------|------|------|-----------|-----------------|
| D-01 | `title` | string | Y | C1 | R1/R2 | 原语题名（保留原文语言） | 首屏/元数据解析 |
| D-02 | `title_zh` / `title_en` | string | N | C1 | R2/R3 | 译名/英译名，供跨语言检索与模型训练 | 规则取对应语言标题；无则不填 |
| D-03 | `authors` | array\<obj> | Y | C1 | R1 | 作者列表，含机构与通信标识 | `[{rank, name, name_id(ORCID), affiliation_name, affiliation_id(ROR/GRID), corresponding:bool}]` |
| D-04 | `affiliations` | array\<obj> | N | C1 | R1 | 机构-地市-国家 (地理可映射到 environment) | `[{name, address, country, org_id}]` |
| D-05 | `journal` | string | N | C1 | R1 | 刊物/学位授予单位/发布平台 | 元数据字段映射 |
| D-06 | `journal_meta` | object | N | C1 | R1 | 期刊分类地位（权威性→可信度先验） | `{issn, category(SCI/EI/核心/普刊), sci_quarter(Q1–Q4/NA), cas_zone(1区–4区/NA)}` |
| D-07 | `year` | int | Y | C1 | R1 | 发表/出版年份 | 文献关键时间；时序治理用 |
| D-08 | `volume` / `issue` / `pages` | string | N | C1 | R1 | 卷期页码 | 元数据映射，缺失置空 |
| D-09 | `doi` | string | N | C1 | R1 | DOI 唯一标识（去重键之一） | 正则 `10.xxxx/…`；缺失用 source_id 兜底 |
| D-10 | `url` / `pdf_path` | string | N | C1 | R1(C5) | 在线地址与本地文件 | url 元数据；pdf_path 入库统一相对路径 |
| D-11 | `abstract` | string | N | C1 | R2/R3 | 摘要原文，作为实体抽取与摘要语义向量源 | 摘要页解析 |
| D-12 | `keywords` | array\<string> | N | C1 | R1 | 关键词（含作者关键词与主题词） | 去重、小写归一 |
| D-13 | `funding` | array\<string> | N | C1 | R1 | 资助项目号，用于同团队结果互引治理 | 页脚/致谢正则 |
| D-14 | `species_list` | array\<obj> | C | C1 | R1/R2/R3 | 文献涉及物种 | `[{name(中英), ncbi_tax_id, crop_group(粮食/油料/纤维/蔬菜/畜禽/水产/园艺)}]`；`doc_type=review` 时允许空并标注 scope |
| D-15 | `field` | array\<enum> | N | C1 | R1/R2 | 育种细分领域标签，驱动模式路由 | 枚举见附录 A-2；用关键词/方法共现分类 |
| D-16 | `sources` | array\<string> | N | C5 | R1 | 采集来源渠道（数据库/爬虫/推送） | 采集管线打标 |
| D-17 | `document_sections` | array\<obj> | Y | C5 | R1/R2 | 正文分块索引，**全局溯源锚点** | `[{section_id, heading, block_type(段落/表/图/补充), block_id, page, line_range, char_start_end, text_snippet}]`；所有 evidence_spans 引用此处 section_id |
| D-18 | `section_vectors` | array\<obj> | N | C3 | R2 | 段落级语义向量（检索增强记忆） | `[{section_id, embedding_model, dim, vector[]}]`；检索时 ANN 命中 |
| D-19 | `citation_count` / `cited_by` | int / array\<string> | N | C1 | R1 | 被引数与关键被引（影响力治理） | 引文索引 API（如有） |
| D-20 | `related_docs` | array\<string> | N | C1 | R1 | 同批/互为补充文献 ID（综述引用子文献等） | pipeline 与 D-19 联动 |

---

## 4 `breed_entities` · 育种实体数据（C1 为主）

所有子块共享**实体基元**字段（E-01~E-07），再叠加各自专有字段。**实体 ID 必须全局可回指**，供 relations/experiments/analyses 引用。

### 4.1 实体基元（每个实体均含）

| # | 字段路径（子块内） | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|------------------|------|------|------|------|-----------|----------|
| E-01 | `entity_id` | string | Y | C1 | R1/R3 | 实体持久 ID，如 `gene:ric:sd1` | 命名空间:物种:名称；同名实体合并后保留多 ID 于 aliases |
| E-02 | `name` / `canonical_name` | string | Y | C2 | R1 | 展示名与**规范名**（本体对齐后） | 规范名来自本体映射，未对齐时先=name |
| E-03 | `aliases` | array\<string> | N | C2 | R1 | 别名/旧名/异体（同实异名治理核心） | 术语词典+LLM 共指消解 |
| E-04 | `ontology_id` | array\<obj> | N | C2 | R1 | 映射到公开本体概念 | `[{ontology(TO/PO/GRO/GO/KEGG/NCBITaxon/STO/自建育种本体), term_id, term_label, match_score}]` |
| E-05 | `description` | string | N | C1 | R2/R3 | 实体一句话描述，供生成式检索 | LLM 摘要源句 |
| E-06 | `confidence` | float | N | C5 | R1/R2 | 抽取置信度 0–1，下游按此加权 | PIPELINE 模板打分+交叉验证 |
| E-07 | `evidence_spans` | array\<obj> | C(core) | C5 | R1 | 溯源锚点，必须指向 D-17 的 section_id | 同通用溯源规范 |

### 4.2 `genes[]`（基因实体）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| G-01 | `gene_symbol` | string | Y | C1 | R1/R2 | 官方基因符号（水稻 `sd1`、玉米 `ZmKRN4`） | 词典+正则严格匹配，防泛化 |
| G-02 | `gene_full_name` / `description` | string | N | C1 | R1 | 全称与功能描述 | LLM 凝练 |
| G-03 | `gene_type` | enum | N | C1 | R1 | 基因类型 | `编码基因/转录因子/非编码RNA/候选基因/克隆基因/未克隆QTL区段基因` |
| G-04 | `chromosome` | string | Y | C1 | R1/R3 | 所在染色体（物种内统一写法 `chr1`/`1A`） | 正则+单位归一 |
| G-05 | `position` | object | N | C1 | R1 | 基因组位置（参考基因组版本必给） | `{ref_genome(如IRGSP1.0/B73v5), start_bp, end_bp, strand}` |
| G-06 | `annotation` | object | N | C1/R2 | R1 | 功能注释（知识溯源/机理推理） | `{go[], kegg[], interpro[], pfam[], gene_ontology_process}` |
| G-07 | `alleles` | array\<obj> | N | R1/C2 | R1/R2 | 等位变异与表型效应（分子育种的基石） | `[{allele_name, variant_type(SNP/Indel/缺失/SV), effect(有利/不利/中性), effect_value, functional_impact, source}]` |
| G-08 | `expression_pattern` | object | N | C3 | R2 | 表达组织/时期（推理上下文） | `{tissues[], stages[], up_regulated_by[], down_regulated_by[]}` |
| G-09 | `ortholog_in_model` | array\<obj> | N | C1 | R1/R2 | 模式种同源基因，跨物种知识迁移 | `[{species, gene_symbol, identity}]` |
| G-10 | `linked_traits` | array\<string> | N | C2 | R1/R2 | 关联性状（冗余字段，提升检索，正式关系见 relations） | 由 relations 反卷生成 |
| G-11 | `mutant_resources` | array\<string> | N | C1 | R1 | 突变体/转基因材料库 ID | `[{stock_id, type(突变体/过表达/敲除/互补), database(Tos17/NBRP/EMS库)}]` |

### 4.3 `traits[]`（性状实体）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| T-01 | `trait_id` | string | Y | C1 | R1/R3 | 性状持久 ID | 命名空间:trait:snake_case |
| T-02 | `trait_name` / `trait_abbr` | string | Y | C1 | R1 | 性状名与缩写（同一性状多写法治理） | 本体词表+同义词映射 |
| T-03 | `trait_category` | array\<enum> | Y | C1 | R1 | 大分类（治理/检索钻取） | 附录 A-3；可多选 |
| T-04 | `trait_ontology_id` | array\<obj> | C | C2 | R1 | 性状本体（TO/CO/PO/自建）映射 | 对齐后必填 |
| T-05 | `trait_class` | enum | N | C1/R3 | R1/R3 | 定性/定量（决定统计模型选择） | `定性/定量/定性有序/比率` |
| T-06 | `data_type` | enum | N | C4 | R3 | 表型数据类型（模型输入编码） | `连续/计数/二值/有序等级/组成成分/缺失比例` |
| T-07 | `measurement_detail` | object | N | C1 | R1/R3 | 测定细则（可复现） | `{unit, stage(生育时期), organ, method_standard, device, survey_numbers, scoring_scheme}` |
| T-08 | `direction_of_improvement` | enum | N | C3 | R2 | 育种改良方向（优化目标符号） | `越大越好/越小越好/适中值优/定向` |
| T-09 | `heritability_h2_estimate` | float | N | C1 | R1/R2 | 遗传力估值（评估改良潜力） | 原文显式的数值；缺失经 analyses 推论则标注来源 |
| T-10 | `component_of` | array\<string> | N | C2 | R1 | 构成的上位性状（难点：性状层级本体） | `产量<-穗粒数<-每穗粒数` |
| T-11 | `related_marker_genes` | array\<string> | N | C1 | R1/R2 | 关联标记/基因 ID（反卷冗余） | 由 relations 生成 |

### 4.4 `germplasm[]`（种质/育种材料）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| GR-01 | `germplasm_id` | string | Y | C1 | R1 | 材料 ID | 命名空间:germplasm:… |
| GR-02 | `germplasm_name` | string | Y | C1 | R1 | 材料名/品种名/登录号 | 词典+正则 |
| GR-03 | `accession_number` | string | N | C1/R2 | R1 | 基因库登录号（引甘蔗/IRRI/国家种质库） | `[{db, accno}]` |
| GR-04 | `species_info` | object | N | C1 | R1/R3 | 物种与倍性 | `{species, sub_species, ploidy, genomic_type(AABB/DD/AA)}` |
| GR-05 | `origin_region` | object | N | C1 | R1 | 起源/适应地域（生态型治理） | `{country, region, ecotype(籼/粳/春麦/冬麦), altitude_range}` |
| GR-06 | `pedigree_text` | string | N | C1/C2 | R1/R2 | 系谱原始文本（解析成 relations 前保留） | 原文系谱段落 |
| GR-07 | `parents` | array\<obj> | N | C1 | R1/R2 | 解析后的亲本 | `[{parent_id, parent_name, role(母本/父本/供体)}]` |
| GR-08 | `breeding_method` | string | N | C1 | R1 | 选育途径（系统选育/诱变/基因编辑等） | 原文描述 |
| GR-09 | `breeding_unit` / `breeder` | string | N | C1 | R1 | 育成单位/人（与 D-03 dc 关联治理） | 元数据 |
| GR-10 | `release_status` | object | N | C1 | R1 | 审定/登记/保护状态 | `{review_level(国审/省审/登记/未审定), year_registered, status}` |
| GR-11 | `key_traits_profile` | array\<obj> | N | C1/R2 | R1/R2 | 关键性状画像（描述性） | `[{trait_name, value, desc}]` |
| GR-12 | `latitude_longitude` | object | N | C1 | R1 | 原产地坐标（环境地理测算公用） | `{lat, lon}` |

### 4.5 `varieties[]`（品种）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| V-01 | `variety_id` | string | Y | C1 | R1 | 品种 ID | 命名空间:variety:… |
| V-02 | `variety_name` | string | Y | C1 | R1 | 品种审定名/商品名 | 词典+正则；别名冲突→治理表 |
| V-03 | `approved_number` | string | N | C2 | R1 | 审定/登记/植物新品种权号 | 正则（国审稻2021001 等） |
| V-04 | `variety_type` | enum | N | C1/R3 | R1/R2 | 品种类型（对应栽培/育种路径） | `杂交组合/常规品种/自交系/克隆家系/核心种质/审定品种` |
| V-05 | `parentage` | array\<obj> | N | C1 | R1/R2 | 亲本组成（配组信息） | `[{variety_id/name, role}]` |
| V-06 | `breeding_lines` | array\<string> | N | C1 | R1 | 衍生系/姊妹系 | 系谱展开 |
| V-07 | `release_info` | object | N | C1 | R1 | 推广与审定 | `{release_year, region_suitable[], approved_area, promotion_area_ha}` |
| V-08 | `suitable_regions` | array\<string> | N | C2 | R1/R3 | 适宜种植区（区域-环境关联治理） | 审定公告+文献 |
| V-09 | `major_traits` | array\<obj> | N | C1/R2 | R1/R2 | 品种主打性状（宣传/审定描述） | `[{trait, claim, level}]` |
| V-10 | `disease_resistance_profile` | array\<obj> | N | C1/R2 | R1/R2 | 抗性谱（病害界面） | `[{disease_name, level(高抗/中抗/感), gene_carried}]` |

### 4.6 `populations[]`（遗传群体）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| P-01 | `population_id` | string | Y | C1 | R1/R3 | 群体 ID | 命名空间:pop:… |
| P-02 | `population_name` | string | Y | C1 | R1 | 群体名/代号 | 词典 |
| P-03 | `pop_type` | enum | Y | C1 | R1/R3 | 群体类型（决定分析模型与连锁分辨率） | 附录 A-4；水稻 `自然群体/重组自交系RIL/双单倍体DH/近等基因系NIL/回交导入系/MAGIC/NAM/F2/由不完全双列杂交衍生` |
| P-04 | `parents` | array\<obj> | C`pop_type≠自然群体` | C1 | R1 | 亲本组合 | `[{pop_id/name, role}]` |
| P-05 | `population_size` | int | N | C1 | R1/R3 | 个体/家系数（模型样本量输入） | 整数 |
| P-06 | `generation` | string | N | C1 | R1 | 世代（F5、BC3F2、DH0 等） | 正则 |
| P-07 | `marker_density` | object | N | C4 | R3 | 标记密度（GWAS/GS 分辨率与 LD 依据） | `{markers_count, platform, average_distance_kb, coverage}` |
| P-08 | `construction_purpose` | string | N | C1/R2 | R1/R2 | 构建目的（QTL定位/选择/预测） | LLM 凝练 |

### 4.7 `environments[]`（环境实体，G×E 与区域适配的锚点）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| EN-01 | `env_id` | string | Y | C1 | R1/R3 | 环境 ID（一个地点×年份×季别=一个环境） | 命名空间:env:{地点}:{年季}；**多点多季必须拆分为多条环境** |
| EN-02 | `env_name` | string | Y | C1 | R1 | 环境描述（如 南京2021春） | 地点+年份 归一化 |
| EN-03 | `location` | object | Y | C1 | R1 | 站点位置（气候区映射） | `{site, province, country, lat, lon, altitude_m, ecosystem_type}` |
| EN-04 | `season` | string | N | C1 | R1 | 季别（早稻/中稻/春播…） | 术语归一 |
| EN-05 | `year` | int | Y | C1 | R1 | 试验年份 | 抽取 |
| EN-06 | `soil` | object | N | C1 | R1 | 土壤特性（地力/逆境治理） | `{soil_type, texture, ph, organic_matter, fertility_level, saline_alkali}` |
| EN-07 | `climate` | object | N | C1 | R1/R2 | 气象概况（灾害归因推理素材） | `{avg_temp_c, rainfall_mm, sunshine_h, gdd, extreme_events[]}` |
| EN-08 | `irrigation` | enum | N | C1 | R1 | 水管理 | `雨养/灌溉/旱作/渍水/水旱轮作` |
| EN-09 | `stress_conditions` | array\<obj> | N | C1/R2 | R1/R2 | 胁迫逆境条件（抗逆专章） | `[{stress_type(干旱/高温/盐碱/病虫害/冷害), severity, duration, method}]` |
| EN-10 | `cropping_system` | string | N | C1 | R1 | 种植制度（轮作/复种） | 抽取 |
| EN-11 | `env_code_in_paper` | string | N | C1 | R1 | 原文中该环境的编号（E1/E2…）溯源 | 段落正则 |

### 4.8 `markers[]`（分子标记）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| M-01 | `marker_id` | string | Y | C1 | R1/R3 | 标记 ID | 命名空间:marker:… |
| M-02 | `marker_name` | string | Y | C1 | R1 | 标记名（含探针名/芯片位点名） | 正则（RSxxx/RMxxx/Sx_xxx/等位） |
| M-03 | `marker_type` | enum | N | C1/R3 | R1/R3 | 标记分子类型（决定分析方法） | `SNP/SSR/InDel/AFLP/RAPD/CAPS/KASP/DArT/SV/CNV/GBS位点/芯片探针` |
| M-04 | `platform` / `array_name` | string | N | C4 | R3 | 检测平台与芯片名称 | `{platform(芯片/测序/GBS/KASP), array_name(如56K/55K/600K)}` |
| M-05 | `chromosome` + `position_bp` | string+int | N | C1 | R1/R3 | 染色体与物理位置（统一参照基因组） | 归一化保留 `{ref_genome}` |
| M-06 | `flanking_sequence` / `delta` | string | N | C4 | R3 | 侧翼序列（引物/PCR 兼容） | 原文序列块 |
| M-07 | `allele_frequency` | object | N | C1 | R1 | 群体内等位频率 | `{minor_allele_frequency, red_missing_rate}` |
| M-08 | `is_core_marker` | bool | N | C1 | R1 | 是否核心标记（指纹/身份证用途） | 治理标志 |
| M-09 | `linked_gene` | array\<string> | N | C2 | R1/R2 | 连锁/候选基因（marker→gene 关系） | relations 反卷 |
| M-10 | `primer` | object | N | C4 | R3/R1 | 引物序列（实验卡自动化） | `{forward, reverse, annealing_temp, product_size}` |

### 4.9 `qtls[]`（QTL/定位区间）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| Q-01 | `qtl_id` | string | Y | C1 | R1/R2 | QTL 持久 ID（同 QTL 跨文献合并成一条，ID 稳定） | 命名空间:qtl:…，candidate 合并见治理 |
| Q-02 | `qtl_name` | string | Y | C1 | R1 | QTL 名（`qLDR4.1`/`qPH3`） | 正则命名 |
| Q-03 | `chromosome` + `interval` | string+obj | Y | C1 | R1/R3 | 染色体与置信区间（cM/bp 统一） | `{unit(cM/bp), start, end, ci_type(LOD-1/2)}` |
| Q-04 | `lod` / `p_value` | number | N | C1 | R1 / R3 | 显著性统计量（阈值标注） | 原文表 |
| Q-05 | `pve` (phenotypic variance explained) | number | N | C1/R4→R3 | R1/R3 | 表型变异解释率 %，效应量排序 | 原文表/文本 |
| Q-06 | `additive_effect` / `dominance_effect` | number | N | C1/R3 | R3/R2 | 加性/显性效应（预测模型参数） | 定位结果 |
| Q-07 | `qtl_type` | enum | N | C1 | R1 | 主效/微效/环境互作 | `主效QTL/微效QTL/环境互作型/上位性QTL` |
| Q-08 | `population_used` | string | N | C1 | R1 | 定位所用群体（回指 populations） | ref P-01 |
| Q-09 | `confidence_interval` | obj | N | C1 | R1 | 置信区间 | `{start, end, unit, overlap_with, }` |
| Q-10 | `candidate_genes` | array\<string> | N | C1/R2 | R1/R2 | 候选基因 ID（从区间基因功能注释筛选） | 注释+文献证据 |
| Q-11 | `nearest_markers` | array\<string> | C | C1 | R3 | 侧翼/峰值标记（用于分子标记辅助） | 关联峰值 |
| Q-12 | `pleiotropy` | array\<string> | N | C2 | R1/R2 | 一因多效关联性状（因果模型输入） | relations 反卷+多性状共定位 |
| Q-13 | `analysis_ref` | array\<string> | N | C5 | R1 | 产出分析的 analysis_id | 回指 analyses |

### 4.10 `disease_pests[]`（病虫害实体）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| DS-01 | `disease_pest_id` | string | Y | C1 | R1 | 病虫 ID | 命名空间:pathogen:… |
| DS-02 | `disease_pest_name` | string | Y | C1 | R1 | 名称（病/虫/生理失调） | 词典 |
| DS-03 | `pathogen_info` | object | N | C1 | R1 | 病原/虫媒信息 | `{pathogen_species, type(真菌/细菌/病毒/虫害/非生物), strain_race, host}` |
| DS-04 | `symptoms` | string | N | C1 | R1/R2 | 症状描述（表型诊断） | 原文 |
| DS-05 | `resistance_sources` | array\<string> | N | C2 | R1/R2 | 已知抗源（种质/基因） | 文献综述+本体 |

### 4.11 `other_entities[]`（开放扩展实体）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| O-01 | `entity_id` | string | Y | C1 | R1 | 通用容器实体 ID | 任意命名空间 |
| O-02 | `entity_type` | enum(开) | Y | C1 | R1 | 扩展类型（不破坏 schema） | `育种技术/农艺措施/激素与代谢物/仪器设备/数据库资源/流程方法/材料批次/其他` |
| O-03 | `name` + `description` | string | Y | C1 | R1/R2 | 实体名与描述 | 同基元 |
| O-04 | `entity_attributes` | object | N | C1 | R1/R3 | **开放式键值属性**（新物种类字段自扩展区） | `{key: value}` 自由 schema，禁止重复键命名冲突 |

---

## 5 `relations[]` · 实体关系数据（C1 为主，C2 对齐信息）

每条关系一条数组元素：`{relation_id, subject{entity_id, entity_type}, object{entity_id, entity_type}, relation_type, …}`。

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| REL-01 | `relation_id` | string | Y | C1 | R1 | 关系边 ID | 命名空间:rel:… |
| REL-02 | `subject` / `object` | object | Y | C1/R2 | R1/R2 | 实体对（图谱边两端） | `{entity_id, entity_type}`；实体必须在 breed_entities 存在 |
| REL-03 | `relation_type` | enum | Y | C1 | R1/R2/R3 | 关系类型（本体关系词表） | 附录 A-5；LLM 从候选表选择 |
| REL-04 | `relation_mechanism` | enum | N | C1/R2 | R1/R2 | 遗传机制（效应类） | `加性效应/显性效应/上位效应/完全显性/不完全显性/剂量效应/未知` |
| REL-05 | `effect_direction` | enum | N | C1/R2 | R1/R2 | 效应方向（方向化推理） | `正向/负向/方向依赖环境/中性` |
| REL-06 | `relation_confidence` | float | N | C5 | R1/R2 | 边置信度（图谱边权重） | 证据数量&强度加权 |
| REL-07 | `evidence_spans` | array\<obj> | C | C5 | R1 | 证据锚点 | 同通用规范 |
| REL-08 | `supporting_method` | array\<enum> | N | C1 | R1/R3 | 支撑证据的方法学（证据等级） | `GWAS/QTL定位/连锁分析/转基因/基因编辑验证/表达分析/单倍型分析/育种实践验证/综述引用/双亲分离验证`（证据强度降序） |
| REL-09 | `ontology_relation_mapping` | object | N | C2 | R1 | 映射到关系本体（如改自自建育种本体/GO relationship） | `{relation_ontology, relationship_uri, mapping_confidence}` |
| REL-10 | `is_inferred` | bool | N | C5 | R1/R2 | 是否推理补全（非原文直引） | 规则/LLM 推断置 true，附推理依据字段 |
| REL-11 | `inferred_from` | array\<string> | N | C5 | R2 | 推理来源关系 ID 链 | 传递闭包/多跳推理记录 |
| REL-12 | `source_section` | string | N | C5 | R1 | 原文出现章节（结果/讨论/方法） | 附录 A-6 |

---

## 6 `experiments[]` · 实验过程数据（C1 为主，C4 承接卡片）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| EX-01 | `experiment_id` | string | Y | C1 | R1/R3 | 实验 ID | 命名空间:exp:… |
| EX-02 | `experiment_name` | string | Y | C1 | R1 | 实验名称 | 原文标题/首句 |
| EX-03 | `experiment_type` | enum | Y | C1 | R1 | 实验形态 | 附录 A-7（田间试验/温室/分子标记辅助选择 MAS/群体构建/基因编辑/品质测定/逆境筛选/区试…） |
| EX-04 | `experiment_objective` | string | N | C3 | R2 | 实验目的（智能体复用为规划目标） | LLM 凝练 |
| EX-05 | `materials_used` | array\<obj> | N | C1 | R1/R3 | 使用材料（种质/群体/品种/资源） | `[{kind(P-01/GR-01/V-01), record_id_ref}]`；ID 引用完整性校验 |
| EX-06 | `experimental_design` | object | C | C1/R4 | R3/R1 | 试验设计（统计效度核心） | `{design_type(附录A-8), replicates, blocks_count, plots_count, randomization_method, control(对照/标准品种), design_yield, partial_balance}` |
| EX-07 | `treatments` | array\<obj> | N | C1 | R3/R1 | 处理因素与水平 | `[{factor, level, description}]` |
| EX-08 | `env_used` | array\<string> | N | C1 | R1/R3 | 关联环境 ID 列表（E1/E2 多点） | 回指 EN-01 |
| EX-09 | `trait_measurements` | array\<obj> | C`有测定` | C1 | R1/R3 | 测定性状-方法-时机 | `[{trait_ref, measurement_time, stage, unit, device, samples, protocol_ref}]` |
| EX-10 | `data_collection` | object | N | C1 | R1 | 数据采集元信息 | `{method, instrument, timepoints[], person_role, data_num}` |
| EX-11 | `experimental_steps` | array\<obj> | N | C4 | R3 | **步骤流**（实验卡自动化的原子步） | `[{step_no, step_name, step_desc, duration, condition, tool_if_used}]` |
| EX-12 | `field_layout` | object | N | C4 | R3 | 田间布局（可视化/复现） | `{plot_size, row_spacing, plant_density, layout_type, pest_management, fertilizer_scheme}` |
| EX-13 | `experiment_notes` | string | N | C1/C5 | R1 | 异常与备注（质量信号） | 原文或人工批注 |
| EX-14 | `dataset_link` | object | N | C1 | R1/R3 | 数据产出链接 | `{dataset_id, repository, release_date, data_access}` |
| EX-15 | `experiment_card_ref` | string | N | C4 | R3 | 对应实验卡 ID（skill.experiment_cards） | 由 skill 回填方一致性检查 |

---

## 7 `analyses[]` · 分析方法数据（C1 为主，C4 承接模型参数）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| AN-01 | `analysis_id` | string | Y | C1 | R1/R3 | 分析 ID | 命名空间:ana:… |
| AN-02 | `analysis_name` | string | Y | C1 | R1 | 分析名称 | 章节标题 |
| AN-03 | `analysis_type` | enum | Y | C1 | R1/R3 | 分析大类 | 附录 A-9（GWAS/QTL定位/连锁/基因组预测/群体遗传/遗传力/方差分析/AMMI/GGE/选择信号/驯化/单倍型/LD/富集/差异表达/表型组学/荟萃分析） |
| AN-04 | `statistical_class` | enum | N | C1 | R1/R3 | 统计范式（模型族路由） | `经典统计/混合线性模型/贝叶斯/机器学习/深度学习/连锁分析/关联分析/全基因组选择/群体遗传/进化统计学` |
| AN-05 | `model_name` | string | C | C1/R4 | R3/R1 | 具体模型（GAPIT-MLM、FarmCPU、GBLUP、BayesCπ…） | 附录 A-10 候选表 |
| AN-06 | `model_equation` | string | N | C4 | R3 | 模型方程（技能卡文档） | 原文公式转换 LaTeX/MathML |
| AN-07 | `model_assumptions` | array\<string> | N | C4/R2 | R2/R3 | 模型假设（因果/统计推断判定） | LLM 推理原文方法段 |
| AN-08 | `software_tools` | array\<obj> | N | C4 | R3 | 软件与版本（可复现） | `[{tool_name, version, url, sdk, command_template}]` |
| AN-09 | `parameters` | array\<obj> | C`该方法必配参数` | C4 | R3/R1 | 参数语义化（工具参数配置/实体参数） | `[{param_name, param_type, param_value, param_default, param_range, param_meaning, is_required}]`；**为 R3 接口参数 schema 直接来源** |
| AN-10 | `inputs` | array\<obj> | N | C4 | R3 | 输入数据与格式（I/O 适配） | `[{input_name, input_kind(基因型矩阵/表型向量/协变量/亲缘矩阵/结构Q矩阵), format(VCF/HapMap/PLINK/txt…), source(id_ref), desc}]` |
| AN-11 | `outputs` | array\<obj> | N | C4 | R3/R1 | 输出与关键量 | `[{output_name, output_kind(数值/矩阵/图/表), key_value, desc, unit}]` |
| AN-12 | `significance_thresholds` | array\<obj> | N | C1 | R1/R3 | 显著性阈值（可复现判定） | `[{metric(p-value/-log10P/LO D/LRT/BIC), value, correction_method(Bonferroni/FDR/Permutation)}]` |
| AN-13 | `key_results` | object | N | C1/R2 | R1/R2/R3 | 结构化关键结果（智能体问答存档） | `{heritability, genetic_corr, var_components{}, prediction_accuracy, top_snps[], population_structure_k, ld_decay_distance_kb, effective_parents}` |
| AN-14 | `validation_design` | object | N | C4 | R3 | 验证方案（模型可信度） | `{strategy(交叉验证/独立验证/留一法), k_folds, training_set, testing_set, metric, repeats}` |
| AN-15 | `model_fit_stats` | object | N | C1/R4 | R3/R1 | 拟合指标 | `{aic, bic, loglik, rmse, r_squared, genomic_h2}` |
| AN-16 | `analysis_notes` | string | N | C5 | R1 | 分析局限/异常 | 原文讨论段负面标注 |
| AN-17 | `analysis_card_ref` | string | N | C4 | R3 | 回指技能化分析卡 | skill.analysis_cards |
| AN-18 | `experiments_used` | array\<string> | N | C1 | R1 | 所用实验 ID | 回指 EX-01 |

---

## 8 `conclusions[]` · 科研结论数据（C1 为主，C3 假设来源）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| CL-01 | `conclusion_id` | string | Y | C1 | R1/R2 | 结论 ID | 命名空间:clu:… |
| CL-02 | `conclusion_type` | enum | Y | C1 | R1 | 结论语义类型 | 附录 A-11（基因-性状关联/效应/QTL/预测模型/适应性/育种策略/多样性/驯化/抗性/品质/机理/综述归纳） |
| CL-03 | `claim_text` | string | Y | C1 | R1/R2 | 结论声明（保留原文语义） | 结果/讨论关键句抽取并改写 |
| CL-04 | `claim_zh` | string | N | C1 | R1/R2 | 中文译文 | 翻译或原文中文 |
| CL-05 | `logic_type` | enum | N | C1/R2 | R2 | 逻辑性质（工智能体推理置信保留） | `关联/因果/统计推断/经验总结/综述归纳/预测`；因果标志勿滥用 |
| CL-06 | `evidence_list` | array\<obj> | C | C5 | R1/R2 | 证据（多重交叉） | `[{evidence_type(实验/统计分析/图表/引用/专家), reference_id, strength}]` |
| CL-07 | `supporting_relations` / `supporting_analyses` | array\<string> | N | C1 | R1 | 支撑关系边/分析/实验（回指） | ID 引用 |
| CL-08 | `confidence_level` | enum | N | C5 | R1/R2 | 结论置信度 | `高/中/低`；自动用证据强度+质量评分混合计算 |
| CL-09 | `novelty` | enum | N | C2 | R1 | 新颖度（与知识库比对） | `无(重复)/低/中/高`；入库时与既有 KG 比对 |
| CL-10 | `scope_constraints` | array\<string> | N | C2/R3 | R1/R3 | 适用范围与限制（防误泛化） | `适应的品种/区域/条件` |
| CL-11 | `causal_flag` | bool | N | C3 | R2 | 是否建立因果（区别于关联） | 有基因编辑/互补/表达验证等强证据方可标 true |
| CL-12 | `contradiction_note` | string | N | C2 | R1 | 与其他结论冲突备注（融合入口） | 冲突检测→进 fuse resolving |
| CL-13 | `breeding_recommendations` | array\<obj> | N | C3/R4→R3 | R2/R3 | **育种行动建议**（智能体计划&建议卡） | `[{action(可利用基因/标记组合/配组方向/选择策略), target_trait, rational_evidence, expected_gain_level}]` |
| CL-14 | `hypothesis_refs` | array\<string> | N | C3 | R2 | 由此结论派生的假设 ID | 回指 agent.hypotheses |

---

## 9 `pipeline` · 上下游任务关联数据（C2 为主）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| PL-01 | `upstream_refs` | array\<obj> | N | C2 | R1 | 上游依赖（数据集/母实验/被引用文献） | `[{record_kind(文献/实验/数据/假设), record_id, relation(基于/引用/复现/承继), from_id}]` |
| PL-02 | `downstream_refs` | array\<obj> | N | C2/R3 | R1/R2/R3 | 下游去向（被哪些任务/文献引用） | `[{record_kind, record_id, relation}]` |
| PL-03 | `ontology_mapping` | array\<obj> | N | C2 | R1 | 实体-本体概念对齐结果（入库前必做） | `[{concept_name, ontology_id, ontology_version, match_score, mapping_status(直配/近配/新概念)}]` |
| PL-04 | `kg_node_id` | string | N | C2/R3 | R1/R3 | 建图后图谱节点 ID（与实体 ID 可互为派生） | 图谱导入时回填 |
| PL-05 | `kg_subgraph_id` | string | N | C2 | R1 | 所属子图（同一研究事件簇） | 聚类算法 |
| PL-06 | `fusion_status` | enum | N | C2 | R1 | 与其他记录的融合状态 | `独立/已并入(fusion_target)/被并入/合并/冲突待解/已消解` |
| PL-07 | `fusion_group_id` | string | N | C2 | R1 | 融合组 ID（同实异名聚类） | 实体对齐聚类结果 |
| PL-08 | `conflict_statements` | array\<obj> | N | C2 | R1/R2 | 冲突描述（跨文献对抗证据） | `[{other_record_id, topic, statement_a, statement_b, difference_reason}]` |
| PL-09 | `resolution_statement` | string | N | C2 | R1 | 消解结论与依据 | 人工评审+模型建议 |
| PL-10 | `canonical_entity_links` | array\<obj> | N | C2 | R1 | 规范实体链接（别名→规范 ID） | `[{alias, canonical_entity_id, confidence}]` |
| PL-11 | `update_chain` | array\<obj> | N | C2 | R1 | 演化链（每条记录可审计） | `[{revision_no, changed_time, change_type(重抽/更正/融合/扩展), changed_field_paths[], old_value, new_value, operator}]` |
| PL-12 | `task_association` | object | N | C2/R3/R4 | R1/R2/R3 | 下游任务使用标记 | `{tasks[知识图谱构建/实体对齐/冲突消解/知识补全/智能体检索/模型训练/工具编排], priority_level}` |

---

## 10 `governance` · 知识治理字段（C2）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| GV-01 | `ontology_ref` | array\<obj> | C`R1必填` | C2 | R1 | 所引本体与版本清单 | `[{ontology_name, version, source_url, namespace}]` |
| GV-02 | `knowledge_units` | array\<obj> | N | C2 | R1 | 可独立治理的知识单元（图谱抽象） | `[{unit_id, unit_type(实体/关系/结论/卡片), ontology_concept, internal_id_ref}]` |
| GV-03 | `curation_status` | enum | Y | C2 | R1 | 策展状态机 | `原始抽取/机器清洗/人工审核/已发布/已过期/已废弃` |
| GV-04 | `curation_history` | array\<obj> | N | C2 | R1 | 策展轨迹 | `[{time, operator, action, note}]` |
| GV-05 | `domain_tags` | array\<enum> | N | C2 | R1/R3 | 领域标签（任务路由/权力分配） | 附录 A-2 复用 + 开放标签 |
| GV-06 | `technical_scope` | array\<enum> | N | C2 | R1/R3 | 技术层次标签 | `常规育种/分子标记辅助/双单倍体/转基因/基因编辑/全基因组选择/智能育种/大数据` |
| GV-07 | `quality_grade` | enum | C`审核后` | C2 | R1 | 综合质量分级（入库放行） | `A(可直接入库)/B(可入库需核验)/C(待补抽)/D(废弃)`；由 provenance 质量分计算 |
| GV-08 | `consistency_checks` | array\<obj> | N | C2 | R1 | 一致性检查结果 | `[{check_name, result(pass/fail/warn), detail}]` |
| GV-09 | `duplicates_group` | string | N | C2 | R1 | 去重簇 ID（与重查后的其他记录同簇） | 指纹+语义去重 |
| GV-10 | `freshness_level` | enum | N | C2 | R1 | 时效水平（知识演化决策） | `新(3年内)/活跃/过时占位` |
| GV-11 | `retention_policy` | string | N | C2 | R1 | 保留策略（合规） | `{accessibility, archive_path, expires_at}` |
| GV-12 | `next_review_date` | string | N | C2 | R1 | 计划复核时间（周期性演化） | 基于时间治理 |
| GV-13 | `pending_updates` | array\<obj> | N | C2 | R1 | 待更新清单（演化队列） | `[{suggested_by, reason, target_field, proposed_value, status}]` |

---

## 11 `provenance` · 数据质量溯源数据（C5）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| PV-01 | `extraction` | object | Y | C5 | R1/R3 | 抽取引擎信息（可复现） | `{method(LLM抽取/规则/词典/人工/混合), pipeline_version, llm_model, llm_prompt_version, extractor_config_hash, extraction_datetime, parser_tool}` |
| PV-02 | `source_locations` | array\<obj> | Y | C5 | R1 | 全记录源文映射 | `[{section_id, block_type, block_id, page, line_range, char_span, text_snippet}]`（与实体级 evidence 互补） |
| PV-03 | `field_level_confidence` | array\<obj> | N | C5 | R1/R2 | **字段级置信度矩阵**（LLM self-check 与规则打分） | `[{field_path, confidence, basis, flags[]}]` |
| PV-04 | `quality_scores` | object | Y | C5 | R1 | 八维度质量评分（0–1 ×权重→GV-07） | `{completeness, accuracy, consistency, uniqueness, timeliness, interpretability, retrieval_ai_ready, provenance_completeness, overall}` |
| PV-05 | `verification` | object | N | C5 | R1/R2 | 人工/跨源核验 | `{status(待核验/已核验/核验失败/无需), verifier, date, notes, cross_doc_support_count}` |
| PV-06 | `conflicts` | array\<obj> | N | C5 | R1 | 冲突明细（对应 pipeline 冲突） | `[{conflict_kind(文献内/跨文献), other_record_id, statement_ref, resolution_status}]` |
| PV-07 | `corrections` | array\<obj> | N | C5 | R1 | 更正日志（可审计补救） | `[{correction_id, date, operator, original_value, corrected_value, reason, affected_fields[]}]` |
| PV-08 | `data_license` | object | N | C5 | R1 | 版权与使用限制 | `{license_name, copyright_note, allowed_usage[], restrictions}` |
| PV-09 | `integrity` | object | N | C5 | R1/R3 | 数据完整性校验 | `{record_sha256, source_file_hash, algorithm}` |
| PV-10 | `provenance_chain` | array\<obj> | N | C5 | R1 | **全链路溯源链**（采集→解析→抽取→清洗→融合→发布） | `[{hop_no, action, actor, tool, timestamp, input_ref, output_ref}]` |

---

## 12 `agent` · 智能体关联字段（C3，研究内容二）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| AG-01 | `agent_state` | object | N | C3 | R2 | 科研状态结构化转换（从文献知识到可推理状态） | `{problem_statement, state_known[], state_unknowns[], evidence_citation[], solved_problem_types[]}` |
| AG-02 | `hypotheses` | array\<obj> | N | C3 | R2 | **科学假设**（由结论/关系反生成） | `[{hypothesis_id, hypothesis_text, hypothesis_type(因果/效应方向/预测/优化/可证伪), basis_evidence[], phenotype_prediction, direction, testability_design, generation_model, status(待验证/已验证/已反驳/已采纳/供检验), refs[]}]` |
| AG-03 | `causal_model` | array\<obj> | N | C3 | R2 | **因果模型**（因果推断依据） | `[{edge_id, cause_entity_id, effect_entity_id, mechanism, confidence, evidence_ids[], is_confirmed, is_directional, mediation_entities[], moderators[](含 G×E)}]` |
| AG-04 | `reasoning_premises` | object | N | C3 | R2 | 推理前提与步链 | `{premises[], inference_type(演绎/归纳/类比/反事实), inference_steps[], conclusion_refs[], uncertainty, retrieval_keys[]}` |
| AG-05 | `planning` | array\<obj> | N | C3 | R2 | **实验计划**（任务分解） | `[{plan_id, goal, task_steps[{task_id, task_type, inputs_state_ref[], expected_output, tools_used[], dependencies[], status}], schedule, success_criteria, risk_points[]}]` |
| AG-06 | `memory` | object | N | C3 | R2 | **分层记忆**（本记录可注入的记忆单元） | `{episodic[{event_id, context, outcome, lesson}], semantic[{fact_id, fact, source_ref, confidence}], procedural[{skill_id, skill_name, condition, action, effect, success_rate}]}` |
| AG-07 | `tool_calls` | array\<obj> | N | C3/R4 | R2/R3 | 工具调用记录（智能体-工具闭环） | `[{call_id, tool_name, endpoint, params{…}, param_hash, result_summary, status, latency_ms, feedback}]` |
| AG-08 | `feedback_loop` | object | N | C3 | R2 | 策略优化反馈 | `{reward_score, policy_update, next_action_recommendation, iteration_no}` |
| AG-09 | `knowledge_state_hash` | string | N | C3 | R2 | 记忆一致性校验（状态版本对账） | sha256 of relevant fields；变更即失效 |

---

## 13 `skill` · 模型工具技能化字段（C4，研究内容三）

| # | 字段路径 | 类型 | 必填 | 类别 | 适配 | 释义与用途 | 抽取规则 |
|---|----------|------|------|------|------|-----------|---------|
| SK-01 | `skill_id` / `skill_name` | string | N | C4 | R3 | 技能标识（工作流/工具绑定主键） | 命名空间:skill:… |
| SK-02 | `skill_category` | enum | N | C4 | R3 | 技能类别（任务路由） | `基因组预测(GS)/全基因组关联分析(GWAS)/QTL定位/群体遗传分析/表型数据分析/序列处理/分子标记开发/分子设计育种/数据预处理/可视化/环境相似性/合成优化` |
| SK-03 | `experiment_cards` | array\<obj> | N | C4 | R3 | **实验卡**（可执行实验步骤定义） | `[{card_id, mission, steps[], inputs[], outputs[], parameters[], expected_results, failure_handling, alternatives[]}]` |
| SK-04 | `analysis_cards` | array\<obj> | N | C4 | R3 | **分析卡**（方法-参数-工具-输出绑定） | `[{card_id, analysis_type, model_ref, tool_bindings[], parameter_schema, io_schema, quality_checks[], outputs_spec, visualization_spec, docs_ref}]` |
| SK-05 | `hypothesis_cards` | array\<obj> | N | C4 | R3 | **假设卡**（假设包实验设计） | `[{card_id, linked_hypothesis_id, testable_predictions[], experiment_spec_ref, success_definition, metrics}]` |
| SK-06 | `workflow_orchestration` | object | N | C4 | R3 | **流程编排**（DAG 定义 / 智能编排） | `{workflow_id, workflow_name, dag_steps[{step_id, step_type, tool_ref, parameter_ref, input_ref, output_ref, depends_on[]}], execution_mode(顺序/并行/条件/循环), version, rollback_strategy}` |
| SK-07 | `tool_bindings` | array\<obj> | N | C4 | R3 | **工具标准化封装** | `[{tool_id, tool_name, interface_type(CLI/API/容器/函数/服务), spec{endpoint, method, auth}, input_schema, output_schema, parameter_schema, version, docs_url, sdk, docker_image, resource_requirement, error_handling, rate_limit}]` |
| SK-08 | `io_adapter` | object | N | C4 | R3 | 标准 I/O 适配（格式互通） | `{standard_input_formats[], standard_output_formats[], unit_conversion, missing_value_convention, sample_key_format, encoding}` |
| SK-09 | `model_profiles` | array\<obj> | N | C4 | R3 | **模型画像**（基因组预测等模型的输入输出语义） | `[{model_id, model_name, model_kind(GS/GWAS/深度学习/经典), input_spec{genotype_format, phenotype_format, covariates{}, kinship}, training_data_ref[], hyperparameters{}, validation_design, metrics{prediction_accuracy/auc/distribution}, version}]` |
| SK-10 | `result_visualizations` | array\<obj> | N | C4 | R3 | 结果可视化规范（自动出图+解释） | `[{result_id, chart_kind(曼哈顿图/QQ图/LD热图/群体结构图/双标图/表型分布图/箱线图), data_spec, annotation_spec, output_formats[](png/svg/交互html), interpretation_hints}]` |
| SK-11 | `execution_feedback` | object | N | C4 | R3 | 执行反馈与技能升级 | `{execution_records[], success_rate, avg_duration, error_logs[], optimization_suggestions[], skill_upgrade_version}` |

---

## 附录 A · 枚举词表（Schema 同步维护）

- **A-1 `doc_type`**：`journal_paper`(期刊论文) / `conference_paper` / `dissertation`(学位论文) / `experiment_report`(实验报告) / `review`(综述) / `patent`(专利) / `dataset_paper` / `technical_report` / `book_chapter` / `other`
- **A-2 `field`（育种细分领域）**：`水稻/玉米/小麦/大麦/高粱/大豆/油菜/花生/棉花/马铃薯/番茄/蔬菜作物/果树/牧草/猪/牛/羊/鸡/鸭/鱼/虾/其他`
- **A-3 `trait_category`**：`产量性状/品质性状(加工·营养)/农艺性状/生育期性状/形态性状/生理性状/抗生物胁迫(病·虫·草)/抗非生物胁迫(旱·盐·温·涝)/适应性/其他`
- **A-4 `pop_type`**：`natural_pop`(自然群体) / `F2` / `BC`(回交群体) / `RIL`(重组自交系) / `DH`(双单倍体) / `NIL`(近等基因系) / `BIL`(回交导入系) / `CSSL`(染色体片段代换系) / `MAGIC` / `NAM` / `TIL` / `异源群体/其他`
- **A-5 `relation_type`（本体关系，可扩展）**：
  `基因-控制-性状`(genotype_controls_trait) / `基因-关联-性状`(候选基因经关联证据) / `基因-互作-基因`(含上位性) / `QTL-关联-性状` / `标记-连锁-QTL` / `标记-定位-位点` / `种质-携带-基因`(germplasm_carries_allele) / `品种-源于-亲本`(variety_derived_from) / `种质-组成-群体` / `环境-影响-性状`(G×E) / `环境-调节-基因表达` / `基因-表达于-组织` / `基因-定位于-区段` / `性状-构成-上位性状` / `品种-适应于-环境/区域` / `材料-抗-病害` / `基因-介导-抗病性` / `方法-基于-群体` / `分析-产出-结论` / `结论-支持-假设` / `材料-登记于-数据库` / `同义-实体` (同实异名)
- **A-6 `source_section`**：`摘要/引言/材料与方法/结果/讨论/图表/补充材料/正文`
- **A-7 `experiment_type`**：`田间产量试验/区域试验/温室试验/大棚试验/盆栽试验/分子标记辅助选择(MAS)/群体构建/杂交配组/自交纯化/回交转育/诱变处理/基因编辑/转基因/离体组织培养/品质测定/逆境筛选(旱·盐·胁迫)/代谢组感测/根系试验/人工接种抗性鉴定/表型自动化平台/动物选育核心群/发酵饲料试验`
- **A-8 `design_type`**：`RCBD(随机完全区组)/CRD(完全随机)/split_plot(裂区)/strip_plot(条区)/alpha_lattice/augmented(增广)/incomplete_block(不完全区组)/lattice(格子)/row_column/三因素交互/相互嵌套区组/无重复/其他`
- **A-9 `analysis_type`**：`GWAS全基因组关联分析/QTL定位/连锁分析(区间作图)/基因组选择(GEBV预测)/全基因组预测/群体遗传分析/遗传力估计/遗传相关分析/方差分析(ANOVA)/AMMI/GGE双标图/连锁不平衡(LD)/单倍型分析/选择信号分析/驯化分析/差异表达/基因富集分析/网络分析/代谢路径分析/表型组学分析/亲子鉴定/亲缘分析/荟萃分析/聚类分析`
- **A-10 `model_name`（候选表）**：关联分析 `MLM/MLMM/FarmCPU/BLINK/SUPER/GLM/GEMMA-MLMA/EMMAX/ECMLM`；全基因组选择 `RRBLUP/GBLUP(single-step SBLUP)/BayesA/BayesB/BayesCπ/BayesLASSO/BayesR/弹性网络/稀疏组Lasso/随机森林/XGBoost/神经网络/深度核`；群体遗传 `STRUCTURE/ADMIXTURE/PCA/MDS/DAPC/sNMF/`；复杂
 
- **A-11 `conclusion_type`**：`基因-性状关联结论/遗传效应结论/QTL定位结论/预测模型与精度结论/品种适应性结论/育种策略建议/种质多样性结论/驯化与进化结论/抗逆性结论/品质结论/生理机理结论/综述归纳结论/方法学结论/可重复性结论`
- **A-12 `quality_grade`**：`A/B/C/D`（见 GV-07）

> 枚举词表为将 v1.0 主干；随本体建设扩展时，修改 `breeding_jsonl_schema.json` 中对应 enum 并升 minor 版本，历史记录不受破坏。
