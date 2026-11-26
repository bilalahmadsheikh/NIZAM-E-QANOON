"""Pure rules for what a judgment's words cite (docs/PRECEDENT-MODEL.md §4, D-119). No database.

- **`statute_citations(text)`:** the provisions a paragraph names, by the one citation grammar
  (nizam.storage.citations, shared with retrieval), each with the role the words around it give it.
- **`case_citations(text)`:** the cases a paragraph cites, as reporter references ("PLD 2016 SC 1", "2019 SCMR
  1234") and as case numbers ("Civil Appeal No. 123 of 2015"). A reporter reference is an identifier only: no
  reporter prose is read or kept (D-120).

Role, from the words around the citation:
- `charge`: "offence under section ...", "convicted under", "registered under", "u/s", "FIR ... under".
- `challenged`: "ultra vires", "unconstitutional", "void", "repugnant", "struck down", near the citation.
- `interpreted`: "interpret", "meaning of", "construed", "connotation", "scope of", near the citation.
- `cited`: everything else.

`quoted` is decided by the linker, which holds the version text: a quotation printed after the citation that is
found in the provision's own words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from nizam.storage import citations as C

_CHARGE_BEFORE = re.compile(r"(?i)(?:offen[cs]es?|charged|convicted|registered|booked|punishable|accused|F\.?\s*I\.?\s*R"
                            r"\.?[^.;]{0,80}?)\s*(?:under|u/s|u/ss)\s*$|\bu/s{1,2}\.?\s*$")
_CHALLENGE = re.compile(r"(?i)\bultra\s+vires\b|\bunconstitutional\b|\bvoid\b|\brepugnant\b|\bstruck\s+down\b|"
                        r"\bdeclared\s+(?:to\s+be\s+)?(?:invalid|without\s+lawful\s+authority)\b")
_INTERPRET = re.compile(r"(?i)\binterpret\w*\b|\bmeaning\s+of\b|\bconstru(?:e|ed|ction)\b|\bconnotation\b|"
                        r"\bscope\s+of\b|\bpurport\s+of\b")

_SERIES = (r"SCMR|PLD|PLC(?:\s*\(C\.?S\.?\))?|PTD|CLC|YLR|MLD|P\s*Cr\.?\s*L\.?\s*J|PCrLJ|CLD|PLJ|SCR|GBLR|NLR|"
           r"YLR|PSC|MLD|KLR|SBLR|CLR|"
           # the courts' own neutral citations (D-162): the Supreme Court's '2022 SCP 313', the Lahore High Court's
           # '2015 LHC 3623', the Islamabad High Court's '2020 IHC 146'
           r"SCP|LHC|IHC")
# "2019 SCMR 1234", "2016 PCr.LJ 77", "1999 YLR 2200 [Lahore]"
_REP_YEAR_FIRST = re.compile(r"\b((?:19|20)\d{2})\s+(" + _SERIES + r")\s+(\d{1,5})\b(?:\s*\[\s*([A-Za-z.() ]{2,25}?)\s*\])?")
# "PLD 2016 SC 1", "PLD 1966 SC 717", "PLD 2013 Lahore 45"
_REP_PLD = re.compile(r"\b(PLD|PLJ|SCR|CLC|NLR)\s+((?:19|20)\d{2})\s+(SC|S\.C\.|FSC|Lahore|Lah\.?|Karachi|Kar\.?|"
                      r"Peshawar|Pesh\.?|Quetta|Islamabad|Isl\.?|Supreme\s+Court|SC\s*\(AJ&K\)|Azad\s+J\s*&\s*K|"
                      r"Federal\s+Shariat\s+Court|Sindh|Balochistan|Baluchistan)\s+(\d{1,5})\b")
_CASE_NO = re.compile(r"\b(Civil\s+Appeals?|Criminal\s+Appeals?|Civil\s+Petitions?(?:\s+for\s+leave\s+to\s+appeal)?|"
                      r"Criminal\s+Petitions?(?:\s+for\s+leave\s+to\s+appeal)?|Jail\s+Petitions?|"
                      r"Constitution(?:al)?\s+Petitions?|Civil\s+Review\s+Petitions?|Criminal\s+Review\s+Petitions?|"
                      r"Suo\s+Mot[uo]\s+Case|Human\s+Rights\s+Case)\s+Nos?\.?\s*(\d{1,6}(?:-[A-Z])?)\s*(?:of|/)\s*"
                      r"((?:19|20)\d{2})\b", re.I)


@dataclass
class StatuteCitation:
    start: int
    end: int
    raw: str
    label: str
    subs: list[str]
    law: str | None          # an alias key or the title as printed
    role: str
    named: str | None = None  # a printed title naming no law: 'kind:<word>' or 'other' (citations.Citation.named)


@dataclass
class CaseCitation:
    start: int
    end: int
    raw: str
    series: str | None
    year: int | None
    court: str | None
    page: int | None
    case_type: str | None
    case_number: str | None
    case_year: int | None


def _words(t: str, limit: int = 400) -> list[str]:
    return re.findall(r"[a-z]+", (t or "").lower())[:limit]


# words every penal or procedural section prints, which say nothing about WHICH provision it is
_BOILERPLATE = set("""whoever shall punished punishable imprisonment either description term which extend years year
with fine both such person persons section sections under this that code ordinance any other than shall been have
being when where there their them they from into upon said same been were will would also only made make case
provided provision provisions subject clause clauses subsection article articles order rules rule hereinafter
mentioned following words mean means include includes including omitted substituted inserted added""".split())


def _content(head: str, text: str, limit: int = 80) -> set[str]:
    words = re.findall(r"[a-z]+", ((head or "") + " " + (text or "")).lower())[: limit + 20]
    return {w[:6] for w in words if len(w) >= 4 and w not in _BOILERPLATE}


def same_provision(head_a: str, head_b: str, text_a: str, text_b: str) -> bool:
    """Whether a unit in one copy of a law is the same provision as the like-numbered unit in another copy (D-136):
    the content words of heading and opening text overlap (shared stems over the smaller set >= .5, boilerplate such
    as 'whoever ... shall be punished with imprisonment' aside). A province's amended words keep the provision
    ('Punishment for rape' and 'Punishment of rape'; s.509 before and after its 2016 substitution, both about
    insulting a woman's modesty), but a different provision under the same number does not: Punjab's copy of the PPC
    prints a prize-bond offence as s.489-F, which shares nothing with the federal s.489-F's cheque dishonour. A unit
    with no words on either side (an omitted section) is never linked."""
    a, b = _content(head_a, text_a), _content(head_b, text_b)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.5


def may_inherit(named: str | None, last_law: str, year: str | None = None) -> bool:
    """Whether a citation that names no law takes the law its judgment last named (0121): a bare citation does
    ('section 497(2)'); one naming only a kind of law does when that law is of the kind ('section 3 of the Ordinance'
    after the NAB Ordinance, not after the PC Act), and, when it prints a year, of that year; one naming something
    that is not a law never does ('section 25 of the Hisba Bill', D-134)."""
    if named is None:
        return True
    if named == "other":
        return False
    if C.law_kind(last_law) != named.split(":", 1)[1]:
        return False
    return year is None or year in C._YEAR.findall(last_law)


# A printed name that refers back to a law already named: 'the Act.', 'the said Ordinance of 1979', 'the same Code'.
# 'the amending Act', 'the principal Act', 'the repealed Ordinance' point elsewhere and never inherit (D-135).
_BACK_REFERENCE = re.compile(r"^\W*(?:the\s+)?(?:said\s+|same\s+|present\s+|above\s+|aforesaid\s+)?"
                             r"(act|ordinance|order|code|rules?|regulations?)\W*(?:of\s+)?((?:18|19|20)\d{2})?\W*$",
                             re.I)


def back_reference(law: str | None) -> tuple[str, str | None] | None:
    """('kind:<word>', year or None) when a printed law name only refers back to a law named earlier, else None."""
    m = _BACK_REFERENCE.match(law or "")
    if not m:
        return None
    return f"kind:{C.law_kind(m.group(1))}", m.group(2)


# ------------------------------------------------------------------ a judgment's own short forms (D-164)
# A judgment names a law in full once and defines its short form: 'the Financial Institutions (Recovery of Finances)
# Ordinance, 2001 ("the 2001 Ordinance")', '... Act, 2017 (hereinafter "the 2017 Act")'. Its later 'section 19 of the
# 2001 Ordinance' means that law -- in this judgment only; the same year is another law in the next one.
_KINDS = r"(Act|Ordinance|Order|Code|Rules|Regulations|Constitution)"
_DEFINES = re.compile(r"\(\s*(?:hereinafter\s+(?:referred\s+to\s+as\s+|called\s+|to\s+be\s+referred\s+(?:to\s+)?as\s+)?)?"
                      r"[\"“‘']\s*(?:the\s+)?((?:18|19|20)\d{2})\s+" + _KINDS + r"\s*[\"”’']\s*\)", re.I)
_NAME_WORD = r"(?:[A-Z][\w&’'.,\-]*|\([^()]{1,80}\)|of|and|the|for|in|on|to|&)"   # 'Generation, Transmission'
_FULL_NAME = re.compile(r"((?:" + _NAME_WORD + r"\s+){1,16}?" + _KINDS + r"\b[,\s]*(?:No\.?\s*[IVXLC\d]+\s+of\s+)?"
                        r"((?:18|19|20)\d{2})\)?)\s*,?\s*$")


_OPENERS = {"the", "under", "in", "by", "as", "per", "of", "with", "from", "that", "this", "since", "whereas", "while",
            "where", "according", "to", "and", "for", "on", "vide", "namely", "i.e", "viz", "also", "see", "is", "are",
            "was", "were", "be", "has", "have", "had", "which", "who", "it", "its", "a", "an"}


def defined_short_forms(texts) -> dict[tuple[str, str], str]:
    """{(year, kind): the full law name} for the short forms a judgment defines; a short form defined for two
    different laws in one judgment is dropped, never chosen between"""
    out: dict[tuple[str, str], str] = {}
    clash: set = set()
    for t in texts:
        for m in _DEFINES.finditer(t or ""):
            before = t[max(0, m.start() - 240):m.start()]
            n = _FULL_NAME.search(before)
            if not n:
                continue
            words = " ".join(n.group(1).split()).split(" ")
            while words and words[0].lower().strip(",.") in _OPENERS:
                words = words[1:]                           # 'Under the Financial Institutions ...' -> 'Financial ...'
            name = " ".join(words)
            year, kind = m.group(1), m.group(2).lower()
            if n.group(3) != year or n.group(2).lower() != kind:
                continue                                    # the name before is not the law the short form names
            key = (year, kind)
            if key in out and C._norm_title(out[key]) != C._norm_title(name):
                clash.add(key)
            out.setdefault(key, name)
    return {k: v for k, v in out.items() if k not in clash}


_KIND_AFTER = re.compile(r"\s*" + _KINDS + r"\b", re.I)


def short_form_of(law: str | None, after: str) -> tuple[str, str] | None:
    """(year, kind) when a citation printed only a year as its law ('of the 2001 Ordinance': the grammar reads the
    law as '2001') and the kind follows it in the text"""
    if not law or not re.fullmatch(r"(?:the\s+)?((?:18|19|20)\d{2})", law.strip(), re.I):
        return None
    m = _KIND_AFTER.match(after or "")
    return (re.search(r"\d{4}", law).group(0), m.group(1).lower()) if m else None


# the one reading that needs no definition: Pakistan's Constitution is the only 1973 Constitution a court here means
FIXED_SHORT_FORMS = {("1973", "constitution"): "Constitution of the Islamic Republic of Pakistan"}


def statute_citations(text: str) -> list[StatuteCitation]:
    out = []
    for cit in C.find(text):
        start, end = cit.start, cit.end
        if start < 0 or text[start:end] != cit.raw:
            continue
        out.append(StatuteCitation(start, end, cit.raw, cit.label, cit.subs, cit.law, role_of(text, start, end),
                                   cit.named))
    out.sort(key=lambda c: c.start)
    return out


_SENTENCE_END = re.compile(r"[.;](?=\s+[A-Z(\[“\"])")   # 'S.302' and 'Cr.P.C.' mid-sentence do not end one


def role_of(text: str, start: int, end: int) -> str:
    """The role the citation's own sentence gives it; a neighbouring sentence's words never decide it."""
    s = 0
    for m in _SENTENCE_END.finditer(text, 0, start):
        s = m.end()
    m = _SENTENCE_END.search(text, end)
    e = m.start() + 1 if m else len(text)
    before = text[max(s, start - 120):start]
    near = text[max(s, start - 150):min(e, end + 150)]
    if _CHARGE_BEFORE.search(before):
        return "charge"
    if _CHALLENGE.search(near):
        return "challenged"
    if _INTERPRET.search(near):
        return "interpreted"
    return "cited"


def quotation_after(text: str, end: int, min_len: int = 60) -> str | None:
    """A quotation printed right after a citation ('section 497 ... reads: "..."'), when there is one."""
    tail = text[end:end + 2500]
    m = re.match(r"[^\"“”]{0,120}?(?:reads?|provides?|states?|runs?|is\s+as\s+under|as\s+follows|namely)?\s*[:,-]*\s*"
                 r"[\"“]([^\"”]{%d,2000})[\"”]" % min_len, tail, re.I)
    return m.group(1) if m else None


def _series(s: str) -> str:
    s = re.sub(r"[\s.]", "", s).upper()
    return {"PCRLJ": "PCrLJ"}.get(s, s)


_SC_COURT = {"sc", "supremecourt"}


def fold_reporter_court(court: str | None) -> str:
    """A reporter citation's court as the law-report index keys it (D-150): '' when none is printed, 'SC' for the
    Supreme Court however printed ('SC', 'S.C.', 'Supreme Court'), otherwise its letters folded ('SC (AJ&K)' stays
    apart from 'SC' as 'scajk')."""
    k = re.sub(r"[^a-z0-9]+", "", (court or "").lower())
    return "SC" if k in _SC_COURT else k


def reporter_key(c: CaseCitation) -> tuple[str, int, str, int] | None:
    """(series, year, folded court, page) of a reporter citation, or None for a case-number citation."""
    if not (c.series and c.year and c.page):
        return None
    return c.series, c.year, fold_reporter_court(c.court), c.page


def case_citations(text: str) -> list[CaseCitation]:
    out: list[CaseCitation] = []
    taken: list[tuple[int, int]] = []

    def free(a, b):
        return not any(x < b and a < y for x, y in taken)

    for m in _REP_PLD.finditer(text):
        if free(m.start(), m.end()):
            taken.append((m.start(), m.end()))
            out.append(CaseCitation(m.start(), m.end(), m.group(0), _series(m.group(1)), int(m.group(2)),
                                    re.sub(r"\s+", " ", m.group(3)).strip("."), int(m.group(4)), None, None, None))
    for m in _REP_YEAR_FIRST.finditer(text):
        if free(m.start(), m.end()):
            taken.append((m.start(), m.end()))
            out.append(CaseCitation(m.start(), m.end(), m.group(0), _series(m.group(2)), int(m.group(1)),
                                    (m.group(4) or None), int(m.group(3)), None, None, None))
    for m in _CASE_NO.finditer(text):
        if free(m.start(), m.end()):
            taken.append((m.start(), m.end()))
            out.append(CaseCitation(m.start(), m.end(), m.group(0), None, None, None, None,
                                    " ".join(m.group(1).split()).lower(), m.group(2).upper(), int(m.group(3))))
    out.sort(key=lambda c: c.start)
    return out
