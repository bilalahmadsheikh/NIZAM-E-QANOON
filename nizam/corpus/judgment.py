"""A superior-court judgment, read from its extracted blocks (docs/PRECEDENT-MODEL.md §3, D-118, D-123).

    parse_judgment(doc, court_aliases, case_types) -> ParsedJudgment | Held

Pure: no database and no network. The worker (nizam/workers/judgments.py) supplies the court aliases and case types
from L2 and writes the result.

What is read, and from where:
- **Header** (everything before the first JUDGMENT/ORDER heading or author line):
  - the court (the first registered court name printed);
  - the jurisdiction ('(Appellate Jurisdiction)'), the bench (lines under PRESENT naming a Justice);
  - the case number line, matched to a recorded case type;
  - the order appealed against ('(Against the judgment dated ... passed by the Lahore High Court ... in ...)');
  - the date of hearing.
- **Body:** each opinion begins at a heading or an author line ('Qazi Muhammad Amin Ahmed, J.-'). Paragraphs begin
  at the number the judgment prints ('2.'), taken only in sequence, so '302.' inside a sentence never opens one. A
  paragraph with no printed number has printed_no None. No number is ever invented (INV-1).
- **Footnotes:** a block in the lower part of a page that opens with a bare footnote number ('1 Muhammad Sadiq v.
  ...').
- **Furniture:** page numbers and running heads, found by recurrence across pages.
- **Closing:** signatures, then the place and date and the reporting note. The decision date comes from here: the
  'Announced in open Court ... on <date>' line first, then '<Place>, the <date>', then a printed 'Date of decision'.
  A judgment with no such date, or with dates that contradict each other, is released marked undated (D-124; gate J1
  held it until then), with the earliest day it allows (the printed hearing, else 1 January of the case year). It is
  never dated from the hearing, the upload or a folder name.

Whatever the parser cannot read with confidence is left None (disposition, lineage outcome) or Held with the reason.
It is never guessed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field

from nizam.storage.case_key import read_case_line

PARSER = "nizam.judgment/12"    # /2: the lower court's date printed after its name; a skipped number only when unseen
#                                 /12: no case number without a "No.", a year or the case grammar's reading; a register
#                                      letter glued to its digits ("CP D101of 2012") read (D-142)
#                                 /11: the AJK and GB courts' seats sign a judgment ('JUDGE / Mirpur, / 22.01.2018');
#                                      the GB Supreme Appellate Court's 'Date of detail judgment' (D-142)
#                                 /10: a reading with no body paragraph is held, not released (D-138)
#                                 /9: the Federal Constitutional Court's 'JUDGMENT OF THE COURT' heading and its
#                                     'JUSTICE <NAME>:' author line (D-139)
#                                 /8: the case number and year come from the case builder's grammar, so a judgment's
#                                     case number and its case key never differ (D-138)
#                                 /7: Sindh's 'ORDER WITH THE SIGNATURE OF THE JUDGE' column header; the register
#                                     letter kept in the case number ('D-1544'); a decision date before the case
#                                     year is not taken: the judgment is undated (D-138)
#                                 /6: a law report's masthead ('2010 P L C (C.S.) 1449 [Quetta High Court]
#                                     Before ...') is a reprint however short its headnote (D-138)
#                                 /5: J9, a text layer whose words are not plausible goes to OCR (D-130)
#                                 /3: no usable decision date -> released undated; a date line never opens a
#                                     paragraph; '22d December', '_14th _January' read (D-124)
#                                 /4: High Court layouts (D-128): ORDER/JUDGMENT SHEET are form titles; the order
#                                     sheet's body and date of order; hearing and counsel after the heading are header;
#                                     'Signed on <date>'; 'Case No.' before a case line; series-first reprints

# ------------------------------------------------------------------------------------------------------ dates

_MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_MONTHS["sept"] = 9
_MON = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|"
        r"jun|jul|aug|sept|sep|oct|nov|dec)\.?")
_D_NUM = re.compile(r"(?<![\d.])(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*((?:19|20)\d{2}|\d{2})(?!\d)")
# '22d December' is an ordinal as printed; '_14th _January' is a blank filled in by hand on the typed form (D-124)
_D_DMY = re.compile(r"(?<!\d)(\d{1,2})\s*(?:st|nd|rd|th|d)?[\s_]*(?:day\s+of\s+|of\s+)?(" + _MON +
                    r")\s*,?\s*((?:19|20)\d{2})", re.I)
_D_MDY = re.compile(r"(" + _MON + r")\s+(\d{1,2})\s*(?:st|nd|rd|th)?\s*,?\s*((?:19|20)\d{2})", re.I)
# a date in any of the three printed forms, as one non-capturing unit for embedding in other patterns
DATE = (r"(?:\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*(?:(?:19|20)\d{2}|\d{2})(?!\d)|"
        r"\d{1,2}\s*(?:st|nd|rd|th|d)?[\s_]*(?:day\s+of\s+|of\s+)?" + _MON + r"\s*,?\s*(?:19|20)\d{2}|"
        + _MON + r"\s+\d{1,2}\s*(?:st|nd|rd|th)?\s*,?\s*(?:19|20)\d{2})")


def read_date(text: str, today: dt.date | None = None) -> dt.date | None:
    """The earliest-printed well-formed date in `text`, if it is a real day between 1947 and today."""
    today = today or dt.date.today()
    best = None
    for rx, order in ((_D_NUM, "dmy"), (_D_DMY, "dMy"), (_D_MDY, "Mdy")):
        for m in rx.finditer(text):
            try:
                if order == "dmy":
                    d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
                    y = int(y) if len(y) == 4 else (2000 + int(y) if 2000 + int(y) <= today.year else 1900 + int(y))
                elif order == "dMy":
                    d, mo, y = int(m.group(1)), _MONTHS[m.group(2).lower().rstrip(".")], int(m.group(3))
                else:
                    mo, d, y = _MONTHS[m.group(1).lower().rstrip(".")], int(m.group(2)), int(m.group(3))
                day = dt.date(y, mo, d)
            except (ValueError, KeyError):
                continue
            if dt.date(1947, 1, 1) <= day <= today and (best is None or m.start() < best[0]):
                best = (m.start(), day)
            break
    return best[1] if best else None


# ------------------------------------------------------------------------------------------------- the model

@dataclass
class Line:
    text: str
    page: int
    block: int              # reading_order of its block
    y0: float               # its block's top, as a fraction of the page height
    footnote: bool = False
    furniture: bool = False


@dataclass
class Paragraph:
    kind: str               # header | body | footnote | closing | furniture
    printed_no: str | None
    opinion: int | None     # index into ParsedJudgment.opinions; set exactly for body paragraphs
    page_first: int
    page_last: int
    first_block: int
    last_block: int
    text: str


@dataclass
class Opinion:
    kind: str
    heading_printed: str | None
    author_printed: str | None


@dataclass
class Lineage:
    relation: str
    lower_court_code: str | None
    lower_court_printed: str
    lower_case_printed: str | None
    lower_decided_on: dt.date | None
    outcome: str | None


@dataclass
class ParsedJudgment:
    court_code: str
    decided_on: dt.date | None          # None: undated (D-124); the writer records the latest possible day
    decided_on_basis: str               # 'undated' when no usable decision date is printed
    decided_on_printed: str | None
    seat: str | None
    hearing_on: dt.date | None
    jurisdiction_printed: str | None
    case_no_printed: str
    case_type_code: str
    case_number: str | None
    case_year: int | None
    bench_printed: list[str]
    reported_flag: bool | None
    disposition: str | None
    disposition_printed: str | None
    parties_raw: str | None
    opinions: list[Opinion]
    paragraphs: list[Paragraph]
    lineage: list[Lineage] = field(default_factory=list)
    body_sha256: str = ""
    detail: dict = field(default_factory=dict)
    undated_reason: str | None = None           # why no decision date was taken (D-124)
    decided_not_before: dt.date | None = None   # the earliest possible day, from the hearing or the case year
    decided_not_before_basis: str | None = None


@dataclass
class Held:
    outcome: str            # held | needs_ocr | reporter_reprint | not_a_judgment
    reason: str
    detail: dict = field(default_factory=dict)


def fold(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


# ------------------------------------------------------------------------------- J9: is the text layer readable

# A court can publish a scan carrying its own rough OCR ('IN TIIE PESIIAWAR IIIGII COUITT'). Such a text layer is not
# released as citable text: the file goes to the OCR lane (D-114) instead. The measure is the share of words (three
# letters or more) found in a vocabulary of the words typed in at least 3 released Supreme Court judgments
# (tools/build_judgment_vocab.py). Measured 23 Nov 2026 on full text: every clean Lahore file scores 0.94 or more;
# about one Peshawar file in ten falls below, some to 0.35 (D-130).
PLAUSIBLE_MIN = 0.90
PLAUSIBLE_MIN_WORDS = 200
_VOCAB: frozenset[str] | None = None


def plausibility(text: str) -> tuple[float | None, int]:
    """(share of known words, words counted); None when fewer than PLAUSIBLE_MIN_WORDS words are counted."""
    global _VOCAB
    if _VOCAB is None:
        from pathlib import Path
        _VOCAB = frozenset((Path(__file__).parent / "data" / "judgment_vocab.txt").read_text(encoding="utf-8").split())
    toks = re.findall(r"[a-z]{3,}", text.lower())
    if len(toks) < PLAUSIBLE_MIN_WORDS:
        return None, len(toks)
    return sum(t in _VOCAB for t in toks) / len(toks), len(toks)


# ---------------------------------------------------------------------------------------------- the patterns

_HEADING = re.compile(r"^\s*(J\s*U\s*D\s*G\s*E?\s*M\s*E\s*N\s*T|O\s*R\s*D\s*E\s*R(?:\s+SHEET)?|SHORT\s+ORDER|"
                      r"ORDER\s+OF\s+THE\s+COURT|JUDG(?:E)?MENT\s+OF\s+THE\s+COURT|"
                      r"FINAL\s+ORDER|DETAILED\s+REASONS|(?:DISSENTING|SEPARATE|ADDITIONAL)\s+(?:NOTE|OPINION)|"
                      r"REASONS\s+FOR\s+THE\s+SHORT\s+ORDER)\s*[:.]?\s*$", re.I)
_AUTHOR = re.compile(r"^\s*((?:[A-Z][\w'’.\-]*\s+){0,6}[A-Z][\w'’]*(?:-[A-Za-z][\w'’]*)*?)\s*[,\-]?\s*\(?\s*"
                     r"(H?\.?\s*C\.?\s*J|A\.?\s*C\.?\s*J|JJ|J)"
                     r"\s*\.?\s*\)?\s*[-–—:.,]{1,3}\s*(.*)$")
# the Federal Constitutional Court names its author before the opinion: 'JUSTICE AAMER FAROOQ: - The petitioner ...',
# 'JUSTICE AMIN-UD-DIN KHAN, CHIEF JUSTICE:' (D-139). Upper case and a colon, so a bench line in the header ('Justice
# AAMER FAROOQ Justice ROZI KHAN BARRECH') is not an author line.
_AUTHOR_TITLED = re.compile(r"^\s*(?:MR\.?\s+)?(CHIEF\s+)?JUSTICE\s+((?:[A-Z][A-Z'’.\-]*\s+){0,5}[A-Z][A-Z'’\-]*)"
                            r"\s*(?:,\s*(CHIEF\s+JUSTICE|C\.?\s*J\.?))?\s*:\s*[-–—]?\s*(.*)$")


def _author(text: str) -> tuple[str, str] | None:
    """(name as printed, title: 'J', 'CJ', 'ACJ', 'HCJ' or 'JJ') from an opinion's author line, or None."""
    m = _AUTHOR.match(text)
    if m:
        return m.group(1), re.sub(r"[ .]", "", m.group(2))
    m = _AUTHOR_TITLED.match(text)
    if m:
        return m.group(2), "CJ" if (m.group(1) or m.group(3)) else "J"
    return None
# High Court form titles printed above the court's name: the form, not an opinion heading (D-128)
_FORM_TITLE = re.compile(r"^\s*(?:ORDER|JUDG(?:E)?MENT)\s+SHEET\s*\.?\s*$", re.I)
# the order sheet's column header; the order itself begins after it ('... where necessary.')
_ORDER_COLUMNS = re.compile(r"order\s+(?:or\s+other\s+proceedings?\s+)?with\s+(?:the\s+)?signatures?\s*(?:\(\s*s\s*\))?"
                            r"\s+of\s+"
                            r"(?:the\s+)?(?:hon\W?ble\s+)?judge",
                            re.I)    # Lahore: 'Order with signatures of Judge'; Peshawar: 'Order or other Proceedings with ...';
#                                      Sindh: 'DATE ORDER WITH SIGNATURE(S) OF JUDGE(S)', '... OF HON'BLE JUDGE' (D-138)
# a header line printed after the JUDGMENT heading in High Court judgments: the hearing date and who appeared
_POST_HEAD = re.compile(r"^\s*(?:date\s+of\s+hearing|(?:for\s+the\s+)?(?:petitioner|appellant|respondent|applicant|"
                        r"complainant|state|plaintiff|defendant|accused|convict)s?(?:\s*(?:no\.?\s*)?[\d,&\-\s]*)?"
                        r"(?:\(s\))?\s*(?:by|:))", re.I)
_CASE_NO_PREFIX = re.compile(r"^\s*(?:case\s+no\s*[.:]?\s*|\(?(?:\d{1,2}|[ivx]{1,4})\s*[.)]\s+)", re.I)
# an order sheet's column labels, as a text layer may print them after the column header
_SHEET_LABEL = re.compile(r"^\s*(?:(?:sr?\s*\.?\s*no\s*\.?|serial\s+no\.?)(?:\s*of)?|date\s+of|order|orders|proceedings?|"
                          r"where|necessary|of|and|or|counsel|parties|[/.,:\s])+\s*$", re.I)
# a new proceeding on the sheet: a line recording who appeared
_APPEARANCE = re.compile(r"\b(?:advocates?|counsel|in\s+person|prosecutor|A\.?A\.?G|D\.?P\.?G|present)\b", re.I)
# a printed paragraph number; '12.02.2026' (a date line in the closing) is not paragraph 12 (D-124)
_PARA = re.compile(r"^\s*(\d{1,3})\s*[.)](?!\d)\s*(.*)$")
_SIGN = re.compile(r"^\s*(?:Sd/?-?\s*)?\(?\s*(?:Judge|JUDGE|Chief\s+Justice|CHIEF\s+JUSTICE|Acting\s+Chief\s+Justice|"
                   r"C\.?\s*J\.?|CJ|J\.)\s*\)?\s*[.,]?\s*$")
_PAGENO = re.compile(r"^\s*[-–(]?\s*(?:Page\s+)?\d{1,3}\s*(?:of\s+\d{1,3})?\s*[-–)]?\s*$", re.I)
_FOOTNOTE = re.compile(r"^\s*(\d{1,2})\s+(?=[A-Z(‘'\"“\[])")
_REPORTER_START = re.compile(r"^\s*\d{4}\s*(?:P\s*L\s*D|S\s*C\s*M\s*R|Y\s*L\s*R|C\s*L\s*C|M\s*L\s*D|P\s*Cr\.?\s*L\s*J|"
                             r"P\s*T\s*D|C\s*L\s*D|P\s*L\s*C|P\s*L\s*J)\s*\d+"
                             # series first, as PLJ prints it: 'PLJ 2020 Lahore 555 (DB)' (D-128)
                             r"|^\s*(?:P\s*L\s*J|P\s*L\s*D|S\s*C\s*M\s*R|Y\s*L\s*R|C\s*L\s*C|M\s*L\s*D|P\s*Cr\.?\s*L\s*J|"
                             r"P\s*T\s*D|C\s*L\s*D|P\s*L\s*C|N\s*L\s*R)\s+\d{4}\s+[A-Z][a-z]+\s+\d+")
# A law report's masthead: its series and year (either order, letters spaced or not, a sub-series such as '(C.S.)'
# or 'Cr.C.' allowed), then within a few words the reporter's bench line 'Before ...' or 'Present: ...'. A court's
# own judgment never opens so; a reprint whose headnote is too short for the '---' count is still a reprint (D-138).
_SERIES = (r"(?:P\s*L\s*D|S\s*C\s*M\s*R|Y\s*L\s*R|C\s*L\s*C|M\s*L\s*D|P\s*\.?\s*Cr\.?\s*L\s*\.?\s*J|P\s*T\s*D|C\s*L\s*D|"
           r"P\s*L\s*C|P\s*L\s*J|N\s*L\s*R|K\s*L\s*R|P\s*S\s*C)")
# a library stamp may precede it ('H.B.T./60/Q 2011 M L D 1819 [Quetta] Before ...'); the page may be glued to the
# series ('2012PCr.LJ646')
_REPRINT_MASTHEAD = re.compile(r"^.{0,20}?(?:\d{4}\s*" + _SERIES + r"|" + _SERIES + r"\s*\d{4})(?:.{0,110}?"
                               r"\b(?:Before|Present\s*:)|[^\[\]]{0,30}\[[A-Za-z .()]{4,45}\])", re.S)
# printed from a law-report website: its address heads the page (D-120)
_REPORT_SITE = re.compile(r"\b(?:pakistanlawsite\.com|plsbeta\.com|pljlawsite\.com)\b", re.I)
_JURIS = re.compile(r"\(\s*([A-Za-z ]{3,40}?Jurisdiction)\s*\)", re.I)
PLACES = ("Islamabad", "Lahore", "Karachi", "Peshawar", "Quetta", "Rawalpindi", "Multan", "Bahawalpur", "Sukkur",
          "Hyderabad", "Abbottabad", "Mingora",
          # /11 (D-142): the AJK and GB courts' seats and registries, which sign 'JUDGE / Mirpur, / 22.01.2018'
          "Muzaffarabad", "Mirpur", "Kotli", "Rawalakot", "Gilgit", "Skardu")
_PLACE = r"(" + "|".join(PLACES) + r")"
# 'Announced in open Court on 18.09.2015'; Peshawar: 'Announced. 14.11.2017', 'ANNOUNCED. Dated: 22/07/2015',
# 'Announced. Dt: 18.5.2016' (D-130)
# GB Supreme Appellate Court (/11, D-142): 'Announced:- 03-11-2016.', 'Announced on: - 12.04.2019.'
_ANNOUNCED = re.compile(r"Announced\s*[.:,]?\s*-?\s*(?:in\s+(?:the\s+)?(?:open\s+)?Court\s*)?(?:at\s+" + _PLACE
                        + r"\s*)?[,.]?[\s_]*(?:on[\s_]*)?"
                        # /12 (D-142): Lahore, 'Announced in open Court today i.e. 02.02.2011.'
                        r"(?:today\s*(?:i\.?\s*e\.?)?\s*)?"
                        r"(?:dated|dt)?\s*[.:]*\s*-?\s*(?:the\s+)?" + DATE, re.I)
_SIGNED_AT = re.compile(r"\b" + _PLACE + r"\b\s*[,.:/\-]*\s*(?:the\s*)?[,.]?\s*" + DATE, re.I)
_PLACE_ONLY = re.compile(r"\b" + _PLACE + r"\b", re.I)
# read in the header only. Balochistan prints 'Announced on 31.01.2020' and 'Announcement of judgment: 16th August,
# 2013' there; Sindh 'Date of Order : 11.06.2026' and 'Date of hearing and Order: 09.03.2026' (D-138). A bare 'dated'
# is not one: a header prints 'FIR No.884/2024 dated 23.10.2024'
_DATE_OF_DECISION = re.compile(r"(?:Date\s+of\s+(?:decision|judgment|judgement|announcement|order|"
                               r"hearing\s*(?:and|&)\s*order|judg(?:e)?ment\s*/\s*reasons|"
                               # /11 (D-142): GB Supreme Appellate Court, 'DATE OF DETAIL JUDGMENT: - 03.11.2016.',
                               # 'Date of delivery of detail judgment', 'Date of detail order'
                               r"(?:delivery\s+of\s+)?detail(?:ed)?\s+(?:judg(?:e)?ment|order))\s*[:.\-\s]*|"
                               r"\bdecided\s+on|"
                               r"\bAnnounced\s+on\s*[:.\-]*|"
                               r"\bAnnouncement\s+of\s+(?:the\s+)?(?:judgment|judgement|order)\s*[:.\-]*)\s*" + DATE,
                               re.I)
_HEARING = re.compile(r"Dates?\s+of\s+hearing[\s:.\-_]*" + DATE, re.I)     # /12 (D-142): Lahore 'Dates of hearing'
# /11 (D-142): a line that is wholly an order's own date, 'Order Dated 07-10-2010', 'ORDER DATED: - 21.03.2019.' (GB
# Supreme Appellate Court). Read only as a whole line or paragraph, never inside one: 'impugned order dated ...'
_ORDER_DATED = re.compile(r"\s*ORDER\s+DATED\s*[:.\-\s]*" + DATE + r"\s*[.,]?\s*", re.I)
_SIGNED_ON = re.compile(r"\bSigned\s+on[\s:._]*" + DATE, re.I)
# 'This judgment has been dictated, pronounced on 13.03.2023 and signed ...': the decision announced
_PRONOUNCED = re.compile(r"\bpronounced\s+(?:in\s+(?:the\s+)?(?:open\s+)?court\s+)?on[\s:._]*" + DATE, re.I)
# an order sheet's date heading its order: '28.10.2022.', '1. 05-04-2022'; Sindh also 'Dated 19-01-2017' (D-138). Read
# at a line's start only, never inside a sentence ('FIR ... dated 23.10.2024')
_ORDER_DATE = re.compile(r"^\s*(?:\d{1,3}\s*[.)]\s+)?(?:Dated\s*[:\-]?\s*)?(" + DATE + r")", re.I)
_DATE_LINE = re.compile(r"^\s*(?:\d{1,3}\s*[.)]\s+)?" + DATE + r"\s*[.,]?\s*$", re.I)
_REPORTED = re.compile(r"\b(not\s+)?approved\s+for\s+report", re.I)
_AGAINST = re.compile(r"\(\s*(?:On\s+)?(?:appeal\s+)?(?:against|from)\s+(?:the\s+)?(?:impugned\s+)?(?:judgments?|orders?|"
                      r"decision|decree)\s+(?:dated|dt\.?|of)?\s*(?P<date>" + DATE + r")?(?P<rest>[^()]*(?:\([^()]*\)"
                      r"[^()]*)*)\)", re.I | re.S)

_DISPOSITIONS = (
    ("leave_refused", re.compile(r"leave\s+(?:to\s+appeal\s+)?(?:is\s+|stands\s+)?(?:hereby\s+)?(?:declined|refused)",
                                 re.I)),
    ("leave_granted", re.compile(r"leave\s+(?:to\s+appeal\s+)?(?:is\s+)?(?:hereby\s+)?granted", re.I)),
    ("partly_allowed", re.compile(r"\b(?:partly|partially)\s+(?:allowed|accepted)\b|\ballowed\s+in\s+part\b", re.I)),
    ("remanded", re.compile(r"\bremand(?:ed)?\b", re.I)),
    ("allowed", re.compile(r"\b(?:is|are|stands?)\s+(?:hereby\s+)?(?:accepted|allowed)\b|"
                           r"\b(?:allow|accept)\s+(?:it|them|this\s+(?:appeal|petition)|the\s+(?:same|appeals?|"
                           r"petitions?))\b", re.I)),
    ("dismissed", re.compile(r"\b(?:is|are|stands?)\s+(?:hereby\s+)?dismissed\b", re.I)),
    ("disposed", re.compile(r"\bdisposed\s+of\b", re.I)),
    ("adjourned", re.compile(r"\badjourned\b", re.I)),
)
_KIND_ORDER = {"header": 0, "body": 1, "closing": 2, "footnote": 3, "furniture": 4}


# ------------------------------------------------------------------------------------------------ lines

def _lines(doc) -> list[Line]:
    heights = {p.page_no: (p.height or 1.0) for p in doc.pages}
    out: list[Line] = []
    for b in doc.blocks:
        rel = b.y0 / heights.get(b.page_no, 1.0)
        parts = [t.strip() for t in b.text.split("\n") if t.strip()]
        note = bool(parts) and rel > 0.6 and bool(_FOOTNOTE.match(parts[0])) and not _PARA.match(parts[0])
        for t in parts:
            out.append(Line(t, b.page_no, b.reading_order, rel, footnote=note))
    _mark_furniture(out, len(doc.pages))
    return out


def _mark_furniture(lines: list[Line], pages: int) -> None:
    """Page numbers at a page's edge, and running heads that recur at the top of many pages."""
    by_page: dict[int, list[Line]] = {}
    for ln in lines:
        by_page.setdefault(ln.page, []).append(ln)
    tops: dict[str, set[int]] = {}
    for p, ls in by_page.items():
        for ln in ls[:2]:
            tops.setdefault(re.sub(r"\d+", "#", fold(ln.text)), set()).add(p)
    for p, ls in by_page.items():
        for ln in ls[:2] + ls[-2:]:
            key = re.sub(r"\d+", "#", fold(ln.text))
            if _PAGENO.match(ln.text) and not ln.footnote:
                ln.furniture = True
            elif (p > 1 and ln in ls[:2] and key and pages >= 3
                  and len(tops.get(key, ())) >= max(2, pages // 3)):
                ln.furniture = True


def _join(texts) -> str:
    out = ""
    for t in texts:
        if not t:
            continue
        if not out:
            out = t
        elif out.endswith("-") and t[:1].islower():
            out += t
        else:
            out += " " + t
    return re.sub(r"[ \t]+", " ", out).strip()


def _court(text: str, aliases: dict[str, str], glued: bool = False) -> str | None:
    """The registered court whose name is printed first in `text`.

    `glued` lets the name follow a stray character ('PSUPREME COURT OF PAKISTAN', a text-layer artefact); it is used
    only on a header's first lines, where the deciding court's own name is printed.
    """
    f = " " + fold(text) + " "
    best = None
    for key, code in aliases.items():
        i = f.find(("" if glued else " ") + key + " ")
        if i >= 0 and (best is None or i < best[0] or (i == best[0] and len(key) > best[2])):
            best = (i, code, len(key))
    return best[1] if best else None


def _case(lines: list[str], case_types: dict[str, tuple[str, list[str]]]):
    """The first header line that opens with a recorded case-type name and carries a number.

    Some text layers break the line word by word ('Jail / Petition / No. 787/2018'), so up to four lines are read
    together, and the shortest window that carries a number and a year wins.
    """
    forms = sorted(((form, code) for code, (_, fs) in case_types.items() for form in fs), key=lambda x: -len(x[0]))
    for i in range(len(lines)):
        for k in range(1, 5):
            if i + k > len(lines):
                break
            text = _CASE_NO_PREFIX.sub("", " ".join(lines[i:i + k]))     # 'Case No. Writ Petition No.2849/2011'
            f = fold(text)
            hit = next(((form, code) for form, code in forms if f.startswith(form + " ")), None)
            if hit is None:
                if k == 1 and not any(form.startswith(f) or f.startswith(form.split()[0]) for form, _ in forms):
                    break
                continue
            form, code = hit
            rest = f[len(form):]
            num = re.search(r"\bnos? ?(\d+(?: [a-z]\b)?)", rest) or re.search(r"\b(\d+(?: [a-z]\b)?)", rest)
            yr = re.search(r"\bof (\d{4})\b", rest) or re.search(r"\b\d+(?: [a-z])? (\d{4})\b", rest)
            if not num or (not yr and k < 4 and i + k < len(lines)):
                continue
            year = int(yr.group(1)) if yr and 1947 <= int(yr.group(1)) <= 2100 else None
            printed = text
            if i + k < len(lines) and re.search(r"(?i)(\b(and|to|in|with)|,|&)\s*$", text):
                printed = text + " " + lines[i + k]
            number = num.group(1).replace(" ", "-").upper()
            # the number and year are the case line's, read by the one grammar the case builder uses
            # (storage.case_key.read_case_line) over the same stored words, so the judgment's case number and its
            # case key agree by construction (D-138): Sindh's register letter ('D-1544'), no leading zero, a list's
            # lead number. Only where that grammar reads nothing does this line's own reading stand.
            line = read_case_line(printed[:500], case_types[code][1])
            if line is not None and line.lead is not None:
                number = line.lead
                if line.year is not None:
                    year = line.year
            elif year is None and not re.search(r"\bnos? ?\d", rest):
                # /12 (D-142): a number with no 'No.' before it, no year after it and no reading by the case grammar
                # is not a case number -- 'CRIMINAL APPEAL UNDER SECTION 417 CR.P.C', 'Criminal Appeal N~2019'
                continue
            return code, printed, number, year, i + k - 1
    return None


# ------------------------------------------------------------------------------------------------ the parser

def parse_judgment(doc, court_aliases: dict[str, str], case_types: dict[str, tuple[str, list[str]]],
                   *, expected_court: str | None = None, today: dt.date | None = None) -> ParsedJudgment | Held:
    """`court_aliases`: folded alias -> court code. `case_types`: code -> (kind, folded printed forms)."""
    today = today or dt.date.today()
    text_pages = [p for p in doc.pages if p.char_count >= 200]
    if doc.char_count < 100 * doc.page_count or len(text_pages) < max(1, (doc.page_count + 1) // 2):
        return Held("needs_ocr", f"text layer too thin: {doc.char_count} chars over {doc.page_count} pages")
    if sum(1 for b in doc.blocks if b.script == "arabic") > len(doc.blocks) / 2:
        return Held("needs_ocr", "Urdu text layer (not trusted as extracted; the OCR lane, D-114)")
    first_text = " ".join(b.text for b in doc.blocks[:12])
    if _REPORTER_START.match(first_text) and (first_text[:3000].count("---") >= 4
                                              or first_text[:3000].count("--") >= 6):
        return Held("reporter_reprint", "opens with a law-reporter citation and headnote (D-120)")
    if _REPRINT_MASTHEAD.match(first_text) or _REPORT_SITE.search(first_text[:400]):
        return Held("reporter_reprint", "opens with a law report's masthead (D-120, D-138)")

    lines = _lines(doc)
    main = [ln for ln in lines if not ln.footnote and not ln.furniture]
    if not main:
        return Held("not_a_judgment", "no text outside page furniture")
    # J9 first: a garbled text layer is a scan to read, not a judgment whose court or heading could not be found
    score, counted = plausibility(" ".join(ln.text for ln in main))
    if score is not None and score < PLAUSIBLE_MIN:
        return Held("needs_ocr", f"J9: text layer not readable ({score:.2f} of {counted} words known; "
                                 f"{PLAUSIBLE_MIN} needed)", {"plausibility": round(score, 3)})

    def is_heading(ln: Line) -> bool:
        return bool(_HEADING.match(ln.text)) and not _FORM_TITLE.match(ln.text)

    # a heading may sit late in a short order whose header is long; an author line is trusted only early on
    start = next((i for i, ln in enumerate(main[:max(10, int(len(main) * 0.9))]) if is_heading(ln)), None)
    order_sheet = False
    if start is None:
        # a High Court order sheet (D-128): no heading; the order begins after the column header 'Order with
        # signatures of Judge, and that of parties or counsel, where necessary'
        col = next((i for i, ln in enumerate(main[:max(12, int(len(main) * 0.6))]) if _ORDER_COLUMNS.search(ln.text)),
                   None)
        if col is not None:
            end = next((k for k in range(col, min(col + 3, len(main))) if re.search(r"(?i)\bnecessary\b", main[k].text)),
                       col)
            if end + 1 < len(main):
                start, order_sheet = end + 1, True
    if start is None:
        start = next((i for i, ln in enumerate(main[:max(10, int(len(main) * 0.6))])
                      if i > 3 and _author(ln.text)), None)
    if start is None:
        return Held("held", "no JUDGMENT/ORDER heading, or author line in the first 60% of the text")
    if order_sheet:
        # a text layer can print the column header early, before the case line, the parties and the column labels
        # ('Sr. No. of order/ proceeding'); the order begins at the first line opening with its date, and what comes
        # before it is header
        k = next((k for k in range(start, min(start + 25, len(main))) if _ORDER_DATE.match(main[k].text)), None)
        if k is not None:
            start = k
    header_lines = main[:start]
    body_lines = main[start:]
    if not order_sheet and is_heading(main[start]):
        # High Court layout (D-128): after the heading come the hearing date, who appeared, sometimes the case line,
        # then the author line. Those lines are header, not the court's text.
        j = next((k for k in range(start + 1, min(start + 60, len(main))) if _author(main[k].text)), None)
        no_case_yet = _case([ln.text for ln in header_lines],
                            {k: v for k, v in case_types.items() if k.startswith(f"{expected_court or ''}:")}) is None
        if j is not None and j > start + 1 and (any(_POST_HEAD.match(x.text) for x in main[start + 1:start + 4])
                                                or (expected_court and no_case_yet)):
            header_lines = main[:start] + main[start + 1:j]
            body_lines = [main[start]] + main[j:]
    header = _join(ln.text for ln in header_lines)

    # the court is the one the first lines print; a name further down is the court below, never the deciding court
    court = _court(_join(ln.text for ln in header_lines[:4]), court_aliases, glued=True)
    if court is None:
        return Held("held", "court not resolved from the header's first lines")
    if expected_court and court != expected_court:
        return Held("held", f"header names {court}, the archive is {expected_court}'s")
    case = _case([ln.text for ln in header_lines], {k: v for k, v in case_types.items() if k.startswith(court + ":")})
    if case is None:
        return Held("held", "J3: no case number line matching a recorded case type")
    case_code, case_printed, case_number, case_year, case_i = case

    bench = [ln.text for ln in header_lines[:case_i]
             if re.search(r"(?i)\bjustice\b", ln.text) and not re.search(r"(?i)\b(supreme|high)\s+court\b", ln.text)]
    jm = _JURIS.search(header)
    hm = _HEARING.search(header)
    hearing = read_date(hm.group(0), today) if hm else None

    paras: list[Paragraph] = []
    opinions: list[Opinion] = []

    def add(kind, no, op, ls):
        ls = [x for x in ls]
        if ls:
            paras.append(Paragraph(kind, no, op if kind == "body" else None, ls[0].page, ls[-1].page,
                                   ls[0].block, ls[-1].block, _join(x.text for x in ls)))

    add("header", None, None, header_lines)
    body = body_lines
    cur: list[Line] = []
    cur_no: str | None = None
    expected = 1
    op = -1
    if order_sheet:
        opinions.append(Opinion("order_of_court", "ORDER SHEET", None))
        op = 0
    closing: list[Line] | None = None
    closings: list[str] = []
    i = 0
    while i < len(body):
        ln = body[i]
        heading = _HEADING.match(ln.text)
        author = _author(ln.text)
        if (heading or author) and (op < 0 or closing is not None):
            if closing is not None:
                add("closing", None, None, closing)
                closings.append(_join(x.text for x in closing))
                closing = None
            add("body", cur_no, op, cur)
            cur, cur_no, expected = [], None, 1
            head_text = re.sub(r"\s+", " ", heading.group(1)).upper() if heading else None
            if heading and i + 1 < len(body):
                author = _author(body[i + 1].text)
            opinions.append(Opinion(_opinion_kind(head_text, len(opinions)), head_text,
                                    f"{author[0]}, {author[1]}." if author else None))
            op = len(opinions) - 1
            if heading:                # a heading is recorded on its opinion, not as a paragraph
                i += 1
                continue
        if closing is not None:
            closing.append(ln)
            i += 1
            continue
        if op >= 0 and _SIGN.match(ln.text) and _signs_off(body, i):
            add("body", cur_no, op, cur)
            cur, cur_no = [], None
            closing = [ln]
            i += 1
            continue
        m = _PARA.match(ln.text)
        if m and op >= 0:
            n = int(m.group(1))
            # one skipped number is tolerated (a text layer can drop a line), unless the skipped number is printed
            # further on: then this line is a stray number, not the next paragraph
            skip_ok = n == expected + 1 and (expected > 1 or (cur_no is None and cur)) and not any(
                (pm := _PARA.match(x.text)) and int(pm.group(1)) == expected for x in body[i + 1:i + 400])
            if n == expected or skip_ok:
                add("body", cur_no, op, cur)
                cur_no, expected = m.group(1), n + 1
                cur = [Line(m.group(2).strip(), ln.page, ln.block, ln.y0)]
                i += 1
                continue
        cur.append(ln)
        i += 1
    if closing is not None:
        add("closing", None, None, closing)
        closings.append(_join(x.text for x in closing))
    else:
        add("body", cur_no, op, cur)
    if not opinions:
        return Held("held", "no opinion found after the header")

    for ln in lines:
        if ln.footnote:
            fm = _FOOTNOTE.match(ln.text)
            last = paras[-1] if paras else None
            if last and last.kind == "footnote" and last.last_block == ln.block:
                last.text = _join([last.text, ln.text])
            elif fm:
                paras.append(Paragraph("footnote", fm.group(1), None, ln.page, ln.page, ln.block, ln.block,
                                       ln.text.strip()))
            elif last and last.kind == "footnote":
                last.text, last.last_block, last.page_last = _join([last.text, ln.text]), ln.block, ln.page
        elif ln.furniture:
            paras.append(Paragraph("furniture", None, None, ln.page, ln.page, ln.block, ln.block, ln.text.strip()))
    paras = [p for p in paras if p.text]
    paras.sort(key=lambda p: (p.first_block, _KIND_ORDER[p.kind]))
    if not any(p.kind == "body" for p in paras):
        # a judgment is released only with the court's text (audit A25): a reading that found a header and a closing
        # but no body has misplaced the opinion, and is held, not released empty (D-138, SHC C.P. D-649/2020)
        return Held("held", "no body text read between the header and the closing")

    court_op = next((k for k, o in enumerate(opinions) if o.kind == "order_of_court"), 0)
    court_body = [p.text for p in paras if p.kind == "body" and p.opinion == court_op]
    all_body = [p.text for p in paras if p.kind == "body"]
    tail_text = (all_body[-1][-400:] if all_body else "")
    decided = basis = printed = place = None
    if order_sheet:
        # the order's date opens it, in the sheet's date column (D-128); a sheet printing several different order
        # dates holds several orders, and which one decides is not guessed
        m0 = _ORDER_DATE.match(body_lines[0].text) if body_lines else None
        d0 = read_date(m0.group(1), today) if m0 else None
        days = {read_date(x.text, today) for k, x in enumerate(body_lines[1:], 1)
                if _DATE_LINE.match(x.text) and k + 1 < len(body_lines)
                and _APPEARANCE.search(body_lines[k + 1].text)} - {None}
        if d0:
            days.add(d0)
        if d0 and len(days) == 1:
            decided, basis, printed, place = d0, "date_of_order", m0.group(1), None
        elif len(days) > 1:
            decided, basis, printed, place = (None, None, None, "several order dates on the sheet: "
                                              + ", ".join(map(str, sorted(days))))
    if decided is None and not (order_sheet and place and place.startswith("several")):
        decided, basis, printed, place = _decision_date(closings, all_body[-3:], tail_text, header, today,
                                                        [ln.text for ln in header_lines])
    undated_reason = not_before = not_before_basis = None
    if decided is None:
        undated_reason = place
    elif hearing and hearing > decided:
        undated_reason = f"hearing {hearing} is after the decision date read ({decided}, {printed!r})"
    elif case_year and 1947 <= case_year <= today.year and decided.year < case_year:
        # a case is decided no earlier than the year it was filed: the date read is an earlier order's, or misprinted,
        # and which is not guessed (D-138)
        undated_reason = f"the decision date read ({decided}, {printed!r}) is before the case year {case_year}"
    if undated_reason:
        # released marked undated (D-124): no date is taken, only the earliest day the judgment itself allows. A
        # hearing date in conflict with the date read, or before the case year, is not trusted as that bound.
        decided, basis, printed, place = None, "undated", None, None
        if (hearing and not undated_reason.startswith("hearing")
                and not (case_year and 1947 <= case_year <= today.year and hearing.year < case_year)):
            not_before, not_before_basis = hearing, "hearing"
        elif case_year and 1947 <= case_year <= today.year:
            not_before, not_before_basis = dt.date(case_year, 1, 1), "case_year"
    if place is None:
        # the bench the header prints ('IN THE LAHORE HIGH COURT, MULTAN BENCH, MULTAN'), D-128
        bm = re.search(_PLACE + r"\s+Bench\b", header, re.I)
        place = bm.group(1).title() if bm else None

    reported = None
    for m in _REPORTED.finditer(" ".join(closings[-1:] + all_body[-1:])):
        reported = m.group(1) is None
    disposition, disposition_printed = _disposition(court_body)
    lineage = _lineage(header, court_aliases, case_types[case_code][0], disposition, disposition_printed, today)

    detail = {"paragraphs": len(paras), "body_paragraphs": len(all_body), "opinions": len(opinions),
              "footnotes": sum(1 for p in paras if p.kind == "footnote"),
              "numbered": sum(1 for p in paras if p.kind == "body" and p.printed_no),
              "coverage_chars": sum(len(p.text) for p in paras), "document_chars": doc.char_count,
              "plausibility": round(score, 3) if score is not None else None}
    return ParsedJudgment(
        court_code=court, decided_on=decided, decided_on_basis=basis,
        decided_on_printed=printed[:300] if printed else None, undated_reason=undated_reason,
        decided_not_before=not_before, decided_not_before_basis=not_before_basis,
        seat=place, hearing_on=hearing, jurisdiction_printed=jm.group(0) if jm else None,
        case_no_printed=case_printed[:500], case_type_code=case_code, case_number=case_number, case_year=case_year,
        bench_printed=bench, reported_flag=reported, disposition=disposition,
        disposition_printed=disposition_printed[:500] if disposition_printed else None,
        parties_raw=_parties(header_lines, case_i), opinions=opinions, paragraphs=paras, lineage=lineage,
        body_sha256=hashlib.sha256(fold(" ".join(all_body)).encode()).hexdigest(), detail=detail)


_CLOSING_CUE = re.compile(r"^\s*(?:\(?[A-Z][A-Z .'’\-]{3,}\)?\s*$|\*|approved|not\s+approved|announced|signed|"
                          r"pronounced|dictated|sd/|" + _PLACE + r"\b)", re.I)


def _signs_off(body: list[Line], i: int) -> bool:
    """Whether a lone 'Judge' line at body[i] is a signature (D-128), not a word wrapped onto its own line ('the
    learned Civil / Judge / Sahiwal dated ...'): it is near the end, or what follows it reads as a closing or a new
    opinion."""
    if len(body) - i <= 40:
        return True
    nxt = next((x.text for x in body[i + 1:i + 3] if x.text.strip()), "")
    return bool(_CLOSING_CUE.match(nxt) or _SIGN.match(nxt) or _HEADING.match(nxt) or _author(nxt))


def _decision_date(closings, tail_body, tail_text, header, today, header_lines=()):
    """(date, basis, printed words, seat) by the fixed order of evidence, or (None, None, None, reason)."""
    d, basis, printed, place = _decision_date_printed(closings, tail_body, tail_text, header, today)
    if d is not None or (place or "").startswith("conflicting"):
        return d, basis, printed, place          # weaker evidence never settles a conflict
    # last: a line that is wholly the order's own date (/11, D-142); one distinct date only
    lines = [t for t in list(header_lines) + closings + tail_body if t and _ORDER_DATED.fullmatch(t)]
    days = {read_date(t, today) for t in lines} - {None}
    if len(days) == 1:
        return days.pop(), "date_of_order", lines[-1].strip(), None
    return d, basis, printed, place


def _decision_date_printed(closings, tail_body, tail_text, header, today):
    for basis, rx, texts in (("announced", _ANNOUNCED, closings + tail_body),
                             ("announced", _PRONOUNCED, closings + tail_body),
                             ("signed_at", _SIGNED_ON, closings + [tail_text]),       # 'Signed on 25.02.2025'
                             ("signed_at", _SIGNED_AT, closings + [tail_text]),
                             ("date_of_decision", _DATE_OF_DECISION, [header])):
        found = []
        for t in texts:
            for m in rx.finditer(t):
                d = read_date(m.group(0), today)
                if d:
                    place = next((g for g in m.groups() if g), None)
                    found.append((d, m.group(0).strip(), place.title() if place else None))
        if found:
            days = sorted({d for d, _, _ in found})
            if len(days) > 1:
                return None, None, None, f"conflicting {basis} dates: " + ", ".join(map(str, days))
            d, printed, place = found[-1]
            return d, basis, printed, place
        if rx is _SIGNED_AT and closings:
            # a closing laid out in columns prints the place and the date apart ('Islamabad / JUDGE / 24.03.2022');
            # it is read only when the last closing names exactly one place and exactly one date
            last = closings[-1]
            if len(last) > 400:          # a signature block is short; a long 'closing' is body text misread
                continue
            places = {m.group(1).title() for m in _PLACE_ONLY.finditer(last)}
            days = {read_date(m.group(0), today) for m in re.finditer(DATE, last, re.I)} - {None}
            if len(places) == 1 and len(days) == 1:
                return days.pop(), basis, last[-200:], places.pop()
    return None, None, None, "no printed decision date (announced / place and date / date of decision)"


def _opinion_kind(heading: str | None, index: int) -> str:
    h = heading or ""
    if "SHORT ORDER" in h:
        return "short_order"
    if "DETAILED REASONS" in h or "REASONS FOR THE SHORT ORDER" in h:
        return "detailed_reasons"
    if "ORDER OF THE COURT" in h or "FINAL ORDER" in h:
        return "order_of_court"
    if "DISSENTING" in h:
        return "dissenting"
    if "NOTE" in h or "OPINION" in h:
        return "separate_note"
    # the court's first opinion; a later one is read for its kind before it can carry a holding
    return "judgment_of_court" if index == 0 else "unclassified"


def _disposition(body_texts: list[str]) -> tuple[str | None, str | None]:
    """The order's outcome from the court's last two paragraphs: the first pattern that matches, None if two conflict."""
    sentences = re.split(r"(?<=[.;])\s+", " ".join(body_texts[-2:]))
    hits = []
    for name, rx in _DISPOSITIONS:
        s = next((s for s in sentences if rx.search(s)), None)
        if s:
            hits.append((name, s.strip()))
    if not hits:
        return None, None
    names = {h[0] for h in hits}
    if {"allowed", "dismissed"} <= names and not names & {"partly_allowed", "leave_refused", "leave_granted"}:
        return None, None              # one order allowing some and dismissing others: read by a person
    return hits[0]


def _lineage(header, aliases, case_kind, disposition, disposition_printed, today) -> list[Lineage]:
    m = _AGAINST.search(header)
    if not m:
        return []
    relation = {"leave_petition": "leave_petition", "jail_petition": "leave_petition", "appeal": "appeal",
                "shariat_appeal": "appeal", "review": "review", "intra_court_appeal": "intra_court_appeal"
                }.get(case_kind, "appeal")
    rest = " ".join((m.group("rest") or "").split())
    lower = _court(rest, aliases)
    court_part = re.sub(r"^(?:passed\s+by|of|by)\s+(?:the\s+)?(?:learned\s+)?", "", rest, flags=re.I)
    court_part = re.split(r"\b(?:passed\s+in|in|dated|dt\.?)\b", court_part, maxsplit=1, flags=re.I)[0].strip(" ,.")
    case_m = re.search(r"\b(?:passed\s+in|in)\s+(.+)$", rest, re.I)
    # the date is printed before the court ('judgment dated 16.03.2017 passed by') or after it ('of the Lahore High
    # Court dated 04.02.2020')
    lower_date = (read_date(m.group("date"), today) if m.group("date") else None) or read_date(
        rest[:case_m.start()] if case_m else rest, today)
    outcome = None
    if disposition == "leave_refused":
        outcome = "leave_refused"
    elif disposition_printed and re.search(r"\bset\s+aside\b", disposition_printed, re.I):
        outcome = "set_aside"
    elif disposition == "remanded":
        outcome = "remanded"
    elif disposition == "dismissed" and relation == "appeal":
        outcome = "dismissed"
    return [Lineage(relation, lower, court_part[:300] or rest[:300], case_m.group(1).strip()[:300] if case_m else None,
                    lower_date, outcome)]


def _parties(header_lines: list[Line], case_i: int) -> str | None:
    """The lines between the case number and the first counsel or hearing line (internal only, D-122)."""
    out = []
    for ln in header_lines[case_i + 1:]:
        if re.match(r"(?i)\s*(for\s+the|for\s+petitioner|for\s+respondent|for\s+appellant|date\s+of\s+hearing|"
                    r"in\s+attendance|on\s+court'?s?\s+notice)", ln.text):
            break
        out.append(ln.text)
    return _join(out)[:2000] or None
