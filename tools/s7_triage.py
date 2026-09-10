"""Decide every repeated-label collision on evidence, so nothing stays uncitable.

THE PROBLEM, STATED PRECISELY. When two sections share a number the segmenter
keeps one and retypes the other from `section` to `clause`. The text is not
deleted -- it is still there, still active -- but it stops being a section, so it
cannot be cited. INV-4 makes the provision the citable unit, and a provision that
cannot be named is, for every purpose above L2, not in the corpus.

WHY BLANKET ADJUDICATION IS THE WRONG FIX. Adjudicating a collision -- with ANY
resolution -- removes it from v_structural_adjudication_pending, which is what
v_release_instrument tests. So recording `accept_non_citable` clears S7 AND
unblocks the document for release, while the law itself stays a clause. That
turns a visible defect into an invisible one. 4,498 decisions have already been
recorded this way, none by a human.

WHAT THE EVIDENCE SHOWS. Comparing the block kept as the section against the
block demoted to a clause, across the pending queue:

    kept 51 chars, demoted 409     597 units   the index was kept, the law demoted
    kept 549 chars, demoted 77     589 units   probably decided correctly
    comparable / unclear         1,184 units   needs a human or a better rule

So there is no single rule, and a tool that pretends otherwise would be the same
mistake in a new coat. This one CLASSIFIES and EVIDENCES; it does not decide.

WHAT ACTUALLY FIXES IT. Re-segmentation, after the parser learns to tell a
contents entry from a body section. Retyping a provision in place would sit
outside the append-only revision model (doc 02 §5), and adjudication alone
changes no text. So this emits regression fixtures the segmenter can be fixed
against -- the durable repair -- and a ranked worklist for the residue.

    ./nz s7                        the whole pending queue, classified
    ./nz s7 --exclude-toc          skip documents another agent is re-segmenting
    ./nz s7 --fixtures out.json    write regression cases for the segmenter
    ./nz s7 --render 5             render source pages for the worst cases
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from nizam.storage.db import connect

CORPUS = Path("/mnt/e/nizam-data")

# A contents entry is a label plus a heading and nothing else: "2. Definitions."
# A body section carries the provision. The distinction is what the segmenter is
# getting wrong, so it is measured rather than assumed.
CONTENTS_LIKE = re.compile(r"^\s*\d+[A-Za-z-]*\.\s*[^.]{0,60}\.?\s*$")
ELIDED = re.compile(r"\*{3,}")          # "1. ***** 2. *****" -- an index with text elided

PENDING = """
SELECT v.id, v.document_id, v.printed_label, v.candidate_provision_id,
       v.canonical_provision_id,
       (v.evidence->>'group_size')::int  AS grp,
       (v.evidence->>'parent_kind')      AS parent_kind,
       v.source_page, v.canonical_source_page,
       k.text AS kept_text, d.text AS demoted_text,
       kp.kind AS kept_kind, dp.kind AS demoted_kind,
       doc.sha256
  FROM v_structural_adjudication_pending v
  LEFT JOIN text_block k  ON k.id  = v.canonical_source_block_id
  LEFT JOIN text_block d  ON d.id  = v.source_block_id
  LEFT JOIN provision  kp ON kp.id = v.canonical_provision_id
  LEFT JOIN provision  dp ON dp.id = v.candidate_provision_id
  LEFT JOIN document  doc ON doc.id = v.document_id AND doc.is_active
 WHERE k.text IS NOT NULL AND d.text IS NOT NULL
   AND (%s::boolean IS NOT TRUE
        OR v.document_id NOT IN (SELECT document_id FROM v_toc_gap))
 ORDER BY v.document_id, v.printed_label
"""


def classify(kept: str, demoted: str, grp: int, parent_kind: str) -> tuple[str, str, str]:
    """Return (verdict, proposed_resolution, why). Never certain -- always evidenced."""
    k, d = (kept or "").strip(), (demoted or "").strip()
    kl, dl = len(k), len(d)

    if grp >= 10:
        return ("compendium", "split_instrument",
                f"{grp} siblings share this label; several Acts in one PDF")

    if ELIDED.search(k):
        return ("inverted", "restore_citable",
                "the kept block is an index with its text elided (*****)")

    if CONTENTS_LIKE.match(k) and dl >= max(3 * kl, 120):
        return ("inverted", "restore_citable",
                f"kept block reads as a contents entry ({kl} chars); "
                f"demoted block carries the provision ({dl} chars)")

    if dl >= 3 * kl and dl >= 120:
        return ("inverted", "restore_citable",
                f"demoted block is {dl // max(kl, 1)}x longer ({dl} vs {kl} chars)")

    if kl >= 3 * dl and kl >= 120:
        return ("probably-correct", "accept_non_citable",
                f"kept block is {kl // max(dl, 1)}x longer ({kl} vs {dl} chars)")

    if parent_kind and parent_kind != "instrument":
        return ("nesting", "reparent",
                f"collision under a {parent_kind}, not the instrument — "
                "likely a subsection read as a section")

    return ("unclear", "",
            f"kept {kl} chars, demoted {dl} chars — no rule separates these")


ORDER = ["inverted", "compendium", "nesting", "unclear", "probably-correct"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify S7 collisions on evidence")
    ap.add_argument("--exclude-toc", action="store_true",
                    help="skip documents that also have TOC gaps (another agent may be there)")
    ap.add_argument("--fixtures", type=Path, help="write segmenter regression cases here")
    ap.add_argument("--render", type=int, default=0, metavar="N",
                    help="render source pages for the N worst inverted cases")
    ap.add_argument("--limit", type=int, default=6, help="examples shown per class")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(PENDING, (a.exclude_toc, ))
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    for r in rows:
        r["verdict"], r["resolution"], r["why"] = classify(
            r["kept_text"], r["demoted_text"], r["grp"] or 0, r["parent_kind"])

    buckets: dict[str, list] = {}
    for r in rows:
        buckets.setdefault(r["verdict"], []).append(r)

    scope = "excluding TOC-gap documents" if a.exclude_toc else "whole pending queue"
    print(f"\nS7 triage — {len(rows)} collisions, {scope}\n")
    print(f"  {'verdict':18} {'units':>6} {'docs':>6}  proposed resolution")
    print("  " + "-" * 62)
    for v in ORDER:
        b = buckets.get(v, [])
        if not b:
            continue
        docs = len({x["document_id"] for x in b})
        res = b[0]["resolution"] or "(needs a person)"
        print(f"  {v:18} {len(b):>6} {docs:>6}  {res}")
    print()

    for v in ORDER:
        b = buckets.get(v, [])
        if not b:
            continue
        print(f"--- {v.upper()} ({len(b)} units)")
        for r in b[:a.limit]:
            k = " ".join((r["kept_text"] or "").split())[:62]
            d = " ".join((r["demoted_text"] or "").split())[:62]
            print(f"  doc {r['document_id']}  label {r['printed_label']}  p{r['source_page']}")
            print(f"     kept as {r['kept_kind']:<10} {k}")
            print(f"     demoted to {r['demoted_kind']:<7} {d}")
            print(f"     -> {r['why']}")
        if len(b) > a.limit:
            print(f"  … {len(b) - a.limit} more")
        print()

    if a.fixtures:
        # One fixture per inverted case: the segmenter must stop preferring the
        # contents entry. These are the durable repair; adjudication is not.
        fx = [{"document_id": r["document_id"], "label": r["printed_label"],
               "page": r["source_page"],
               "must_be_section": " ".join((r["demoted_text"] or "").split())[:400],
               "must_not_be_section": " ".join((r["kept_text"] or "").split())[:400],
               "why": r["why"]}
              for r in buckets.get("inverted", [])]
        a.fixtures.write_text(json.dumps(fx, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {len(fx)} regression fixtures to {a.fixtures}")

    if a.render:
        out = CORPUS / "s7-review"
        out.mkdir(parents=True, exist_ok=True)
        worst = sorted(buckets.get("inverted", []),
                       key=lambda r: -len(r["demoted_text"] or ""))[:a.render]
        for r in worst:
            sha, page = r["sha256"], r["source_page"] or 1
            src = None
            for p in CORPUS.rglob(f"{sha}.pdf"):
                src = p
                break
            if not src:
                print(f"  doc {r['document_id']}: source pdf not found for {sha[:12]}")
                continue
            dest = out / f"doc{r['document_id']}-p{page}"
            subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "110",
                            "-png", str(src), str(dest)], check=False)
            print(f"  rendered doc {r['document_id']} page {page} -> {dest}*.png")

    print("\nNOTE: adjudicating any of these clears S7 AND unblocks the document for\n"
          "release, without changing a single provision. The repair is a parser fix\n"
          "plus re-segmentation. Use --fixtures to drive that.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
