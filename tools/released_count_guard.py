"""Stop a post-replay sequence when a document gained a released expression nobody declared.

    python tools/released_count_guard.py [--baseline DIR]

WHY (doc 4419, 12 Oct 2026). A replay rebuilt a byte-identical duplicate observation without the readings its
canonical carried; it stopped being an exact duplicate, passed every release predicate, and a second, uncorrected
copy of the Constitution entered the release. Nothing was withdrawn, so every withdrawal check stayed green.
This check compares each document's released-expression count with a signed baseline (claude-baseline-N:
released.json + manifest.json) and exits 1 on any rise that was not declared. A rise is declared by

  * a reviewed multi-expression split plan, tools/evidence/multi-instrument-plans/doc-N.json (not a -DRAFT), whose
    expressions account for the new count; or
  * an approval reason, recorded on a segmentation run of the document since the baseline
    (detail.release_change_approval), that says so in words: it contains "new released expression".

Read-only. Exit 0: no undeclared rise. Exit 1: undeclared rises are listed. Exit 2: no baseline found.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANS = ROOT / "tools" / "evidence" / "multi-instrument-plans"
BASELINES = ROOT / ".artifacts" / "release-work-2026-09-24"
DECLARES_RISE = re.compile(r"new released expression", re.I)


def undeclared_rises(before: dict[int, int], now: dict[int, int], plan_expressions: dict[int, int],
                     approvals: dict[int, list[str]]) -> list[tuple[int, int, int]]:
    """(document, released before, released now) for every rise neither a split plan nor an approval declares."""
    out = []
    for doc, count in sorted(now.items()):
        was = before.get(doc, 0)
        if count <= was:
            continue
        if plan_expressions.get(doc, 0) >= count:
            continue
        if any(DECLARES_RISE.search(reason or "") for reason in approvals.get(doc, [])):
            continue
        out.append((doc, was, count))
    return out


def plan_expression_counts(plans_dir: pathlib.Path = PLANS) -> dict[int, int]:
    counts = {}
    for path in plans_dir.glob("doc-*.json"):
        if not re.fullmatch(r"doc-\d+\.json", path.name):
            continue                                   # a -DRAFT plan declares nothing
        plan = json.loads(path.read_text(encoding="utf-8-sig"))
        counts[int(plan["document_id"])] = len(plan.get("expressions") or [])
    return counts


def newest_baseline(root: pathlib.Path = BASELINES) -> pathlib.Path | None:
    dirs = [p for p in root.glob("claude-baseline-*") if re.fullmatch(r"claude-baseline-\d+", p.name)
            and (p / "released.json").exists() and (p / "manifest.json").exists()]
    return max(dirs, key=lambda p: int(p.name.rsplit("-", 1)[1]), default=None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=pathlib.Path, help="a signed baseline directory (default: the newest)")
    a = ap.parse_args()
    base = a.baseline or newest_baseline()
    if base is None:
        print("released-count guard: no signed baseline found", file=sys.stderr)
        return 2
    released_ids = list(json.loads((base / "released.json").read_text(encoding="utf-8")))
    measured_at = json.loads((base / "manifest.json").read_text(encoding="utf-8"))["measured_at"]
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT document_id, count(*) FROM instrument WHERE id::text = ANY(%s) GROUP BY 1""",
                    (released_ids,))
        before = {int(d): int(n) for d, n in cur.fetchall()}
        cur.execute("""SELECT i.document_id, count(*) FROM v_release_instrument r
                         JOIN instrument i ON i.id=r.id GROUP BY 1""")
        now = {int(d): int(n) for d, n in cur.fetchall()}
        rising = [d for d, n in now.items() if n > before.get(d, 0)]
        approvals: dict[int, list[str]] = {}
        if rising:
            cur.execute("""SELECT document_id, detail->>'release_change_approval' FROM segmentation_run
                            WHERE document_id = ANY(%s) AND run_at > %s::timestamptz
                              AND detail ? 'release_change_approval'""", (rising, measured_at))
            for d, reason in cur.fetchall():
                approvals.setdefault(int(d), []).append(reason)
    bad = undeclared_rises(before, now, plan_expression_counts(), approvals)
    print(f"released-count guard against {base.name}: {sum(before.values())} -> {sum(now.values())} released; "
          f"{len(rising)} document(s) rose; undeclared {len(bad)}")
    for doc, was, count in bad:
        print(f"  UNDECLARED: document {doc} released expressions {was} -> {count} "
              "(no split plan covers it; no approval reason says 'new released expression')")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
