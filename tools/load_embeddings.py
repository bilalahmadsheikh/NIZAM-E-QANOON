"""load_embeddings.py RUN_DIR SLUG ENCODER_DIR [--apply] : write a bake-off run's binary vectors into chunk.embedding
under a new, active embedding_generation (D-098; docs/03 §3).

  RUN_DIR      the fetched Kaggle output: out/ids.npy (chunk ids, in export order) and out/<SLUG>/{bits.npy, metrics.json}
  ENCODER_DIR  the validated int8 query encoder (encoder.json: model, revision, pooling, query_template, max_tokens)

Refuses, before writing anything, unless:
  * ids.npy is EXACTLY today's chunk ids (same set, same count) and the chunker is unchanged -- a replay between the
    export and the load would otherwise pair vectors with other text;
  * bits.npy has one 128-byte row per id (1024 sign bits);
  * encoder.json names the model, commit, pooling and query template the run embedded with (metrics.json).
Then, in ONE transaction: the previous generation is deactivated and its vectors cleared, the new generation is
recorded active with the bake-off evidence, and every chunk gets its vector (streamed in batches through a temporary
table: ~3 GB free RAM on this host). Dry run by default.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np  # noqa: E402

from nizam.storage.db import connect  # noqa: E402

BATCH = 50_000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path); ap.add_argument("slug"); ap.add_argument("encoder_dir", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--evidence", type=Path, action="append", default=[],
                    help="a JSON file (e.g. evals/paired_bootstrap.py output) kept in the generation's selection record")
    a = ap.parse_args()
    out = a.run_dir / "out"
    ids = np.load(out / "ids.npy")
    bits = np.load(out / a.slug / "bits.npy", mmap_mode="r")
    metrics = json.loads((out / a.slug / "metrics.json").read_text(encoding="utf-8"))
    enc = json.loads((a.encoder_dir / "encoder.json").read_text(encoding="utf-8"))
    if bits.shape != (len(ids), 128):
        sys.exit(f"bits.npy is {bits.shape}, expected ({len(ids)}, 128)")
    for key in ("model", "revision", "pooling", "query_template"):
        if enc[key] != metrics.get(key):
            sys.exit(f"encoder {key} {enc[key]!r} is not the run's ({metrics.get(key)!r}): the query encoder must be "
                     "the model, commit, pooling and query form the corpus was embedded with")
    evidence = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in a.evidence}   # read now: a dry run checks it
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT array_agg(id ORDER BY id), count(*), array_agg(DISTINCT chunker) FROM chunk")
        db_ids, n, chunkers = cur.fetchone()
        if n != len(ids) or not np.array_equal(np.asarray(db_ids, dtype=np.int64), np.sort(ids)):
            sys.exit(f"chunk ids differ from the run's ({n} in the database, {len(ids)} embedded): re-export and "
                     "re-embed, or embed the difference -- vectors are never paired with other text")
        if len(chunkers) != 1:
            sys.exit(f"more than one chunker in the table: {chunkers}")
        print(f"checks passed: {n} chunks, chunker {chunkers[0]}, model {enc['model']}@{enc['revision'][:12]}")
        if not a.apply:
            print("dry run (nothing written); pass --apply")
            return 0
        cur.execute("UPDATE embedding_generation SET active = false WHERE active")
        cur.execute("UPDATE chunk SET embedding = NULL WHERE embedding IS NOT NULL")
        selection = {"bake_off": "tools/kaggle/embed_kernel.py, golden DEV split only (evals/golden/split-v1.json)",
                     "full_precision": metrics["full_precision"]["all"], "binary": metrics["binary"]["all"],
                     "chunks_per_second_gpu": metrics.get("chunks_per_second"), "dtype": metrics.get("dtype"),
                     "evidence": evidence}
        cur.execute("""INSERT INTO embedding_generation (model, revision, dims, quantization, pooling, query_template,
                                                         passage_source, max_tokens, chunker, chunk_count, selection,
                                                         active)
                       VALUES (%s, %s, 1024, 'binary_sign', %s, %s, 'context_prefix + newline + span text', %s, %s,
                               %s, %s::jsonb, true) RETURNING id""",
                    (enc["model"], enc["revision"], enc["pooling"], enc["query_template"], enc["max_tokens"],
                     chunkers[0], n, json.dumps(selection)))
        gen = cur.fetchone()[0]
        cur.execute("CREATE TEMP TABLE _emb (id bigint PRIMARY KEY, e bit(1024)) ON COMMIT DROP")
        for i in range(0, len(ids), BATCH):
            block = np.unpackbits(np.asarray(bits[i:i + BATCH]), axis=1)          # (b, 1024) of 0/1
            text = (block + ord("0")).astype(np.uint8)
            with cur.copy("COPY _emb (id, e) FROM STDIN") as cp:
                for cid, row in zip(ids[i:i + BATCH], text):
                    cp.write_row((int(cid), row.tobytes().decode("ascii")))
        cur.execute("UPDATE chunk c SET embedding = t.e FROM _emb t WHERE t.id = c.id")
        updated = cur.rowcount
        if updated != n:
            raise SystemExit(f"updated {updated} of {n} chunks; rolled back")
        conn.commit()
    print(f"generation {gen}: {updated} chunk vectors written in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
