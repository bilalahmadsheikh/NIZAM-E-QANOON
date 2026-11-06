"""Close contents gaps whose promised section IS in the tree under the same number -- the row simply was not linked.

tools/triage_toc_gaps.py class (a): 'label already a section -- contents row simply not linked'. The contents promises
'12. Repeal.'; the body prints section 12; the segmenter did not attach the contents row to it (a typography or
heading-spelling difference). No law is absent. tools/adjudicate_toc_found_elsewhere.py deliberately leaves this shape
alone (it decides differently-numbered sections); this decides the same-numbered one, with two guards:

  * exactly ONE active section or article of the same instrument carries the printed label (folded), and
  * where both the contents row and that section print a heading, they agree: at least half of the contents
    heading's words occur in the section's heading or marginal note. A contents page and body numbered
    differently would otherwise be linked to the wrong law.

Recorded as `found_elsewhere` with `found_provision_id` -- the section the row describes -- which the database can
check; no page reading is claimed. Dry run by default.

    python tools/adjudicate_toc_same_label.py            report
    python tools/adjudicate_toc_same_label.py --apply    record
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nizam.storage.db import connect  # noqa: E402

DECIDED_BY = "claude.toc-same-label/1"
METHOD = "the printed label is exactly one section of the instrument, and its heading agrees"

SQL = """
SELECT g.toc_entry_id, g.document_id, g.instrument_id::text, g.printed_label, g.printed_heading, g.source_page,
       (SELECT array_agg(p.id::text || '|' || coalesce(p.heading,'') || '|' || coalesce(p.marginal_note,'')
                         || '|' || coalesce(p.first_page::text,'') || '|' || p.kind::text)
          FROM provision p
         WHERE p.instrument_id = g.instrument_id AND p.is_active AND p.kind IN ('section','article')
           AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g')
             = regexp_replace(lower(g.printed_label), '[^a-z0-9]', '', 'g')) AS matches
  FROM v_toc_gap_pending g
 WHERE g.toc_entry_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication prior
                    WHERE prior.toc_entry_id = g.toc_entry_id AND prior.resolution = 'found_elsewhere')
"""


def words(s: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in {"the", "and", "for", "with"}}


def agrees(printed: str | None, heading: str | None, note: str | None) -> bool:
    """Both sides must print a heading and they must agree. A missing heading on either side decides nothing:
    on the 20 Oct recrawl, running headers read as contents rows ('1898 ] Central Provinces Tenancy. 463') and
    bogus year-sections ('section 1898') would otherwise link."""
    want = words(printed)
    have = words(heading) | words(note)
    if not want or not have:
        return False
    return len(want & have) * 2 >= len(want)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = cur.fetchall()
        decided, skipped = [], {"no section": 0, "several sections": 0, "headings disagree": 0}
        for entry, doc, inst, label, printed, page, matches in rows:
            matches = matches or []
            if not matches:
                skipped["no section"] += 1; continue
            if len(matches) > 1:
                skipped["several sections"] += 1; continue
            pid, heading, note, first_page, kind = matches[0].split("|", 4)
            if not agrees(printed, heading, note):
                skipped["headings disagree"] += 1; continue
            decided.append((entry, doc, inst, label, printed, page, pid, heading, first_page, kind))
        print(f"pending contents-entry gaps: {len(rows)}; decided {len(decided)}; left {skipped}")
        for d in decided[:10]:
            print(f"   doc {d[1]} contents {d[3]!r} {str(d[4])[:40]!r} -> section {d[3]} {d[7][:40]!r}")
        if not a.apply:
            print("dry run -- pass --apply to record"); return 0
        for entry, doc, inst, label, printed, page, pid, heading, first_page, kind in decided:
            cur.execute("""INSERT INTO toc_gap_adjudication
                             (instrument_id, document_id, toc_entry_id, printed_label, resolution, source_page,
                              evidence, rationale, decided_by)
                           VALUES (%s,%s,%s,%s,'found_elsewhere',%s,%s,%s,%s)""",
                        (inst, doc, entry, label, page,
                         json.dumps({"found_provision_id": pid, "body_label": label, "body_kind": kind,
                                     "body_first_page": first_page, "printed_heading": printed,
                                     "body_heading": heading, "method": METHOD, "reviewer_type": "assistant",
                                     "human_page_review": False}, ensure_ascii=False),
                         "The contents row's printed label is exactly one section of this instrument and its "
                         "heading agrees: the section is present and citable under the same number; only the link "
                         "from the contents row was missing. No page reading is claimed.", DECIDED_BY))
        conn.commit()
        print(f"recorded {len(decided)} decision(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
