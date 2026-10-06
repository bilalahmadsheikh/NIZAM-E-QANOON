"""Compare full-corpus stored-tree dry runs with and without a parser patch.

Inputs are JSONL files from measure_segmenter_against_stored.py. This reads
those files only; it does not connect to or write to the corpus database.
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path


def read(patterns: list[str]) -> dict[tuple[int, int], dict]:
    records = {}
    for pattern in patterns:
        for filename in sorted(glob.glob(pattern)):
            with open(filename, encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    key = (record["document"], record["observation"])
                    if key in records:
                        raise ValueError(f"Duplicate observation {key}: {filename}")
                    records[key] = record
    return records


def expression_map(record: dict) -> dict[int, dict]:
    return {item["expression"]: item for item in record.get("expressions", [])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", nargs="+", required=True)
    parser.add_argument("--patched", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="Compare only common observations while runs are still active")
    args = parser.parse_args()
    baseline, patched = read(args.baseline), read(args.patched)
    if set(baseline) != set(patched) and not args.allow_incomplete:
        raise ValueError(
            f"Observation mismatch: baseline-only={len(set(baseline)-set(patched))}, "
            f"patched-only={len(set(patched)-set(baseline))}"
        )
    lines = []
    errors = []
    counts = Counter()
    counts["baseline_observations_unmatched"] = len(set(baseline) - set(patched))
    counts["patched_observations_unmatched"] = len(set(patched) - set(baseline))
    for key in sorted(set(baseline) & set(patched)):
        before, after = baseline[key], patched[key]
        if before.get("error") or after.get("error"):
            errors.append({
                "document": key[0], "observation": key[1],
                "baseline_error": before.get("error"),
                "patched_error": after.get("error"),
            })
        bex, aex = expression_map(before), expression_map(after)
        if set(bex) != set(aex):
            raise ValueError(f"Expression mismatch for {key}")
        for expr in sorted(bex):
            b, a = bex[expr], aex[expr]
            if b["instrument"] != a["instrument"]:
                raise ValueError(f"Instrument mismatch for {key}/{expr}")
            if b["released"] != a["released"]:
                raise ValueError(f"Release-state mismatch for {key}/{expr}")
            old, new = b["compare"], a["compare"]
            categories = [name for name in ("tree", "s7", "toc")
                          if old[name] != new[name]]
            row = {
                "document": key[0], "observation": key[1],
                "expression": expr, "instrument": a["instrument"],
                "released": a["released"],
                "baseline_same_as_stored": old["same"],
                "patched_same_as_stored": new["same"],
                "patch_changed_comparison": bool(categories),
                "changed_categories": categories,
                "baseline": old, "patched": new,
            }
            if categories:
                lines.append(row)
            counts["expressions"] += 1
            counts["released_expressions"] += bool(a["released"])
            counts["baseline_different_from_stored"] += not old["same"]
            counts["patched_different_from_stored"] += not new["same"]
            counts["patch_changed_comparison"] += bool(categories)
            counts["patch_changed_released"] += bool(categories) and bool(a["released"])
            counts["patch_changed_tree"] += "tree" in categories
            counts["patch_changed_s7"] += "s7" in categories
            counts["patch_changed_toc"] += "toc" in categories
            counts["new_stored_differences"] += old["same"] and not new["same"]
            counts["new_stored_differences_released"] += (
                old["same"] and not new["same"] and bool(a["released"])
            )
            counts["repaired_stored_drift"] += not old["same"] and new["same"]
        if before.get("error") != after.get("error"):
            counts["changed_observation_errors"] += 1
    counts["observations"] = len(set(baseline) & set(patched))
    counts["baseline_errors"] = sum(bool(r.get("error")) for r in baseline.values())
    counts["patched_errors"] = sum(bool(r.get("error")) for r in patched.values())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as stream:
        for row in lines:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(dict(sorted(counts.items())), indent=2) + "\n",
                            encoding="utf-8")
    args.out.with_suffix(".errors.json").write_text(
        json.dumps(errors, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(sorted(counts.items())), indent=2))


if __name__ == "__main__":
    main()
