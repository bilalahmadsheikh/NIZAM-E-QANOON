"""A compact per-document fingerprint of what the segmenter would write.

Run it once with a parser change and once without, then diff the two files: any
document whose line moved is a document the change touched. Nothing is written
to the corpus.

    python .probe_fingerprint.py --documents 12,19,49 > before.tsv
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from nizam.storage import legal_write
from nizam.workers.segment import build

MUST_OWN_PROVISION = ("body", "heading", "schedule_row", "preamble")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--documents", help="comma-separated document ids")
    ap.add_argument("--documents-file",
                    help="file holding the comma-separated ids (avoids shell "
                         "quoting through PowerShell and WSL)")
    ap.add_argument("--marginal-fusion", action="store_true")
    ap.add_argument("--compare-fusion", action="store_true",
                    help="build both ways and print only changed fingerprints")
    ap.add_argument("--progress-every", type=int, default=50)
    a = ap.parse_args()

    raw = a.documents
    if a.documents_file:
        raw = pathlib.Path(a.documents_file).read_text(encoding="utf-8")
    if not raw:
        ap.error("give --documents or --documents-file")
    wanted = {int(v) for v in raw.split() for v in v.split(",") if v.strip()}
    targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=True) if t[0] in wanted]
    print(f"fingerprinting {len(targets)} of {len(wanted)} requested",
          file=sys.stderr)

    fields = ("sections", "provisions", "missing_toc", "stranded",
              "stranded_chars", "demoted", "footnote_blocks", "unlinked")
    print("document\t" + "\t".join(fields))
    changed = 0
    totals = {field: [0, 0] for field in fields}

    def fingerprint(doc_id, sha, observation_id, source_id, title, year,
                    source_url, blocks, fused):
        inst, seg = build(
            doc_id, sha, observation_id, source_id, title, year,
            source_url, blocks, legal_write.observed_on(observation_id),
            legal_write.segmentation_patches_for(observation_id),
            toc_dispositions=legal_write.toc_dispositions_for(observation_id),
            split_fused_margins=fused)
        stranded = [r for r in inst.block_roles
                    if r[2] is None and r[1] in MUST_OWN_PROVISION]
        # What the RELEASE GATE counts: contents rows left without a provision.
        # seg.missing is the segmenter's own view of unmatched labels and is a
        # different number. Verifying against it let a change measure "zero
        # regressions" while costing 56 release instruments -- 240 rows that
        # used to match by plain label stopped matching, and seg.missing never
        # moved.
        unlinked = sum(1 for e in inst.toc_entries
                       if e.get("provision_key") is None)
        return {
            "sections": sum(1 for r in inst.provisions
                            if r["kind"] == "section"),
            "provisions": len(inst.provisions),
            "missing_toc": len(seg.missing) if seg.toc else -1,
            "stranded": len(stranded),
            "stranded_chars": sum(r[3] for r in stranded),
            "demoted": seg.repeated_labels_demoted,
            "footnote_blocks": sum(1 for r in inst.block_roles
                                   if r[1] == "footnote"),
            "unlinked": unlinked,
        }
    for n, (doc_id, sha, observation_id, source_id, title, year,
            _doc_type, source_url) in enumerate(sorted(targets), 1):
        if a.progress_every == 1:
            print(f"  [{n}/{len(targets)}] doc {doc_id} …", file=sys.stderr, flush=True)
        try:
            blocks = legal_write.blocks_for(doc_id)
            if not blocks:
                print(f"{doc_id}\tNO_BLOCKS")
                continue
            if a.compare_fusion:
                before = fingerprint(
                    doc_id, sha, observation_id, source_id, title, year,
                    source_url, blocks, False)
                after = fingerprint(
                    doc_id, sha, observation_id, source_id, title, year,
                    source_url, blocks, True)
                if before != after:
                    changed += 1
                    for field in fields:
                        totals[field][0] += before[field]
                        totals[field][1] += after[field]
                    delta = ";".join(
                        f"{field}={before[field]}->{after[field]}"
                        for field in fields if before[field] != after[field]
                    )
                    print(f"{doc_id}\t{delta}")
            else:
                result = fingerprint(
                    doc_id, sha, observation_id, source_id, title, year,
                    source_url, blocks, a.marginal_fusion)
                print(f"{doc_id}\t" + "\t".join(
                    str(result[field]) for field in fields))
        except Exception as exc:                       # noqa: BLE001
            print(f"{doc_id}\tERROR\t{type(exc).__name__}: {exc}"[:200])
        if a.progress_every and n % a.progress_every == 0:
            print(f"  {n}/{len(targets)}", file=sys.stderr)
    if a.compare_fusion:
        print(f"changed\t{changed}")
        for field in fields:
            before, after = totals[field]
            if before != after:
                print(f"total_{field}\t{before}->{after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
