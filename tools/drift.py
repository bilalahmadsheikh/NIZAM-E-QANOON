"""What changed in the corpus since you last looked, and who changed it.

Two coding agents work on this database. Yesterday one of them pruned three
gigabytes of retired revisions a few hours after the other had recorded a
decision NOT to prune. Nothing surfaced that. It was noticed by chance, from a
number that looked different from the one remembered.

That is the failure this closes. Not "is the corpus correct" -- `./nz audit`
answers that, and answered it PASS on both sides of the prune, because deleting
history violates no invariant. The unanswered question is narrower and more
human: *is the corpus the same one I was reasoning about ten minutes ago?*

So this records a fingerprint, diffs it against the previous one, and attributes
what it can from the append-only ledgers -- extraction attempts, segmentation
runs, adjudications all carry who and when. Attribution is best-effort and says
so: a ledger records the worker that wrote a row, which is not always the same as
the agent that decided to.

    ./nz drift                 what changed since last time, then re-baseline
    ./nz drift --no-update     compare without moving the baseline
    ./nz drift --since 2h      who touched the ledgers in the last two hours
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from nizam.storage.db import connect

STATE = Path(os.environ.get("NIZAM_DRIFT_DIR", "/mnt/e/nizam-data/drift"))

# One row per metric. Kept deliberately small: a fingerprint that changes on
# every ordinary write is noise, and noise is how a real change goes unread.
METRICS = {
    "documents_active":      "SELECT count(*) FROM document WHERE is_active",
    "instruments_live":      "SELECT count(*) FROM instrument WHERE is_active AND duplicate_of IS NULL",
    "instruments_duplicate": "SELECT count(*) FROM instrument WHERE duplicate_of IS NOT NULL",
    "provisions_live":       """SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id
                                 WHERE p.is_active AND i.is_active""",
    "provisions_retired":    """SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id
                                 WHERE NOT i.is_active""",
    "release_instruments":   "SELECT count(*) FROM v_release_instrument",
    "text_blocks_active":    """SELECT count(*) FROM text_block b JOIN document d ON d.id=b.document_id
                                 WHERE d.is_active""",
    "s7_pending":            "SELECT count(*) FROM v_structural_adjudication_pending",
    "s10_pending":           "SELECT count(*) FROM v_boundary_adjudication_pending",
    "toc_gaps":              "SELECT coalesce(sum(gaps),0) FROM v_toc_gap",
    "unlanded_sources":      "SELECT count(*) FROM source_observation WHERE sha256 IS NULL",
    "structural_decisions":  "SELECT count(*) FROM segmentation_structural_adjudication",
    "ocr_adjudications":     "SELECT count(*) FROM page_ocr_adjudication",
    "migrations_applied":    "SELECT count(*) FROM schema_migration",
    "db_size_bytes":         "SELECT pg_database_size(current_database())",
    "tables":                """SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                                WHERE n.nspname='public' AND c.relkind='r'""",
    "views":                 """SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                                WHERE n.nspname='public' AND c.relkind='v'""",
}

# Ledgers that record who did something and when. Each yields (actor, when).
ACTORS = [
    ("segmentation_structural_adjudication", "decided_by", "decided_at"),
    ("page_ocr_adjudication", "decided_by", "decided_at"),
    ("extraction_assertion", "asserted_by", "asserted_at"),
]


def human_bytes(n) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def fingerprint(cur) -> dict:
    out = {}
    for key, sql in METRICS.items():
        try:
            cur.execute(sql)
            out[key] = int(cur.fetchone()[0])
        except Exception:
            out[key] = None                 # a view that does not exist yet is not an error
    return out


def latest(dirpath: Path) -> tuple[Path | None, dict]:
    if not dirpath.exists():
        return None, {}
    files = sorted(dirpath.glob("drift-*.json"))
    if not files:
        return None, {}
    try:
        return files[-1], json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return files[-1], {}


def parse_since(text: str) -> str:
    """'2h' / '30m' / '3d' -> a Postgres interval string."""
    unit = {"m": "minutes", "h": "hours", "d": "days"}.get(text[-1:].lower())
    if not unit or not text[:-1].isdigit():
        return "24 hours"
    return f"{int(text[:-1])} {unit}"


def main() -> int:
    ap = argparse.ArgumentParser(description="What changed, and who changed it")
    ap.add_argument("--no-update", action="store_true", help="do not move the baseline")
    ap.add_argument("--since", default="24h", help="window for actor attribution (2h, 30m, 3d)")
    a = ap.parse_args()

    prev_path, prev = latest(STATE)
    window = parse_since(a.since)

    with connect() as conn, conn.cursor() as cur:
        now = fingerprint(cur)

        actors = []
        for table, who, when in ACTORS:
            try:
                cur.execute(
                    f"SELECT {who}, count(*), max({when}) FROM {table} "
                    f"WHERE {when} > now() - interval %s GROUP BY 1 ORDER BY 2 DESC",
                    (window,))
                for actor, n, last in cur.fetchall():
                    actors.append((table, actor, n, last))
            except Exception:
                conn.rollback()

    print(f"\ncorpus drift — {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M UTC}")
    if prev_path:
        print(f"baseline: {prev_path.name}\n")
    else:
        print("baseline: none — this run creates the first one\n")

    if prev:
        changed = [(k, prev.get(k), now.get(k)) for k in METRICS
                   if prev.get(k) is not None and now.get(k) is not None
                   and prev[k] != now[k]]
        if changed:
            width = max(len(k) for k, _, _ in changed)
            print(f"  {'metric'.ljust(width)}  {'before':>14}  {'after':>14}  change")
            print("  " + "-" * (width + 46))
            for k, before, after in changed:
                d = after - before
                if k == "db_size_bytes":
                    b, af, ds = human_bytes(before), human_bytes(after), human_bytes(d)
                else:
                    b, af, ds = f"{before:,}", f"{after:,}", f"{d:+,}"
                flag = "  <-- schema change" if k in ("tables", "views", "migrations_applied") else ""
                print(f"  {k.ljust(width)}  {b:>14}  {af:>14}  {ds:>12}{flag}")
            print()
        else:
            print("  nothing changed.\n")
    else:
        width = max(len(k) for k in METRICS)
        for k in METRICS:
            v = now.get(k)
            print(f"  {k.ljust(width)}  "
                  f"{human_bytes(v) if k == 'db_size_bytes' and v else (f'{v:,}' if v is not None else '-')}")
        print()

    if actors:
        print(f"  who wrote to the ledgers in the last {window}:")
        for table, actor, n, last in actors:
            print(f"    {actor:34} {n:>7,} row(s) in {table}  (last {last:%H:%M})")
        print("\n  Attribution is the WORKER that wrote the row, which is not always the\n"
              "  agent that decided to. Treat it as a lead, not a verdict.\n")
    else:
        print(f"  no ledger writes in the last {window}.\n")

    if not a.no_update:
        STATE.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (STATE / f"drift-{stamp}.json").write_text(
            json.dumps(now, indent=1), encoding="utf-8")
        print(f"  baseline updated: drift-{stamp}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
