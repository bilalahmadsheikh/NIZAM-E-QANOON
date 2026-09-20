"""Render the page where a promised section should be, so it can be read.

``review_toc_dispositions.py`` only selects contents rows whose heading already
says "Omitted" or "Repealed". That route is exhausted -- 162 recorded, 0 left.
Everything still in the queue needs the opposite of a keyword test: somebody has
to look at the page and see whether the section is printed there.

This prepares exactly that. For each pending gap it finds the provisions that
bracket the missing label in the tree, renders the source pages between them,
and records where it looked. Reading the render answers one question:

  * the section IS printed there -> the parser missed it; the gap is a defect
    and a disposition would be a lie.
  * the section is NOT there    -> the contents row outlived its section; a
    disposition assertion records that, with this render as its evidence.

It decides nothing. It writes no corpus row. It renders, hashes what it
rendered, and writes a manifest that a decision can later cite.

    ./nz toc-review --limit 40            render the cheapest gaps
    ./nz toc-review --document 1234       one document
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess

from nizam.storage.db import connect

CORPUS_ROOT = pathlib.Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
OUT = pathlib.Path(".artifacts/toc-gap-review")

# Where should the missing section be? Between the nearest lower and nearest
# higher provision that DID land, by the document's own printed order.
SQL = """
WITH gap AS (
  SELECT g.toc_entry_id, g.document_id, g.instrument_id, g.ordinal,
         g.printed_label, g.printed_heading, g.source_page AS contents_page,
         i.source_observation_id, i.short_title,
         count(*) OVER (PARTITION BY g.document_id) AS gaps_in_document
    FROM v_toc_gap_pending g
    JOIN instrument i ON i.id = g.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
),
placed AS (
  SELECT e.instrument_id, e.ordinal, p.first_page
    FROM instrument_toc_entry e
    JOIN provision p ON p.id = e.provision_id AND p.is_active
   WHERE e.provision_id IS NOT NULL AND p.first_page IS NOT NULL
)
SELECT gap.toc_entry_id, gap.document_id, gap.source_observation_id,
       gap.short_title, gap.printed_label, gap.printed_heading,
       gap.contents_page, gap.gaps_in_document,
       (SELECT max(first_page) FROM placed
         WHERE placed.instrument_id = gap.instrument_id
           AND placed.ordinal < gap.ordinal)          AS page_before,
       (SELECT min(first_page) FROM placed
         WHERE placed.instrument_id = gap.instrument_id
           AND placed.ordinal > gap.ordinal)          AS page_after,
       d.sha256, b.object_key, d.page_count,
       -- Where the body starts, so a gap with nothing linked before it renders
       -- the operative text rather than the contents page it is promised on.
       (SELECT r.body_starts_page FROM segmentation_run r
         WHERE r.instrument_id = gap.instrument_id
         ORDER BY r.run_at DESC LIMIT 1) AS body_starts_page
  FROM gap
  JOIN document d ON d.id = gap.document_id AND d.is_active
  JOIN blob b ON b.sha256 = d.sha256
 WHERE %(document)s::bigint IS NULL OR gap.document_id = %(document)s::bigint
 ORDER BY gap.gaps_in_document, gap.document_id, gap.ordinal
"""


def render(pdf: pathlib.Path, page: int, dest: pathlib.Path) -> str | None:
    """One page at 130 dpi -- enough to read a printed section number."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        proc = subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "130",
             "-png", "-singlefile", str(pdf), str(dest.with_suffix(""))],
            capture_output=True)
        if proc.returncode != 0 or not dest.exists():
            return None
    return hashlib.sha256(dest.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--document", type=int)
    ap.add_argument("--max-pages", type=int, default=2,
                    help="pages to render per gap (default 2)")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL, {"document": a.document})
        keys = ("toc_entry_id", "document_id", "source_observation_id",
                "short_title", "printed_label", "printed_heading",
                "contents_page", "gaps_in_document", "page_before",
                "page_after", "sha256", "object_key", "page_count",
                "body_starts_page")
        rows = [dict(zip(keys, r)) for r in cur.fetchall()]

    print(f"pending gaps: {len(rows)}")
    rows = rows[:a.limit]
    manifest = []
    for row in rows:
        pdf = CORPUS_ROOT / row["object_key"]
        if not pdf.exists():
            continue
        lo = row["page_before"] or row["body_starts_page"] or 1
        hi = row["page_after"] or min(lo + 1, row["page_count"])
        inverted = hi < lo
        if inverted:
            # The bracket is not trustworthy: a contents entry AFTER this one is
            # linked to an earlier page than the entry before it. Swapping the
            # ends, which this used to do, renders from the LOW one and produces
            # pages that cannot answer the question -- the Karachi Metropolitan
            # Transport Authority Ordinance rendered pages 3 and 4 for its
            # section 26, which sits on page 16 between sections 25 and 27. Five
            # of the first renders read this session pointed at the wrong pages
            # for this reason, and a decision made from one of them would have
            # been made on the wrong evidence.
            #
            # The preceding provision's page is the half that is still reliable,
            # so render forward from it and record that the bracket was broken.
            hi = min(lo + a.max_pages - 1, row["page_count"])
        pages = list(range(lo, min(hi, lo + a.max_pages - 1) + 1))
        shots = []
        for page in pages:
            dest = OUT / (f"doc{row['document_id']}-e{row['toc_entry_id']}"
                          f"-label{row['printed_label']}-p{page}.png")
            digest = render(pdf, page, dest)
            if digest:
                shots.append({"page": page, "file": str(dest),
                              "sha256": digest})
        if not shots:
            continue
        manifest.append({
            "toc_entry_id": row["toc_entry_id"],
            "document_id": row["document_id"],
            "source_observation_id": row["source_observation_id"],
            "short_title": row["short_title"],
            "printed_label": row["printed_label"],
            "printed_heading": row["printed_heading"],
            "contents_page": row["contents_page"],
            "searched_pages": [s["page"] for s in shots],
            "bracketed_by": {"after_page": row["page_before"],
                             "before_page": row["page_after"],
                             "inverted": inverted},
            "gaps_in_document": row["gaps_in_document"],
            "renders": shots,
        })
        print(f"  doc {row['document_id']:<6} label {row['printed_label']:<6} "
              f"pages {[s['page'] for s in shots]}  "
              f"{(row['printed_heading'] or '')[:46]}")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"\nrendered {len(manifest)} gap(s) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
