"""Localise independent-extractor differences to exact PDF pages."""
from __future__ import annotations

import argparse
import collections
import os
import subprocess
import unicodedata
from pathlib import Path

import pymupdf

from nizam.storage.db import connect
from nizam.workers.verify_extraction import _chars, _multiset_overlap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document_ids", nargs="+", type=int)
    parser.add_argument("--threshold", type=float, default=1.0,
                        help="print pages below this recall or precision")
    args = parser.parse_args()
    root = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT d.id,b.object_key,d.page_count
                 FROM document d JOIN blob b USING (sha256)
                WHERE d.id=ANY(%s) ORDER BY d.id""",
            (args.document_ids,),
        )
        documents = cur.fetchall()
        for document_id, object_key, page_count in documents:
            cur.execute(
                """SELECT page_no,string_agg(text,E'\n' ORDER BY reading_order)
                     FROM text_block WHERE document_id=%s GROUP BY page_no""",
                (document_id,),
            )
            stored = dict(cur.fetchall())
            result = subprocess.run(
                ["pdftotext", "-q", "-enc", "UTF-8", str(root / object_key), "-"],
                capture_output=True, timeout=300, check=False,
            )
            reference = result.stdout.decode("utf-8", "replace").split("\f")
            if reference and not reference[-1].strip():
                reference.pop()
            print(f"document={document_id} pages={page_count} poppler_pages={len(reference)}")
            with pymupdf.open(root / object_key) as pdf:
                for page_no in range(1, page_count + 1):
                    ours = _chars(stored.get(page_no, ""))
                    theirs = _chars(reference[page_no - 1] if page_no <= len(reference) else "")
                    shared = _multiset_overlap(ours, theirs)
                    recall = shared / max(sum(theirs.values()), 1)
                    precision = shared / max(sum(ours.values()), 1)
                    if recall < args.threshold or precision < args.threshold:
                        missing = theirs - ours
                        extra = ours - theirs
                        page = pdf[page_no - 1]
                        media = _chars(page.get_text("text", clip=page.mediabox))
                        media_shared = _multiset_overlap(media, theirs)
                        media_recall = media_shared / max(sum(theirs.values()), 1)
                        original_crop = page.cropbox
                        page.set_cropbox(page.mediabox)
                        expanded = _chars(page.get_text("text"))
                        page.set_cropbox(original_crop)
                        expanded_shared = _multiset_overlap(expanded, theirs)
                        expanded_recall = expanded_shared / max(sum(theirs.values()), 1)
                        no_clip = _chars(page.get_text("text", flags=3))
                        no_clip_shared = _multiset_overlap(no_clip, theirs)
                        no_clip_recall = no_clip_shared / max(sum(theirs.values()), 1)
                        raw = page.get_text("rawdict")
                        raw_text = "".join(
                            char.get("c", "")
                            for block in raw.get("blocks", [])
                            for line in block.get("lines", [])
                            for span in line.get("spans", [])
                            for char in span.get("chars", [])
                        )
                        raw_chars = _chars(raw_text)
                        raw_shared = _multiset_overlap(raw_chars, theirs)
                        raw_recall = raw_shared / max(sum(theirs.values()), 1)
                        print(
                            f"  page={page_no} recall={recall:.5f} precision={precision:.5f} "
                            f"media_recall={media_recall:.5f} expanded_recall={expanded_recall:.5f} "
                            f"no_clip_recall={no_clip_recall:.5f} raw_recall={raw_recall:.5f} "
                            f"crop={original_crop} media={page.mediabox} "
                            f"missing={sum(missing.values())}:{missing.most_common(12)!r} "
                            f"extra={sum(extra.values())}:{extra.most_common(12)!r}"
                        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
