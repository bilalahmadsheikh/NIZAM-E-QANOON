"""Record a contents-gap decision from pages that were actually read.

The TOC counterpart of `adjudicate_s7_from_source.py`. It takes readings -- one
per pending contents entry, each naming the rendered page images it was read
from and their SHA-256 -- and records them in `toc_gap_adjudication` as an
assistant page review under migration 0050. It writes nothing without that
evidence, and it never writes `parser_defect` (that resolution classifies work
but closes nothing; record it with the tools that repair the tree).

    python tools/adjudicate_toc_from_source.py --readings FILE.json          dry run
    python tools/adjudicate_toc_from_source.py --readings FILE.json --apply  record

A reading:

    {"document_id": 1442, "toc_entry_id": 1082255,
     "resolution": "found_elsewhere",           # or absent_in_source /
                                                # other_instrument / source_incomplete
     "found_provision_id": "b1ec...",           # found_elsewhere only
     "other_instrument_id": "...",              # other_instrument only
     "source_incompleteness_id": 41,            # source_incomplete only
     "source_page": 5,                          # the body page that settles it
     "observed": "Page 5 prints 'SCHEDULE [* * *]' ...",
     "renders": [{"path": ".artifacts/.../page-1.png", "sha256": "..."}, ...]}

WHAT `found_elsewhere` MEANS HERE. The promised unit's own printed text is a
live provision of THIS instrument that the contents linker did not pick --
never a neighbouring heading (the doc 169 / 306 / 732 retractions). The dry run
prints the provision's kind, label, heading and first text so the reader can
check that before --apply.

WHAT `source_incomplete` MEANS HERE (migration 0060). The landed copy does not
print the promised unit, and a `source_incompleteness` row (migration 0054)
already records that this file is partial and that no complete copy has been
obtained. It is NOT `absent_in_source`: the Act has the section, this copy does
not carry it. The reading must name that row; the tool refuses unless it is
the latest record for the instrument's own observation, is about the same
document, and still says `no_complete_copy_acquired` -- the same rules the
database trigger enforces, checked here first so the dry run says why. Record
the dated refetch (tools/record_source_refetch.py) and the 0054 row first.

Append-only: a reading that supersedes an earlier decision on the same entry
records `supersedes_id` and leaves the original in place. Decisions are keyed
on toc_entry_id, which a replay regenerates: run `./nz toc-reattach` after any
later replay of the same document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from nizam.storage.db import connect

DECIDED_BY = "claude.toc-source-review/2"
RESOLUTIONS = {"found_elsewhere", "absent_in_source", "other_instrument",
               "source_incomplete"}

ENTRY = """
SELECT e.id, e.instrument_id::text, i.document_id, e.printed_label,
       e.printed_heading, e.entry_kind, e.source_page, e.provision_id,
       (SELECT a.id::text FROM v_toc_gap_adjudication_latest a
         WHERE a.instrument_id = e.instrument_id
           AND a.toc_entry_id = e.id
           AND a.printed_label = e.printed_label) AS current,
       EXISTS (SELECT 1 FROM v_toc_gap_pending g
                WHERE g.toc_entry_id = e.id) AS pending
  FROM instrument_toc_entry e
  JOIN instrument i ON i.id = e.instrument_id
                   AND i.is_active AND i.duplicate_of IS NULL
 WHERE e.id = %s
"""

FOUND = """
SELECT p.instrument_id::text, p.kind::text, p.label, p.heading, p.path::text,
       p.first_page, p.first_block,
       left(regexp_replace(coalesce(b.text, ''), '\\s+', ' ', 'g'), 160)
  FROM provision p
  LEFT JOIN text_block b ON b.id = p.first_block
 WHERE p.id = %s AND p.is_active
"""

# The 0054 record a source_incomplete reading names, the latest record for the
# same observation, and the observation the entry's instrument was built from.
INCOMPLETENESS = """
SELECT s.id, s.source_observation_id, s.document_id, s.resolution,
       s.body_stops_at,
       (SELECT l.id FROM v_source_incompleteness_latest l
         WHERE l.source_observation_id = s.source_observation_id) AS latest_id,
       (SELECT i.source_observation_id FROM instrument i
         WHERE i.id = %s::uuid)                                   AS built_from
  FROM source_incompleteness s
 WHERE s.id = %s
"""


def reading_problem(r: dict) -> str | None:
    """Why a reading cannot be recorded, judged on the reading alone (no
    database, no files), or None. The checks that need the tree come later."""
    resolution = r.get("resolution")
    if resolution not in RESOLUTIONS:
        return f"resolution {resolution!r} not one of {sorted(RESOLUTIONS)}"
    observed = (r.get("observed") or "").strip()
    if len(observed) < 40:
        return "no observation: say what the page shows"
    if not (r.get("renders") or []):
        return "no rendered page named"
    if resolution == "other_instrument" and not r.get("other_instrument_id"):
        return "other_instrument_id required"
    if resolution == "source_incomplete":
        named = r.get("source_incompleteness_id")
        if isinstance(named, bool) or not isinstance(named, int) or named < 1:
            return ("source_incompleteness_id required: the id of the "
                    "migration-0054 record this reading rests on")
    return None


def verify_renders(renders: list[dict]) -> tuple[list[str], list[str], str | None]:
    """Hash every named render. Returns (paths, digests, problem)."""
    paths, digests = [], []
    for render in renders:
        path = pathlib.Path(render.get("path", ""))
        if not path.is_file():
            return paths, digests, f"render not on disk: {path}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if render.get("sha256") and render["sha256"] != digest:
            return paths, digests, f"sha256 does not match {path}"
        paths.append(str(path).replace("\\", "/"))
        digests.append(digest)
    return paths, digests, None


def incompleteness_problem(record: dict | None, document_id: int) -> str | None:
    """Mirror of migration 0060's trigger, so the dry run refuses with a reason
    instead of the --apply failing on the guard. `record` is the INCOMPLETENESS
    row as a dict, or None when the id names nothing."""
    if record is None:
        return "source_incompleteness_id names no source_incompleteness row"
    if record["source_observation_id"] != record["built_from"]:
        return (f"source_incompleteness {record['id']} is about observation "
                f"{record['source_observation_id']}, but the entry's instrument "
                f"was built from observation {record['built_from']}")
    if record["document_id"] != document_id:
        return (f"source_incompleteness {record['id']} is about document "
                f"{record['document_id']}, not {document_id}")
    if record["latest_id"] != record["id"]:
        return (f"source_incompleteness {record['id']} is not the latest record "
                f"for observation {record['source_observation_id']} (latest is "
                f"{record['latest_id']}); read the newer one and name it")
    if record["resolution"] != "no_complete_copy_acquired":
        return (f"source_incompleteness {record['id']} says "
                f"{record['resolution']}: a complete copy is held, so retire "
                "this tree with tools/apply_source_incompleteness.py instead "
                "of releasing it with a gap")
    return None


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
            entry_id = r.get("toc_entry_id")
            where = f"doc {doc} entry {entry_id}"
            resolution = r.get("resolution")
            problem = reading_problem(r)
            if problem:
                refused.append((where, problem))
                continue
            observed = r["observed"].strip()
            paths, digests, bad = verify_renders(r["renders"])
            if bad:
                refused.append((where, bad))
                continue

            cur.execute(ENTRY, (entry_id,))
            row = cur.fetchone()
            if row is None:
                refused.append((where, "no such contents entry on an active "
                                       "canonical instrument (stale id?)"))
                continue
            (_, instrument_id, entry_doc, label, heading, kind, contents_page,
             linked, current, pending) = row
            if entry_doc != doc:
                refused.append((where, f"entry belongs to document {entry_doc}"))
                continue
            if linked is not None or not pending:
                refused.append((where, "entry is not a pending gap"))
                continue
            page = int(r.get("source_page") or contents_page or 1)

            evidence = {
                "assistant_page_review": True,
                "human_page_review": False,
                "reviewer_type": "assistant",
                "render_artifact": paths,
                "render_sha256": digests,
                "observed": observed,
                "printed_heading": heading,
                "entry_kind": kind,
                "toc_entry_id_at_review": entry_id,
                "tool": "tools/adjudicate_toc_from_source.py",
            }
            shown = ""
            if resolution == "found_elsewhere":
                pid = r.get("found_provision_id")
                cur.execute(FOUND, (pid,))
                found = cur.fetchone()
                if found is None:
                    refused.append((where, "found_provision_id is not an active "
                                           "provision"))
                    continue
                (f_inst, f_kind, f_label, f_heading, f_path, f_page,
                 f_block, f_text) = found
                if f_inst != instrument_id:
                    refused.append((where, "found provision belongs to another "
                                           "instrument"))
                    continue
                evidence.update({
                    "found_provision_id": pid, "found_kind": f_kind,
                    "found_label": f_label, "found_path": f_path,
                    "found_first_block": f_block, "body_first_page": f_page,
                })
                shown = (f"\n        -> {f_kind} {f_label!r} {f_heading!r} "
                         f"p{f_page} blk {f_block}: {f_text[:110]}")
            elif resolution == "other_instrument":
                evidence["other_instrument_id"] = r["other_instrument_id"]
            elif resolution == "source_incomplete":
                named = r["source_incompleteness_id"]
                cur.execute(INCOMPLETENESS, (instrument_id, named))
                found = cur.fetchone()
                record = (dict(zip([d.name for d in cur.description], found))
                          if found else None)
                why = incompleteness_problem(record, doc)
                if why:
                    refused.append((where, why))
                    continue
                evidence.update({
                    "source_incompleteness_id": named,
                    "source_observation_id": record["source_observation_id"],
                    "source_incompleteness_resolution": record["resolution"],
                    "not_absent_in_source": (
                        "the Act has this unit; the landed copy does not print "
                        "it (migration 0054 record named above)"),
                })
                shown = (f"\n        -> source_incompleteness {named} "
                         f"(observation {record['source_observation_id']}): "
                         f"{record['body_stops_at'][:100]}")

            planned.append({
                "where": where, "instrument_id": instrument_id, "doc": doc,
                "entry_id": entry_id, "label": label, "resolution": resolution,
                "page": page, "evidence": evidence, "observed": observed,
                "supersedes": current, "shown": shown, "heading": heading,
            })

        print(f"readings          : {len(readings)}")
        print(f"  will record     : {len(planned)}")
        print(f"  refused         : {len(refused)}")
        for where, why in refused:
            print(f"    {where}: {why}")
        for p in planned:
            print(f"    {p['where']} [{p['label']}] {p['heading']!r} -> "
                  f"{p['resolution']}{' (supersedes)' if p['supersedes'] else ''}"
                  f"{p['shown']}")

        if not a.apply:
            print("\ndry run -- pass --apply to record these decisions")
            return 0 if not refused else 1

        for p in planned:
            cur.execute("""
                INSERT INTO toc_gap_adjudication
                    (instrument_id, document_id, toc_entry_id, printed_label,
                     resolution, source_page, evidence, rationale, decided_by,
                     supersedes_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (p["instrument_id"], p["doc"], p["entry_id"], p["label"],
                  p["resolution"], p["page"],
                  json.dumps(p["evidence"], ensure_ascii=False),
                  p["observed"], DECIDED_BY, p["supersedes"]))
        conn.commit()
        print(f"\nrecorded {len(planned)} assistant page-review decision(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
