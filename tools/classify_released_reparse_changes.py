"""Summarize released tree deltas without treating them as PDF-verified errors."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def rows(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", required=True, type=Path)
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    evidence = {row["instrument_id"]: row for row in rows(args.evidence)}
    totals = Counter()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        for observation in rows(args.detail):
            for item in observation["instruments"]:
                if not item["previously_released"]:
                    continue
                iid = item["instrument_id"]
                if iid not in evidence:
                    continue
                tree = item["tree"]
                fields = Counter(field for node in tree["matched_changed"]
                                 for field in node["changed_fields"])
                facets = {
                    "node_membership_or_identity": bool(tree["added"] or tree["removed"]),
                    "parent_or_citation_path": bool(fields["parent_path"] or fields["path"]),
                    "operative_text": bool(fields["text"]),
                    "source_block_role_or_owner": bool(observation["block_role_changes"]
                                                       or observation["block_owner_path_changes"]),
                    "source_page_or_order": bool(fields["first_page"] or fields["last_page"]
                                                 or fields["ordinal"]),
                    "heading_or_label_or_kind": bool(fields["heading"] or fields["label"]
                                                     or fields["kind"]),
                    "structural_candidate_change": item["s7_before"] != item["s7_after"],
                    "contents_link_change": item["toc_before"] != item["toc_after"],
                }
                # A change is material for replay if it can affect what law is
                # represented or how it is cited. This is a risk label, not a
                # verdict that either the stored or newly parsed tree is right.
                material = any(facets[name] for name in (
                    "node_membership_or_identity", "parent_or_citation_path",
                    "operative_text", "source_block_role_or_owner",
                    "heading_or_label_or_kind", "structural_candidate_change",
                    "contents_link_change"))
                record = {
                    "instrument_id": iid,
                    "document_id": observation["document_id"],
                    "source_observation_id": observation["source_observation_id"],
                    "stored_node_count": tree["before_count"],
                    "dry_run_node_count": tree["after_count"],
                    "added_unmatched_rows": len(tree["added"]),
                    "removed_unmatched_rows": len(tree["removed"]),
                    "matched_changed_rows": len(tree["matched_changed"]),
                    "changed_field_counts": dict(fields),
                    "block_role_change_count": len(observation["block_role_changes"]),
                    "block_owner_change_count": len(observation["block_owner_path_changes"]),
                    "facets": facets,
                    "potentially_material_for_replay": material,
                    "known_source_review_status": evidence[iid]["evidence_status"],
                    "classification": "source_review_required_before_replay",
                    "caveat": "Unmatched added/removed rows are best-effort source-block matches, not verified legal additions or omissions.",
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                totals["changed_released_instruments"] += 1
                totals["potentially_material_for_replay"] += material
                totals["patch_attributable"] += bool(
                    evidence[iid]["read_only_reparse"]["patch_attributable_change"])
                for facet, present in facets.items():
                    totals["facet_" + facet] += present
    summary = dict(totals)
    summary["classification_note"] = (
        "Diff facets identify replay risk, not PDF-verified error. Detailed row-level "
        "before/after evidence remains in changed-detail.jsonl.")
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
