"""The Pages site: one build writes eight pages that share one shell (site/kit) and link to each other — the
overview, the pipeline, the walk-through, the downstream outputs, the paper dashboard, the importers, the field
catalog and the contract reference."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from scripts import make_site

PAGES = ("index.html", "pipeline.html", "demo.html", "outputs.html", "papers.html", "importers.html", "fields.html",
         "contract.html")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    make_site.build(out)
    return out


def embedded(html: str, element_id: str = "site-data") -> dict:
    return json.loads(re.search(rf'<script id="{element_id}" type="application/json">(.*?)</script>', html, re.S).group(1))


def page(site, name: str) -> str:
    return (site / name).read_text(encoding="utf-8")


def test_one_build_writes_every_page_on_the_shared_shell(site, root):
    kit = (root / "site/kit/kit.js").read_text(encoding="utf-8")
    for name in PAGES:
        text = page(site, name)
        assert text.startswith("<!doctype html>") and not re.search(r"__[A-Z][A-Z_]+__|/\*__\w+__\*/|<!--__\w+__-->", text), name
        assert f'data-page="{name[:-5]}"' in text and "K.mount(" in text and embedded(text)["site"]["version"], name
        assert f'href: "{name}"' in kit, f"{name} is missing from the shared navigation"
    assert (site / ".nojekyll").is_file() and (site / "assets/pipeline.svg").is_file() and (site / "assets/pipeline.en.svg").is_file()


def test_pages_link_only_to_each_other_and_to_files_in_the_site(site):
    for name in PAGES:
        text = page(site, name)
        for href in set(re.findall(r'(?:href|src)="([^"#$][^"$]*)"', text)):
            if href.startswith(("http://", "https://", "data:", "mailto:")):
                continue
            assert (site / href.split("#")[0].split("?")[0]).exists(), f"{name} links to {href}, which is not in the site"
    papers = page(site, "papers.html")
    assert '<base href="./">' in papers and 'href="outputs.html' in papers and "README.md" not in papers
    assert "README" not in page(site, "pipeline.html")


def test_fields_page_carries_every_field_with_its_example_and_tags(site):
    data = embedded(page(site, "fields.html"))["contract"]
    assert all("example" in f and f.get("tags") for f in data["fields"])
    assert set(data["tags"]) >= {"research_1", "research_2", "iteration", "general"}


def test_outputs_page_carries_the_derived_outputs_and_their_files(site):
    data = embedded(page(site, "outputs.html"))
    derived = data["derived"]
    assert derived["counts"]["statements"] == len(derived["statements"]) == 3
    ids = {n["id"] for n in derived["graph"]["nodes"]}
    assert all(e["s"] in ids and e["o"] in ids for e in derived["graph"]["edges"])
    assert derived["qa"] and derived["corpus"] and set(derived["tables"]) >= {"records", "statements", "record_entities"}
    for rel in derived["files"]:   # every listed download exists
        assert (site / rel).is_file()
    assert json.loads((site / "derived/synthetic_rice_qtl.graph.json").read_text()) == derived["graph"]
    assert set(data["relation_roles"]) == {"relation_subject", "relation_predicate", "relation_object"}
    assert data["workflow"]["workflow"]["nodes"]


def test_importers_are_shown_uniformly(site, root):
    importers = {i["command"]: i for i in embedded(page(site, "importers.html"))["importers"]}
    assert set(importers) == {"legacy", "omics", "merged"}
    for imp in importers.values():
        assert sum(imp["status"].values()) == imp["leaves"] > 0 and imp["counts"]["records"] >= 1
        assert (root / imp["mapping_file"]).is_file() and (root / imp["input"]).is_file() and imp["sample"]["common"]["record_id"]
    gallery = embedded(page(site, "contract.html"))["gallery"]
    assert {g["source"] for g in gallery} >= {"curated", "pdf2jsonl", "legacy", "omics", "merged"}


def test_pipeline_page_counts_every_candidate_through_the_gates(site):
    gates = embedded(page(site, "pipeline.html"))["gates"]
    n = len(gates["candidates"])
    assert n and all(r["ci"] is None or 0 <= r["ci"] < n for r in gates["records"])
    # every candidate either became a record or was rejected
    kept = {r["ci"] for r in gates["records"] if r["ci"] is not None}
    assert len(kept) + len(gates["rejected"]) == n
    assert gates["verification"]["independent"] and gates["verification"]["counts"]["verdicts"]


def test_papers_page_carries_its_files_and_the_new_exports(site):
    data = embedded(page(site, "papers.html"))
    assert data["summary"]["papers"] >= 1 and data["summary"]["runs"] >= 1 and data["site"]["version"]
    paper = next(p for p in data["papers"] if p["filename"] == "synthetic_rice_qtl.pdf")
    assert (site / paper["pdf_url"]).is_file()
    run = paper["runs"][0]
    assert run["integrity_ok"] and all((site / url).is_file() for url in run["urls"].values())
    assert run["derived"]["counts"]["statements"] == 3 and run["derived"]["qa"] and run["derived"]["graph"]["nodes"]
    assert all(not p["pdf_paths"] or p["pdf_paths"][0].startswith("examples/") for p in data["papers"])  # checked-in only


def test_papers_page_shows_a_two_file_paper_as_one_paper(site):
    text = page(site, "papers.html")
    data = embedded(text)
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
    for needle in ("来源不完整", "研究流程结构", "补充材料"):
        assert needle in text


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_page_scripts_parse(site, tmp_path):
    for name in PAGES:
        text = page(site, name)
        scripts = [body for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", text, re.S) if "application/json" not in attrs]
        assert len(scripts) >= 3, name   # theme boot, kit, page
        for i, body in enumerate(scripts):
            path = tmp_path / f"{name}.{i}.js"
            path.write_text(body, encoding="utf-8")
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            assert result.returncode == 0, f"{name}: {result.stderr[:400]}"
