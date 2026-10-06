"""Read-only, single-document probe for an exact-block S7 reparent override."""

from __future__ import annotations

import argparse
import json

from nizam.corpus.segment import segment
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import reviewed_structural_overrides


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("document_id", type=int)
    ap.add_argument("source_block_id", type=int)
    ap.add_argument("parent_block_id", type=int)
    ap.add_argument("kind", choices=("clause", "subsection", "paragraph", "item"))
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("""SELECT source_observation_id FROM instrument
                        WHERE document_id=%s AND is_active AND duplicate_of IS NULL""",
                    (args.document_id,))
        observations = [row[0] for row in cur.fetchall()]
        if len(observations) != 1:
            raise SystemExit("requires exactly one active canonical expression")
        observation = observations[0]

    blocks = legal_write.blocks_for(args.document_id)
    patches = legal_write.segmentation_patches_for(observation)
    dispositions = legal_write.toc_dispositions_for(observation)
    resolutions = legal_write.structural_resolutions_for(args.document_id)
    overrides = reviewed_structural_overrides(resolutions, patches)
    if "source_reparent_blocks" in overrides:
        raise SystemExit("an existing source reparent override already applies")
    spec = {"source_block_id": args.source_block_id,
            "parent_block_id": args.parent_block_id, "kind": args.kind}
    baseline = segment(blocks, curation_patches=patches,
                       toc_dispositions=dispositions,
                       structural_resolutions=resolutions,
                       structural_overrides=overrides)
    proposed = segment(blocks, curation_patches=patches,
                       toc_dispositions=dispositions,
                       structural_resolutions=resolutions,
                       structural_overrides={**overrides,
                           "source_reparent_blocks": [spec]})

    def describe(seg):
        return [{"block": node.first_block, "kind": node.kind,
                 "label": node.label,
                 "parent_block": node.parent.first_block if node.parent else None,
                 "text_chars": len(node.text or "")}
                for node in seg.flatten()
                if node.first_block in (args.source_block_id, args.parent_block_id)]

    result = {
        "document_id": args.document_id, "source_observation_id": observation,
        "specification": spec,
        "before": describe(baseline), "after": describe(proposed),
        "before_new_candidates": len(baseline.repeated_label_decisions),
        "after_new_candidates": len([row for row in proposed.repeated_label_decisions
                                     if not row.get("settled_by_review")]),
        "before_missing_toc": baseline.missing,
        "after_missing_toc": proposed.missing,
        "enacted": proposed.structural_reviews_enacted,
    }
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
