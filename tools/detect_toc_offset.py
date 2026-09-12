"""Find instruments whose contents list is numbered one ahead of its body.

Five source pages read so far show the same shape. A contents page that lists
"Preamble." as its first row, or a long title, numbers everything after it one
higher than the body does:

    contents 3. Repeal of Sindh Ordinance X of 2002.   body: section 2
    contents 8. Power to make rules.                   body: section 7
    contents 9. Repeal of Sindh Ordinance XVII of 2006 body: section 8

Nothing is missing from those statutes. But the parser links contents row k to
body section k, so every heading lands on the section before the right one, the
last contents row matches nothing, and that row becomes a permanent gap. It also
means heading matching cannot repair it: with all headings shifted, none agrees.

The offset is measurable without reading anything. Compare how well the printed
headings agree with the body at offset 0 against offset 1, using the body's own
first words. A document numbered correctly agrees best at 0; one of these agrees
far better at 1.

Reads only; writes nothing.
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher

from nizam.storage.db import connect

SQL = """
SELECT i.id::text, i.document_id, i.short_title,
       (SELECT count(*) FROM v_toc_gap_pending v WHERE v.instrument_id = i.id) AS gaps,
       e.ordinal, e.printed_label, e.printed_heading,
       p.label, p.heading, left(coalesce(pv.text_en, ''), 120) AS body_text
  FROM instrument i
  JOIN instrument_toc_entry e ON e.instrument_id = i.id
  LEFT JOIN provision p ON p.instrument_id = i.id AND p.is_active
                       AND p.kind IN ('section','article')
                       AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g')
                           = regexp_replace(lower(e.printed_label), '[^a-z0-9]', '', 'g')
  LEFT JOIN LATERAL (
     SELECT text_en FROM provision_version v2
      WHERE v2.provision_id = p.id ORDER BY v2.created_at DESC LIMIT 1
  ) pv ON true
 WHERE i.is_active AND i.duplicate_of IS NULL
   AND EXISTS (SELECT 1 FROM v_toc_gap_pending v WHERE v.instrument_id = i.id)
 ORDER BY i.id, e.ordinal
"""


def norm(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def agreement(pairs: list[tuple[str, str]]) -> float:
    """How well printed headings match the body units they are paired with."""
    scored = [SequenceMatcher(None, a, b[:len(a) + 10]).ratio()
              for a, b in pairs if a and b]
    return sum(scored) / len(scored) if scored else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-entries", type=int, default=4)
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = cur.fetchall()

    by_instrument: dict[str, list] = {}
    meta: dict[str, tuple] = {}
    for (iid, document_id, title, gaps, ordinal, printed_label,
         printed_heading, label, heading, body_text) in rows:
        by_instrument.setdefault(iid, []).append(
            (ordinal, printed_heading, heading, body_text))
        meta[iid] = (document_id, title, gaps)

    offset_docs = []
    for iid, entries in by_instrument.items():
        entries.sort(key=lambda item: item[0])
        if len(entries) < a.min_entries:
            continue
        # offset 0: printed heading k against the body unit it was linked to.
        at_zero = [(norm(printed), norm(body))
                   for _o, printed, _h, body in entries]
        # offset 1: printed heading k against the body unit one earlier.
        at_one = [(norm(entries[i][1]), norm(entries[i - 1][3]))
                  for i in range(1, len(entries))]
        zero, one = agreement(at_zero), agreement(at_one)
        if one > zero + 0.12 and one >= 0.45:
            document_id, title, gaps = meta[iid]
            offset_docs.append((one - zero, document_id, title, gaps, zero, one))

    offset_docs.sort(reverse=True)
    total_gaps = sum(item[3] for item in offset_docs)
    print(f"instruments whose contents reads one ahead of its body: "
          f"{len(offset_docs)}")
    print(f"contents gaps sitting in them: {total_gaps}\n")
    for delta, document_id, title, gaps, zero, one in offset_docs[:a.show]:
        print(f"  doc {document_id:<6} gaps {gaps:>3}  "
              f"agreement {zero:.2f} -> {one:.2f} (+{delta:.2f})  "
              f"{(title or '')[:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
