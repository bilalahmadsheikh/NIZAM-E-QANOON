"""Why each pending contents gap is a gap, counted over the whole queue.

Reading pages finds real defects but one at a time, and the three found that
way so far were worth 2, 5 and 16 gaps. The queue is 1,000. This asks the same
question the reading asks -- where is the promised section, and what shape is it
printed in -- but of every gap at once, so the classes can be ranked before any
parser change is attempted.

It rests on C5 = 0: every character of every PDF is in a `text_block`, so the
raw blocks can be searched directly rather than the tree, which is the thing in
question. For each pending gap it looks for the promised label at the start of a
non-contents block and reports the form it found:

  period            "23. Unless a work"      the form the grammar already reads
  fused_subsection  "23(1). Unless a work"   landed today, tight form only
  spaced_subsection "23 (1) Unless a work"   left alone -- collides in compendiums
  periodless        "23 Unless a work"       needs contents corroboration
  bracket_amend     "1[23. Unless a work"    an amendment bracket ahead of it
  heading_only      the promised HEADING appears, the label does not
  absent            neither label nor heading appears outside the contents

`period` is the interesting one: the label IS printed in the ordinary form and
the tree still lacks it, so the defect is elsewhere -- a boundary, a demotion,
or a parent. Those need reading; the rest are grammar.

    ./nz gap-causes
    ./nz gap-causes --show 12 --class periodless

Reads only.
"""
from __future__ import annotations

import argparse
import collections
import re

from nizam.storage.db import connect

GAPS = """
SELECT g.toc_entry_id, i.document_id, e.printed_label, e.printed_heading,
       i.id::text, left(coalesce(i.short_title,''), 34),
       (SELECT count(*) FROM v_toc_gap_pending g2
         WHERE g2.instrument_id = i.id) AS gaps_here
  FROM v_toc_gap_pending g
  JOIN instrument i ON i.id = g.instrument_id
  JOIN instrument_toc_entry e ON e.id = g.toc_entry_id
 ORDER BY i.document_id
"""

BLOCKS = """
SELECT tb.text,
       coalesce((SELECT pb.role::text FROM provision_block pb
                  WHERE pb.block_id = tb.id LIMIT 1), 'unassigned')
  FROM text_block tb WHERE tb.document_id = %s
"""


def norm_label(label: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", label or "").upper()


def forms(label: str) -> list[tuple[str, re.Pattern]]:
    """Patterns that would open a section carrying this printed label."""
    lit = re.escape(label.strip())
    # tolerate the spacing the extractor introduces inside a label
    loose = r"\s*".join(re.escape(ch) for ch in label.strip() if not ch.isspace())
    return [
        ("period", re.compile(rf"^\s*(?:\d{{0,3}}\s*\[\s*)?{loose}\s*\.", re.I)),
        ("fused_subsection", re.compile(rf"^\s*{loose}\s*\(\s*1\s*\)", re.I)),
        ("bracket_amend", re.compile(rf"^\s*[\d*†]{{0,3}}\s*\[\s*{loose}\b", re.I)),
        ("periodless", re.compile(rf"^\s*{loose}\s+\S", re.I)),
        ("anywhere_at_start", re.compile(rf"^\s*{lit}", re.I)),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--class", dest="klass", help="list gaps in this class")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(GAPS)
        gaps = cur.fetchall()

    by_doc: dict[int, list] = collections.defaultdict(list)
    for row in gaps:
        by_doc[row[1]].append(row)

    tally = collections.Counter()
    examples: dict[str, list] = collections.defaultdict(list)

    with connect() as conn, conn.cursor() as cur:
        for n, (doc, rows) in enumerate(sorted(by_doc.items()), 1):
            cur.execute(BLOCKS, (doc,))
            blocks = cur.fetchall()
            body = [t for t, role in blocks if role != "contents" and t]
            contents = [t for t, role in blocks if role == "contents" and t]
            for entry_id, _d, label, heading, _iid, title, gaps_here in rows:
                verdict = "absent"
                hit = ""
                # Take the block whose text also supports the promised heading
                # where one exists, not merely the first block carrying the
                # label. Document 1117 is why: its contents promises section 12
                # "Consequences of de-registration" and its SCHEDULE prints
                # "12. Welfare of the aged and infirm.", so first-match reported
                # the section as found in the ordinary form when the schedule
                # row is all that was there. Eight of that document's gaps read
                # that way.
                hk = re.sub(r"[^a-z0-9]", "", (heading or "").lower())[:40]
                for name, pat in forms(label):
                    hits = [t for t in body if pat.match(t.strip())]
                    if not hits:
                        continue
                    agreeing = [
                        t for t in hits
                        if len(hk) >= 10
                        and hk[:24] in re.sub(r"[^a-z0-9]", "", t.lower())
                    ]
                    match = (agreeing or hits)[0]
                    verdict = name if agreeing or len(hk) < 10 else name + "_other"
                    hit = " ".join(match.split())[:72]
                    break
                if verdict in ("absent", "anywhere_at_start"):
                    hk = re.sub(r"[^a-z0-9]", "", (heading or "").lower())
                    if len(hk) >= 12:
                        found = next(
                            (t for t in body
                             if hk in re.sub(r"[^a-z0-9]", "", t.lower())), None)
                        if found is not None:
                            verdict = "heading_only"
                            hit = " ".join(found.split())[:72]
                        elif any(hk in re.sub(r"[^a-z0-9]", "", t.lower())
                                 for t in contents):
                            verdict = "absent"
                tally[verdict] += 1
                if len(examples[verdict]) < 400:
                    examples[verdict].append((doc, label, gaps_here, title,
                                              heading or "", hit))
            if n % 60 == 0:
                print(f"  {n}/{len(by_doc)} documents", flush=True)

    total = sum(tally.values())
    print(f"\npending contents gaps : {total}\n")
    print(f"{'class':<20} {'gaps':>6} {'share':>7}  what it means")
    meaning = {
        "period": "label AND heading printed plainly -- the tree simply missed it",
        "period_other": "label printed plainly but the heading differs -- often a schedule row",
        "periodless_other": "periodless label, heading differs",
        "bracket_amend_other": "bracketed label, heading differs",
        "fused_subsection": "23(1). -- landed today, tight form only",
        "periodless": "23 Unless -- needs contents corroboration",
        "bracket_amend": "1[23. -- amendment bracket ahead of the number",
        "heading_only": "heading printed, label is not",
        "absent": "neither label nor heading outside the contents",
        "anywhere_at_start": "label opens a block in some other shape",
    }
    for name, count in tally.most_common():
        print(f"{name:<20} {count:>6} {100.0*count/total:>6.1f}%  "
              f"{meaning.get(name,'')}")

    if a.klass:
        rows = examples.get(a.klass, [])
        print(f"\n{a.klass} ({len(rows)} shown of {tally[a.klass]}):")
        for doc, label, gaps_here, title, heading, hit in rows[:a.show or 20]:
            print(f"  doc {doc:>5} label {str(label)[:6]:<6} gaps={gaps_here:<3} "
                  f"{title}")
            print(f"        promised: {heading[:64]}")
            if hit:
                print(f"        found   : {hit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
