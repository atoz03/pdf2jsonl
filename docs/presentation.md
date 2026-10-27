# 展示规则：实体、验证状态与限定语

本文件是**界面契约**：凡是从记录派生的列表（论文看板 `site/pages/papers.html`、后续任何同类视图），
必须把下面四件事直接显示在列表行里，不能只放在详情弹窗或导出文件里。`bdc check` 会检查看板模板是否
实现了这几条（`check_presentation`），删掉对应的列或标签会让 CI 失败。

## 1. 实体必须与它的类型一起显示

记录里的每个实体提及都要带上**类型**，否则 QTN、QTL 和候选基因在界面上长得一样，读者会把三者混为一谈：

- 类型来自字段本身：`common.qtn_names` → QTN，`common.qtl_names` → QTL，`common.gene_names` → 基因，
  `common.trait_names` → 性状，`common.marker_names` → 标记，`common.germplasm_names` → 种质，
  `common.parent_names` → 亲本，`common.population_name` → 群体，`common.species_name` → 物种；
- 已有 `transform.entity_links[].entity_type` 时以它为准（那是管线按引文锚定的类型）；
- 关系语句的主语与宾语同样带类型（关系表用 `typedMention`）。

禁止的写法：只显示 `AX-157439837`、`qPH7.1`、`Rsv4` 而不标 QTN / QTL / 基因。
**候选基因永远是基因**，不因为论文里叫它 QTN 就改标。

## 2. 验证状态是一个独立列

`transform.validation_status` 只有两个值，必须显式显示：

| 值 | 显示 | 含义 |
|---|---|---|
| `candidate` | 候选 | 论文没有给出验证该结论的实验记录 |
| `experiment_reported` | 已提供验证实验 | 记录链接到论文自己报告的验证实验（`agent.validated_by_record_ids`） |

"候选"不是缺陷，也不能被省略成空白——空白会让读者以为这条结论已验证。没有该字段的记录显示 `—`，与
"候选"区分开。

## 3. 原文限定语必须逐字显示

作者自己的限定措辞（may、might、suggest、putative、likely、potential、可能、推测……）要显示在列表行里：

- 来源字段：`agent.claim_qualifier_text`（逐字），逐字引用原文，不改写成"可能"；
- `transform.relation_assertion_mode = hedged` 时同时给出"限定表述"标记；
- 类型是 `condition` / `study_design` 的字段（适用群体、环境、处理）**不是**限定语，不要混为一谈。

## 4. 结论强度与判定结果同样可见

- `transform.claim_strength`：因果措辞按证据类型分档（有干预证据 / 仅表达支持 / 仅统计定位 / 未给依据），
  与"性质"分开显示；
- 关系未编码时的原因（`transform.relation_resolution`：多码打平 / 无线索词 / 原文否定）与覆盖率必须可见，
  否则"未判定"会退化成一个无法行动的词。

## 落地位置

| 规则 | 实现 | 检查 |
|---|---|---|
| 实体类型 | `site/pages/papers.html`：`ENTITY_LABEL`、`entityCell`、`typedMention`、记录表"实体"列 | `check_presentation` 要求这些标记存在 |
| 验证状态 | 记录表"验证"列（`validationCell`） | 同上 |
| 限定语 | 记录表"限定语"列（`qualifierCell`） | 同上 |
| 结论强度与判定 | 记录表"结论强度"列、"关系"页签的强度列与判定行 | 同上 |

改动这条规则时：先改本文件与模板，再让 `bdc check` 通过；两边必须一致。
