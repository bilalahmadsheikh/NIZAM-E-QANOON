"""Read-only diagnostic: compare printed ``Rule N.`` blocks with a fresh tree."""
from __future__ import annotations

import argparse
import re
from collections import Counter

from nizam.corpus.segment import segment
from nizam.storage import legal_write

RULE = re.compile(r"^\s*Rules?\s*(\d{1,4})\s*[.]", re.I)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document_id", type=int)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    blocks = legal_write.blocks_for(args.document_id)
    result = segment(blocks)
    section_blocks = {
        node.first_block for node in result.flatten()
        if node.kind == "section" and node.first_block is not None
    }
    missing = []
    dispositions = Counter()
    for block in blocks:
        match = RULE.match(block["text"] or "")
        if not match or block["id"] in section_blocks:
            continue
        role,node = result.block_roles.get(block["id"], ("absent", None))
        dispositions[(role, node.kind if node else None)] += 1
        missing.append((
            block["id"], block["page_no"], match.group(1), role,
            node.kind if node else None, node.label if node else None,
            " ".join((block["text"] or "").split())[:220],
        ))

    print(f"printed Rule blocks: {sum(1 for b in blocks if RULE.match(b['text'] or ''))}")
    print(f"fresh section anchors: {len(section_blocks)}")
    print(f"printed Rule blocks without section anchor: {len(missing)}")
    for key,count in dispositions.most_common():
        print(f"  role={key[0]} owner={key[1]}: {count}")
    print("\nblock\tpage\trule\trole\towner_kind\towner_label\ttext")
    for row in missing[:args.limit]:
        print("\t".join("" if value is None else str(value) for value in row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
