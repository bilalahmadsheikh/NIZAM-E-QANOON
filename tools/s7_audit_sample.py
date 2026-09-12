"""Audit the S7 decisions a program made and approved by itself.

4,498 repeated-label collisions were resolved as ``accept_non_citable`` by
``nizam.structural_adjudicator/1``. Every one demotes a provision from
``section`` to ``clause``, which under INV-4 removes it from citation. None was
reviewed by a person, and the same rule is known to have got at least one case
backwards: in document 16 it kept "It shall come into force at once" -- a
commencement subsection -- as section 2, and demoted "In the Sind Civil Servants
Act, 1973, section 9-A shall be omitted", the entire operative purpose of that
Ordinance.

So the question this answers is not "is S7 closed" but "which of those 4,498
need source review". It samples and triages on evidence a reviewer would use,
then can render pages for visual confirmation.  Its automatic labels are not a
measured error rate; only a person reading the rendered source may supply that.
It writes no decision and changes no provision.

WEIGHTING. A uniform sample would be dominated by two- and three-way collisions,
which are the easy cases. Large sibling groups are where a compendium was
mistaken for one Act and where an error costs most, so the sample is drawn
weighted by group size -- the goal's "weighted 200-decision" requirement.

    ./nz s7-audit                 draw and classify the sample
    ./nz s7-audit --render 12     also render source pages for the worst
    ./nz s7-audit --size 200
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from nizam.corpus.segment import _AMEND_NOTE, _FOOTNOTE
from nizam.storage.db import connect

CORPUS = Path("/mnt/e/nizam-data")
OUT = CORPUS / "s7-audit"

# STRATIFIED, not top-N. A first version ordered by group_size DESC and drew all
# 200 rows from one document whose label was shared 194 ways -- a sample that
# describes a single wage notification, not 4,555 decisions. Weighting must
# over-represent large groups WITHOUT collapsing onto them, so the draw is:
#
#   * four bands by sibling-group size, sampled in a 1:2:3:4 ratio so the
#     consequential cases carry four times their uniform weight;
#   * at most 8 rows per document, so no single compendium can dominate;
#   * ordered by a hash of the row id, so the same 200 come back every run and
#     a disputed verdict can be re-examined.
SAMPLE = """
WITH decided AS (
  SELECT a.id AS adjudication_id, a.resolution, a.decided_by,
         c.document_id, c.printed_label, c.source_page, c.canonical_source_page,
         (c.evidence->>'group_size')::int AS grp,
         (c.evidence->>'parent_kind')     AS parent_kind,
         k.text AS kept_text, d.text AS demoted_text,
         doc.sha256
    FROM segmentation_structural_adjudication a
    JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
    LEFT JOIN text_block k ON k.id = c.canonical_source_block_id
    LEFT JOIN text_block d ON d.id = c.source_block_id
    LEFT JOIN document doc ON doc.id = c.document_id AND doc.is_active
   WHERE a.resolution = 'accept_non_citable'
     AND a.decided_by = 'nizam.structural_adjudicator/1'
     AND k.text IS NOT NULL AND d.text IS NOT NULL
),
banded AS (
  SELECT *, CASE WHEN coalesce(grp,1) >= 50 THEN 4
                 WHEN coalesce(grp,1) >= 10 THEN 3
                 WHEN coalesce(grp,1) >= 4  THEN 2
                 ELSE 1 END AS band,
         row_number() OVER (PARTITION BY document_id
                            ORDER BY md5(adjudication_id::text)) AS per_doc
    FROM decided
),
capped AS (
  SELECT *, row_number() OVER (PARTITION BY band ORDER BY md5(adjudication_id::text)) AS rn
    FROM banded WHERE per_doc <= 8
),
quota_pick AS (
  SELECT * FROM capped WHERE rn <= ceil(%s * band / 10.0)
),
chosen AS (
  SELECT * FROM quota_pick
   ORDER BY band DESC, rn, md5(adjudication_id::text)
   LIMIT %s
),
fill AS (
  SELECT c.* FROM capped c
   WHERE NOT EXISTS (
       SELECT 1 FROM chosen q WHERE q.adjudication_id=c.adjudication_id
   )
   ORDER BY md5(c.adjudication_id::text)
   LIMIT greatest(%s - (SELECT count(*) FROM chosen), 0)
)
SELECT * FROM chosen
UNION ALL
SELECT * FROM fill
 ORDER BY band DESC, rn
"""


def _is_footnote(text: str) -> bool:
    """Is this an amendment footnote rather than a provision?

    Reuses the segmenter's own definitions rather than a private guess, because
    a private guess is what made the first version of this audit report a 20.3%
    error rate. Document 3892 shares "label 1" thirty-eight ways because every
    page carries footnotes numbered 1-4 ("Subs. by Sind Act 17 of 1975, s. 3"),
    and the rendered page shows both sides of those collisions are footnotes.
    Demoting one footnote in favour of another is not an error about the law.
    """
    head = (text or "").strip()[:160]
    return bool(_FOOTNOTE.match(head) or _AMEND_NOTE.match(head))


def verdict(kept: str, demoted: str, grp: int) -> tuple[str, str]:
    """Classify on the evidence a reviewer would weigh. Never certain."""
    k, d = (kept or "").strip(), (demoted or "").strip()
    kl, dl = len(k), len(d)

    # Footnote-vs-footnote first: neither side is a provision, so the decision
    # cannot have demoted the law. It is still a defect -- footnotes should never
    # have become sections -- but it belongs to extraction, not to S7.
    if _is_footnote(k) and _is_footnote(d):
        return "not-law", "both blocks are amendment footnotes, not provisions"
    if _is_footnote(k) and not _is_footnote(d):
        return "WRONG", "a footnote was kept as the section and the provision demoted"
    if _is_footnote(d) and not _is_footnote(k):
        return "right", "the demoted block is an amendment footnote"

    if "***" in k:
        return "WRONG", "kept block is an index line with its text elided"
    if dl >= 3 * kl and dl >= 120:
        return "WRONG", (f"demoted block carries the provision ({dl} chars) while the "
                         f"kept block is a heading ({kl} chars)")
    if kl >= 3 * dl and kl >= 120:
        return "right", f"kept block carries the provision ({kl} vs {dl} chars)"
    if grp and grp >= 10:
        return "SUSPECT", (f"{grp} siblings share this label — a compendium, where "
                           "demoting is the wrong repair even if this pair is close")
    return "unclear", f"kept {kl} chars, demoted {dl} chars — no rule separates these"


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit machine-made S7 decisions")
    ap.add_argument("--size", type=int, default=200)
    ap.add_argument("--render", type=int, default=0, metavar="N",
                    help="render source pages for the N worst cases")
    ap.add_argument("--show", type=int, default=5)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SAMPLE, (a.size, a.size, a.size))
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.execute("SELECT count(*) FROM segmentation_structural_adjudication "
                    "WHERE resolution = 'accept_non_citable' "
                    "AND decided_by = 'nizam.structural_adjudicator/1'")
        population = cur.fetchone()[0]

    for r in rows:
        r["verdict"], r["why"] = verdict(r["kept_text"], r["demoted_text"], r["grp"])

    order = ["WRONG", "SUSPECT", "unclear", "not-law", "right"]
    buckets: dict[str, list] = {}
    for r in rows:
        buckets.setdefault(r["verdict"], []).append(r)

    n = len(rows)
    print(f"\nS7 decision audit — {n} sampled from {population:,} "
          f"machine-made `accept_non_citable` decisions")
    print(f"weighted toward large sibling groups\n")
    print(f"  {'verdict':10} {'n':>5} {'share':>7}   meaning")
    print("  " + "-" * 72)
    meaning = {
        "WRONG":   "the law was demoted and a heading kept in its place",
        "SUSPECT": "compendium — demoting is the wrong repair regardless",
        "unclear": "needs a person to read the page",
        "right":   "the kept block does carry the provision",
        "not-law": "both blocks are footnotes — a different defect, not S7",
    }
    for v in order:
        b = buckets.get(v, [])
        if b:
            print(f"  {v:10} {len(b):>5} {100*len(b)/n:>6.1f}%   {meaning[v]}")

    wrong = len(buckets.get("WRONG", []))
    suspect = len(buckets.get("SUSPECT", []))
    print(f"\n  HEURISTIC FLAG RATE (NOT SOURCE-AUDITED): "
          f"{100*wrong/n:.1f}% likely wrong"
          f"{f', {100*(wrong+suspect)/n:.1f}% likely wrong or unsafe' if suspect else ''}")
    print("  Render and read the source pages before reporting an error rate.\n")

    for v in order:
        for r in buckets.get(v, [])[:a.show]:
            k = " ".join((r["kept_text"] or "").split())[:60]
            d = " ".join((r["demoted_text"] or "").split())[:60]
            print(f"  [{v}] doc {r['document_id']} label {r['printed_label']} "
                  f"(group {r['grp']}) p{r['source_page']}")
            print(f"      kept    : {k}")
            print(f"      demoted : {d}")
            print(f"      -> {r['why']}")
        if buckets.get(v) and len(buckets[v]) > a.show:
            print(f"      … {len(buckets[v]) - a.show} more {v}\n")
        elif buckets.get(v):
            print()

    if a.render:
        OUT.mkdir(parents=True, exist_ok=True)
        worst = (buckets.get("WRONG", []) + buckets.get("SUSPECT", []))[:a.render]
        with connect() as conn, conn.cursor() as cur:
            for r in worst:
                cur.execute("SELECT object_key FROM blob WHERE sha256=%s", (r["sha256"],))
                row = cur.fetchone()
                if not row:
                    continue
                src, page = CORPUS / row[0], r["source_page"] or 1
                dest = OUT / f"doc{r['document_id']}-{r['printed_label']}-p{page}"
                subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "110",
                                "-png", str(src), str(dest)], check=False)
                print(f"  rendered doc {r['document_id']} p{page} -> {dest}*.png")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample.json").write_text(json.dumps(
        [{k: v for k, v in r.items() if k not in ("kept_text", "demoted_text")}
         for r in rows], ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"  sample written to {OUT / 'sample.json'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
