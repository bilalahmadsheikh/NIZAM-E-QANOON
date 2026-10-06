"""Enrich read-only stored-vs-parser comparisons with stable-block and role diffs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import glob
import json
from pathlib import Path
import sys

from nizam.storage import legal_write
from nizam.storage.db import connect
import nizam.workers.segment as worker
from tools.measure_segmenter_against_stored import (
    MULTI_DOCS, TARGETS_SQL, built, stored,
)
from tools.materialize_multi_instrument import prepare as prepare_multi


FIELDS = ("path", "parent_path", "kind", "label", "ordinal", "first_page",
          "last_page", "first_block", "text", "heading")


def _record(row: tuple) -> dict:
    return dict(zip(FIELDS, row))


def _match_rows(before: list[tuple], after: list[tuple]) -> tuple[list, list, list]:
    """Match by source block first; paths are never used as identity."""
    old = set(range(len(before)))
    new = set(range(len(after)))
    matched = []
    for key in (
        lambda row: (row[7], row[2], row[3]),
        lambda row: (row[7], row[3]),
        lambda row: (row[7],),
    ):
        old_groups = defaultdict(list)
        new_groups = defaultdict(list)
        for index in old:
            old_groups[key(before[index])].append(index)
        for index in new:
            new_groups[key(after[index])].append(index)
        for identity in old_groups.keys() & new_groups.keys():
            if len(old_groups[identity]) == len(new_groups[identity]) == 1:
                i, j = old_groups[identity][0], new_groups[identity][0]
                matched.append((i, j))
                old.remove(i)
                new.remove(j)
    return matched, sorted(old), sorted(new)


def _tree_diff(before: list[tuple], after: list[tuple]) -> dict:
    paired, removed, added = _match_rows(before, after)
    changed = []
    for i, j in paired:
        a, b = before[i], after[j]
        if a == b:
            continue
        fields = [name for name, left, right in zip(FIELDS, a, b)
                  if left != right]
        changed.append({
            "source_block_id": a[7] if a[7] is not None else b[7],
            "changed_fields": fields,
            "before": _record(a), "after": _record(b),
        })
    return {
        "before_count": len(before), "after_count": len(after),
        "matched_changed": changed,
        "removed": [_record(before[i]) for i in removed],
        "added": [_record(after[j]) for j in added],
        "ambiguous_match_blocks": sorted({
            row[7] for row in ([before[i] for i in removed]
                           + [after[j] for j in added]) if row[7] is not None
        } & {row[7] for row in before} & {row[7] for row in after}),
    }


def _stored_roles(cur, observation: int) -> dict[int, tuple[str, str | None]]:
    cur.execute("""SELECT pb.block_id,pb.role::text,p.path::text
      FROM block_assignment_set s
      JOIN provision_block pb ON pb.assignment_set_id=s.id
      LEFT JOIN provision p ON p.id=pb.provision_id
      WHERE s.source_observation_id=%s AND s.is_active""", (observation,))
    return {int(block): (role, path) for block, role, path in cur.fetchall()}


def _built_roles(insts: dict) -> dict[int, tuple[str, str | None]]:
    result = {}
    for inst in insts.values():
        paths = {row["key"]: row["path"] for row in inst.provisions}
        for block, role, key, _chars in inst.block_roles:
            value = (role, paths.get(key))
            if block in result and result[block] != value:
                raise ValueError(f"multiple proposed roles for block {block}")
            result[block] = value
    return result


def _build_group(doc: int, obs: int, meta: tuple) -> dict:
    if doc in MULTI_DOCS:
        insts, _segments = prepare_multi(doc, obs)[:2]
        return {inst.expression_ordinal: inst for inst in insts}
    sha, source_id, title, year, url = meta
    patches = legal_write.segmentation_patches_for(obs)
    resolutions = legal_write.structural_resolutions_for(doc)
    inst, _seg = worker.build(
        doc, sha, obs, source_id, title, year, url,
        legal_write.blocks_for(doc), legal_write.observed_on(obs), patches,
        toc_dispositions=legal_write.toc_dispositions_for(obs),
        structural_resolutions=resolutions,
        structural_overrides=worker.reviewed_structural_overrides(
            resolutions, patches) or None,
    )
    return {0: inst}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--comparisons", required=True, nargs="+",
                        help="JSONL files or glob patterns from measure_segmenter_against_stored")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--documents", help="comma-separated document IDs for triage")
    args = parser.parse_args()
    records = []
    for pattern in args.comparisons:
        for name in sorted(glob.glob(pattern)):
            with open(name, encoding="utf-8") as source:
                records.extend(json.loads(line) for line in source if line.strip())
    records.sort(key=lambda row: (row["document"], row["observation"]))
    if args.documents:
        wanted = {int(value) for value in args.documents.replace(",", " ").split()}
        records = [row for row in records if row["document"] in wanted]
    changed = [row for row in records if any(
        not e["compare"]["same"] for e in row.get("expressions", []))]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute(TARGETS_SQL)
        metadata = {(doc, obs): (sha, source_id, title, year, url)
                    for doc, obs, _expr, _iid, _released, sha, source_id,
                    title, year, url in cur.fetchall()}
        cur.execute("""SELECT d.id,d.sha256,b.object_key FROM document d
                       LEFT JOIN blob b ON b.sha256=d.sha256""")
        sources = {doc: (sha, key) for doc, sha, key in cur.fetchall()}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        totals = Counter()
        with args.out.open("w", encoding="utf-8") as sink:
            for index, row in enumerate(changed, 1):
                doc, obs = row["document"], row["observation"]
                result = {
                    "document_id": doc, "source_observation_id": obs,
                    "segmenter_sha": row["segmenter"],
                    "source_sha256": sources.get(doc, (None, None))[0],
                    "source_pdf_object_key": sources.get(doc, (None, None))[1],
                    "instruments": [], "block_role_changes": [],
                    "block_owner_path_changes": [],
                }
                try:
                    insts = _build_group(doc, obs, metadata[(doc, obs)])
                    old_roles = _stored_roles(cur, obs)
                    new_roles = _built_roles(insts)
                    for block in sorted(old_roles.keys() | new_roles.keys()):
                        was = old_roles.get(block)
                        now = new_roles.get(block)
                        if was == now:
                            continue
                        item = {"source_block_id": block,
                                "before": {"role": was[0], "owner_path": was[1]} if was else None,
                                "after": {"role": now[0], "owner_path": now[1]} if now else None}
                        if was is None or now is None or was[0] != now[0]:
                            result["block_role_changes"].append(item)
                        else:
                            result["block_owner_path_changes"].append(item)
                    for expression in row["expressions"]:
                        if expression["compare"]["same"]:
                            continue
                        expr = expression["expression"]
                        old = stored(cur, expression["instrument"])
                        new = built(insts[expr])
                        tree = _tree_diff(old["rows"], new["rows"])
                        result["instruments"].append({
                            "expression_ordinal": expr,
                            "instrument_id": expression["instrument"],
                            "previously_released": expression["released"],
                            "tree": tree,
                            "s7_before": old["s7"], "s7_after": new["s7"],
                            "toc_before": old["toc"], "toc_after": new["toc"],
                        })
                        totals["changed_instruments"] += 1
                        if expression["released"]:
                            totals["changed_released"] += 1
                        totals["added_nodes"] += len(tree["added"])
                        totals["removed_nodes"] += len(tree["removed"])
                        totals["changed_matched_nodes"] += len(tree["matched_changed"])
                    totals["block_role_changes"] += len(result["block_role_changes"])
                except Exception as exc:  # record every failed comparison
                    result["error"] = f"{type(exc).__name__}: {exc}"[:500]
                    totals["errors"] += 1
                    conn.rollback()
                    cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                sink.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
                if index % 25 == 0:
                    sink.flush()
                    print(f"enriched {index}/{len(changed)} changed observations",
                          file=sys.stderr, flush=True)
    summary = {"screened_observations": len(records),
               "changed_observations": len(changed), **totals}
    args.out.with_suffix(".summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if totals["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
