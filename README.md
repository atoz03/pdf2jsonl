# 🌾 pdf2jsonl

**简体中文** | [English](README.en.md)

![稻穗、发芽的论文与笑脸数据卡片：育种论文长成可追溯的 JSONL 数据](docs/assets/readme-hero.svg)

从一篇育种论文出发，整理出**有原文证据、字段含义明确、能够回查的 JSONL 数据**；同一份数据再直接派生出
知识图谱、语料、问答种子和关系表。本仓库维护育种文献数据契约，并提供抽取、校验、导入和派生工具。

<table>
<tr>
<td align="center" width="25%">
<a href="https://atoz03.github.io/pdf2jsonl/papers.html"><img src="docs/assets/icons/paper.svg" width="54" height="54" alt="论文看板"><br><strong>论文看板</strong></a><br><sub>看论文，也看每次运行</sub>
</td>
<td align="center" width="25%">
<a href="https://atoz03.github.io/pdf2jsonl/fields.html"><img src="docs/assets/icons/fields.svg" width="54" height="54" alt="字段图鉴"><br><strong>字段图鉴</strong></a><br><sub>含义、功能标签与示例</sub>
</td>
<td align="center" width="25%">
<a href="https://atoz03.github.io/pdf2jsonl/pipeline.html"><img src="docs/assets/icons/pipeline.svg" width="54" height="54" alt="管线地图"><br><strong>管线地图</strong></a><br><sub>从 PDF 到原子记录</sub>
</td>
<td align="center" width="25%">
<a href="#quick-start"><img src="docs/assets/icons/extract.svg" width="54" height="54" alt="开始抽取"><br><strong>开始抽取</strong></a><br><sub>用一篇论文跑起来</sub>
</td>
</tr>
</table>

> 🌱 仓库负责数据规范，Skill 负责抽取流程，每条记录都带着它的出处。

## ✨ 能做什么

- **把论文抽成带证据的记录。** `pdf2jsonl` Skill 把一篇论文（正文加补充材料）抽成原子 JSONL 记录，
  每个取值都带页码和原文引文；未通过检查的候选连同原因被拒收，不会写成正式记录。
- **按版本化的契约校验。** 字段、受控词表、画像和跨字段规则定义在同一份字段目录中，并冻结为带哈希的版本；
  每条记录按它自己声明的版本校验。
- **导入已有数据。** `bdc migrate` 把 legacy、omics、merged 三种已有格式导入为同样的记录，
  被拒绝和未转换的内容都会报告，不静默丢弃。
- **派生下游视图。** `bdc derive` 从同一批记录派生关系表、关系语句、三元组与属性图、研究流程、
  带标注的语料和问答种子。
- **按证据给关系定级。** 关系带有性质（因果、相关等）和结合证据类型得出的结论强度；
  措辞本身不会把相关升级为因果。
- **分级复核。** 确定性检查、独立复核者（`bdc verify`）和人工决定（`bdc review apply`）依次把
  `review_status` 从 `pending_review` 推进到 `expert_approved` 或 `rejected`。
- **查看结果。** 静态站点展示契约、字段和每次示例运行；逐篇研究视图展示证据链、文章包和跨文置信。

**当前版本：** 数据契约 **3.8.0** · `bdc` 工具 **1.1.0** · Skill 运行时 **0.6.0**。
各版本改了什么：[CHANGELOG](CHANGELOG.md) · [版本历史](docs/releases/README.md)。

## 🧭 一次抽取，多种下游

```
论文 PDF ── pdf2jsonl ──┐                          ┌─► 关系语句 · 三元组 · 属性图（知识图谱）
（正文 + 补充材料）     ├─► 记录（JSONL，带钩子）──┼─► 研究流程（问题 → 假设 → 步骤 → 结果）
已有数据 ── bdc migrate ┘        bdc derive        ├─► 带实体偏移标注的语料
                                                   ├─► 完形问答种子
                                                   └─► 关系表（CSV）
```

记录是下游共用的中间格式，下游不必对原文再解析一遍。**模型只抄写**关系的主语、谓词和宾语原文；
**管线来计算**实体类型、偏移、主宾语角色，以及由线索词表确定性得到的关系代码；**人工与下游再补充**
审核后的谓词、实体对齐和问答，各有对应字段，不与抽取结果混写。记录没有的钩子，派生结果里就没有对应的行，
不做猜测。设计说明见 [`docs/downstream.md`](docs/downstream.md)。

[![育种文献数据管线：规范发布、文献抽取、证据校验、存量迁移、JSONL 输出与下游派生](docs/diagrams/pipeline.svg)](docs/diagrams/pipeline.svg)

[HTML 图源](docs/diagrams/pipeline.html) · [SVG 原图](docs/diagrams/pipeline.svg) · [架构说明](docs/architecture.md)

<a id="quick-start"></a>

## 🌱 快速开始

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e '.[dev]'   # 或：pip install -e '.[dev]'
make check        # bdc check --strict
make test         # pytest
```

### 🧪 抽取论文（agent 模式）

```bash
skills/pdf2jsonl/scripts/pdf2jsonl paper.pdf --profile pdf_extraction --schema-version latest --out-dir out/
# 退出码 3：out/paper.work/ 中已生成 brief.md、pages.txt、candidate.schema.json、request.json
# 按 brief.md 编写 out/paper.work/candidates.json，然后再次运行同一命令：
skills/pdf2jsonl/scripts/pdf2jsonl paper.pdf --profile pdf_extraction --schema-version latest --out-dir out/
```

输出包括 `paper.jsonl`（记录）、`paper.validation.json`（校验报告，含证据链审计、研究流程结构和来源完整性）、
`paper.errors.jsonl`（被拒绝的候选，不会写入正式记录）和 `paper.manifest.json`（规范标识、输入哈希、后端、
环境及输出哈希）；加上 `--bundle` 还会输出 `paper.bundle.json`。其他接入方式包括 `--candidates file.json`、
`--backend mock` 和 `--backend module:callable`。

论文有多个文件时一次处理：加上 `--supplement paper_supplement.pdf`（可重复）；附录用
`--supplement appendix.pdf:appendix` 标明，证据随之写明所在部分，每个文件各有一条资产记录。

在本仓库使用 Claude Code 时，`.claude/skills/pdf2jsonl` 已链接到 `skills/pdf2jsonl`。
用户级安装可将 `~/.claude/skills/pdf2jsonl` 软链接到同一目录。

### Python API

```python
from breeding_contract import resolve_schema, load_profile, load_field_catalog, validate_record

rc = resolve_schema("latest")                  # 也可指定 "3.0.0" 或 "dev"（未发布的工作目录）
profile = load_profile("pdf_extraction", "latest")
catalog = load_field_catalog("3.8.0")
result = validate_record(record)               # 按记录声明的版本校验
result.valid, [i.to_dict() for i in result.errors]
```

## 🔁 常用流程

<a id="import"></a>

### 导入已有数据

已经按其他格式整理的数据通过导入器进入同一份契约，不另设第二套 Schema。每个导入器对应一份逐叶映射
（`mappings/`），产出与抽取结果相同的原子记录，并经过同样的校验。

| 命令 | 输入 | 示例 |
| --- | --- | --- |
| `bdc migrate legacy` | 一篇论文一行的文档级 JSONL | `sources/legacy_v1/breeding_jsonl_example.jsonl` |
| `bdc migrate omics` | 多组学元数据模板的填写实例 | `examples/migration/omics_v2/synthetic_deg_instance.json` |
| `bdc migrate merged` | 文档加观测、样本、测定和资产数组，按显式 ID 关联 | `sources/merged_v2/breeding_jsonl_example_v2.json` |

```bash
bdc migrate merged sources/merged_v2/breeding_jsonl_example_v2.json --out out/merged --page-offset 2220
```

`--page-offset` 把出版页码换算成 PDF 物理页（`2220` 只适用于这个示例，已是物理页码时填写 `0`）。
导入的记录一律为 `pending_review`。说明见[导入与派生视图](docs/migration.md)和[来源分析](docs/source_analysis.md)。

### 派生、复核与人工决定

```bash
bdc derive out/paper.jsonl --out derived/                       # 关系表、三元组、属性图、研究流程、语料、问答
bdc verify tasks out/paper.jsonl --out review/                  # 生成给独立复核者的任务
bdc verify apply out/paper.jsonl review/paper.verify.verdicts.json --out review/
bdc review apply out/paper.jsonl decisions.json --out out/reviewed   # 写回人工决定
```

复核与人工决定只改复核字段，不改内容。见[质量与复核](docs/review.md)和[研究流程](docs/workflow.md)。

### 查看结果

[站点](https://atoz03.github.io/pdf2jsonl/)由 `scripts/make_site.py` 根据最新发布版本和仓库内的示例生成，
随 `main` 分支自动部署：管线、合成论文的抽取演示、下游派生、论文看板、存量导入、全部字段，以及带版本历史的规范。
本地预览执行 `make site`，然后打开 `_site/index.html`。

`make dashboard` 生成 `dashboard.html`，即**研究视图**：默认逐篇查看，每篇只保留“表型—基因—种群”关系、
完整证据链和文章包；可切换到全库大网，跨文去重并显示 A/B/C 置信。页头的**人工复核（N）**面板导出复核决定，
由 `bdc review apply` 写回。完整论文看板用 `make dashboard-full`；`make network-demo` 跑四篇合成论文的 demo。
说明见 [`docs/research_view.md`](docs/research_view.md)。

### 修改规范

编辑字段目录，更新 `VERSION`，填写 `CHANGELOG.md`，然后运行：

```bash
bdc generate && bdc release && bdc check --strict && pytest
```

完整步骤见 [`docs/versioning.md`](docs/versioning.md#changing-the-contract)。Skill 无需手工修改：下次运行会解析 `latest`。

## 🛠 `bdc` 命令行

| 命令 | 用途 |
| --- | --- |
| `bdc check [--strict]` | 检查字段目录、画像、版本、文档、示例、映射及 Skill 的一致性 |
| `bdc generate [--xlsx F]` | 根据字段目录和文档示例重新生成 `docs/generated/` |
| `bdc release` | 将工作目录规范冻结到 `releases/<VERSION>`，需先填写 CHANGELOG |
| `bdc resolve [--schema-version V] [--profile P]` | 输出版本标识，默认 `latest` |
| `bdc validate FILE.jsonl` | 按每条记录声明的版本校验，并执行数据集级规则 |
| `bdc diff A B` | 比较两个版本的字段差异 |
| `bdc migrate legacy\|omics\|merged F --out DIR [--page-offset N]` | 把已有数据导入为原子记录，见[导入已有数据](#import) |
| `bdc bundle F.jsonl [--legacy-v1]` | 从原子记录派生文档级视图，或 legacy v1 布局 |
| `bdc derive F.jsonl --out DIR` | 派生关系表（CSV）、关系语句、三元组与属性图、研究流程、带标注的语料和问答种子，并记录派生来源 |
| `bdc audit F.jsonl [--json]` | 审计证据链的 Toulmin／Flavell 要素、引用闭合及复核标记，以及研究流程结构，不生成分数 |
| `bdc verify tasks\|apply F.jsonl [VERDICTS] --out DIR` | 由独立复核者做语义复核：生成复核任务，再把判定结果写入复核字段 |
| `bdc review apply F.jsonl DECISIONS --out DIR` | 应用人工/专家复核决定（通过、驳回、退回补证），只改 `review_status` / `review_note` |

`make help` 列出全部 Makefile 目标。

## 🔬 规范概览（3.8.0）

- 共 422 个字段，分为五组（`common`、`agent`、`skills`、`transform`、`omics`）。v3.0.0 的 259 个字段标记为
  `verified`，定义逐字保留；其后新增的字段标记为 `provisional`。
- 记录采用嵌套结构：`common.record_id` 对应 `{"common": {"record_id": ...}}`。
- **缺失信息直接省略**，不写 `null`、空字符串、空数组或空对象。
- 每条记录包含 `common.schema_name`、`common.schema_version`、稳定的 `common.record_id`（`rec_` 加 32 位十六进制字符）、
  来源信息（`source_id`、`source_locator`；论文证据还需页码和原文引文）以及 `review_status`。
- 可获得性代码描述数据来源方式，不是质量分数：**D** 直接抽取、**N** 标准化、**I** 人工判断、**G** 后续生成、**F** 未来来源。
- 每个字段说明键角色（`key_role`）和服务功能（`serves`），详见[字段功能说明](docs/field_functions.md)。
- 未决问题作为歧义（`AMB-…`）登记在字段目录中，不做隐式决定。

字段参考：[在线字段目录](https://atoz03.github.io/pdf2jsonl/fields.html)、[字段定义与示例](docs/generated/field_definitions.md)、
[完整字段字典](docs/generated/field_dictionary.md)（也提供 [CSV](docs/generated/field_dictionary.csv)，
运行 `bdc generate --xlsx out.xlsx` 可导出 Excel）和[按功能组织的字段表](docs/generated/field_functions.md)。

## 📚 仓库内容

| 路径 | 用途 |
| --- | --- |
| `field_catalog/field_catalog.yaml` | **规范源文件**：字段、类型、可获得性代码、规则及歧义登记 |
| `vocabularies/`、`profiles/` | 受控词表（含单位换算表）；面向不同用途的字段选择 |
| `releases/` | 冻结且经过哈希校验的规范版本；`index.json` 维护 `latest` 指针 |
| `schemas/` | 源文件（`meta/`）与运行输出（`runtime/`）的 JSON Schema |
| `mappings/`、`sources/` | 导入器映射及问题登记；不可变的原始输入（[`sources/SOURCES.md`](sources/SOURCES.md)） |
| `src/breeding_contract/` | 契约工具与 `bdc` 命令行 |
| `skills/pdf2jsonl/` | Skill 说明、抽取任务模板及运行入口 `scripts/pdf2jsonl` |
| `scripts/`、`site/` | 站点、看板、管线图与示例的生成脚本；页面模板 |
| `examples/` | 合成论文、整理后的记录、管线输出、语义复核、派生视图、导入输出及无效数据示例 |
| `docs/`、`tests/` | 说明文档与生成的参考；pytest 测试 |

## 🗂 文档导航

- [**文档索引**](docs/README.md)：所有说明与参考文件，以及新内容应当写在哪里。
- 说明：[架构](docs/architecture.md) · [版本管理](docs/versioning.md) · [下游派生](docs/downstream.md) ·
  [研究流程](docs/workflow.md) · [质量与复核](docs/review.md) · [导入与派生视图](docs/migration.md) ·
  [字段功能](docs/field_functions.md) · [来源分析](docs/source_analysis.md) ·
  [因果与相关](docs/relation_semantics.md) · [研究视图](docs/research_view.md)
- 历史：[CHANGELOG](CHANGELOG.md) 记录每个版本改了什么；[版本历史](docs/releases/README.md) 汇总日期、
  详细发布说明以及从本 README 移出的内容。

本 README 只描述项目的现状。各版本细节写进 CHANGELOG，设计细节写进 `docs/`
（见[内容放在哪里](docs/README.md#where-things-go)）。
