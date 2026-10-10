"""The Pages site: one build that shows the contract, the example run, its downstream outputs, the importers and
the paper dashboard."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from scripts import make_site

PAGES = ("index.html", "papers.html", "pipeline.html")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    make_site.build(out)
    return out


def embedded(html: str, element_id: str) -> dict:
    return json.loads(re.search(rf'<script id="{element_id}" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_one_build_writes_every_page_and_no_placeholder_survives(site):
    for name in PAGES:
        text = (site / name).read_text(encoding="utf-8")
        assert text.startswith("<!doctype html>") and not re.search(r"__[A-Z][A-Z_]+__|/\*__\w+__\*/|<!--__\w+__-->", text), name
    assert (site / ".nojekyll").is_file() and (site / "assets/pipeline.en.svg").is_file()


def test_pages_link_only_to_each_other_and_to_files_in_the_site(site):
    for name in PAGES:
        text = (site / name).read_text(encoding="utf-8")
        for href in set(re.findall(r'(?:href|src)="([^"#$][^"$]*)"', text)):
            if href.startswith(("http://", "https://", "data:", "${")):
                continue
            assert (site / href.split("#")[0].split("?")[0]).exists(), f"{name} links to {href}, which is not in the site"
    papers = (site / "papers.html").read_text(encoding="utf-8")
    assert '<base href="./">' in papers and 'href="index.html#downstream"' in papers and "README.md" not in papers
    assert "README" not in (site / "pipeline.html").read_text(encoding="utf-8")


def test_index_shows_fields_with_examples_tags_and_the_downstream_outputs(site, root):
    data = embedded((site / "index.html").read_text(encoding="utf-8"), "site-data")
    fields = data["contract"]["fields"]
    assert all("example" in f and f.get("tags") for f in fields) and set(data["contract"]["tags"]) >= {"research_1", "general"}
    derived = data["demo"]["derived"]
    assert derived["counts"]["statements"] == len(derived["statements"]) == 3
    ids = {n["id"] for n in derived["graph"]["nodes"]}
    assert all(e["s"] in ids and e["o"] in ids for e in derived["graph"]["edges"])
    assert derived["qa"] and derived["corpus"] and set(derived["tables"]) >= {"records", "statements", "record_entities"}
    for rel in derived["files"]:   # every listed download exists
        assert (site / rel).is_file()
    assert json.loads((site / "derived/synthetic_rice_qtl.graph.json").read_text()) == derived["graph"]
    assert set(data["demo"]["relation_roles"]) == {"relation_subject", "relation_predicate", "relation_object"}


def test_importers_are_shown_uniformly(site, root):
    data = embedded((site / "index.html").read_text(encoding="utf-8"), "site-data")
    importers = {i["command"]: i for i in data["importers"]}
    assert set(importers) == {"legacy", "omics", "merged"}
    for imp in importers.values():
        assert sum(imp["status"].values()) == imp["leaves"] > 0 and imp["counts"]["records"] >= 1
        assert (root / imp["mapping_file"]).is_file() and (root / imp["input"]).is_file() and imp["sample"]["common"]["record_id"]
    assert {g["source"] for g in data["gallery"]} >= {"legacy import", "omics import", "merged import", "pdf2jsonl output"}


def test_papers_page_carries_its_files_and_the_new_exports(site):
    data = embedded((site / "papers.html").read_text(encoding="utf-8"), "dashboard-data")
    assert data["summary"]["papers"] >= 1 and data["summary"]["runs"] >= 1
    paper = next(p for p in data["papers"] if p["filename"] == "synthetic_rice_qtl.pdf")
    assert (site / paper["pdf_url"]).is_file()
    run = paper["runs"][0]
    assert run["integrity_ok"] and all((site / url).is_file() for url in run["urls"].values())
    assert run["derived"]["counts"]["statements"] == 3 and run["derived"]["qa"] and run["derived"]["graph"]["nodes"]
    assert all(not p["pdf_paths"] or p["pdf_paths"][0].startswith("examples/") for p in data["papers"])  # checked-in only


def test_papers_page_shows_a_two_file_paper_as_one_paper(site):
    data = embedded((site / "papers.html").read_text(encoding="utf-8"), "dashboard-data")
    assert data["summary"]["papers"] == 2  # the supplement is a part of its paper, not a third paper
    paper = next(p for p in data["papers"] if p["filename"] == "synthetic_rice_heat.pdf")
    [part] = paper["supplements"]
    assert part["part"] == "supplement" and part["filename"] == "synthetic_rice_heat.supplement.pdf"
    assert (site / part["pdf_url"]).is_file() and len(part["pages"]) == 2
    with_supplement, main_only = paper["runs"]  # newest first: the run that had the supplement
    assert with_supplement["source_parts"]["complete"] and not main_only["source_parts"]["complete"]
    assert main_only["source_parts"]["missing"] == ["supplement"]
    assert with_supplement["workflow"]["flags"] == {"HYPOTHESIS_UNTESTED": 1, "STEP_WITHOUT_OUTPUT": 1}
    assert with_supplement["counts"]["workflow_flags"] == 2
    assert with_supplement["derived"]["workflow"]["hypotheses"]
    template = (site / "papers.html").read_text(encoding="utf-8")
    for needle in ("来源不完整", "研究流程结构", "补充材料"):
        assert needle in template


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_page_scripts_parse(site, tmp_path):
    for name in PAGES:
        text = (site / name).read_text(encoding="utf-8")
        scripts = [body for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", text, re.S) if "application/json" not in attrs]
        assert scripts, name
        for i, body in enumerate(scripts):
            path = tmp_path / f"{name}.{i}.js"
            path.write_text(body, encoding="utf-8")
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            assert result.returncode == 0, f"{name}: {result.stderr[:400]}"
