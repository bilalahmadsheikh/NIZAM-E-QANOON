"""served_paired.py RESULT_JSON [ARM_A ARM_B] : paired bootstrap CI of (B - A) between two arms of one served run
(evals/lexical_benchmark.py output: the same cases through two impls, e.g. hybrid vs ranked), with each arm's summary.
Default arms: hybrid and ranked -- what the cross-encoder adds on the served path (D-101)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals.paired_bootstrap import paired  # noqa: E402

KEYS = ("ndcg10", "mrr10", "recall10", "recall50")


def main() -> int:
    d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    a, b = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("hybrid", "ranked")
    out = {"run": sys.argv[1], "split": d.get("split"), "b_minus_a": f"{b} - {a}",
           "summary": {arm: {k: v for k, v in d["summary"][arm].items() if not isinstance(v, dict)} for arm in (a, b)},
           "paired": {k: paired(d["cases"][a], d["cases"][b], k) for k in KEYS}}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
