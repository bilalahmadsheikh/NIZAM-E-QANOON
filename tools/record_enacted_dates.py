"""Record each released instrument's printed enactment date (migration 0070, field enacted_on).

WHAT IS READ. The instrument's own TITLE REGION (tools/record_instrument_numbers.py: its first <= 40 blocks, cut at
the long title / preamble / enacting formula / first section), for
  * the bracketed date printed under the title and number -- '[18th April, 1956]' -- which for an Act is the date
    of assent, for an Ordinance the date of promulgation, and for rules, regulations, orders and notifications the
    date they were made or notified; or
  * a printed assent statement -- 'Received the assent of the Governor General on the 6th October, 1860'.
The basis names which, and for which kind, so nobody reads a notification date as an assent date.

A DATE IS RECORDED ONLY WHEN it is a real calendar date, its year equals the instrument's year, and it is the ONLY
distinct such date in the title region. The source catalogue's date is NOT a source (placeholders such as
1869-12-31 and upload dates on Balochistan rules); where it happens to agree, that is noted in the evidence.

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

from record_instrument_numbers import (BLOCKS, latest_withdrawn, title_region,  # noqa: E402  (same title region)
                                       withdraw)

METHOD = "nizam.printed_enactment_date/1"
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


def to_date(day: str, month: str, year: str) -> date | None:
    m = MONTHS.get(month.lower().rstrip(".")) or ABBR.get(month.lower().rstrip("."))
    try:
        return date(int(year), m, int(day)) if m else None
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dump")
    args = ap.parse_args()
    from nizam.storage.db import connect
    counts = dict(considered=0, recorded=0, none_printed=0, ambiguous=0, unchanged=0, portal_agrees=0,
                  portal_disagrees=0)
    dumped = []
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
        for iid, obs, ordinal, doc, kind, year, start, end, portal in todo:
            counts["considered"] += 1
            if (obs, ordinal) in withdrawn:
                continue
            cur.execute("""SELECT t.id, t.page_no, coalesce(t.text, '') FROM text_block t
                            WHERE t.document_id = %s AND t.id >= %s AND t.id <= coalesce(%s, t.id)
                            ORDER BY t.id LIMIT %s""", (doc, start, end, BLOCKS))
            blocks = cur.fetchall()
            region, spans, stop = title_region(blocks)
            found = []
            for rx, how in ((BRACKET, "bracket"), (ASSENT, "assent")):
                for m in rx.finditer(region):
                    d = to_date(m.group(1), m.group(2), m.group(3))
                    if d and d.year == year:
                        found.append((d, how, m.start(), m.end()))
            dates = {f[0] for f in found}
            if len(dates) != 1:
                counts["none_printed" if not dates else "ambiguous"] += 1
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
            basis = ("printed_assent_statement" if how == "assent"
                     else KIND_BASIS.get(kind, "printed_date_under_title"))
            quote = " ".join(region[max(0, first[2] - 30):first[3] + 5].split())
            bid, page = next(((b, p) for s, e, b, p in spans if s <= first[2] < e), (blocks[0][0], blocks[0][1]))
            portal_iso = None
            if portal:
                m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", portal.strip())
                portal_iso = portal.strip() if m else None
            if portal_iso:
                counts["portal_agrees" if portal_iso == value else "portal_disagrees"] += 1
            evidence = dict(reviewer_type="tool", kind=kind, year=year, form=how,
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
        Path(args.dump).write_text(json.dumps(dumped, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps(counts, indent=1))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
