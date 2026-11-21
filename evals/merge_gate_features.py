"""merge_gate_features.py MAIN.json EXTRA.json : copy EXTRA's modes into MAIN, case by case (D-111).

evals/gate_features.py merges the modes it computes into its --out file, so two runs writing one file at the same time
would each keep only its own modes. The GPU modes run into their own file beside the CPU run; this joins them. A case
or mode present in both must agree on everything but the mode; nothing in MAIN is dropped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    main_p, extra_p = Path(sys.argv[1]), Path(sys.argv[2])
    m, x = (json.loads(p.read_text(encoding="utf-8")) for p in (main_p, extra_p))
    if m.get("split") != x.get("split"):
        sys.exit(f"splits differ: {m.get('split')} vs {x.get('split')}")
    added = 0
    for cid, rec in x["cases"].items():
        if cid not in m["cases"]:
            sys.exit(f"{cid}: in {extra_p.name}, not in {main_p.name}")
        mine = m["cases"][cid]
        for k in ("family", "stratum", "expected", "veto"):
            if mine.get(k) != rec.get(k):
                sys.exit(f"{cid}: {k} differs ({mine.get(k)!r} vs {rec.get(k)!r})")
        for mode, row in rec.get("modes", {}).items():
            mine.setdefault("modes", {})[mode] = row
            added += 1
    pending = sum(1 for r in m["cases"].values() if (r.get("modes", {}).get("gpu") or {}).get("pending"))
    main_p.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{main_p.name}: {added} mode rows merged from {extra_p.name}; gpu pending {pending}")
    return 1 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
