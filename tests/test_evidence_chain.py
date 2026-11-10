"""Evidence chains: claim -> result -> experiment/method, complete or visibly incomplete."""
from __future__ import annotations

from breeding_contract.evidence_chain import build_chain


def rec(rid, kind="claim", **agent):
    return {"common": {"record_id": rid, "record_kind": kind, "source_page": 1, "source_section": "Results",
                       "source_quote": f"quote {rid}"},
            "agent": agent}


def method(rid):
    return {"common": {"record_id": rid, "record_kind": "method", "source_page": 1, "source_section": "Methods",
                       "source_quote": f"method {rid}"},
            "skills": {"method_name": f"method {rid}"}}


def test_complete_chain_reaches_the_experiment():
    records = [
        rec("c", finding_text="gene controls trait", evidence_record_ids=["r"]),
        rec("r", kind="observation", actual_observation="knockout changed the trait", method_record_ids=["m"]),
        method("m"),
    ]
    # method links live on the result, not on the claim
    records[1]["skills"] = {"method_record_ids": ["m"]}
    chain = build_chain(records, "c")
    assert chain["complete"] is True
    assert chain["data_count"] == 1
    assert chain["method_count"] == 1
    assert chain["missing"] == []
    assert [n["record_id"] for n in chain["nodes"]] == ["c", "r", "m"]


def test_a_claim_without_links_is_incomplete_not_invented():
    chain = build_chain([rec("c", finding_text="a claim")], "c")
    assert chain["complete"] is False
    assert chain["applicable"] is True
    assert "未链接到数据/结果记录" in chain["missing"]
    assert "未链接到实验/方法记录" in chain["missing"]


def test_result_without_method_reports_the_missing_experiment():
    records = [
        rec("c", evidence_record_ids=["r"]),
        rec("r", kind="observation", actual_observation="observed"),
    ]
    chain = build_chain(records, "c")
    assert chain["complete"] is False
    assert chain["data_count"] == 1
    assert chain["method_count"] == 0
    assert chain["missing"] == ["未链接到实验/方法记录"]


def test_background_statement_is_not_scored_as_an_incomplete_experiment():
    chain = build_chain([rec("b", statement_role="background", finding_text="background")], "b")
    assert chain["applicable"] is False
    assert chain["complete"] is False
    assert chain["missing"] == []


def test_a_cycle_does_not_recurse_forever():
    records = [
        rec("c", evidence_record_ids=["r"]),
        rec("r", kind="observation"),
        method("m"),
    ]
    records[1]["skills"] = {"method_record_ids": ["m"]}
    records[2]["agent"] = {"prerequisite_record_ids": ["c"]}
    chain = build_chain(records, "c")
    assert chain["complete"] is True
    assert [n["record_id"] for n in chain["nodes"]].count("c") == 1


def test_missing_anchor_is_reported():
    chain = build_chain([rec("c")], "nope")
    assert chain["anchor"] is None
    assert chain["complete"] is False
    assert chain["missing"] == ["记录不存在"]
