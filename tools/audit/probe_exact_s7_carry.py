"""Read-only preflight of exact-candidate S7 carry on one released document."""

import argparse
import json

from nizam.storage.db import connect
from nizam.storage.legal_write import _matching_prior_acceptance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("""
            SELECT i.id,c.id FROM instrument i
            JOIN segmentation_structural_candidate c ON c.instrument_id=i.id
           WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL
           ORDER BY c.source_block_id,c.id
        """, (args.document_id,))
        pairs = cur.fetchall()
        results = [{"candidate_id": str(candidate),
                    "exact_self_match": bool(_matching_prior_acceptance(
                        cur, instrument, candidate))}
                   for instrument, candidate in pairs]
        print(json.dumps({"document_id": args.document_id,
                          "candidates": results}))


if __name__ == "__main__":
    main()
