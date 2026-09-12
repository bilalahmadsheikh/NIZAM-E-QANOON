"""Which stored trees would be better if re-segmented by today's parser?

A stored instrument was written by whichever segmenter ran at the time. After a
parser fix the tree does not change until the document is replayed, so a
document can sit in the blocked queue on a defect that was repaired weeks ago --
document 33 carries 5 unresolved collisions from an old parse and has none at
all under the current one.

Replaying is not free: it retires the instrument's S7 adjudications, and an
instrument that is released today can fall out of release until those are
re-earned. So compare, per document, what is STORED against what the current
parser would produce, and report only the documents where replaying pays:

  * fewer unlinked contents rows, or the same with fewer collisions, and
  * nothing currently released would become blocked.

Reads only. It writes a document-id list for the segmentation worker.

    ./nz stale                 report
    ./nz stale --out FILE      also write the replay list
"""
from __future__ import annotations

import argparse
import sys

from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import build

STORED = """
SELECT i.document_id, i.id::text,
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id = i.id),
       (SELECT count(*) FROM v_structural_adjudication_pending s
         WHERE s.instrument_id = i.id),
       (SELECT count(*) FROM segmentation_structural_adjudication a
          JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
         WHERE c.instrument_id = i.id),
       (i.id IN (SELECT id FROM v_release_instrument)),
       (SELECT count(*) FROM provision p WHERE p.instrument_id = i.id
          AND p.is_active AND p.kind IN ('section','article'))
  FROM instrument i
 WHERE i.is_active AND i.duplicate_of IS NULL
   AND (EXISTS (SELECT 1 FROM v_toc_gap_pending g WHERE g.instrument_id = i.id)
     OR EXISTS (SELECT 1 FROM v_structural_adjudication_pending s
                 WHERE s.instrument_id = i.id))
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the replay list here")
    ap.add_argument("--show", type=int, default=14)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(STORED)
        stored: dict[int, dict] = {}
        for doc, iid, gaps, s7_pending, s7_decided, released, sections in cur:
            row = stored.setdefault(doc, {
                "gaps": 0, "s7_pending": 0, "s7_decided": 0,
                "released": False, "sections": 0, "instruments": 0})
            row["gaps"] += gaps
            row["s7_pending"] += s7_pending
            row["s7_decided"] += s7_decided
            row["released"] = row["released"] or released
            row["sections"] += sections
            row["instruments"] += 1

    # The segmentation work queue is observation-oriented, so a document that
    # currently materialises more than one legal expression can appear more
    # than once. Comparing or emitting it twice is not harmless: the ordinary
    # worker would perform two append-only replays, and it is the wrong worker
    # for a multi-expression source in the first place. Keep one target per
    # document and reserve reviewed multi-expression documents for the
    # dedicated materializer.
    queued = [t for t in legal_write.documents_needing_segmentation(
              redo=True, include_review=True) if t[0] in stored]
    targets_by_document: dict[int, tuple] = {}
    for target in queued:
        targets_by_document.setdefault(target[0], target)
    targets = [target for doc_id, target in targets_by_document.items()
               if stored[doc_id]["instruments"] == 1]
    multi_expression = sorted(
        doc_id for doc_id in targets_by_document
        if stored[doc_id]["instruments"] > 1
    )
    print(f"comparing {len(targets)} blocked documents against the current parser",
          file=sys.stderr)
    if multi_expression:
        print(f"holding {len(multi_expression)} multi-expression documents for "
              "the dedicated materializer", file=sys.stderr)

    pays, costs, same, failed, held = [], [], [], [], []
    for n, (doc_id, sha, obs, source_id, title, year,
            _doc_type, source_url) in enumerate(sorted(targets), 1):
        try:
            blocks = legal_write.blocks_for(doc_id)
            if not blocks:
                continue
            inst, seg = build(
                doc_id, sha, obs, source_id, title, year, source_url, blocks,
                legal_write.observed_on(obs),
                legal_write.segmentation_patches_for(obs),
                toc_dispositions=legal_write.toc_dispositions_for(obs))
        except Exception as exc:                        # noqa: BLE001
            failed.append((doc_id, f"{type(exc).__name__}: {exc}"[:90]))
            continue
        # The pending view has two arms: unresolved persisted TOC rows and the
        # segmentation run's legacy ``missing`` labels. Counting only proposed
        # entry rows produced a dangerous false improvement for documents 1438
        # and 2581: the parser recognised four TOC rows and linked all four, but
        # still reported 21/20 promised labels missing. Zero unlinked rows was
        # therefore not zero gaps. Fail closed on either signal.
        now_unlinked_entries = sum(
            1 for e in inst.toc_entries if e.get("provision_key") is None
        )
        now_unlinked = max(now_unlinked_entries, len(seg.missing))
        now_demoted = seg.repeated_labels_demoted
        now_sections = sum(1 for r in inst.provisions if r["kind"] == "section")
        was = stored[doc_id]
        was_collisions = was["s7_pending"] + was["s7_decided"]
        better = (now_unlinked < was["gaps"]
                  or (now_unlinked <= was["gaps"] and now_demoted < was_collisions))
        worse = now_unlinked > was["gaps"] or now_demoted > was_collisions
        record = (doc_id, was, now_unlinked, now_demoted, now_sections)
        # A large statute that loses half its sections needs reading, not a
        # batch replay. Fewer sections is often CORRECT -- a contents list that
        # had become sections stops being them -- but the Income Tax Ordinance
        # going 459 to 210 is not a thing to take on a gap count alone. Hold
        # them out and name them.
        big_section_loss = (was["sections"] >= 50
                            and now_sections < was["sections"] * 0.6)
        # A replay that leaves anything pending costs a released instrument.
        if was["released"] and (now_unlinked or now_demoted):
            costs.append(record)
        elif big_section_loss:
            held.append(record)
        elif better and not worse:
            pays.append(record)
        elif worse:
            costs.append(record)
        else:
            same.append(record)
        if n % 200 == 0:
            print(f"  {n}/{len(targets)}", file=sys.stderr)

    print(f"blocked documents compared : {len(targets)}")
    print(f"  replaying PAYS           : {len(pays)}")
    print(f"  replaying costs          : {len(costs)}")
    print(f"  no change                : {len(same)}")
    print(f"  parse failed             : {len(failed)}")
    print(f"  HELD, large section loss : {len(held)}  (read these, do not batch)")
    gaps_now = sum(r[1]["gaps"] for r in pays)
    gaps_after = sum(r[2] for r in pays)
    coll_now = sum(r[1]["s7_pending"] + r[1]["s7_decided"] for r in pays)
    coll_after = sum(r[3] for r in pays)
    print(f"\n  across the paying set: contents gaps {gaps_now} -> {gaps_after}, "
          f"collisions {coll_now} -> {coll_after}")
    for doc_id, was, unlinked, demoted, sections in sorted(
            pays, key=lambda r: (r[1]["gaps"] - r[2]) + (
                r[1]["s7_pending"] + r[1]["s7_decided"] - r[3]),
            reverse=True)[:a.show]:
        print(f"    doc {doc_id:<6} gaps {was['gaps']:>3} -> {unlinked:<3} "
              f"collisions {was['s7_pending'] + was['s7_decided']:>3} -> {demoted:<3} "
              f"sections {was['sections']:>3} -> {sections}")
    for doc_id, was, unlinked, demoted, sections in sorted(
            held, key=lambda r: r[1]["sections"] - r[4], reverse=True)[:8]:
        print(f"    HELD doc {doc_id:<6} sections {was['sections']:>4} -> {sections:<4} "
              f"gaps {was['gaps']:>3} -> {unlinked:<3} "
              f"collisions {was['s7_pending'] + was['s7_decided']:>3} -> {demoted}")
    for doc_id, why in failed[:6]:
        print(f"    FAILED doc {doc_id}: {why}")
    if a.out and pays:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(",".join(str(r[0]) for r in pays))
        print(f"\nwrote {a.out} ({len(pays)} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
