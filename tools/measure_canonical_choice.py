"""Does the kept occurrence of a repeated label actually carry the law?

The segmentation fingerprint cannot answer this. It counts sections, clauses,
provisions and unlinked contents rows, and choosing the OTHER occurrence of a
repeated label as canonical changes none of them: one unit is a section and one
is a clause either way. A change that fixes which of two units a citation
resolves to is invisible to it -- the same blindness that let `seg.missing` pass
a change costing 56 release instruments.

So measure the property directly. For every repeated-label group the segmenter
resolves, ask whether the occurrence it kept carries text or children at all. A
kept unit with neither is a contents or index line that the parse turned into a
section, while the provision itself sits beside it as a demoted clause -- the
citation resolves to a heading with no law under it.

    ./nz canonical-choice                  the whole corpus
    ./nz canonical-choice --documents 1,2  a bounded set
"""
from __future__ import annotations

import argparse
import sys

from nizam.corpus.segment import segment
from nizam.storage import legal_write


def norm(value: str) -> str:
    return " ".join((value or "").split())


def carries_law(node) -> bool:
    """Text BEYOND the unit's own heading, or children.

    "Non-empty text" does not separate a contents line from a section: the line
    "48. Repeal and savings." parses with rest "Repeal and savings.", so its
    heading is its whole text. Mirrors the segmenter's own rule.
    """
    if node.children:
        return True
    body = norm("".join(node.text_parts)).casefold()
    head = norm(node.heading or "").casefold()
    if head and body.startswith(head.rstrip(". ")):
        body = body[len(head.rstrip(". ")):]
    return len(body.strip(" .—–-")) >= 20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--documents")
    ap.add_argument("--documents-file")
    ap.add_argument("--show", type=int, default=12)
    a = ap.parse_args()

    raw = a.documents
    if a.documents_file:
        raw = open(a.documents_file, encoding="utf-8").read()
    wanted = ({int(v) for chunk in raw.split() for v in chunk.split(",") if v.strip()}
              if raw else None)

    targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=True)
               if wanted is None or t[0] in wanted]
    print(f"measuring {len(targets)} documents", file=sys.stderr)

    groups = kept_without_law = kept_without_law_but_sibling_has = 0
    offenders: list[tuple[int, str, int]] = []
    for n, (doc_id, sha, obs, source_id, title, year,
            _doc_type, source_url) in enumerate(sorted(targets), 1):
        try:
            blocks = legal_write.blocks_for(doc_id)
            if not blocks:
                continue
            seg = segment(
                blocks,
                curation_patches=legal_write.segmentation_patches_for(obs),
                toc_dispositions=legal_write.toc_dispositions_for(obs))
        except Exception as exc:                        # noqa: BLE001
            print(f"{doc_id}\tERROR\t{type(exc).__name__}: {exc}"[:160])
            continue
        bad = 0
        for decision in seg.repeated_label_decisions:
            canonical = decision["canonical"]
            candidate = decision["candidate"]
            groups += 1
            canonical_has = carries_law(canonical)
            candidate_has = carries_law(candidate)
            if not canonical_has:
                kept_without_law += 1
                if candidate_has:
                    kept_without_law_but_sibling_has += 1
                    bad += 1
        if bad:
            offenders.append((doc_id, title or "", bad))
        if n % 300 == 0:
            print(f"  {n}/{len(targets)}", file=sys.stderr)

    print(f"repeated-label decisions            : {groups}")
    print(f"  kept occurrence carries no law    : {kept_without_law}")
    print(f"  ... while the demoted one does    : {kept_without_law_but_sibling_has}")
    print(f"  documents affected                : {len(offenders)}")
    for doc_id, title, bad in sorted(offenders, key=lambda r: -r[2])[:a.show]:
        print(f"    doc {doc_id:<6} {bad:>4}  {title[:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
