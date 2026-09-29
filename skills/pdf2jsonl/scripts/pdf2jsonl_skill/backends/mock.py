"""Deterministic rule-based backend (extraction_method = rule).

It exists to exercise the pipeline end-to-end without a model. It only fills fields bound to *roles* in the
resolved profile, so it follows contract changes like any other backend and contains no field paths.
Its output is deliberately conservative: verbatim sentences, literal tokens, no interpretation.
"""
from __future__ import annotations

import re

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+[^\s\"<>.,;)\]])")
YEAR_RE = re.compile(r"(?:Published|Accepted|Received|©|\(c\)|发表|出版)[^\n]{0,40}?\b((?:19|20)\d{2})\b", re.I)
QTL_RE = re.compile(r"\bq[A-Z][A-Za-z]{0,6}\d{1,2}(?:\.\d{1,2})?\b")
SOFTWARE_RE = re.compile(r"\b([A-Z][A-Za-z0-9+_-]{1,30})\s+(?:software\s+)?(?:version|ver\.|v)\s?(\d+(?:\.\d+){1,3})\b")
CLAIM_CUES = re.compile(
    r"\b(significant(?:ly)?|associated with|identified|revealed|increased|decreased|reduced|enhanced|"
    r"explained|co-?localized|controls?|regulates?)\b|显著|相关|鉴定|定位|提高|降低", re.I)
CLAIM_SECTIONS = ("abstract", "summary", "results", "discussion", "conclusion", "摘要", "结果", "讨论", "结论")
# A period/?/! ends a sentence only when followed by whitespace or the end (keeps "qPH7.1", "23.5%", "v4.2").
SENT_RE = re.compile(r"(?:[^.!?。！？]|[.!?](?=\S))+(?:[.!?]+(?=\s|$)|[。！？]+|$)")


def _mentions(text: str, alias: str) -> bool:
    a = alias.casefold()
    if a.isascii():
        return re.search(rf"\b{re.escape(a)}\b", text) is not None
    return a in text  # CJK has no word boundaries


def _roles(profile: dict, family: str) -> dict:
    return (profile.get("roles") or {}).get(family) or {}


def _blocks(page):
    """Split a page into text blocks at blank lines, section headings and table/figure captions."""
    heading_offsets = {off for off, _ in page.headings}
    caption_offsets = {off for off, _ in page.captions}
    block, start, offset = [], 0, 0
    for line in page.text.splitlines(keepends=True):
        stripped = line.strip()
        line_start = offset
        offset += len(line)
        is_heading = stripped and any(line_start <= h < offset for h in heading_offsets)
        if not stripped or is_heading or line_start in caption_offsets:
            if block:
                yield start, "".join(block)
            block = [] if (not stripped or is_heading) else [line]
            start = line_start if block else offset
            continue
        if not block:
            start = line_start
        block.append(line)
    if block:
        yield start, "".join(block)


def _sentences(page):
    for bstart, text in _blocks(page):
        for m in SENT_RE.finditer(text):
            s = m.group(0)
            stripped = s.strip()
            if len(stripped) >= 25:
                yield bstart + m.start() + s.index(stripped[0]), " ".join(stripped.split())


def _section(page, offset: int, prev: str | None) -> str | None:
    before = [h for off, h in page.headings if off <= offset]
    return before[-1] if before else prev


def extract(doc, profile: dict, rc, options: dict) -> dict:
    sem, prov = _roles(profile, "semantic"), _roles(profile, "provenance")
    document: dict = {}
    first = doc.page(1)
    if first and prov.get("title"):
        title = next((ln.strip() for ln in first.text.splitlines() if ln.strip()), None)
        if title:
            document[prov["title"]] = title
    head = "\n".join(p.text for p in doc.pages[:2])
    if sem.get("doi") and (m := DOI_RE.search(head)):
        document[sem["doi"]] = m.group(1)
    if sem.get("year") and (m := YEAR_RE.search(head)):
        document[sem["year"]] = int(m.group(1))
    crop_path = sem.get("crop")
    crop_field = next((f for f in profile["fields"] if f["path"] == crop_path), None)
    if crop_field and crop_field.get("vocabulary"):
        # Only explicit aliases (surface forms) are matched; codes and umbrella labels such as "other" are not.
        voc = profile["vocabularies"][crop_field["vocabulary"]]
        text = doc.full_text.casefold()
        hits = [v["code"] for v in voc["values"] if any(_mentions(text, a) for a in v.get("aliases") or [])]
        if len(hits) == 1:  # only when unambiguous
            document[crop_path] = hits[0]

    kinds = set(profile.get("model_record_kinds") or [])
    candidates = []
    section = None
    for page in doc.pages:
        for off, sent in _sentences(page):
            section = _section(page, off, section)
            sec_key = (section or "").casefold()
            ev = {"page": page.number, "quote": sent}
            if section:
                ev["section"] = section
            sw = SOFTWARE_RE.search(sent)
            if sw and "method" in kinds and sem.get("software_name"):
                fields = {sem["software_name"]: sw.group(1)}
                if sem.get("software_version"):
                    fields[sem["software_version"]] = sw.group(2)
                candidates.append({"record_kind": "method", "fields": fields, "evidence": ev})
                continue
            if "claim" in kinds and sem.get("statement") and any(sec_key.startswith(s) for s in CLAIM_SECTIONS) \
                    and CLAIM_CUES.search(sent):
                fields = {sem["statement"]: sent}
                qtls = sorted(set(QTL_RE.findall(sent)))
                if qtls and sem.get("qtl_mention"):
                    fields[sem["qtl_mention"]] = qtls
                candidates.append({"record_kind": "claim", "fields": fields, "evidence": ev})
    return {"extraction": {"method": "rule", "backend": "mock"}, "document": document, "candidates": candidates}


extract.extraction_method = "rule"
