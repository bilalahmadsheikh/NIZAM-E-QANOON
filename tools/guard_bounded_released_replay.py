"""Verify a bounded released-document replay against a frozen DB snapshot.

Only explicitly allowed document IDs may retire/replace a previously released
instrument. Every other previously released instrument must retain its UUID
and full stored-tree fingerprint. The allowed replacements must remain released
with the same source observation, expression ordinal and source hash.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nizam.storage.db import connect
from tools.second_parser_release import RELEASE_FINGERPRINT_SQL, RELEASE_IDENTITY_SQL


def rows(cur, sql: str, params=()):
    cur.execute(sql, params)
    columns = [column.name for column in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def key(row):
    return (row["document_id"], row["source_observation_id"],
            row["expression_ordinal"], str(row["source_sha256"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--allow-documents", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    allowed = {int(item) for item in args.allow_documents.split(",") if item.strip()}
    if not allowed:
        raise SystemExit("an explicit nonempty document allowlist is required")
    baseline = json.loads((args.baseline / "released.json").read_text(encoding="utf-8"))
    baseline_ids = list(baseline)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        before = rows(cur, """SELECT id::text AS instrument_id,document_id,
            source_observation_id,expression_ordinal,source_sha256
            FROM instrument WHERE id=ANY(%s::uuid[])""", (baseline_ids,))
        measured = rows(cur, "SELECT now() AS measured_at,current_database() AS database")[0]
        current = rows(cur, RELEASE_IDENTITY_SQL)
        cur.execute(RELEASE_FINGERPRINT_SQL)
        fingerprints = dict(cur.fetchall())

    before_by_id = {row["instrument_id"]: row for row in before}
    current_by_id = {row["instrument_id"]: row for row in current}
    current_by_key = {}
    for row in current:
        current_by_key.setdefault(key(row), []).append(row)
    if set(before_by_id) != set(baseline):
        raise SystemExit("baseline instrument identities could not be read")

    unwanted_removed = []
    unwanted_changed = []
    allowed_replacements = []
    errors = []
    for instrument_id, old_fingerprint in baseline.items():
        old = before_by_id[instrument_id]
        if old["document_id"] in allowed:
            matches = current_by_key.get(key(old), [])
            if len(matches) != 1:
                errors.append({"document_id": old["document_id"],
                               "reason": "allowed source identity has no unique released replacement"})
            else:
                new = matches[0]
                allowed_replacements.append({
                    "document_id": old["document_id"],
                    "old_instrument_id": instrument_id,
                    "new_instrument_id": new["instrument_id"],
                    "source_observation_id": old["source_observation_id"],
                    "source_sha256": str(old["source_sha256"]),
                })
            continue
        if instrument_id not in current_by_id:
            unwanted_removed.append(instrument_id)
        elif fingerprints.get(instrument_id) != old_fingerprint:
            unwanted_changed.append(instrument_id)

    report = {
        **measured,
        "allowed_documents": sorted(allowed),
        "baseline_released": len(baseline),
        "current_released": len(current),
        "unwanted_removed": unwanted_removed,
        "unwanted_changed": unwanted_changed,
        "allowed_replacements": allowed_replacements,
        "other_new_releases": len(set(current_by_id) - set(baseline)
                                  - {item["new_instrument_id"] for item in allowed_replacements}),
        "errors": errors,
        "safe": not (unwanted_removed or unwanted_changed or errors)
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, default=str, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({field: report[field] for field in (
        "measured_at", "baseline_released", "current_released",
        "unwanted_removed", "unwanted_changed", "allowed_replacements",
        "other_new_releases", "errors", "safe")}, default=str))
    return 0 if report["safe"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
