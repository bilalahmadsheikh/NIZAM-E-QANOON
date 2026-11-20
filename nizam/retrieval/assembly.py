"""L3 evidence assembly (docs/04 §7: "retrieve narrow; assemble complete"; D-107).

The gate passes a bundle of unit identities (GroundingContext.items). Assembly turns it into the evidence the
generator reads, deterministically, with a recorded reason for every addition:

  1. Each bundle unit is widened to the WHOLE unit: every operative sub-section, clause, proviso, explanation and
     illustration, printed order, as at the context's date and in its territory (INV-5). Never half a section.
  2. Definitions the unit depends on: clauses of the SAME law that define a word the unit uses ('"employer"
     means ...'), in scope -- "In this Act" (the whole law), "In this Chapter/Part" (units inside it), "In this
     section" (that section only, already whole). The narrowest definition in scope wins.
  3. Qualifications: units of the same law that the unit is "subject to", "notwithstanding", "save as / except
     as provided in", or "without prejudice to".
  4. References: other units and schedules of the same law the unit names ("under section 4", "the Second
     Schedule"). A reference to ANOTHER law ("section 5 of the Pakistan Penal Code", "of the Act") is not
     followed here; it is counted in the coverage record.
  5. Each item carries its law's facts (title, place, status, currency, dates, how far back the text is known),
     the Part and Chapter it sits in, the amendment footnotes printed on its nodes, the instruments made under it
     (`empowers`, 0089), its source (URL, file sha256, pages), and a citation RENDERED FROM RECORDS (INV-1).
  6. A budget selector admits items in priority order -- the governing rule first, then what it needs, then the
     next bundle unit -- skipping (never cutting) an item that does not fit, and recording why. The result is
     ordered as the law is printed: law by law (the best-ranked law first), then by printed order.

Assembly changes nothing the gate decided. If none of the bundle is law at the context's date (the corpus changed
between the two reads), retrieve() abstains; that is still one of the two values (INV-2).

Not built here (recorded in coverage['not_built']): sub-question coverage, conflict sets, definitions in General
Clauses Acts or a parent Act, references to other laws, the matched span's offsets, Urdu-script definitions.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field, replace
from datetime import date

from nizam.storage import evidence_read as ER
from nizam.storage.library_read import render_citation
from nizam.storage.unit_search import OUTER_KINDS, UNIT_KINDS

# --- the budget (docs/05 §5.2: "a compact evidence window capped by a configured input budget"; no figure is set
# there, so this one is D-107's, by evals/results/assembly-rule-2026-11-20.json: the smallest multiple of 5,000 at
# or above the dev p90 of the unconstrained GPU packet (48,593 characters, 20 Nov 2026), fixed before any gold
# metric was computed. About 12.5k tokens at ~4 characters a token) -----------------------------------------------
BUDGET_CHARS = int(os.environ.get("NIZAM_EVIDENCE_CHARS", "50000"))
MAX_UNITS = 20              # docs/04 §7: "admit at most about 20 legal units"
DEFS_PER_UNIT = 8           # definitions attached for one unit, by first use in its words
QUALS_PER_UNIT = 3
REFS_PER_UNIT = 3
NOTES_PER_ITEM = 12         # printed amendment footnotes carried per item
RANGE_MAX = 6               # "sections 4 to 9" is expanded when it names at most this many
DIVISION_SHARE = 0.25       # of the budget, for the sections standing for one bundle Part or Chapter
DIVISION_UNITS = 5          # sections standing for one Part or Chapter, at most (of MAX_UNITS)
DIVISION_READ = 60          # sections read from one Part or Chapter, at most
STUB_CHARS = 40             # a section this short ('3A. [Omitted]') does not stand for its Chapter

NOT_BUILT = ("sub-question coverage", "conflict sets", "General Clauses Act and parent-Act definitions",
             "references to other laws", "matched-span offsets", "Urdu-script definitions")

ROLE_RANK = {"governing": 0, "qualification": 1, "definition": 2, "reference": 3, "schedule": 3}


# ====================================================================================================================
# pure parsing
# ====================================================================================================================
_TERM_SRC = r"(?:[\"“”]\s*([^\"“”]{1,80}?)\s*[\"“”]|[‘'`]\s*([^‘’'`\"“”]{1,80}?)\s*[’'`])"
_TERM = re.compile(_TERM_SRC)
_VERB = re.compile(r"\b(?:shall\s+)?(?:means?|includes?|denotes?|signif(?:y|ies)|"
                   r"ha(?:s|ve)\s+the\s+(?:same\s+)?meanings?|have\s+the\s+(?:same\s+)?meanings?|"
                   r"is\s+deemed\s+to\s+include)\b", re.I)
# the run of quoted terms right before the verb: '"child" and "minor"', '"Court" or "court"', '"bank" (or "banker")'
_RUN = re.compile(_TERM_SRC + r"(?:\s*(?:,|and|or|/|\([^()]{0,30}\))\s*(?:the\s+)?(?:" + _TERM_SRC + r"))*"
                  r"\s*,?\s*(?:\([^()]{0,40}\)\s*)?$")


def _clean_term(t: str) -> str | None:
    t = " ".join((t or "").split()).strip(" ,.;:-–—")
    if not (2 <= len(t) <= 60) or not re.search(r"[A-Za-z]", t):
        return None
    return t


def definitions_in(text: str) -> list[tuple[str, bool]]:
    """[(word, empty)] for the words a clause defines, in printed order. `empty` is True when nothing follows the
    defining verb in this node ('"voter" means--' whose sub-clauses the segmenter did not place under it)."""
    out: list[tuple[str, bool]] = []
    for m in _VERB.finditer(text or ""):
        before = text[max(0, m.start() - 300):m.start()]
        run = _RUN.search(before)
        if not run:
            continue
        empty = not text[m.end():].strip(" \t\n—–―-:_.;,")
        for t in _TERM.finditer(run.group(0)):
            term = _clean_term(t.group(1) or t.group(2))
            if term and term.lower() not in (x[0].lower() for x in out):
                out.append((term, empty))
    return out


# a dash, a colon, underscores or a word that cannot end a definition; '; and' / '; or' end a list item and are not
_CONTINUES = re.compile(r"(?:[—–―:-]|_{2,}|\b(?:namely|of|includes?|means?|following))[\s_—–―:,-]*$", re.I)
CONTINUATION_NODES = 15
CONTINUATION_CHARS = 3000


def continues(text: str) -> bool:
    """does a definition's node stop mid-definition ('means--', 'namely:__', 'under the control of__')?"""
    return bool(_CONTINUES.search((text or "").rstrip()))


def continuation(nodes) -> list:
    """the siblings that carry a flattened definition's sub-items: in printed order, until a node that itself
    defines a word (the next definition), CONTINUATION_NODES nodes or CONTINUATION_CHARS characters"""
    out, size = [], 0
    for n in nodes:
        if defined_terms(n.text) or len(out) >= CONTINUATION_NODES or size + len(n.text or "") > CONTINUATION_CHARS:
            break
        out.append(n)
        size += len(n.text or "")
    return out


def defined_terms(text: str) -> list[str]:
    """the words a clause defines, in printed order: '"employer" means ...' -> ['employer'];
    'the words "public servant" denote ...' -> ['public servant']; '"child" and "minor" mean ...' -> both.
    A quoted word NOT followed by a defining verb is not a definition."""
    return [t for t, _empty in definitions_in(text)]


def term_pattern(term: str) -> re.Pattern:
    """a defined word as used in a unit: whole words, any case, a plain plural ('employer' finds 'employers')"""
    words = r"\s+".join(re.escape(w) for w in term.split())
    return re.compile(r"(?<![\w-])" + words + r"(?:s|es)?(?![\w-])", re.I)


# words that name a kind of instrument: '"Act" means the Punjab ... Act, 2019' defines the law's own name for itself
# (or, in Rules, the parent Act). Such a word is used only as "the Act", "this Act", "the said Act" -- never as the
# last word of another law's title ("the Punjab Rented Premises Act, 2009")
_INSTRUMENT_WORDS = {"act", "ordinance", "order", "code", "regulation", "regulations", "rules", "rule",
                     "constitution", "schedule", "statute", "president's order"}


def term_use(term: str, text: str) -> int | None:
    """where a unit first USES a defined word, or None"""
    pat = term_pattern(term)
    if term.lower() not in _INSTRUMENT_WORDS:
        m = pat.search(text or "")
        return m.start() if m else None
    for m in pat.finditer(text or ""):
        before = text[max(0, m.start() - 16):m.start()]
        after = text[m.end():m.end() + 8]
        if re.search(r"\b(?:the|this|said|that)\s+$", before, re.I) and not re.match(r"\s*,?\s*(?:\d{4}|\()", after):
            return m.start()
    return None


_SCOPE = re.compile(r"\b(?:in|for\s+the\s+purposes?\s+of|under|throughout)\s+this\s+(Act|Ordinance|Order|Code|"
                    r"Regulations?|Rules?|Constitution|Statute|Bye?-?laws?|Part|Chapter|section|sub-?section|"
                    r"article|clause|paragraph|rule|Schedule)\b", re.I)


def scope_word(texts) -> str | None:
    """the first 'In this <X>' among `texts` (the definition's own opening words first, then the words of the
    nodes above it, nearest first), lowercased; None when none says"""
    for t in texts:
        m = _SCOPE.search(t or "")
        if m:
            return m.group(1).lower().replace("-", "")
    return None


# "section 4", "sections 4, 8 and 9", "sections 10 to 12", "Article 25(1)", "section 9A"; the word part is
# case-free, the label's letter suffix is capitals only
_LAB = r"\d{1,4}[A-Z]{0,3}(?:\s*\(\s*[0-9a-zA-Z]{1,5}\s*\))*"
_REF = re.compile(r"\b(?i:(sections?|articles?))\s+(" + _LAB + r"(?:\s*(?:,|and|or|to|-|–|&)\s*" + _LAB + r")*)")
_SCHED = re.compile(r"\b(?:the\s+)?(?:(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|"
                    r"Twelfth)\s+)?Schedule(?:\s+([IVXL]{1,5}|\d{1,2})\b)?")
_EXTERNAL = re.compile(r"\s*,?\s*(?:\(\s*[0-9a-zA-Z]{1,5}\s*\)\s*)*(?:of|in|under|to)\s+(?:the\s+)?"
                       r"(?:said\s+|that\s+|above\s+|aforesaid\s+|principal\s+)?"
                       r"(?!this\b|these\b|Chapter\b|Part\b|Schedule\b|Sub-?section\b|Clause\b|Article\b|Section\b)"
                       r"(?:[A-Z][\w’'.()-]*|Act\b|Ordinance\b|Code\b|Order\b|Regulation)")
_QUAL = re.compile(r"\b(subject\s+to|notwithstanding|save\s+as|except\s+as|without\s+prejudice\s+to)\b", re.I)
# a law named earlier in the same sentence: 'In the Profession Tax Limitation Act, 1941 (XX of 1941), for section 2'
_TITLE_BEFORE = re.compile(r"\b[A-Z][A-Za-z’'&(),.\- ]{2,120}?\b(?:Act|Ordinance|Code|Order|Rules|Regulations)\b"
                           r",?\s*(?:\d{4}|\([IVXLC]+ of \d{4}\))")
# an amending law's section numbers name the law it amends ('In section 4, for the words ...')
AMENDING_TITLE = re.compile(r"\b(?:amendment|amending)\b|\bfinance\s+(?:act|ordinance|bill)\b", re.I)
_ORDINAL = {w: i for i, w in enumerate(("first second third fourth fifth sixth seventh eighth ninth tenth eleventh "
                                        "twelfth").split(), 1)}
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50}


def _roman(s: str) -> int | None:
    s = s.lower()
    if not s or any(c not in _ROMAN for c in s):
        return None
    total = 0
    for i, c in enumerate(s):
        v = _ROMAN[c]
        total += -v if i + 1 < len(s) and _ROMAN[s[i + 1]] > v else v
    return total


@dataclass(frozen=True)
class Reference:
    kind: str                 # "unit" (section/article) or "schedule"
    labels: tuple             # unit labels; or (schedule number,) / () for "the Schedule"
    qualifies: bool           # inside a "subject to / notwithstanding / save as ..." phrase
    external: bool            # names another law
    printed: str


def _sentence_head(text: str, pos: int) -> str:
    start = max(text.rfind(c, 0, pos) for c in ".;:\n")
    return text[max(start + 1, pos - 200):pos]


def _labels(group: str) -> tuple:
    toks = re.findall(r"\d{1,4}[A-Z]{0,3}|\([^)]*\)|\bto\b|[-–]", group)
    out: list[str] = []
    pending_range = False
    for t in toks:
        if t.startswith("("):
            continue
        if t in ("to", "-", "–"):
            pending_range = True
            continue
        if pending_range and out and out[-1].isdigit() and t.isdigit() and 0 < int(t) - int(out[-1]) <= RANGE_MAX:
            out.extend(str(n) for n in range(int(out[-1]) + 1, int(t) + 1))
        else:
            out.append(t)
        pending_range = False
    return tuple(dict.fromkeys(out))


def references(text: str) -> list[Reference]:
    """the units and schedules a unit's words name, in printed order"""
    text = text or ""
    out = []
    for m in _REF.finditer(text):
        head = _sentence_head(text, m.start())
        ext = bool(_EXTERNAL.match(text, m.end())) or bool(_TITLE_BEFORE.search(head))
        out.append(Reference("unit", _labels(m.group(2)), bool(_QUAL.search(head)), ext, m.group(0)))
    for m in _SCHED.finditer(text):
        n = None
        if m.group(1):
            n = _ORDINAL[m.group(1).lower()]
        elif m.group(2):
            n = int(m.group(2)) if m.group(2).isdigit() else _roman(m.group(2))
        ext = bool(_EXTERNAL.match(text, m.end()))
        out.append(Reference("schedule", (n,) if n else (), bool(_QUAL.search(_sentence_head(text, m.start()))),
                             ext, m.group(0)))
    return out


def schedule_number(label: str, heading: str | None) -> int | None:
    """the number a schedule prints for itself: 'FIRST SCHEDULE' -> 1, 'Schedule II' -> 2, 'SCHEDULE 3' -> 3"""
    for s in (label or "", heading or ""):
        m = re.search(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)\b",
                      s, re.I)
        if m:
            return _ORDINAL[m.group(1).lower()]
        m = re.search(r"schedule\s*[-–]?\s*([IVXL]{1,5}|\d{1,2})\b", s, re.I)
        if m:
            g = m.group(1)
            return int(g) if g.isdigit() else _roman(g)
    return None


# ====================================================================================================================
# pure rendering (INV-1: every part of a citation is a stored record; nothing is generated)
# ====================================================================================================================
def _tidy(label: str) -> str:
    lab = " ".join((label or "").split())
    if lab.isupper():
        lab = " ".join(w if _roman(w) else w.capitalize() for w in lab.split())
    return lab


def unit_head(kind: str, label: str, law_kind: str | None = None) -> str:
    """a unit as prose names it ('Section 4', 'Article 25' -- a constitution's sections are Articles, D-070)"""
    lab = " ".join((label or "").split())
    if kind == "section":
        return f"Article {lab}" if law_kind == "constitution" else f"Section {lab}"
    if kind == "article":
        return f"Article {lab}"
    if kind == "order":
        return _tidy(lab) if lab.lower().startswith("order") else f"Order {lab}"
    if kind in OUTER_KINDS:
        lab = re.sub(r"^\d+(?=[A-Za-z])", "", lab)        # a footnote marker glued to 'Schedule' ('19Schedule')
        return _tidy(lab) if re.search(r"[A-Za-z]{3}", lab) else f"{kind.capitalize()} {lab}".strip()
    return lab


def citation(unit_kind: str, unit_label: str, title: str, chain=(), year: int | None = None,
             law_kind: str | None = None) -> str | None:
    """the server's citation form (nizam.storage.library_read.render_citation, D-070), from records only (INV-1):
    'Punjab ... Act, 2021, s. 2(1)(e)'; 'Constitution of ..., Art. 25'; '..., Order XXI'; '..., Third Schedule'.
    The labels below the unit follow it: sub-sections and clauses in brackets, then ', proviso' or ', Explanation 1'.
    None without a title or label, never guessed."""
    brackets, tail = "", ""
    for kind, label in chain:
        lab = " ".join((label or "").split())
        if kind in ("subsection", "clause") and lab:
            brackets += f"({lab})"
        elif kind == "proviso":
            tail += ", proviso"
        elif kind in ("explanation", "illustration") and lab:
            tail += f", {lab}"
    lab = " ".join((unit_label or "").split())
    if unit_kind in ("section", "article", "preamble"):
        out = render_citation(title, year, unit_kind, (lab + brackets) if lab else lab, law_kind)
        return out + tail if out else None
    if not title or not lab:
        return None
    name = title.strip().rstrip(".")
    if year and str(year) not in name:
        name = f"{name}, {year}"
    return f"{name}, {unit_head(unit_kind, unit_label, law_kind)}{brackets}{tail}"


def node_line(n: ER.Node, base_depth: int) -> str:
    text = " ".join((n.text or "").split())
    lab = " ".join((n.label or "").split())
    indent = "  " * max(0, n.path.count(".") - base_depth)
    if n.kind in ("section", "article"):
        head = f"{lab}." + (f" {' '.join(n.heading.split())}" if n.heading else "")
        line = f"{head} {text}".strip()
    elif n.kind == "order":
        line = f"{_tidy(lab)}" + (f" {' '.join(n.heading.split())}" if n.heading else "") + (f" {text}" if text else "")
    elif n.kind in ("subsection", "clause"):
        line = f"({lab}) {text}".strip()
    elif n.kind in ("proviso", "explanation", "illustration"):
        line = text if (lab.isdigit() or text.lower().startswith(lab.lower())) else f"{lab} {text}".strip()
    else:
        head = " ".join(x for x in (_tidy(lab), " ".join((n.heading or "").split())) if x)
        line = f"{head} {text}".strip()
    return indent + line


def unit_line(u) -> str:
    """a unit's own label and heading, as printed ('5. Jurisdiction'): the first line of an item whose unit node
    has no words of its own (the section's words are all in its sub-sections)"""
    lab = " ".join((u.label or "").split())
    heading = " ".join((u.heading or "").split())
    if u.kind in ("section", "article"):
        return f"{lab}." + (f" {heading}" if heading else "")
    return " ".join(x for x in (_tidy(lab), heading) if x)


def render(nodes, base_path: str, head_line: str | None = None) -> str:
    depth = base_path.count(".")
    lines = [line for line in (node_line(n, depth) for n in nodes) if line.strip()]
    if head_line and (not nodes or nodes[0].path != base_path):
        lines.insert(0, head_line)
    return "\n".join(lines)


# ====================================================================================================================
# the output
# ====================================================================================================================
@dataclass(frozen=True)
class EvidenceItem:
    """docs/04 §7's EvidenceItem, as built. Identities are stored ids (INV-4: provisions, never chunks)."""
    unit_id: str                     # legalUnitId: the section, article, order or schedule
    provision_id: str                # the node the item IS: the unit, or a definition clause inside one
    instrument_id: str
    role: str                        # governing | qualification | definition | reference | schedule
    inclusion_reason: str
    citation: str                    # displayCitation, rendered from records (INV-1)
    heading: str | None
    text: str                        # the item's operative nodes, printed order, one per line
    nodes: tuple                     # ((provision id, version id, kind, label), ...), the lines' order
    divisions: tuple                 # ((kind, label, heading), ...): the Parts and Chapters it sits in
    law: dict                        # the law's facts from operative_provision at as_of in the territory
    amendments: tuple                # printed amendment footnotes on its nodes, verbatim
    delegated: tuple                 # ((instrument id, title, kind, year), ...) made under it (governing units)
    source: dict                     # url, sha256, document id, pages
    as_of: date
    territory: str | None
    rank: int | None = None          # the bundle rank of a governing unit
    rerank_score: float | None = None
    order: tuple = field(default=(), compare=False)

    @property
    def chars(self) -> int:
        return len(self.text) + sum(len(a) for a in self.amendments)


@dataclass
class _Cand:
    key: str                         # the provision the item is
    unit_id: str
    instrument_id: str
    role: str
    reason: str
    nodes: tuple
    base_path: str
    chain: tuple = ()
    rank: int | None = None
    rerank: float | None = None
    size: int = 0
    head_line: str | None = None     # the unit's label and heading, when its own node has no words


def select(cands: list[_Cand], budget: int, max_units: int):
    """admit in priority order: skip an item already inside an admitted one, an item that would pass the unit cap,
    or one that does not fit the budget (it is skipped, never cut). The first governing unit is always admitted
    (an answer never lacks its governing rule); if it alone passes the budget, that is recorded. A whole unit
    admitted after one of its own clauses replaces the clause."""
    admitted: list[_Cand] = []
    omitted: list[dict] = []
    used = 0
    units = 0

    def inside(path: str, other: _Cand) -> bool:
        return path == other.base_path or path.startswith(other.base_path + ".")

    for c in cands:
        holder = next((a for a in admitted if a.instrument_id == c.instrument_id and inside(c.base_path, a)), None)
        if holder is not None:
            omitted.append({"provision": c.key, "role": c.role, "reason": f"inside {holder.key}"})
            continue
        whole = c.role != "definition"
        first = not admitted and c.role == "governing"
        if whole and units >= max_units and not first:
            omitted.append({"provision": c.key, "role": c.role, "reason": "unit cap"})
            continue
        replaced = [a for a in admitted if a.instrument_id == c.instrument_id and inside(a.base_path, c)]
        size = c.size - sum(a.size for a in replaced)
        if used + size > budget and not first:
            omitted.append({"provision": c.key, "role": c.role, "reason": "budget", "chars": c.size})
            continue
        for a in replaced:
            admitted.remove(a)
            omitted.append({"provision": a.key, "role": a.role, "reason": f"inside {c.key}"})
            if a.role != "definition":
                units -= 1
        admitted.append(c)
        used += size
        units += int(whole)
    return admitted, omitted, used


# ====================================================================================================================
# assembly
# ====================================================================================================================
def _unit_text(u: ER.Unit) -> str:
    return " ".join(x for n in u.nodes for x in (n.heading or "", n.text or "") if x)


def _unit_of(chain) -> ER.Ancestor | None:
    inner = [a for a in chain if a.kind in UNIT_KINDS]
    if inner:
        return inner[-1]
    outer = [a for a in chain if a.kind in OUTER_KINDS]
    return outer[0] if outer else (chain[-1] if chain else None)


def _scope_path(word: str | None, chain, unit: ER.Ancestor, law_kind: str | None) -> tuple[str, str | None]:
    """('law', None) | ('division', path) | ('unit', path)"""
    if word in ("part", "chapter"):
        # the named division, as the tree holds it; when the tree lacks it (a Chapter the segmenter did not make a
        # node), the definition reaches no further than its own unit: never the whole law
        div = [a for a in chain if a.kind == word]
        return ("division", div[-1].path) if div else ("unit", unit.path)
    if word == "order":
        order = [a for a in chain if a.kind == "order"]
        if order and "order" not in (law_kind or "").lower():
            return "division", order[-1].path
        return "law", None
    if word in ("section", "subsection", "article", "clause", "paragraph", "rule", "schedule"):
        return "unit", unit.path
    return "law", None


def _applies(scope: tuple, unit_path: str, unit_ordinal: int | None = None) -> bool:
    """does a definition's scope reach a unit? ('law', None) reaches the whole law; ('division', path[, ordinal])
    the units inside that Part or Chapter printed AFTER the definition -- a Chapter's definitions open it, so a unit
    printed before them is outside them, which also keeps a definition inside its true Chapter when the tree has
    folded two Chapters into one (Constitution Chapter 3A under Chapter 3, D-107); ('unit', path) its own unit"""
    kind, path = scope[0], scope[1]
    if kind == "law":
        return True
    if not (unit_path == path or unit_path.startswith(path + ".")):
        return False
    after = scope[2] if len(scope) > 2 else None
    return kind != "division" or after is None or unit_ordinal is None or unit_ordinal > after


@dataclass(frozen=True)
class _Gov:
    """a governing unit: a bundle unit, or a section standing for a bundle Part or Chapter"""
    unit_id: str
    rank: int
    rerank_score: float | None
    via_citation: bool
    note: str


def division_name(kind: str, label: str, heading: str | None) -> str:
    name = f"{'Chapter' if kind == 'chapter' else 'Part'} {' '.join((label or '').split())}"
    return name + (f" ({' '.join(heading.split())})" if heading else "")


def _governing(s, live, units: dict, budget: int, cov: dict) -> list[_Gov]:
    """the bundle as governing units. A Part or Chapter in the bundle (retrieval maps a match on its heading to it)
    is not a citable unit (INV-4: provisions are): its sections stand for it. Those the bundle already holds keep
    their own rank; the rest are taken in printed order, whole, at most DIVISION_UNITS of them and while they fit
    DIVISION_SHARE of the budget (the first always, if it fits the budget), skipping stubs ('[Omitted]'), so one
    heading match cannot crowd out the bundle's other units."""
    held = {b.unit_id for b in live}
    out: list[_Gov] = []
    for b in live:
        u = units[b.unit_id]
        if u.kind not in ER.DIVISION_KINDS:
            out.append(_Gov(b.unit_id, b.rank, b.rerank_score, b.via_citation,
                            f"bundle rank {b.rank}" + (", named in the question" if b.via_citation else "")))
            continue
        name = division_name(u.kind, u.label, u.heading)
        inner = s.units_within(u.instrument_id, u.path)
        rest = [i for i in inner if i not in held][:DIVISION_READ]
        got = s.units(rest)
        share, taken = 0, []
        for i in rest:
            if i not in got:
                continue
            size = len(render(got[i].nodes, got[i].path))
            if size < STUB_CHARS:
                continue
            if len(taken) >= DIVISION_UNITS:
                break
            if share + size > budget * DIVISION_SHARE:
                if not taken and size <= budget:
                    taken.append(i)
                break
            share += size
            taken.append(i)
        for i in taken:
            units[i] = got[i]
            out.append(_Gov(i, b.rank, b.rerank_score, False,
                            f"in {name}, whose heading matched (bundle rank {b.rank})"))
        cov.setdefault("divisions", []).append({"division": u.unit_id, "name": name, "rank": b.rank,
                                                "sections": len(inner), "in_bundle": len(inner) - len(rest),
                                                "taken": len(taken)})
    return out


def assemble(ctx, connect_fn=None, budget: int | None = None, max_units: int = MAX_UNITS):
    """GroundingContext -> the same context with `evidence` (EvidenceItem, legal order) and `coverage`; or None
    when no bundle unit is law at the context's date (the caller abstains)"""
    t0 = time.perf_counter()
    laps: dict[str, float] = {}

    def lap(name: str, since=[t0]):
        now = time.perf_counter()
        laps[name] = round((now - since[0]) * 1000, 1)
        since[0] = now

    budget = BUDGET_CHARS if budget is None else budget
    f = ctx.filters
    kwargs = {"connect_fn": connect_fn} if connect_fn else {}
    bundle = list(ctx.items)
    cov: dict = {"budget_chars": budget, "max_units": max_units, "omitted": [], "not_operative": [],
                 "references": {"followed": 0, "other_law": 0, "unresolved": [], "not_operative": []},
                 "not_built": list(NOT_BUILT)}
    with ER.session(f, **kwargs) as s:
        units = s.units([b.unit_id for b in bundle])
        cov["not_operative"] = [b.unit_id for b in bundle if b.unit_id not in units]
        live = _governing(s, [b for b in bundle if b.unit_id in units], units, budget, cov)
        if not live:
            return None
        laws = list(dict.fromkeys(units[b.unit_id].instrument_id for b in live))
        text_of = {b.unit_id: _unit_text(units[b.unit_id]) for b in live}

        def head(u) -> str:          # 'Section 4', or 'Article 4' in a constitution
            lf = s._facts.get(u.instrument_id)
            return unit_head(u.kind, u.label, lf.kind if lf else None)
        lap("units")

        # --- references named by the bundle's words: one label lookup per law -------------------------------
        def amending(u) -> bool:
            lf = s._facts.get(u.instrument_id)
            return bool(lf and AMENDING_TITLE.search(lf.title or ""))

        parsed = {b.unit_id: [replace(r, external=True) if r.kind == "unit" and amending(units[b.unit_id]) else r
                              for r in references(text_of[b.unit_id])] for b in live}
        cov["references"]["other_law"] = sum(1 for rs in parsed.values() for r in rs if r.external)
        labels_by_law: dict[str, set] = {}
        sched_laws = set()
        for b in live:
            u = units[b.unit_id]
            for r in parsed[b.unit_id]:
                if r.external:
                    continue
                if r.kind == "unit":
                    labels_by_law.setdefault(u.instrument_id, set()).update(r.labels)
                else:
                    sched_laws.add(u.instrument_id)
        found = {iid: s.units_labelled(iid, sorted(labs)) for iid, labs in labels_by_law.items()}
        scheds = {iid: [x for x in s.outer_units(iid) if x[1] == "schedule"] for iid in sched_laws}
        per_unit_refs: dict[str, list[tuple[str, str, str]]] = {}
        ref_ids: list[str] = []
        for b in live:
            u = units[b.unit_id]
            wanted: list[tuple[Reference, str]] = []
            for r in parsed[b.unit_id]:
                if r.external:
                    continue
                if r.kind == "unit":
                    for lab in r.labels:
                        uid = found.get(u.instrument_id, {}).get(lab)
                        if uid is None:
                            cov["references"]["unresolved"].append(f"{head(u)}: {lab}")
                        elif uid != u.unit_id:
                            wanted.append((r, uid))
                else:
                    pool = scheds.get(u.instrument_id, [])
                    hits = ([x for x in pool if schedule_number(x[2], x[3]) == r.labels[0]] if r.labels
                            else (pool if len(pool) == 1 else []))
                    if hits:
                        wanted.append((r, hits[0][0]))
                    else:
                        cov["references"]["unresolved"].append(f"{head(u)}: {r.printed}")
            seen, lst = {u.unit_id}, []
            for qualifying, cap in ((True, QUALS_PER_UNIT), (False, REFS_PER_UNIT)):
                n = 0
                for r, uid in wanted:
                    if r.qualifies != qualifying or uid in seen or n >= cap:
                        continue
                    seen.add(uid)
                    n += 1
                    role = "qualification" if r.qualifies else ("schedule" if r.kind == "schedule" else "reference")
                    lst.append((uid, role, r.printed))
                    ref_ids.append(uid)
            per_unit_refs[b.unit_id] = lst
        units.update(s.units([uid for uid in dict.fromkeys(ref_ids) if uid not in units]))
        cov["references"]["followed"] = len({uid for uid in ref_ids if uid in units})
        cov["references"]["not_operative"] = sorted({uid for uid in ref_ids if uid not in units})
        lap("references")

        # --- definitions: parse every definition clause of the bundle's laws, keep those a unit uses ----------
        dnodes, empty = [], set()
        # an amending law's quoted words are new text for the law it amends, not definitions of its own
        own = [iid for iid in laws if not AMENDING_TITLE.search(getattr(s._facts.get(iid), "title", "") or "")]
        for iid, n in s.definition_nodes(own):
            found_terms = definitions_in(n.text)
            empty |= {(n.provision_id, t.lower()) for t, e in found_terms if e}
            dnodes.append((iid, n, [t for t, _e in found_terms]))
        lap("definition_read")
        uses: dict[str, list] = {}           # bundle unit id -> [(pos, term, node)]
        for iid, n, terms in dnodes:
            for b in live:
                u = units[b.unit_id]
                if u.instrument_id != iid or n.path == u.path or n.path.startswith(u.path + "."):
                    continue
                for t in terms:
                    pos = term_use(t, text_of[b.unit_id])
                    if pos is not None:
                        uses.setdefault(b.unit_id, []).append((pos, t, n))
        used_nodes = list({n.provision_id: n for lst in uses.values() for _p, _t, n in lst}.values())
        chains = s.ancestors([n.provision_id for n in used_nodes])
        scope_of: dict[str, tuple] = {}
        unit_anc: dict[str, ER.Ancestor] = {}
        leads_wanted = []
        for n in used_nodes:
            chain = chains.get(n.provision_id, ())
            unit = _unit_of(chain)
            if unit is not None:
                unit_anc[n.provision_id] = unit
                leads_wanted += [a.provision_id for a in chain if a.depth >= unit.depth and a.provision_id != n.provision_id]
        leads = s.lead_texts(leads_wanted)
        for n in used_nodes:
            unit = unit_anc.get(n.provision_id)
            if unit is None:
                continue
            chain = chains[n.provision_id]
            first_quote = re.search(r"[\"“”‘'`]", n.text or "")
            own_head = (n.text or "")[: first_quote.start()] if first_quote else ""
            above = [leads.get(a.provision_id, "") for a in reversed(chain)
                     if a.depth >= unit.depth and a.provision_id != n.provision_id]
            sc = _scope_path(scope_word([own_head] + above), chain, unit, None)
            scope_of[n.provision_id] = (sc[0], sc[1], n.ordinal) if sc[0] == "division" else sc
        lap("definition_scope")

        # --- candidates, in priority order: each bundle unit, then what it needs ------------------------------
        bundle_rank = {b.unit_id: b for b in live}
        cands: list = []
        late: list[_Cand] = []
        def_wanted: dict[str, list] = {}
        for b in live:
            u = units[b.unit_id]
            cands.append(_Cand(u.unit_id, u.unit_id, u.instrument_id, "governing", b.note, u.nodes, u.path,
                               rank=b.rank, rerank=b.rerank_score))
            for uid, role, printed in per_unit_refs.get(b.unit_id, []):
                if uid not in units:
                    continue
                r = units[uid]
                also = bundle_rank.get(uid)
                c = _Cand(uid, uid, r.instrument_id, role,
                          f"{head(u)} {'is qualified by' if role == 'qualification' else 'names'}"
                          f" '{printed}'" + (f" (also bundle rank {also.rank})" if also else ""), r.nodes, r.path,
                          rank=also.rank if also else None, rerank=also.rerank_score if also else None)
                (cands if role == "qualification" else late).append(c)
            # one definition per word: the narrowest scope that reaches this unit, then the earliest clause
            best: dict[str, tuple] = {}
            for pos, term, n in uses.get(b.unit_id, []):
                scope = scope_of.get(n.provision_id)
                if scope is None or not _applies(scope, u.path, u.ordinal):
                    continue
                rank = (("unit", "division", "law").index(scope[0]), n.ordinal)
                key = term.lower()
                if key not in best or rank < best[key][0]:
                    best[key] = (rank, pos, term, n)
            for _rank, _pos, term, n in sorted(best.values(), key=lambda x: (x[1], -len(x[2])))[:DEFS_PER_UNIT]:
                def_wanted.setdefault(n.provision_id, []).append((u, term, n, len(cands)))
                cands.append(None)            # filled below, once the definition's subtree is read
        subs = s.subtrees(list(def_wanted))
        # a definition that stops mid-sentence with nothing under it: its sub-items are its following siblings
        flat = [pid for pid, sub in subs.items() if len(sub) == 1 and continues(sub[0].text)]
        nexts = s.following(flat, CONTINUATION_NODES) if flat else {}
        for pid, wants in def_wanted.items():
            sub = subs.get(pid)
            if not sub:
                continue
            u, _term, n, idx = wants[0]
            if pid in nexts:
                more = continuation(nexts[pid])
                if more:
                    sub = tuple(sub) + tuple(more)
                    cov.setdefault("continued_definitions", []).append({"provision": pid, "siblings": len(more)})
            if len(sub) == 1 and all((pid, w[1].lower()) in empty for w in wants):
                # '"voter" means--' with nothing under it or after it: its words are not in the corpus's nodes
                cov["omitted"].append({"provision": pid, "role": "definition", "reason": "definition text not in node"})
                continue
            unit = unit_anc[pid]
            chain = chains[pid]
            terms = sorted({w[1] for w in wants}, key=str.lower)
            users = list(dict.fromkeys(head(w[0]) for w in wants))
            cands[idx] = _Cand(pid, unit.provision_id, u.instrument_id, "definition",
                               f"defines {', '.join(repr(t) for t in terms)}, used in {', '.join(users)}",
                               sub, n.path, chain=tuple((a.kind, a.label) for a in chain if a.depth > unit.depth))
        cands = [c for c in cands if c is not None] + late
        for c in cands:
            if c.role != "definition" and c.unit_id in units:
                c.head_line = unit_line(units[c.unit_id])
            c.size = len(render(c.nodes, c.base_path, c.head_line))
        admitted, omitted, used = select(cands, budget, max_units)
        cov["omitted"] = cov["omitted"] + omitted
        lap("select")

        # --- what each admitted item carries ------------------------------------------------------------------
        divs = s.ancestors(list({c.unit_id for c in admitted}))
        notes = s.amendment_notes([nd.provision_id for c in admitted for nd in c.nodes],
                                  [c.instrument_id for c in admitted])
        lap("notes")
        dele = s.delegated([c.unit_id for c in admitted if c.role == "governing"])
        lap("delegated")
        facts = s.facts({c.instrument_id for c in admitted})
    law_order = {iid: i for i, iid in enumerate(dict.fromkeys(c.instrument_id for c in admitted))}
    items = []
    for c in admitted:
        lf = facts.get(c.instrument_id)
        uchain = divs.get(c.unit_id, ())
        u_anc = uchain[-1] if uchain else None
        text = render(c.nodes, c.base_path, c.head_line)
        printed: list[str] = []
        for nd in c.nodes:
            for a in notes.get(nd.provision_id, ()):
                if a.printed and a.printed not in printed:
                    printed.append(a.printed)
        if len(printed) > NOTES_PER_ITEM:
            cov.setdefault("notes_dropped", {})[c.key] = len(printed) - NOTES_PER_ITEM
        pages = [p for nd in c.nodes for p in (nd.first_page, nd.last_page) if p]
        heading = None if c.role == "definition" else (u_anc.heading if u_anc else None)
        items.append(EvidenceItem(
            unit_id=c.unit_id, provision_id=c.key, instrument_id=c.instrument_id, role=c.role,
            inclusion_reason=c.reason,
            citation=citation(u_anc.kind if u_anc else "section", u_anc.label if u_anc else "",
                              lf.title if lf else "", c.chain, lf.year if lf else None, lf.kind if lf else None),
            heading=heading, text=text,
            nodes=tuple((nd.provision_id, nd.version_id, nd.kind, nd.label) for nd in c.nodes),
            divisions=tuple((a.kind, a.label, a.heading) for a in uchain if a.kind in ER.DIVISION_KINDS),
            law=_law_dict(lf), amendments=tuple(printed[:NOTES_PER_ITEM]),
            delegated=tuple((d.instrument_id, d.title, d.kind, d.year) for d in dele.get(c.unit_id, ())),
            source={"url": lf.source_url if lf else None, "sha256": lf.source_sha256 if lf else None,
                    "document_id": lf.document_id if lf else None,
                    "pages": [min(pages), max(pages)] if pages else None},
            as_of=f.as_of, territory=f.territory, rank=c.rank, rerank_score=c.rerank,
            order=(law_order[c.instrument_id], c.nodes[0].ordinal if c.nodes else 0, c.base_path)))
    items.sort(key=lambda it: it.order)
    lap("build")
    cov.update(used_chars=used, units=sum(1 for c in admitted if c.role != "definition"),
               definitions=sum(1 for c in admitted if c.role == "definition"), over_budget=used > budget,
               timings_ms=laps, assembly_ms=round((time.perf_counter() - t0) * 1000, 1))
    return replace(ctx, evidence=tuple(items), coverage=cov)


def _law_dict(lf: ER.LawFacts | None) -> dict:
    if lf is None:
        return {}
    d = dict(lf.__dict__)
    for k in ("enacted_on", "commenced_on", "text_known_from"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d
