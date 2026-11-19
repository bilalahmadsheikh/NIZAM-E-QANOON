"""embed_topup.py OUT_DIR : export the chunks that lack a GPU-generation vector (D-099), for a Kaggle top-up run.

A replay adds chunks (nizam.workers.chunk); the CPU generation embeds them on the spot, the GPU generation cannot
(its encoder is 8B), so audit A22 fails until they are embedded on a GPU. This writes, in embed_inputs.py's format:
  chunks.jsonl.gz   {"id", "u": 0, "j": jurisdiction, "t": context_prefix + "\\n" + span text} per missing chunk
  dev.json          the golden dev questions of the main export (the run re-encodes them; the loader requires they
                    reproduce the generation's own, cosine >= 0.999 -- proof the top-up is the same space)
  manifest.json
Then:  bash tools/kaggle/kg.sh dsup topup-<stamp> OUT_DIR   (a private dataset)
       KG_DS=nizam-topup-<stamp> KG_NSHARD=1 KG_REV=<commit> bash tools/kaggle/kg.sh e8push topup<stamp> 0
       bash tools/kaggle/kg.sh embedfetch topup<stamp>
       python tools/load_embeddings_gpu.py --topup OUT_DIR /mnt/e/nizam-data/embed/out-topup<stamp> --apply
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
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, revision FROM embedding_generation WHERE active AND encoder_device = 'gpu'")
        gen = cur.fetchone()
        if gen is None:
            sys.exit("no active GPU generation: nothing to top up")
        cur.execute("""SELECT c.id, c.jurisdiction, c.context_prefix,
                              substr(v.text_normalised, c.char_start + 1, c.char_end - c.char_start)
                         FROM chunk c JOIN provision_version v ON v.id = c.version_id
                        WHERE NOT EXISTS (SELECT 1 FROM chunk_embedding_gpu e WHERE e.chunk_id = c.id)
                        ORDER BY c.id""")
        rows = cur.fetchall()
    with gzip.open(out / "chunks.jsonl.gz", "wt", encoding="utf-8") as gz:
        for cid, juris, prefix, text in rows:
            gz.write(json.dumps({"id": cid, "u": 0, "j": juris, "t": passage_text(prefix, text)},
                                ensure_ascii=False) + "\n")
    shutil.copy(MAIN_DS / "dev.json", out / "dev.json")
    manifest = {"chunks": len(rows), "generation": gen[0], "revision": gen[1],
                "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in sorted(out.iterdir()) if f.name != "manifest.json" and f.suffix in (".gz", ".json")}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "sha256"}))
    if not rows:
        print("every chunk has its GPU vector: no top-up needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
