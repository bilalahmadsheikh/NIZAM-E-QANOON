"""List cases that still prevent a corpus-wide structural parser replay.

Consumes read-only dry-run artifacts, never connects to the database.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


TARGET_SOURCE_VERIFIED = {118, 956}
SPOT_CHECKED_PROVISOS = {120, 247, 671}


def read_lines(patterns: list[str]):
    for pattern in patterns:
        for filename in sorted(glob.glob(pattern)):
            with open(filename, encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", nargs="+", required=True)
    parser.add_argument("--control-comparison", type=Path, required=True)
    parser.add_argument("--errors", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    control = list(read_lines([str(args.control_comparison)]))
    baseline = list(read_lines(args.baseline))
    patch_cases = [{
        "document_id": item["document"],
        "source_observation_id": item["observation"],
        "expression_ordinal": item["expression"],
        "instrument_id": item["instrument"],
        "previously_released": item["released"],
        "changed_categories": item["changed_categories"],
        "source_review": (
            "proviso_page_spot_checked_other_tree_effects_unreviewed"
            if item["document"] in SPOT_CHECKED_PROVISOS
            else "not_source_verified"
        ),
        "reason": "Patch changes a stored tree; source and citation review incomplete",
    } for item in control if item["document"] not in TARGET_SOURCE_VERIFIED]

    prior_drift = [{
        "document_id": row["document"],
        "source_observation_id": row["observation"],
        "expression_ordinal": expression["expression"],
        "instrument_id": expression["instrument"],
        "previously_released": expression["released"],
        "reason": "Pre-fix parser already differs from the stored tree",
    } for row in baseline for expression in row.get("expressions", [])
        if not expression["compare"]["same"]]

    errors = json.loads(args.errors.read_text(encoding="utf-8"))
    result = {
        "status": "not_ready_for_corpus_wide_production_replay",
        "patch_changed_instruments_needing_source_review": patch_cases,
        "preexisting_stored_tree_drift": prior_drift,
        "unbuilt_observations": errors,
        "additional_source_verified_unresolved": [{
            "document_id": 671,
            "source_page": 14,
            "source_block_ids": [28224, 28225, 28226, 28227],
            "issue": "New bracketed proviso under section 10 is correct, but romanettes (i) and (ii) remain direct section-10 children rather than proviso children",
            "status": "source_verified_parentage_unfixed",
        }],
        "counts": {
            "patch_changed_needing_source_review": len(patch_cases),
            "patch_changed_previously_released_needing_source_review": sum(
                item["previously_released"] for item in patch_cases),
            "preexisting_stored_tree_drift": len(prior_drift),
            "unbuilt_observations": len(errors),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
