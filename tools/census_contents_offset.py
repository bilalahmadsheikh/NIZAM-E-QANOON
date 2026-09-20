"""Corpus-wide scan for a contents list that runs at a constant offset to the body.

For each instrument carrying a printed contents list, each entry's HEADING is
looked for at the head of a body block that opens with a label.  The label the
BODY prints there, minus the label the CONTENTS prints, is the offset.  A run of
four or more consecutive entries sharing one non-zero offset is the proof the
queue asks for: it cannot arise from a single coincidental heading match.

Contents blocks are excluded two ways -- below the recorded body floor, and any
block a contents entry was read out of -- so a row cannot match itself.

Reads only.
"""
from __future__ import annotations

import collections
import os
import json
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nizam.storage.db import connect

OUT = os.environ.get("NIZAM_CENSUS_OUT", "")

LAB = re.compile(r"^\s*(?:\d{0,3}\s*\[\s*)?([0-9]{1,4})\s*[.)]?\s")
MIN_RUN = 4


def nk(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main() -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.id::text, i.document_id, left(i.short_title,48),
                   coalesce((SELECT r.body_starts_page FROM segmentation_run r
                              WHERE r.instrument_id=i.id ORDER BY r.id DESC LIMIT 1),1)
              FROM instrument i
             WHERE i.is_active AND i.duplicate_of IS NULL
               AND (SELECT count(*) FROM instrument_toc_entry e
                     WHERE e.instrument_id=i.id) >= 10
             ORDER BY i.document_id""")
        insts = cur.fetchall()
    print(f"instruments with a contents list of 10+ entries: {len(insts)}", flush=True)

    found = []
    with connect() as conn, conn.cursor() as cur:
        for n, (iid, doc, title, floor) in enumerate(insts, 1):
            cur.execute("""SELECT e.ordinal, e.printed_label, e.printed_heading,
                                  (e.provision_id IS NOT NULL)
                             FROM instrument_toc_entry e
                            WHERE e.instrument_id=%s ORDER BY e.ordinal""", (iid,))
            entries = cur.fetchall()
            cur.execute("""SELECT tb.page_no, tb.text
                             FROM text_block tb
                            WHERE tb.document_id=%s AND tb.page_no >= %s
                              AND tb.text ~ '^[[:space:]]*[0-9]{1,4}[[:space:]]*[.)]'
                              AND NOT EXISTS (SELECT 1 FROM instrument_toc_entry e2
                                               WHERE e2.source_block_id=tb.id)
                            ORDER BY tb.id""", (doc, floor))
            opens = []
            for pg, t in cur.fetchall():
                flat = " ".join((t or "").split())
                m = LAB.match(flat)
                if m:
                    opens.append((pg, int(m.group(1)), nk(flat[m.end():])[:60]))
            if not opens:
                continue
            seq = []
            for o, lab, head, linked in entries:
                # Compare the WHOLE printed heading, not a 26-character stem.
                # The Securities Act 2015 states the same rule twice, once for a
                # securities exchange and once for a clearing house, and the two
                # headings agree for 25 characters; a stem match invented two
                # "constant offsets" of -19 and -43 in that Act alone.
                h = nk(head)[:60]
                em = re.match(r"^(\d+)", (lab or "").strip())
                if len(h) < 16 or not em:
                    seq.append(None)
                    continue
                hit = next((x for x in opens if x[2].startswith(h)), None)
                if hit is None:
                    seq.append(None)
                    continue
                seq.append((o, int(em.group(1)), hit[1], hit[0], lab, head, linked))
            # maximal runs of one constant non-zero delta
            runs, cur_run = [], []
            for item in seq:
                if item is None:
                    continue
                d = item[2] - item[1]
                if cur_run and cur_run[-1][2] - cur_run[-1][1] == d:
                    cur_run.append(item)
                else:
                    if len(cur_run) >= MIN_RUN and cur_run[0][2] - cur_run[0][1] != 0:
                        runs.append(list(cur_run))
                    cur_run = [item]
            if len(cur_run) >= MIN_RUN and cur_run[0][2] - cur_run[0][1] != 0:
                runs.append(list(cur_run))
            for run in runs:
                d = run[0][2] - run[0][1]
                found.append({
                    "doc": doc, "instrument": iid, "title": title, "delta": d,
                    "entries_in_run": len(run),
                    "first_contents_label": run[0][4], "last_contents_label": run[-1][4],
                    "first_page": run[0][3], "last_page": run[-1][3],
                    "linked_in_run": sum(1 for r in run if r[6]),
                    "sample": [(r[4], r[2], r[5][:44]) for r in run[:4]],
                })
            if n % 400 == 0:
                print(f"  {n}/{len(insts)}", flush=True)

    if OUT:
        json.dump(found, open(OUT, "w"), indent=0)
    print(f"\nconstant-offset runs of {MIN_RUN}+ entries: {len(found)} "
          f"in {len({f['doc'] for f in found})} documents")
    print(f"contents entries inside those runs: {sum(f['entries_in_run'] for f in found)}; "
          f"of those, already linked to a provision: "
          f"{sum(f['linked_in_run'] for f in found)}")
    print(f"\n{'doc':>6} {'d':>4} {'n':>4} {'linked':>7}  labels        pages      title")
    for f in sorted(found, key=lambda f: -f["entries_in_run"])[:40]:
        print(f"{f['doc']:>6} {f['delta']:>+4} {f['entries_in_run']:>4} "
              f"{f['linked_in_run']:>7}  {f['first_contents_label']}-{f['last_contents_label']:<10} "
              f"p{f['first_page']}-{f['last_page']:<7} {f['title'][:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
