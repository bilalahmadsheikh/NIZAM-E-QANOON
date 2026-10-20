"""Copy a reviewed TOC disposition assertion onto a same-blob sibling observation (append-only).

    python tools/copy_toc_disposition.py --assertion 162 --observation 424 --reason "<approval ref>" [--apply]

WHY (docs 4501 and 2605, owner 12 Oct 2026). A disposition read on one observation's rendered contents page was
recorded on that observation only. Its byte-identical sibling then built a different tree (the omitted/repealed
section absent), never collapsed into an exact duplicate, and both stayed released. A disposition read on one copy
of the pages is a reading of every copy; this narrow path copies exactly the named assertion, nothing else.

Checks (refuse otherwise): the assertion is the LATEST, non-withdrawn assertion for its entry; the target is
another observation of the same document and the same blob, with an active canonical instrument at the same
expression whose contents entry at that ordinal prints the same label and heading from the same source block and
page (the 0045 trigger re-checks this). An identical latest assertion already on the target is skipped.
The copy keeps the review (reviewed_by, render artifact and sha, evidence) and adds
evidence.copied_from_assertion_id, copy_reason and copy_tool. Nothing is withdrawn or deleted.
"""
from __future__ import annotations

import argparse
import json
import sys

from nizam.storage.db import connect

TOOL = "tools/copy_toc_disposition.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assertion", type=int, action="append", required=True)
    ap.add_argument("--observation", type=int, required=True, help="the sibling observation to copy onto")
    ap.add_argument("--reason", required=True, help="the approval reference")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if len(" ".join(a.reason.split())) < 12:
        ap.error("--reason needs the approval reference")
    with connect() as conn, conn.cursor() as cur:
        done = 0
        for assertion_id in a.assertion:
            cur.execute("""SELECT a.id, a.source_observation_id, a.expression_ordinal, a.toc_entry_ordinal,
                                  a.printed_label, a.printed_heading, a.disposition, a.source_block_id,
                                  a.source_page, a.render_artifact, a.render_sha256, a.amending_instrument_id,
                                  a.amending_instrument_citation, a.evidence, a.reviewed_by
                             FROM v_toc_disposition_assertion_latest a WHERE a.id=%s""", (assertion_id,))
            row = cur.fetchone()
            if row is None:
                raise SystemExit(f"assertion {assertion_id} is not the latest standing assertion for its entry")
            (aid, obs, expr, ordinal, label, heading, disposition, block, page, artifact, sha, amending,
             citation, evidence, reviewed_by) = row
            if obs == a.observation:
                raise SystemExit(f"assertion {aid} is already on observation {obs}")
            cur.execute("""SELECT o.id, o.sha256 FROM source_observation o WHERE o.id = ANY(%s)""",
                        ([obs, a.observation],))
            blobs = dict(cur.fetchall())
            cur.execute("""SELECT DISTINCT document_id FROM instrument
                            WHERE source_observation_id = ANY(%s) AND is_active""", ([obs, a.observation],))
            documents = {r[0] for r in cur.fetchall()}
            if len(documents) != 1 or blobs.get(obs) is None or blobs.get(obs) != blobs.get(a.observation):
                raise SystemExit(f"observation {a.observation} is not a same-blob sibling of {obs} "
                                 f"(documents {sorted(documents)})")
            cur.execute("""SELECT e.id FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id
                            WHERE i.source_observation_id=%s AND i.expression_ordinal=%s
                              AND i.is_active AND i.duplicate_of IS NULL
                              AND e.ordinal=%s AND e.printed_label=%s AND e.printed_heading=%s
                              AND e.source_block_id=%s AND e.source_page=%s""",
                        (a.observation, expr, ordinal, label, heading, block, page))
            entries = [r[0] for r in cur.fetchall()]
            if len(entries) != 1:
                raise SystemExit(f"observation {a.observation}: {len(entries)} matching contents entries for "
                                 f"ordinal {ordinal} label {label!r} (needs exactly one, on a canonical instrument)")
            cur.execute("""SELECT id, disposition, source_block_id, source_page FROM v_toc_disposition_assertion_latest
                            WHERE source_observation_id=%s AND expression_ordinal=%s AND toc_entry_ordinal=%s""",
                        (a.observation, expr, ordinal))
            existing = cur.fetchone()
            if existing is not None and tuple(existing[1:]) == (disposition, block, page):
                print(f"assertion {aid} -> observation {a.observation}: already carried by assertion {existing[0]}")
                continue
            copied = dict(evidence or {}, copied_from_assertion_id=aid, copy_reason=" ".join(a.reason.split()),
                          copy_tool=TOOL)
            print(f"assertion {aid} (obs {obs}, label {label}, {disposition}, block {block} p{page}) -> observation "
                  f"{a.observation} entry {entries[0]}" + ("" if a.apply else "  [dry run]"))
            if a.apply:
                cur.execute("""
                    INSERT INTO toc_disposition_assertion
                        (source_observation_id,expression_ordinal,toc_entry_ordinal,reviewed_toc_entry_id,
                         printed_label,printed_heading,disposition,source_block_id,source_page,render_artifact,
                         render_sha256,amending_instrument_id,amending_instrument_citation,evidence,reviewed_by,
                         supersedes_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (a.observation, expr, ordinal, entries[0], label, heading, disposition, block, page, artifact,
                     sha, amending, citation, json.dumps(copied, ensure_ascii=False), reviewed_by,
                     existing[0] if existing is not None else None))
                print(f"  recorded assertion {cur.fetchone()[0]}")
                done += 1
        if a.apply:
            conn.commit()
        print(f"{'recorded' if a.apply else 'would record'} {done if a.apply else len(a.assertion)} copy(ies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
