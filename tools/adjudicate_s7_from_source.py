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
STRUCTURAL_OVERRIDE_KEYS = {
    "source_body_start_block", "source_apparatus_blocks",
    "source_reparent_blocks",
}

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

FIND_BY_ID = """
SELECT c.id::text, c.instrument_id::text, c.candidate_provision_id,
       c.canonical_provision_id, c.printed_label, c.source_page,
       (SELECT a.id::text FROM v_structural_adjudication_latest a
         WHERE a.candidate_id = c.id) AS current_adjudication
  FROM v_active_structural_candidate c
 WHERE c.id = %s
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

            # A document that prints the same label twice -- doc 4482's form
            # has two "3." -- offers two candidates for one label, and the
            # reading has to say which. `candidate_id` (from ./nz s7-render)
            # names it; without one, an ambiguous label is still refused.
            if r.get("candidate_id"):
                cur.execute(FIND_BY_ID, (r["candidate_id"],))
                where = f"{where} cand {r['candidate_id'][:8]}"
            else:
                cur.execute(FIND, (doc, label))
            rows = cur.fetchall()
            if len(rows) != 1:
                refused.append((where, f"{len(rows)} active candidates match; "
                                       "expected exactly one"))
                continue
            (cid, _iid, cand_pid, canon_pid, printed, page,
             current) = rows[0]

            structural_overrides = r.get("structural_overrides") or {}
            unknown_overrides = set(structural_overrides) - STRUCTURAL_OVERRIDE_KEYS
            if unknown_overrides:
                refused.append((where, "unknown structural overrides: "
                                + ", ".join(sorted(unknown_overrides))))
                continue
            if "source_body_start_block" in structural_overrides:
                body_start = structural_overrides["source_body_start_block"]
                cur.execute("""SELECT 1 FROM text_block
                                WHERE id=%s AND document_id=%s""",
                            (body_start, doc))
                if cur.fetchone() is None:
                    refused.append((where, "source_body_start_block does not "
                                    "belong to this document"))
                    continue
            if "source_apparatus_blocks" in structural_overrides:
                apparatus = structural_overrides["source_apparatus_blocks"]
                if (not isinstance(apparatus, list) or not apparatus
                        or any(not isinstance(value, int) for value in apparatus)
                        or len(set(apparatus)) != len(apparatus)):
                    refused.append((where, "source_apparatus_blocks must be a "
                                    "non-empty list of unique block ids"))
                    continue
                cur.execute("""SELECT id FROM text_block
                                WHERE document_id=%s AND id=ANY(%s)
                                ORDER BY id""", (doc, apparatus))
                found = {row[0] for row in cur.fetchall()}
                missing = sorted(set(apparatus) - found)
                if missing:
                    refused.append((where, "source_apparatus_blocks do not "
                                    "belong to this document: "
                                    + ", ".join(map(str, missing))))
                    continue
            if "source_reparent_blocks" in structural_overrides:
                reparents = structural_overrides["source_reparent_blocks"]
                # Only kinds the provision_kind enum carries: a spec with
                # "item" or "paragraph" passed here and then failed the replay
                # on insert (agent E, doc 1572, 25 Sep 2026).
                valid_kinds = {"clause", "subsection"}
                if (not isinstance(reparents, list) or not reparents
                        or any(not isinstance(value, dict) for value in reparents)):
                    refused.append((where, "source_reparent_blocks must be a "
                                    "non-empty list of objects"))
                    continue
                source_ids = [value.get("source_block_id") for value in reparents]
                parent_ids = [value.get("parent_block_id") for value in reparents]

                def _qualified(value, side):
                    return (value.get(f"{side}_label") is not None
                            or value.get(f"{side}_kind") is not None)

                # One block can open a section AND its sub-section (1); with a
                # label/kind qualifier on both sides a same-block move is exact.
                malformed = any(
                    not isinstance(source, int)
                    or not isinstance(parent, int)
                    or (source == parent and not (
                        _qualified(value, "source") and _qualified(value, "parent")))
                    or value.get("kind") not in valid_kinds
                    for value, source, parent in zip(
                        reparents, source_ids, parent_ids)
                )
                source_keys = [(value.get("source_block_id"), value.get("source_label"),
                                value.get("source_kind")) for value in reparents]
                if malformed or len(set(source_keys)) != len(source_keys):
                    refused.append((where, "source_reparent_blocks contains "
                                    "an invalid or repeated source block"))
                    continue
                block_ids = sorted(set(source_ids + parent_ids))
                cur.execute("""SELECT id FROM text_block
                                WHERE document_id=%s AND id=ANY(%s)
                                ORDER BY id""", (doc, block_ids))
                found = {row[0] for row in cur.fetchall()}
                missing = sorted(set(block_ids) - found)
                if missing:
                    refused.append((where, "source_reparent_blocks reference "
                                    "blocks outside this document: "
                                    + ", ".join(map(str, missing))))
                    continue

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

            # Provenance of a re-attached reading, when the reading carries it.
            # It belongs in `evidence`, never in `observed` or `rationale`:
            # those are the READER'S description of the page, and appending to
            # them compounds -- before 21 Sep 2026 the re-attach tool appended
            # 199 characters of prose per replay, leaving 1,439 decisions
            # carrying 407,500 characters of boilerplate, 12.6% of all S7
            # observation text, around a shrinking kernel of what was seen.
            reattachment = None
            if r.get("reattached_from"):
                reattachment = {
                    "from_adjudication_id": r["reattached_from"],
                    "origin": r.get("reattach_origin") or r["reattached_from"],
                    "generation": int(r.get("reattach_generation", 1)),
                    "basis": r.get("reattach_basis", ""),
                    "tool": "tools/reattach_orphaned_adjudications.py",
                    "note": "The observation is the original reader's words, "
                            "carried forward unchanged. Only the pointer into "
                            "our own numbering broke.",
                }

            planned.append({
                "candidate_id": cid, "where": where, "resolution": resolution,
                "observed": observed, "render": str(path), "sha256": digest,
                "supersedes": current, "page": page,
                "reattachment": reattachment,
                "structural_overrides": structural_overrides,
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
            if p["reattachment"]:
                evidence["reattachment"] = p["reattachment"]
            if p["structural_overrides"]:
                evidence["structural_overrides"] = p["structural_overrides"]
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
