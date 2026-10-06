"""Inventory live S7 numbering/demotion cases from the last release checkpoint.

This is an offline evidence report, not a fresh DB query or an adjudicator.
The checkpoint's exact-blocker state prevents released/stale pack cases from
being counted as live. No response or production record is modified.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


NUMERIC_LABEL = re.compile(r"^\(?\d+[.)]?$")


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    checkpoint = json.loads((args.checkpoint / "summary.json").read_text(encoding="utf-8"))
    live = {
        item["case_id"]: item
        for item in read_jsonl(args.checkpoint / "cases.jsonl")
        if item["defect_type"] == "repeated_citation_label"
        and item["exact_blocker_still_pending"]
    }
    questions = {}
    for path in sorted((args.pack / "questions").glob("doc-*/s7-*.json")):
        question = json.loads(path.read_text(encoding="utf-8"))
        if question["case_id"] != path.stem:
            raise ValueError(f"case ID does not match filename: {path}")
        questions[question["case_id"]] = question

    rows = []
    for case_id, state in sorted(live.items(), key=lambda pair: (pair[1]["document_id"], pair[0])):
        question = questions.get(case_id)
        finding = question["how_found"] if question else {}
        review = finding.get("existing_review") or {}
        label = finding.get("printed_label", state.get("printed_label"))
        row = {
            "case_id": case_id,
            "instrument_id": state["instrument_id"],
            "document_id": state["document_id"],
            "source_observation_id": state["source_observation_id"],
            "source_sha256": state["source_sha256"],
            "printed_label": label,
            "numeric_label": bool(label and NUMERIC_LABEL.fullmatch(label.strip())),
            "parser_proposal": finding.get("parser_proposal"),
            "candidate_carries_law_parser_signal": (finding.get("parser_evidence") or {}).get("candidate_carries_law"),
            "candidate_source_block_id": (finding.get("candidate_source_block") or {}).get("id", state.get("source_block_id")),
            "candidate_page": finding.get("candidate_page", state.get("source_page")),
            "canonical_source_block_id": (finding.get("canonical_source_block") or {}).get("id"),
            "source_review_resolution": review.get("resolution"),
            "source_review_basis": review.get("review_basis"),
            "checkpoint_state": state["state"],
            "response_verdict": state.get("response_verdict"),
            "pack_snapshot_stale": state.get("pack_snapshot_stale"),
            "question_path": str(args.pack / "questions" / f"doc-{state['document_id']}" / f"{case_id}.json") if question else None,
            "needs_new_source_review": not bool(review.get("resolution")),
        }
        rows.append(row)

    if len(rows) != checkpoint["pending_s7_units"]:
        raise ValueError(f"live S7 count {len(rows)} differs from checkpoint {checkpoint['pending_s7_units']}")
    by_resolution = Counter(row["source_review_resolution"] or "unreviewed" for row in rows)
    documents = defaultdict(set)
    for row in rows:
        documents[row["source_review_resolution"] or "unreviewed"].add(row["document_id"])
    summary = {
        "checkpoint_measured_at": checkpoint["measured_at"],
        "not_a_fresh_database_query": True,
        "live_s7_cases_at_checkpoint": len(rows),
        "affected_documents": len({row["document_id"] for row in rows}),
        "numeric_label_cases": sum(row["numeric_label"] for row in rows),
        "parser_law_carrying_signal_true": sum(row["candidate_carries_law_parser_signal"] is True for row in rows),
        "source_review_resolution_cases": dict(sorted(by_resolution.items())),
        "source_review_resolution_document_ids": {
            key: sorted(value) for key, value in sorted(documents.items())
        },
        "interpretation": "Numbering and parser proposals are leads, not verified defects. Source-reviewed reparent/restore/split/reject decisions require correction or supersession before release.",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "s7-numbering-cases.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (args.out / "s7-numbering-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: summary[key] for key in (
        "checkpoint_measured_at", "live_s7_cases_at_checkpoint", "affected_documents",
        "numeric_label_cases", "parser_law_carrying_signal_true", "source_review_resolution_cases"
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
