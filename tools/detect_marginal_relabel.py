"""Find sections the source misnumbers, whose marginal heading names the truth.

Document 732 page 14 prints "14." twice. The first is section 14 ("Registration
of an Institution."); the second is section 15 ("Registration and renewal fee"),
and the source simply misprints its number. The contents has it right. The
parser saw a repeated label, demoted the second to a clause, and section 15 left
the citable corpus -- while the contents row for 15 became a permanent gap.

The evidence is on the page, in two independent forms:

  * GEOMETRY. The marginal heading sits in a column far left of the body's
    (document 732: margin x0 127-149, body x0 234) and begins at the same y0 as
    the body block it heads -- 390 and 390 for "Registration and renewal fee".
  * THE CONTENTS. That heading is what the contents lists against 15, not 14.

Where both agree, the occurrence is section 15 however the page numbers it.

A marginal heading is usually broken across lines -- "Registration and" then
"renewal fee." as two blocks -- so the blocks in one y-band are stitched before
matching. Matching a single block silently finds almost nothing.

This only measures; it writes nothing and changes no tree.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from difflib import SequenceMatcher

from nizam.storage.db import connect

GEOMETRY = """
SELECT b.document_id, b.page_no, b.id, b.x0, b.x1, b.y0, b.text,
       c.x_left, c.x_body
  FROM text_block b
  JOIN document d ON d.id = b.document_id AND d.is_active
  JOIN (
    SELECT b2.document_id,
           percentile_disc(0.10) WITHIN GROUP (ORDER BY b2.x0) AS x_left,
           percentile_disc(0.50) WITHIN GROUP (ORDER BY b2.x0) AS x_body
      FROM text_block b2
      JOIN document d2 ON d2.id = b2.document_id AND d2.is_active
     GROUP BY b2.document_id
  ) c ON c.document_id = b.document_id
 WHERE b.document_id = ANY(%s) AND c.x_body - c.x_left >= 60
"""

GAPS = """
SELECT v.toc_entry_id, v.document_id, v.printed_label, v.printed_heading
  FROM v_toc_gap_pending v
 WHERE v.toc_entry_id IS NOT NULL
   AND coalesce(btrim(v.printed_heading), '') <> ''
"""

OPENER = re.compile(r"^\s*(\d{1,4})\s*\.")


def norm(value: str | None) -> str:
    return " ".join(re.sub(r"[^A-Za-z0-9 ]+", " ", (value or "")).lower().split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.86)
    ap.add_argument("--band", type=float, default=44.0,
                    help="how far below a body block's y0 a marginal line may sit")
    ap.add_argument("--show", type=int, default=14)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(GAPS)
        gaps = cur.fetchall()
        documents = sorted({row[1] for row in gaps})
        cur.execute(GEOMETRY, (documents,))
        blocks = cur.fetchall()

    # Split each page into the marginal column and the body column.
    margin: dict[tuple, list] = defaultdict(list)
    body: dict[tuple, list] = defaultdict(list)
    for document_id, page_no, _bid, x0, x1, y0, text, _x_left, x_body in blocks:
        if x0 is None or x1 is None or y0 is None:
            continue
        key = (document_id, page_no)
        # A marginal line is one that ends before the body column begins. Its
        # LEFT edge varies -- the second line of a heading is often indented
        # ("Registration and" at x0 127, "renewal fee." at 149) -- so keying on
        # x0 drops half of every wrapped heading and the match then fails.
        if x1 < x_body - 4:
            margin[key].append((float(y0), text))
        elif x0 >= x_body - 8:
            body[key].append((float(y0), text))

    # For every body block that opens a numbered provision, stitch the marginal
    # lines that sit in its band into one heading.
    headed: dict[int, list] = defaultdict(list)
    for key, entries in body.items():
        for y0, text in entries:
            opener = OPENER.match(text or "")
            if not opener:
                continue
            lines = sorted((my, mt) for my, mt in margin.get(key, [])
                           if -6 <= my - y0 <= a.band)
            if not lines:
                continue
            headed[key[0]].append(
                (opener.group(1), " ".join(t.strip() for _y, t in lines), key[1]))

    hits, mislabelled = 0, []
    for entry_id, document_id, label, heading in gaps:
        want = norm(heading)
        best = (0.0, None, None)
        for printed, margin_text, page_no in headed.get(document_id, []):
            score = SequenceMatcher(None, want, norm(margin_text)).ratio()
            if score > best[0]:
                best = (score, printed, page_no)
        if best[0] < a.threshold:
            continue
        hits += 1
        if best[1] != label:
            mislabelled.append((best[0], document_id, label, best[1], heading,
                                best[2]))

    print(f"gaps whose contents heading is printed in the marginal column: {hits}")
    print(f"  ... beside a body block the source numbers differently: "
          f"{len(mislabelled)}")
    print(f"  ... in {len({m[1] for m in mislabelled})} documents\n")
    for score, document_id, label, printed, heading, page_no in sorted(
            mislabelled, key=lambda v: -v[0])[:a.show]:
        print(f"  doc {document_id:<6} contents says {label:<5} "
              f"page prints {printed:<5} p{page_no:<4} match {score:.2f}")
        print(f"      {(heading or '')[:62]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
