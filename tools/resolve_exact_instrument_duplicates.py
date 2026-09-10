"""Resolve only byte-identical, tree-identical active legal expressions.

Distinct source observations are provenance and are never removed. This tool
only links a redundant active instrument revision to the best-attributed copy
after hashing every relative path, structural field and provision text field.
The release views then represent that legal expression once.
"""
from __future__ import annotations

import argparse
import hashlib
import json

from nizam.storage.db import connect

METHOD = "nizam.exact_instrument_identity/1"


def _fingerprint(rows: list[tuple]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"),
                         default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="record exact matches and set duplicate_of; default is dry-run")
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        lineage_links_advanced = 0
        if args.apply:
            # A canonical tree may be corrected by an append-only replay after
            # an exact duplicate was linked to it.  Identity belongs to the
            # source expression, not to one parser revision, so advance the
            # duplicate pointer to the active successor without discarding the
            # original fingerprint resolution or either historical tree.
            cur.execute("""
                WITH RECURSIVE lineage AS (
                    SELECT d.id AS duplicate_id,d.duplicate_of AS canonical_id
                      FROM instrument d
                     WHERE d.is_active AND d.duplicate_of IS NOT NULL
                    UNION ALL
                    SELECT l.duplicate_id,next.id
                      FROM lineage l
                      JOIN instrument next
                        ON next.supersedes_instrument_id=l.canonical_id
                ), active_successor AS (
                    SELECT DISTINCT ON (l.duplicate_id)
                           l.duplicate_id,l.canonical_id
                      FROM lineage l
                      JOIN instrument c ON c.id=l.canonical_id AND c.is_active
                     ORDER BY l.duplicate_id,c.created_at DESC,c.id DESC
                )
                UPDATE instrument d SET duplicate_of=a.canonical_id
                  FROM active_successor a
                 WHERE d.id=a.duplicate_id
                   AND d.duplicate_of IS DISTINCT FROM a.canonical_id
            """)
            lineage_links_advanced = cur.rowcount
        cur.execute("""
            SELECT i.document_id,i.expression_ordinal,
                   array_agg(i.id ORDER BY i.id),i.source_sha256
              FROM instrument i
             WHERE i.is_active
             GROUP BY i.document_id,i.source_sha256,i.expression_ordinal
            HAVING count(*)>1
        """)
        groups = cur.fetchall()
        resolutions: list[dict] = []
        differing = 0

        for document_id, expression_ordinal, instrument_ids, source_sha256 in groups:
            fingerprints: dict[str, list] = {}
            attribution: dict[str, tuple] = {}
            node_counts: dict[str, int] = {}
            for instrument_id in instrument_ids:
                cur.execute("""
                    SELECT subpath(p.path,3)::text,p.kind::text,p.label,
                           coalesce(p.heading,''),p.ordinal,p.first_page,p.last_page,
                           p.first_block,coalesce(v.text_en,''),coalesce(v.text_ur,''),
                           v.text_normalised,v.operation::text,
                           coalesce(v.amendment_note,'')
                      FROM provision p
                      JOIN provision_version v ON v.provision_id=p.id
                     WHERE p.instrument_id=%s AND p.is_active
                     ORDER BY subpath(p.path,3)::text
                """, (instrument_id,))
                rows = cur.fetchall()
                fp = _fingerprint(rows)
                fingerprints.setdefault(fp, []).append(instrument_id)
                node_counts[str(instrument_id)] = len(rows)
                cur.execute("""
                    SELECT (o.canonical_url IS NOT NULL)::int,
                           (o.source_metadata ? 'title')::int,o.id
                      FROM instrument i
                      JOIN source_observation o ON o.id=i.source_observation_id
                     WHERE i.id=%s
                """, (instrument_id,))
                attribution[str(instrument_id)] = cur.fetchone()

            if len(fingerprints) != 1:
                differing += 1
                continue
            tree_sha256, exact_ids = next(iter(fingerprints.items()))
            # Prefer an official canonical URL and explicit catalogue title;
            # thereafter use the earliest stable observation id.
            canonical = max(
                exact_ids,
                key=lambda iid: (
                    attribution[str(iid)][0], attribution[str(iid)][1],
                    -attribution[str(iid)][2]))
            for duplicate in exact_ids:
                if duplicate == canonical:
                    continue
                resolutions.append({
                    "duplicate": duplicate,
                    "canonical": canonical,
                    "source_sha256": source_sha256,
                    "tree_sha256": tree_sha256,
                    "evidence": {
                        "document_id": document_id,
                        "expression_ordinal": expression_ordinal,
                        "relative_tree_fields": [
                            "path", "kind", "label", "heading", "ordinal",
                            "pages", "first_block", "text_en", "text_ur",
                            "text_normalised", "operation", "amendment_note"],
                        "duplicate_nodes": node_counts[str(duplicate)],
                        "canonical_nodes": node_counts[str(canonical)],
                        "same_source_sha256": True,
                    },
                })

        print(json.dumps({
            "candidate_groups": len(groups),
            "differing_groups": differing,
            "exact_redundant_trees": len(resolutions),
            "lineage_links_advanced": lineage_links_advanced,
            "applied": args.apply,
        }, indent=2))

        if args.apply:
            for row in resolutions:
                cur.execute("""
                    INSERT INTO instrument_identity_resolution
                        (duplicate_instrument_id,canonical_instrument_id,
                         source_sha256,tree_sha256,method,evidence,resolved_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (duplicate_instrument_id) DO NOTHING
                """, (row["duplicate"], row["canonical"], row["source_sha256"],
                      row["tree_sha256"], METHOD,
                      json.dumps(row["evidence"], ensure_ascii=False), METHOD))
                cur.execute("""
                    UPDATE instrument SET duplicate_of=%s
                     WHERE id=%s AND is_active AND duplicate_of IS NULL
                """, (row["canonical"], row["duplicate"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
