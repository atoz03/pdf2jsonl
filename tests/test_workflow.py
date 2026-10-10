"""3.5.0: the research workflow of a paper as roles and links between records (AMB-039)."""
from __future__ import annotations

import copy
import json

import pytest

from breeding_contract import resolve_schema
from breeding_contract.derive import Deriver, counts, derive_file
from breeding_contract.util import get_path, set_path
from breeding_contract.workflow import FLAG_HELP, workflow_audit, workflow_view
from pdf2jsonl_skill.pipeline import RunOptions, run

from conftest import (EXAMPLE_CANDIDATES, EXAMPLE_PDF, HEAT_CANDIDATES, HEAT_PDF, HEAT_SUPPLEMENT, read_jsonl,
                      records_by_ref, run_bdc)

EDGE_FIELDS = {"evidence": "agent.evidence_record_ids", "method": "skills.method_record_ids",
               "tests": "agent.tests_record_ids", "addresses": "agent.addresses_record_ids",
               "prerequisite": "agent.prerequisite_record_ids"}


@pytest.fixture(scope="module")
def rc(root):
    return resolve_schema("latest", root)


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("workflow")
    return run(HEAT_PDF, RunOptions(candidates_file=str(HEAT_CANDIDATES), supplements=[str(HEAT_SUPPLEMENT)],
                                    out_dir=str(out), run_id="run_workflow"))


@pytest.fixture(scope="module")
def by_ref(result):
    return records_by_ref(result, HEAT_CANDIDATES)


@pytest.fixture(scope="module")
def view(result, rc):
    return workflow_view(read_jsonl(result.outputs["records"]), rc.contract)


def rid(by_ref, ref):
    return by_ref[ref]["common"]["record_id"]


def flags_of(records, rc):
    return {n["id"]: n.get("flags", []) for n in workflow_view(records, rc.contract)["nodes"]}


# ------------------------------------------------------------------ contract

def test_catalog_marks_the_link_fields_that_are_workflow_edges(rc):
    fields = {f["path"]: f for f in rc.contract["fields"]}
    assert {f["workflow_edge"]: p for p, f in fields.items() if f.get("workflow_edge")} == EDGE_FIELDS
    assert set(rc.contract["codes"]["workflow_edge"]) == set(EDGE_FIELDS)
    for path in EDGE_FIELDS.values():
        assert fields[path]["key_role"] == "record_link" and fields[path]["type"] == "array_string"
        assert fields[path]["availability"] == "N"  # resolved by the pipeline, never written by the model
    role = fields["agent.statement_role"]
    assert role["availability"] == "D" and role["vocabulary"] == "statement_role"
    codes = [v["code"] for v in rc.contract["vocabularies"]["statement_role"]["values"]]
    assert codes == ["background", "research_question", "objective", "hypothesis", "design", "result", "conclusion"]


def test_profile_resolves_the_three_new_links(rc):
    links = rc.profile("pdf_extraction")["record_links"]
    assert {k: v["field"] for k, v in links.items()} == EDGE_FIELDS
    assert links["tests"]["target_kinds"] == ["claim"]
    assert "method" in links["prerequisite"]["target_kinds"]


# ------------------------------------------------------------------ extraction

def test_links_become_record_ids(by_ref):
    assert by_ref["m_ko"]["agent"]["tests_record_ids"] == [rid(by_ref, "h_under")]
    assert by_ref["h_under"]["agent"]["addresses_record_ids"] == [rid(by_ref, "obj")]
    assert by_ref["m_adv"]["agent"]["prerequisite_record_ids"] == [rid(by_ref, "m_bc"), rid(by_ref, "m_heat")]
    assert by_ref["m_adv"]["agent"]["step_condition"] == "Only recombinant plants that survived the heat treatment"
    assert by_ref["h_under"]["agent"]["statement_role"] == "hypothesis"
    # one sentence, two records: the hypothesis and the step that tests it
    assert by_ref["h_under"]["common"]["source_quote"] == by_ref["m_ko"]["common"]["source_quote"]
    assert rid(by_ref, "h_under") != rid(by_ref, "m_ko")


def test_report_carries_the_workflow_audit(result, rc):
    report = json.loads(result.outputs["validation"].read_text())
    audit = report["workflow_structure"]
    assert audit == workflow_audit(read_jsonl(result.outputs["records"]), rc.contract)
    assert audit["stages"] == {"background": 1, "research_question": 1, "objective": 1, "hypothesis": 2, "design": 2,
                               "step": 5, "observation": 1, "result": 4, "conclusion": 1, "statement": 1}
    assert audit["edges_by_type"] == {"addresses": 5, "evidence": 3, "method": 7, "prerequisite": 5, "tests": 2}
    assert audit["links"] == {"total": 22, "unresolved": 0}
    assert audit["flags"] == {"HYPOTHESIS_UNTESTED": 1, "STEP_WITHOUT_OUTPUT": 1}


# ------------------------------------------------------------------ the view

def test_nodes_are_records_and_edges_are_their_links(view, result, by_ref):
    ids = {r["common"]["record_id"] for r in read_jsonl(result.outputs["records"])}
    nodes = {n["id"]: n for n in view["nodes"]}
    assert set(nodes) < ids  # asset records are not part of a workflow
    assert all(e["s"] in nodes and e["o"] in nodes for e in view["edges"])
    assert all(e["field"] == EDGE_FIELDS[e["type"]] for e in view["edges"])
    assert nodes[rid(by_ref, "m_ko")]["stage"] == "step"
    assert nodes[rid(by_ref, "r_ko")]["stage"] == "result"          # an observation the paper reports as a result
    assert nodes[rid(by_ref, "o_s1")]["stage"] == "observation"
    assert nodes[rid(by_ref, "m_stat")]["stage"] == "design"
    assert nodes[rid(by_ref, "gap")]["stage"] == "statement"        # a claim without a role
    assert nodes[rid(by_ref, "m_heat")]["source_part"] == "supplement"
    assert nodes[rid(by_ref, "m_adv")]["condition"].startswith("Only recombinant plants")


def test_hypothesis_traces_show_what_tests_each_one(view, by_ref):
    traces = {t["hypothesis"]: t for t in view["hypotheses"]}
    tested = traces[rid(by_ref, "h_under")]
    assert tested["label"] == "HTR1 underlies qHT3"
    assert tested["addresses"] == [rid(by_ref, "obj")]
    assert set(tested["tested_by"]) == {rid(by_ref, "m_ko"), rid(by_ref, "r_ko")}
    untested = traces[rid(by_ref, "h_recruit")]
    assert "tested_by" not in untested and untested["addresses"] == [rid(by_ref, "q")]
    nodes = {n["id"]: n for n in view["nodes"]}
    assert nodes[rid(by_ref, "h_recruit")]["flags"] == ["HYPOTHESIS_UNTESTED"]
    assert "flags" not in nodes[rid(by_ref, "h_under")]


def test_order_follows_dependencies_not_presentation(view, by_ref):
    order = view["step_order"]
    pos = {r: i for i, r in enumerate(order)}
    for step, needs in (("m_bc", "r_sl14"), ("a_map", "m_bc"), ("m_adv", "m_bc"), ("m_adv", "m_heat"), ("m_ko", "a_map")):
        assert pos[rid(by_ref, needs)] < pos[rid(by_ref, step)]
    # the heat treatment is described last (in the supplement) and is needed before the selection step
    assert pos[rid(by_ref, "m_heat")] < pos[rid(by_ref, "m_adv")]
    assert view["branch_points"] == [rid(by_ref, "m_bc")]  # fine mapping and selection both start from the cross
    assert len(order) == len(set(order))


def test_structural_flags(result, rc, by_ref):
    records = read_jsonl(result.outputs["records"])

    def edit(ref, path, value):
        out = copy.deepcopy(records)
        rec = next(r for r in out if r["common"]["record_id"] == rid(by_ref, ref))
        if value is None:
            group, key = path.split(".")
            del rec[group][key]
        else:
            set_path(rec, path, value)
        return out
    assert flags_of(edit("c_up", "agent.evidence_record_ids", None), rc)[rid(by_ref, "c_up")] == \
        ["CONCLUSION_WITHOUT_EVIDENCE"]
    assert flags_of(edit("r_luc", "skills.method_record_ids", None), rc)[rid(by_ref, "r_luc")] == \
        ["RESULT_WITHOUT_METHOD"]
    assert flags_of(edit("q", "agent.addresses_record_ids", None), rc)[rid(by_ref, "bg")] == []
    assert flags_of(edit("h_under", "agent.addresses_record_ids", None), rc)[rid(by_ref, "obj")] == \
        ["QUESTION_UNADDRESSED"]
    cyc = flags_of(edit("r_sl14", "agent.prerequisite_record_ids", [rid(by_ref, "m_ko")]), rc)
    assert "DEPENDENCY_CYCLE" in cyc[rid(by_ref, "m_ko")] and "DEPENDENCY_CYCLE" in cyc[rid(by_ref, "m_bc")]
    assert "DEPENDENCY_CYCLE" not in cyc[rid(by_ref, "m_heat")]
    dangling = edit("m_ko", "agent.tests_record_ids", ["rec_" + "0" * 32])
    assert flags_of(dangling, rc)[rid(by_ref, "m_ko")] == ["UNRESOLVED_LINK"]
    assert [i for _, i in rc.validator().validate_dataset(dangling) if i.code == "RULE_R035"]
    assert not [i for _, i in rc.validator().validate_dataset(records) if i.code == "RULE_R035"]
    assert set(FLAG_HELP) >= {f for fs in cyc.values() for f in fs}


def test_a_gap_is_shown_not_closed(by_ref, view):
    """The paper reports an interaction assay right after the second hypothesis and never says the assay tests it."""
    assert "tests_record_ids" not in by_ref["r_luc"]["agent"]
    assert not any(e["type"] == "tests" and e["o"] == rid(by_ref, "h_recruit") for e in view["edges"])


# ------------------------------------------------------------------ derive, audit, older contracts

def test_derive_writes_the_workflow(result, rc, tmp_path, view):
    report = derive_file(result.outputs["records"], tmp_path, rc)
    stem = result.outputs["records"].name[:-6]
    written = json.loads((tmp_path / f"{stem}.workflow.json").read_text())
    assert written == view
    assert report["counts"]["workflow_nodes"] == len(view["nodes"]) == 19
    assert report["counts"]["workflow_edges"] == len(view["edges"]) == 22
    links = [r for r in Deriver(rc.contract).views(read_jsonl(result.outputs["records"]))["tables"]["record_links"]]
    assert len(links) == len(view["edges"])


def test_audit_command_reports_the_workflow(result, root):
    out = json.loads(run_bdc(root, "audit", str(result.outputs["records"]), "--json").stdout)
    assert out["workflow"]["flags"] == {"HYPOTHESIS_UNTESTED": 1, "STEP_WITHOUT_OUTPUT": 1}
    text = run_bdc(root, "audit", str(result.outputs["records"])).stdout
    assert "HYPOTHESIS_UNTESTED" in text and "prerequisite=5" in text


def test_contracts_without_workflow_edges_have_no_workflow(root, tmp_path, epoch):
    old = resolve_schema("3.4.0", root)
    res = run(EXAMPLE_PDF, RunOptions(schema_version="3.4.0", candidates_file=str(EXAMPLE_CANDIDATES),
                                      out_dir=str(tmp_path), run_id="run_340"))
    assert workflow_view(res.records, old.contract) is None and workflow_audit(res.records, old.contract) is None
    views = Deriver(old.contract).views(res.records)
    assert views["workflow"] is None and "workflow_nodes" not in counts(views)
    derive_file(res.outputs["records"], tmp_path / "derived", old)
    assert not list((tmp_path / "derived").glob("*.workflow.json"))


def test_the_first_example_still_has_a_workflow_of_evidence_and_method_links(root, rc):
    records = read_jsonl(root / "examples/output/synthetic_rice_qtl.jsonl")
    view = workflow_view(records, rc.contract)
    assert set(view["edges_by_type"]) == {"evidence", "method"} and view["hypotheses"] == []
    assert all(get_path(r, "agent.statement_role", None) is None for r in records)
