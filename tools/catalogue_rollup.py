"""Roll the catalogue reader results up into a fix worklist.

Readers write one JSON file per document under
``.artifacts/catalogue/results/<shard>/doc<id>.json``.  This reads all of them,
checks each row against the shard that commissioned it, and prints what the fix
phase has to do, grouped by the kind of fix.

    python tools/catalogue_rollup.py                 # summary
    python tools/catalogue_rollup.py --fix curation_patch   # one worklist
    python tools/catalogue_rollup.py --json .artifacts/catalogue/worklist.json

A row is only counted when its ``defect_key`` is one the shard actually listed,
so a stale result file from an earlier inventory cannot leak into the worklist.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARDS = ROOT / ".artifacts/catalogue/shards"
RESULTS = ROOT / ".artifacts/catalogue/results"

REQUIRED = ("defect_key", "document_id", "stage", "class", "fix", "observed")
# Every fix a reader is allowed to name. Anything else is a defect in the row.
FIXES = {
    "accept_non_citable", "restore_citable", "reparent", "split_instrument",
    "reject_candidate", "curation_patch", "disposition_omitted", "disposition_repealed",
    "found_elsewhere", "absent_in_source", "parser_rule", "reacquire_source",
    "needs_second_read",
}


def shard_index() -> dict[str, dict[int, set[str]]]:
    """shard name -> document id -> the defect keys that shard commissioned."""
    index: dict[str, dict[int, set[str]]] = {}
    for path in sorted(SHARDS.glob("defects-*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        # One document can hold several instruments (document 3949 holds five),
        # so the keys have to be merged rather than overwritten.
        per_doc: dict[int, set[str]] = {}
        for inst in shard["instruments"]:
            keys = per_doc.setdefault(inst["document_id"], set())
            for d in inst["defects"]:
                keys.add(str(d.get("toc_entry_id") or d.get("candidate_id") or "quality"))
        index[path.stem] = per_doc
    return index


def load(index: dict[str, dict[int, set[str]]]) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    problems: list[str] = []
    for shard_dir in sorted(RESULTS.glob("defects-*")):
        shard = shard_dir.name
        commissioned = index.get(shard)
        if commissioned is None:
            problems.append(f"{shard}: results exist for a shard that is not in {SHARDS}")
            continue
        for path in sorted(shard_dir.glob("doc*.json")):
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                problems.append(f"{shard}/{path.name}: not valid JSON ({exc})")
                continue
            if not isinstance(content, list):
                problems.append(f"{shard}/{path.name}: expected a list of defect rows")
                continue
            doc = int(path.stem[3:])
            wanted = commissioned.get(doc)
            if wanted is None:
                problems.append(f"{shard}/{path.name}: document {doc} is not in that shard")
                continue
            seen = set()
            for row in content:
                missing = [f for f in REQUIRED if not row.get(f)]
                if missing:
                    problems.append(f"{shard}/{path.name}: a row is missing {', '.join(missing)}")
                    continue
                key = str(row["defect_key"])
                if key not in wanted:
                    problems.append(f"{shard}/{path.name}: defect {key} is not in the shard")
                    continue
                if row["fix"] not in FIXES:
                    problems.append(f"{shard}/{path.name}: unknown fix {row['fix']!r} on defect {key}")
                    continue
                if len(row["observed"]) < 60:
                    problems.append(f"{shard}/{path.name}: defect {key} quotes only {len(row['observed'])} characters")
                seen.add(key)
                row["shard"] = shard
                rows.append(row)
            for key in sorted(wanted - seen):
                problems.append(f"{shard}/{path.name}: defect {key} of document {doc} has no row")
    return rows, problems


def coverage(index: dict[str, dict[int, set[str]]]) -> tuple[int, int, int, int]:
    docs = sum(len(d) for d in index.values())
    defects = sum(len(keys) for d in index.values() for keys in d.values())
    done_docs = done_defects = 0
    for shard, per_doc in index.items():
        shard_dir = RESULTS / shard
        if not shard_dir.exists():
            continue
        for doc, keys in per_doc.items():
            path = shard_dir / f"doc{doc}.json"
            if not path.exists():
                continue
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            got = {str(r.get("defect_key")) for r in rows if isinstance(r, dict)}
            done_defects += len(keys & got)
            if keys <= got:
                done_docs += 1
    return docs, done_docs, defects, done_defects


# A replay re-creates a document's contents entries and S7 candidates, and the
# decisions recorded against the retired revision do not carry over (seen on the
# Penal Code). So a document whose fix changes the tree must be rebuilt BEFORE
# any of its decisions are recorded.
#
# Only some decisions release by themselves. Migration 0036: "Only accepting the
# parser's non-citable classification resolves the current candidate as written.
# Restore/reparent/split/reject are instructions to build a corrected revision,
# so they remain blocking until that replay supersedes the candidate." Nothing
# in the pipeline applies those instructions yet, so they belong with the rows
# that need a different tree, not with the rows that a decision closes.
RELEASE_BY_DECISION = {"accept_non_citable", "found_elsewhere", "absent_in_source",
                       "disposition_omitted", "disposition_repealed"}
REBUILD_FIRST = {"curation_patch", "parser_rule", "restore_citable", "reparent",
                 "reject_candidate", "split_instrument"}
BLOCKED = {"reacquire_source", "needs_second_read"}


def print_plan(index: dict[str, dict[int, set[str]]], rows: list[dict]) -> None:
    by_doc: dict[int, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_doc[int(r["document_id"])].append(r)
    wanted = {doc: keys for per_doc in index.values() for doc, keys in per_doc.items()}
    decide, rebuild, blocked, partial = [], [], [], []
    for doc, doc_rows in sorted(by_doc.items()):
        if {str(r["defect_key"]) for r in doc_rows} < wanted.get(doc, set()):
            partial.append(doc)
            continue
        fixes = {r["fix"] for r in doc_rows}
        if fixes & BLOCKED:
            blocked.append((doc, sorted(fixes & BLOCKED)))
        elif fixes & REBUILD_FIRST:
            rebuild.append((doc, len(doc_rows)))
        else:
            decide.append((doc, len(doc_rows)))
    print(f"\nplan over {len(by_doc)} documents with rows:")
    print(f"  decide now     {len(decide):4} documents, {sum(n for _, n in decide)} decisions that release by themselves")
    print(f"  rebuild first  {len(rebuild):4} documents, {sum(n for _, n in rebuild)} rows (the tree must change, then replay, then decide)")
    corrective = collections.Counter(r["fix"] for r in rows
                                     if r["fix"] in REBUILD_FIRST - {"curation_patch", "parser_rule"})
    if corrective:
        print("    of which corrective S7 instructions nothing applies yet: "
              + ", ".join(f"{k} {v}" for k, v in corrective.most_common()))
    print(f"  blocked        {len(blocked):4} documents (reacquire or second read)")
    if partial:
        print(f"  partly read    {len(partial):4} documents")
    rules = collections.Counter()
    for r in rows:
        if r["fix"] == "parser_rule":
            rules[(r.get("fix_detail") or {}).get("parser_rule", "(unstated)")[:90]] += 1
    if rules:
        print("\nmost requested parser rules:")
        for text, n in rules.most_common(12):
            print(f"  {n:3}  {text}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", help="print the worklist for one fix value")
    ap.add_argument("--stage", help="restrict to one stage")
    ap.add_argument("--json", help="write every row to this file")
    ap.add_argument("--problems", action="store_true", help="print every validation problem")
    ap.add_argument("--plan", action="store_true",
                    help="split fully-read documents into decide-now and rebuild-first")
    args = ap.parse_args()

    index = shard_index()
    rows, problems = load(index)
    docs, done_docs, defects, done_defects = coverage(index)

    print(f"catalogue: {done_docs}/{docs} documents read, {done_defects}/{defects} defects diagnosed")
    if rows:
        by_fix = collections.Counter(r["fix"] for r in rows)
        by_stage = collections.Counter(r["stage"] for r in rows)
        by_conf = collections.Counter(r.get("confidence", "?") for r in rows)
        releases = sum(1 for r in rows if r.get("releases_if_fixed"))
        print(f"\nby stage:      " + ", ".join(f"{k} {v}" for k, v in by_stage.most_common()))
        print(f"by fix:        " + ", ".join(f"{k} {v}" for k, v in by_fix.most_common()))
        print(f"by confidence: " + ", ".join(f"{k} {v}" for k, v in by_conf.most_common()))
        print(f"rows whose fix is said to release the instrument: {releases}")
    if problems:
        print(f"\n{len(problems)} validation problems"
              + ("" if args.problems else " (use --problems to list them)"))
        if args.problems:
            for p in problems:
                print("  " + p)

    if args.fix or args.stage:
        picked = [r for r in rows
                  if (not args.fix or r["fix"] == args.fix)
                  and (not args.stage or r["stage"] == args.stage)]
        print(f"\n{len(picked)} rows")
        for r in sorted(picked, key=lambda r: (r["document_id"], str(r["defect_key"]))):
            print(f"\ndoc {r['document_id']} {r['kind']} {r.get('label')!r} [{r['shard']}] "
                  f"{r['stage']}/{r['class']} conf={r.get('confidence')}")
            print(f"  {r['observed'][:300]}")
            if r.get("fix_detail"):
                print(f"  detail: {json.dumps(r['fix_detail'], ensure_ascii=False)[:400]}")
            if r.get("notes"):
                print(f"  notes: {r['notes'][:300]}")

    if args.plan:
        print_plan(index, rows)

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {len(rows)} rows to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
