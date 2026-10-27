"""3.6.0: the semantic nature of a relation is contract data, not a reading of the record (AMB-042).

Three layers that must not be conflated: the nature of the predicate (`transform.relation_nature`, derived from
the `nature` of the vocabulary code), the wording of the paper (`transform.relation_assertion_mode`), and the
strength of the evidence (`transform.relation_evidence_type`). R036/R037 keep an association from being read as a
causation.
"""
from __future__ import annotations

import copy

import pytest

from breeding_contract import resolve_schema
from breeding_contract.api import load_profile
from breeding_contract.util import del_path, get_path, set_path
from pdf2jsonl_skill.fill_rules import REGISTRY
from pdf2jsonl_skill.pipeline import RunOptions, run

from conftest import EXAMPLE_CANDIDATES, EXAMPLE_PDF, read_jsonl


@pytest.fixture(scope="module")
def rc(root):
    return resolve_schema("latest", root)


@pytest.fixture(scope="module")
def _run_records(root, tmp_path_factory):
    out = tmp_path_factory.mktemp("relation_semantics")
    opts = RunOptions(backend="candidates", candidates_file=str(EXAMPLE_CANDIDATES), out_dir=str(out),
                      run_id="run_relation_semantics")
    return read_jsonl(run(EXAMPLE_PDF, opts).outputs["records"])


@pytest.fixture
def statement(_run_records):
    """A fresh copy of one statement record from the example paper (subject – predicate – object).

    Function-scoped on purpose: the tests edit the record, and a shared dict would leak the edits.
    """
    return copy.deepcopy(next(r for r in _run_records
                              if "explained 23.5%" in (get_path(r, "common.source_quote", None) or "")))


class _Run:
    def __init__(self, rc):
        self.rc = rc


class _Ctx:
    """The slice of RecordContext the fill rule touches: the contract and the record under construction."""

    def __init__(self, rc, record):
        self.run, self.record, self.notes = _Run(rc), record, {}

    def value(self, path):
        return get_path(self.record, path)


# ------------------------------------------------------------------ the three layers

def test_nature_is_assigned_to_every_predicate_code(rc):
    """A code a reviewer can choose must say what the relation asserts: no code is left 'unknown'."""
    natures = rc.contract["relation_natures"]
    codes = {v["code"] for v in rc.contract["vocabularies"]["predicate_label"]["values"]}
    assert set(natures) == codes
    assert set(natures.values()) <= {"causal", "associational", "structural", "descriptive", "unknown"}
    assert "unknown" not in natures.values()
    # the two codes the association rule names are associational, the control relation is causal
    assert natures["qtl_associated_with_trait"] == natures["gene_associated_with_trait"] == "associational"
    assert natures["genotype_controls_trait"] == natures["gene_interacts_with_gene"] == "causal"
    assert natures["cross_omics_regulates"] == "causal"


def test_nature_is_derived_from_the_contract_not_judged(rc, statement):
    """The rule reads the compiled map: the derivation is deterministic and independent of the model."""
    rule = REGISTRY["relation_nature_from_predicate"]
    params = {"inputs": {"predicate": "transform.predicate_label", "code": "transform.predicate_code"},
              "outputs": {"nature": "transform.relation_nature"}}
    ctx = _Ctx(rc, statement)
    del_path(ctx.record, "transform.predicate_label")
    # unreviewed: the code the pipeline matched names the same contract judgement, so the nature reaches the record
    assert rule.fn(ctx, params) == {"transform.relation_nature": "associational"}
    del_path(ctx.record, "transform.predicate_code")
    del_path(ctx.record, "transform.relation_nature")
    assert rule.fn(ctx, params) == {}                       # nothing to derive: the field stays absent
    assert not get_path(ctx.record, "transform.relation_nature", None)
    for code, nature in (("qtl_associated_with_trait", "associational"), ("genotype_controls_trait", "causal"),
                         ("synonym_of", "descriptive"), ("variety_derived_from", "structural")):
        set_path(ctx.record, "transform.predicate_label", code)
        assert rule.fn(ctx, params) == {"transform.relation_nature": nature}
    set_path(ctx.record, "transform.predicate_label", "no_such_code")
    assert rule.fn(ctx, params) == {}


def test_extraction_is_never_asked_for_the_nature(root):
    """The nature is N; the assertion mode is D and reaches the model through the brief."""
    prof = load_profile("pdf_extraction", "latest", root)
    by_path = {f["path"]: f for f in prof["fields"]}
    assert by_path["transform.relation_nature"]["availability"] == "N"
    assert by_path["transform.relation_assertion_mode"]["availability"] == "D"
    assert "transform.relation_nature" not in {f["path"] for f in prof["fields"] if f["role"] == "extract"}


# ------------------------------------------------------------------ the two rules

def _warn_codes(validator, rec):
    return {i.code for i in validator.validate(rec).warnings}


def test_flat_association_without_evidence_is_flagged(rc, statement):
    v = rc.validator()
    rec = statement
    set_path(rec, "transform.predicate_label", "qtl_associated_with_trait")
    set_path(rec, "transform.relation_nature", "associational")
    set_path(rec, "transform.relation_assertion_mode", "stated")
    for p in ("transform.relation_evidence_type", "agent.supporting_evidence"):
        del_path(rec, p)
    assert "RULE_R036" in _warn_codes(v, rec) and v.validate(rec).valid   # a warning, never a rejection

    justified = copy.deepcopy(rec)
    set_path(justified, "transform.relation_evidence_type", "statistical_mapping")
    assert "RULE_R036" not in _warn_codes(v, justified)

    hedged = copy.deepcopy(rec)
    set_path(hedged, "transform.relation_assertion_mode", "hedged")
    assert "RULE_R036" not in _warn_codes(v, hedged)                       # the paper already qualifies it

    evidenced = copy.deepcopy(rec)
    set_path(evidenced, "agent.supporting_evidence", [{"quote": get_path(rec, "common.source_quote")}])
    assert "RULE_R036" not in _warn_codes(v, evidenced)                    # D evidence justifies it too


def test_causal_relation_should_state_its_evidence(rc, statement):
    v = rc.validator()
    rec = statement
    set_path(rec, "transform.predicate_label", "genotype_controls_trait")
    set_path(rec, "transform.relation_nature", "causal")
    del_path(rec, "transform.relation_evidence_type")
    assert "RULE_R037" in _warn_codes(v, rec)
    set_path(rec, "transform.relation_evidence_type", "functional_validation")
    assert "RULE_R037" not in _warn_codes(v, rec)
    # an association is not asked for causal evidence
    set_path(rec, "transform.relation_nature", "associational")
    del_path(rec, "transform.relation_evidence_type")
    assert "RULE_R037" not in _warn_codes(v, rec)


def test_the_example_record_carries_no_new_warning(rc, statement):
    """The shipped example is a verbatim paper record; the new rules must not fire on it unchanged."""
    assert not ({"RULE_R036", "RULE_R037"} & _warn_codes(rc.validator(), statement))


# ------------------------------------------------------------------ the derived views carry the three layers

def test_derived_statement_carries_the_nature_from_the_record_or_the_code(rc, statement):
    """The page reads the nature off the derived statement, so `statement()` must project it (AMB-042).

    A reviewer's value wins; when the record has none, the reviewed code `predicate_code` names is the same
    deterministic judgement, so its `nature` (contract data) fills the gap instead of guessing.
    """
    from breeding_contract.derive import Deriver
    d = Deriver(rc.contract)
    rec = copy.deepcopy(statement)
    for p in ("transform.relation_nature", "transform.predicate_code", "transform.predicate_label"):
        del_path(rec, p)
    assert "relation_nature" not in d.statement(rec)                      # nothing to say: the key is absent
    set_path(rec, "transform.predicate_code", "qtl_associated_with_trait")
    assert d.statement(rec)["relation_nature"] == "associational"         # from the code's contract nature
    set_path(rec, "transform.relation_nature", "causal")                  # the record's own value wins
    assert d.statement(rec)["relation_nature"] == "causal"


def test_derived_statement_carries_the_assertion_mode(rc, statement):
    from breeding_contract.derive import Deriver
    rec = copy.deepcopy(statement)
    set_path(rec, "transform.relation_assertion_mode", "hedged")
    assert Deriver(rc.contract).statement(rec)["relation_assertion_mode"] == "hedged"


def test_claim_strength_puts_the_evidence_beside_the_wording(rc, statement):
    """3.8.0 (AMB-046): a causal predicate is never settled by the verb alone, and never downgraded either."""
    rule = REGISTRY["claim_strength_from_evidence"]
    params = {"inputs": {"nature": "transform.relation_nature", "evidence_type": "transform.relation_evidence_type"},
              "outputs": {"strength": "transform.claim_strength"}}
    ctx = _Ctx(rc, statement)
    set_path(ctx.record, "transform.relation_nature", "causal")
    del_path(ctx.record, "transform.relation_evidence_type")
    assert rule.fn(ctx, params) == {"transform.claim_strength": "causal_unverified"}
    for evidence, expected in (("functional_validation", "causal_supported"),
                               ("genetic_interaction", "causal_supported"),
                               ("biochemical_assay", "causal_supported"),
                               ("expression_support", "causal_expression_supported"),
                               ("statistical_mapping", "causal_statistical_only")):
        set_path(ctx.record, "transform.relation_evidence_type", evidence)
        assert rule.fn(ctx, params) == {"transform.claim_strength": expected}, evidence
    set_path(ctx.record, "transform.relation_nature", "associational")
    set_path(ctx.record, "transform.relation_evidence_type", "functional_validation")
    assert rule.fn(ctx, params) == {"transform.claim_strength": "associational"}   # evidence never upgrades
    set_path(ctx.record, "transform.relation_nature", "unknown")
    assert rule.fn(ctx, params) == {}


def test_validation_status_reads_the_link_not_the_wording(rc, statement):
    """3.8.0 (AMB-045): candidate vs experiment_reported comes from the validated_by link only."""
    rule = REGISTRY["validation_status_from_links"]
    params = {"inputs": {"links": "agent.validated_by_record_ids", "predicate": "transform.predicate_mention"},
              "outputs": {"status": "transform.validation_status"}}

    class Ctx(_Ctx):
        record_kind = "claim"

    ctx = Ctx(rc, statement)
    del_path(ctx.record, "agent.validated_by_record_ids")
    assert rule.fn(ctx, params) == {"transform.validation_status": "candidate"}
    set_path(ctx.record, "agent.validated_by_record_ids", ["rec_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"])
    assert rule.fn(ctx, params) == {"transform.validation_status": "experiment_reported"}
    # a method record with no relation is not a conclusion and gets no status
    class Method(Ctx):
        record_kind = "method"
    mctx = Method(rc, copy.deepcopy(statement))
    del_path(mctx.record, "transform.predicate_mention")
    assert rule.fn(mctx, params) == {}


def test_evidence_origin_marks_a_review(rc, statement):
    """3.8.0 (AMB-047): only the review case is written; the document type already travels with every record."""
    rule = REGISTRY["evidence_origin_from_document_type"]
    params = {"inputs": {"document_type": "common.source_document_type"},
              "outputs": {"origin": "transform.evidence_origin"}}
    ctx = _Ctx(rc, statement)
    set_path(ctx.record, "common.source_document_type", "journal_paper")
    assert rule.fn(ctx, params) == {}
    set_path(ctx.record, "common.source_document_type", "review")
    assert rule.fn(ctx, params) == {"transform.evidence_origin": "review_report"}


def test_the_new_cue_classes_resolve_without_guessing_direction(rc):
    """3.8.0 (AMB-046): the four classes the trial needed, with active/passive and overlap kept apart."""
    from breeding_contract.relations import predicate_code
    voc = rc.contract["vocabularies"]["predicate_label"]
    assert predicate_code(voc, "colocalizes with", ["qtl"], ["qtn"]) == "locus_overlaps_locus"
    assert predicate_code(voc, "coincides with", ["qtn"], ["qtl"]) == "locus_overlaps_locus"
    assert predicate_code(voc, "has major effects on", ["gene"], ["trait"]) == "locus_affects_trait"
    assert predicate_code(voc, "is mainly controlled by", ["trait"], ["gene"]) == "trait_controlled_by_gene"
    assert predicate_code(voc, "is upstream of", ["gene"], ["gene"]) == "gene_upstream_of_gene"
    assert predicate_code(voc, "was completely deleted in", ["gene"], ["variety"]) == "gene_absent_in_germplasm"
    assert predicate_code(voc, "were tightly linked to", ["qtl"], ["gene"]) == "locus_linked_to_locus"
    assert predicate_code(voc, "was associated with", ["qtn"], ["trait"]) == "qtn_associated_with_trait"
    assert predicate_code(voc, "correlation was observed between", ["trait"], ["trait"]) == "trait_correlated_with_trait"


def test_qtn_is_its_own_entity_type(rc):
    """3.8.0 (AMB-045): QTN, QTL and candidate gene are three entities; a candidate gene is not renamed a QTN."""
    from breeding_contract.relations import entity_type
    fields = {f["path"]: f for f in rc.contract["fields"]}
    assert entity_type("common.qtn_names") == "qtn"
    assert entity_type("common.qtl_names") == "qtl"
    assert entity_type("common.gene_names") == "gene"
    assert fields["common.qtn_names"]["availability"] == "D" and \
        fields["common.qtn_names"]["key_role"] == "entity_mention"
    # the QTN can carry an association of its own, and the other locus codes accept it as an end
    from breeding_contract.relations import predicate_code
    voc = rc.contract["vocabularies"]["predicate_label"]
    assert predicate_code(voc, "was associated with", ["qtn"], ["trait"]) == "qtn_associated_with_trait"
    assert predicate_code(voc, "overlapped with", ["qtn"], ["qtl"]) == "locus_overlaps_locus"


def test_a_predicate_keeps_its_direction(rc):
    """A cue counts only in a mention of its own voice, so no edge comes out reversed — with or without types."""
    from breeding_contract.relations import predicate_code
    voc = rc.contract["vocabularies"]["predicate_label"]
    # active: the subject acts on the object
    assert predicate_code(voc, "controlled", ["gene"], ["trait"]) == "genotype_controls_trait"
    assert predicate_code(voc, "affected", [], ["trait"]) == "environment_affects_trait"
    # passive: "plant height was controlled by qPH7.1" has the trait as subject, so it goes to the passive code
    # (3.8.0, AMB-046) and never to the active one; a subject typed as a gene cannot take the passive code
    assert predicate_code(voc, "was controlled by", [], []) == "trait_controlled_by_gene"
    assert predicate_code(voc, "was controlled by", ["trait"], ["gene"]) == "trait_controlled_by_gene"
    assert predicate_code(voc, "was controlled by", ["gene"], ["trait"]) is None
    assert predicate_code(voc, "was affected by", ["trait"], []) is None
    assert predicate_code(voc, "受一个主效基因调控", ["qtl"], ["gene"]) is None
    # suppress/suppressed by are two codes with opposite subjects; neither may serve the other
    assert predicate_code(voc, "suppressed", ["gene"], ["gene"]) == "gene_suppresses_gene"
    assert predicate_code(voc, "was almost completely suppressed by", ["gene"], ["gene"]) == "gene_suppressed_by_gene"
    # a "by" that only modifies the object leaves the main verb active; 被认为 (is considered) is no passive
    assert predicate_code(voc, "decreased the degree of chalkiness conferred by", [], ["trait"]) == "locus_decreases_trait"
    assert predicate_code(voc, "被认为与株高显著相关", ["qtl"], ["trait"]) == "qtl_associated_with_trait"
    # the passive code names the regulated locus as its subject, so an active "regulates" never matches it
    assert predicate_code(voc, "are likely regulated by", ["qtl"], ["gene"]) == "locus_regulated_by_gene"
    assert predicate_code(voc, "regulates", ["gene"], ["gene"]) is None
    assert predicate_code(voc, "调控", ["gene"], ["gene"]) is None
