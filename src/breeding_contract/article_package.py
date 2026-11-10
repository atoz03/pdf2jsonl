"""Article package: the acceptance checklist of one paper as one data unit.

A paper is more than its main PDF: figures, tables, supplements, and the data/code and licence statements are
part of the same source.  This module derives a deterministic package view from files, extracted text and
records.  It does not extract new knowledge and it never turns "not detected" into "does not exist": the status
distinguishes a cited item that was not supplied from a caption the text layer did not contain.
"""
from __future__ import annotations

import re
from typing import Any

from .util import get_path

PACKAGE_FORMAT = 1
CAPTION_RE = re.compile(r"(?m)^\s*(Fig(?:ure)?\.?|Table)\s+(S\s?\d+[A-Za-z]?|\d+[A-Za-z]?)\b", re.IGNORECASE)
INLINE_RE = re.compile(r"\b(Fig(?:ure)?\.?|Table)\s+(S\s?\d+[A-Za-z]?|\d+[A-Za-z]?)\b", re.IGNORECASE)
AVAILABILITY_RE = re.compile(
    r"(?im)^\s*(?:\d+(?:\.\d+)*\.?\s*)?(data|code|data and code|availability of data|availability of code)"
    r"\s+(?:and\s+code\s+)?availability\b|^\s*(data|code)\s+availability\s*:", re.IGNORECASE)
LICENSE_RE = re.compile(r"(?im)^\s*(?:licen[cs]e|版权|许可)\b")


def _label(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip().rstrip(".:")
    m = re.match(r"(Fig(?:ure)?\.?|Table)\s*(S?\s?\d+[A-Za-z]?)", text, re.IGNORECASE)
    if not m:
        return None
    prefix = "Fig." if m.group(1).lower().startswith("fig") else "Table"
    number = re.sub(r"\s+", "", m.group(2)).upper()
    return f"{prefix} {number}"


def _is_supplement(label: str) -> bool:
    return bool(re.match(r"(?:Fig\.|Table)\s+S\d", label, re.IGNORECASE))


def _items(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _caption_labels(pages: list[dict] | None) -> list[str]:
    out: list[str] = []
    for page in pages or []:
        for m in CAPTION_RE.finditer(str((page or {}).get("text") or "")):
            label = _label(f"{m.group(1)} {m.group(2)}")
            if label and label not in out:
                out.append(label)
    return out


def cited_labels(records: list[dict]) -> list[str]:
    """Labels the records cite, from the dedicated fields and from their verbatim quotes."""
    out: list[str] = []
    for record in records:
        for value in _items(get_path(record, "transform.cited_source_items", None)):
            label = _label(str(value))
            if label and label not in out:
                out.append(label)
        label = _label(get_path(record, "common.source_table_figure", None))
        if label and label not in out:
            out.append(label)
        quote = str(get_path(record, "common.source_quote", "") or "")
        for m in INLINE_RE.finditer(quote):
            label = _label(f"{m.group(1)} {m.group(2)}")
            if label and label not in out:
                out.append(label)
    return out


def _part_pages(part: dict) -> list[dict]:
    pages = part.get("pages") or []
    return [p for p in pages if isinstance(p, dict)]


def build_package(records: list[dict] | None, *, input: dict | None = None,
                  source_parts: dict | None = None, pages: list[dict] | None = None,
                  supplements: list[dict] | None = None, source_id: str | None = None,
                  title: str | None = None, doi: str | None = None, year: int | None = None) -> dict:
    """The package view of one run.  ``pages`` are the main-text pages; ``supplements`` carry their own."""
    records = records or []
    input = input or {}
    source_parts = source_parts or {}
    supplements = supplements or []
    main_pages = _part_pages({"pages": pages or []})
    main_text = "\n".join(str(p.get("text") or "") for p in main_pages)
    supplement_pages = [(part.get("part") or "supplement", _part_pages(part)) for part in supplements]
    supplement_text = "\n".join(str(p.get("text") or "") for _, ps in supplement_pages for p in ps)

    detected_main = _caption_labels(main_pages)
    detected_supp = _caption_labels([p for _, ps in supplement_pages for p in ps])
    cited = cited_labels(records)
    cited_main = [x for x in cited if not _is_supplement(x)]
    cited_supp = [x for x in cited if _is_supplement(x)]
    missing_supp = [x for x in cited_supp if x not in detected_supp]
    cited_not_detected = [x for x in cited_main if x not in detected_main]

    supplied_parts = {str(p.get("part")) for p in supplements if p.get("part")}
    part_states = {str(p.get("part")): p for p in (source_parts.get("parts") or []) if isinstance(p, dict)}
    missing_parts = [str(p.get("part")) for p in (source_parts.get("missing") or []) if isinstance(p, dict)]
    no_text = [str(p.get("part")) for p in (source_parts.get("parts") or [])
               if isinstance(p, dict) and p.get("supplied") and not p.get("text_pages")]

    data_code_present = bool(AVAILABILITY_RE.search(main_text) or AVAILABILITY_RE.search(supplement_text))
    data_assets = []
    for record in records:
        data_assets.extend(_items(get_path(record, "skills.reproducibility_assets", None)))
        value = get_path(record, "common.data_access_uri", None)
        if value:
            data_assets.append(value)
    license_values = []
    for record in records:
        value = get_path(record, "common.license_id", None)
        if value and value not in license_values:
            license_values.append(value)

    text_pages = sum(1 for p in main_pages if str(p.get("text") or "").strip())
    if not input:
        status = "not_submitted"
    elif not main_pages or not main_text.strip():
        status = "unverified"
    elif missing_supp or missing_parts or no_text:
        status = "partial"
    else:
        status = "complete"

    missing = []
    if missing_parts:
        missing.extend(f"未提供 {part}" for part in missing_parts)
    if missing_supp:
        missing.extend(f"Supplement 引用但未在已提供文件中找到：{label}" for label in missing_supp)
    if no_text:
        missing.extend(f"{part} 已提供但没有文本层" for part in no_text)

    notes = []
    if cited_not_detected:
        notes.append("正文引用但文本层未检测到图注/表注（不作为“不存在”）：" + "、".join(cited_not_detected))
    if not data_code_present and not data_assets:
        notes.append("未检测到数据/代码可用性声明（建议项，不影响完整状态）")
    if not license_values:
        notes.append("未检测到引用/许可字段（建议项，不影响完整状态）")

    return {
        "package_format": PACKAGE_FORMAT,
        "source_id": source_id,
        "paper": {"title": title, "doi": doi, "year": year},
        "main_text": {
            "present": bool(input), "file_name": input.get("file_name"), "sha256": input.get("sha256"),
            "page_count": input.get("page_count") or len(main_pages), "text_pages": text_pages,
        },
        "figures": {
            "detected": [x for x in detected_main if x.startswith("Fig.")],
            "cited": [x for x in cited_main if x.startswith("Fig.")],
            "supplement_detected": [x for x in detected_supp if x.startswith("Fig.")],
            "supplement_cited": [x for x in cited_supp if x.startswith("Fig.")],
            "cited_not_detected": [x for x in cited_not_detected if x.startswith("Fig.")],
        },
        "tables": {
            "detected": [x for x in detected_main if x.startswith("Table")],
            "cited": [x for x in cited_main if x.startswith("Table")],
            "supplement_detected": [x for x in detected_supp if x.startswith("Table")],
            "supplement_cited": [x for x in cited_supp if x.startswith("Table")],
            "cited_not_detected": [x for x in cited_not_detected if x.startswith("Table")],
        },
        "supplement": {
            "parts": [{"part": part.get("part"), "file_name": part.get("file_name") or part.get("filename"),
                       "sha256": part.get("sha256"), "page_count": part.get("page_count"),
                       "text_pages": sum(1 for p in _part_pages(part) if str(p.get("text") or "").strip())}
                      for part in supplements],
            "supplied_parts": sorted(supplied_parts),
            "cited_items": cited_supp,
            "detected_items": detected_supp,
            "missing_items": missing_supp,
        },
        "data_code": {"status": "present" if (data_code_present or data_assets) else "not_detected",
                      "assets": data_assets, "statement_detected": data_code_present},
        "license": {"status": "present" if license_values else "not_detected", "values": license_values},
        "status": status,
        "missing": missing,
        "notes": notes,
        "part_states": part_states,
    }
