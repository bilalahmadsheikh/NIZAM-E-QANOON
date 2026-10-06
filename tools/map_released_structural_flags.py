"""Map the prior SQL-only structural screen onto a current released snapshot.

This is an audit artifact builder, not an adjudicator. No database connection or
writer is used, and none of its clusters is labelled a confirmed defect.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


PRIORITY = {
    "top_level_nested_kind": 1,
    "numbered_proviso_without_own_node": 1,
    "footnote_phrase_in_operative_text": 1,
    "toc_source_promoted": 2,
    "root_source_order_inversion": 2,
    "repeated_sibling_label": 3,
}

# Only these exact screen leads coincide with a page-reviewed source finding.
# Other leads in the same instrument are deliberately not inherited as verified.
SOURCE_VERIFIED_LEADS = {
    (17, "footnote_phrase_in_operative_text", "277"),
    (120, "numbered_proviso_without_own_node", "3500"),
    (247, "numbered_proviso_without_own_node", "10540"),
    (671, "numbered_proviso_without_own_node", "28225"),
}


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def cluster_key(flag: dict) -> tuple:
    category = flag["category"]
    if category == "repeated_sibling_label":
        # A repeated-sibling collision is one question per parent and label,
        # even if the SQL screen emits a row for every participating node.
        return (flag["instrument_id"], category, str(flag.get("parent_id")),
                str(flag.get("label")))
    block = (flag.get("first_block") or flag.get("source_block_id")
             or flag.get("block_id") or flag.get("id"))
    return (flag["instrument_id"], category, str(block))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--screening", type=Path, required=True)
    ap.add_argument("--evidence-summary", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    released = {row["instrument_id"]: row for row in read_jsonl(args.evidence)}
    screen = json.loads(args.screening.read_text(encoding="utf-8"))
    evidence_summary = json.loads(args.evidence_summary.read_text(encoding="utf-8"))
    groups: dict[tuple, list[dict]] = defaultdict(list)
    all_count = Counter()
    released_count = Counter()
    for flag in screen["findings"]:
        category = flag["category"]
        all_count[category] += 1
        if flag.get("instrument_id") in released:
            released_count[category] += 1
            groups[cluster_key(flag)].append(flag)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cluster_count = Counter()
    review_state_count = Counter()
    affected = defaultdict(set)
    with args.output.open("w", encoding="utf-8") as handle:
        for key in sorted(groups, key=lambda k: (PRIORITY.get(k[1], 4), k)):
            flags = groups[key]
            first = flags[0]
            instrument = released[first["instrument_id"]]
            category = first["category"]
            cluster_count[category] += 1
            affected[category].add(first["instrument_id"])
            source_review = instrument.get("independent_source_review")
            verified = ((instrument["document_id"], category, key[-1])
                        in SOURCE_VERIFIED_LEADS and source_review is not None
                        and source_review["evidence_status"] == "CONFIRMED_DEFECT")
            state = "confirmed_defect" if verified else "not_yet_reviewed"
            review_state_count[state] += 1
            record = {
                "instrument_id": first["instrument_id"],
                "document_id": instrument["document_id"],
                "category": category,
                "priority_tier": PRIORITY.get(category, 4),
                "cluster_key": list(key),
                "raw_flag_count": len(flags),
                "source_block_ids": sorted({f.get("first_block") or f.get("source_block_id")
                    or f.get("block_id") for f in flags if f.get("first_block")
                    or f.get("source_block_id") or f.get("block_id")}),
                "source_pages": sorted({f["first_page"] for f in flags
                    if f.get("first_page") is not None}),
                "stored_node_ids": [f["id"] for f in flags if f.get("id")],
                "stored_paths": [f["path"] for f in flags if f.get("path")],
                "stored_parent_ids": sorted({f["parent_id"] for f in flags
                    if f.get("parent_id")}),
                "source_pdf_object_key": instrument["source_pdf"]["object_key"],
                "screen_generated_at": screen["generated_at"],
                "adjudication_status": state,
                "adjudication_note": (
                    "Exact lead is corroborated by the reviewed PDF page and block-role/provision comparison."
                    if verified else
                    "Heuristic cluster only. Instrument-level source review, if any, does not adjudicate this specific cluster."),
                "source_review_pages": source_review["pages_reviewed"] if verified else [],
                "source_review_block_ids": source_review["source_block_ids"] if verified else [],
                "instrument_evidence_status": instrument["evidence_status"],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        "current_released_snapshot_at": evidence_summary["snapshot_at"],
        "screen_generated_at": screen["generated_at"],
        "released_instruments": len(released),
        "all_corpus_raw_flag_count": sum(all_count.values()),
        "released_raw_flag_count": sum(released_count.values()),
        "released_deduplicated_cluster_count": len(groups),
        "released_flagged_instrument_count": len({k[0] for k in groups}),
        "all_corpus_raw_flags_by_category": dict(all_count),
        "released_raw_flags_by_category": dict(released_count),
        "released_clusters_by_category": dict(cluster_count),
        "released_affected_instruments_by_category": {
            category: len(ids) for category, ids in affected.items()},
        "released_clusters_by_adjudication_status": dict(review_state_count),
        "classification_note": "Only four exact leads are source-confirmed; all other clusters remain heuristic and not yet reviewed. No cluster was proven a false positive or resolved as ambiguous in this limited source sample. Priority tiers order review only.",
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"clusters": len(groups), "summary": str(summary_path)}))


if __name__ == "__main__":
    main()
