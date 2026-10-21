# 因果与相关的语义分层（3.6.0）

本文说明契约如何在**抽取阶段**就把知识间的关系分成可判定的三层，以便同一套数据同时支撑两件事：
从相关性出发逐步升级为因果，以及把已经确认的因果直接交给实验设计——只有因果关系才能直接指导实验。

## 三层信息，互不替代

| 层 | 字段 | 可获得性 | 回答的问题 |
|---|---|---|---|
| 谓词性质 | `transform.predicate_label` 的值属性 `nature` → 派生字段 `transform.relation_nature` | I → N | 这个关系**本身**断言的是因果、相关、结构还是描述？ |
| 原文语气 | `transform.predicate_mention`、`transform.relation_assertion_mode` | D | 原文用了什么谓语？语气是明确陈述、限定表述还是无法判断？ |
| 证据强度 | `transform.relation_evidence_type` | I | 支持它的证据是统计定位、表达支持、功能验证，还是定位成像、生化实验、药理处理或遗传互作？ |

三层必须分开记录，因为它们彼此独立：

- `nature` 是谓词的语义性质，**与证据强弱无关**。`qtl_associated_with_trait` 即使有功能验证级别的证据，
  它断言的仍然只是关联；`genotype_controls_trait` 也可能只有统计定位证据。
- `relation_assertion_mode` 记录原文**怎么说的**，不记录关系真假。`was associated with` 若被 `may` 限定，
  即 `hedged`。

因此 `transform.relation_nature` 由 `predicate_label` 词表的值属性在编译期映射得到
（`contract["relation_natures"]`，填充规则 `relation_nature_from_predicate`），**不由抽取模型判断**——
避免模型把自己的解读写进契约。

## 为什么谓词性质放在 N 层

`transform.predicate_label` 是 I（规范化名称，需要人工判断），抽取模型看不到它。但它的性质不应该是
一个新的主观判断：性质属于词表里的每一个代码，一旦人工审核给出 `predicate_label`，性质就随之确定。
把它编译成 `contract["relation_natures"]` 并由规则引擎填充，使「因果还是相关」成为契约数据而不是文档约定。

逐字谓词仍在 D 层（`transform.predicate_mention`，AMB-038），原文语气也在 D 层
（`transform.relation_assertion_mode`）：模型能看到原文，能抄谓语、能判断语气，但不能决定本体代码。

## 关联不得自动升级为因果

- **R036**（warning，inferred）：`relation_nature = associational` 且 `relation_assertion_mode = stated`
  时，若记录既没有 `transform.relation_evidence_type` 也没有 `agent.supporting_evidence`，提示补证据或降低
  表述强度。限定表述（`hedged`）的关系不触发——原文本身已经限定了。
- **R037**（warning，inferred）：`relation_nature = causal` 时提示给出 `transform.relation_evidence_type`，
  说明因果结论依据的是哪一级证据。

两级规则都是 warning，且 `basis: inferred`：契约从不因为「看似把关联写成了因果」而使记录无效。

## 与既有的 I 字段和 merged v2 的关系

- `agent.causal_direction`、`agent.association_vs_causation` 表达的正是这一区分，但取值未定义（AMB-024）
  且为 I，抽取画像不暴露。3.6.0 没有改动它们：`nature` 补的是**抽取阶段**可用的那一半，两者待数据负责人
  确定取值后再对齐（AMB-042）。
- `transform.relation_evidence_type` 的七个代码（AMB-040）即证据强度阶梯；本版本沿用，不新增。
- merged v2 附录 A-5 的 `跨组学-调控` 补为 `predicate_label` 代码 `cross_omics_regulates`
  （`nature: causal`，`origin: [merged_v2]`）。`mappings/merged_to_current.yaml` 中
  `relations[].relation_type → transform.predicate_label` 仍为 `partial`：A-5 之外的关系名需要新增代码，
  按 minor 升级。

## 待数据负责人确认（AMB-042）

AMB-042 的这一半是**判断标准**问题，不是字段问题，因此不放进契约的表里，写在这里：

- 五个 `nature` 取值、以及每个 `predicate_label` 代码归入哪一个，都是仓库的**拟定**；因果/相关这条线尤其
  需要育种领域的专家来定，而不是读代码清单就能定。
- `transform.relation_nature` 是派生值，词表覆盖到哪一步它就只能到哪一步。原文明说、但没有代码覆盖的关系
  没有性质（该键缺席）——这是有意为之，但意味着词表覆盖率是个真问题。
- `agent.causal_direction`、`agent.association_vs_causation` 取值仍未定义（AMB-024）。它们最终应当与
  `relation_nature` 一致，或者二者只留一个；本版本不做决定。
- **R036 的证据判定**同时接受 `transform.relation_evidence_type`（I，人工复核）与 `agent.supporting_evidence`
  （D，原文自身的话）。请确认二者之一都足以支撑一句平铺的相关陈述，还是只有人工复核的那一个才算。

字段本身的定位见 [downstream.md](downstream.md)。
