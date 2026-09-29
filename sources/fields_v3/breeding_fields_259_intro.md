# 生物育种 JSONL 259 字段最终版

## 文件定位

本文件对应当前项目已经验证的 v3.0.0 字段基线，共 **259 个不重复逻辑字段**。它是完整字段目录，适合长期数据治理、跨来源汇交、课题二科学智能体、课题三技能封装，以及知识图谱、GraphRAG、语料、问答和指令微调数据的统一输入。

四组字段属于同一份稀疏 JSONL 契约，不要求每一行填满全部字段：

| 字段组 | 数量 | 主要用途 |
| --- | ---: | --- |
| `common` | 127 | 来源、作物、种质、环境、测量、资产、质量和版本治理 |
| `agent` | 46 | 课题二的科学问题、证据链、假设、实验设计、结果解释和反馈 |
| `skills` | 46 | 课题三的分析任务、输入输出、参数、工作流、验证和技能注册 |
| `transform` | 40 | 知识图谱、语料块、问答、推理路径、泄漏控制和许可派生 |

## 记录粒度

- `claim`、`observation`、`method`：一条可独立定位的论文结论、观测或方法证据。
- `phenotype_observation`、`environment_observation`、`genotype_observation`：一个材料/样本在环境、位点或测量维度上的单值观测。
- `asset_manifest`：PDF、图像、VCF、Parquet、Zarr 等不可变资产的索引。
- `analysis_result`、`tool_spec`：分析结果或课题三工具说明。

## 填写原则

1. 所有发布行保留 `common.record_id`、`schema_version`、`record_kind`、`source_id`、`source_type`、`source_locator`、`extraction_method`、`review_status` 和 `crop_name`。
2. 论文记录补充 `source_title`、物理 `source_page` 和最小 `source_quote`；表图数值使用页码、表号、行列键定位。
3. 来源标识使用 DOI、数据库注册号、持久 URI 或命名空间 ID，不写盘符、本机路径、`file:` URI 或压缩包 `member:`。
4. 数值字段使用 JSON number/integer，并保留原文值与单位；范围拆成上下界，无法换算时不强行标准化。
5. GWAS、QTL、BSA-seq、表达差异和功能验证分层保存；关联证据不能自动升级为因果结论。
6. 大文件和媒体不内嵌 Base64，使用 `asset_uri`、`asset_sha256` 和 `asset_schema_ref` 引用。
7. `D/N/I/G/F` 表示直接抽取、标准化、人工判断、后续生成和未来来源，不是质量分数。

## 与课题二、课题三的关系

- 课题二主要读取 `common + agent`，用于知识状态、假设卡、实验设计卡、结果分析卡和证据约束。
- 课题三主要读取 `common + skills`，用于 GWAS、基因组预测、QTL、群体遗传和 BSA-seq 等工具的标准输入输出、参数和验证。
- 图谱和训练派生主要读取 `common + transform`，要求保留条件限定、证据 ID、来源位置、训练划分和授权信息。

## TB 级使用边界

259 字段是逻辑数据字典，不是单行列数要求。生产数据建议按 `dataset_version/crop/record_kind/year` 分片，单行只保存事实、观测、来源和资产索引，高维矩阵与媒体保留原格式。

详细字段表见 [breeding_fields_259_final.md](breeding_fields_259_final.md)。