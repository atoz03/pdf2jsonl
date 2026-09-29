"""Evidence verification: every model-produced record must be anchored to a verbatim quote in the source.

Matching is tolerant only to layout artefacts (whitespace, line-break hyphenation, typographic quotes/dashes,
ligatures, case) — never to wording. A quote that cannot be found is rejected, not repaired.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .pdf_parse import ParsedDocument

_TRANSLATE = str.maketrans({
    "­": "", "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
})


def normalize_with_map(raw: str) -> tuple[str, list[int]]:
    """Normalize text and return, for every normalized char, the index of its source char in ``raw``."""
    chars: list[tuple[str, int]] = []
    for i, ch in enumerate(raw):
        for c in unicodedata.normalize("NFKC", ch).translate(_TRANSLATE).casefold():
            chars.append((c, i))
    # drop line-break hyphenation: <alnum>-<ws incl. newline><alnum>
    kept: list[tuple[str, int]] = []
    j = 0
    n = len(chars)
    while j < n:
        c, i = chars[j]
        if c == "-" and kept and kept[-1][0].isalnum():
            k = j + 1
            saw_newline = False
            while k < n and chars[k][0].isspace():
                saw_newline |= chars[k][0] == "\n"
                k += 1
            if saw_newline and k < n and chars[k][0].isalnum():
                j = k
                continue
        kept.append((c, i))
        j += 1
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    for c, i in kept:
        if c.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space = True
        else:
            out.append(c)
            idx.append(i)
            prev_space = False
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def normalize(text: str) -> str:
    return normalize_with_map(text)[0]


@dataclass
class Match:
    page: int
    start: int          # raw char offset in the page text
    end: int            # raw char offset (exclusive)
    stated_page: int | None

    @property
    def page_corrected(self) -> bool:
        return self.stated_page is not None and self.stated_page != self.page


class EvidenceIndex:
    def __init__(self, doc: ParsedDocument):
        self.doc = doc
        self._norm = [normalize_with_map(p.text) for p in doc.pages]
        self._full = " ".join(n for n, _ in self._norm)

    def locate(self, quote: str, page_hint: int | None, radius: int = 1) -> Match | None:
        q = normalize(quote or "")
        if len(q) < 3:
            return None
        order: list[int] = []
        if page_hint and 1 <= page_hint <= self.doc.page_count:
            order.append(page_hint)
            for d in range(1, radius + 1):
                order += [p for p in (page_hint - d, page_hint + d) if 1 <= p <= self.doc.page_count]
        else:
            order = list(range(1, self.doc.page_count + 1))
        for pno in order:
            norm, idx = self._norm[pno - 1]
            pos = norm.find(q)
            if pos >= 0:
                return Match(page=pno, start=idx[pos], end=idx[pos + len(q) - 1] + 1, stated_page=page_hint)
        return None

    def section_at(self, page: int, offset: int) -> str | None:
        """Nearest preceding section heading (may come from an earlier page)."""
        p = self.doc.page(page)
        if p:
            before = [h for off, h in p.headings if off <= offset]
            if before:
                return before[-1]
        for prev in range(page - 1, 0, -1):
            hs = self.doc.page(prev).headings
            if hs:
                return hs[-1][1]
        return None

    def page_mentions(self, page: int, text: str) -> bool:
        p = self.doc.page(page)
        return bool(p) and normalize(text) in self._norm[page - 1][0]

    def value_present(self, value, page: int | None = None) -> bool:
        """Whether a scalar value literally appears in the page (or anywhere, if page is None)."""
        hay = self._norm[page - 1][0] if page else self._full
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            forms = {repr(value), str(value)}
            if isinstance(value, float) and value.is_integer():
                forms.add(str(int(value)))
            return any(re.search(rf"(?<![\d.]){re.escape(f)}{'0*' if '.' in f else ''}(?!\d)", hay)
                       for f in forms)
        if isinstance(value, str):
            return normalize(value) in hay
        return True
