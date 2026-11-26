"""Citations in a question -> the provision they name, from the database only (D-097; docs/04 R0 citation grammar).

"s. 302 PPC", "section 15 of the Punjab Rented Premises Act, 2009", "302 PPC", "PPC 302", "Article 199 of the
Constitution", "s. 497(5) CrPC". A recognised citation is RESOLVED, never generated (INV-1): the law it names is found
by its recorded title, the unit by its recorded label, and every identifier comes back from the database. When the
law named cannot be found, or no law is named ('Article 199' alone), the citation is returned UNRESOLVED with the
reason -- docs/04 R0's "typed ambiguity" -- and the question still goes to the lexical search; nothing is guessed.

Aliases are the short names practitioners use for the principal codes, mapped to words their recorded titles carry and
the jurisdiction they belong to. A title match that is an amending Act ('... (Amendment) Act') is skipped unless the
citation itself names an amendment, and among the rest the law the corpus relies on most is taken (law_citation_count,
D-075): the Pakistan Penal Code itself, not one of its West Pakistan amendments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# alias -> (title words, jurisdictions)
ALIASES: dict[str, tuple[str, tuple[str, ...]]] = {
    "ppc": ("Pakistan Penal Code", ("fed",)),
    "crpc": ("Code of Criminal Procedure", ("fed",)),
    "cr.p.c": ("Code of Criminal Procedure", ("fed",)),
    "cpc": ("Code of Civil Procedure", ("fed",)),
    "c.p.c": ("Code of Civil Procedure", ("fed",)),
    "qso": ("Qanun-e-Shahadat", ("fed",)),
    "constitution": ("Constitution Islamic Republic Pakistan", ("fed",)),
    "mflo": ("Muslim Family Laws Ordinance", ("fed",)),
    "ata": ("Anti-terrorism Act", ("fed",)),
    "cnsa": ("Control of Narcotic Substances", ("fed",)),
    "nao": ("National Accountability Ordinance", ("fed",)),
}
_ALIAS_WORDS = {"pakistan penal code": "ppc", "penal code": "ppc", "criminal procedure code": "crpc",
                "code of criminal procedure": "crpc", "civil procedure code": "cpc", "code of civil procedure": "cpc",
                "qanun-e-shahadat": "qso", "qanun e shahadat": "qso"}

_UNIT = r"(?<![A-Za-z])(?P<unit>(?i:ss?|secs?|sections?|arts?|articles?))\.?\s*"   # not the 's.' of 'Rs.'
# a label is digits with an optional letter suffix, glued ('337A', '462-I') or after one space when a lone capital
# then ends the token ('462 I.'); it never swallows the next word ('302 PPC' is label 302)
_LABEL = r"(?P<label>\d{1,4}(?:-?[A-Z]{1,3}(?![A-Za-z])|\s[A-Z](?![A-Za-z]))?)"
_SUBS = r"(?P<subs>(?:\s*\(\s*[0-9A-Za-z]{1,4}\s*\))*)"
_ALIAS = r"(?P<alias>(?i:PPC|P\.P\.C\.?|CrPC|Cr\.?\s?P\.?\s?C\.?|CPC|C\.P\.C\.?|QSO|MFLO|ATA|CNSA|NAO))"
# A law's title: the GREEDY run of title tokens after 'of (the)' -- capitalised words (curly or straight apostrophes),
# parenthesised phrases, and the small words titles use ('of', 'and', 'to' ...), optionally closed by ', <year>'.
# Validated in find(): it must hold a type word or end with a year, and trailing small words are trimmed. A lazy
# pattern once captured 'the Code' from 'the Code of Civil Procedure, 1908' and resolved it to the CrPC (18 Nov 2026).
_TOKEN = (r"(?:\([^()]{1,80}\)|[A-Z][\w'\u2019&.-]*|of|the|and|for|in|on|to|against|at|by|from|with|"
          r"relating|regarding)")
_TITLE = r"(?P<title>" + _TOKEN + r"(?:(?:,\s*(?=[A-Z(])|\s+)" + _TOKEN + r")*(?:,?\s*\d{4})?)"
_TYPE = re.compile(r"\b(?:Act|Ordinance|Order|Code|Constitution|Regulations?|Rules|Shahadat)\b", re.I)
# a law named only by its kind ('the Act.', 'Act, 2013', 'the Amending Act', 'the said Ordinance of 1979'): no name
_KIND_ONLY = re.compile(r"^\W*(?:the\s+)?(?:said\s+|same\s+|present\s+|above\s+|aforesaid\s+|amending\s+|principal\s+|"
                        r"parent\s+|new\s+|old\s+|repealed\s+)?(?:act|ordinance|order|code|rules?|regulations?|law|"
                        r"statute|enactment)s?\W*(?:of\s+)?(?:(?:18|19|20)\d{2})?\W*$", re.I)
_YEAR = re.compile(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)")
# A title ends at a sentence's end: a type word or a year, its full stop, then the next sentence's capital ('section 3
# of the Limitation Act. It ...'). The stop is kept, so 'of the Act.' stays a kind of law (D-127). Dotted
# abbreviations inside a title ('N.-W.F.P. Pre-emption Act') carry no type word before their stops (D-134).
_SENTENCE_CUT = re.compile(r"(?:\b[A-Za-z][a-z]{3,}|\bAct|(?<!\d)(?:18|19|20)\d{2})\.(?=\s+[A-Z“\"(\[])")
# ... and before the next citation's unit word: 'the General Clauses Act and Article 4', 'the Limitation Act, Section 5'
_NEXT_UNIT = re.compile(r"(?:,|\s+and)\s+(?:Articles?|Sections?|Rules?)\b")
# a sub-clause the grammar swallowed ahead of the name: 'Article 8(1) and (2) of the Constitution'
_LEADING_PARENS = re.compile(r"^(?:\([^()]*\)\s*(?:,|and|or|to)?\s*)+(?:of\s+)?(?:the\s+)?", re.I)
# trailing parentheses after a title are its act number or a short name, not its words: '(V of 1908)',
# '(Act XLV of 1860)', '(Cr.P.C.)', '("FIO")', '(hereinafter referred to as ...)' (D-134)
_TRAILING_PARENS = re.compile(r"(?:\s*\([^()]*\))+\s*$")
_SMALL = {"of", "the", "and", "for", "in", "on", "to", "against", "at", "by", "from", "with", "relating", "regarding"}

_P_FULL = re.compile(_UNIT + _LABEL + _SUBS + r"(?:\s*,?\s*(?:(?i:of)\s+(?:(?i:the)\s+)?)?(?:(?P<const>(?i:Constitution))\b|"
                     + _ALIAS + r"(?![\w])|" + _TITLE + r"))?")
_P_LABEL_ALIAS = re.compile(r"(?<![\w.])" + _LABEL + _SUBS + r"\s+" + _ALIAS + r"(?![\w])")
_P_ALIAS_LABEL = re.compile(r"(?<![\w])" + _ALIAS + r"\s+(?:(?i:s|sec|section)\.?\s*)?" + _LABEL + _SUBS)


@dataclass
class Citation:
    raw: str
    label: str
    subs: list[str]
    law: str | None                 # an alias key, or the title words as written
    resolved_unit: object | None = None        # storage Unit, once resolved
    resolved_law: str | None = None            # its recorded title
    unresolved: str | None = None              # why not, when not (typed ambiguity)
    candidates: list[str] = field(default_factory=list)
    # the same unit in a same-titled law of the asked territory (a provincial copy of a federal Act, or a provincial
    # law the federal copy mirrors): which one governs there is a matter of legislative history the catalogue does
    # not record, so both are returned, federal first -- typed ambiguity, never a guess (D-097)
    alternates: list = field(default_factory=list)
    alternate_laws: list = field(default_factory=list)
    start: int = -1                 # where `raw` is printed in the text given to find()
    end: int = -1
    via_alias: str | None = None    # the reviewed law_alias key it resolved through (D-134), when it did
    # when a title was printed but names no law: 'kind:ordinance' ('of the Ordinance') or 'other' ('of the Hisba
    # Bill'); None when no title was printed. The linker inherits a law only for a bare citation or a matching kind.
    named: str | None = None


def _norm_title(t: str) -> str:
    t = re.sub(r"[^a-z0-9]+", " ", (t or "").lower())
    return " ".join(w for w in t.split() if w not in ("the", "act", "ordinance", "no"))


def _alias_key(s: str) -> str | None:
    k = re.sub(r"\s+", "", s or "").lower().rstrip(".")
    k = {"p.p.c": "ppc", "crp.c": "crpc", "cr.pc": "crpc", "cr.p.c": "cr.p.c", "c.p.c": "c.p.c"}.get(k, k)
    return k if k in ALIASES else None


_CODE_KIND = {"ppc": "code", "crpc": "code", "cr.p.c": "code", "cpc": "code", "c.p.c": "code", "qso": "order",
              "constitution": "constitution", "mflo": "ordinance", "ata": "act", "cnsa": "act", "nao": "ordinance"}


def _kind_word(w: str) -> str:
    w = w.lower()
    return {"shahadat": "order", "regulations": "regulation", "rules": "rule"}.get(w, w)


def law_kind(law: str | None) -> str | None:
    """The kind of law a name is ('act', 'ordinance', 'order', 'code' ...): from a code alias, else the last kind word
    the name prints ('Qanoon-e-Shahadat Order, 1984' is an order). Used to keep 'of the Ordinance' from inheriting an
    Act (D-134)."""
    if not law:
        return None
    if law in _CODE_KIND:
        return _CODE_KIND[law]
    words = _TYPE.findall(law)
    return _kind_word(words[-1]) if words else None


def _title_named(title: str) -> str | None:
    """What a captured title that names no law names: 'kind:<word>' when it is only a kind of law, 'other' when it
    names something else (a Bill, a report, a person), None when nothing but small words was captured."""
    words = [w for w in re.findall(r"[A-Za-z][\w'-]*", title) if w.lower() not in _SMALL]
    if not words:
        return None
    kinds = [w for w in words if _TYPE.fullmatch(w)]
    return f"kind:{_kind_word(kinds[-1])}" if kinds and len(kinds) == len(words) else "other"


def law_key(law: str | None) -> str:
    """The key a printed law name is reviewed and aliased under (law_alias, D-134): case, punctuation, hyphen spacing
    and a leading 'the' folded; the words and any year kept ('Qanoon-e- Shahadat Order, 1984' and 'Qanoon-e-Shahadat
    Order 1984' share 'qanoon e shahadat order 1984'; 'NAB Ordinance' and 'NAB Ordinance, 1999' do not)."""
    t = re.sub(r"[‘’“”'\"]", "", (law or "").lower())
    t = re.sub(r"[^a-z0-9]+", " ", t).split()
    while t and t[0] == "the":
        t.pop(0)
    return " ".join(t)


def _title_law(title: str) -> str | None:
    """the law a captured title names: an alias key, the title words, or None when it is not a law's title"""
    def trim(s):
        words = s.replace(",", " , ").split()
        while words and (words[-1].lower() in _SMALL or words[-1] == ","):
            words.pop()
        while words and words[0].lower() in _SMALL:
            words.pop(0)
        return " ".join(words).replace(" , ", ", ").strip(" ,")
    t = trim(title)
    t = trim(_LEADING_PARENS.sub("", t))
    bare = _TRAILING_PARENS.sub("", t).strip(" ,")
    if bare and bare != t:
        # the parentheses go; a year printed only inside them stays ('Contempt of Court Ordinance (Ordinance V of
        # 2003)' is the 2003 Ordinance, not the 1998 or 2004 one)
        year = _YEAR.findall(t[len(bare):])
        t = bare + (f", {year[-1]}" if year and not _YEAR.findall(bare) else "")
    if not t or not (_TYPE.search(t) or re.search(r"\d{4}$", t)):
        return None
    if t.lower().rstrip(".") == "constitution":   # 'Article 8(1) and (2) of the Constitution', as the const branch
        return "constitution"
    if not _TYPE.sub("", t).strip(" ,"):          # 'the Act', 'the Ordinance': which one depends on context
        return None
    return _ALIAS_WORDS.get(re.sub(r"[,\s]*\d{4}\.?$", "", t).lower().strip(" ,."), None) or t


def find(text: str) -> list[Citation]:
    out: list[Citation] = []
    seen = set()

    def add(m, law, end=None, named=None):
        # a CPC Order or Rule number is not a section ('Order 39 CPC', 'O. 39 r. 1'): a different numbering that
        # this grammar does not resolve, so it is left to the lexical search rather than misread
        if re.search(r"(?:\border|\brule|\bO\.|\br\.)\s*$", (text or "")[:m.start()], re.I):
            return
        end = m.end() if end is None else end
        span = (m.start(), end)
        if any(a <= span[0] < b for a, b in seen):
            return
        seen.add(span)
        label = re.sub(r"\s+", " ", m.group("label")).strip()
        subs = re.findall(r"\(\s*([0-9A-Za-z]{1,4})\s*\)", m.group("subs") or "")
        whole = text[m.start():end]
        raw = whole.strip()
        lead = len(whole) - len(whole.lstrip())
        out.append(Citation(raw, label, subs, law, start=m.start() + lead, end=m.start() + lead + len(raw),
                            named=named if law is None else None))

    pos = 0
    while True:
        m = _P_FULL.search(text or "", pos)
        if not m:
            break
        pos = max(m.end(), pos + 1)
        alias = m.group("alias")
        title = m.group("title")
        end = None
        if alias:
            law = _alias_key(alias)
        elif m.group("const"):
            law = "constitution"
        elif title:
            # the title stops at its sentence's end, or where the next citation begins (D-134)
            stops = [x.end() for x in [_SENTENCE_CUT.search(title)] if x] + \
                    [x.start() for x in [_NEXT_UNIT.search(title)] if x]
            if stops:
                title = title[:min(stops)]
                end = m.start("title") + len(title)
                pos = max(end, m.start() + 1)               # what follows the cut is read again
            law = _title_law(title)
        else:
            law = None
        add(m, law, end, _title_named(title) if (title and law is None) else None)
    for rx in (_P_LABEL_ALIAS, _P_ALIAS_LABEL):
        for m in rx.finditer(text or ""):
            add(m, _alias_key(m.group("alias")))
    return out


_COPY_KINDS = {"act", "ordinance", "order", "code", "rules", "rule", "regulations", "regulation"}

# D-149: how well a law's title fits a name printed without an alias. Province prefixes a territory's copy carries
# ('West Pakistan Land-Revenue Act', 'Sindh Buildings Control Ordinance') and one-word brackets (an acronym '(ATA)',
# '(Punjab)') are set aside; a bracket of two or more words is the law's own words ('School Bags (Limitation of
# Weight) Act'), so it never lends them to another law's name.
_PLACE_PREFIXES = (("west", "pakistan"), ("north", "west", "frontier", "province"), ("khyber", "pakhtunkhwa"),
                   ("islamabad", "capital", "territory"), ("azad", "jammu", "and", "kashmir"), ("gilgit", "baltistan"),
                   ("punjab",), ("sindh",), ("sind",), ("balochistan",), ("baluchistan",), ("baln",), ("nwfp",),
                   ("kp",), ("ajk",), ("ict",), ("gb",))
_PLACE_WORDS = {w for p in _PLACE_PREFIXES for w in p if len(p) == 1}


def _fit_words(t: str, acronyms: bool = True) -> list[str]:
    """A title or printed name as fit words: brackets of two or more words dropped (a one-word bracket kept when
    `acronyms`, unless it is a place), case, punctuation, hyphens, years, 'the' and 'no' folded, a plural 's' folded,
    a leading place prefix dropped."""
    t = re.sub(r"\(([^()]*)\)", lambda m: " " if not acronyms or len(m.group(1).split()) > 1
               or m.group(1).strip().lower() in _PLACE_WORDS else f" {m.group(1)} ", (t or "").lower())
    w = [x for x in re.sub(r"[^a-z0-9]+", " ", t).split()
         if x not in ("the", "no", "codified") and not _YEAR.fullmatch(x)]
    w = [x[:-1] if len(x) > 3 and x.endswith("s") and not x.endswith("ss") else x for x in w]
    for p in _PLACE_PREFIXES:
        if tuple(w[:len(p)]) == p:
            w = w[len(p):]
            break
    return w


def name_fit(printed: str, title: str) -> int:
    """How a law's title fits a printed law name (D-149), best first:
    1 the same name; 2 the name as one run within the title ('Indian Limitation Act'); 3 the name's words in order
    with others between ('Colonization of Government Lands Act' for 'Colonization Act'); 4 the words only somewhere
    (never a resolution: 'Limitation Act' is not 'School Bags (Limitation of Weight) Act', and 'Sales Tax Act' is
    rather the Sales Tax Act than 'Sindh Sales Tax on Services Act', which fits only at 3)."""
    p = _fit_words(printed)
    if not p:
        return 4

    def fit(t):
        if p == t:
            return 1
        n = len(p)
        if any(t[i:i + n] == p for i in range(len(t) - n + 1)):
            return 2
        it = iter(t)
        return 3 if all(x in it for x in p) else 4
    # a one-word bracket is an acronym the name may omit ('Anti-Terrorism Act' for 'Anti Terrorism Act (ATA)') or
    # print in place of the words it abbreviates ('PEMRA Ordinance' for 'Pakistan Electronic Media Regulatory
    # Authority Ordinance (PEMRA)', 'FIA Act' for 'Federal Investigation Agency Act (FIA)'): the best reading
    readings = [_fit_words(title), _fit_words(title, acronyms=False)]
    kinds = [x for x in readings[1] if x in _FIT_KINDS]
    for a in re.findall(r"\(\s*([A-Za-z&.]{2,12})\s*\)", title or ""):
        a = re.sub(r"[^a-z0-9]+", "", a.lower())
        if a and a in p and a not in _PLACE_WORDS:
            readings.append([a] + kinds[-1:])
    return min(fit(r) for r in readings)


_FIT_KINDS = {"act", "ordinance", "order", "code", "rule", "regulation", "constitution"}


def name_fit_any(printed: str, titles: list[str]) -> int:
    """The best fit of a printed name over a law's recorded titles (its short and its display title, D-149)."""
    return min((name_fit(printed, t) for t in titles if t), default=4)


def same_law(a: str, b: str) -> bool:
    """Whether two recorded titles name one law in two copies ('Pakistan Penal Code' and 'Pakistan Penal Code,
    1860'; 'Qanun-e-Shahadat, 1984' and 'Qanun-E-Shahadat Order, 1984'): the same words once case, punctuation,
    'the' and 'No.' are folded; a year or a kind word counts only when both titles print one (D-136). Two printed
    years that differ are two laws ('Industrial Relations Act, 2008' and '..., 2012')."""
    def parts(t):
        w = [x for x in re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).split() if x not in ("the", "no")]
        return ([x for x in w if not _YEAR.fullmatch(x) and x not in _COPY_KINDS],
                {x for x in w if x in _COPY_KINDS}, {x for x in w if _YEAR.fullmatch(x)})
    (wa, ka, ya), (wb, kb, yb) = parts(a), parts(b)
    return wa == wb and (not ka or not kb or ka == kb) and (not ya or not yb or bool(ya & yb))


def resolve(session, cit: Citation, copies_in: tuple[str, ...] | None = None) -> Citation:
    """fill resolved_unit / resolved_law, or unresolved with the reason; database identifiers only.

    `copies_in` (the judgment linker of a High Court passes its territory, D-136): a law named by a federal alias is
    also looked for in those jurisdictions, and its copy there joins the alternates after the federal resolution.
    Retrieval passes nothing and is unchanged.

    The law named is the top match among SERVED laws -- federal before a territory's same-titled copy, then the most
    relied-on (D-075). The label is looked up in THAT law and in its same-titled copies only (the asked territory's
    reprint of a federal Act, or the provincial law a federal copy mirrors); the first copy holding the label is the
    resolution and the others are its alternates. A label missing from every copy is an unresolved citation, never a
    hop to a different law (a fall-through once resolved 'section 96 of the Code of Civil Procedure' in the CrPC,
    18 Nov 2026). Labels are tried as written and in their other printed spellings ('17-A', '17A')."""
    if not cit.law:
        cit.unresolved = "no law named (e.g. 'Article 199' alone): not guessed"
        return cit
    reviewed = None if cit.law in ALIASES else session.law_alias(law_key(cit.law))
    if cit.law in ALIASES:
        words, juris = ALIASES[cit.law]
    elif reviewed:
        # a printed name a person read and tied to one law (law_alias, D-134): that law's own title is searched
        (words, juris), cit.via_alias = reviewed, law_key(cit.law)
    else:
        words, juris = cit.law, None
        if _KIND_ONLY.match(words):
            # 'section 4 of the Act.', 'the Act, 2013', 'the Amending Act': a kind of law, not a name (D-127)
            cit.unresolved = f"no law named ({words!r} names only a kind of law): not guessed"
            return cit
    # 'Article 151 of the First Schedule to the Limitation Act, 1908' names the Limitation Act: the unit is looked for
    # in its schedule (D-164)
    sched = _SCHEDULE_OF.match(words)
    if sched:
        words = sched.group(2)
    wants_amendment = "amend" in words.lower()
    year = (_YEAR.findall(words) or [None])[-1]

    printed = not (cit.law in ALIASES or reviewed)

    def lookup(w, j=juris):
        # a year printed with the name must be the year in the law's title, when the title prints one (D-127)
        got = [x for x in session.instruments_titled(w, 25 if printed else 10, j)
               if (wants_amendment or not re.search(r"amend", x[1], re.I))
               and (year is None or not _YEAR.findall(x[1]) or year in _YEAR.findall(x[1]))]
        if not printed:
            return got
        # a printed name is resolved by how well a title fits it, then by the session's order (served, the court's
        # territory, federal, reliance): 'the Limitation Act' in a Peshawar judgment is the Limitation Act 1908, not
        # KP's School Bags (Limitation of Weight) Act; a title holding the words only somewhere is no match (D-149)
        lister = getattr(session, "instrument_titles", None)     # a session that lists both titles (unit_search)
        titles = lister([x[0] for x in got]) if (got and lister) else {}
        fit = {x[0]: name_fit_any(w, titles.get(x[0]) or [x[1]]) for x in got}
        return sorted((x for x in got if fit[x[0]] < 4), key=lambda x: fit[x[0]])
    laws = lookup(words)
    if not laws and year:                                            # a reprint whose title drops the year
        laws = lookup(re.sub(r"[,\s]*(?:of\s+)?\d{4}", "", words).strip(" ,"))
    if not laws and _HYPHENED.search(words):
        # 'Cooperative Societies Act' printed, 'Co-operative Societies Act' titled: the title search reads the hyphen
        # as two words (D-164); the hyphenated spelling is the same name
        laws = lookup(_HYPHENED.sub(lambda m: _HYPHENS[m.group(0).lower()], words))
    cit.candidates = [t for _i, t, _r in laws[:3]]
    if not laws:
        cit.unresolved = f"no served law titled like {words!r}"
        return cit
    if copies_in and juris and not set(copies_in) <= set(juris):
        # a federal alias in a High Court's judgment: the territory's own copy of the law, after the federal one
        seen = {x[0] for x in laws}
        laws = laws + [x for x in lookup(words, tuple(copies_in)) if x[0] not in seen]
    same = [x for x in laws if same_law(laws[0][1], x[1])]      # copies of the one law, in preference order
    found = []
    for oid, otitle, _r in same:
        ounits = _label_units(session, cit.label, oid)
        if sched:
            # a schedule's article: a unit of any kind inside the law's marked schedule; in a law whose copy marks
            # no schedule, the label's only unit. A label the law's own sections share too ('Article 29' and s.29)
            # is never chosen between, and a marked schedule's law never falls back to a section (D-164)
            in_sched, marked = _schedule_units(session, cit.label, oid, sched.group("ord"))
            ounits = in_sched if marked else (ounits if len(ounits) == 1 else [])
        if ounits:
            found.append((otitle, session.child_by_label(ounits[0], cit.subs) if cit.subs else ounits[0]))
    if not found:
        cit.unresolved = f"{laws[0][1]!r} has no unit labelled {cit.label!r}"
        return cit
    (cit.resolved_law, cit.resolved_unit), rest = found[0], found[1:]
    cit.alternate_laws = [t for t, _u in rest]
    cit.alternates = [u for _t, u in rest]
    return cit


_SCHEDULE_OF = re.compile(r"(?i)^(?:the\s+)?(?P<ord>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|"
                          r"tenth|1st|2nd|3rd|[4-9]th)\s+schedule\s+(?:to|of|appended\s+to|annexed\s+to)\s+"
                          r"(?:the\s+)?(.+)$")
# words a judgment prints whole and a title prints hyphenated (the title search reads a hyphen as a word break)
_HYPHENS = {"cooperative": "co-operative", "preemption": "pre-emption", "coordination": "co-ordination",
            "reorganisation": "re-organisation", "reorganization": "re-organization"}
_HYPHENED = re.compile(r"(?i)\b(?:" + "|".join(_HYPHENS) + r")\b")


_ORDINAL = {"1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth", "5th": "fifth", "6th": "sixth",
            "7th": "seventh", "8th": "eighth", "9th": "ninth"}


def _schedule_units(session, label: str, instrument_id: str, ordinal: str):
    """(units labelled `label` inside the law's marked schedule of that ordinal (path '.sch_FIRST_SCHEDULE'),
    whether the law marks that schedule at all). A copy that marks its Second Schedule but keeps its First's
    articles as sections (the federal Limitation Act) does not mark the First."""
    cur = getattr(session, "cur", None)
    if cur is None:
        return [], False
    word = _ORDINAL.get(ordinal.lower(), ordinal.lower()).upper()
    pattern = rf"[.]sch_{word}(_|$)"
    folded = "".join((label or "").split()).lower()
    cur.execute("""SELECT p.id::text, p.path::text, p.instrument_id::text FROM provision p
                    WHERE p.instrument_id = %s AND p.is_active AND p.path::text ~ %s
                      AND lower(replace(p.label, ' ', '')) = %s
                    ORDER BY p.ordinal, p.id""", (instrument_id, pattern, folded))
    rows = cur.fetchall()
    if rows:
        return [_unit(*r) for r in rows], True
    cur.execute("SELECT EXISTS (SELECT 1 FROM provision WHERE instrument_id = %s AND is_active AND path::text ~ %s)",
                (instrument_id, pattern))
    return [], bool(cur.fetchone()[0])


def _unit(unit_id, path, instrument_id):
    from nizam.storage.unit_search import Unit
    return Unit(unit_id, path, instrument_id)


def _label_units(session, label: str, instrument_id: str):
    """the label as written, then its other printed spellings: '17-A' / '17A' / '17 A'"""
    m = re.fullmatch(r"(\d+)\s*-?\s*([A-Z]{1,3})", label.strip(), re.I)
    variants = [label] + ([f"{m.group(1)}{m.group(2)}", f"{m.group(1)}-{m.group(2)}"] if m else [])
    for v in dict.fromkeys(variants):
        units = session.label_units(v, [instrument_id])
        if units:
            return units
    return []
