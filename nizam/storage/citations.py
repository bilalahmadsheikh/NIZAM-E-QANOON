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


def _norm_title(t: str) -> str:
    t = re.sub(r"[^a-z0-9]+", " ", (t or "").lower())
    return " ".join(w for w in t.split() if w not in ("the", "act", "ordinance", "no"))


def _alias_key(s: str) -> str | None:
    k = re.sub(r"\s+", "", s or "").lower().rstrip(".")
    k = {"p.p.c": "ppc", "crp.c": "crpc", "cr.pc": "crpc", "cr.p.c": "cr.p.c", "c.p.c": "c.p.c"}.get(k, k)
    return k if k in ALIASES else None


def _title_law(title: str) -> str | None:
    """the law a captured title names: an alias key, the title words, or None when it is not a law's title"""
    words = title.replace(",", " , ").split()
    while words and (words[-1].lower() in _SMALL or words[-1] == ","):
        words.pop()
    while words and words[0].lower() in _SMALL:
        words.pop(0)
    t = " ".join(words).replace(" , ", ", ").strip(" ,")
    if not t or not (_TYPE.search(t) or re.search(r"\d{4}$", t)):
        return None
    if not _TYPE.sub("", t).strip(" ,"):          # 'the Act', 'the Ordinance': which one depends on context
        return None
    return _ALIAS_WORDS.get(re.sub(r"[,\s]*\d{4}$", "", t).lower().strip(" ,"), None) or t


def find(text: str) -> list[Citation]:
    out: list[Citation] = []
    seen = set()

    def add(m, law):
        # a CPC Order or Rule number is not a section ('Order 39 CPC', 'O. 39 r. 1'): a different numbering that
        # this grammar does not resolve, so it is left to the lexical search rather than misread
        if re.search(r"(?:\border|\brule|\bO\.|\br\.)\s*$", (text or "")[:m.start()], re.I):
            return
        span = (m.start(), m.end())
        if any(a <= span[0] < b for a, b in seen):
            return
        seen.add(span)
        label = re.sub(r"\s+", " ", m.group("label")).strip()
        subs = re.findall(r"\(\s*([0-9A-Za-z]{1,4})\s*\)", m.group("subs") or "")
        raw = m.group(0).strip()
        lead = len(m.group(0)) - len(m.group(0).lstrip())
        out.append(Citation(raw, label, subs, law, start=m.start() + lead, end=m.start() + lead + len(raw)))

    for m in _P_FULL.finditer(text or ""):
        alias = m.group("alias")
        title = m.group("title")
        if alias:
            law = _alias_key(alias)
        elif m.group("const"):
            law = "constitution"
        elif title:
            law = _title_law(title)
        else:
            law = None
        add(m, law)
    for rx in (_P_LABEL_ALIAS, _P_ALIAS_LABEL):
        for m in rx.finditer(text or ""):
            add(m, _alias_key(m.group("alias")))
    return out


def resolve(session, cit: Citation) -> Citation:
    """fill resolved_unit / resolved_law, or unresolved with the reason; database identifiers only.

    The law named is the top match among SERVED laws -- federal before a territory's same-titled copy, then the most
    relied-on (D-075). The label is looked up in THAT law and in its same-titled copies only (the asked territory's
    reprint of a federal Act, or the provincial law a federal copy mirrors); the first copy holding the label is the
    resolution and the others are its alternates. A label missing from every copy is an unresolved citation, never a
    hop to a different law (a fall-through once resolved 'section 96 of the Code of Civil Procedure' in the CrPC,
    18 Nov 2026). Labels are tried as written and in their other printed spellings ('17-A', '17A')."""
    if not cit.law:
        cit.unresolved = "no law named (e.g. 'Article 199' alone): not guessed"
        return cit
    if cit.law in ALIASES:
        words, juris = ALIASES[cit.law]
    else:
        words, juris = cit.law, None
        if _KIND_ONLY.match(words):
            # 'section 4 of the Act.', 'the Act, 2013', 'the Amending Act': a kind of law, not a name (D-127)
            cit.unresolved = f"no law named ({words!r} names only a kind of law): not guessed"
            return cit
    wants_amendment = "amend" in words.lower()
    year = (_YEAR.findall(words) or [None])[-1]

    def lookup(w):
        # a year printed with the name must be the year in the law's title, when the title prints one (D-127)
        return [x for x in session.instruments_titled(w, 10, juris)
                if (wants_amendment or not re.search(r"amend", x[1], re.I))
                and (year is None or not _YEAR.findall(x[1]) or year in _YEAR.findall(x[1]))]
    laws = lookup(words)
    if not laws and year:                                            # a reprint whose title drops the year
        laws = lookup(re.sub(r"[,\s]*(?:of\s+)?\d{4}", "", words).strip(" ,"))
    cit.candidates = [t for _i, t, _r in laws[:3]]
    if not laws:
        cit.unresolved = f"no served law titled like {words!r}"
        return cit
    key = _norm_title(laws[0][1])
    same = [x for x in laws if _norm_title(x[1]) == key]        # copies of the one law, in preference order
    found = []
    for oid, otitle, _r in same:
        ounits = _label_units(session, cit.label, oid)
        if ounits:
            found.append((otitle, session.child_by_label(ounits[0], cit.subs) if cit.subs else ounits[0]))
    if not found:
        cit.unresolved = f"{laws[0][1]!r} has no unit labelled {cit.label!r}"
        return cit
    (cit.resolved_law, cit.resolved_unit), rest = found[0], found[1:]
    cit.alternate_laws = [t for t, _u in rest]
    cit.alternates = [u for _t, u in rest]
    return cit


def _label_units(session, label: str, instrument_id: str):
    """the label as written, then its other printed spellings: '17-A' / '17A' / '17 A'"""
    m = re.fullmatch(r"(\d+)\s*-?\s*([A-Z]{1,3})", label.strip(), re.I)
    variants = [label] + ([f"{m.group(1)}{m.group(2)}", f"{m.group(1)}-{m.group(2)}"] if m else [])
    for v in dict.fromkeys(variants):
        units = session.label_units(v, [instrument_id])
        if units:
            return units
    return []
