"""Record an S7 decision from a page that was actually read.

Every one of the 8,518 S7 decisions in the corpus is `machine_evidenced`.
The schema has admitted `source_verified` since the table was created and
nothing has ever written it, which is why the queue cannot move: the machine
path reports 0 eligible once its own tests are exhausted, and the source path
has no instrument at all.

This is that instrument. It takes readings -- one per candidate, each naming
the rendered page it was read from and its SHA-256 -- and records them with
`review_basis = 'source_verified'`. It writes nothing without that evidence.

WHAT A READING HAS TO SAY. Not "accept" but what the page shows, in words, the
way migration 0050 requires of an assistant's `absent_in_source` assertion. The
rationale stored is the observation, not the conclusion.

THE STUB GUARD APPLIES HERE TOO, and is not overridable. `accept_non_citable`
is refused when the unit being demoted carries 500+ characters and the unit
being kept carries less than half of it, whatever the reader believes: that is
the shape that produced 359 citations resolving to less than half their
provision, and a person reading one page is in no better position to see it
than the adjudicator was. Use `restore_citable` or `reparent` for those; they
record the finding without opening the gate, which is correct, because the tree
still needs repairing.

    ./nz s7-source --readings FILE.json            dry run
    ./nz s7-source --readings FILE.json --apply    record them

The readings file is a list of objects:

    [{"document_id": 2692, "printed_label": "5",
      "resolution": "restore_citable",
      "observed": "Page 3 prints section 5 in full, 'Criminal misconduct.- (1)
                   A public servant is said to commit...'. The kept node is a
                   footnote on page 2.",
      "render": ".artifacts/s7-source/doc2692-p3.png",
      "render_sha256": "..."}]

Append-only: a reading that supersedes an earlier decision records
`supersedes_adjudication_id` and leaves the original in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from nizam.storage.db import connect

METHOD = "claude.s7-source-review/1"
DECIDED_BY = "claude.s7-source-review/1"
RESOLUTIONS = {"accept_non_citable", "restore_citable", "reparent",
               "split_instrument", "reject_candidate"}

FIND = """
SELECT c.id::text, c.instrument_id::text, c.candidate_provision_id,
       c.canonical_provision_id, c.printed_label, c.source_page,
       (SELECT a.id::text FROM v_structural_adjudication_latest a
         WHERE a.candidate_id = c.id) AS current_adjudication
  FROM v_active_structural_candidate c
 WHERE c.document_id = %s
   AND regexp_replace(lower(c.printed_label), '[^a-z0-9]', '', 'g')
     = regexp_replace(lower(%s), '[^a-z0-9]', '', 'g')
"""

SIZES = """
SELECT (SELECT coalesce(sum(pb.chars), 0) FROM provision x
          JOIN provision_block pb ON pb.provision_id = x.id
         WHERE x.instrument_id = p.instrument_id AND x.is_active
           AND x.path <@ p.path)
  FROM provision p WHERE p.id = %s AND p.is_active
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readings", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    readings = json.loads(pathlib.Path(a.readings).read_text(encoding="utf-8"))
    if isinstance(readings, dict):
        readings = [readings]

    planned, refused = [], []
    with connect() as conn, conn.cursor() as cur:
        for r in readings:
            doc = r.get("document_id")
            label = str(r.get("printed_label", ""))
            where = f"doc {doc} label {label}"

            resolution = r.get("resolution")
            if resolution not in RESOLUTIONS:
                refused.append((where, f"resolution {resolution!r} not one of "
                                       f"{sorted(RESOLUTIONS)}"))
                continue
            observed = (r.get("observed") or "").strip()
            if len(observed) < 40:
                refused.append((where, "no observation: say what the page shows"))
                continue
            render = r.get("render")
            if not render:
                refused.append((where, "no render named"))
                continue
            path = pathlib.Path(render)
            if not path.exists():
                refused.append((where, f"render not on disk: {render}"))
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if r.get("render_sha256") and r["render_sha256"] != digest:
                refused.append((where, "render_sha256 does not match the file"))
                continue

            cur.execute(FIND, (doc, label))
            rows = cur.fetchall()
            if len(rows) != 1:
                refused.append((where, f"{len(rows)} active candidates match; "
                                       "expected exactly one"))
                continue
            (cid, _iid, cand_pid, canon_pid, printed, page,
             current) = rows[0]

            if resolution == "accept_non_citable":
                cur.execute(SIZES, (cand_pid,))
                cand = (cur.fetchone() or [0])[0]
                cur.execute(SIZES, (canon_pid,))
                canon = (cur.fetchone() or [0])[0]
                if cand >= 500 and canon < cand * 0.5:
                    refused.append((
                        where,
                        f"stub guard: the demoted unit carries {cand} chars and "
                        f"the kept one {canon}. Use restore_citable or reparent."))
                    continue

            planned.append({
                "candidate_id": cid, "where": where, "resolution": resolution,
                "observed": observed, "render": str(path), "sha256": digest,
                "supersedes": current, "page": page,
            })

        print(f"readings          : {len(readings)}")
        print(f"  will record     : {len(planned)}")
        print(f"  refused         : {len(refused)}")
        for where, why in refused:
            print(f"    {where}: {why}")
        for p in planned:
            print(f"    {p['where']} -> {p['resolution']}"
                  f"{' (supersedes)' if p['supersedes'] else ''}")

        if not a.apply:
            print("\ndry run -- pass --apply to record these decisions")
            return 0

        for p in planned:
            evidence = {
                "render_artifact": p["render"],
                "render_sha256": p["sha256"],
                "observed": p["observed"],
                "source_page": p["page"],
                "assistant_page_review": True,
            }
            cur.execute("""
                INSERT INTO segmentation_structural_adjudication
                    (candidate_id, resolution, review_basis, method, rationale,
                     evidence, decided_by, supersedes_adjudication_id)
                VALUES (%s,%s,'source_verified',%s,%s,%s,%s,%s)
            """, (p["candidate_id"], p["resolution"], METHOD, p["observed"],
                  json.dumps(evidence, ensure_ascii=False), DECIDED_BY,
                  p["supersedes"]))
        conn.commit()
        print(f"\nrecorded {len(planned)} source-verified decision(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
