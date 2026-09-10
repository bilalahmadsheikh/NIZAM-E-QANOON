"""Print PyMuPDF spans for one stored document page, including exact overlays."""
from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import pymupdf

from nizam.storage.db import connect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document_id", type=int)
    parser.add_argument("page", type=int)
    args = parser.parse_args()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT b.object_key FROM document d JOIN blob b USING (sha256) WHERE d.id=%s",
            (args.document_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit("document not found")
    root = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
    with pymupdf.open(root / row[0]) as pdf:
        raw = pdf[args.page - 1].get_text("dict", sort=True)
    spans = []
    for block in raw["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                key = (
                    span["text"], tuple(round(v, 3) for v in span["bbox"]),
                    span.get("font"), round(span.get("size", 0), 3),
                    span.get("color"), span.get("flags"),
                )
                spans.append(key)
    counts = Counter(spans)
    for key, count in counts.items():
        print(f"{count}x {key!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
