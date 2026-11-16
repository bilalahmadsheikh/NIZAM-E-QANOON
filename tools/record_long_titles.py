"""Record each released instrument's printed long title (migration 0083, field long_title).

WHAT IS READ. The instrument's leading blocks (the same window as tools/record_instrument_numbers.py's title region),
for the long title the law prints under its short title and number:
    'AN ACT to provide for the establishment of the Balochistan Food Authority.'
    'AN ORDINANCE further to amend the Code of Criminal Procedure, 1898.'
    'An Act to amend the Indian Penal Code.'
It opens 'An Act|An Ordinance|An Order|A Regulation' followed by 'to', 'further to', 'for', 'relating to', 'so as
to', 'providing', 'making', 'whereby', and runs to the end of its sentence: a full stop or semicolon followed by
'WHEREAS', 'Preamble', 'It is hereby enacted', 'BE it enacted', a section 1, or the next sentence; at most 700
characters. Footnote markers ('1[Balochistan]') are kept as printed.

RECORDED ONLY WHEN exactly one distinct long title is printed there (a Gazette page that prints the notification
and the Act can print it twice; the same words twice is one title), it is 15-700 characters, and it is not a line of a
contents page or a citation inside the body ('... an Act to amend ...' after section 1 is never read: the window stops
at section 1 in body form). Rules, notifications and most orders print none; nothing is recorded for them.

    python tools/record_long_titles.py            # report
    python tools/record_long_titles.py --apply    # write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_instrument_numbers import BLOCKS, latest_withdrawn, withdraw  # noqa: E402

METHOD = "nizam.printed_long_title/1"
# a long contents page puts the long title past record_instrument_numbers' 80 blocks (KP Trust Act 2020, Sindh Local
# Government Act 2013); the window still ends at section 1 in body form, so a wider one reads no body text
WINDOW = 400
# capitalised as a title is ('AN ACT', 'An Act'): a body sentence citing 'an act for which ...' or 'an order for
# ejectment' is lower-case and is never read (found widening the window, 16 Nov 2026)
OPEN = re.compile(r"\b(?:AN|An|A)\s+(?:ACT|Act|ORDINANCE|Ordinance|ORDER|Order|REGULATION|Regulation)\s+"
                  r"(?:(?i:further)\s+)?(?i:to|for|so\s+as\s+to|relating\s+to|providing|making|whereby|in\s+order\s+to)\b")
# the sentence ends: before the preamble or enacting words (with or without the stop), or at a full stop that is not
# an abbreviation ('No. IX', 'Govt. of', 'W.P. Act') and is followed by anything but a lower-case word ('... Presidency.
# 1-18. [Repeals ...' ends at 'Presidency.'; an OCR stop inside the sentence, 'sums. in respect', does not)
END = re.compile(r"(?:[.;:]\s*|\s*,?\s*)(?=WHEREAS\b|Whereas\b|Preamble\b|PREAMBLE\b|It\s+is\s+hereby|"
                 r"IT\s+IS\s+HEREBY|BE\s+it\b|Be\s+it\b|It\s+is\s+(?:necessary|expedient)\b|"
                 r"W[A-Za-z]{3,8}\s+it\s+is\s+expedient)|"       # an OCR'd WHEREAS: 'WHLBEAS it is expedient'
                 r"(?<!\bNo)(?<!\bNos)(?<!\bOrd)(?<!\bGovt)(?<!\bArt)(?<!\bReg)(?<!\bSec)(?<!\bW\.P)(?<!\bSt)"
                 r"(?<!\bVol)(?<!\bCo)(?<!\bDr)(?<!\bMr)(?<!\bSh)(?<!\bPvt)(?<!\b[A-Z])\.\s*(?![a-z]|\d{2,4}\))|;\s*$")
# a title that ends on a function word or a fragment was cut, and one carrying '; (c)' took in a neighbouring column
# of a two-column Gazette scan ('An Act to control the manufacture ... ; (c) the manner in which applications ...')
CUT = re.compile(r"\b(?:the|thee|of|and|to|for|in|a|an|declaring|with|by|or)\.$", re.I)
COLUMN_BLEED = re.compile(r";\s*\([a-z]\)|\(\s*[a-z]\s*\)\s+the\s+(?:forms?|manner|conditions)\b|"
                          r"\bexpedient\b|hereby\s+enacted|\(\d{1,2}\)\s+[A-Z]|"
                          r"printed\s+by|printing|published\s+by|registered\s+no|\bgazette\b|extraordinary", re.I)
BODY_START = re.compile(r"(?:^|\s)1\.\s*(?:\(1\)\s*)?(?:This|These)\b|Short title[^.\n]{0,60}?[—–-]+\s*\(1\)")


def long_titles(text: str) -> list[tuple[str, int, int]]:
    """Every long title printed in `text` before section 1's body: (title, start, end)."""
    stop = BODY_START.search(text)
    window = text[:stop.start()] if stop else text
    out = []
    for m in OPEN.finditer(window):
        rest = text[m.start():m.start() + 700]
        e = END.search(rest, 12)
        if not e:
            continue
        t = " ".join(rest[:e.start()].split()).rstrip(";:,.- ")
        t += "."
        if CUT.search(t) or COLUMN_BLEED.search(t):
            continue
        if 25 <= len(t) <= 700:
            out.append((t, m.start(), m.start() + e.start() + 1))
    return out


def key(t: str) -> str:
    return re.sub(r"[^a-z]+", "", t.lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", type=int, default=20)
    args = ap.parse_args()
    from nizam.storage.db import connect
    counts: dict = {}
    shown = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.document_id, i.kind::text,
                              i.source_start_block_id, i.source_end_block_id
                         FROM v_release_instrument i""")
        todo = cur.fetchall()
        cur.execute("""SELECT source_observation_id, expression_ordinal, value FROM v_instrument_metadata_current
                        WHERE field = 'long_title'""")
        standing = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        withdrawn = latest_withdrawn(cur, "long_title")
        # as in record_enacted_dates.py: a key THIS method withdrew itself on recheck may be asserted again
        cur.execute("""SELECT source_observation_id, expression_ordinal FROM (
                           SELECT DISTINCT ON (source_observation_id, expression_ordinal) *
                             FROM instrument_metadata_assertion WHERE field = 'long_title'
                            ORDER BY source_observation_id, expression_ordinal, recorded_at DESC, id DESC) l
                        WHERE assertion = 'withdrawn' AND basis = 'recheck_not_reproduced' AND method = %s""",
                    (METHOD,))
        withdrawn -= {(r[0], r[1]) for r in cur.fetchall()}
        for iid, obs, ordinal, doc, kind, start, end in todo:
            if (obs, ordinal) in withdrawn:
                continue
            cur.execute("""SELECT t.id, t.page_no, coalesce(t.text, '') FROM text_block t
                            WHERE t.document_id = %s AND t.id >= %s AND t.id <= coalesce(%s, t.id)
                            ORDER BY t.id LIMIT %s""", (doc, start, end, WINDOW))
            blocks = cur.fetchall()
            found, text, spans = [], "", []
            # the first BLOCKS blocks decide; the wider WINDOW is read only when they print no long title (a second,
            # OCR-variant print further in must not unsettle a title the title region already prints once)
            for limit in (BLOCKS, WINDOW):
                text, spans = "", []
                for bid, page, btxt in blocks[:limit]:
                    spans.append((len(text), bid, page)); text += btxt + "\n"
                found = long_titles(text)
                if found:
                    break
            distinct = {key(t) for t, _s, _e in found}
            if len(distinct) != 1:
                why = "none_printed" if not distinct else "ambiguous"
                counts[why] = counts.get(why, 0) + 1
                if (obs, ordinal) in standing:
                    withdraw(cur, obs, ordinal, "long_title", METHOD, f"not reproduced: {why}")
                    counts["withdrawn_on_recheck"] = counts.get("withdrawn_on_recheck", 0) + 1
                continue
            title, s, _e = found[0]
            if standing.get((obs, ordinal)) == title:
                counts["unchanged"] = counts.get("unchanged", 0) + 1; continue
            bid, page = next(((b, p) for off, b, p in reversed(spans) if off <= s), (blocks[0][0], blocks[0][1]))
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'long_title', %s, 'asserted', 'printed_long_title', %s, %s, %s, %s,
                                   %s::jsonb, 'claude')""",
                        (obs, ordinal, title, bid, page, title[:300], METHOD,
                         json.dumps({"reviewer_type": "tool", "kind": kind, "printed_times": len(found)})))
            counts["recorded"] = counts.get("recorded", 0) + 1
            if len(shown) < args.show:
                shown.append(f"  {doc} {kind}: {title[:150]}")
        if not args.apply:
            conn.rollback()
    print(json.dumps(counts, indent=1))
    print("\n".join(shown))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
