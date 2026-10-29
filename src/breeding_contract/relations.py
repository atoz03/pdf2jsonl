"""Relation and entity anchors: the hooks that let records become graph edges, corpora and QA pairs without
re-parsing the source text (AMB-038).

A record that states a relation carries one statement, subject – predicate – object, in the ``relation`` fields.
Every entity mention of the record is a marker in the ``array_entity_link`` field, with its character offsets in
the evidence quote and, for the two ends of the statement, its role. Everything here is deterministic: offsets
come from a literal search, entity types from the field that holds the mention, and the predicate code from
the cue phrases of the vocabulary bound to the code field. No match means no value; nothing is guessed, and a
negated relation is never given the code of the positive one.

Shared by the extraction pipeline (fill rule ``relation_anchors``), the validator (rule kind
``offsets_match_text``) and the derived views, so all three agree on what an anchor is.
"""
from __future__ import annotations

import re

from .ids import normalize_text
from .util import get_path

ENTITY_SUFFIX = re.compile(r"(_names|_name|_ids|_id|_accessions)$")
RELATION_ENDS = ("subject", "object")
# Words that negate a relation, matched in normalized text. 不同, 不仅, 无论, 非常 and the like do not negate.
NEGATION = re.compile(r"(?<![a-z0-9])(?:not|no|non|none|never|neither|nor|cannot|without|fail(?:s|ed)? to)(?![a-z0-9])"
                      r"|n't|未|没|不(?![同仅但断论])|无(?!论)|非(?!常)")
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
        if role in matched:
            continue
        # The statement end is often a short phrase that contains the entity ("The QTL qDTS1-2",
        # "TaPTR gene") rather than the entity string alone. Type it when every entity mention
        # inside that phrase has the same type. Mixed types stay untyped, so two codes cannot tie.
        end_text = ends[role][1]
        contained = [m for m in markers if m.get("entity_type") and not m.get("relation_role")
                     and find_span(end_text, m["mention"])]
        types = {m["entity_type"] for m in contained}
        if contained and len(types) == 1:
            for m in contained:
                m["relation_role"] = role
            continue
        add(path, end_text, None, role)
    return markers


def end_types(markers: list[dict], role: str) -> list[str]:
    """Entity types of the markers playing ``role`` (empty when the end is not a typed entity mention)."""
    return sorted({m["entity_type"] for m in markers or [] if isinstance(m, dict)
                   and m.get("relation_role") == role and m.get("entity_type")})


def relation_context(text, markers: list[dict]) -> str:
    """The stretch of ``text`` between the two anchored ends of the statement ("" unless both are anchored)."""
    spans: dict[str, tuple[int, int]] = {}
    for m in markers or []:
        if isinstance(m, dict) and m.get("relation_role") in RELATION_ENDS and isinstance(m.get("start"), int) \
                and isinstance(m.get("end"), int):
            spans.setdefault(m["relation_role"], (m["start"], m["end"]))
    if not isinstance(text, str) or len(spans) < 2:
        return ""
    first, second = sorted(spans.values())
    return text[first[1]:second[0]]


def negated(*texts) -> bool:
    """True when one of the verbatim texts contains a negation word ("was not associated with", "不相关")."""
    return any(isinstance(t, str) and NEGATION.search(normalize_text(t)) for t in texts)


# An active cue used passively reads the relation backwards: "plant height was controlled by qPH7.1" has the trait
# as its subject. In English such a participle is followed by "by" (an adverb may sit between); in Chinese 受 or 被
# comes before the verb — not the 受 of 受体 (receptor), nor 被 in 被认为 / 被发现 … (is considered, is found).
BY_AFTER = re.compile(r"\s+(?:[a-z]+ly\s+)?by(?![a-z0-9])")
PASSIVE_ZH = re.compile(r"受(?!体)|被(?!认为|视为|发现|证明|证实|鉴定|报道|用于)")


def _passive_cue(cue: str) -> bool:
    """A cue that is itself passive ("regulated by", "受…调控"): it states the code's own direction."""
    return re.search(r"(?<![a-z0-9])by(?![a-z0-9])", cue) is not None or PASSIVE_ZH.search(cue) is not None


def _ing(token: str) -> str | None:
    """Present participle of a one-word English cue (controls -> controlling, mediates -> mediating)."""
    if not token.isascii() or not token.endswith("s") or token.endswith("ss") or len(token) <= 4:
        return None
    base = token[:-1]
    if base.endswith("e"):
        return base[:-1] + "ing"
    if len(base) >= 2 and base[-1] not in "aeiou" and base[-2] in "aeiou" and base[-1] not in "wxy":
        return base + base[-1] + "ing"
    return base + "ing"


def _cue_forms(cue: str) -> list[str]:
    """Surface forms of a vocabulary cue. Papers write "controlling" and "located within"; the cue list has
    "controls" and "located in". Only the participle and that one location preposition are added."""
    forms = [cue]
    if cue == "located in":
        forms.extend(("located within", "mapped in"))
    if cue == "associated with":
        forms.append("related to")
    if " " not in cue:
        ing = _ing(cue)
        if ing and ing not in forms:
            forms.append(ing)
    return forms


def _cue_in(cue: str, text: str) -> bool:
    """The cue occurs in the (normalized) mention in its own voice: a passive cue anywhere, an active cue at least
    once where it is not used passively."""
    return any(_form_in(form, text, _passive_cue(cue)) for form in _cue_forms(normalize_text(cue)))


def _form_in(form: str, text: str, passive: bool) -> bool:
    pattern = f"(?<![a-z0-9]){re.escape(form)}(?![a-z0-9])" if form.isascii() else re.escape(form)
    hits = list(re.finditer(pattern, text))
    if not hits or passive:
        return bool(hits)
    return any(not BY_AFTER.match(text, m.end()) and not PASSIVE_ZH.search(text, 0, m.start()) for m in hits)


def predicate_match(vocabulary: dict, mention, subject_types: list[str], object_types: list[str],
                    context: str | None = None) -> tuple[str | None, str | None]:
    """-> (code, unresolved reason): the code of ``vocabulary`` identified by a verbatim predicate, or None plus
    why no code was assigned (AMB-043).

    A code matches when one of its ``cues`` occurs in the mention and its ``subject_types`` / ``object_types``
    (when declared) include a type of the corresponding end. The longest cue wins; a tie between codes gives no
    code and the reason ``ambiguous``, no match gives ``no_cue``. A negation — in the mention or in ``context``
    (the quote between the two ends, see ``relation_context``) — gives ``negated``: the codes name positive
    relations, and "was not associated with" must not become one. Polarity is a reviewer's call. A mention that
    is not a string or is blank has no predicate to resolve and returns ``(None, None)``.

    The reason is what ``transform.relation_resolution`` records, so a record says *why* it has no code: a cue
    the vocabulary misses (fix the vocabulary) is not the same problem as two codes a reviewer can separate by
    registering the entity mention (fix the record).

    A declared type list is a filter only over ends that have a type. An end whose mention no entity field
    lists carries no type — the pipeline types a mention by the field that holds it, and a paper states many
    ends only in passing ("a single gene", a trait abbreviation defined in a table). Such an end is not
    evidence against the code: a wrong subject must be excluded because its type is known to differ, not
    because it is unknown. So an untyped end passes the filter, and only a typed end that misses the list
    rejects the code.

    A cue counts only where it is used in its own voice. An active cue used passively ("was controlled by",
    "受…调控") would read the relation backwards, and with an untyped end no type check is left to catch it. A
    passive code carries passive cues only ("regulated by"), so an active "regulates" never matches it.
    """
    if not isinstance(mention, str) or not mention.strip():
        return None, None
    if negated(mention, context):
        return None, "negated"
    text = normalize_text(mention)
    hits: dict[str, int] = {}
    for v in vocabulary.get("values") or []:
        cues = v.get("cues")
        if not cues:
            continue
        subj = set(subject_types)
        # "FLN1.1 controlled the number of flowers": the only causal "controlled" code lists gene as its
        # subject. A QTL is the same kind of locus in these papers, so it satisfies that list. The cue and
        # the trait object still have to match; a passive "was controlled by" does not.
        if v.get("code") == "genotype_controls_trait" and "qtl" in subj:
            subj.add("gene")
        # A GWAS SNP is stored as a marker. "S06_47123508 associated with β-carotene" is the same
        # associational statement as a QTL, and no marker-trait code exists in the vocabulary.
        if v.get("code") == "qtl_associated_with_trait" and "marker" in subj:
            subj.add("qtl")
        if subj and v.get("subject_types") and not set(v["subject_types"]) & subj:
            continue
        if object_types and v.get("object_types") and not set(v["object_types"]) & set(object_types):
            continue
        best = max((len(c) for c in cues if _cue_in(c, text)), default=0)
        if best:
            hits[v["code"]] = best
    if not hits:
        return None, "no_cue"
    top = max(hits.values())
    winners = [code for code, n in hits.items() if n == top]
    return (winners[0], None) if len(winners) == 1 else (None, "ambiguous")


def predicate_code(vocabulary: dict, mention, subject_types: list[str], object_types: list[str],
                   context: str | None = None) -> str | None:
    """The code of ``vocabulary`` identified by a verbatim predicate, or None (see ``predicate_match``)."""
    return predicate_match(vocabulary, mention, subject_types, object_types, context)[0]
