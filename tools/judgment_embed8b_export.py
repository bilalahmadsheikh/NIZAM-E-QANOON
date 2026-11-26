"""judgment_embed8b_export.py OUT_DIR : export the judgment chunks lacking a GPU-generation vector (D-158), for the
Qwen3-Embedding-8B shard kernel (tools/kaggle/embed8b_kernel.py, D-099), unchanged.

The judgment chunks (0120) are embedded by the CPU generation as they are made (nizam.workers.judgment_chunk); the
GPU generation cannot be (its encoder is 8B), so audit A33 reports them until a Kaggle run embeds them. This writes,
in embed_inputs.py's format (tools/kaggle/shards.py load_ds reads it):
  chunks.jsonl.gz   {"id": judgment_chunk.id, "u": 0, "j": court code, "t": context_prefix + "\\n" + span text},
                    in id order -- the same passage text the CPU generation embedded (chunking.passage_text)
  dev.json          the statutes' golden dev questions of the GPU generation's main export: the run re-encodes them,
                    and the loader requires they reproduce the generation's own (cosine >= 0.999), proof the judgment
                    vectors are in the one GPU space laws and judgments share
  manifest.json
Then (D-158):
  bash tools/kaggle/kg.sh dsup j8-<stamp> OUT_DIR                                   (each account that runs shards)
  KG_DS=nizam-j8-<stamp> KG_NSHARD=24 KG_REV=<generation commit> bash tools/kaggle/kg.sh e8push j8a 0-11
  KG_ACCOUNT=2 KG_DS=nizam-j8-<stamp> KG_NSHARD=24 KG_REV=... bash tools/kaggle/kg.sh e8push j8b 12-23
  python tools/load_judgment_embeddings_gpu.py OUT_DIR RUN_DIR... --apply
Read-only against the database.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nizam.storage.chunking import passage_text  # noqa: E402
from nizam.storage.db import connect  # noqa: E402

MAIN_DS = Path("/mnt/e/nizam-data/embed/ds-v1")


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    with connect() as conn, conn.cursor(name="judgment_chunks") as cur:
        meta = conn.execute("SELECT id, revision FROM embedding_generation WHERE active AND encoder_device = 'gpu'")
        gen = meta.fetchone()
        if gen is None:
            sys.exit("no active GPU generation")
        cur.itersize = 20000
        cur.execute("""SELECT c.id, j.court_code, c.context_prefix,
                              substr(p.text, c.char_start + 1, c.char_end - c.char_start)
                         FROM judgment_chunk c
                         JOIN judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on
                         JOIN judgment_paragraph p ON p.id = c.paragraph_id AND p.decided_on = c.decided_on
                        WHERE NOT EXISTS (SELECT 1 FROM judgment_chunk_embedding_gpu e WHERE e.chunk_id = c.id)
                        ORDER BY c.id""")
        with gzip.open(out / "chunks.jsonl.gz", "wt", encoding="utf-8") as gz:
            for cid, court, prefix, text in cur:
                gz.write(json.dumps({"id": cid, "u": 0, "j": court, "t": passage_text(prefix, text)},
                                    ensure_ascii=False) + "\n")
                n += 1
    shutil.copy(MAIN_DS / "dev.json", out / "dev.json")
    manifest = {"chunks": n, "kind": "judgment_chunk", "generation": gen[0], "revision": gen[1],
                "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in sorted(out.iterdir()) if f.name != "manifest.json" and f.suffix in (".gz", ".json")}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "sha256"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
