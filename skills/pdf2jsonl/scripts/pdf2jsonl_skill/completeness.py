"""Source completeness: which parts of a paper the text refers to, and which of them were supplied (AMB-041, AMB-044).

A paper is often more than one file. The library may hold only the main text while the text cites
"fig. S2" or says that materials and methods are in the supplementary materials. The pipeline cannot extract
what it was not given, but it can say so: this module scans the supplied text for references to supplementary
items and reports the parts that are referenced but neither supplied as a file nor present in the supplied
pages. Detection is literal (labels and stock phrases); it never guesses what a missing part contains.

Since 3.7.0 every part also carries a *state*, because "we do not have it", "we have it and nobody cites it"
and "we have it but there is no text layer to read" need different actions from the person who prepares the
run. Item labels ("Fig. S2") are one pool for all further files: a quoted item cannot be attributed to the
supplement or to the appendix, so an item is only reported when no further file was supplied, or when a
supplied file has no readable text (AMB-044).
"""
from __future__ import annotations

import re

from .pdf_parse import APPENDIX_PART, MAIN_PART, PART_KINDS, SUPPLEMENT_PART, ParsedDocument

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

# States of one part (AMB-044). The first three are about a supplied file, the last three about a referenced part.
STATE_SUPPLIED_PARSED = "supplied_parsed"
STATE_SUPPLIED_NO_TEXT = "supplied_no_text"
STATE_SUPPLIED_UNREFERENCED = "supplied_not_referenced"
STATE_SUPPLIED_ITEMS_NOT_FOUND = "supplied_items_not_found"
STATE_REFERENCED_MISSING = "referenced_not_supplied"
STATE_IN_MAIN_PAGES = "in_main_pages"
STATE_NOT_REFERENCED = "not_referenced"

STATE_LABEL_ZH = {
    STATE_SUPPLIED_PARSED: "已提供并解析",
    STATE_SUPPLIED_NO_TEXT: "已提供但没有文本层",
    STATE_SUPPLIED_UNREFERENCED: "已提供但正文未引用",
    STATE_SUPPLIED_ITEMS_NOT_FOUND: "已提供但引用项未在其中定位",
    STATE_REFERENCED_MISSING: "正文引用但未提供",
    STATE_IN_MAIN_PAGES: "引用项已在提供的页中（与正文同一文件）",
    STATE_NOT_REFERENCED: "未引用",
}

PART_NOT_PARSED = "SOURCE_PART_NOT_PARSED"
PART_UNREFERENCED = "SOURCE_PART_UNREFERENCED"
PART_ITEM_NOT_FOUND = "SOURCE_PART_ITEM_NOT_FOUND"


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


def _text_pages(docs: list[ParsedDocument]) -> int:
    return sum(1 for d in docs for p in d.pages if p.text and p.text.strip())


def _text_chars(docs: list[ParsedDocument]) -> int:
    return sum(len(p.text.strip()) for d in docs for p in d.pages)


def source_completeness(doc: ParsedDocument, part_codes: dict | None = None) -> dict:
    """-> {"provided", "referenced", "parts", "missing", "items_not_found", "warnings", "complete"}

    ``parts`` carries one entry per part kind the text references or the run supplies, with its ``state`` (see
    the ``STATE_*`` constants), its files, page and text counts, and what the main text cites. ``missing`` lists
    the part kinds that are referenced and not supplied; ``items_not_found`` the cited items without a caption in
    any supplied page. ``warnings`` holds run-level notices (a supplied part without text, a supplied part the
    text never cites) — they are not per-record problems. ``complete`` is false when a part is missing."""
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
    supplied: dict[str, list[ParsedDocument]] = {}
    for d in doc.supplements:
        supplied.setdefault(d.part_kind, []).append(d)
    parts: list[dict] = []
    missing: list[str] = []
    warnings: list[dict] = []
    for kind in PART_KINDS:
        docs = supplied.get(kind, [])
        r = referenced.get(kind) or {"mentions": 0, "pages": [], "items": []}
        entry = {"part": kind, "source_part": codes.get(kind, kind), "supplied": bool(docs),
                 "files": [d.path.name for d in docs], "page_count": sum(d.page_count for d in docs),
                 "text_pages": _text_pages(docs), "text_chars": _text_chars(docs)}
        if docs:
            if entry["text_pages"] == 0:
                entry["state"] = STATE_SUPPLIED_NO_TEXT
                warnings.append({"code": PART_NOT_PARSED, "part": entry["source_part"],
                                 "message": f"{entry['source_part']} 已提供但没有可解析的文本："
                                            f"{', '.join(entry['files'])}"})
            elif not r["mentions"]:
                entry["state"] = STATE_SUPPLIED_UNREFERENCED
                warnings.append({"code": PART_UNREFERENCED, "part": entry["source_part"],
                                 "message": f"{entry['source_part']} 已提供，但正文没有引用它"})
            elif kind == SUPPLEMENT_PART and not_found:
                # The file is here and readable, but an item the text cites is not in it: a different problem
                # from "not supplied" and from "no text layer" (AMB-044).
                entry["state"] = STATE_SUPPLIED_ITEMS_NOT_FOUND
                warnings.append({"code": PART_ITEM_NOT_FOUND, "part": entry["source_part"],
                                 "items": sorted(not_found, key=_item_key),
                                 "message": f"{entry['source_part']} 已提供，但正文引用的 "
                                            f"{', '.join(sorted(not_found, key=_item_key))} 没有在其中定位到"})
            else:
                entry["state"] = STATE_SUPPLIED_PARSED
        elif kind == SUPPLEMENT_PART and r.get("items") and not not_found:
            entry["state"] = STATE_IN_MAIN_PAGES  # every cited item is in the supplied pages: same file
        elif r["mentions"]:
            entry["state"] = STATE_REFERENCED_MISSING
            missing.append(kind)
        else:
            entry["state"] = STATE_NOT_REFERENCED
        if r["mentions"]:
            entry["referenced"] = {k: r[k] for k in ("mentions", "pages", "items") if r.get(k)}
        if kind == SUPPLEMENT_PART and not_found:
            entry["items_not_found"] = sorted(not_found, key=_item_key)
        entry["state_label_zh"] = STATE_LABEL_ZH[entry["state"]]
        parts.append(entry)
    for r in referenced.values():
        r["items"].sort(key=_item_key)
        if not r["items"]:
            del r["items"]
    return {"provided": provided, "referenced": referenced, "parts": parts, "missing": sorted(missing),
            "items_not_found": sorted(not_found, key=_item_key), "warnings": warnings, "complete": not missing}


def _item_key(item: str) -> tuple:
    label, _, num = item.rpartition(" S")
    return (label, int(num) if num.isdigit() else 0)


def _unparsed_parts(completeness: dict) -> list[str]:
    return [p["part"] for p in completeness.get("parts") or [] if p.get("state") == STATE_SUPPLIED_NO_TEXT]


def unavailable_items(quote: str, completeness: dict) -> list[str]:
    """Items cited by ``quote`` that cannot be checked: the part that could hold them is missing, or a supplied
    part has no text layer to look in (AMB-041, AMB-044). Empty when every supplied part is readable."""
    missing = set(completeness.get("missing") or [])
    if not (missing & set(PART_KINDS)) and not _unparsed_parts(completeness):
        return []
    not_found = set(completeness.get("items_not_found") or [])
    return [i for i in cited_items(quote) if i in not_found]


def unavailable_reason(completeness: dict) -> str:
    """The warning code a record gets for an uncheckable citation: a supplied part without text is a different
    problem from a part that was never supplied (supply a text layer vs supply the file)."""
    return PART_NOT_PARSED if _unparsed_parts(completeness) else "SOURCE_PART_UNAVAILABLE"


__all__ = ["MAIN_PART", "SUPPLEMENT_PART", "APPENDIX_PART", "PART_KINDS", "cited_items", "source_completeness",
           "unavailable_items", "unavailable_reason", "STATE_LABEL_ZH", "PART_NOT_PARSED", "PART_UNREFERENCED",
           "PART_ITEM_NOT_FOUND"]
