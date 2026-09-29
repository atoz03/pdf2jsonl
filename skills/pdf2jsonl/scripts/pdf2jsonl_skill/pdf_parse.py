"""Parse an input document into physical pages with light layout signals (section headings, captions).

Supported inputs
  *.pdf          text layer via pypdf (optional dependency: pip install pypdf)
  *.txt          pages separated by form feed (\\f)
  *.pages.jsonl  pre-parsed pages, one JSON object per line: {"page": 1, "text": "..."}
                 (use this to plug in MinerU / GROBID / OCR output)
Page numbers are physical, starting at 1 (contract rule for source_page).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .contract_link import sha256_file

HEADINGS = [
    "abstract", "summary", "introduction", "background", "materials and methods", "material and methods",
    "methods", "methodology", "experimental procedures", "results", "results and discussion", "discussion",
    "conclusion", "conclusions", "acknowledgements", "acknowledgments", "references", "supplementary material",
    "supplementary information", "data availability", "author contributions",
    "摘要", "引言", "前言", "材料与方法", "材料和方法", "结果", "结果与分析", "结果与讨论", "讨论", "结论", "参考文献", "致谢",
]
_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+|[IVX]+\.\s+)?(" + "|".join(re.escape(h) for h in HEADINGS) + r")\s*:?\s*$",
    re.IGNORECASE)
_CAPTION_RE = re.compile(r"^\s*((?:Table|Tab\.|Figure|Fig\.?|表|图)\s*S?\d+[A-Za-z]?)", re.IGNORECASE)


@dataclass
class Page:
    number: int
    text: str
    headings: list[tuple[int, str]] = field(default_factory=list)   # (char offset, heading text)
    captions: list[tuple[int, str]] = field(default_factory=list)   # (char offset, label e.g. "Table 2")


@dataclass
class ParsedDocument:
    path: Path
    sha256: str
    size_bytes: int
    media_type: str
    pages: list[Page]
    parser: dict

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def page(self, number: int) -> Page | None:
        return self.pages[number - 1] if 1 <= number <= len(self.pages) else None

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)


def _annotate(page: Page) -> Page:
    offset = 0
    for line in page.text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            m = _HEADING_RE.match(stripped)
            if m and len(stripped) <= 60:
                page.headings.append((offset + line.index(stripped[0]), stripped.rstrip(":").strip()))
            c = _CAPTION_RE.match(stripped)
            if c:
                page.captions.append((offset, re.sub(r"\s+", " ", c.group(1))))
        offset += len(line)
    return page


def _parse_pdf(path: Path) -> tuple[list[str], dict]:
    try:
        import pypdf
    except ImportError as e:  # pragma: no cover - environment dependent
        raise RuntimeError("PDF input needs pypdf (pip install 'breeding-data-contract[pdf]'), "
                           "or supply a .txt / .pages.jsonl text layer") from e
    reader = pypdf.PdfReader(str(path))
    texts = [(pg.extract_text() or "") for pg in reader.pages]
    return texts, {"name": "pypdf", "version": pypdf.__version__}


def _read_pages(path: Path) -> tuple[list[str], dict, str]:
    name = path.name.lower()
    if name.endswith(".pages.jsonl"):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows.sort(key=lambda r: r["page"])
        if [r["page"] for r in rows] != list(range(1, len(rows) + 1)):
            raise ValueError(f"{path}: pages must be numbered 1..N without gaps")
        texts, parser, media = [r["text"] for r in rows], {"name": "pages.jsonl", "version": "1"}, "application/jsonl"
    elif name.endswith(".txt"):
        texts = path.read_text(encoding="utf-8").split("\f")
        if texts and not texts[-1].strip():
            texts = texts[:-1]
        parser, media = {"name": "text-formfeed", "version": "1"}, "text/plain"
    elif name.endswith(".pdf"):
        texts, parser = _parse_pdf(path)
        media = "application/pdf"
    else:
        raise ValueError(f"unsupported input type: {path.name} (expected .pdf, .txt or .pages.jsonl)")
    return texts, parser, media


def parse_document(path: Path | str, text_layer: Path | str | None = None) -> ParsedDocument:
    """Parse ``path``. With ``text_layer`` (a .txt / .pages.jsonl produced by OCR, MinerU, GROBID ...) the pages
    come from the text layer while the document identity (hash, size, media type) stays that of ``path``."""
    path = Path(path)
    texts, parser, media = _read_pages(path if text_layer is None else Path(text_layer))
    if text_layer is not None:
        parser = {**parser, "text_layer": Path(text_layer).name,
                  "text_layer_sha256": sha256_file(Path(text_layer))}
        media = "application/pdf" if path.name.lower().endswith(".pdf") else media
    pages = [_annotate(Page(number=i + 1, text=t)) for i, t in enumerate(texts)]
    return ParsedDocument(path=path, sha256=sha256_file(path), size_bytes=path.stat().st_size, media_type=media,
                          pages=pages, parser=parser)
