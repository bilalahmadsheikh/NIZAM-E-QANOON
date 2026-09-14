"""Name the exact rule that demoted a section, by line number.

Reading a rendered page says a section is printed and the tree does not hold it.
It does not say why, and the segmenter has several independent rules that turn a
classified section into a clause. Guessing which one fired has been wrong more
often than right here.

This builds an instrumented COPY of the segmenter -- the real file is never
touched -- with a print at every ``kind = "clause"`` assignment, runs one
document through it, and reports the line that fired together with the tree the
run produced. Three defects were found this way in one session, each in a single
run:

    DEMOTE@2442 label='3'   the numbered-list rule, measuring indentation
                            against a marginal heading's x0
    DEMOTE@2583 label='5'   the same rule, ignoring the detached heading the
                            source prints beside the block
    (none)                  document 3255 fires nothing: its defect is upstream,
                            104 subsections parented straight to a chapter

That last line is the point. A run with no output is evidence too.

    ./nz why-demoted 275
    ./nz why-demoted 275 --label 5
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import sys

from nizam.storage import legal_write
from nizam.storage.db import connect

SOURCE = pathlib.Path("nizam/corpus/segment.py")
PROBE = pathlib.Path(".segment_instrumented.py")


def build_probe() -> int:
    lines = SOURCE.read_text(encoding="utf-8").split("\n")
    out: list[str] = []
    sites = 0
    for lineno, line in enumerate(lines, 1):
        out.append(line)
        match = re.match(r'^(\s*)(kind|node\.kind) = "clause"\s*$', line)
        if not match:
            continue
        indent, target = match.group(1), match.group(2)
        var = "label" if target == "kind" else "node.label"
        out.append(f'{indent}import sys as _s; print(f"DEMOTE@{lineno} '
                   f'label={{{var}!r}}", file=_s.stderr)')
        sites += 1
    PROBE.write_text("\n".join(out), encoding="utf-8")
    return sites


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("document", type=int)
    ap.add_argument("--label", help="only print tree nodes with this label")
    ap.add_argument("--keep", action="store_true",
                    help="leave the instrumented copy on disk")
    a = ap.parse_args()

    sites = build_probe()
    print(f"instrumented {sites} demotion sites", file=sys.stderr)

    spec = importlib.util.spec_from_file_location(
        "segment_instrumented", str(PROBE.resolve()))
    module = importlib.util.module_from_spec(spec)
    sys.modules["segment_instrumented"] = module
    spec.loader.exec_module(module)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT source_observation_id FROM instrument
                        WHERE document_id=%s AND is_active AND duplicate_of IS NULL
                        LIMIT 1""", (a.document,))
        row = cur.fetchone()
    if row is None:
        print(f"document {a.document}: no active canonical instrument")
        return 1
    observation = row[0]

    blocks = legal_write.blocks_for(a.document)
    seg = module.segment(
        blocks,
        curation_patches=legal_write.segmentation_patches_for(observation),
        toc_dispositions=legal_write.toc_dispositions_for(observation),
    )

    print(f"\ndoc {a.document} obs {observation}: "
          f"toc {len(seg.toc)} entries, missing {sorted(seg.missing)}")

    def walk(node, depth=0):
        for child in node.children:
            if a.label is None or str(child.label) == a.label:
                print(f"  {'  ' * depth}{child.kind:<12} {str(child.label):<8} "
                      f"parent={node.kind} {node.label!r} "
                      f"block={child.first_block}")
            walk(child, depth + 1)

    walk(seg.root)
    if not a.keep:
        PROBE.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
