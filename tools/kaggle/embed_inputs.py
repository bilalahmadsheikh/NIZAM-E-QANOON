"""embed_inputs.py OUT_DIR : the inputs of the embedding bake-off and corpus embedding run (D-098), for Kaggle.

Writes OUT_DIR/
  chunks.jsonl.gz   one line per chunk of a RELEASED version, in chunk-id order:
                    {"id": chunk id, "u": unit index, "j": jurisdiction, "t": context_prefix + "\\n" + span text}
                    The text is read through the chunk's offsets from provision_version.text_normalised (the chunk
                    table holds none, docs/03 §3). It is what gets embedded: context and words, never altered.
  units.json        unit index -> provision id of the legal unit (innermost section/article/order, else the
                    outermost schedule/form/appendix/annexure/preamble -- nizam.storage.unit_search's rule)
  dev.json          the golden DEV cases (evals/golden/split-v1.json) that have necessary units: question, scope
                    jurisdictions, gold unit indexes. TEST cases are not exported: they stay frozen (docs/10).
  manifest.json     counts, chunker, the corpus signature, sha256 of each file
Read-only against the database. Public law text only; the Kaggle dataset is private.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.chunking import passage_text  # noqa: E402
from nizam.storage.db import connect  # noqa: E402

UNIT_KINDS = {"section", "article", "order"}
OUTER_KINDS = {"schedule", "form", "appendix", "annexure", "preamble"}
ROOT = Path("/mnt/e/Nizam_e_Qanoon")


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET max_parallel_workers_per_gather = 2")
        cur.execute("SELECT id, parent_id, kind::text FROM provision WHERE is_active")
        tree = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        def unit_of(pid):
            inner = outer = None
            node = pid
            while node is not None and node in tree:
                parent, kind = tree[node]
                if inner is None and kind in UNIT_KINDS:
                    inner = node
                if kind in OUTER_KINDS:
                    outer = node
                node = parent
            return inner or outer or pid
        unit_index: dict = {}
        units: list[str] = []
        n = 0
        with gzip.open(out / "chunks.jsonl.gz", "wt", encoding="utf-8", compresslevel=6) as gz:
            cur.execute("""SELECT c.id, v.provision_id, subltree(p.path, 0, 1)::text, c.context_prefix,
                                  substr(v.text_normalised, c.char_start + 1, c.char_end - c.char_start)
                             FROM chunk c JOIN provision_version v ON v.id = c.version_id
                             JOIN provision p ON p.id = v.provision_id
                            ORDER BY c.id""")
            while True:
                rows = cur.fetchmany(50000)
                if not rows:
                    break
                for cid, pid, juris, prefix, text in rows:
                    u = unit_of(pid)
                    if u not in unit_index:
                        unit_index[u] = len(units)
                        units.append(str(u))
                    gz.write(json.dumps({"id": cid, "u": unit_index[u], "j": juris, "t": passage_text(prefix, text)},
                                        ensure_ascii=False) + "\n")
                    n += 1
        (out / "units.json").write_text(json.dumps(units), encoding="utf-8")
        split = json.loads((ROOT / "evals/golden/split-v1.json").read_text(encoding="utf-8"))
        dev = set(split["dev"])
        cases = []
        import glob
        for f in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
            for line in open(f, encoding="utf-8"):
                d = json.loads(line)
                gold = d["retrievalGold"].get("necessaryUnits") or []
                if d["caseId"] not in dev or d["expectedOutcome"] not in ("answer", "conditional") or not gold:
                    continue
                j = d["scope"]["jurisdiction"]
                # gold is matched by PATH: a replay gives a provision a new id but keeps its path (D-090); 9 of the
                # dev gold units had been re-identified on 18 Nov (their recorded ids retired or pruned)
                gu = set()
                for g in gold:
                    cur.execute("SELECT id FROM provision WHERE path = %s::ltree AND is_active LIMIT 1", (g["path"],))
                    row = cur.fetchone()
                    if row and unit_of(row[0]) in unit_index:
                        gu.add(unit_index[unit_of(row[0])])
                gu = sorted(gu)
                cases.append({"case": d["caseId"], "stratum": d["stratum"], "script": d["question"]["script"],
                              "q": d["question"]["text"],
                              "juris": ["fed"] if j in ("fed", "foreign") else [j, "fed"], "gold": gu,
                              "gold_total": len(gold)})
        (out / "dev.json").write_text(json.dumps(cases, ensure_ascii=False, indent=0), encoding="utf-8")
        cur.execute("SELECT DISTINCT chunker FROM chunk")
        chunker = [r[0] for r in cur.fetchall()]
        sig = (ROOT / "infra/scripts/corpus-signature.sql").read_text(encoding="utf-8")
        cur.execute(sig)
        signature = cur.fetchone()[0]
    manifest = {"chunks": n, "units": len(units), "dev_cases": len(cases), "chunker": chunker,
                "corpus_signature": signature, "built_s": round(time.time() - t0),
                "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in sorted(out.iterdir()) if f.suffix in (".gz", ".json") and f.name != "manifest.json"}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "sha256"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
