"""The key of a case, as printed (D-125): '<court>/<type>/<number>/<year>', e.g. 'SC/CA/1507/2024'.

It lives in storage so that the builder (L1, nizam.corpus.judgment_case), the linker and the API (L6) build the same
key from the same words. It is built from printed words, never from a row id, so a rebuild never changes it.
Leading zeros are not part of a number ('No.05/2012' is case 5 of 2012).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass


def norm_number(number: str) -> str:
    """'05' -> '5', '801-l' -> '801-L', '0780' -> '780', 'D-01' -> 'D-1'. Keeps a trailing letter suffix (a
    registry's seat) and a register letter before the number (D-138)."""
    n = re.sub(r"\s+", "", number).upper()
    return re.sub(r"^([A-Z]-)?0+(?=\d)", r"\1", n)


def case_key(court: str, case_type_code: str, number: str, year: int) -> str:
    kind = case_type_code.split(":", 1)[1] if ":" in case_type_code else case_type_code
    return f"{court}/{kind}/{norm_number(number)}/{year}"


RANGE_MAX = 500         # a printed range wider than this is not expanded (a misread, or a year)


# ------------------------------------------------------------------------------------------- the case line

# a number and its registry suffix: '801-L', '2143-CB' (cancellation of bail), '4-RWP', '07(S)', '241 K' (D-128)
_ITEM = r"(\d{1,6})(?:\s*[-–—]\s*([A-Za-z]{1,3})(?![A-Za-z])|\(\s*([A-Za-z])\s*\)|\s([A-Z])(?![A-Za-z]))?"
# after the type's form: a form's unread tail ('Crl.P' + '.L.A.'), then 'No.' as printed ('No,', 'NO-', 'No»', 'N.')
# a register letter printed BEFORE the number is part of it: Sindh's 'C.P. No. D-2606 of 2018' (division bench) and
# 'Cr. Bail Application No. S-1043' (single bench) are separate registers, as is 'Suit No. B-12' (banking) (D-138)
_LEAD = re.compile(r"[\s.:#(,]*(?:[a-z]{1,2}(?:s?\.\s*|\s+)){0,3}(?:nos?|numbers?|n)?[\s.:#,»\-]*"
                   r"(?:(?<![A-Za-z])([A-Z])\s*[-–]\s*(?=\d))?" + _ITEM, re.I)
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
    register = m.group(1)
    prev_digits, prev_suffix = m.group(2), m.group(3) or m.group(4) or m.group(5)
    if int(prev_digits) == 0:
        return CaseLine(None, None, [], printed[pos:pos + 40])     # 'No. 0 of 2005': no case is numbered 0
    lead = norm_number((f"{register}-" if register else "") + prev_digits
                       + (("-" + prev_suffix) if prev_suffix else ""))
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
