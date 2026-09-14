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

DO NOT ACT ON `heading_only` WITHOUT READING THE PAGES FIRST. It is the largest
class at 304 of 958 and it is not trustworthy. It says the promised heading was
found outside the contents, but "outside the contents" is decided here from
`provision_block.role` plus the run's body floor, and a contents list whose rows
never linked has no role row at all. Document 308's page-2 list -- "35.
Acquisition lands.", "36. Contract water and water rates.", "38. Preferential
treatment." -- classifies as headings printed in the body under both rules.

A parser change was written for this class on 14 Sep 2026 -- admitting a bare
periodless opener as a candidate for the detached-heading pairing, which is the
real mechanism where it applies -- and measured against all 138 documents in
the class with `./nz diff-trees`: **0 sections gained, 0 lost, on every one**.
It was reverted. Whatever heading_only is counting, it is mostly not sections
whose number the grammar cannot read.

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
         WHERE g2.instrument_id = i.id) AS gaps_here,
       coalesce((SELECT r.body_starts_page FROM segmentation_run r
                  WHERE r.instrument_id = i.id
                  ORDER BY r.id DESC LIMIT 1), 1) AS body_page
  FROM v_toc_gap_pending g
  JOIN instrument i ON i.id = g.instrument_id
  JOIN instrument_toc_entry e ON e.id = g.toc_entry_id
 ORDER BY i.document_id
"""

# A block is "contents" if the ledger says so OR if a contents ENTRY was read
# out of it. The second arm matters: an entry whose row never linked leaves its
# block with no provision_block row at all, so role defaults to unassigned and
# the block reads as body. Document 308's page-2 contents list -- "35.
# Acquisition lands.", "36. Contract water and water rates.", "38. Preferential
# treatment." -- came through that way and put its own contents rows in the
# heading_only class, as headings "printed in the body".
BLOCKS = """
SELECT tb.text, tb.page_no,
       CASE WHEN EXISTS (SELECT 1 FROM instrument_toc_entry e
                          WHERE e.source_block_id = tb.id)
            THEN 'contents'
            ELSE coalesce((SELECT pb.role::text FROM provision_block pb
                            WHERE pb.block_id = tb.id LIMIT 1), 'unassigned')
       END
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
            # The contents REGION, not merely the blocks the ledger linked.
            # Document 308's page-2 list -- "35. Acquisition lands.", "36.
            # Contract water and water rates.", "38. Preferential treatment." --
            # has no provision_block row at all, so role defaults to unassigned
            # and every one of its own contents rows read as a heading "printed
            # in the body". That put 138 documents in heading_only and a parser
            # change built for them moved nothing, in either direction, on any
            # of the 138. The segmentation run already records where the body
            # starts; use it.
            floor = rows[0][7] or 1
            body = [t for t, pg, role in blocks
                    if t and role != "contents" and (pg or 1) >= floor]
            contents = [t for t, pg, role in blocks
                        if t and (role == "contents" or (pg or 1) < floor)]
            for entry_id, _d, label, heading, _iid, title, gaps_here, _bp in rows:
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
                    # A heading too short or too damaged to compare cannot
                    # corroborate anything, and calling those "corroborated"
                    # is how `period` first read as 228 and then 42 while
                    # still carrying "* * * *.", "................" and "11l"
                    # as its promised headings. Name that case instead.
                    if agreeing:
                        verdict = name
                    elif len(hk) < 10:
                        verdict = name + "_nohead"
                    else:
                        verdict = name + "_other"
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
