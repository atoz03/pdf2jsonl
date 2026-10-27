# 因果与相关的语义分层（3.8.0）

本文说明契约如何在**抽取阶段**就把知识间的关系分成可判定的三层，以便同一套数据同时支撑两件事：
从相关性出发逐步升级为因果，以及把已经确认的因果直接交给实验设计——只有因果关系才能直接指导实验。

3.7.0 补的是这套分层的**可读性**：一个关系为什么没有代码、词表覆盖到哪一步、以及"性质"如何在不经人工审核时
仍然进入记录（AMB-043）。

## 三层信息，互不替代

| 层 | 字段 | 可获得性 | 回答的问题 |
|---|---|---|---|
| 谓词性质 | `transform.predicate_label` 的值属性 `nature` → 派生字段 `transform.relation_nature` | I → N | 这个关系**本身**断言的是因果、相关、结构还是描述？ |
| 判定结果 | `transform.predicate_code`、`transform.relation_resolution` | N | 谓词被判成了哪个代码？没判出来是因为词表没覆盖、两码打平，还是原文否定？ |
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

## 判定结果：为什么没有代码

`predicate_code` 只在恰好一个代码命中时填写。3.6.0 里"没有代码"有四种完全不同的原因，记录里却看不出区别，
复核只能逐条回读原文。3.7.0 把原因写成 `transform.relation_resolution`（词表 `relation_resolution`）：

| 代码 | 含义 | 谁来修 |
|---|---|---|
| `coded` | 恰好一个代码命中 | — |
| `ambiguous` | 多个代码的线索词同样长，端点类型不足以区分（典型：主语没有被任何实体提及字段登记） | 补登实体提及，或人工给 `predicate_label` |
| `no_cue` | 谓词在原文中存在，但词表没有覆盖它的线索词 | 补词表线索词 |
| `negated` | 否定词在谓语或两端之间的原文里 | 极性由复核人判定，正关系的代码不得套用 |

没有谓语的记录不写这个字段。`counts.relation.coverage`（`coded / statements`）是词表覆盖率的直接读数，
运行之间可比。打平时**不猜**：3.7.0 没有引入泛化回退代码，先按 `ambiguous` 统计比例，再决定是否值得加。

## 词表覆盖了什么

`predicate_label` 的代码按反馈里出现的关系类型补齐（AMB-043），并按"关系本身断言什么"分入 `nature`：

| 类 | 代码（`nature`） |
|---|---|
| 统计相关 | `gene_associated_with_trait`、`qtl_associated_with_trait`、`locus_correlated_with_trait`、`trait_correlated_with_trait`（associational） |
| 位置重叠／共定位 | `locus_overlaps_locus`（structural） |
| 预测与模型比较 | `model_predicts_trait`（associational，**不得**升级为因果） |
| 实验干预支持的功能效应 | `genotype_controls_trait`、`locus_increases_trait`、`locus_decreases_trait`、`gene_mediates_resistance`（causal） |

线索词是字面短语，词表**不变位**：一个动词要写出第三人称、过去式与被动式（`increased`、`increases`、
`conferred`、`mediated`）。`qtl_overlaps_qtl` 已弃用（`status: deprecated`，`replaced_by: locus_overlaps_locus`）：
位置重叠是结构关系，而一个 nature 写着 associational 的代码不能原地改义。旧记录仍按它派生 nature，
新抽取不会命中它（弃用代码不再给出线索词），使用它的记录会收到 `VOCAB_CODE_DEPRECATED`。

## 性质如何进入记录

`transform.predicate_label` 是 I（规范化名称，需要人工判断），抽取模型看不到它。但它的性质不应该是
一个新的主观判断：性质属于词表里的每一个代码，一旦人工审核给出 `predicate_label`，性质就随之确定。
把它编译成 `contract["relation_natures"]` 并由规则引擎填充，使「因果还是相关」成为契约数据而不是文档约定。

3.6.0 只从 `predicate_label` 派生，因此**新抽取的记录永远没有 nature**，R036/R037 在抽取链路上从不触发。
3.7.0 起，记录没有人工 `predicate_label` 时由 `predicate_code` 兜底：两者来自同一份契约数据，都是确定性判定，
不是第二次解读。人工标签仍然优先。

逐字谓词仍在 D 层（`transform.predicate_mention`，AMB-038），原文语气也在 D 层
（`transform.relation_assertion_mode`）：模型能看到原文，能抄谓语、能判断语气，但不能决定本体代码。

## 关联不得自动升级为因果

- **R036**（warning，inferred）：`relation_nature = associational` 且 `relation_assertion_mode = stated`
  时，若记录既没有 `transform.relation_evidence_type` 也没有 `agent.supporting_evidence`，提示补证据或降低
  表述强度。限定表述（`hedged`）的关系不触发——原文本身已经限定了。
- **R037**（warning，inferred）：`relation_nature = causal` 时提示给出 `transform.relation_evidence_type`，
  说明因果结论依据的是哪一级证据。

两级规则都是 warning，且 `basis: inferred`：契约从不因为「看似把关联写成了因果」而使记录无效。

3.7.0 起两条规则都标了 `blocking: false`：它们照常报出、计数、写进 `common.qc_failure_codes`，但**不单独把
记录降为待复核**。原因是 R037 要求的 `transform.relation_evidence_type` 是 I（人工判断），抽取环节无法满足；
若让它阻断，每一句因果句都会永久待审，而人工只能靠点"通过"清掉——这只会教人忽略复核队列。先观察一版数量，
再决定是否阻断（AMB-043）。


## 结论强度：动词之外还要看证据

`nature` 只说谓词**怎么断言**，不说这个断言**凭什么成立**。3.8.0 把两者合起来读，派生
`transform.claim_strength`（词表 `claim_strength`，AMB-046）：

| `claim_strength` | 什么时候 | 含义 |
|---|---|---|
| `causal_supported` | causal + 功能验证／遗传互作／生化／定位成像／药理处理 | 因果措辞且有干预级证据 |
| `causal_expression_supported` | causal + 表达支持 | 表达共变，不等于干预验证 |
| `causal_statistical_only` | causal + 统计定位 | 因果措辞但只有统计证据；R038 提示补验证方法或降级表述 |
| `causal_unverified` | causal + 未给证据类型 | 论文用了因果措辞而未说明依据，**不当作已证实的因果** |
| `associational` / `structural` / `descriptive` | 对应 nature | 原样传递 |

两条边界必须守住：证据类型不会把相关升级为因果（`associational` 即使有功能验证证据仍是 `associational`），
缺证据也不会把谓词降级（记录保留原文的因果说法，只是强度写 `causal_unverified`）。这就是"不能仅凭
increased 这类动词判为因果"的落地方式：动词决定**措辞**，证据决定**强度**，两者分开记录、分开计数。

## 实体：QTN、QTL 与候选基因

3.8.0 新增 `common.qtn_names`（实体类型 `qtn`，AMB-045）。QTN（关联定位的显著位点/单核苷酸位点）、QTL
（连锁定位区间）与候选基因（`common.gene_names`）是三种实体：候选基因不会被改称 QTN，QTN 也不并入 QTL 名单。
`qtn_associated_with_trait` 让 QTN 能表达自己的关联；`locus_correlated_with_trait`、`locus_overlaps_locus`、
`model_predicts_trait` 都接受 `qtn` 作为一端。

## 验证状态：候选还是已提供验证实验

`transform.validation_status`（词表 `validation_status`：`candidate` / `experiment_reported`）只由
`agent.validated_by_record_ids` 这条链接派生，不读记录措辞：链接到论文自己报告的验证实验（互补、转基因、
基因编辑、表达分析、酶活、互作等）就是 `experiment_reported`，否则是 `candidate`。关联记录与验证记录各自
保留证据，验证记录不覆盖关联记录；`agent.candidate_gene_status`（I）仍是人工判断的证据层级，两者不互相替代。



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
