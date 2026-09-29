"""Source-to-contract mappings (mappings/*.yaml): leaf enumeration, matching and coverage checks."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import jsonschema

from .compile import compile_contract, field_index
from .sources import load_sources, meta_schema
from .util import load_json, load_yaml, parse_semver

TRANSFER_STATUSES = {"mapped", "partial", "transformed", "merged"}


def legacy_schema_leaves(schema: dict) -> list[str]:
    """Enumerate leaf paths of the legacy v1 JSON Schema (arrays of objects as ``name[]``)."""
    defs = schema.get("$defs", {})
    out: list[str] = []

    def walk(node: dict, path: str) -> None:
        if "$ref" in node:
            return walk(defs[node["$ref"].split("/")[-1]], path)
        t = node.get("type")
        if t == "object" and node.get("properties"):
            for k, v in node["properties"].items():
                walk(v, f"{path}.{k}" if path else k)
        elif t == "array" and isinstance(node.get("items"), dict) and \
                (node["items"].get("properties") or "$ref" in node["items"]):
            walk(node["items"], path + "[]")
        else:
            out.append(path)
    walk(schema, "")
    return out


def template_leaves(template: dict) -> list[str]:
    skip = {"schema_info", "controlled_vocabularies"}
    return [f"{g}.{k}" for g, v in template.items() if g not in skip and isinstance(v, dict) for k in v]


def source_leaves(root: Path, mapping: dict) -> list[str]:
    src = mapping["source"]
    doc = load_json(root / src["file"])
    if src["leaf_source"] == "json_schema":
        return legacy_schema_leaves(doc)
    return template_leaves(doc)


def entry_matches(pattern: str, path: str) -> bool:
    if pattern.endswith(".**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + ".") or path.startswith(prefix + "[]")
    return pattern == path


def _covers(source: str, path: str) -> bool:
    """``source`` is a ``prefix.**`` pattern matching ``path``, or an exact entry for an ancestor of ``path``
    (a schema leaf that is a free-form object, e.g. ``analyses[].key_results`` covers its data-defined keys)."""
    if source.endswith(".**"):
        return entry_matches(source, path)
    return path.startswith(source + ".") or path.startswith(source + "[]")


def match_entry(entries: list[dict], path: str) -> dict | None:
    """Exact match wins; otherwise the longest covering entry (``prefix.**`` pattern or free-form ancestor)."""
    for e in entries:
        if e["source"] == path:
            return e
    best = None
    for e in entries:
        if _covers(e["source"], path):
            if best is None or len(e["source"].removesuffix(".**")) > len(best["source"].removesuffix(".**")):
                best = e
    return best


def entry_targets(entry: dict) -> list[str]:
    return ([entry["target"]] if entry.get("target") else []) + list(entry.get("targets") or [])


@lru_cache(maxsize=8)
def load_mapping(root_str: str, name: str) -> dict:
    return load_yaml(Path(root_str) / "mappings" / f"{name}.yaml")


def check_mapping(root: Path, mapping: dict, contract: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    mid = mapping["id"]
    v = jsonschema.Draft202012Validator(meta_schema(root, "mapping"))
    for e in v.iter_errors(mapping):
        out.append(("error", f"{mid}: {'/'.join(map(str, e.absolute_path))}: {e.message[:200]}"))
    if out:
        return out
    if mapping["target"]["contract"] != contract["name"]:
        out.append(("error", f"{mid}: target contract {mapping['target']['contract']} != {contract['name']}"))
    if parse_semver(mapping["target"]["min_version"]) > parse_semver(contract["version"].split("-")[0]):
        out.append(("error", f"{mid}: min_version {mapping['target']['min_version']} newer than contract"))
    idx = field_index(contract)
    leaves = source_leaves(root, mapping)
    entries = mapping["entries"]
    used = set()
    for leaf in leaves:
        e = match_entry(entries, leaf)
        if e is None:
            out.append(("error", f"{mid}: source path {leaf} is not covered by any entry"))
        else:
            used.add(id(e))
    issue_ids = {i["id"] for i in mapping.get("issues") or []}
    for e in entries:
        if id(e) not in used:
            out.append(("error", f"{mid}: entry {e['source']} matches no source path (stale)"))
        for t in entry_targets(e):
            if t not in idx:
                out.append(("error", f"{mid}: {e['source']} -> unknown target field {t}"))
            elif idx[t]["status"] != "active":
                out.append(("warning", f"{mid}: {e['source']} -> deprecated target {t}"))
        if e["status"] == "merged":
            for t in entry_targets(e):
                if t in idx and mapping["source"]["id"] not in idx[t]["origin"]:
                    out.append(("error", f"{mid}: {e['source']} merged into {t} but the field's origin lacks "
                                         f"{mapping['source']['id']}"))
        for iid in e.get("issues") or []:
            if iid not in issue_ids:
                out.append(("error", f"{mid}: {e['source']} references unknown issue {iid}"))
    sources_seen = [e["source"] for e in entries]
    if len(sources_seen) != len(set(sources_seen)):
        out.append(("error", f"{mid}: duplicate entry sources"))
    return out


def coverage_summary(root: Path, mapping: dict) -> dict:
    from collections import Counter
    leaves = source_leaves(root, mapping)
    c = Counter()
    for leaf in leaves:
        e = match_entry(mapping["entries"], leaf)
        c[e["status"] if e else "uncovered"] += 1
    return {"leaves": len(leaves), "by_status": dict(sorted(c.items()))}


def check_all_mappings(root: Path) -> list[tuple[str, str]]:
    files = sorted((root / "mappings").glob("*.yaml"))
    if not files:
        return []
    contract = compile_contract(load_sources(root))
    out = []
    for p in files:
        mapping = load_yaml(p)
        if mapping.get("id") != p.stem:
            out.append(("error", f"mappings/{p.name}: id {mapping.get('id')!r} must equal file stem"))
            continue
        out.extend(check_mapping(root, mapping, contract))
    return out
