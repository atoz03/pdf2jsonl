# lyy v3.0.0（259 字段） & d v2.0.0（多组学模板） → merged v2.0.0 字段映射

> 本文件是合并基线：逐个字段给出「旧路径 → merged 归属」的精确映射与取舍说明。
> merged 采用**文档行主锚 + 单位行扩展**三层模型，见 `breeding_jsonl_spec_v2.md`。
> 列：`来源路径` / `merged 归属（JSON 路径）` / `说明（含别名/改名/吸收/并入）`。

---

## 0. 映射归属规则（约定）

| 语义类别 | 归属 |
| --- | --- |
| 来源标识、来源日期、来源页码/章节/表图/原句/定位 | `doc_meta.*` 或 `provenance.source_locations[]`（细定位） |
| 记录/数据集聚合、批次、抽取运行、来源版本 | `provenance.*`（运行与批次）与 `doc_meta.dataset_*`/`record_version` |
| 材料、品种、群体、环境、性状、基因、标记、QTL、病害 | `breed_entities.<子块>[]` |
| 观测级单值（measurement/genotype/plot/replicate/统计量） | `observations[]`（单位行 `record_kind=observation`） |
| 大文件/高维矩阵（VCF/Parquet/Zarr/媒体） | `assets[]`（单位行 `record_kind=asset_manifest`） |
| 许可、访问、保留、去重、时效 | `governance.*` |
| 跨文献冲突、融合、更新链 | `pipeline.*` / `conclusions.contradiction_note` |
| 图谱语句、语料块、QA、防泄漏、训练划分 | `transform.*` |
| 科学问题、发现、证据、假设、因果、验证 | `agent.scientific_reasoning.*`（吸收 lyy agent 扁平字段） |
| 方法、软件、参数、验证、技能注册 | `skill.method_profile.*` / `skill.validation.*` / `skill.skill_registry.*` |

---

## 1. lyy `common`（127 字段）映射

### 1.1 来源与记录标识 → `doc_meta` / `provenance`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `common.record_id` | `record_id`（顶层） | cyx R-01 同义，直接合并 |
| `common.schema_version` | `schema_version`（顶层） | merged 固定 `v2.0.0` |
| `common.record_kind` | `record_kind`（顶层） | 新增；cyx 语义缺位，本字段启用单位行契约 |
| `common.source_id` | `doc_meta.source_id` | **新增**，如 `doi:/sra:/urn:` |
| `common.source_type` | `doc_meta.source_type` | **新增**（paper/experiment_record/tool_description…） |
| `common.source_title` | `doc_meta.title` | 同义，cyx 键为准 |
| `common.source_doi` | `doc_meta.doi` | 同义 |
| `common.source_year` | `doc_meta.year` | 同义 |
| `common.source_authors` | `doc_meta.authors[].name` | cyx 结构化为数组对象 |
| `common.source_asset_id` | `provenance.source_file_asset_id` | **新增**（与 `doc_meta.pdf_path` 并存的资产级引用） |
| `common.source_file_sha256` | `provenance.integrity.source_file_hash` | 与 cyx PV-09 同名合并 |
| `common.source_locator` | `provenance.source_locations[].locator` | **新增键**，回查页/表单元/行键/文件偏移统一定位符 |
| `common.source_page` | `provenance.source_locations[].page` | 并入结构 |
| `common.source_section` | `provenance.source_locations[].section_id`(doc_meta.document_sections) | 并入结构 |
| `common.source_table_figure` | `provenance.source_locations[].block_id` | 并入结构 |
| `common.source_table_row_key` | `provenance.source_locations[].table_row_key` | **新增键**（细定位） |
| `common.source_table_column_key` | `provenance.source_locations[].table_column_key` | **新增键** |
| `common.source_quote` | `provenance.source_locations[].text_snippet` | 同义，min 原句 |
| `common.source_span` | `provenance.source_locations[].char_span` | 同义（字符偏移/版面坐标） |
| `common.source_language` | `record_info.lang` | 同义 |
| `common.extraction_method` | `provenance.extraction.method` | 同义 cyx PV-01 |
| `common.extraction_confidence` | `provenance.extraction.confidence` | **新增键** |
| `common.review_status` | `provenance.verification.status` | 与 cyx PV-05 合并（值对齐：pending/auto_pass/expert_pass/rejected） |
| `common.review_note` | `provenance.verification.notes` | 同义 |
| `common.ingested_at` | `provenance.ingested_at` | **新增键**（ISO8601 UTC） |
| `common.ingest_batch_id` | `provenance.ingest_batch_id` | **新增键** |
| `common.extraction_run_id` | `provenance.extraction_run_id` | **新增键**（复现抽取任务） |
| `common.source_record_id` | `provenance.source_record_id` | **新增键**（幂等导入） |
| `common.source_version` | `provenance.source_version` | **新增键** |
| `common.source_uri` | `doc_meta.source_uri` | **新增键**（持久 URI，非本地路径） |
| `common.missing_fields` | `provenance.missing_fields` | **新增键**（缺失字段→原因代码映射） |
| `common.record_version` | `doc_meta.record_version` | **新增键**（同 record_id 修订序号） |
| `common.record_grain` | `record_kind` | 合并为 record_kind 语义 |
| `common.dataset_id` | `doc_meta.dataset_id` | **新增键**（TB 级分片聚合） |
| `common.dataset_version` | `doc_meta.dataset_version` | **新增键** |
| `common.study_id` | `doc_meta.study_id` | **新增键** |
| `common.trial_id` | `doc_meta.trial_id` | **新增键** |
| `common.environment_id` | `breed_entities.environments[].env_id` | 同义 |
| `common.site_id` | `breed_entities.environments[].location.site_id` | **新增键** |
| `common.experiment_id` | `experiments[].experiment_id` | 同义 |
| `common.analysis_run_id` | `analyses[].analysis_id` / `provenance.extraction_run_id` | 分析行级 → analyses；记录级 → provenance |
| `common.data_modality` | `doc_meta.data_modality` | **新增键** |
| `common.linked_modalities` | `doc_meta.linked_modalities` | **新增键** |
| `common.license_id` | `governance.data_license.license_name` | 与 cyx 并入授权块 |
| `common.access_level` | `governance.access_level` | **新增键**（open/controlled/restricted） |

### 1.2 作物/物种/材料 → `breed_entities`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `common.crop_name` | `doc_meta.species_list[].crop_group` / `breed_entities.other_entities` | 顶层作物 → `doc_meta.crop_primary`(**新增**) |
| `common.crop_taxon_id` | `species_list[].ncbi_tax_id`+`tax_id_source` | cyx 已含 ncbi_tax_id |
| `common.species_name` | `species_list[].name` | 同义 |
| `common.subspecies` | `germplasm[].species_info.sub_species` | 同义 |
| `common.germplasm_names` | `germplasm[].germplasm_name` | 同义 |
| `common.variety_names` | `varieties[].variety_name` | 同义 |
| `common.population_name` | `populations[].population_name` | 同义 |
| `common.population_type` | `populations[].pop_type` | 同义（附录 A-4） |
| `common.parent_names` | `populations[].parents[].name` / `germplasm[].parents[].name` | 同义 |
| `common.donor_parent` | `populations[].parents[]`（role=供体） | 并入 parents |
| `common.recurrent_parent` | `populations[].parents[]`（role=轮回亲本） | 并入 parents |
| `common.sample_size` | `populations[].population_size` / `observations[].sample_size` | 实体级→群体；观测级→观测行 |
| `common.population_generation` | `populations[].generation` | 同义 |
| `common.genetic_background` | `germplasm[].species_info.genetic_background` | **新增键** |
| `common.ploidy` | `samples`/`omics_samples[].ploidy` + `observations[].genotype.ploidy` | 稀疏基因型调用必填 |

### 1.3 环境/试验条件 → `breed_entities.environments[]` + `experiments`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `common.trial_year` | `environments[].year` | 同义 |
| `common.location_name` | `environments[].location.site` | 同义 |
| `common.latitude_deg`/`longitude_deg`/`elevation_m` | `environments[].location.lat/lon/altitude_m` | 同义 |
| `common.agroecological_zone` | `environments[].location.eco_zone` | **新增键** |
| `common.soil_type` | `environments[].soil.soil_type` | 同义 |
| `common.environmental_conditions` | `environments[].soil/climate` 原文摘要 | 结构化吸收 |
| `common.trial_season` | `environments[].season` | 同义 |
| `common.growth_stage` | `traits[].measurement_detail.stage` / `observations[].stage` | 同义 |
| `common.treatment` | `experiments[].treatments[]` | 同义 |
| `common.environment_code` | `environments[].env_code_in_paper` | 同义 |
| `common.environment_count` | `experiments[].env_used.length`（语义注明） | 保留注释不设实体字段 |

### 1.4 性状/基因/标记/QTL → `breed_entities`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `common.trait_names` | `traits[].trait_name` | 同义 |
| `common.trait_ids` | `traits[].trait_ontology_id` | 同义 |
| `common.trait_id`（本行单一性状） | `observations[].trait_ref` | 观测行级 |
| `common.gene_names` | `genes[].gene_symbol` | 同义 |
| `common.gene_ids` | `genes[].ontology_id` | 同义 |
| `common.marker_names` | `markers[].marker_name` | 同义 |
| `common.qtl_names` | `qtls[].qtl_name` | 同义 |
| `common.genome_assembly` | `markers[].position.ref_genome` / `qtls[].ref_genome`(**新增**) / `variants` | 变异坐标依赖的组装版本 |
| `common.chromosome` | `qtls[].chromosome` / `markers[].chromosome` / `observations[].variant.chromosome` | 同义 |
| `common.locus_interval_start_bp` / `end_bp` | `qtls[].interval.{start,end}`（unit=bp） | 同义 |
| `common.locus_interval_label` | `qtls[].interval.label` | **新增键**（G1149-R727 原样标签） |
| `common.trait_measurement_protocol` | `traits[].measurement_detail.method_standard` | 同义 |

### 1.5 观测测量 → `observations[]`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `common.observation_time` | `observations[].observation_time` | **新块** |
| `common.measurement_name` | `observations[].measurement.name` | 新块 |
| `common.measurement_value` | `observations[].measurement.value` | 新块（缺失不填 0） |
| `common.measurement_text` | `observations[].measurement.text` | 新块，与 value 二选一 |
| `common.measurement_unit` | `observations[].measurement.unit` | 新块 |
| `common.measurement_quality_flag` | `observations[].measurement.quality_flag` | 新块 |
| `common.original_value` / `original_unit` | `observations[].original_value` / `original_unit` | **新增键**（原文原样） |
| `common.normalized_value` / `normalized_min_value` / `normalized_max_value` / `normalized_unit` | `observations[].normalized{_min,_max,_unit}` | **新增键** |
| `common.genotype_call` | `observations[].genotype.call` | 新块 |
| `common.genotype_dosage` | `observations[].genotype.dosage` | 新块 |
| `common.reference_allele` | `observations[].genotype.ref_allele` | 新块 |
| `common.alternate_allele` | `observations[].genotype.alt_allele` | 新块 |
| `common.dosage_allele` | `observations[].genotype.dosage_allele` | 新块 |
| `common.material_id` | `observations[].material_ref` / `germplasm[].entity_id` | 观测行回链 |
| `common.sample_id` | `breed_entities.omics_samples[].sample_id` + `observations[].sample_ref` | 新块 |
| `common.plot_id` | `observations[].plot_id` | **新块键** |
| `common.replicate_id` | `observations[].replicate_id` | 新块键 |
| `common.treatment_id` | `observations[].treatment_ref` | 新块键 |
| `common.assay_id` | `observations[].assay_ref` / `omics_experiments[].assay_id` | 新块键 |
| `common.variant_id` | `observations[].variant.variant_id` | 新块键 |
| `common.variant_ids` | `observations[].variant` 或资产引用 | 未来基因组库接入 |
| `common.sequence_accessions` | `assets[].asset_accession` | 序列资源登录号→资产 |

### 1.6 资产 → `assets[]`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `common.asset_uri` | `assets[].asset_uri` | **新块** |
| `common.asset_kind` | `assets[].asset_kind` | 新块 |
| `common.asset_format` | `assets[].asset_format` | 新块 |
| `common.asset_compression` | `assets[].asset_compression` | 新块 |
| `common.asset_size_bytes` | `assets[].asset_size_bytes` | 新块 |
| `common.asset_sha256` | `assets[].asset_sha256` | 新块 |
| `common.asset_row_count` / `asset_column_count` | `assets[].asset_row_count` / `asset_column_count` | 新块 |
| `common.asset_schema_ref` | `assets[].asset_schema_ref` | 新块（高维文件字段/单位定义引用） |
| `common.genotype_dataset_id` / `phenotype_dataset_id` | `assets[].related_dataset_id` | 新块 |
| `common.data_access_uri` | `assets[].asset_uri` / `governance.access_level` | 并入资产与访问级 |

### 1.7 质量/冲突/许可 → `provenance` / `governance` / `pipeline`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `common.qc_rule_set_version` | `provenance.qc_rule_set_version` | **新增键** |
| `common.qc_failure_codes` | `governance.consistency_checks[]` + `provenance.qc_failure_codes`(**新增**) | 保留双写策略 |
| `common.conflict_record_ids` | `pipeline.conflict_statements[].other_record_id` | 同义 |
| `common.review_status` | `provenance.verification.status` | 合并（见 1.1） |

---

## 2. lyy `agent`（46 字段）映射 → `agent.scientific_reasoning`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `agent.scientific_question` | `agent.scientific_reasoning.scientific_question` | **新子块**（与 `agent_state.problem_statement` 同义回链） |
| `agent.finding_text` | `agent.finding_text` | 新子块 |
| `agent.finding_kind` | `agent.finding_kind` | 关联/预测/功能验证/机制发现 |
| `agent.evidence_type` | `agent.evidence_type` | QTL/GWAS/基因编辑… |
| `agent.evidence_strength` | `agent.evidence_strength` | 证据级别 |
| `agent.supporting_evidence` | `agent.supporting_evidence`（array，可回 `provenance.source_locations`） | 结构化为统一 evidence 对象 |
| `agent.contradictory_evidence` | `agent.contradictory_evidence` | 竞争假设证据 |
| `agent.hypothesis_stated` | `agent.hypothesis_stated` | 作者原假设 |
| `agent.candidate_mechanism` | `agent.candidate_mechanism` | 生物学机制 |
| `agent.mechanism_entities` | `agent.mechanism_entities` | 机制路径实体 |
| `agent.causal_direction` | `agent.causal_direction` | 作用方向 |
| `agent.association_vs_causation` | `agent.association_vs_causation` | 区分关联/因果 |
| `agent.assumption_conditions` | `agent.assumption_conditions` | 结论成立前提 |
| `agent.applicable_population` | `agent.applicable_population` | 适用群体 |
| `agent.applicable_environment` | `agent.applicable_environment` | 适用环境边界 |
| `agent.expected_observation` | `agent.expected_observation` | 预期观测 |
| `agent.actual_observation` | `agent.actual_observation` | 实际观测 |
| `agent.alternative_explanations` | `agent.alternative_explanations` | 替代解释 |
| `agent.uncertainty_note` | `agent.uncertainty_note` | 不确定性 |
| `agent.falsification_test` | `agent.falsification_test` | 可证伪对照试验 |
| `agent.experiment_objective` | `agent.experiment_objective` | 实验目标（复用为规划目标） |
| `agent.experiment_design` | `experiments[].experimental_design.design_type` + `agent` 简述 | 结构化落实验行 |
| `agent.experimental_materials` | `experiments[].materials_used[]` | 结构化落实验行 |
| `agent.treatment_groups` | `experiments[].treatments[]` | 结构化落实验行 |
| `agent.control_groups` | `experiments[].experimental_design.control` | 结构化落实验行 |
| `agent.replicate_count` | `experiments[].experimental_design.replicates` | 结构化落实验行 |
| `agent.observation_indicators` | `experiments[].trait_measurements[]` | 结构化落实验行 |
| `agent.workflow_steps` | `experiments[].experimental_steps[]` / `skill.method_profile.workflow_steps` | 实验行或技能行 |
| `agent.workflow_dependencies` | `experiments[].experimental_steps[].depends_on` | 步骤依赖 |
| `agent.result_interpretation` | `agent.result_interpretation` | 作者解释 |
| `agent.breeding_relevance` | `conclusions[].breeding_recommendations[]` + `agent.breeding_relevance` 简述 | 双向 |
| `agent.followup_experiment` | `agent.followup_experiment` | 后续验证 |
| `agent.knowledge_gap` | `agent_state.state_unknowns` + `agent.knowledge_gap` 简述 | 结构化吸收 |
| `agent.task_tags` | `governance.domain_tags` + `agent.task_tags` | **新增键** |
| `agent.hypothesis_origin` | `agent.hypothesis_origin` | 作者提出/抽取归纳，不得混同 |
| `agent.candidate_gene_status` | `observations/stats` 或 `genes[].candidate_status`(**新增**) | d 受控词表分级 |
| `agent.statistical_test` | `analyses[].model_name` + `agent.statistical_test` 简述 | **新增键** |
| `agent.lod_score` | `qtls[].lod` / `observations[].statistic` | 结构与观测双落 |
| `agent.pve_percent` | `qtls[].pve` / `observations[].statistic` | 结构与观测双落 |
| `agent.effect_estimate` | `qtls[].additive_effect` / `observations[].statistic.effect_size` | 结构与观测双落 |
| `agent.effect_unit` | `observations[].statistic.effect_unit` | **新增键** |
| `agent.environment_stability` | `qtls[].qtl_type` + `observations[].statistic.replication_status` | 合并 |
| `agent.validation_methods` | `analyses[].validation_design.strategy` + `agent.validation_methods` | **新增键** |
| `agent.claim_id` | `conclusions[].conclusion_id` | 结论行级稳定 ID |
| `agent.evidence_record_ids` | `conclusions[].supporting_relations` + `evidence_list[].reference_id` | 证据链闭合 |
| `agent.external_validity_scope` | `conclusions[].scope_constraints` + `agent.external_validity_scope` 简述 | 合并 |

---

## 3. lyy `skills`（46 字段）映射 → `skill.*`

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `skills.analysis_task` | `skill.method_profile.analysis_task` | **新子块** |
| `skills.method_category` | `skill.skill_category` / `skill.method_profile.method_category` | cyx 已有 skill_category |
| `skills.method_name` | `skill.method_profile.method_name` | 论文方法原文 |
| `skills.algorithm_name` | `skill.method_profile.algorithm_name` | **新增键** |
| `skills.software_name` | `analyses[].software_tools[].tool_name` + `skill.method_profile.software_name` | 双落 |
| `skills.software_version` | `analyses[].software_tools[].version` + `skill.method_profile.software_version` | 双落 |
| `skills.input_modalities` | `skill.method_profile.input_modalities` | **新增键** |
| `skills.genotype_data_format` | `skill.method_profile.genotype_data_format` | 文献未报省略 |
| `skills.phenotype_data_format` | `skill.method_profile.phenotype_data_format` | 同上 |
| `skills.environment_data_format` | `skill.method_profile.environment_data_format` | 同上 |
| `skills.preprocessing_steps` | `skill.method_profile.preprocessing_steps` | 流程编排 |
| `skills.qc_filters` | `skill.method_profile.qc_filters` | 质控规则原文 |
| `skills.parameters` | `skill.method_profile.parameters`（统一 array_parameter：param_name/type/value/value_kind/unit/约束/来源） | **新增键**；同时 `analyses[].parameters` 同构 |
| `skills.population_structure_control` | `skill.method_profile.population_structure_control` | **新增键** |
| `skills.kinship_control` | `skill.method_profile.kinship_control` | **新增键** |
| `skills.feature_count` | `skill.method_profile.feature_count` | **新增键** |
| `skills.training_population` | `skill.validation.training_population` | **新子块** |
| `skills.training_set_size` | `skill.validation.training_set_size` | 新子块 |
| `skills.test_set_size` | `skill.validation.test_set_size` | 新子块 |
| `skills.validation_strategy` | `skill.validation.strategy` + `analyses[].validation_design.strategy` | 双落 |
| `skills.folds` | `skill.validation.folds` + `analyses[].validation_design.k_folds` | 双落 |
| `skills.split_basis` | `skill.validation.split_basis` | 防泄漏原则 |
| `skills.random_seed` | `skill.validation.random_seed` | **新增键** |
| `skills.output_artifacts` | `skill.method_profile.output_artifacts` + `analyses[].outputs[]` | 双落 |
| `skills.output_fields` | `skill.method_profile.output_fields` | **新增键** |
| `skills.metric_name` | `skill.validation.metrics[].name` + `analyses[].key_results` | 双落 |
| `skills.metric_value` | `skill.validation.metrics[].value` | 双落 |
| `skills.metric_unit` | `skill.validation.metrics[].unit` | **新增键** |
| `skills.significance_threshold` | `skill.method_profile.significance_threshold` + `analyses[].significance_thresholds[]` | 双落 |
| `skills.method_assumptions` | `skill.method_profile.method_assumptions` + `analyses[].model_assumptions` | 双落 |
| `skills.applicability_limit` | `skill.method_profile.applicability_limit` | **新增键** |
| `skills.reproducibility_assets` | `skill.method_profile.reproducibility_assets`（引用 assets[]） | **新增键** |
| `skills.tool_description_uri` | `skill.skill_registry.tool_description_uri` | **新子块** |
| `skills.input_schema_ref` | `skill.skill_registry.input_schema_ref` + `skill.io_adapter` | 双落 |
| `skills.output_schema_ref` | `skill.skill_registry.output_schema_ref` | 双落 |
| `skills.parameter_schema_ref` | `skill.skill_registry.parameter_schema_ref` | 双落 |
| `skills.workflow_steps` | `skill.workflow_orchestration.dag_steps` + `skill.method_profile.workflow_steps` | cyx 已含工作流编排 |
| `skills.genotyping_method` | `skill.method_profile.genotyping_method` | **新增键** |
| `skills.phenotyping_method` | `skill.method_profile.phenotyping_method` | **新增键** |
| `skills.target_variable` | `skill.method_profile.target_variable` | **新增键** |
| `skills.threshold_calibration` | `skill.method_profile.threshold_calibration` | **新增键** |
| `skills.skill_spec_id` | `skill.skill_registry.skill_spec_id` | 可调用技能 ID |
| `skills.skill_spec_version` | `skill.skill_registry.skill_spec_version` | 接口版本 |
| `skills.input_asset_refs` | `skill.skill_registry.input_asset_refs` | 引用 assets[] |
| `skills.output_asset_refs` | `skill.skill_registry.output_asset_refs` | 引用 assets[] |
| `skills.runtime_environment_ref` | `skill.skill_registry.runtime_environment_ref` | **新增键** |

---

## 4. lyy `transform`（40 字段）映射 → `transform.*`（新块）

> 新顶层块 `transform`：`{ graph_statements:[], corpus_chunks:[], qa_pairs:[], corpus_split, leakage_group_id, dedup_group_id, ontology_version, derivative_license_id, transform_review_status }`。

| 来源路径 | merged 归属 | 说明 |
| --- | --- | --- |
| `transform.subject_mention` | `transform.graph_statements[].subject_mention` | **新块** |
| `transform.subject_type` | `transform.graph_statements[].subject_type` | 新块 |
| `transform.subject_id` | `transform.graph_statements[].subject_id` | 新块 |
| `transform.predicate_label` | `transform.graph_statements[].predicate_label` | 新块 |
| `transform.predicate_id` | `transform.graph_statements[].predicate_id` | 新块 |
| `transform.object_mention` | `transform.graph_statements[].object_mention` | 新块 |
| `transform.object_type` | `transform.graph_statements[].object_type` | 新块 |
| `transform.object_id` | `transform.graph_statements[].object_id` | 新块 |
| `transform.relation_polarity` | `transform.graph_statements[].relation_polarity` | 增加/降低/无显著/未知 |
| `transform.relation_qualifiers` | `transform.graph_statements[].relation_qualifiers` | 群体/环境/时间处理限定 |
| `transform.graph_statement_id` | `transform.graph_statements[].graph_statement_id` | 语句稳定 ID |
| `transform.graph_status` | `transform.graph_statements[].graph_status` | 候选/已审核/已发布 |
| `transform.entity_alignment_status` | `transform.graph_statements[].entity_alignment_status` | 未链接/候选/已链接 |
| `transform.entity_alignment_source` | `transform.graph_statements[].entity_alignment_source` | 词表版本 |
| `transform.external_graph_ids` | `transform.graph_statements[].external_graph_ids` | 外部图节点/边 ID |
| `transform.provenance_record_ids` | `transform.graph_statements[].provenance_record_ids` | 支持语句的证据 ID |
| `transform.relation_evidence_type` | `transform.graph_statements[].relation_evidence_type` | 统计定位/表达支持/功能验证 |
| `transform.ontology_version` | `transform.ontology_version` | 主谓宾 ID 依赖的本体版本 |
| `transform.chunk_id` | `transform.corpus_chunks[].chunk_id` | **新块** |
| `transform.chunk_text` | `transform.corpus_chunks[].chunk_text` | 检索文本 |
| `transform.chunk_page` | `transform.corpus_chunks[].chunk_page` | 所在页 |
| `transform.chunk_section` | `transform.corpus_chunks[].chunk_section` | 所属章节 |
| `transform.chunk_start_offset` | `transform.corpus_chunks[].chunk_start_offset` | 字符偏移 |
| `transform.chunk_end_offset` | `transform.corpus_chunks[].chunk_end_offset` | 字符偏移 |
| `transform.chunk_keywords` | `transform.corpus_chunks[].chunk_keywords` | 检索召回词 |
| `transform.chunk_support_ids` | `transform.corpus_chunks[].chunk_support_ids` | 原子证据 ID |
| `transform.qa_seed_question` | `transform.qa_pairs[].seed_question` | **新块** |
| `transform.qa_seed_answer` | `transform.qa_pairs[].seed_answer` | 新块 |
| `transform.qa_answerable` | `transform.qa_pairs[].answerable` | 证据覆盖 |
| `transform.qa_support_ids` | `transform.qa_pairs[].support_ids` | 证据单元 ID |
| `transform.qa_reasoning_path_ids` | `transform.qa_pairs[].reasoning_path_ids` | 多跳图谱路径 |
| `transform.qa_difficulty` | `transform.qa_pairs[].difficulty` | 单跳/多跳/跨模态 |
| `transform.qa_answer_scope` | `transform.qa_pairs[].answer_scope` | 适用范围 |
| `transform.qa_unanswerable_reason` | `transform.qa_pairs[].unanswerable_reason` | 无法作答原因 |
| `transform.qa_review_status` | `transform.qa_pairs[].review_status` | 抽检状态 |
| `transform.leakage_group_id` | `transform.leakage_group_id` | **新键**（防泄漏） |
| `transform.corpus_split` | `transform.corpus_split` | train/validation/test |
| `transform.dedup_group_id` | `transform.dedup_group_id` | 近重复聚类 |
| `transform.derivative_license_id` | `transform.derivative_license_id` | 派生许可，不推断版权 |
| `transform.transform_review_status` | `transform.transform_review_status` | 转化产物审核 |

---

## 5. d v2.0.0 多组学模板 → merged 映射

> d 模板为扁平键集合，映射到 `breed_entities.omics_samples[]`、`breed_entities.omics_experiments[]`、`observations[].omics_feature`、`relations`、`assets[]` 与受控词表附录。

### 5.1 通用块

| 来源键 | merged 归属 | 说明 |
| --- | --- | --- |
| `schema_info`（schema 版本/语言/研究问题） | `schema_version` + `README` | 设计说明并入 README |
| `missing_value_convention` | `skill.io_adapter.missing_value_convention` | 空值约定统一 |
| `basic_identity.*` | `doc_meta`/`record_info` | record_id/source_id/doi 等与 cyx 同义合并 |
| `evidence_span` | `provenance.source_locations[]` | 并入细定位 |
| `species_and_material.*` | `species_list` + `germplasm[]` + `populations[]` | germplasm_id/name/type、accession、parental_line、population 全部并入 |
| `data_files.*` | `assets[]` | raw/processed format、checksum、data_availability |
| `data_processing.*` | `analyses[]` + `skill.method_profile` | qc/preprocessing/normalization/analysis/software/parameters |
| `quality_and_provenance.*` | `provenance.*` | extraction_method/confidence、review、quality_flag、notes |
| `controlled_vocabularies.candidate_gene_status` | 附录 A-12 受控词表 + `genes[].candidate_status` | 枚举吸收 |

### 5.2 样本/组织/组学实验 → `breed_entities.omics_samples[]` / `omics_experiments[]`

| 来源块 | merged 归属 | 说明 |
| --- | --- | --- |
| `sample.sample_id/name/type` | `omics_samples[].sample_id/name/type` | **新子块** |
| `sample.biological_replicate/technical_replicate` | `omics_samples[].biological_replicate/technical_replicate` | 新子块 |
| `sample.batch_id` | `omics_samples[].batch_id` | 新子块 |
| `sample.sex` | `omics_samples[].sex` | 新子块 |
| `sample.ploidy` | `omics_samples[].ploidy` | 新子块 |
| `tissue_and_development.*` | `omics_samples[].{organ,tissue,cell_type,cell_state,development_stage,sampling_time,sampling_time_relative}` | 新子块 |
| `treatment_and_environment.*` | `environments[]`+`experiments[].treatments[]` | treatment/control/location/year/soil/ph/光温湿灌 | `treatments[]` 结构化并入 |
| `omics_experiment.omics_type` | `omics_experiments[].omics_type` | 受控词表：genomics/transcriptomics/single_cell/epigenomics/proteomics/metabolomics |
| `omics_experiment.assay_type` | `omics_experiments[].assay_type` | RNA-seq/WGS/ATAC-seq… |
| `experimental_design` | `omics_experiments[].design` + `experiments[].experimental_design` | 合并 |
| `library_strategy/selection/layout` | `omics_experiments[].library_{strategy,selection,layout}` | **新子块键** |
| `platform`/`instrument_model` | `omics_experiments[].platform`/`instrument_model` | 新子块键 |
| `sequencing_depth`/`read_length` | `omics_experiments[].sequencing_depth`/`read_length` | 新子块键 |
| `reference_system.*` | `omics_experiments[].reference_genome` + `{reference_genome_version,annotation_version,gene_id_system,coordinate_system}` | 新子块键 |

### 5.3 统一特征/统计/组学专块 → `observations[].omics_feature`

| 来源块 | merged 归属 | 说明 |
| --- | --- | --- |
| `unified_feature.feature_type/id/name/value/unit` | `observations[].feature{_type,_id,_name,_value,_unit}` | **统一特征接口**（d 核心贡献） |
| `statistical_results.contrast` | `observations[].statistic.contrast` | 新键 |
| `statistical_results.effect_direction/size` | `observations[].statistic.effect_direction/effect_size` | 新键 |
| `statistical_results.standard_error` | `observations[].statistic.standard_error` | 新键 |
| `statistical_results.p_value/q_value/confidence_interval` | `observations[].statistic.{p_value,q_value,confidence_interval}` | 新键 |
| `genomics_specific.*` | `observations[].variant.{chromosome,position,start_position,end_position,variant_id,variant_type,ref_allele,alt_allele,effect_allele,genotype_call,allele_frequency,minor_allele_frequency,genotype_quality,read_depth,haplotype_id,structural_variant_type}` | 变异行 |
| `qtl_gwas_specific.*` | `qtls[]`（已有 chr/start/end/lod/pve/model/结构修正/阈值/候选基因） | 与 cyx 合并 |
| `transcriptomics_specific.*` | `observations[].omics_feature(transcriptomics).{gene_id,transcript_id,expression_value,expression_unit,raw_count,log2_fold_change,base_mean,deg_status,deg_threshold,coexpression_module,gene_set,pathway_id,go_term}` | 新块 |
| `single_cell_specific.*` | 同 `omics_feature(single_cell)`：cell_id/type/state/cluster/marker_genes/qc/integration/trajectory/pseudotime/interaction | 新块 |
| `epigenomics_specific.*` | 同 `omics_feature(epigenomics)`：assay/peak/histone/methylation/motif/tf/regulatory_gene/differential_peak | 新块 |
| `proteomics_specific.*` | 同 `omics_feature(proteomics)`：protein/peptide/abundance/fold_change/q_value/ms/method/id_score/PTM/interaction | 新块 |
| `metabolomics_specific.*` | 同 `omics_feature(metabolomics)`：metabolite/db_id/formula/mz/rt/abundance/fold_change/q_value/annotation_level/pathway |
| `breeding_links.*` | `relations[]` + `qtls[]` + `traits[]` | trait_raw→traits[].aliases、trait_ontology_id→T-04、phenotype→observations、linked_gene/variant/qtl→relations |

### 5.4 证据/跨组学/跨物种/发现/技能 → `relations` / `agent` / `skill`

| 来源块 | merged 归属 | 说明 |
| --- | --- | --- |
| `evidence.*` | `relations[].{supporting_method,relation_confidence}` + `conclusions[].evidence_list[]` | validation_type/status、replication、contradiction 合并 |
| `cross_omics.*` | `relations[]`（subject/object=feature，relation_type=`跨组学-调控`) + `relations[].relation_qualifiers.multiomics_support_count` | 新关系类型加枚举 |
| `cross_omics_relation.*` | `relations[]` + `observations[].statistic` | source/target/relation/direction/effect/evidence/context/validation |
| `cross_species.*` | `genes[].ortholog_in_model[]` + `breed_entities.cross_species[]`(**新子块**) | ortholog_id/species/type/synteny/evidence |
| `research_discovery.*` | `agent_state` + `agent.scientific_reasoning` + `conclusions[]` | research_question/hypothesis/main_finding/knowledge_gap/limitation/future_direction/breeding_implication 全并入 |
| `tool_skill.*` | `skill.tool_bindings[]` + `skill.method_profile` | tool I/O/param/dependency/validation/failure_modes 并入 |
| `ontology_mapping.*` | `pipeline.ontology_mapping[]` + `entities[].ontology_id[]` | mapping_type/confidence/synonyms 并入 |

---

## 6. 合并取舍说明（决策记录）

1. **粒度**：文档行 `record_kind=document` 为主；claim/observation/asset/analysis_result/tool_spec/transform 为单位行，**非空即入**，不做深嵌套主记录之外的固定行。
2. **回链锚点**：单位行通过**顶层 `record_parent_id`**（指向文档主记录 `record_id`）+ `provenance.source_locations[]` 回链；`provenance.source_record_id` 保留「源系统中的原始记录 ID」语义（用于幂等导入），两者不混用。
3. **命名**：JSON 键以 cyx camelCase 为规范；lyy snake_case 作为逻辑别名在映射表保留，脚本可平移。
4. **高维数据不内嵌**：VCF/表达矩阵/代谢物全表 → `assets[]`；只抽取显著差异 feature 行 → `observations[]`。
5. **证据分层**：GWAS/QTL/BSA/表达/功能验证分级保存；关联证据不自动升级为因果，`causal_flag` 仅强证据可 true。
6. **许可不推断**：`derivative_license_id`/`license_id` 均不猜测版权。
7. **缺失值约定**：论文未报告字段省略，不用空串/猜值；数值缺失不填 0（`measurement.value` 除外需显式）。

---

*映射完成于 merged v2.0.0 对齐。字段归属如与 `breeding_jsonl_schema_v2.json` 冲突，以 Schema 与 `breeding_jsonl_spec_v2.md` 为准。*
