"""pdf2jsonl Skill runtime: PDF -> atomic JSONL records that satisfy the repository data contract.

The Skill defines *how* extraction runs; *what* the data means is resolved at runtime from the
repository (releases/<version>/). Nothing here hard-codes field definitions: profiles declare roles and
named fill rules, and this package implements those rules (see fill_rules.IMPLEMENTED_RULES).
"""
PIPELINE_VERSION = "0.1.0"

# Contract family and major versions this pipeline implements. Minor/patch releases of the contract are
# consumed automatically; a new major may introduce rules the pipeline does not know (CI checks this).
SUPPORTED_CONTRACT = "breeding-literature-record"
SUPPORTED_MAJORS = (3,)
