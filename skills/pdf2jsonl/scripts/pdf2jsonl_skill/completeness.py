"""Source completeness: which parts of a paper the text refers to, and which of them were supplied (AMB-041).

A paper is often more than one file. The library may hold only the main text while the text cites
"fig. S2" or says that materials and methods are in the supplementary materials. The pipeline cannot extract
what it was not given, but it can say so: this module scans the supplied text for references to supplementary
items and reports the parts that are referenced but neither supplied as a file nor present in the supplied
pages. Detection is literal (labels and stock phrases); it never guesses what a missing part contains.
"""
from __future__ import annotations

import re

from .pdf_parse import MAIN_PART, SUPPLEMENT_PART, ParsedDocument

APPENDIX_PART = "appendix"

_KIND = (r"(?P<kind>Fig(?:ure)?s?\.?|Tables?|Movies?|Videos?|Data\s?sets?|Data|Notes?|Methods|Text|Files?|"
         r"附图|附表|补充图|补充表)")
_END = r"(?![A-Za-z0-9_])"  # "S7_1203" is a marker name, not supplementary item S7
_NUMS = (r"(?P<nums>S\s?\d+[A-Za-z]?" + _END +
         r"(?:\s*(?:,|and|to|through|–|-|&|和|至|、)\s*(?:S\s?)?\d+[A-Za-z]?" + _END + r")*)")
ITEM_RE = re.compile(r"(?<![A-Za-z])" + _KIND + r"\s*" + _NUMS, re.IGNORECASE)
_NUM = re.compile(r"(?:S\s?)?(\d+)", re.IGNORECASE)
_RANGE = re.compile(r"\s*(?:to|through|–|-|至)\s*$", re.IGNORECASE)
GENERIC = {
    SUPPLEMENT_PART: re.compile(
        r"supplementa(?:ry|l)\s+(?:materials?|information|data|text|methods|figures?|tables?|files?|notes?)|"
        r"supporting\s+information|supplementa(?:ry|l)\s+online|补充材料|补充信息|支持信息|附加材料", re.IGNORECASE),
    APPENDIX_PART: re.compile(r"\bappendi(?:x|ces)\b|附录", re.IGNORECASE),
}
KIND_LABEL = (("fig", "Fig."), ("附图", "Fig."), ("补充图", "Fig."), ("table", "Table"), ("附表", "Table"),
              ("补充表", "Table"), ("movie", "Movie"), ("video", "Video"), ("data", "Data"), ("note", "Note"),
              ("method", "Methods"), ("text", "Text"), ("file", "File"))


def _label(kind: str) -> str:
    k = kind.casefold()
    return next((label for prefix, label in KIND_LABEL if k.startswith(prefix)), kind)


def cited_items(text: str) -> list[str]:
    """Supplementary items a text cites, normalised to ``Fig. S2`` / ``Table S1``; ranges are expanded."""
    out: list[str] = []
    for m in ITEM_RE.finditer(text or ""):
        label, nums = _label(m.group("kind")), m.group("nums")
        prev = None
        for n in _NUM.finditer(nums):
            value = int(n.group(1))
            if prev is not None and _RANGE.search(nums[:n.start()]) and 0 < value - prev <= 50:
                values = range(prev + 1, value + 1)
            else:
                values = (value,)
            for v in values:
                item = f"{label} S{v}"
                if item not in out:
                    out.append(item)
            prev = value
    return out


def _captioned(doc: ParsedDocument) -> set[str]:
    """Items that have a caption (a line starting with their label) in any supplied page."""
    found: set[str] = set()
    for part in doc.parts():
        for page in part.pages:
            for _, caption in page.captions:
                found.update(cited_items(caption))
    return found


def source_completeness(doc: ParsedDocument, part_codes: dict | None = None) -> dict:
    """-> {"provided": [...], "referenced": {part: {mentions, pages, items}}, "missing": [...],
           "items_not_found": [...], "complete": bool}

    A referenced part counts as missing when no supplement file was supplied and the supplied pages do not
    contain it: for itemised references, none of the cited items has a caption; for generic references
    ("supplementary materials"), there is nothing to find by definition. With a supplement file supplied,
    nothing is reported missing; cited items without a caption are listed as ``items_not_found``."""
    codes = part_codes or {}
    provided = [{"part": d.part, "source_part": codes.get(d.part_kind, d.part_kind), "file_name": d.path.name,
                 "sha256": d.sha256, "page_count": d.page_count} for d in doc.parts()]
    referenced: dict[str, dict] = {}

    def ref(part: str) -> dict:
        return referenced.setdefault(part, {"mentions": 0, "pages": [], "items": []})
    for page in doc.pages:  # references are read from the main text; a supplement citing itself proves nothing
        hits = {SUPPLEMENT_PART: len(ITEM_RE.findall(page.text))}
        for part, rx in GENERIC.items():
            hits[part] = hits.get(part, 0) + len(rx.findall(page.text))
        for part, n in hits.items():
            if n:
                r = ref(part)
                r["mentions"] += n
                r["pages"].append(page.number)
        for item in cited_items(page.text):
            r = ref(SUPPLEMENT_PART)
            if item not in r["items"]:
                r["items"].append(item)
    captioned = _captioned(doc)
    cited = referenced.get(SUPPLEMENT_PART, {}).get("items", [])
    not_found = [i for i in cited if i not in captioned]
    has_supplement = bool(doc.supplements)
    missing = []
    for part, r in referenced.items():
        if has_supplement:
            continue
        if part == SUPPLEMENT_PART and r["items"] and not not_found:
            continue  # every cited item is in the supplied pages: the supplement is part of this file
        missing.append(part)
    for r in referenced.values():
        r["items"].sort(key=_item_key)
        if not r["items"]:
            del r["items"]
    return {"provided": provided, "referenced": referenced, "missing": sorted(missing),
            "items_not_found": sorted(not_found, key=_item_key), "complete": not missing}


def _item_key(item: str) -> tuple:
    label, _, num = item.rpartition(" S")
    return (label, int(num) if num.isdigit() else 0)


def unavailable_items(quote: str, completeness: dict) -> list[str]:
    """Items cited by ``quote`` that belong to a missing part (empty when the source is complete)."""
    if SUPPLEMENT_PART not in completeness.get("missing", []):
        return []
    not_found = set(completeness.get("items_not_found") or [])
    return [i for i in cited_items(quote) if i in not_found]


__all__ = ["MAIN_PART", "SUPPLEMENT_PART", "APPENDIX_PART", "cited_items", "source_completeness",
           "unavailable_items"]
