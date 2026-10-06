"""Compare a frozen release baseline to today's blocked expressions.

The comparison is read-only and UUID-independent. A full replay regenerates
instrument/provision UUIDs, so identity is the durable tuple of document,
source observation, expression ordinal and source hash. Relative tree
fingerprints exclude generated UUIDs but include every structural field and
version text; an old release with a changed tree is therefore not mislabeled as
a mere review-pointer regression.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from nizam.storage.db import connect


IDENTITY_SQL = """
SELECT i.id::text AS instrument_id,i.document_id,i.source_observation_id,
       i.expression_ordinal,i.source_sha256
  FROM instrument i
 WHERE i.id=ANY(%s::uuid[])
"""

FINGERPRINT_SQL = """
SELECT i.id::text,
       md5(jsonb_build_object(
           'kind',i.kind::text,'jurisdiction',i.jurisdiction::text,
           'year',i.year,'number',i.number,
           'expression_ordinal',i.expression_ordinal,
           'expression_role',i.expression_role,
           'tree',coalesce((
             SELECT jsonb_agg(jsonb_build_object(
                 'path',subpath(p.path,3)::text,
                 'parent',CASE WHEN p.parent_id IS NULL THEN NULL ELSE
                    (SELECT subpath(parent.path,3)::text
                       FROM provision parent WHERE parent.id=p.parent_id) END,
                 'kind',p.kind::text,'label',p.label,'heading',p.heading,
                 'ordinal',p.ordinal,'first_page',p.first_page,
                 'last_page',p.last_page,'first_block',p.first_block,
                 'versions',coalesce((
                   SELECT jsonb_agg(jsonb_build_object(
                       'text_en',v.text_en,'text_ur',v.text_ur,
                       'text_normalised',v.text_normalised,
                       'operation',v.operation::text,
                       'amendment_note',v.amendment_note)
                       ORDER BY v.created_at,v.id)
                     FROM provision_version v WHERE v.provision_id=p.id
                 ),'[]'::jsonb)) ORDER BY subpath(p.path,3)::text)
               FROM provision p WHERE p.instrument_id=i.id
           ),'[]'::jsonb))::text) AS relative_fingerprint
  FROM instrument i
 WHERE i.id=ANY(%s::uuid[])
"""


def identity(row: dict) -> tuple:
    return (
        int(row["document_id"]),
        int(row["source_observation_id"]),
        int(row["expression_ordinal"]),
        str(row["source_sha256"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True,
                        help="frozen released.json (UUID -> fingerprint)")
    parser.add_argument("--current", type=Path, required=True,
                        help="fresh blocked instruments.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    current = json.loads(args.current.read_text(encoding="utf-8"))
    baseline_ids = list(baseline)
    current_ids = [row["id"] for row in current]

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute(IDENTITY_SQL, (baseline_ids,))
        columns = [column.name for column in cur.description]
        old_rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.execute(IDENTITY_SQL, (current_ids,))
        columns = [column.name for column in cur.description]
        new_rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        pair_ids = baseline_ids + current_ids
        cur.execute(FINGERPRINT_SQL, (pair_ids,))
        fingerprints = dict(cur.fetchall())

    old_by_identity: dict[tuple, list[dict]] = {}
    for row in old_rows:
        old_by_identity.setdefault(identity(row), []).append(row)
    new_identity = {row["instrument_id"]: identity(row) for row in new_rows}
    current_by_id = {row["id"]: row for row in current}

    overlap = []
    for instrument_id in current_ids:
        matches = old_by_identity.get(new_identity[instrument_id], [])
        if len(matches) != 1:
            continue
        old_id = matches[0]["instrument_id"]
        row = current_by_id[instrument_id]
        same_tree = fingerprints.get(old_id) == fingerprints.get(instrument_id)
        overlap.append({
            "document_id": row["document_id"],
            "expression_ordinal": row["expression_ordinal"],
            "old_instrument_id": old_id,
            "current_instrument_id": instrument_id,
            "same_relative_tree": same_tree,
            "toc_count": row["toc_count"],
            "s7_count": row["s7_count"],
            "short_title": row["short_title"],
        })

    families = Counter(
        "both" if row["toc_count"] and row["s7_count"] else
        "toc_only" if row["toc_count"] else "s7_only"
        for row in overlap
    )
    summary = {
        "baseline_released": len(baseline_ids),
        "current_blocked": len(current_ids),
        "previously_released_now_blocked": len(overlap),
        "pct_current_blocked_previously_released": round(
            100 * len(overlap) / len(current_ids), 2) if current_ids else 0,
        "same_relative_tree": sum(row["same_relative_tree"] for row in overlap),
        "changed_relative_tree": sum(not row["same_relative_tree"] for row in overlap),
        "blocker_families": dict(families),
    }
    result = {"summary": summary, "expressions": overlap}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
