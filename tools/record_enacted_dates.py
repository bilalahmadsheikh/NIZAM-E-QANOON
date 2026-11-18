"""Record each released instrument's printed enactment date (migration 0070, field enacted_on).

WHAT IS READ. The instrument's own TITLE REGION (tools/record_instrument_numbers.py: its first <= 40 blocks, cut at
the long title / preamble / enacting formula / first section), for
  * the bracketed date printed under the title and number -- '[18th April, 1956]' -- which for an Act is the date
    of assent, for an Ordinance the date of promulgation, and for rules, regulations, orders and notifications the
    date they were made or notified; or
  * a printed assent statement -- 'Received the assent of the Governor General on the 6th October, 1860'.
The basis names which, and for which kind, so nobody reads a notification date as an assent date.

Version 2 (16 Nov 2026) reads four more printed forms, each with its own basis:
  * 'assented to by the Governor of Sindh on 28th July, 2021' -- the Assembly notification's assent clause (v1's
    pattern required the noun 'assent' and missed the verb);
  * 'The following Ordinance made by the President on the 26th day of August, 1979' -- a promulgation (or making)
    statement, for ordinances, orders and regulations;
  * a block that is nothing but a date, under the title ('18th May, 2015.') -- the Sindh Code's unbracketed form of
    the date under the title;
  * for rules, regulations, notifications and orders only: the notification's own date line -- 'Dated Lahore, the
    15th November 2021', 'Islamabad, the 8th October, 2010', 'No. SO(Tech)ED/V-105, dated 2.11.2004' -- the date the
    instrument was made. A Gazette masthead ('ISLAMABAD, SATURDAY, MARCH 11, 2023') is the issue's date, not this, and
    has a different shape; it is never read. On an Act or Ordinance the 'Dated Quetta, the ...' line is the date of
    publication, so it is not read there. A title region that calls the text 'draft' is refused outright.
Numeric dates (2.11.2004) are read day.month.year, the form Pakistani notifications print, and only with a 4-digit year
and only inside one of these statements. OCR's readings of superscript ordinals ('17"', '25%', '08™') are accepted.

PRECEDENCE (v2): assent or promulgation statement > bracket under the title > date line > notification line. The most
direct form present decides and must give exactly one date; disagreeing lower forms are kept in the evidence.

A DATE IS RECORDED ONLY WHEN it is a real calendar date, its year equals the instrument's year -- or the year of the
instrument's own printed number, 'SIND ORDINANCE NO. XIII OF 1971' above 'THE ... ORDINANCE, 1970 [8th December, 1971]'
(v2) -- and it is the ONLY distinct such date in the title region across every form. The source catalogue's date is
NOT a source (placeholders such as 1869-12-31 and upload dates on Balochistan rules); where it happens to agree, that
is noted in the evidence. 'Updated till' / 'UPDATED ON' dates are a consolidator's, never an enactment date.

    python tools/record_enacted_dates.py            # report
    python tools/record_enacted_dates.py --apply    # write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_instrument_numbers import (BLOCKS, WITH_KIND, latest_withdrawn, title_region,  # noqa: E402
                                       withdraw)                                            # (same title region)

METHOD = "nizam.printed_enactment_date/2"
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], 1)}
ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10,
        "nov": 11, "dec": 12}
MONTH_RX = r"(January|February|March|April|May|June|July|August|September|October|November|December|" \
           r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?"
DAY_RX = r"(\d{1,2})\s*(?:st|nd|rd|th|ST|ND|RD|TH)?"
BRACKET = re.compile(rf"\[\s*(?:Dated\s*)?{DAY_RX}\s+(?:day\s+of\s+)?{MONTH_RX},?\s*(\d{{4}})\s*\]", re.I)
ASSENT = re.compile(rf"assent\b[^.\]]{{0,80}}?\bon\s+(?:the\s+)?{DAY_RX}\s+(?:day\s+of\s+)?{MONTH_RX},?\s*(\d{{4}})",
                    re.I)
KIND_BASIS = {"act": "printed_assent_date", "ordinance": "printed_promulgation_date"}

# --- version 2 forms -------------------------------------------------------------------------------------------------
# a day with an ordinal OCR may have read as a quote mark, percent, trademark or asterisk ('17"', '25%', '08™', '1*t')
DAY2 = r"(\d{1,2})\s*(?:st|nd|rd|th|ST|ND|RD|TH|[\"'’”™®°%*]+[a-z]{0,2})?"
DATE2 = rf"{DAY2}[\s-]+(?:day\s+of\s+)?{MONTH_RX}\s*[,.]?\s*(\d{{4}})"
NUMERIC = r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})\b"
ASSENTED = re.compile(rf"assented\s+to\b[^.\]]{{0,80}}?\bon\s+(?:the\s+)?(?:{DATE2}|{NUMERIC})", re.I)
ASSENT2 = re.compile(rf"assent\b[^.\]]{{0,80}}?\bon\s+(?:the\s+)?(?:{DATE2}|{NUMERIC})", re.I)
MAKER = r"(?:President|Governor(?:[\s-]+General)?|Chief\s+(?:Executive|Commissioner|Martial\s+Law\s+Administrator)|" \
        r"Prime\s+Minister|Chief\s+Minister|Federal\s+Government|Provincial\s+Government)"
PROMULGATED = re.compile(rf"\b(?:made|promulgated)\s+by\s+(?:the\s+)?{MAKER}\b[^.\]]{{0,60}}?\bon\s+(?:the\s+)?"
                         rf"(?:{DATE2}|{NUMERIC})", re.I)
DATE_LINE = re.compile(rf"^\s*\[?\s*(?:Dated\s*[:,]?\s*)?{DATE2}\s*\.?\s*\]?\s*\.?\s*$", re.I)
PLACES = r"(?:Lahore|Karachi|Peshawar|Quetta|Islamabad|Rawalpindi|Muzaffarabad|Gilgit|Dacca|Dhaka|Simla|Calcutta|" \
         r"New\s+Delhi|Delhi|Hyderabad|Murree|Abbottabad)"
PLACE_DATE = re.compile(rf"(?:\[\s*)?(?:Dated\s*[:,]?\s*)?\b{PLACES}\s*[,.]?\s*(?:the\s*[,.]?\s*)?(?:dated\s*[:,]?\s*)?"
                        rf"(?:the\s+)?(?:{DATE2}|{NUMERIC})", re.I)
NO_DATED = re.compile(rf"\bNo\s*\.?\s*[\w().:\-/&\\ ]{{1,60}}?,?\s*dated\s*[:,]?\s*(?:the\s+)?(?:{DATE2}|{NUMERIC})", re.I)
DRAFT = re.compile(r"\bdraft\b", re.I)
PUBLICATION_BEFORE = re.compile(r"Gazette|Gazatte|Extraordinary|Extra\.|\bpublished\b", re.I)
NUMBER_YEAR_GAP = 2   # 'ACT, 1995 [22nd January, 1996]': passed one year, numbered and assented the next
# How directly a form states the instrument's own date. A printed assent or promulgation statement names the act of
# enactment itself; the bracket under the title is the consolidator's statement of it; a bare date line is the same
# with less around it; a notification line can also be an AMENDING notification's ('notified vide ... dated').
# The most direct form present decides, and must give exactly one date; lower forms that disagree are kept in the
# evidence ('lower_forms_disagree'), never silently dropped.
RANK = {"assent": 0, "promulgation": 0, "bracket": 1, "date_line": 2, "notification_date": 3}
SUBORDINATE = {"rules", "regulation", "notification", "order"}
PROMULGATING = {"ordinance", "order", "regulation"}


def match_date(m: re.Match) -> date | None:
    """A v2 match: groups (day, month, year) for the worded form, then (day, month, year) for the numeric one."""
    g = m.groups()[-6:]
    if g[0] is not None:
        return to_date(g[0], g[1], g[2])
    try:
        return date(int(g[5]), int(g[4]), int(g[3]))
    except (ValueError, TypeError):
        return None


def to_date(day: str, month: str, year: str) -> date | None:
    m = MONTHS.get(month.lower().rstrip(".")) or ABBR.get(month.lower().rstrip("."))
    try:
        return date(int(year), m, int(day)) if m else None
    except ValueError:
        return None


def printed_dates(region: str, spans, kind: str, years: set[int]) -> list[tuple[date, str, int, int]]:
    """Every accepted (date, form, start, end) in a title region, version 1 and 2 forms together."""
    found = []
    for rx, how in ((BRACKET, "bracket"), (ASSENT, "assent")):
        for m in rx.finditer(region):
            d = to_date(m.group(1), m.group(2), m.group(3))
            if d and d.year in years:
                found.append((d, how, m.start(), m.end()))
    forms = [(ASSENTED, "assent"), (ASSENT2, "assent")]
    if kind in PROMULGATING:
        forms.append((PROMULGATED, "promulgation"))
    if kind in SUBORDINATE:
        forms += [(PLACE_DATE, "notification_date"), (NO_DATED, "notification_date")]
    for rx, how in forms:
        for m in rx.finditer(region):
            if how == "notification_date" and PUBLICATION_BEFORE.search(region[max(0, m.start() - 40):m.start()]):
                continue      # 'THE SIND GOVERNMENT GAZETTE KARACHI, 11TH AUGUST, 1977' is the issue's masthead
            d = match_date(m)
            if d and d.year in years:
                found.append((d, how, m.start(), m.end()))
    for s, e, _bid, _page in spans:
        if s >= len(region):
            break
        line = region[s:min(e, len(region))]
        m = DATE_LINE.match(line)
        before = region[max(0, s - 80):s]
        if m and PUBLICATION_BEFORE.search(before):
            continue          # the tail of '[Gazette of Sind, Extraordinary, dated the 26th March, 1991]'
        if m and kind in ("act", "ordinance") and (re.match(r"\s*\[?\s*Dated", line, re.I)
                                                   or re.search(r"\bdated\s*(?:the)?\s*[,:]?\s*$", before, re.I)):
            continue          # 'Dated 24th September, 1984.' on an Act or Ordinance is its publication
        if m:
            d = match_date(m) if len(m.groups()) >= 6 else to_date(m.group(1), m.group(2), m.group(3))
            if d and d.year in years:
                found.append((d, "date_line", s, min(e, len(region))))
    return [f for f in found if date(1800, 1, 1) <= f[0] <= date.today()]


def number_years(region: str, kind: str, year: int) -> set[int]:
    """The instrument's year, plus -- for an Act or Ordinance -- the year of its own printed number when the region
    prints exactly one. Not for subordinate instruments: their title region cites the enabling Act's number."""
    if kind not in ("act", "ordinance"):
        return {year}
    ys = {int(m.group(3)) for m in WITH_KIND.finditer(region)
          if m.group(1).lower() == kind}
    # a number far from the instrument's year is another law's ('PRESIDENT's ACT No. VI of 1957' above a 1931 Act)
    return {year} | (ys if len(ys) == 1 and abs(next(iter(ys)) - year) <= NUMBER_YEAR_GAP else set())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dump")
    ap.add_argument("--raw-text", action="store_true",
                    help="read the extracted blocks without the page-read corrections (the pre-D-092 behaviour)")
    args = ap.parse_args()
    from tools.title_region_text import corrected, load_corrections
    from nizam.storage.db import connect
    counts = dict(considered=0, recorded=0, none_printed=0, ambiguous=0, unchanged=0, portal_agrees=0,
                  portal_disagrees=0)
    dumped, ambiguous = [], []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.document_id, i.kind::text,
                              i.year, i.source_start_block_id, i.source_end_block_id, o.source_metadata->>'date'
                         FROM v_release_instrument i JOIN source_observation o ON o.id = i.source_observation_id
                        WHERE i.year IS NOT NULL""")
        todo = cur.fetchall()
        cur.execute("""SELECT source_observation_id, expression_ordinal, value FROM v_instrument_metadata_current
                        WHERE field = 'enacted_on'""")
        standing = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        withdrawn = latest_withdrawn(cur, "enacted_on")
        # the one exception to 'never re-assert a withdrawn key': a key THIS method version withdrew itself on
        # recheck (basis recheck_not_reproduced) may be re-asserted when this version reproduces a date again.
        # A person's withdrawal, or another method's, still stands for good.
        cur.execute("""SELECT source_observation_id, expression_ordinal FROM (
                           SELECT DISTINCT ON (source_observation_id, expression_ordinal) *
                             FROM instrument_metadata_assertion WHERE field = 'enacted_on'
                            ORDER BY source_observation_id, expression_ordinal, recorded_at DESC, id DESC) l
                        WHERE assertion = 'withdrawn' AND basis = 'recheck_not_reproduced' AND method = %s""",
                    (METHOD,))
        withdrawn -= {(r[0], r[1]) for r in cur.fetchall()}
        corrections = {} if args.raw_text else load_corrections(cur)      # D-092: the text as page-read
        for iid, obs, ordinal, doc, kind, year, start, end, portal in todo:
            counts["considered"] += 1
            if (obs, ordinal) in withdrawn:
                continue
            cur.execute("""SELECT t.id, t.page_no, coalesce(t.text, '') FROM text_block t
                            WHERE t.document_id = %s AND t.id >= %s AND t.id <= coalesce(%s, t.id)
                            ORDER BY t.id LIMIT %s""", (doc, start, end, BLOCKS))
            blocks, n_corr = corrected(cur.fetchall(), corrections.get(obs, []))
            if n_corr:
                counts["read_with_corrections"] = counts.get("read_with_corrections", 0) + 1
            region, spans, stop = title_region(blocks)
            years = number_years(region, kind, year)
            found = printed_dates(region, spans, kind, years)
            if kind in SUBORDINATE and DRAFT.search(region):
                found = []
                counts["draft_refused"] = counts.get("draft_refused", 0) + 1
            # v2 precedence: the most direct statement present decides; it must give exactly one date
            others = []
            if found:
                top = min(RANK[f[1]] for f in found)
                others = sorted({f"{f[0]} {f[1]}" for f in found if RANK[f[1]] > top and
                                 f[0] not in {g[0] for g in found if RANK[g[1]] == top}})
                found = [f for f in found if RANK[f[1]] == top]
            dates = {f[0] for f in found}
            if len(dates) != 1:
                counts["none_printed" if not dates else "ambiguous"] += 1
                if args.dump and dates:
                    ambiguous.append(dict(document_id=doc, kind=kind, year=year,
                                          dates=sorted({f"{f[0]} {f[1]}" for f in found})))
                if (obs, ordinal) in standing:   # an earlier, looser run asserted one; the current rules do not
                    withdraw(cur, obs, ordinal, "enacted_on", METHOD,
                             "not reproduced by the current title-region rules")
                    counts["withdrawn_on_recheck"] = counts.get("withdrawn_on_recheck", 0) + 1
                continue
            d = dates.pop()
            value = d.isoformat()
            if standing.get((obs, ordinal)) == value:
                counts["unchanged"] += 1; continue
            first = min(found, key=lambda f: f[2])
            how = first[1]
            basis = {"assent": "printed_assent_statement",
                     "promulgation": "printed_promulgation_statement",
                     "notification_date": "printed_notification_date",
                     "date_line": "printed_date_line_under_title"}.get(how) or \
                KIND_BASIS.get(kind, "printed_date_under_title")
            quote = " ".join(region[max(0, first[2] - 30):first[3] + 5].split())
            bid, page = next(((b, p) for s, e, b, p in spans if s <= first[2] < e), (blocks[0][0], blocks[0][1]))
            portal_iso = None
            if portal:
                m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", portal.strip())
                portal_iso = portal.strip() if m else None
            if portal_iso:
                counts["portal_agrees" if portal_iso == value else "portal_disagrees"] += 1
            evidence = dict(reviewer_type="tool", kind=kind, year=year, form=how,
                            forms_agreeing=sorted({f[1] for f in found}),
                            lower_forms_disagree=others or None,
                            year_from_printed_number=(d.year != year) or None,
                            catalogue_date=portal, catalogue_date_agrees=(portal_iso == value) if portal_iso else None)
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'enacted_on', %s, 'asserted', %s, %s, %s, %s, %s, %s::jsonb, 'claude')""",
                        (obs, ordinal, value, basis, bid, page, quote, METHOD, json.dumps(evidence)))
            counts["recorded"] += 1
            dumped.append(dict(document_id=doc, kind=kind, year=year, value=value, basis=basis, quote=quote,
                               catalogue=portal))
        if not args.apply:
            conn.rollback()
    if args.dump:
        Path(args.dump).write_text(json.dumps(dict(recorded=dumped, ambiguous=ambiguous), ensure_ascii=False,
                                              indent=0), encoding="utf-8")
    print(json.dumps(counts, indent=1))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
