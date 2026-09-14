"""Contents entries that link to a provision holding no law.

The gap queue counts contents rows with NO link. It cannot see a row whose link
resolves to nothing, and 1,005 pending gaps is therefore a floor, not a total.
`find_stub_citations` asked this question of S7 retypes; this asks it of the
contents ledger, which is ten times larger.

Document 3523 is the shape of it. The contents promise section 8, *Costs of
determination of pollution level*. The entry links to a `section 8` node on
page 6 that carries **zero** blocks. The Act's real section 8 is block 400551
on page 3:

    8. Costs of determination of pollution level .- The industri...

and that block's role is `contents`. The contents boundary was set two pages
too late, so the body was absorbed into the contents region and never became
citable. Nothing is lost -- C4 and C5 both pass, every block is assigned -- and
nothing is citable either.

DO NOT measure this by comparing the printed heading to the linked node's text.
That was tried and produced 14,302 "disagreements" which were mostly correct
links: this corpus drops `s` characters in many documents, so `Treasurer.`
extracts as `trea urer` and trigram similarity collapses. `Acting Vice
Chancellor` scored below the threshold against a linked node reading `acting
vice chancellor 12 acting vice chancellor`. The test here is structural --
how much body text hangs beneath the linked node -- which that artefact cannot
reach.

    ./nz empty-citations
    ./nz empty-citations --released-only --show 30
    ./nz empty-citations --document 3523

Reads only.
"""
from __future__ import annotations

import argparse

from nizam.storage.db import connect

SQL = """
WITH linked AS (
  SELECT e.id, e.instrument_id, i.document_id, e.printed_label,
         e.printed_heading, p.id AS pid, p.path, p.first_page,
         (i.id IN (SELECT id FROM v_release_instrument)) AS released,
         left(coalesce(i.short_title, ''), 38) AS title
    FROM instrument_toc_entry e
    JOIN instrument i ON i.id = e.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
    JOIN provision p ON p.id = e.provision_id AND p.is_active
   WHERE e.entry_kind = 'section'
)
SELECT l.document_id, l.printed_label, l.printed_heading, l.first_page,
       l.released, l.title,
       (SELECT coalesce(sum(pb.chars), 0)
          FROM provision x
          JOIN provision_block pb ON pb.provision_id = x.id
         WHERE x.instrument_id = l.instrument_id AND x.is_active
           AND x.path <@ l.path
           AND pb.role::text IN ('body', 'heading')) AS body_chars,
       (SELECT count(*) FROM provision x
         WHERE x.instrument_id = l.instrument_id AND x.is_active
           AND x.path <@ l.path AND x.id <> l.pid) AS kids
  FROM linked l
"""

# A section whose printed text really is only a disposition marker is not a
# defect: "4 [Repealed.]" carries no law by design. Those are short AND say so.
DISPOSITION = ("repeal", "omit", "delet", "[ ]", "* *")


def verdict(body_chars: int, kids: int, heading: str | None) -> str:
    if body_chars >= 60:
        return "carries law"
    head = (heading or "").lower()
    if any(word in head for word in DISPOSITION):
        return "disposition marker, correctly empty"
    if body_chars == 0 and kids == 0:
        return "empty: no body text, no children"
    if body_chars == 0:
        return "no body text anywhere beneath it"
    return "under 60 characters of body"


ORDER = ["empty: no body text, no children", "no body text anywhere beneath it",
         "under 60 characters of body", "disposition marker, correctly empty",
         "carries law"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--released-only", action="store_true")
    ap.add_argument("--document", type=int)
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = cur.fetchall()

    items = []
    for doc, label, heading, page, released, title, body, kids in rows:
        if a.released_only and not released:
            continue
        if a.document is not None and doc != a.document:
            continue
        items.append({"doc": doc, "label": label, "heading": heading or "",
                      "page": page, "released": released, "title": title,
                      "body": body, "kids": kids,
                      "verdict": verdict(body, kids, heading)})

    if not items:
        print("no linked contents entries matched")
        return 0

    print(f"linked contents entries : {len(items)}")
    for name in ORDER:
        group = [i for i in items if i["verdict"] == name]
        if not group:
            continue
        print(f"  {name:<36} {len(group):>6}  "
              f"{len({i['doc'] for i in group}):>4} documents  "
              f"{sum(1 for i in group if i['released']):>6} released")

    bad = [i for i in items
           if i["verdict"] not in ("carries law",
                                   "disposition marker, correctly empty")]
    print(f"\ncitations that return no law : {len(bad)} in "
          f"{len({i['doc'] for i in bad})} documents "
          f"({sum(1 for i in bad if i['released'])} released)")

    bad.sort(key=lambda i: (i["body"], -len(i["heading"])))
    print(f"\n{'doc':>6} {'lbl':<6} {'pg':>4} {'body':>5}  rel  "
          f"{'the contents promises':<34} title")
    for i in bad[:a.show]:
        print(f"{i['doc']:>6} {str(i['label'])[:6]:<6} {i['page'] or 0:>4} "
              f"{i['body']:>5}  {'y' if i['released'] else '.':^3}  "
              f"{i['heading'][:34]:<34} {i['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
