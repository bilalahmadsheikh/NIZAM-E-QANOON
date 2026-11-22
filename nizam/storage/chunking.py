"""Chunk spans and context for the retrieval index (L2). Pure: no database.

docs/03 §3: a chunk is an index artefact -- ordered character offsets (char_start, char_end) into ONE
provision_version.text_normalised, never a second copy of the text. docs/02 §5.3: chunk only after the legal tree
exists; never split a proviso, exception, explanation or definition from the rule it qualifies; repeat compact
context (instrument title, section heading) in metadata, never by altering quoted text. INV-4: chunks find law,
provisions cite it -- no chunk identifier leaves L2.

AS BUILT (D-095, 18 Nov 2026). A provision_version holds its own node's words only: a clause does not contain its
sub-section's lead-in, and a proviso or Explanation is its own version. So a chunk covers (part of) one version, and
the rule a node qualifies travels in `context_prefix` (`qualifies: <its parent's opening words>`), which is what is
embedded with it. Grouping a unit's chunks is retrieval's collapse (docs/04 §5), not a wider span here.

`spans(text)` cuts a version into pieces of at most MAX_CHARS, preferring, inside [MIN_CHARS, MAX_CHARS] of the
current piece, a sentence end, then ';' or ':', then ',', then a space -- the latest of the strongest found. It never
cuts inside a word or after a citation abbreviation ('s.', 'No.', 'Rs.'), so 's. 302' stays whole. Text arrives
single-line and trimmed (schedule rows are flattened), so a sentence or row number ending '. ' is the row boundary.
Every non-space character of the text lies in exactly one span, in order; the spaces between spans belong to none.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CHUNKER = "nizam.chunking/1"
MAX_CHARS = 1200        # ~300 tokens: inside a 512-token multilingual encoder with the prefix prepended
MIN_CHARS = 400         # a cut is looked for only after this much of the piece
TAIL_MERGE = 120        # a last piece shorter than this joins the previous one when the two fit MAX_CHARS * 1.15
PREFIX_MAX = 240

# A '.' that ends an abbreviation does not end a sentence: 's. 302', 'No. 5', 'Rs. 500', 'Art. 199', 'i.e. the'.
_ABBREV = re.compile(
    r"(?:^|[\s(\[])(?:s|ss|S|Ss|No|Nos|no|nos|Rs|Art|Arts|art|Cl|cl|Sub|sub|Sch|sch|para|Para|paras|viz|i\.e|e\.g|"
    r"etc|Mr|Mrs|Dr|St|Govt|Vol|vol|p|pp|Ord|Reg|Regs|r|rr|O|Ch|ch|Pt|pt|Sec|sec|U|u|Co|Ltd|Pvt|Dy|Asstt|Addl|"
    r"[A-Z])\.$")
_STRENGTH = (("sentence", 3, re.compile(r"[.?!](?=\s+\S)")),
             ("clause", 2, re.compile(r"[;:](?=\s+\S)")),
             ("comma", 1, re.compile(r",(?=\s+\S)")),
             ("space", 0, re.compile(r"\S(?=\s+\S)")))


# Whitespace is ASCII only, the class audit A20's Postgres regex '\s' also matches: Python's str.isspace() counts
# NBSP and other Unicode spaces too, and a version whose spans were cut at one would fail A20 falsely (review,
# 18 Nov 2026). Released text holds none today (measured: 0 versions), so output is unchanged.
_WS = frozenset(" \t\n\r\f\v")


def _ws(c: str) -> bool:
    return c in _WS


@dataclass(frozen=True)
class Span:
    start: int
    end: int


def _cut(text: str, lo: int, hi: int) -> int | None:
    """End offset (exclusive) of the best boundary whose punctuation lies in text[lo:hi], or None."""
    window = text[lo:hi]
    for name, _strength, rx in _STRENGTH:
        best = None
        for m in rx.finditer(window):
            end = lo + m.end()
            if name == "sentence" and _ABBREV.search(text[max(0, end - 8):end]):
                continue
            best = end
        if best is not None:
            return best
    return None


def spans(text: str, max_chars: int = MAX_CHARS, min_chars: int = MIN_CHARS) -> list[Span]:
    """Ordered, non-overlapping spans covering every non-space character of `text` exactly once."""
    n = len(text)
    i = 0
    while i < n and _ws(text[i]):
        i += 1
    out: list[Span] = []
    while i < n:
        end_all = n
        while end_all > i and _ws(text[end_all - 1]):
            end_all -= 1
        if end_all - i <= max_chars:
            out.append(Span(i, end_all))
            break
        e = _cut(text, i + min_chars, i + max_chars) or _cut(text, i + 1, i + max_chars)
        if e is None:                       # one unbroken run longer than max_chars (a hash, a URL): hard cut
            e = i + max_chars
        out.append(Span(i, e))
        i = e
        while i < n and _ws(text[i]):
            i += 1
    if len(out) >= 2 and out[-1].end - out[-1].start < TAIL_MERGE \
            and out[-1].end - out[-2].start <= int(max_chars * 1.15):
        out[-2:] = [Span(out[-2].start, out[-1].end)]
    return out


# --- context: what is embedded beside a span, never altering the span ------------------------------------------

_UNIT_ABBR = {"section": "s.", "article": "Art.", "order": "O.", "schedule": "", "form": "", "appendix": "",
              "annexure": "", "preamble": "Preamble", "notification": "Notification", "chapter": "", "part": ""}
_QUALIFIES = {"proviso", "explanation", "illustration", "exception"}


@dataclass(frozen=True)
class Node:
    kind: str
    label: str
    heading: str | None


def unit_label(chain: list[Node]) -> str:
    """'s. 378(1)(a), Explanation 1' from the chain top-down (divisions excluded; schedules, forms by label)."""
    out = ""
    for nd in chain:
        k, lab = nd.kind, (nd.label or "").strip()
        if k in ("chapter", "part"):
            continue
        if k in ("section", "article", "order"):
            out = f"{_UNIT_ABBR[k]} {lab}".strip()
        elif k in ("schedule", "form", "appendix", "annexure"):
            out = lab or k.title()
        elif k == "preamble":
            out = "Preamble"
        elif k == "notification":            # D-115: an unnumbered notification is one unit, cited by its heading
            out = "Notification"
        elif k in ("subsection", "clause"):
            out += f"({lab})" if lab else ""
        elif k in _QUALIFIES:
            # 'Explanation 1' as printed; a proviso is labelled 'Provided' in the tree and named 'Proviso' here
            if lab.lower().startswith(k):
                word = lab
            elif lab and not lab.lower().startswith("provided"):
                word = f"{k.title()} {lab}"
            else:
                word = k.title()
            out += (", " if out else "") + word
        else:
            out += f" {lab}" if lab else ""
    return out.strip()


def context_prefix(title: str, division_heading: str | None, chain: list[Node],
                   qualifies: str | None = None, max_len: int = PREFIX_MAX) -> str:
    """'<title> | <chapter heading> | <unit> <section heading> | qualifies: <the rule's opening words>'."""
    parts = [" ".join((title or "").split())]
    if division_heading:
        parts.append(" ".join(division_heading.split()))
    unit = unit_label(chain)
    top = next((nd for nd in chain if nd.kind in ("section", "article", "order", "schedule", "form", "appendix",
                                                  "annexure", "notification")), None)
    head = " ".join((top.heading or "").split()) if top else ""
    if unit or head:
        parts.append(" ".join(x for x in (unit, head) if x))
    if qualifies and chain and chain[-1].kind in _QUALIFIES:
        q = " ".join(qualifies.split())
        parts.append("qualifies: " + (q[:80].rsplit(" ", 1)[0] + "…" if len(q) > 80 else q))
    s = " | ".join(p for p in parts if p)
    return s if len(s) <= max_len else s[:max_len - 1].rsplit(" ", 1)[0] + "…"


def passage_text(prefix: str, span_text: str) -> str:
    """what an embedding model reads for a chunk (D-098): its context prefix, a newline, its words -- the same string
    for the GPU corpus run (tools/kaggle/embed_inputs.py) and the CPU top-up (nizam.workers.chunk)"""
    return prefix + "\n" + span_text
