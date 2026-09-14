"""Diff the trees two segmenters build for the same documents.

`compare_fingerprints` scores `unlinked`, which is what the release gate counts,
and that is the right measure for whether a change may land. It is not a
sufficient one. A section demoted where no contents row promised it moves
nothing the gate can see -- and `find_stub_citations` showed where that ends:
359 citations across 194 documents resolving to less than half the provision,
because a phantom kept the section number and the body became a clause.

So when a candidate rule moves `demoted` without moving `sections` or
`unlinked`, the aggregate cannot say whether it carved finer structure out of a
block or buried a provision. This answers that by naming the nodes.

The inline fused-note rule was cleared this way. Fifteen documents gained
demotions with no other movement; every one of them gained *clause* nodes and
lost no section:

    doc 1977: nodes 91 -> 101  sections 44 -> 44   LOST []   GAINED []
    doc 2739: nodes 158 -> 159 sections 30 -> 31   LOST []   GAINED ['26']

Point it at any other copy of the segmenter -- a `.bak`, a git worktree, a
hand-edited probe:

    ./nz diff-trees .segment_inline_off.py 1977 2023 1524
    ./nz diff-trees nizam/corpus/segment.py.bak24 --file .probe_improved.txt

Reads only, and imports both copies rather than editing anything on disk.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

from nizam.storage import legal_write
from nizam.storage.db import connect

CURRENT = pathlib.Path("nizam/corpus/segment.py")
CITABLE = ("section", "article")


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(path.resolve()))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def walk(node, out: list, depth: int = 0) -> None:
    for child in node.children:
        out.append((depth, child.kind, str(child.label)))
        walk(child, out, depth + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("other", help="the segmenter to compare against")
    ap.add_argument("documents", nargs="*", type=int)
    ap.add_argument("--file", help="read document ids from this file")
    ap.add_argument("--base", default=str(CURRENT),
                    help="the segmenter to treat as current (default the repo's)")
    a = ap.parse_args()

    docs = list(a.documents)
    if a.file:
        for line in pathlib.Path(a.file).read_text(encoding="utf-8").split():
            if line.isdigit():
                docs.append(int(line))
    if not docs:
        print("no documents given")
        return 2

    base = load("seg_base", pathlib.Path(a.base))
    other = load("seg_other", pathlib.Path(a.other))

    lost_total = gained_total = 0
    for doc in docs:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT source_observation_id FROM instrument
                            WHERE document_id=%s AND is_active
                              AND duplicate_of IS NULL LIMIT 1""", (doc,))
            row = cur.fetchone()
        if row is None:
            print(f"doc {doc}: no active canonical instrument")
            continue
        blocks = legal_write.blocks_for(doc)
        kw = dict(curation_patches=legal_write.segmentation_patches_for(row[0]),
                  toc_dispositions=legal_write.toc_dispositions_for(row[0]))
        left, right = other.segment(blocks, **kw), base.segment(blocks, **kw)
        tl, tr = [], []
        walk(left.root, tl)
        walk(right.root, tr)
        sl = {(d, lb) for d, k, lb in tl if k in CITABLE}
        sr = {(d, lb) for d, k, lb in tr if k in CITABLE}
        lost = sorted(x[1] for x in sl - sr)
        gained = sorted(x[1] for x in sr - sl)
        lost_total += len(lost)
        gained_total += len(gained)
        flag = "  <-- LOSES SECTIONS" if lost else ""
        print(f"doc {doc}: contents {len(left.toc)}  nodes {len(tl)} -> {len(tr)}  "
              f"sections {len(sl)} -> {len(sr)}{flag}")
        if lost:
            print(f"  lost   : {lost}")
        if gained:
            print(f"  gained : {gained}")

    print(f"\n{len(docs)} documents: {lost_total} sections lost, "
          f"{gained_total} gained")
    if lost_total:
        print("a section lost where no contents row promised it is invisible to "
              "the gate -- read those against source before landing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
