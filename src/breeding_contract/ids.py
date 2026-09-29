"""Repository conventions for stable record IDs, locators and spans (AMB-011).

These are contract-level conventions (not PDF-specific) so every ingestion path produces the same IDs.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

_WS = re.compile(r"\s+")
_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
_TRANSLATE = str.maketrans({
    "­": "", "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"', "ﬁ": "fi", "ﬂ": "fl",
})


def normalize_text(text: str) -> str:
    """Whitespace/hyphenation/typography-insensitive form used for quote matching and IDs."""
    s = unicodedata.normalize("NFKC", text)
    s = _HYPHEN_BREAK.sub(r"\1\2", s)
    s = s.translate(_TRANSLATE)
    s = _WS.sub(" ", s).strip()
    return s.casefold()


def stable_record_id(source_id: str, record_kind: str, anchor: str, quote: str | None, ordinal: int = 0) -> str:
    """rec_ + 32 hex chars of sha256 over the evidence anchor (content-addressed, parser-independent)."""
    payload = "\x1f".join([source_id, record_kind, anchor, normalize_text(quote or ""), str(ordinal)])
    return "rec_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _esc(value: str) -> str:
    return str(value).replace("%", "%25").replace(";", "%3B").replace("=", "%3D")


def _unesc(value: str) -> str:
    return value.replace("%3D", "=").replace("%3B", ";").replace("%25", "%")


LOCATOR_KEYS = ("page", "section", "table", "row", "col")


def build_locator(page=None, section=None, table=None, row=None, col=None) -> str:
    parts = []
    for key, value in zip(LOCATOR_KEYS, (page, section, table, row, col)):
        if value is not None and value != "":
            parts.append(f"{key}={_esc(value)}")
    return ";".join(parts)


def parse_locator(locator: str) -> dict:
    out = {}
    for part in locator.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = _unesc(v)
    return out


def build_span(page: int, start: int, end: int) -> str:
    return f"page={page};char={start}-{end}"
