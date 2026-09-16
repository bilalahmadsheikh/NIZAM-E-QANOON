"""Render the source pages a batch of pending S7 units needs, and describe them.

The reading loop was costing one render script, one hand-computed SHA-256 and
one hand-written reading per unit. At 186 expressions and 385 distinct pages
that is not a loop anyone finishes. This does the mechanical half in one call:
picks a batch of pending units, renders every distinct page they cite, computes
the digest `adjudicate_s7_from_source` will demand, and prints what the corpus
believes about each unit so the reading has something to agree or disagree with.

What it does NOT do is decide. The manifest it writes carries `resolution` and
`observed` as nulls; a reading is only a reading once someone has looked at the
page and written what is on it.

Selection is by expression, never by unit, because the gate is per expression:
settling four of an expression's five units releases nothing. `--max-subtree`
bounds the batch by the LARGEST demoted subtree in the expression, which is the
honest difficulty signal -- an expression whose every demoted node holds 40
characters is a page of apparatus, and one holding 900 may be an inversion.

    ./nz s7-render --max-subtree 500 --limit 12 --out .s7_batch.json

Expressions that still carry a contents gap are excluded by default: settling
their S7 units releases nothing while the gap stands. So are units already
carrying a `source_verified` decision -- `restore_citable` leaves a unit
pending on purpose, and the page has already been read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

from nizam.storage.db import connect

ART = pathlib.Path(".artifacts/s7-source")
RAW = pathlib.Path("/mnt/e/nizam-data")

SELECT = """
WITH d AS (
  SELECT s.id, s.instrument_id, s.document_id, s.printed_label, s.source_page,
         s.candidate_provision_id, s.canonical_provision_id, s.source_block_id,
         (SELECT coalesce(sum(pb.chars), 0) FROM provision x
            JOIN provision_block pb ON pb.provision_id = x.id
           WHERE x.instrument_id = s.instrument_id AND x.is_active
             AND x.path <@ cand.path) AS dsub,
         EXISTS (SELECT 1 FROM v_structural_adjudication_latest a
                  WHERE a.candidate_id = s.id
                    AND a.review_basis = 'source_verified') AS decided
    FROM v_structural_adjudication_pending s
    JOIN provision cand ON cand.id = s.candidate_provision_id AND cand.is_active
), e AS (
  -- `units` counts only units NOT yet source-verified. A `restore_citable`
  -- or `reparent` decision leaves its unit pending on purpose, so counting
  -- every pending unit made the batch selector re-offer expressions that had
  -- already been read end to end -- it ordered by a number that no longer
  -- moved. What schedules the work is how much reading an expression still
  -- needs, which is the undecided count.
  SELECT instrument_id, max(dsub) AS max_sub,
         count(*) FILTER (WHERE NOT decided) AS units,
         count(*) AS units_pending
    FROM d GROUP BY 1
)
SELECT d.document_id, d.printed_label, d.source_page, d.dsub, e.units,
       e.units_pending, e.max_sub,
       d.id::text AS candidate_id,
       b.object_key, doc.page_count,
       regexp_replace(coalesce(tb.text, ''), E'\\s+', ' ', 'g') AS demoted_text,
       (SELECT regexp_replace(
                 coalesce(string_agg(k.text, ' ' ORDER BY k.id), ''),
                 E'\\s+', ' ', 'g')
          FROM provision_block kb JOIN text_block k ON k.id = kb.block_id
         WHERE kb.provision_id = d.canonical_provision_id) AS kept_text,
       (SELECT p.marginal_note FROM provision p
         WHERE p.id = d.canonical_provision_id) AS kept_note,
       (SELECT c2.kind::text || ' ' || c2.label
                 || coalesce(' under ' || (SELECT pa.kind::text || ' ' || pa.label
                                             FROM provision pa WHERE pa.id = c2.parent_id), ' at root')
          FROM provision c2 WHERE c2.id = d.candidate_provision_id) AS demoted_ancestry,
       (SELECT count(*) FROM provision p
         WHERE p.instrument_id = d.instrument_id AND p.is_active
           AND p.kind = 'section') AS sections_in_expression,
       -- Does the demoted node's own text also hang under a citable section?
       -- If it does, accepting costs no law; if it does not, accepting buries it.
       (SELECT count(*) FROM provision_block cb
         WHERE cb.provision_id = d.candidate_provision_id
           AND EXISTS (SELECT 1 FROM provision_block ob
                         JOIN provision op ON op.id = ob.provision_id
                                          AND op.is_active
                        WHERE ob.block_id = cb.block_id
                          AND op.id <> d.candidate_provision_id
                          AND EXISTS (SELECT 1 FROM provision sec
                                       WHERE sec.instrument_id = op.instrument_id
                                         AND sec.is_active AND sec.kind = 'section'
                                         AND op.path <@ sec.path))) AS blocks_also_under_section,
       (SELECT count(*) FROM provision_block cb
         WHERE cb.provision_id = d.candidate_provision_id) AS blocks_on_candidate
  FROM d
  JOIN e ON e.instrument_id = d.instrument_id
  JOIN document doc ON doc.id = d.document_id
  JOIN blob b ON b.sha256 = doc.sha256
  LEFT JOIN text_block tb ON tb.id = d.source_block_id
 WHERE e.max_sub < %(max_subtree)s
   AND e.max_sub >= %(min_subtree)s
   AND NOT EXISTS (SELECT 1 FROM v_toc_gap_pending g
                    WHERE g.instrument_id = d.instrument_id)
   AND NOT d.decided
   AND d.instrument_id IN (
        SELECT instrument_id FROM e
         WHERE max_sub < %(max_subtree)s AND max_sub >= %(min_subtree)s
           AND units > 0
           AND NOT EXISTS (SELECT 1 FROM v_toc_gap_pending g2
                            WHERE g2.instrument_id = e.instrument_id)
         ORDER BY units, instrument_id
         LIMIT %(limit)s)
 ORDER BY d.document_id, d.source_page, d.printed_label
"""


def render(object_key: str, page: int, stem: str) -> pathlib.Path | None:
    """Rasterise one page. pdftoppm names its output; find what it wrote."""
    src = RAW / object_key
    if not src.exists():
        return None
    out = ART / stem
    ART.mkdir(parents=True, exist_ok=True)
    existing = sorted(ART.glob(f"{stem}-*.png"))
    if existing:
        return existing[0]
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "130", "-png",
         str(src), str(out)],
        check=False, capture_output=True)
    written = sorted(ART.glob(f"{stem}-*.png"))
    return written[0] if written else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-subtree", type=int, default=500)
    ap.add_argument("--min-subtree", type=int, default=0)
    ap.add_argument("--limit", type=int, default=12,
                    help="expressions, not units")
    ap.add_argument("--out", default=".s7_batch.json")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SELECT, {"max_subtree": a.max_subtree,
                             "min_subtree": a.min_subtree,
                             "limit": a.limit})
        rows = cur.fetchall()

    batch, missing = [], 0
    for (doc, label, page, dsub, units, upend, max_sub, cid, key, pages,
         demoted, kept, note, ancestry, nsec, shared, nblocks) in rows:
        stem = f"doc{doc}-p{page}"
        path = render(key, page, stem)
        if path is None:
            missing += 1
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        batch.append({
            "document_id": doc,
            "printed_label": label,
            "candidate_id": cid,
            "resolution": None,
            "observed": None,
            "render": str(path).replace("\\", "/"),
            "render_sha256": digest,
            "_source_page": page,
            "_document_pages": pages,
            "_units_in_expression": units,
            "_units_pending_in_expression": upend,
            "_demoted_subtree_chars": dsub,
            "_largest_subtree_in_expression": max_sub,
            "_demoted_text": (demoted or "")[:400],
            "_kept_marginal_note": note,
            "_kept_text": (kept or "")[:400],
            "_demoted_ancestry": ancestry,
            "_sections_in_expression": nsec,
            "_blocks_on_candidate": nblocks,
            "_blocks_also_under_a_section": shared,
        })

    pathlib.Path(a.out).write_text(json.dumps(batch, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    exprs = len({(b["document_id"]) for b in batch})
    print(f"units      : {len(batch)}")
    print(f"documents  : {exprs}")
    print(f"pages      : {len({b['render'] for b in batch})}")
    if missing:
        print(f"unrendered : {missing}  (source blob not on disk)")
    print(f"written    : {a.out}")
    for b in batch:
        print(f"  doc {b['document_id']:>5} p{b['_source_page']:<3} "
              f"label {b['printed_label']:<8} sub {b['_demoted_subtree_chars']:>5}  "
              f"{b['_demoted_text'][:64]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
