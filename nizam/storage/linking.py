"""Pure rules for the links a provision's own words make (docs/03b §1.1; D-108): the words it defines, for where,
and the units and schedules it names, with how it relates to them. No database: nizam.workers.links builds the
derived tables from these rules, and L3 assembly reads the same rules where it must (nizam.retrieval.assembly).

  defines         '"employer" means ...', 'the words "public servant" denote ...', scoped by 'In this Act /
                  Chapter / section'
  notwithstanding 'Notwithstanding anything contained in section 5' -- this provision prevails over the one named
  subject_to      'Subject to section 5', 'save as / except as provided in section 5', 'without prejudice to
                  section 5' -- this provision yields where the two would conflict
  refers_to       any other naming of a unit or schedule ('under section 4', 'the Second Schedule')

A unit named "of the Pakistan Penal Code" (or with a law's title earlier in the sentence) is another law's: it is
returned with `other_law` as printed, for the builder to resolve, and never to the law the words are in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

RANGE_MAX = 6               # "sections 4 to 9" is expanded when it names at most this many
CONTINUATION_NODES = 15
CONTINUATION_CHARS = 3000

# --- definitions ------------------------------------------------------------------------------------------------------
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


def term_key(term: str) -> str:
    """the form a defined word is looked up by: case and spacing folded"""
    return " ".join((term or "").lower().split())


def definitions_in(text: str) -> list[tuple[str, bool]]:
    """[(word, empty)] for the words a clause defines, in printed order. `empty` is True when nothing follows the
    defining verb in this node ('"voter" means--' whose sub-clauses the segmenter did not place under it)."""
    out: list[tuple[str, bool]] = []
    for m in _VERB.finditer(text or ""):
        before = text[max(0, m.start() - 300):m.start()]
        run = _RUN.search(before)
        if not run:
            continue
        empty = not text[m.end():].strip(" \t\n" + _DASHES + ":_.;,")
        for t in _TERM.finditer(run.group(0)):
            term = _clean_term(t.group(1) or t.group(2))
            if term and term_key(term) not in (term_key(x[0]) for x in out):
                out.append((term, empty))
    return out


def defined_terms(text: str) -> list[str]:
    """the words a clause defines, in printed order: '"employer" means ...' -> ['employer'];
    'the words "public servant" denote ...' -> ['public servant']; '"child" and "minor" mean ...' -> both.
    A quoted word NOT followed by a defining verb is not a definition."""
    return [t for t, _empty in definitions_in(text)]


# a dash, a colon, underscores or a word that cannot end a definition; '; and' / '; or' end a list item and are not.
# The dashes statutes print: em, en, horizontal bar, figure dash, two-em (⸺), horizontal line extension (⎯)
_DASHES = "—–―‒⸺⸻⎯-"
_D = re.escape(_DASHES)
_CONTINUES = re.compile(r"(?:[" + _D + r":]|_{2,}|\b(?:namely|of|includes?|means?|following))[\s_" + _D + r":,]*$",
                        re.I)


def continues(text: str) -> bool:
    """does a definition's node stop mid-definition ('means--', 'namely:__', 'under the control of__')?"""
    return bool(_CONTINUES.search((text or "").rstrip()))


def continuation(texts) -> int:
    """how many of the siblings printed after a flattened definition carry its sub-items: in order, until one that
    itself defines a word (the next definition), CONTINUATION_NODES nodes or CONTINUATION_CHARS characters"""
    n, size = 0, 0
    for t in texts:
        if defined_terms(t) or n >= CONTINUATION_NODES or size + len(t or "") > CONTINUATION_CHARS:
            break
        n += 1
        size += len(t or "")
    return n


def term_pattern(term: str) -> re.Pattern:
    """a defined word as used in a unit: whole words, any case, a plain plural ('employer' finds 'employers')"""
    words = r"\s+".join(re.escape(w) for w in term.split())
    return re.compile(r"(?<![\w-])" + words + r"(?:s|es)?(?![\w-])", re.I)


# words that name a kind of instrument: '"Act" means the Punjab ... Act, 2019' defines the law's own name for itself
# (or, in Rules, the parent Act). Such a word is used only as "the Act", "this Act", "the said Act" -- never as the
# last word of another law's title ("the Punjab Rented Premises Act, 2009")
INSTRUMENT_WORDS = {"act", "ordinance", "order", "code", "regulation", "regulations", "rules", "rule",
                    "constitution", "schedule", "statute", "president's order"}


# drafting words: a definition of the statute's own structure ('"section" means ...', '"year" means a year reckoned
# according to the British calendar') explains no rule, and they occur in nearly every unit
DRAFTING_WORDS = {"section", "sub-section", "subsection", "chapter", "part", "clause", "sub-clause", "schedule",
                  "rule", "regulation", "act", "central act", "year", "month", "financial year", "week", "day",
                  "gazette", "official gazette", "constitution", "article", "paragraph", "item", "form"}
# a General Clauses Act word too general to explain a particular provision (defaults_from): the law's own
# definition still applies
GENERAL_TOO_BROAD = {"person", "government", "the government", "provincial government", "federal government",
                     "central government", "the central government", "pakistan", "province", "provinces",
                     "the punjab", "punjab", "sindh", "sind", "west pakistan", "east pakistan", "khyber pakhtunkhwa",
                     "balochistan", "baluchistan", "india", "british india", "british possession", "colony",
                     "her majesty", "the crown", "son", "father", "writing", "sign", "signature", "number", "swear",
                     "commencement", "tribal areas"}


def term_use(term: str, text: str) -> int | None:
    """where a unit first USES a defined word, or None"""
    pat = term_pattern(term)
    if term_key(term) not in INSTRUMENT_WORDS:
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


_UNIT_WORDS = ("section", "subsection", "article", "clause", "paragraph", "rule", "schedule")


def definition_scope(word: str | None, chain, unit, law_kind: str | None) -> tuple[str, object]:
    """('law', None) | ('division', the Part/Chapter/Order) | ('unit', the definition's unit), from the scope word
    and the definition's ancestors `chain` [(id, kind), ...] outermost first:
      "In this Act"            -> the law;
      "In this Chapter/Part"   -> that division as the tree holds it; when the tree lacks it (a Chapter the
                                  segmenter did not make a node) the definition reaches no further than its unit;
      "In this Order"          -> the CPC-style Order it sits in, unless the law itself is an Order;
      "In this section/clause" -> its unit."""
    if word in ("part", "chapter"):
        div = [i for i, k in chain if k == word]
        return ("division", div[-1]) if div else ("unit", unit)
    if word == "order":
        order = [i for i, k in chain if k == "order"]
        return ("division", order[-1]) if order and "order" not in (law_kind or "") else ("law", None)
    if word in _UNIT_WORDS:
        return "unit", unit
    return "law", None


def lead_in(preceding) -> str:
    """the words that introduce a run of definitions printed as siblings ('Explanation.--For the purposes of this
    section:' before '(a) "company" means ...', '(b) "director" means ...'): walking back from the nearest preceding
    sibling over those that themselves define a word, the first that does not, if it ends as a lead-in (a colon,
    a dash, 'namely'); else ''"""
    for t in preceding:
        if defined_terms(t):
            continue
        return t if _CONTINUES.search((t or "").rstrip()) else ""
    return ""


def opening(text: str) -> str:
    """a definition's own opening words: everything before its first quotation mark ('In this Chapter, ')"""
    m = re.search(r"[\"“”‘'`]", text or "")
    return (text or "")[: m.start()] if m else ""


# --- references -------------------------------------------------------------------------------------------------------
# "section 4", "sections 4, 8 and 9", "sections 10 to 12", "Article 25(1)", "section 9A"; the word part is
# case-free, the label's letter suffix is capitals only
# a printed suffix may stand apart ('section 295 C of the Pakistan Penal Code', '462 I'): one or two capitals, then a
# word that can only follow a label
_LAB = (r"\d{1,4}(?:\.\d{1,3}){0,2}(?:-?[A-Z]{1,3}|\s[A-Z]{1,2}(?=\s*(?:,|of\b|or\b|and\b|to\b|\)|\(|$)))?"
        r"(?:\s*\(\s*[0-9a-zA-Z]{1,5}\s*\))*")
# a footnote marker glued before a title: 'of the 2Guardian and Wards Act', 'of the 1[Pakistan] Penal Code'
_MARK = r"(?:\d{1,2}\[?|\[)?"
_REF = re.compile(r"(?<![Ss]ub-)(?<![Ss]ub)(?<![Ss]ub )\b(?i:(sections?|articles?|rules?|regulations?))\s+(" + _LAB +
                  r"(?:\s*(?:,|and|or|to|-|–|&)\s*" + _LAB + r")*)")
# 'section 16 of these rules': a subordinate instrument naming its own unit by the word 'section'
_OF_THESE = re.compile(r"\s*,?\s*(?:\(\s*[0-9a-zA-Z]{1,5}\s*\)\s*)*of\s+these\s+(?:rules|regulations|bye-?laws)\b",
                       re.I)
_SCHED = re.compile(r"\b(?:the\s+)?(?:(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|"
                    r"Twelfth)\s+)?Schedule(?:\s+([IVXL]{1,5}|\d{1,2})\b)?")
_NOT_A_LAW = r"(?!this\b|these\b|Chapter\b|Part\b|Schedule\b|Sub-?section\b|Clause\b|Article\b|Section\b)"
_EXTERNAL = re.compile(r"\s*,?\s*(?:\(\s*[0-9a-zA-Z]{1,5}\s*\)\s*)*(?:(?:of|in|under|to)\s+(?:the\s+)?"
                       r"(?:said\s+|that\s+|above\s+|aforesaid\s+|principal\s+)?" + _NOT_A_LAW + _MARK +
                       r"(?:[A-Z][\w’'.()-]*|Act\b|Ordinance\b|Code\b|Order\b|Regulation)"
                       # a title straight after the number: 'Section 62 Criminal Procedure Code'
                       r"|(?:the\s+)?(?:[A-Z][\w’'&()-]*\s+){1,6}(?:Act|Code|Ordinance)\b)")
# the law a reference names after it, as printed: 'of the Pakistan Penal Code', 'of the Contract Act, 1872',
# 'of the said Act', 'of the Act'
_LAW_AFTER = re.compile(r"\s*,?\s*(?:\(\s*[0-9a-zA-Z]{1,5}\s*\)\s*)*(?:of|in|under|to)\s+(?:the\s+)?"
                        r"(?P<said>said\s+|that\s+|above\s+|aforesaid\s+|principal\s+)?" + _NOT_A_LAW +
                        r"(?P<law>(?:(?:" + _MARK + r"[A-Z(][\w’'&()\[\]-]*|of|and|the|for|on|in|at|against|to|&)\s+)"
                        r"{0,16}?"
                        r"(?:Act|Ordinance|Code|Order|Rules|Regulations?)\b(?:\s+of\s+(?:[A-Z][\w-]*\s*){1,3})?"
                        r"(?:,?\s*\d{4})?)"
                        r"|\s+(?:the\s+)?(?P<direct>(?:[A-Z(][\w’'&()-]*\s+){1,6}(?:Act|Code|Ordinance)\b"
                        r"(?:,?\s*\d{4})?)")
_QUAL = re.compile(r"\b(subject\s+to|notwithstanding|save\s+as|except\s+as|without\s+prejudice\s+to)\b", re.I)
# a law named earlier in the same sentence: 'In the Profession Tax Limitation Act, 1941 (XX of 1941), for section 2'
_TITLE_BEFORE = re.compile(r"\b[A-Z][A-Za-z’'&(),.\- ]{2,120}?\b(?:Act|Ordinance|Code|Order|Rules|Regulations)\b"
                           r"(?:\s+of\s+(?:[A-Z][\w-]*\s*){1,3})?,?\s*(?:\d{4}|\([IVXLC]+ of \d{4}\))")
# an amending law's section numbers name the law it amends ('In section 4, for the words ...')
AMENDING_TITLE = re.compile(r"\b(?:amendment|amending|adaptation|repealing|statute\s+reform)\b"
                            r"|\bfinance\s+(?:act|ordinance|bill)\b", re.I)
# 'rule 40 & 40A of Chapter Miscellaneous of Sales Tax (Withholding) Rules, 2007': another law, past a division name
_LAW_PAST_DIVISION = re.compile(r"\s*(?:\(\s*[0-9a-zA-Z]{1,5}\s*\)\s*)*of\s+(?:Chapter|Part|Schedule)\b[^.;:]{0,60}?"
                                r"\bof\s+(?:the\s+)?(?!this\b)(?P<law>(?:[A-Z(][\w’'&()-]*\s+){1,8}"
                                r"(?:Act|Ordinance|Code|Rules|Regulations|Order)\b(?:,?\s*\d{4})?)")
ORDINAL = {w: i for i, w in enumerate(("first second third fourth fifth sixth seventh eighth ninth tenth eleventh "
                                       "twelfth").split(), 1)}
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50}


def roman(s: str) -> int | None:
    s = (s or "").lower()
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
    edge: str                 # notwithstanding | subject_to | refers_to (docs/03b)
    external: bool            # names another law
    printed: str
    start: int = 0            # offsets of the printed words in the text read
    end: int = 0
    other_law: str | None = None   # the other law as printed: 'Pakistan Penal Code', 'the Act', 'said Act'
    word: str = "section"     # the word printed before the number: section | article | rule | regulation
    of_these: bool = False    # 'section 16 of these rules': the instrument's own unit

    @property
    def qualifies(self) -> bool:
        return self.edge != "refers_to"


_BOUNDARY = re.compile(r"[;:\n]|\.(?=\s+[A-Z(\[])")      # 'Rep. by', 'S.101' and '(XX of 1941).' mid-sentence


def _sentence_head(text: str, pos: int) -> str:
    lo = max(0, pos - 200)
    start = lo
    for m in _BOUNDARY.finditer(text, lo, pos):
        start = m.end()
    return text[start:pos]


def _edge(head: str, own_law: str | None = None) -> str:
    """the phrase nearest the reference governs it -- when nothing else is named in between ('Notwithstanding
    anything in the Code of Criminal Procedure, ... the Third Schedule': the phrase is about the Code). A law named
    in between that is the reference's own law ('notwithstanding anything in the Code of Civil Procedure, 1908,
    section 9') does not break it."""
    m = None
    for m in _QUAL.finditer(head):
        pass
    if m is None:
        return "refers_to"
    gap = head[m.end():]
    names_law = re.search(r"\b(?:Act|Code|Ordinance|Order|Rules|Regulations)\b", gap)
    own = own_law and own_law.split(",")[0].strip().lower() in gap.lower()
    # a new clause after the phrase ('Notwithstanding anything in sub-section (1), the trial of offences under
    # sections 354A ...'): the phrase governed what came before the comma
    clause = re.search(r",\s+(?:the|a|an|any|no|every|such|all|it|he|she|they|where|when|if)\b", gap, re.I)
    if len(gap) > 90 or (names_law and not own) or clause:
        return "refers_to"
    if m.group(1).lower().startswith("notwithstanding"):
        return "notwithstanding"
    # 'shall be subject to the penalties provided in sections 494 and 495 of the Pakistan Penal Code': a liability the
    # reference imposes, not which provision prevails (D-110, read in a dev conflict sample: Parsi Marriage Act s.5,
    # Special Marriage Act s.16)
    if _LIABILITY.match(gap):
        return "refers_to"
    return "subject_to"


_LIABILITY = re.compile(r"\s*(?:the\s+|such\s+|a\s+|any\s+)?(?:penalt|punishment|fine|imprisonment|liabilit|forfeiture)",
                        re.I)


def _labels(group: str) -> tuple:
    group = re.sub(r"(\d)[\s-]([A-Z]{1,3})\b", r"\1\2", group)       # '295 C' and '4-A' are '295C' and '4A'
    toks = re.findall(r"\d{1,4}(?:\.\d{1,3}){0,2}[A-Z]{0,3}|\([^)]*\)|\bto\b|[-–]", group)
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


def _unmark(s: str) -> str:
    """a printed title without its footnote markers: '2Guardian and Wards Act' -> 'Guardian and Wards Act'"""
    s = re.sub(r"(?<![\w])\d{1,2}\[|\[|\]", "", s)
    s = re.sub(r"(?<![\w])\d{1,2}(?=[A-Z])", "", s)
    return " ".join(s.split())


def _other_law(text: str, end: int, head: str) -> str | None:
    m = _LAW_AFTER.match(text, end)
    if m and m.group("direct"):
        return _unmark(m.group("direct"))
    if m:
        law = _unmark(m.group("law"))
        return (f"said {law}" if m.group("said") and law.split()[0] in ("Act", "Ordinance", "Code", "Order")
                else law)
    b = None
    for b in _TITLE_BEFORE.finditer(head):
        pass
    if not b:
        return None
    title = " ".join(b.group(0).split())
    # the title starts after the last 'the' before it: 'Nothing in this section shall affect the Evidence Act, 1872'
    cut = [m.end() for m in re.finditer(r"\b[Tt]he\s+", title)]
    title = title[cut[-1]:] if cut else title
    return re.sub(r"^(?:[a-z][\w’'-]*\s+)+", "", title) or None


def references(text: str) -> list[Reference]:
    """the units and schedules a provision's words name, in printed order"""
    text = text or ""
    out = []
    for m in _REF.finditer(text):
        word = m.group(1).lower().rstrip("s")
        if word in ("rule", "regulation"):
            labels = _labels(m.group(2))
            if (re.search(r"[A-Z][a-z]+\s+$", text[max(0, m.start() - 30):m.start()])      # 'Martial Law Regulation'
                    or all(re.fullmatch(r"(18|19|20)\d\d", x) for x in labels)):          # 'Rules 1977': a year
                continue
        head = _sentence_head(text, m.start())
        of_these = bool(_OF_THESE.match(text, m.end()))
        past = None if of_these else _LAW_PAST_DIVISION.match(text, m.end())
        ext = not of_these and (bool(past) or bool(_EXTERNAL.match(text, m.end()))
                                or bool(_TITLE_BEFORE.search(head)))
        other = (" ".join(past.group("law").split()) if past else _other_law(text, m.end(), head)) if ext else None
        out.append(Reference("unit", _labels(m.group(2)), _edge(head, other), ext, m.group(0), m.start(), m.end(),
                             other, word, of_these))
    for m in _SCHED.finditer(text):
        n = None
        if m.group(1):
            n = ORDINAL[m.group(1).lower()]
        elif m.group(2):
            n = int(m.group(2)) if m.group(2).isdigit() else roman(m.group(2))
        head = _sentence_head(text, m.start())
        ext = bool(_EXTERNAL.match(text, m.end())) or bool(_TITLE_BEFORE.search(head))
        out.append(Reference("schedule", (n,) if n else (), _edge(head), ext,
                             m.group(0), m.start(), m.end(), _other_law(text, m.end(), head) if ext else None))
    out.sort(key=lambda r: r.start)
    return _share_trailing_law(text, out)


_RUN_GAP = re.compile(r"^\s*(?:,|and|or|&|,\s*and|,\s*or)?\s*$")


def _share_trailing_law(text: str, refs: list) -> list:
    """'section 161, section 164, section 165, of the Azad Kashmir Penal Code': a run of unit references joined
    only by separators shares the law named after its last one"""
    out = list(refs)
    i = 0
    while i < len(out):
        j = i
        while (j + 1 < len(out) and out[j].kind == out[j + 1].kind == "unit"
               and _RUN_GAP.match(text[out[j].end:out[j + 1].start])):
            j += 1
        last = out[j]
        if j > i and last.external and last.other_law and _LAW_AFTER.match(text, last.end):
            for k in range(i, j):
                out[k] = replace(out[k], external=True, other_law=last.other_law)
        i = j + 1
    return out


def schedule_number(label: str, heading: str | None) -> int | None:
    """the number a schedule prints for itself: 'FIRST SCHEDULE' -> 1, 'Schedule II' -> 2, 'SCHEDULE 3' -> 3"""
    for s in (label or "", heading or ""):
        m = re.search(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)\b",
                      s, re.I)
        if m:
            return ORDINAL[m.group(1).lower()]
        m = re.search(r"schedule\s*[-–]?\s*([IVXL]{1,5}|\d{1,2})\b", s, re.I)
        if m:
            g = m.group(1)
            return int(g) if g.isdigit() else roman(g)
    return None


_TITLE_YEAR = re.compile(r"^(?P<title>.*?)(?:,?\s*(?P<year>1[89]\d\d|20\d\d))?\s*$")


def law_named(printed: str) -> tuple[str, int | None] | None:
    """('Contract Act', 1872) for 'Contract Act, 1872'; ('Pakistan Penal Code', None); None for 'the Act' / 'said
    Act' (the builder reads those as the parent law) or for words too short to be a title"""
    s = " ".join((printed or "").split())
    if not s or s.lower().startswith("said ") or s.lower() in INSTRUMENT_WORDS:
        return None
    m = _TITLE_YEAR.match(s)
    title = m.group("title").strip(" ,")
    if len(title.split()) < 2:
        return None
    return title, int(m.group("year")) if m.group("year") else None


def parent_word(printed: str | None) -> str | None:
    """the kind a subordinate instrument names its parent by -- 'the Act' / 'said Act' -> 'act', 'the Ordinance' ->
    'ordinance' -- or None. The parent must be of that kind: 'section 2 of the Ordinance' is never the parent Act."""
    s = " ".join((printed or "").split()).lower()
    return {"act": "act", "said act": "act", "principal act": "act", "ordinance": "ordinance",
            "said ordinance": "ordinance", "order": "order", "said order": "order"}.get(s)
