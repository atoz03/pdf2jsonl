"""Function / role annotations of fields (AMB-032): which of the four record functions a key serves, which
facets of those functions it feeds, and which statements come from the sources rather than the repository.

Works on the catalog and on a compiled contract alike (both carry ``codes``, ``groups`` and ``fields``).
"""
from __future__ import annotations


def source_functions(cat: dict, f: dict) -> list[str]:
    """Functions a field serves according to the sources: its group's `serves` plus every function whose
    `downstream_labels` occur in the v3 downstream column. Empty for fields without a downstream statement."""
    ds = f.get("downstream_zh")
    if not ds:
        return []
    found = set(cat["groups"].get(f["path"].split(".")[0], {}).get("serves") or [])
    codes_of: dict[str, set[str]] = {}
    for code, spec in cat["codes"]["function"].items():
        for label in spec.get("downstream_labels") or []:
            codes_of.setdefault(label, set()).add(code)
    for label in sorted(codes_of, key=len, reverse=True):  # longest first: 全部转化 is not 全部
        if label in ds:
            found |= codes_of[label]
            ds = ds.replace(label, "\0")
    return [c for c in cat["codes"]["function"] if c in found]


def source_card(cat: dict, f: dict) -> str | None:
    """The card named by the v3 downstream column (假设卡, 实验设计卡, 结果分析卡, ...), if any."""
    ds = f.get("downstream_zh") or ""
    return next((code for code, spec in (cat["codes"].get("card") or {}).items()
                 if ds in (spec.get("downstream_labels") or [])), None)


def field_facets(cat: dict, f: dict) -> dict[str, list[str]]:
    """Facets a field feeds: its key_role's facets restricted to the functions the field serves."""
    spec = (cat["codes"].get("key_role") or {}).get(f.get("key_role"), {})
    return {fn: list((spec.get("facets") or {}).get(fn) or []) for fn in f.get("serves") or []}


def added_functions(contract: dict, f: dict) -> list[str]:
    """Functions the repository added beyond the source statement (all of them for fields without one)."""
    src = set(source_functions(contract, f))
    return [fn for fn in f.get("serves") or [] if fn not in src]
