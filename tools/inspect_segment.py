"""Dry-run one observation through the segmenter and report path bounds.

This diagnostic never writes to PostgreSQL.  It is intentionally small so a
failed database insert can be distinguished from a parsing/path construction
defect using the exact extracted blocks that triggered it.
"""
from __future__ import annotations

import argparse
import json

from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.corpus.segment import _section_numbers, _twocol_run, parse_contents
from nizam.workers.segment import build


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("observation_id", type=int)
    parser.add_argument("--toc-only", action="store_true")
    parser.add_argument(
        "--toc-summary",
        action="store_true",
        help="print pending TOC reconciliation as compact tab-separated rows",
    )
    parser.add_argument(
        "--toc-debug",
        action="store_true",
        help="print the raw numbered stream and chosen TOC boundary",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="print only machine-readable reconciliation deltas",
    )
    parser.add_argument(
        "--tree",
        action="store_true",
        help="print the prospective provision tree with source anchors",
    )
    parser.add_argument(
        "--marginal-fusion", action="store_true",
        help="enable the gated geometric margin/body split",
    )
    args = parser.parse_args()

    pending_toc: list[tuple[int | None, str]] = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.sha256, o.id, o.source_id,
                   o.source_metadata->>'title',
                   coalesce(o.source_metadata->>'year',
                            o.source_metadata->>'year_or_dept'),
                   o.canonical_url
              FROM source_observation o
              JOIN document d ON d.sha256=o.sha256 AND d.is_active
             WHERE o.id=%s
            """,
            (args.observation_id,),
        )
        target = cur.fetchone()
        cur.execute(
            """
            SELECT g.ordinal,g.printed_label
              FROM v_toc_gap_pending g
              JOIN instrument i ON i.id=g.instrument_id
             WHERE i.is_active AND i.duplicate_of IS NULL
               AND i.source_observation_id=%s
             ORDER BY g.ordinal NULLS LAST,g.printed_label
            """,
            (args.observation_id,),
        )
        pending_toc = cur.fetchall()
    if target is None:
        raise SystemExit(f"observation {args.observation_id} has no active extraction")

    document_id, sha256, observation_id, source_id, title, year, url = target
    blocks = legal_write.blocks_for(document_id)
    if args.toc_debug:
        raw_numbers = _section_numbers(blocks)
        print("raw_twocol_run=" + json.dumps(
            _twocol_run(blocks, {label for _, _, label, _ in raw_numbers}),
            ensure_ascii=False,
        ))
        print("raw_section_numbers=" + json.dumps(
            raw_numbers, ensure_ascii=False,
        ))
        toc_debug, boundary_debug, found_debug = parse_contents(blocks)
        print("raw_toc=" + json.dumps(toc_debug, ensure_ascii=False))
        print(f"raw_toc_boundary={boundary_debug}")
        print(f"raw_toc_found={found_debug}")
    instrument, segmentation = build(
        document_id, sha256, observation_id, source_id, title, year, url,
        blocks, legal_write.observed_on(observation_id),
        legal_write.segmentation_patches_for(observation_id),
        split_fused_margins=args.marginal_fusion,
    )
    longest = max(instrument.provisions, key=lambda row: len(row["path"].encode()))
    print(f"provisions={len(instrument.provisions)}")
    print(f"max_path_bytes={len(longest['path'].encode())}")
    print(f"max_path_levels={longest['path'].count('.') + 1}")
    print(f"max_path={longest['path']}")
    print(f"body_starts_page={segmentation.body_starts_page}")
    print(f"toc_found={segmentation.toc_found}")
    print(f"toc_entries={len(segmentation.toc_entries)}")
    print(f"toc_matched={segmentation.matched}")
    print(f"toc_missing={json.dumps(segmentation.missing, ensure_ascii=False)}")
    print(f"toc_extra={json.dumps(segmentation.extra, ensure_ascii=False)}")
    if args.tree:
        print("prospective_tree=" + json.dumps([
            {
                "kind": node.kind,
                "label": node.label,
                "heading": node.heading,
                "text": node.text[:180],
                "page": node.first_page,
                "block": node.first_block,
                "parent_kind": node.parent.kind if node.parent else None,
                "parent_label": node.parent.label if node.parent else None,
            }
            for node in segmentation.flatten()
        ], ensure_ascii=False, indent=2))
    if args.compact:
        entries_by_key = {
            (entry["ordinal"], entry["label"]): entry
            for entry in segmentation.toc_entries
        }
        recovered = []
        remaining = []
        for ordinal, label in pending_toc:
            entry = entries_by_key.get((ordinal, label))
            node = entry.get("node") if entry else None
            target = recovered if node is not None else remaining
            target.append({
                "ordinal": ordinal,
                "label": label,
                "page": node.first_page if node else None,
                "block": node.first_block if node else None,
                "kind": node.kind if node else None,
            })
        print("pending_recovered=" + json.dumps(recovered, ensure_ascii=False))
        print("pending_remaining=" + json.dumps(remaining, ensure_ascii=False))
        print(
            "structural_candidate_count="
            f"{len(segmentation.repeated_label_decisions)}"
        )
        return 0
    prospective_schedules = [
        {
            "label": node.label,
            "heading": node.heading,
            "first_page": node.first_page,
            "last_page": node.last_page,
            "first_block": node.first_block,
        }
        for node in segmentation.flatten()
        if node.kind == "schedule"
    ]
    print("prospective_schedules=" + json.dumps(
        prospective_schedules, ensure_ascii=False,
    ))
    prospective_divisions = [
        {
            "kind": node.kind,
            "label": node.label,
            "heading": node.heading,
            "first_page": node.first_page,
            "first_block": node.first_block,
            "parent_kind": node.parent.kind if node.parent else None,
            "parent_label": node.parent.label if node.parent else None,
        }
        for node in segmentation.flatten()
        if node.kind in {"part", "chapter", "schedule", "annexure"}
    ]
    print("prospective_divisions=" + json.dumps(
        prospective_divisions, ensure_ascii=False,
    ))
    recovered_pending = []
    entries_by_key = {
        (entry["ordinal"], entry["label"]): entry
        for entry in segmentation.toc_entries
    }
    for ordinal, label in pending_toc:
        entry = entries_by_key.get((ordinal, label))
        node = entry.get("node") if entry else None
        recovered_pending.append({
            "ordinal": ordinal,
            "printed_label": label,
            "recovered": node is not None,
            "provision_page": node.first_page if node else None,
            "provision_block": node.first_block if node else None,
            "provision_kind": node.kind if node else None,
            "entry_kind": entry.get("kind") if entry else None,
            "provision_heading": node.heading if node else None,
            "provision_text": node.text[:300] if node else None,
        })
    if args.toc_summary:
        print("prospective_toc_matches:")
        print(
            "ordinal\tlabel\tmatched\ttoc_page\ttoc_block\t"
            "body_page\tbody_block\tkind\theading"
        )
        for entry in segmentation.toc_entries:
            node = entry.get("node")
            heading = (
                (node.heading if node else entry.get("heading")) or ""
            ).replace("\t", " ")
            print(
                f'{entry["ordinal"]}\t{entry["label"]}\t'
                f'{str(node is not None).lower()}\t'
                f'{entry.get("source_page") or ""}\t'
                f'{entry.get("source_block_id") or ""}\t'
                f'{node.first_page if node else ""}\t'
                f'{node.first_block if node else ""}\t'
                f'{node.kind if node else entry.get("kind", "")}\t{heading}'
            )
        print("pending_toc_reconciliation:")
        print("ordinal\tlabel\trecovered\tpage\tblock\tkind\theading")
        for item in recovered_pending:
            heading = (item["provision_heading"] or "").replace("\t", " ")
            print(
                f'{item["ordinal"]}\t{item["printed_label"]}\t'
                f'{str(item["recovered"]).lower()}\t'
                f'{item["provision_page"] or ""}\t'
                f'{item["provision_block"] or ""}\t'
                f'{item["provision_kind"] or ""}\t{heading}'
            )
        print("prospective_unmatched_toc:")
        print("ordinal\tlabel\tpage\theading")
        for entry in segmentation.toc_entries:
            if entry.get("node") is not None:
                continue
            heading = (entry.get("heading") or "").replace("\t", " ")
            print(
                f'{entry["ordinal"]}\t{entry["label"]}\t'
                f'{entry.get("source_page") or ""}\t{heading}'
            )
        print("prospective_compound_candidates:")
        print("citation\tpage\tblock\tkind\theading\ttext")
        for node in segmentation.flatten():
            if (node.kind != "subsection" or node.parent is None
                    or node.parent.kind not in {"section", "article", "clause"}):
                continue
            citation = f"{node.parent.label}({node.label})"
            if not any(entry["label"] == citation
                       for entry in segmentation.toc_entries):
                continue
            heading = (node.heading or "").replace("\t", " ")
            value = node.text[:160].replace("\t", " ").replace("\n", " ")
            print(
                f"{citation}\t{node.first_page}\t{node.first_block}\t"
                f"{node.kind}\t{heading}\t{value}"
            )
    else:
        print("pending_toc_reconciliation=" + json.dumps(
            recovered_pending, ensure_ascii=False, indent=2,
        ))
    decisions = []
    for decision in segmentation.repeated_label_decisions:
        candidate = decision["candidate"]
        canonical = decision["canonical"]
        decisions.append({
            "printed_label": decision["printed_label"],
            "group_size": decision["group_size"],
            "candidate_block": candidate.first_block,
            "candidate_page": candidate.first_page,
            "candidate_heading": candidate.heading,
            "candidate_text": candidate.text[:300],
            "candidate_parent": (
                f"{candidate.parent.kind}:{candidate.parent.label}"
                if candidate.parent else None
            ),
            "canonical_block": canonical.first_block,
            "canonical_page": canonical.first_page,
            "canonical_heading": canonical.heading,
            "toc_heading": decision["toc_heading"],
        })
    if not args.toc_only:
        print("structural_candidates=" + json.dumps(
            decisions, ensure_ascii=False, indent=2,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
