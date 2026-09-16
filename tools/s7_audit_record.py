"""Record verdicts for the rendered audit batch into verdicts.json.

Reads `batch-next.json` (written by `s7_audit_batch.py --next`) for the render
paths and their SHA-256, and a small JSON map from adjudication-id prefix to
`{"verdict": ..., "observed": ...}` written after reading the pages. Refuses a
verdict outside the vocabulary, an observation shorter than 40 characters, a
prefix that matches no row or several, or a render whose file no longer hashes
to the value recorded when it was rendered.

    uv run python tools/s7_audit_record.py --readings FILE.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

OUT = Path("/mnt/e/nizam-data/s7-audit")
VERDICTS = OUT / "verdicts.json"
BATCH = OUT / "batch-next.json"
ALLOWED = {"correct", "wrong", "not_s7"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readings", required=True)
    a = ap.parse_args()
    readings = json.loads(Path(a.readings).read_text(encoding="utf-8"))
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    done = json.loads(VERDICTS.read_text(encoding="utf-8")) if VERDICTS.exists() else {}

    recorded, refused = 0, []
    for prefix, r in readings.items():
        rows = [b for b in batch if b["adjudication_id"].startswith(prefix)]
        if len(rows) != 1:
            refused.append((prefix, f"{len(rows)} rows match"))
            continue
        row = rows[0]
        if r.get("verdict") not in ALLOWED:
            refused.append((prefix, f"verdict {r.get('verdict')!r} not in {sorted(ALLOWED)}"))
            continue
        if len((r.get("observed") or "").strip()) < 40:
            refused.append((prefix, "observation too short: say what the page shows"))
            continue
        bad = [x for x in row["renders"]
               if hashlib.sha256(Path(x["render"]).read_bytes()).hexdigest() != x["sha256"]]
        if bad:
            refused.append((prefix, "a render no longer matches its recorded hash"))
            continue
        done[row["adjudication_id"]] = {
            "document_id": row["document_id"],
            "printed_label": row["printed_label"],
            "verdict": r["verdict"],
            "observed": " ".join(r["observed"].split()),
            "renders": row["renders"],
            "heuristic": row["heuristic"],
            "band": row["band"],
            "instrument_active_now": row["instrument_active_at_freeze"],
        }
        recorded += 1

    VERDICTS.write_text(json.dumps(done, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"recorded {recorded}; total verdicts {len(done)}")
    for p, why in refused:
        print(f"  refused {p}: {why}")
    return 0 if not refused else 1


if __name__ == "__main__":
    raise SystemExit(main())
