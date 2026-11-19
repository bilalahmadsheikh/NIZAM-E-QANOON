"""The golden dev/test split (D-098; docs/10: "Frozen test split, never used for tuning. Separate dev split").

    python evals/golden/split.py          # writes evals/golden/split-v1.json (idempotent: same input, same split)

Deterministic and stratified: within each stratum, cases are ordered by sha256(caseId) and the first 60% are DEV,
the rest TEST. No case content, score or result enters the choice, so the split cannot favour any method. Dev is for
choosing and tuning (models, thresholds, constants); TEST is read only to report a decision already made on dev.
New cases (sets 5-10) are assigned by the same rule when they are added; an existing case never moves.
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEV_SHARE = 0.6


def main() -> int:
    by_stratum = collections.defaultdict(list)
    for f in sorted(glob.glob(str(HERE / "golden-pk-v1-set*.draft.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            by_stratum[d["stratum"]].append(d["caseId"])
    out_path = HERE / "split-v1.json"
    prior = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"dev": [], "test": []}
    fixed = {c: "dev" for c in prior["dev"]} | {c: "test" for c in prior["test"]}
    split = {"dev": [], "test": []}
    for stratum, ids in sorted(by_stratum.items()):
        ids = sorted(ids, key=lambda c: hashlib.sha256(c.encode()).hexdigest())
        n_dev = round(len(ids) * DEV_SHARE)
        for i, c in enumerate(ids):
            split[fixed.get(c, "dev" if i < n_dev else "test")].append(c)
    split = {k: sorted(v) for k, v in split.items()}
    out_path.write_text(json.dumps({"rule": "per stratum, sha256(caseId) order, first 60% dev (D-098)",
                                    **split}, indent=1), encoding="utf-8")
    print(f"dev {len(split['dev'])}  test {len(split['test'])}  "
          + "  ".join(f"{s}:{len(v)}" for s, v in sorted(by_stratum.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
