# README release highlights (3.5.0 – 3.8.0, tooling 1.1.0)

Until 2026-11-10 both READMEs carried a "what this version added" section for every release. Those sections
were moved here verbatim when the READMEs were cut back to the current state of the project; only relative link
targets were adjusted for this directory. They are kept for traceability and are not updated. The curated
record of each release is the [CHANGELOG](../../CHANGELOG.md); the release index is [README.md](README.md).

The sections appear in the order the READMEs printed them (3.6.0, 3.8.0, 3.7.0, 3.5.0), after the tooling 1.1.0
paragraph that introduced the research view.

## English (from `README.en.md`)

### Tooling 1.1.0: research view

The view is backed by `src/breeding_contract/evidence_chain.py` (claim → result → experiment/method),
`src/breeding_contract/article_package.py` (article package) and `src/breeding_contract/aggregate.py`
(cross-paper clustering, conflicts and confidence); see [docs/research_view.md](../research_view.md).
This is tooling **1.1.0**; the data contract remains **3.8.0**
([release notes](tooling-1.1.0.md)). The per-paper view also has a **人工复核 (N)** button that
opens a review panel for every `pending_review` record: approve / reject / return for evidence are kept in
the browser, exported as JSON, and applied with `bdc review apply RECORDS DECISIONS --out DIR`.

### Contract releases

3.6.0 records the semantic nature of a relation; both additions are provisional:

- **Every predicate code carries a nature**: `causal` / `associational` / `structural` / `descriptive`, mapped at
  compile time to `transform.relation_nature` (N, derived from the contract, never judged by the model), while
  `transform.relation_assertion_mode` (D) keeps the source's own wording. Only a causal relation can directly
  guide an experiment, so R036 / R037 flag a flat association with no evidence and a causal relation with no
  evidence type. See [`docs/relation_semantics.md`](../relation_semantics.md).
- **The derived views and the dashboard carry it**: `bdc derive` statements, triples and graph edges include
  `relation_nature` and `relation_assertion_mode` (`derive_format` = 4), and the paper dashboard gained a 关系 tab
  that lists every statement with its nature and filters by it.

3.8.0 makes "what makes a conclusion hold" a field (provisional):

- **A causal wording is no longer decided by the verb alone**: `transform.claim_strength` reads the predicate's
  nature together with the relation evidence type — `causal_supported` (functional validation, genetic
  interaction, biochemical assay, localization imaging, pharmacological perturbation),
  `causal_expression_supported`, `causal_statistical_only`, `causal_unverified`; R038 asks for a validation
  method when a causal claim has statistical evidence only. Evidence never upgrades an association, and missing
  evidence never downgrades the wording.
- **The four relation classes the trial needed**: `qtn_associated_with_trait`, `gene_suppresses_gene` /
  `gene_suppressed_by_gene` (active and passive kept apart), `gene_upstream_of_gene`,
  `trait_controlled_by_gene`, `locus_affects_trait`, `locus_linked_to_locus`, `gene_absent_in_germplasm`, and
  `colocalizes with` / `coincides with` for overlap. On the six trial papers relation coverage rose from 41.7%
  to 69.4%.
- **Entities and validation state**: `common.qtn_names` keeps QTN apart from QTL and candidate genes;
  `agent.validated_by_record_ids` links the validation experiment the paper reports and
  `transform.validation_status` turns that into `candidate` / `experiment_reported`, with association and
  validation evidence kept side by side.
- **Review paraphrase**: `transform.evidence_origin` marks `review_report`, `agent.reported_citation_text`
  keeps the lead the review prints, and R040 asks for it.
- **The dashboard explains its own numbers**: the run header shows 候选 → 生成 → 接收 / 拒收 / 待审 with the
  definitions, and the paper badge separates pending records from structural hints.
- **The display contract lives in the repository**: `docs/presentation.md` requires every list view to show the
  entity beside its type, the validation status as its own column, the author's qualifier verbatim and the claim
  strength; `bdc check` enforces it through `check_presentation`, so deleting one of those columns fails CI. The
  dashboard's record table therefore has 实体 / 验证 / 限定语 / 结论强度 columns, and the relations table types
  both ends.
- **The regression is re-runnable**: `scripts/acceptance_report.py` runs the same papers with the main text and
  with the supplements, on 3.6.0 and 3.8.0, and writes every review-queue item and verdict to
  [`docs/acceptance_3.8.0.md`](../acceptance_3.8.0.md); `tests/test_acceptance.py` asserts the same matrix and
  `make acceptance` re-runs it (the human review-time column is left to the reviewer, the script does not time).

3.7.0 records *why* a relation has no code, and writes the state of a source part as data (both provisional):

- **The resolution is visible**: `transform.relation_resolution` (`coded` / `ambiguous` / `no_cue` / `negated`)
  says why `predicate_code` has a value or not — a vocabulary gap (fix the vocabulary) and a tie between two
  codes (register the entity mention) need different actions; `counts.relation.coverage` is the coverage read-out.
  The nature is derived from `predicate_code` when no human `predicate_label` exists, so a fresh record carries
  causal / associational itself. See [`docs/relation_semantics.md`](../relation_semantics.md).
- **The cue lexicon covers four classes**: statistical correlation (`locus_correlated_with_trait`), interval
  overlap and co-localisation (`locus_overlaps_locus`, structural), prediction and model comparison
  (`model_predicts_trait`, never causal) and functional effects backed by intervention (`locus_increases_trait`
  …); verb cues include the third person, the past tense and the passive, and the old `qtl_overlaps_qtl` is
  deprecated with a replacement.
- **Warnings are blocking or informational**: a rule may set `blocking: false` (R018, R036, R037). Such a warning
  is counted, written to `qc_failure_codes` and shown, but does not by itself put the record in `pending_review`
  — a value only the operator can supply, or one only a human can judge, cannot be cleared by the extraction.
- **The counts say what they count**: `counts.system_records` (one asset manifest per input file), `counts.warnings`
  (by code, by family, blocking versus informational) and `counts.relation`, with `count_definitions` in the
  report; `pending_review` is a subset of the accepted records, not another bucket.
- **Part states and the appendix**: `source_parts.parts[]` gives the state of every part (parsed, supplied
  without a text layer, supplied but never cited, cited but not supplied), `--supplement FILE:appendix` makes the
  appendix a part of its own, and the new `SOURCE_PART_NOT_PARSED` / `SOURCE_PART_UNREFERENCED` keep the two
  "we cannot read it" cases apart. See [`docs/downstream.md`](../downstream.md).

Three things were added in 3.5.0 for the agent that plans research (Topic 2); all are provisional:

- **The research workflow of a paper** as links between records: the role of a statement (background,
  question, objective, hypothesis, design, result, conclusion) and the links *tests*, *addresses* and
  *prerequisite* next to *evidence* and *method*. `bdc derive` writes `workflow.json` with step order, branch
  points, one trace per hypothesis and structural flags. See [`docs/workflow.md`](../workflow.md).
- **Semantic verification by a second model**: `bdc verify` asks, record by record and link by link, whether
  the quote really states the value. It can send a record back to review and promote one to `model_verified`,
  never to expert approval. See [`docs/review.md`](../review.md).
- **Papers in several files, and incomplete papers**: `--supplement` adds the supplementary file as a part of
  the same source; a main text that cites "fig. S2" without the supplement is reported as incomplete and the
  affected records are flagged instead of being filled in.

## 简体中文（摘自 `README.md`）

### 工具 1.1.0：研究视图

研究视图的后端模块是 `src/breeding_contract/evidence_chain.py`（结论→结果→实验/方法）、
`src/breeding_contract/article_package.py`（文章包清单）和 `src/breeding_contract/aggregate.py`
（跨文聚类、冲突与置信）；说明见 [docs/research_view.md](../research_view.md)。本版工具版本为
**1.1.0**，数据契约仍为 **3.8.0**（[发布说明](tooling-1.1.0.md)）。逐篇视图页头的
**人工复核（N）** 按钮打开复核面板：通过 / 驳回 / 退回补证先保存在浏览器，导出后由
`bdc review apply 记录文件 决定文件 --out 输出目录` 写回 `review_status` 和 `review_note`。

### 契约版本

3.6.0 记录关系的语义性质，均为拟定（provisional）：

- **每条关系谓词带上性质**：`predicate_label` 词表的每个代码声明 `nature`（causal／associational／
  structural／descriptive），编译期映射为 `transform.relation_nature`（N，由契约派生，不交给模型判断）；
  来源自己的措辞另由 `transform.relation_assertion_mode`（D）记录。只有因果关系能直接指导实验，R036／R037
  在「相关性被平铺陈述却没有证据」或「因果关系没有说明证据类型」时提示。见
  [`docs/relation_semantics.md`](../relation_semantics.md)。
- **派生视图与看板沿用这层性质**：`bdc derive` 的 statements、三元组与属性图边都带 `relation_nature` 与
  `relation_assertion_mode`（`derive_format` = 4）；论文看板新增「关系」页签，逐条列出主谓宾并可按性质筛选。

3.8.0 把"结论凭什么成立"写成字段（均为拟定）：

- **因果措辞不再只由动词决定**：`transform.claim_strength` 把谓词性质与关系证据类型合起来读——
  `causal_supported`（功能验证／遗传互作／生化／定位成像／药理处理）、`causal_expression_supported`、
  `causal_statistical_only`、`causal_unverified`；R038 在"因果措辞 + 只有统计证据"时提示补验证方法。
  证据不会把相关升级为因果，缺证据也不会把谓词降级。
- **四类关系的词表补齐**：新增 `qtn_associated_with_trait`、`gene_suppresses_gene` / `gene_suppressed_by_gene`
  （主动与被动分码）、`gene_upstream_of_gene`、`trait_controlled_by_gene`、`locus_affects_trait`、
  `locus_linked_to_locus`、`gene_absent_in_germplasm`；`locus_overlaps_locus` 补 `colocalizes with` /
  `coincides with`。六篇真实论文的关系覆盖率从 41.7% 提到 69.4%。
- **实体与验证状态**：`common.qtn_names` 让 QTN 与 QTL、候选基因分开；`agent.validated_by_record_ids`
  链接论文自己报告的验证实验，`transform.validation_status` 据此给 `candidate` / `experiment_reported`，
  关联证据与验证证据各自保留。
- **综述转述**：`transform.evidence_origin` 标 `review_report`，`agent.reported_citation_text` 保留原文线索，
  R040 在缺线索时提示。
- **看板解释自己的数字**：运行页头一行"候选 → 生成 → 接收 / 拒收 / 待审"并附计算口径；论文徽章区分
  "有待审记录"与"有结构提示"；记录带"候选／已提供验证实验""因果·仅统计定位"等徽章。

3.7.0 记录「一个关系为什么没有代码」，并把材料状态写成数据（均为拟定）：

- **判定结果可见**：`transform.relation_resolution`（`coded`／`ambiguous`／`no_cue`／`negated`）说明
  `predicate_code` 为什么有值或没有值——词表没覆盖（补词表）与两码打平（补登实体提及）需要完全不同的动作；
  `counts.relation.coverage` 是词表覆盖率的直接读数。谓词性质在没有人 `predicate_label` 时由
  `predicate_code` 兜底，因此新抽取的记录本身就带因果／相关。见 [`docs/relation_semantics.md`](../relation_semantics.md)。
- **线索词覆盖四类关系**：统计相关（`locus_correlated_with_trait`）、位置重叠／共定位
  （`locus_overlaps_locus`，结构关系）、预测与模型比较（`model_predicts_trait`，不得升级为因果）、
  实验干预支持的功能效应（`locus_increases_trait` 等）；动词线索词覆盖第三人称、过去式与被动式，
  旧代码 `qtl_overlaps_qtl` 弃用并指明替代。
- **提示分「阻断」与「只报告」**：规则可标 `blocking: false`（R018、R036、R037）。非阻断提示照常计数、
  写进 `qc_failure_codes`，但不单独把记录降为待复核——只由操作者提供或只能人工判断的值，抽取环节无法清除。
- **计数自解释**：`counts` 增加 `system_records`（每个输入文件一条资产清单）、`warnings`
  （按代码／家族、阻断／非阻断）与 `relation`，报告里附 `count_definitions` 说明每个数字的算法；
  `pending_review` 是已接收记录的子集，不是另一类记录。
- **材料状态与附录**：`source_parts.parts[]` 给出每个部分的状态（已解析／已提供但没有文本层／已提供但未引用／
  引用但未提供），`--supplement FILE:appendix` 让附录成为一等部分，新增 `SOURCE_PART_NOT_PARSED` 与
  `SOURCE_PART_UNREFERENCED`。见 [`docs/downstream.md`](../downstream.md)。
- **展示规则写进仓库**：`docs/presentation.md` 规定列表视图必须显示"实体＋类型""验证状态（候选／已提供
  实验验证）""原文限定语"与"结论强度"，`bdc check` 的 `check_presentation` 会检查看板模板是否实现，
  删掉其中一列即 CI 失败。看板记录表因此有 实体 / 验证 / 限定语 / 结论强度 四列，关系表的主宾语也带类型。
- **回归验收可复跑**：`scripts/acceptance_report.py` 把同一批论文分别以正文、正文+补充材料输入，在
  3.6.0 与 3.8.0 上各跑一次，逐条列出待审项与验收结论，写入
  [`docs/acceptance_3.8.0.md`](../acceptance_3.8.0.md)；`tests/test_acceptance.py` 用同一矩阵做断言，
  `make acceptance` 一键复跑（人工复核耗时一列留给复核人，脚本不计时）。

3.5.0 面向课题二的科研智能体新增三项能力，均为拟定（provisional）：

- **论文内的研究流程**，以记录之间的链接表示：陈述的角色（背景、科学问题、研究目标、假设、实验设计、
  结果、结论），以及在“依据”“产生方法”之外新增的“检验”“回应”“前置”三类链接。`bdc derive` 输出
  `workflow.json`，含步骤顺序、分支点、每条假设的链路和结构提示。见 [`docs/workflow.md`](../workflow.md)。
- **由第二个模型做语义复核**：`bdc verify` 逐条记录、逐条链接判定引文是否确实陈述了该取值。复核可以把
  记录退回待审，也可以把记录提升为 `model_verified`，但不能代替专家通过。见 [`docs/review.md`](../review.md)。
- **多文件论文与不完整论文**：`--supplement` 把补充材料作为同一来源的另一部分一并处理；正文引用了
  “fig. S2”而补充材料未提供时，报告标明来源不完整，受影响的记录被标记而不是被补全。
