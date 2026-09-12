"""Find the CAUSE of the remaining defects, instead of waiting to notice one.

WHY THIS IS THE TOOL THAT MATTERS. Closing TOC gaps one document at a time hides
shared causes. An earlier version of this tool also taught the opposite lesson:
it searched every block, selected the printed contents entry itself, and claimed
94.9% of missing sections already existed in body text. Excluding active
``contents`` assignments reduced the measured recoverable share to 37%.

One diagnosis was worth more than two days of grinding. So the bottleneck is not
execution, it is FINDING THE PATTERN, and that is what this automates.

Every remaining defect is given a signature built from things that are cheap to
measure and likely to correlate with cause: where the text sits relative to the
document's own column geometry, what shape the label is, what role the block
carrying it was assigned, which portal it came from, and how concentrated the
defect is within its document. Signatures are then counted. A large cluster is a
candidate for one fix; a flat distribution is honest evidence that the residue
really is a long tail and should be worked case by case.

It proves nothing. A cluster is a hypothesis with a size attached -- worth the
cost of testing, in the order the sizes suggest.

    ./nz cluster                     rank the causes behind the TOC gaps
    ./nz cluster --defect s7         the same for repeated-label collisions
    ./nz cluster --show 3            sample rows from the top N clusters
"""
from __future__ import annotations

import argparse
import re

from nizam.storage.db import connect

# Column geometry is measured PER DOCUMENT. Five provincial portals use
# different page sizes, so a fixed x0 threshold is right for one and wrong for
# the rest -- the mistake that would make every cluster meaningless.
TOC_SQL = """
WITH gap AS (
  SELECT g.toc_entry_id,g.instrument_id,g.document_id,g.printed_label AS label,
         count(*) OVER (PARTITION BY g.document_id) AS gaps_in_doc,
         so.source_id
    FROM v_toc_gap_pending g
    JOIN instrument i ON i.id=g.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
    LEFT JOIN source_observation so ON so.id=i.source_observation_id
),
cols AS (
  SELECT b.document_id,
         percentile_disc(0.10) WITHIN GROUP (ORDER BY b.x0) AS x_left,
         percentile_disc(0.50) WITHIN GROUP (ORDER BY b.x0) AS x_body
    FROM text_block b JOIN document d ON d.id = b.document_id AND d.is_active
   GROUP BY b.document_id
),
active_role AS (
  SELECT pb.block_id,pb.role::text AS role
    FROM provision_block pb
    JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
),
hit AS (
  SELECT gap.document_id, gap.label, gap.gaps_in_doc,
         found.id AS block_id, found.x0, found.x1, c.x_left, c.x_body,
         length(found.text) AS chars, found.block_role,
         d.lane::text AS lane, gap.source_id
    FROM gap
    JOIN cols c ON c.document_id = gap.document_id
    JOIN document d ON d.id = gap.document_id AND d.is_active
    LEFT JOIN LATERAL (
      SELECT b.id,b.x0,b.x1,b.text,r.role AS block_role
        FROM text_block b
        LEFT JOIN active_role r ON r.block_id=b.id
       WHERE b.document_id=gap.document_id
         AND coalesce(r.role,'') <> 'contents'
         AND b.text ~ ('(^|[[:space:]])' ||
             regexp_replace(gap.label, '([.^$*+?()\\[\\]{}|\\\\])', '\\\\\\1', 'g') || '[.)]')
       ORDER BY b.id
       LIMIT 1
    ) found ON true
)
SELECT * FROM hit
"""

S7_SQL = """
WITH cols AS (
  SELECT b.document_id,
         percentile_disc(0.10) WITHIN GROUP (ORDER BY b.x0) AS x_left,
         percentile_disc(0.50) WITHIN GROUP (ORDER BY b.x0) AS x_body
    FROM text_block b JOIN document d ON d.id = b.document_id AND d.is_active
   GROUP BY b.document_id
)
SELECT v.document_id, v.printed_label AS label,
       (v.evidence->>'group_size')::int AS gaps_in_doc,
       k.id AS block_id, k.x0, k.x1, c.x_left, c.x_body,
       length(k.text) AS chars, pb.role::text AS block_role,
       d.lane::text AS lane, so.source_id
  FROM v_structural_adjudication_pending v
  JOIN document d ON d.id = v.document_id AND d.is_active
  JOIN cols c ON c.document_id = v.document_id
  LEFT JOIN source_observation so ON so.sha256 = d.sha256
  LEFT JOIN text_block k ON k.id = v.canonical_source_block_id
  LEFT JOIN provision_block pb ON pb.block_id = k.id
"""


def label_shape(label: str) -> str:
    if re.fullmatch(r"\d+", label):            return "plain"
    if re.fullmatch(r"\d+[A-Za-z]+", label):   return "num+letter"
    if re.fullmatch(r"\d+-[A-Za-z0-9]+", label): return "hyphenated"
    if "." in label:                            return "dotted"
    if re.fullmatch(r"[IVXLCivxlc]+", label):  return "roman"
    return "other"


def geometry(r: dict) -> str:
    if r["block_id"] is None:
        return "text-absent"
    x0, x1, xl, xb = r["x0"], r["x1"], r["x_left"], r["x_body"]
    if x0 is None or xl is None:
        return "no-geometry"
    if x0 <= xl + 6 and x1 > xb + 40:
        return "fused-margin+body"
    if x0 <= xl + 6:
        return "margin-only"
    return "body"


def density(n: int) -> str:
    if n is None:      return "?"
    if n == 1:         return "1 defect"
    if n <= 5:         return "2-5"
    if n <= 20:        return "6-20"
    return "20+"


def main() -> int:
    ap = argparse.ArgumentParser(description="Cluster remaining defects by likely cause")
    ap.add_argument("--defect", choices=("toc", "s7"), default="toc")
    ap.add_argument("--show", type=int, default=0, help="sample rows from the top N clusters")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(TOC_SQL if a.defect == "toc" else S7_SQL)
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    for r in rows:
        r["sig"] = (geometry(r), label_shape(r["label"] or ""),
                    r["block_role"] or "no-role", r["source_id"] or "?",
                    density(r["gaps_in_doc"]))

    clusters: dict[tuple, list] = {}
    for r in rows:
        clusters.setdefault(r["sig"], []).append(r)
    ranked = sorted(clusters.items(), key=lambda kv: -len(kv[1]))

    total = len(rows)
    print(f"\n{a.defect.upper()} defects: {total:,} in {len({r['document_id'] for r in rows})} documents\n")
    print(f"  {'n':>6} {'docs':>5} {'cum%':>6}  geometry            label        block role      portal")
    print("  " + "-" * 84)
    run = 0
    for sig, group in ranked[:a.top]:
        run += len(group)
        g, shape, role, src, dens = sig
        docs = len({r["document_id"] for r in group})
        print(f"  {len(group):>6} {docs:>5} {100*run/total:>5.1f}%  "
              f"{g:<19} {shape:<12} {role:<15} {src}")
    if len(ranked) > a.top:
        rest = sum(len(g) for _, g in ranked[a.top:])
        print(f"  {rest:>6} {'':>5} {100.0:>5.1f}%  … {len(ranked)-a.top} smaller clusters")

    big = [(s, g) for s, g in ranked if len(g) >= max(20, total * 0.03)]
    print(f"\n  {len(ranked)} distinct signatures; "
          f"{len(big)} clusters hold >=3% each, covering "
          f"{100*sum(len(g) for _, g in big)/total:.0f}% of the defects.")
    print("  A few large clusters means bulk fixes remain. A flat spread means the\n"
          "  residue is a genuine long tail and should be worked case by case.\n")

    for sig, group in ranked[:a.show]:
        print(f"--- {sig}   ({len(group)} defects)")
        for r in group[:4]:
            print(f"    doc {r['document_id']:<6} label {str(r['label']):<8} "
                  f"x0={r['x0']} x1={r['x1']} (left {r['x_left']}, body {r['x_body']}) "
                  f"{r['chars']} chars")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
