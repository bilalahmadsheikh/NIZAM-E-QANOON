"""Extract confirmed source-backed findings that require a human release decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EFFECTS = {
    3: "Editorial signature/order and heading are in Section 2 operative text; Section 1 block ownership is also wrong.",
    17: "Enactment-history footnote contaminates Section 3 operative text.",
    19: "Enacted title/preamble are treated as contents and the Section 1 opening as preface; source roles and preamble are wrong.",
    120: "Printed Section 3(1) proviso lacks a separate citable node in the released tree.",
    157: "Enacted preamble is treated as contents and a page separator contaminates the Section 2 proviso.",
    220: "Section 1(2) has no separate citation; its text is fused into 1(1), and a footnote becomes a false clause under 2(2).",
    247: "Printed Section 3(3) proviso lacks a separate citable node in the released tree.",
    671: "Printed Section 10 proviso is absent in the released tree; its numbered items have the wrong parent and citation paths.",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    decisions = []
    with args.evidence.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["evidence_status"] != "CONFIRMED_DEFECT":
                continue
            review = row["independent_source_review"]
            doc = row["document_id"]
            if doc not in EFFECTS or not review:
                raise ValueError(f"Missing source-backed decision explanation for {doc}")
            decisions.append({
                "instrument_id": row["instrument_id"],
                "document_id": doc,
                "title": row["title"],
                "jurisdiction": row["jurisdiction"],
                "current_production_release_status": row["production_release_status"],
                "audit_evidence_status": row["evidence_status"],
                "source_pdf_object_key": row["source_pdf"]["object_key"],
                "source_pdf_sha256": row["source_pdf"]["document_sha256"],
                "source_block_ids": review["source_block_ids"],
                "pages_reviewed": review["pages_reviewed"],
                "full_instrument_source_image_review_completed": review["full_pdf_pages_reviewed"],
                "confirmed_finding": review["finding"],
                "operative_or_citation_effect": EFFECTS[doc],
                "release_status_decision": "required_under_existing_policy_not_automated",
                "recommended_next_step": "Review the confirmed source defect and the rest of this instrument against its PDF, then decide whether to correct, annotate, restrict, or retain the release under existing policy.",
            })
    decisions.sort(key=lambda r: r["document_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"count": len(decisions), "cases": decisions},
                                      indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"decisions": len(decisions), "output": str(args.output)}))


if __name__ == "__main__":
    main()
