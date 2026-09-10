"""Find active PDF extractions containing provable same-geometry text overlays."""
from __future__ import annotations

import os
import argparse
from pathlib import Path

import pymupdf

from nizam.corpus.extract import _remove_exact_overlay_spans
from nizam.storage.db import connect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reextract", action="store_true",
                        help="append revised extraction for every proven overlay PDF")
    args = parser.parse_args()
    root = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT d.id,d.sha256,b.object_key,b.byte_length,
                      d.extractor_config ? 'exact_overlay_policy'
                 FROM document d JOIN blob b USING (sha256)
                WHERE d.is_active AND d.lane <> 'E4'
                ORDER BY d.id"""
        )
        rows = cur.fetchall()
    found = 0
    targets = []
    for n, (document_id, sha256, object_key, byte_length, already_fixed) in enumerate(rows, 1):
        overlays = 0
        with pymupdf.open(root / object_key) as pdf:
            for page in pdf:
                raw = page.get_text("blocks", sort=True)
                _, count = _remove_exact_overlay_spans(page, raw)
                overlays += count
        if overlays:
            found += 1
            print(f"{sha256}|{document_id}|{overlays}", flush=True)
            if not already_fixed:
                targets.append((sha256, object_key, byte_length))
        if n % 500 == 0:
            print(f"# scanned {n}/{len(rows)}", flush=True)
    print(f"# exact-overlay documents {found}/{len(rows)}")
    if args.reextract and targets:
        # Use the normal worker so each revision and extraction attempt is
        # recorded through the same transactional production path.
        from nizam.workers.extract import run
        print(f"# revising {len(targets)} affected active extraction(s)")
        done, rejected = run(targets)
        return 0 if done == len(targets) and rejected == 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
