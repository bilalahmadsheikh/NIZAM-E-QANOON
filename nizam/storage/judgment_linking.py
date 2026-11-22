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
           r"YLR|PSC|MLD|KLR|SBLR|CLR")
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


def statute_citations(text: str) -> list[StatuteCitation]:
    out = []
    for cit in C.find(text):
        start, end = cit.start, cit.end
        if start < 0 or text[start:end] != cit.raw:
            continue
        out.append(StatuteCitation(start, end, cit.raw, cit.label, cit.subs, cit.law, role_of(text, start, end)))
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
