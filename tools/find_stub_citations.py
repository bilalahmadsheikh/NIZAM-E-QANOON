"""Citable sections whose text lives in a sibling that cannot be cited.

INV-4 says provisions are the citable unit. A section can satisfy that
formally -- the label exists, `operative_provision` resolves it, a citation
renders -- and still hand the reader nothing, because the parser split one
printed section into two siblings and the S7 adjudicator kept the wrong one.

The mechanism is the right-margin gazette layout. The printed marginal note
("Criminal misconduct") arrives as its own block; the segmenter builds it as a
section; the real body ("5. (1) A public servant is said to commit the offence
of criminal misconduct...") becomes a second sibling with the same label. S7
flags that as `repeated_sibling_label`, proposes `retype_non_citable`, and the
machine adjudicator accepts -- keeping the note, burying the body. All 8,518
S7 decisions in the corpus are `accept_non_citable`; none is `restore_citable`,
`reparent` or `split_instrument`, though the schema admits all five.

What that costs, measured on the released set:

    Prevention of Corruption Act 1947 s.5   citable text: "Criminal misconduct
                                            5A."          uncitable: 4,272 ch
    Usurious Loans Act 1918 s.3             "Re-opening of transactions"
                                                          uncitable: 4,223 ch
    Explosives Act 1884 s.2                 the commencement clause
                                                          uncitable: 5,123 ch

The label is citable in every one of these. That matters, because
``s7_citability_check.py`` asks exactly that question -- "is the printed label
still reachable as a section?" -- and concludes a demotion "removed a duplicate
and cost nothing" whenever a same-label sibling survives. It is right that no
citation was destroyed, and it is why the corpus reports clean here. The two
tools are not redundant: this one asks what the surviving citation is worth.

So the question here is the next one. Does the citable node actually carry the
provision, or does a same-label sibling that nobody can cite carry it instead?

    ./nz stub-citations
    ./nz stub-citations --released-only --show 40
    ./nz stub-citations --document 2692

Reads only. Proposes nothing; the repair is a parser fix plus a superseding
adjudication, both of which belong in their own tools.
"""
from __future__ import annotations

import argparse

from nizam.storage.db import connect

# One row per accepted `retype_non_citable` whose provision is still active,
# with the size of what was retyped and the size of the same-label section
# that stayed citable. `path <@ p.path` includes p itself, which is what we
# want: the node's own blocks count toward the text it carries.
PAIRS = """
WITH decided AS (
  SELECT DISTINCT c.candidate_provision_id AS pid, c.instrument_id,
         c.document_id, c.printed_label
    FROM segmentation_structural_adjudication a
    JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
   WHERE a.resolution = 'accept_non_citable'
), sized AS (
  SELECT d.*, p.path, p.first_page,
         (SELECT count(*) FROM provision x
           WHERE x.instrument_id = d.instrument_id AND x.is_active
             AND x.path <@ p.path AND x.id <> p.id) AS kids,
         (SELECT coalesce(sum(pb.chars), 0) FROM provision x
            JOIN provision_block pb ON pb.provision_id = x.id
           WHERE x.instrument_id = d.instrument_id AND x.is_active
             AND x.path <@ p.path) AS retyped_chars,
         (d.instrument_id IN (SELECT id FROM v_release_instrument)) AS released
    FROM decided d
    JOIN provision p ON p.id = d.pid AND p.is_active
)
SELECT s.document_id, s.printed_label, s.first_page, s.kids, s.retyped_chars,
       s.released, left(coalesce(i.short_title, ''), 40),
       coalesce((
         SELECT max((SELECT coalesce(sum(pb.chars), 0) FROM provision y
                       JOIN provision_block pb ON pb.provision_id = y.id
                      WHERE y.instrument_id = s.instrument_id AND y.is_active
                        AND y.path <@ t.path))
           FROM provision t
          WHERE t.instrument_id = s.instrument_id AND t.is_active
            AND t.kind::text IN ('section', 'article')
            AND regexp_replace(lower(t.label), '[^a-z0-9]', '', 'g')
              = regexp_replace(lower(s.printed_label), '[^a-z0-9]', '', 'g')
       ), 0) AS retained_chars
  FROM sized s
  JOIN instrument i ON i.id = s.instrument_id
 WHERE s.retyped_chars >= %s
"""


def verdict(retained: int, retyped: int) -> str:
    """How much of the provision the citable node actually carries."""
    if retained >= retyped:
        return "sound"
    if retained >= retyped * 0.5:
        return "comparable"
    if retained >= 200:
        return "thin"
    return "stub"


ORDER = ["stub", "thin", "comparable", "sound"]
LEGEND = {
    "stub": "citable node under 200 chars - the text is in the retyped sibling",
    "thin": "citable node much smaller than the retyped sibling",
    "comparable": "citable node smaller but the same order of size",
    "sound": "citable node carries at least as much - retype was right",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-chars", type=int, default=500,
                    help="ignore retyped nodes smaller than this (default 500)")
    ap.add_argument("--released-only", action="store_true")
    ap.add_argument("--document", type=int, help="only this document")
    ap.add_argument("--show", type=int, default=25)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(PAIRS, (a.min_chars,))
        rows = cur.fetchall()

    items = []
    for doc, label, page, kids, retyped, released, title, retained in rows:
        if a.released_only and not released:
            continue
        if a.document is not None and doc != a.document:
            continue
        items.append({"doc": doc, "label": label, "page": page, "kids": kids,
                      "retyped": retyped, "retained": retained,
                      "released": released, "title": title,
                      "verdict": verdict(retained, retyped)})

    if not items:
        print("no accepted retypes above the size threshold")
        return 0

    print(f"retyped nodes of {a.min_chars}+ chars : {len(items)}")
    for name in ORDER:
        group = [i for i in items if i["verdict"] == name]
        if not group:
            continue
        rel = sum(1 for i in group if i["released"])
        docs = len({i["doc"] for i in group})
        print(f"  {name:<11} {len(group):>5} units  {docs:>4} documents  "
              f"{rel:>4} released   {LEGEND[name]}")

    bad = [i for i in items if i["verdict"] in ("stub", "thin")]
    print(f"\ncitations that resolve to less than half the provision : "
          f"{len(bad)} in {len({i['doc'] for i in bad})} documents "
          f"({sum(1 for i in bad if i['released'])} released)")

    bad.sort(key=lambda i: (-i["retyped"] + i["retained"]))
    print(f"\n{'doc':>6} {'lbl':<5} {'pg':>4} {'kids':>5} "
          f"{'citable':>8} {'uncitable':>10}  rel  title")
    for i in bad[:a.show]:
        print(f"{i['doc']:>6} {str(i['label'])[:5]:<5} {i['page'] or 0:>4} "
              f"{i['kids']:>5} {i['retained']:>8} {i['retyped']:>10}  "
              f"{'y' if i['released'] else '.':^3}  {i['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
