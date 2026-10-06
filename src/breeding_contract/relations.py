"""Relation and entity anchors: the hooks that let records become graph edges, corpora and QA pairs without
re-parsing the source text (AMB-038).

A record that states a relation carries one statement, subject – predicate – object, in the ``relation`` fields.
Every entity mention of the record is a marker in the ``array_entity_link`` field, with its character offsets in
the evidence quote and, for the two ends of the statement, its role. Everything here is deterministic: offsets
come from a literal search, entity types from the field that holds the mention, and the predicate code from
the cue phrases of the vocabulary bound to the code field. No match means no value; nothing is guessed.

Shared by the extraction pipeline (fill rule ``relation_anchors``), the validator (rule kind
``offsets_match_text``) and the derived views, so all three agree on what an anchor is.
"""
from __future__ import annotations

import re

from .ids import normalize_text
from .util import get_path

ENTITY_SUFFIX = re.compile(r"(_names|_name|_ids|_id|_accessions)$")
RELATION_ENDS = ("subject", "object")
_ASCII_WORD = "A-Za-z0-9"


def entity_type(path: str) -> str:
    """Entity type named by the field (common.gene_names -> gene, common.crop_taxon_id -> crop_taxon)."""
    return ENTITY_SUFFIX.sub("", path.split(".", 1)[1]) or path.split(".", 1)[1]


def find_span(text, mention) -> tuple[int, int] | None:
    """Offsets (end exclusive) of the first literal occurrence of ``mention`` in ``text``.

    Tolerant only to letter case and to the length of whitespace runs. An ASCII word edge must not sit inside a
    longer word, so the trait abbreviation PH is not found inside qPH7.1.
    """
    if not isinstance(text, str) or not isinstance(mention, str):
        return None
    tokens = mention.split()
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(t) for t in tokens)
    if re.match(f"[{_ASCII_WORD}]", tokens[0]):
        pattern = f"(?<![{_ASCII_WORD}])" + pattern
    if re.search(f"[{_ASCII_WORD}]$", tokens[-1]):
        pattern += f"(?![{_ASCII_WORD}])"
    m = re.search(pattern, text, re.IGNORECASE)
    return (m.start(), m.end()) if m else None


def span_matches(text, mention, start, end) -> bool:
    """Whether ``text[start:end]`` is ``mention`` up to case, typography and inner whitespace."""
    if not isinstance(text, str) or not isinstance(mention, str):
        return False
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, end)) or not 0 <= start < end <= len(text):
        return False
    span = text[start:end]
    return span == span.strip() and normalize_text(span) == normalize_text(mention)


def mention_fields(contract: dict) -> list[dict]:
    """Fields that hold verbatim entity mentions. A field bound to a vocabulary holds a code, not a mention."""
    return [f for f in contract["fields"] if f.get("key_role") == "entity_mention" and not f.get("vocabulary")
            and f["type"] in ("string", "array_string")]


def entity_markers(record: dict, contract: dict, quote, ends: dict[str, tuple[str, object]] | None = None) -> list[dict]:
    """One marker per entity mention of the record, anchored in ``quote`` where it occurs literally.

    ``ends`` maps a statement end (``subject`` / ``object``) to ``(field path, mention)``. The marker whose
    mention equals an end gets its ``relation_role``; an end that no entity field lists gets a marker of its
    own, pointing at the relation field, without an entity type.
    """
    wanted = {role: (path, normalize_text(m)) for role, (path, m) in (ends or {}).items()
              if role in RELATION_ENDS and isinstance(m, str) and m.strip()}
    markers: list[dict] = []
    seen: set[tuple[str, str]] = set()
    matched: set[str] = set()

    def add(path: str, mention: str, etype: str | None, role: str | None) -> None:
        item = {"mention": mention, "source_field": path}
        if etype:
            item["entity_type"] = etype
        span = find_span(quote, mention)
        if span:
            item["start"], item["end"] = span
        if role:
            item["relation_role"] = role
        markers.append(item)

    for f in mention_fields(contract):
        value = get_path(record, f["path"], None)
        for x in (value if isinstance(value, list) else [value]):
            if not isinstance(x, str) or not x.strip():
                continue
            key = normalize_text(x)
            if (f["path"], key) in seen:
                continue
            seen.add((f["path"], key))
            role = next((r for r, (_, k) in wanted.items() if k == key), None)
            if role:
                matched.add(role)
            add(f["path"], x, entity_type(f["path"]), role)
    for role, (path, _) in wanted.items():
        if role not in matched:
            add(path, ends[role][1], None, role)
    return markers


def end_types(markers: list[dict], role: str) -> list[str]:
    """Entity types of the markers playing ``role`` (empty when the end is not a typed entity mention)."""
    return sorted({m["entity_type"] for m in markers or [] if isinstance(m, dict)
                   and m.get("relation_role") == role and m.get("entity_type")})


def _cue_in(cue: str, text: str) -> bool:
    cue = normalize_text(cue)
    if cue.isascii():
        return re.search(f"(?<![a-z0-9]){re.escape(cue)}(?![a-z0-9])", text) is not None
    return cue in text


def predicate_code(vocabulary: dict, mention, subject_types: list[str], object_types: list[str]) -> str | None:
    """The code of ``vocabulary`` identified by a verbatim predicate, or None.

    A code matches when one of its ``cues`` occurs in the mention and its ``subject_types`` / ``object_types``
    (when declared) include a type of the corresponding end. The longest cue wins; a tie between codes, or no
    match, gives None: the verbatim predicate stays the only statement of the relation.
    """
    if not isinstance(mention, str) or not mention.strip():
        return None
    text = normalize_text(mention)
    hits: dict[str, int] = {}
    for v in vocabulary.get("values") or []:
        cues = v.get("cues")
        if not cues:
            continue
        if v.get("subject_types") and not set(v["subject_types"]) & set(subject_types):
            continue
        if v.get("object_types") and not set(v["object_types"]) & set(object_types):
            continue
        best = max((len(c) for c in cues if _cue_in(c, text)), default=0)
        if best:
            hits[v["code"]] = best
    if not hits:
        return None
    top = max(hits.values())
    winners = [code for code, n in hits.items() if n == top]
    return winners[0] if len(winners) == 1 else None
