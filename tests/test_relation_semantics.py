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
    params = {"inputs": {"predicate": "transform.predicate_label"}, "outputs": {"nature": "transform.relation_nature"}}
    ctx = _Ctx(rc, statement)
    del_path(ctx.record, "transform.predicate_label")
    assert rule.fn(ctx, params) == {}                       # unreviewed: the field stays absent, nothing is guessed
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
