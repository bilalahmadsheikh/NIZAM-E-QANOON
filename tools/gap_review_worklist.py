"""Order the rendered contents gaps so each page read settles the most of them.

830 distinct pages stand behind 1,167 pending gaps, and they are not evenly
distributed: one page of a contents-heavy Act can answer a dozen gaps while
another answers one. Reading them in manifest order wastes most of the effort.

This groups the pending gaps by the page rendered for them and prints the pages
in descending order of how many gaps each settles, with the labels and headings
a reader has to look for and the render's SHA-256, which migration 0050 requires
a decision to cite.

Reads only.

    ./nz gap-worklist --limit 20
    ./nz gap-worklist --document 3979
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

from nizam.storage.db import connect

MANIFEST = pathlib.Path(".artifacts/toc-gap-review/manifest.json")

PENDING = """
SELECT g.toc_entry_id, g.document_id, g.printed_label,
       coalesce(g.printed_heading, ''), g.source_page
  FROM v_toc_gap_pending g
 WHERE g.toc_entry_id = ANY(%s)
   AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication a
                    WHERE a.toc_entry_id = g.toc_entry_id)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--document", type=int)
    a = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_entry = {item["toc_entry_id"]: item for item in manifest}

    with connect() as conn, conn.cursor() as cur:
        cur.execute(PENDING, (list(by_entry),))
        rows = cur.fetchall()

    # page -> the gaps it was rendered for
    per_page: dict[tuple, list] = collections.defaultdict(list)
    sha: dict[tuple, str] = {}
    paths: dict[tuple, str] = {}
    for entry_id, document, label, heading, contents_page in rows:
        if a.document and document != a.document:
            continue
        for render in by_entry[entry_id].get("renders", []):
            # Group by the image's CONTENT, not its filename. review_toc_gaps
            # names a render per gap, so the same page of the same document is
            # written once per gap that needs it -- document 127 page 6 arrives
            # as fourteen files with one sha256. Keying on the path made every
            # page look like it settled exactly one gap, which is the opposite
            # of what this tool is for.
            key = (document, render["page"], render.get("sha256", ""))
            per_page[key].append((entry_id, label, heading, contents_page))
            sha[key] = render.get("sha256", "")
            paths.setdefault(key, render["file"])

    order = sorted(per_page.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    total_gaps = len({g[0] for gaps in per_page.values() for g in gaps})
    print(f"pending unadjudicated gaps with a fresh render : {total_gaps}")
    print(f"distinct pages behind them                     : {len(per_page)}")
    print(f"reading the top {a.limit} pages settles at most : "
          f"{sum(len(v) for _k, v in order[:a.limit])} gap-references\n")

    for key, gaps in order[:a.limit]:
        document, page, digest = key
        print(f"doc {document}  page {page}  ({len(gaps)} gaps)")
        print(f"  {paths[key]}")
        print(f"  sha256 {digest[:32]}...")
        for entry_id, label, heading, contents_page in gaps[:12]:
            print(f"    entry {entry_id}  promises {label!r}: "
                  f"{heading[:56]!r}  (contents p{contents_page})")
        if len(gaps) > 12:
            print(f"    ... and {len(gaps) - 12} more")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
