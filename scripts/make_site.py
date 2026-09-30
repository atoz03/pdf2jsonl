#!/usr/bin/env python3
"""Build the static demo site (GitHub Pages) from the latest release and the checked-in examples.

    PYTHONPATH=src python scripts/make_site.py [--out _site]

Nothing on the page is hand-written data: fields, profiles, vocabularies and rules come from the resolved
release; the PDF -> JSONL walk-through comes from examples/ (synthetic paper, agent candidates, pipeline output).
The page itself is one self-contained HTML file (site/index.template.html + embedded JSON).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "skills/pdf2jsonl/scripts"):
    sys.path.insert(0, str(p))

from breeding_contract.api import available_versions, resolve_schema  # noqa: E402
from breeding_contract.derive import Deriver  # noqa: E402
from breeding_contract.functions import source_functions  # noqa: E402
from breeding_contract.schema_gen import rule_paths  # noqa: E402
from breeding_contract.util import load_json  # noqa: E402

EX = ROOT / "examples"
PAPER = "synthetic_rice_qtl"
FIELD_KEYS = ("path", "group", "type", "availability", "required", "definition_zh", "data_source_zh",
              "downstream_zh", "since", "status", "maturity", "origin", "vocabulary", "ambiguities", "source_ref",
              "constraints", "key_role", "serves", "card", "argument_role")


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def contract_data(rc) -> dict:
    c = rc.contract
    vocabs = []
    for name, v in sorted(c["vocabularies"].items()):
        if v.get("vocabulary_type") == "unit_conversion":
            continue
        vocabs.append({"name": name, "title_zh": v.get("title_zh"), "enforcement": v.get("enforcement"),
                       "closure": v.get("closure"), "code_status": v.get("code_status"),
                       "values": [{k: x[k] for k in ("code", "label_zh", "aliases") if x.get(k)}
                                  for x in v.get("values", [])]})
    profiles = {}
    for name in rc.profile_names():
        p = rc.profile(name)
        profiles[name] = {"title_zh": p.get("title_zh"), "description_zh": p.get("description_zh"),
                          "extends_chain": p.get("extends_chain"),
                          "roles": {f["path"]: f["role"] for f in p["fields"]}}
    return {
        "name": c["name"], "version": rc.version, "title_zh": c["title_zh"], "baseline_zh": c.get("baseline_zh"),
        "codes": c["codes"], "groups": c["groups"], "record_kinds": c["record_kinds"],
        "fields": [{**{k: f[k] for k in FIELD_KEYS if f.get(k) not in (None, [], {})},
                    "serves_src": source_functions(c, f)} for f in c["fields"]],
        "rules": [{"id": r["id"], "severity": r["severity"], "basis": r["basis"], "kind": r["kind"],
                   "title_zh": r["title_zh"], "fields": rule_paths(r)} for r in c["rules"]],
        "vocabularies": vocabs,
        "ambiguities": c["ambiguities"],
        "profiles": profiles,
    }


def demo_data(rc) -> dict:
    from pdf2jsonl_skill.brief import render_brief
    from pdf2jsonl_skill.pdf_parse import parse_document
    from pdf2jsonl_skill.pipeline import resolve_contract

    out = EX / "output"
    manifest = load_json(out / f"{PAPER}.manifest.json")
    version = manifest["contract"]["schema_version"]
    doc = parse_document(EX / "papers" / f"{PAPER}.pdf")
    rc_demo, profile = resolve_contract(version, "pdf_extraction", False)
    records = jsonl(out / f"{PAPER}.jsonl")
    deriver = Deriver(rc_demo.contract)
    tables, triples, corpus = deriver.tables(records), deriver.triples(records), deriver.corpus(records)
    return {
        "file_name": f"{PAPER}.pdf",
        "pages": [p.text for p in doc.pages],
        "candidates": load_json(EX / "papers" / f"{PAPER}.candidates.json"),
        "records": records,
        "errors": jsonl(out / f"{PAPER}.errors.jsonl"),
        "validation": load_json(out / f"{PAPER}.validation.json"),
        "manifest": {k: manifest[k] for k in ("run_id", "contract", "profile", "input", "backend", "counts")},
        "brief": render_brief(rc_demo, profile, "pages.txt", "candidates.json", "candidate.schema.json"),
        "record_links": profile.get("record_links") or {},
        # function 3 on the demo output (`bdc derive`): counts plus the rows a reader can check by eye
        "derived": {
            "counts": {**{f"table:{k}": len(v) for k, v in tables.items()}, "triples": len(triples),
                       "corpus_chunks": len(corpus)},
            "record_links": tables["record_links"],
            "statements": [t for t in triples if "statement" in t],
            "entity_triples": list({t["p"]: t for t in reversed(triples) if t["o_kind"] == "iri"
                                    and str(t["o"]).startswith(("ent:", "rec:")) and t["s"].startswith("rec:")}.values())[::-1],
            "corpus": corpus[:4],
        },
    }


def gallery() -> list[dict]:
    items = []
    for p in sorted((EX / "records").glob("*.jsonl")):
        items.append({"source": "curated example", "file": str(p.relative_to(ROOT)), "record": jsonl(p)[0]})
    seen = set()
    for label, p in (("pdf2jsonl output", EX / "output" / f"{PAPER}.jsonl"),
                     ("legacy v1 migration", EX / "migration/legacy_v1/breeding_jsonl_example.migrated.jsonl"),
                     ("omics v2 migration", EX / "migration/omics_v2/synthetic_deg_instance.migrated.jsonl")):
        for r in jsonl(p):
            key = (label, r["common"]["record_kind"])
            if key not in seen:
                seen.add(key)
                items.append({"source": label, "file": str(p.relative_to(ROOT)), "record": r})
    order = list(resolve_schema("latest", ROOT).contract["record_kinds"])
    items.sort(key=lambda x: (order.index(x["record"]["common"]["record_kind"]), x["source"]))
    return items


def versions() -> list[dict]:
    index = load_json(ROOT / "releases/index.json")
    out = []
    for r in index["releases"]:
        if r["version"] not in available_versions(ROOT):
            continue
        rc = resolve_schema(r["version"], ROOT)
        out.append({"version": r["version"], "released_on": r["released_on"], "fields": len(rc.fields),
                    "rules": len(rc.contract["rules"]), "vocabularies": len(rc.contract["vocabularies"]),
                    "profiles": rc.profile_names(), "latest": r["version"] == index["latest"]})
    return out


def build(out_dir: Path) -> Path:
    rc = resolve_schema("latest", ROOT)
    data = {"contract": contract_data(rc), "demo": demo_data(rc), "gallery": gallery(), "versions": versions(),
            "repo": "https://github.com/atoz03/pdf2jsonl"}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = (ROOT / "site/index.template.html").read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/null", payload).replace("__VERSION__", rc.version)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    print(build(ap.parse_args().out))
