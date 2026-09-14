"""Contents gaps whose section IS printed, in a shape the parser cannot read.

Three defects were found this session one document at a time, and all three had
the same signature: a block that OPENS with the promised label, whose text the
contents corroborates, and which ``classify()`` refuses.

    16 Zone approval criteria.- ...          no period after the number
    21.(1) Government may, by notification   no space after the period
    Power and Function of 4.  The follo...   the marginal note fused inline

Finding the fourth by reading documents in turn is slow. This does the sweep
instead: for every pending contents gap, look for a body block that begins with
the promised label, ask ``classify()`` what it makes of it, and group the
refusals by the SHAPE of the characters between the label and the text. Each
group is a candidate defect, with its size attached.

The grouping is what makes it useful. One block is an anecdote; forty blocks
sharing a separator are a rule worth writing, and the count says whether it is
worth the measurement a parser change costs.

Reads only.

    ./nz unrecognised-openers
    ./nz unrecognised-openers --show 12
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict

from nizam.corpus.segment import _classify_body, classify
from nizam.storage.db import connect

GAPS = """
SELECT g.document_id, g.printed_label, g.printed_heading
  FROM v_toc_gap_pending g
 WHERE g.printed_label ~ '^[0-9]'
   AND coalesce(btrim(g.printed_heading), '') <> ''
"""

BLOCKS = """
SELECT b.document_id, b.text
  FROM text_block b
 WHERE b.document_id = ANY(%s)
   AND NOT EXISTS (SELECT 1 FROM instrument_toc_entry e
                    WHERE e.source_block_id = b.id)
 ORDER BY b.document_id, b.reading_order
"""


def shape(separator: str) -> str:
    """A readable name for what sits between the label and the text."""
    if separator == "":
        return "nothing at all (label runs into the text)"
    if re.fullmatch(r"\.\s+", separator):
        return "period + space  (recognised; should not appear here)"
    if re.fullmatch(r"\.", separator):
        return "period, no space"
    if re.fullmatch(r"\s+", separator):
        return "space only, NO period"
    if re.fullmatch(r"\.\s*[-–—―]\s*", separator):
        return "period + dash"
    if re.fullmatch(r"[-–—―]\s*", separator):
        return "dash, no period"
    if re.fullmatch(r"[:)\]]\s*", separator):
        return "bracket or colon instead of a period"
    return f"other: {separator[:12]!r}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=6,
                    help="example blocks to print per shape")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(GAPS)
        gaps = cur.fetchall()
        documents = sorted({row[0] for row in gaps})
        cur.execute(BLOCKS, (documents,))
        blocks: dict[int, list[str]] = defaultdict(list)
        for document_id, text in cur.fetchall():
            blocks[document_id].append(text or "")

    groups: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    checked = 0
    for document_id, label, _heading in gaps:
        pattern = re.compile(r"^\s*" + re.escape(label.strip()) + r"(\D{0,4}?)(\S.*)$",
                             re.S)
        for text in blocks.get(document_id, []):
            match = pattern.match(text)
            if not match:
                continue
            checked += 1
            # Ask the question the parser actually asks. classify() alone is
            # the wrong test: the contents-corroborated rules live in
            # _classify_body, so checking classify() reports shapes that are
            # already handled -- it counted 245 refusals where the real number
            # is far smaller.
            if _classify_body(text, {label.strip(): _heading or ""}) is not None:
                break                       # the parser already reads this one
            groups[shape(match.group(1))].append(
                (document_id, label, " ".join(text.split())[:72]))
            break

    print(f"pending gaps with a numeric label        : {len(gaps)}")
    print(f"  a body block opens with that label     : {checked}")
    print(f"  ... and classify() refuses it          : "
          f"{sum(len(v) for v in groups.values())}\n")
    for name, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(rows):>4}  {name}")
        for document_id, label, text in rows[:a.show]:
            print(f"          doc {document_id:<6} {label:<6} {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
