"""adr1d_export.py OUT_DIR : the inputs of ADR-1d's after-reranking check for the CPU generation (D-110).

ADR-1d (D-005) allows binary vectors only if they cost at most 2 NDCG points AFTER reranking. The CPU generation
(bge-m3) stores sign bits only. Its whole corpus embeds in about 1.5 h on a Kaggle T4 (D-098: 209 chunks/s), so the
float arm is exact: tools/kaggle/embed_kernel.py with KG_KEEPFLOAT=1 and KG_REV = the generation's commit re-embeds
every chunk in float and returns, per dev question, the served window (900 chunks) nearest by float cosine and by
Hamming on the same vectors' sign bits. evals/adr1d_eval.py does the rest on this machine.

Writes, in embed_inputs.py's format:
  chunks.jsonl.gz  {"id", "u": 0, "j", "t": context_prefix + "\\n" + span} -- every chunk, the text the generation embeds
  dev.json         the answerable dev questions with their scope; NO gold (gold never leaves the laptop)
  manifest.json    counts, the generation and commit, sha256 of each file
"""
from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.storage.chunking import passage_text  # noqa: E402
from nizam.storage.db import connect  # noqa: E402


def dev_cases():
    keep = set(json.loads((ROOT / "evals/golden/split-v1.json").read_text(encoding="utf-8"))["dev"])
    for f in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            if (d["caseId"] in keep and d["expectedOutcome"] in ("answer", "conditional")
                    and d["retrievalGold"].get("necessaryUnits")):
                yield d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cases = []
    for d in dev_cases():
        j = d["scope"]["jurisdiction"]
        cases.append({"case": d["caseId"], "stratum": d["stratum"], "script": d["question"]["script"],
                      "q": d["question"]["text"], "juris": ["fed"] if j in ("fed", "foreign") else [j, "fed"],
                      "gold": [], "gold_total": 1})
    n = 0
    with connect() as conn, conn.cursor(name="adr1d") as cur, \
            gzip.open(a.out / "chunks.jsonl.gz", "wt", encoding="utf-8") as gz:
        cur.itersize = 20000
        cur.execute("""SELECT c.id, c.jurisdiction, c.context_prefix,
                              substr(v.text_normalised, c.char_start + 1, c.char_end - c.char_start)
                         FROM chunk c JOIN provision_version v ON v.id = c.version_id ORDER BY c.id""")
        for cid, juris, prefix, text in cur:
            gz.write(json.dumps({"id": cid, "u": 0, "j": juris, "t": passage_text(prefix, text)},
                                ensure_ascii=False) + "\n")
            n += 1
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, model, revision FROM embedding_generation WHERE active AND encoder_device = 'cpu'")
        gen = cur.fetchone()
    (a.out / "dev.json").write_text(json.dumps(cases, ensure_ascii=False, indent=0), encoding="utf-8")
    manifest = {"what": "ADR-1d after reranking: the whole corpus for a float run (D-110)", "chunks": n,
                "cases": len(cases), "generation": gen[0], "model": gen[1], "revision": gen[2],
                "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in sorted(a.out.iterdir()) if f.suffix in (".gz", ".json") and f.name != "manifest.json"}}
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "sha256"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
