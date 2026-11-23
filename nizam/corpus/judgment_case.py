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
from nizam.storage.case_key import case_key, norm_number  # noqa: F401  (re-exported: the builder's one import)

RANGE_MAX = 500         # a printed range wider than this is not expanded (a misread, or a year)
COPY_MIN = 0.90         # word 5-gram Jaccard at which two bodies of one case are one decision (dev-read, D-125)
COPY_LEN_MIN = 0.90     # and the shorter body is at least this share of the longer


# ------------------------------------------------------------------------------------------- the case line

# a number and its registry suffix: '801-L', '2143-CB' (cancellation of bail), '4-RWP', '07(S)', '241 K' (D-128)
_ITEM = r"(\d{1,6})(?:\s*[-–—]\s*([A-Za-z]{1,3})(?![A-Za-z])|\(\s*([A-Za-z])\s*\)|\s([A-Z])(?![A-Za-z]))?"
# after the type's form: a form's unread tail ('Crl.P' + '.L.A.'), then 'No.' as printed ('No,', 'NO-', 'No»', 'N.')
_LEAD = re.compile(r"[\s.:#(,]*(?:[a-z]{1,2}(?:s?\.\s*|\s+)){0,3}(?:nos?|numbers?|n)?[\s.:#,»\-]*" + _ITEM, re.I)
# '/2015', 'of 2015', '-2015', '611-L 2018'; and '/15' (two digits only after a slash, as the SC registry writes)
_YEAR = re.compile(r"\s*(?:(?:of|/|-)\s*|\s)((?:19|20)\d{2})(?!\d)|\s*/\s*(\d{2})(?![\d/])", re.I)
_NEXT = re.compile(r"\s*(,|&|\band\b|\bto\b|-)\s*(?:nos?\.?\s*)?" + _ITEM, re.I)


@dataclass
class CaseLine:
    lead: str | None            # the lead number as this grammar reads it, normalised
    year: int | None            # the year printed after the list
    joined: list[str]           # the other numbers of the same type and year, normalised, in printed order
    printed: str                # the words read


def _fold_map(s: str) -> tuple[str, list[int]]:
    """fold(s), and for each folded character the index in `s` it came from."""
    out, idx, space = [], [], True
    for i, ch in enumerate(s.lower()):
        if ch.isascii() and ch.isalnum():
            out.append(ch)
            idx.append(i)
            space = False
        elif not space:
            out.append(" ")
            idx.append(i)
            space = True
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def read_case_line(printed: str, forms: list[str], today: dt.date | None = None) -> CaseLine | None:
    """Read the numbers after the longest of `forms` (folded printed forms) that opens `printed`."""
    f, idx = _fold_map(printed)
    form = next((x for x in sorted(forms, key=len, reverse=True) if f == x or f.startswith(x + " ")), None)
    if form is None:
        return None
    pos = idx[len(form) - 1] + 1
    m = _LEAD.match(printed, pos)
    if not m:
        return CaseLine(None, None, [], printed[pos:pos + 40])
    prev_digits, prev_suffix = m.group(1), m.group(2) or m.group(3) or m.group(4)
    if int(prev_digits) == 0:
        return CaseLine(None, None, [], printed[pos:pos + 40])     # 'No. 0 of 2005': no case is numbered 0
    lead = norm_number(prev_digits + (("-" + prev_suffix) if prev_suffix else ""))
    numbers: list[str] = []
    pos = m.end()
    year = None
    while True:
        y = _YEAR.match(printed, pos)
        if y:
            if y.group(1):
                year = int(y.group(1))
            else:
                yy = int(y.group(2))
                year = 2000 + yy if 2000 + yy <= (today or dt.date.today()).year else 1900 + yy
            pos = y.end()
            break
        n = _NEXT.match(printed, pos)
        if not n:
            break
        sep = n.group(1).lower()
        digits, suffix = n.group(2), n.group(3) or n.group(4) or n.group(5)
        tail = ("-" + suffix) if suffix else ""
        lo, hi = int(prev_digits), int(digits)
        if sep in ("to", "-") and (suffix or "").upper() == (prev_suffix or "").upper() and 0 < hi - lo <= RANGE_MAX:
            numbers.extend(norm_number(str(k) + tail) for k in range(lo + 1, hi + 1))
        elif sep == "-" and not suffix and not prev_suffix and hi <= lo:
            break                                          # '10-0': not a range, not a list; stop reading
        else:
            numbers.append(norm_number(digits + tail))     # a list item, or a range's end kept unexpanded
        prev_digits, prev_suffix = digits, suffix
        pos = n.end()
    if year is None or not (1947 <= year <= 2100):
        return CaseLine(lead, None, [], printed[:pos])
    joined = [x for i, x in enumerate(numbers) if x != lead and x not in numbers[:i] and not re.match(r"0+(-|$)", x)]
    return CaseLine(lead, year, joined, printed[:pos])


# --------------------------------------------------------------------------- cases listed in the header

# words just before a case line that make it another court's case or the case an application is made in
_NOT_DECIDED_HERE = re.compile(r"(?i)\b(?:in|against|from|passed|of\s+the\s+learned|vide|arising\s+out\s+of|"
                               r"impugned|decided\s+by|dated)\W*$")
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
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(form) + r"(?= (?:nos? )?\d)", f):
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
