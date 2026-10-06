"""Read-only probe of a source-backed contents/body boundary override."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nizam.corpus.segment import segment
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import reviewed_structural_overrides


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("document_id", type=int)
    ap.add_argument("body_start_block", type=int)
    ap.add_argument("--blocks", required=True, help="comma-separated source block IDs to inspect")
    ap.add_argument("--patch-file", type=Path,
                    help="JSON list of proposed parser-input patches (read-only probe)")
    args = ap.parse_args()
    block_ids = {int(value) for value in args.blocks.split(",") if value.strip()}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("""SELECT source_observation_id FROM instrument
                       WHERE document_id=%s AND is_active AND duplicate_of IS NULL""",
                    (args.document_id,))
        observations = [row[0] for row in cur.fetchall()]
    if len(observations) != 1:
        raise SystemExit("requires one active canonical expression")
    observation = observations[0]
    blocks = legal_write.blocks_for(args.document_id)
    patches = legal_write.segmentation_patches_for(observation)
    proposed_patches = (json.loads(args.patch_file.read_text(encoding="utf-8"))
                        if args.patch_file else [])
    dispositions = legal_write.toc_dispositions_for(observation)
    resolutions = legal_write.structural_resolutions_for(args.document_id)
    overrides = reviewed_structural_overrides(resolutions, patches)
    if "source_body_start_block" in overrides:
        raise SystemExit("an existing source body-start override already applies")

    def build(extra, added_patches=None):
        parsed = segment(blocks, curation_patches=patches + (added_patches or []),
                         toc_dispositions=dispositions,
                         structural_resolutions=resolutions,
                         structural_overrides={**overrides, **extra})
        return {
            "body_starts_page": parsed.body_starts_page,
            "roles": {str(block_id): parsed.block_roles.get(block_id, (None, None))[0]
                      for block_id in sorted(block_ids)},
            "preamble": [node.text[:220] for node in parsed.flatten()
                         if node.kind == "preamble"],
            "sections": [(node.label, node.first_block) for node in parsed.flatten()
                         if node.kind == "section"],
            "selected_nodes": [
                {"kind": node.kind, "label": node.label,
                 "block": node.first_block, "text": (node.text or "")[:240]}
                for node in parsed.flatten() if node.first_block in block_ids],
            "pending_toc_labels": parsed.missing,
            "s7_candidates": len([row for row in parsed.repeated_label_decisions
                                  if not row.get("settled_by_review")]),
        }
    print(json.dumps({"document_id": args.document_id, "observation": observation,
                      "before": build({}),
                      "after": build({"source_body_start_block": args.body_start_block},
                                     proposed_patches)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
