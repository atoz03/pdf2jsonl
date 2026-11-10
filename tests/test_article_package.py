"""Article package: complete, partial, unverified; missing is visible and never guessed."""
from __future__ import annotations

from breeding_contract.article_package import build_package


def record(quote="", cited=None, table=None, license_id=None):
    return {"common": {"record_id": "r", "source_quote": quote, "source_table_figure": table,
                       "license_id": license_id},
            "transform": {"cited_source_items": cited or []}}


def main_pages(text="Results\nTable 1 Summary of QTLs.\n"):
    return [{"page": 1, "text": text}]


def test_complete_package_with_supplement_items():
    pkg = build_package(
        [record("see Fig. S1 and Table 1", cited=["Fig. S1"], table="Table 1")],
        input={"file_name": "paper.pdf", "sha256": "a" * 64, "page_count": 1},
        source_parts={"complete": True, "parts": [], "missing": []},
        pages=main_pages(),
        supplements=[{"part": "supplement", "file_name": "supp.pdf", "page_count": 1,
                      "pages": [{"page": 1, "text": "Fig. S1 Survival of lines."}]}],
        title="Paper", doi="10.1/x", year=2026,
    )
    assert pkg["status"] == "complete"
    assert pkg["figures"]["supplement_cited"] == ["Fig. S1"]
    assert pkg["tables"]["cited"] == ["Table 1"]
    assert pkg["missing"] == []
    assert pkg["data_code"]["status"] == "not_detected"
    assert pkg["license"]["status"] == "not_detected"


def test_cited_supplement_without_a_file_is_partial():
    pkg = build_package(
        [record("see Fig. S4", cited=["Fig. S4"])],
        input={"file_name": "paper.pdf", "sha256": "a" * 64, "page_count": 1},
        source_parts={"complete": False, "parts": [], "missing": [{"part": "supplement"}]},
        pages=main_pages(),
        supplements=[],
    )
    assert pkg["status"] == "partial"
    assert pkg["supplement"]["missing_items"] == ["Fig. S4"]
    assert any("Supplement" in m for m in pkg["missing"])


def test_no_text_layer_is_unverified_not_missing():
    pkg = build_package(
        [record("see Fig. S4", cited=["Fig. S4"])],
        input={"file_name": "paper.pdf", "sha256": "a" * 64, "page_count": 1},
        source_parts={"complete": False, "parts": [{"part": "supplement", "supplied": True, "text_pages": 0}],
                      "missing": []},
        pages=[],
        supplements=[{"part": "supplement", "file_name": "supp.pdf", "page_count": 1, "pages": []}],
    )
    assert pkg["status"] == "unverified"
    assert any("文本层" in m for m in pkg["missing"])


def test_data_code_and_license_are_reported_as_recommendations():
    pkg = build_package(
        [record("Data availability: https://example.org/data", license_id="CC-BY-4.0")],
        input={"file_name": "paper.pdf", "sha256": "a" * 64, "page_count": 1},
        pages=[{"page": 1, "text": "Data availability: https://example.org/data\n"}],
        supplements=[],
    )
    assert pkg["data_code"]["status"] == "present"
    assert pkg["license"]["status"] == "present"
    assert pkg["license"]["values"] == ["CC-BY-4.0"]
    assert pkg["status"] == "complete"
