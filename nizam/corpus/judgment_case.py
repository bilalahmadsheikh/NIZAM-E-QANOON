"""Case identity: which case a judgment decides, and how the judgments of one case relate (D-125).

Pure functions over what a judgment prints. The builder (nizam.workers.judgment_cases) writes their results.

- `case_key(court, case_type_code, number, year)`: 'SC/CA/1507/2024'. The key is built from the case as printed, so
  rebuilding never changes it and a stored reference to a case never breaks (the INV-4 rule, read for cases).
  Leading zeros are not part of a number ('No.05/2012' is case 5 of 2012).
- `read_case_line(printed, form, ...)`: the lead number this grammar reads after the case type's printed form,
  and the numbers of the same type and year printed beside it ('Civil Appeals No. 1507 and 1508 of 2024',
  'Nos. 545 to 550 of 2015', 'Nos. 11-15, 18-22 & 24/2010'). A number of another type ('and CMA No. 2382') is an
  application in the case, not another case, and is not read. Nothing is read when the list does not end in the
  lead's own year.
- `reasons_statement(paragraphs, own_date)`: the sentence in which the court says this judgment gives the reasons
  for its short order ('The above are the reasons for our short order dated 22.4.2024'; 'of even date'), and the
  short order's date as printed. A short order of another court ('vide short order dated ... the High Court
  allowed') is not a statement of this kind: the reasons must be the reasons *for* or *of* the short order.
- `copy_score(a, b)`: word 5-gram overlap of two bodies. Two judgments of one case whose bodies overlap at
  COPY_MIN are two copies of one decision.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from nizam.corpus.judgment import DATE, fold, read_date
from nizam.storage.case_key import (RANGE_MAX, CaseLine, _fold_map, case_key, norm_number,  # noqa: F401
                                    read_case_line)  # re-exported: the grammar lives in storage, so L3 reads it too (D-137)

COPY_MIN = 0.90         # word 5-gram Jaccard at which two bodies of one case are one decision (dev-read, D-125)
COPY_LEN_MIN = 0.90     # and the shorter body is at least this share of the longer


# --------------------------------------------------------------------------- cases listed in the header

# words just before a case line that make it another court's case or the case an application is made in
_NOT_DECIDED_HERE = re.compile(r"(?i)\b(?:in|against|from|passed|of\s+the\s+learned|vide|arising\s+out\s+of|"
                               r"impugned|decided\s+by|dated|"
                               # an order sheet's list of what is before the court: 'For orders on M.A. No. 1056'
                               # (Sindh, D-138) is an application in the case, not a case decided
                               r"for\s+(?:the\s+)?(?:hearing|orders?)\s+(?:of|on))\W*$")
_BELOW = re.compile(r"(?i)\b(?:in|against|from|passed|impugned|vide|arising|decided\s+by|on\s+appeal)\b")


def header_cases(header: str, forms_by_code: dict[str, list[str]], today: dt.date | None = None) -> list[tuple]:
    """[(case type code, CaseLine)] for every case line printed in a judgment's header, in printed order (D-128).

    A High Court prints the cases it decides together on separate lines ('Murder Reference No.290 of 2015 ...
    Criminal Appeal No.1112-J of 2015'). A case line preceded by 'in', 'against', 'from', 'passed', 'vide' or
    'impugned' is the court below's case, or the case an application is made in, and is not read."""
    f, idx = _fold_map(header)
    out = []
    taken: set[int] = set()
    forms = sorted(((form, code) for code, fs in forms_by_code.items() for form in fs), key=lambda x: -len(x[0]))
    for form, code in forms:
        # the number may carry a register letter before it ('C.P No. D-2606', folded 'c p no d 2606'; D-138)
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(form) + r"(?= (?:nos? )?(?:[a-z] )?\d)", f):
            raw_start = idx[m.start()]
            if raw_start in taken or _NOT_DECIDED_HERE.search(header[max(0, raw_start - 40):raw_start]):
                continue
            # inside an open parenthesis, the clause that opened it decides: '(Against the judgment ... passed by the
            # Lahore High Court in Criminal Appeal No.300-J/2013 and Murder Reference No.138/2011)'
            opened, closed = header.rfind("(", 0, raw_start), header.rfind(")", 0, raw_start)
            if opened > closed and _BELOW.search(header[opened:raw_start]):
                continue
            # 'Murder Reference', 'Capital Sentence Reference', 'Income Tax Reference': not this court's 'Reference'
            if re.search(r"(?i)\b(?:murder|sentence|tax|customs?|jail)\s*$", header[max(0, raw_start - 12):raw_start]):
                continue
            line = read_case_line(header[raw_start:raw_start + 160], [form], today)
            if line and line.lead and line.year:
                taken.update(range(raw_start, raw_start + len(line.printed)))
                out.append((raw_start, code, line))
    return [(code, line) for _s, code, line in sorted(out, key=lambda x: x[0])]


# ------------------------------------------------------------------------------------------- reasons for

_SHORT = r"short\s+o\s*r?\s*der"
_REASONS = re.compile(
    r"\b(?:detailed\s+)?(?:reasons?|judgment)\s+(?:assigned\s+)?(?:for|of|in\s+support\s+of)\s+"
    r"(?:our|the|this\s+court\W{0,2}s|such|the\s+said|the\s+aforesaid)?\s*(?:own\s+)?" + _SHORT + r"\b"
    r"(?P<after>.{0,90})", re.I | re.S)
_ANNOUNCED_THEN = re.compile(
    _SHORT + r"\s+(?:was\s+)?(?:announced|passed|delivered|pronounced|made)\s+(?:in\s+(?:open\s+)?court\s+)?"
    r"(?:on\s+)?(?:the\s+)?(?P<date>" + DATE + r")[^.]{0,30}\.\s*(?:These|The\s+following|The\s+above)\s+are\s+the\s+"
    r"(?:detailed\s+)?reasons", re.I | re.S)
_SAID = (r"(?:(?:announced|pronounced|delivered|passed|made|recorded)(?:\s+by\s+us)?"
         r"(?:\s+in\s+(?:the\s+)?(?:open\s+)?court)?\s+)")
_EVEN = re.compile(r"^\W{0,3}(?:dated\s+|of\s+|" + _SAID + r")?(?:on\s+)?(?:the\s+)?(?:(?:even|event|same)\s+date|today)\b",
                   re.I)
_DATED = re.compile(r"^\W{0,3}(?:dated|dt\.?|of|" + _SAID + r"on|" + _SAID + r"|on)?\s*(?:the\s+)?(?P<date>" + DATE
                    + r")", re.I)
_PRIOR = re.compile(_SHORT + r"\s+(?:dated|dt\.?|of|announced\s+on|delivered\s+on|passed\s+on|made\s+on)?\s*(?:the\s+)?"
                    r"(?P<date>" + DATE + r")", re.I)
# the sentence speaks of another court's or another case's short order
_OTHER = re.compile(r"\b(?:high\s+court|tribunal|learned\s+(?:single|division)\s+bench|minority)\b", re.I)
# a short order says the reasons will come: 'For reasons to be recorded later', 'for the reasons to follow separately'
_LATER = re.compile(r"\breasons?\s+(?:to\s+(?:be\s+)?(?:recorded|given|assigned|follow)|recorded\s+(?:later|separately))|"
                    r"\bdetailed\s+(?:reasons|judgment)\s+(?:to|will|shall|would)\s+follow", re.I)


@dataclass
class ReasonsStatement:
    printed: str                    # the sentence as printed (up to 300 characters)
    short_order_on: dt.date | None  # the short order's date as printed; None when it cannot be read
    date_basis: str                 # 'printed' | 'even_date' | 'paragraph' | 'not_printed'


def reasons_statement(paragraphs: list[str], own_date: dt.date | None,
                      today: dt.date | None = None) -> ReasonsStatement | None:
    """The first statement, in the paragraphs given (the opening and closing body paragraphs), that this judgment
    gives the reasons for the court's short order. `own_date` is this judgment's printed decision date, None when
    it is undated: 'of even date' then names no date."""
    for text in paragraphs:
        for m in _ANNOUNCED_THEN.finditer(text):
            return ReasonsStatement(_sentence(text, m.start(), m.end()), read_date(m.group("date"), today),
                                    "printed")
        for m in _REASONS.finditer(text):
            sentence = _sentence(text, m.start(), m.end())
            if _OTHER.search(text[m.start():m.end()]) or _quoted(text, m.start()):
                continue
            after = m.group("after")
            if _EVEN.match(after):
                return ReasonsStatement(sentence, own_date, "even_date" if own_date else "not_printed")
            d = _DATED.match(after)
            if d and read_date(d.group("date"), today):
                return ReasonsStatement(sentence, read_date(d.group("date"), today), "printed")
            # 'allowed vide our short order dated 19.06.2025. Above are the reasons of such short order'
            prior = {read_date(p.group("date"), today) for p in _PRIOR.finditer(text[:m.start()])} - {None}
            if len(prior) == 1:
                return ReasonsStatement(sentence, prior.pop(), "paragraph")
            return ReasonsStatement(sentence, None, "not_printed")
    return None


def _quoted(text: str, at: int) -> bool:
    """Whether `at` falls inside a quotation (more curly opening quotes than closing ones before it): the court
    quoting an earlier order's words is not its own statement about this judgment."""
    before = text[:at]
    return before.count("“") > before.count("”")


def announces_reasons_later(paragraphs: list[str]) -> bool:
    """Whether a judgment's own words say its reasons will follow: the mark of a short order (D-125)."""
    return any(_LATER.search(t) for t in paragraphs)


def _sentence(text: str, start: int, end: int) -> str:
    a = max(text.rfind(". ", 0, start) + 2, start - 160, 0)
    b = text.find(". ", end)
    b = len(text) if b < 0 else b + 1
    return " ".join(text[a:min(b, end + 160)].split())[:300]


# ---------------------------------------------------------------------------------------------- copies

def shingles(text: str, k: int = 5) -> set[int]:
    w = fold(text).split()
    return {hash(" ".join(w[i:i + k])) for i in range(max(0, len(w) - k + 1))}


def copy_score(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
