"""load_judgment_embeddings_gpu.py DS_DIR RUN_DIR... [--apply] : load the GPU generation's Qwen3-Embedding-8B sign bits
for judgment chunks (D-158) into judgment_chunk_embedding_gpu (0141).

DS_DIR is the export the runs embedded (tools/judgment_embed8b_export.py); RUN_DIR the fetched kernel outputs
(tools/kaggle/embed8b_kernel.py, every shard once, over one or both accounts). A shard is packed sign bits
(KG_BITS=1: uint8 [rows, 512], numpy.packbits order) or float16 [rows, 4096]; either gives the same bit(4096).

Refuses, before writing anything, unless:
  * the shards verify (tools/kaggle/shards.py: each holds exactly its slice of the export's ids, nothing non-finite,
    one model revision; the dev questions and the 256 probe chunks agree across runs and accounts);
  * the runs are the active GPU generation's model, commit and query template, and their dev questions reproduce the
    generation's own (reference_q.npy of the GPU encoder bundle, cosine >= 0.999): the judgment vectors are in the one
    GPU space the statutes' chunk_embedding_gpu holds, so one question vector searches both;
  * every exported chunk that still exists and lacks a vector is the SAME text the run embedded: its passage text
    (context prefix + span, chunking.passage_text) is read again and compared, character for character, with the
    export's. One difference refuses the load; vectors are never paired with other text.
A run takes hours, and judgments are re-read and landed meanwhile: an exported chunk a re-read removed is skipped
(counted), and a chunk made since is not in the export -- it is a later top-up (A33 reports it). Then ONE
transaction: the rows are copied, and the HNSW index (ix_judgment_chunk_embedding_gpu_hnsw) is built if it does not
exist (after the first, whole load) or kept and grown (a top-up). Dry run by default.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np  # noqa: E402

from nizam.storage.chunking import passage_text  # noqa: E402
from nizam.storage.db import connect  # noqa: E402
from tools.kaggle.shards import load_ds, verified_runs  # noqa: E402
from tools.load_embeddings_gpu import encoder_dir  # noqa: E402

TABLE = "judgment_chunk_embedding_gpu"
INDEX = "ix_judgment_chunk_embedding_gpu_hnsw"
WIDTH = 4096


def export_texts(ds: Path) -> dict[int, str]:
    """chunk id -> the passage text the run embedded, from the export itself"""
    import gzip
    import json
    out = {}
    with gzip.open(Path(ds) / "chunks.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[int(r["id"])] = r["t"]
    return out


def shard_bits(path: Path) -> np.ndarray:
    """uint8 [rows, WIDTH] of 0/1, from a packed-bits shard or a float16 shard"""
    X = np.load(path)
    if X.dtype == np.uint8 and X.shape[1] == WIDTH // 8:
        return np.unpackbits(X, axis=1)[:, :WIDTH]
    return (X[:, :WIDTH] > 0).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ds", type=Path)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    ids, _units, _jidx, _jnames = load_ds(a.ds)
    R = verified_runs(ids, a.runs)
    if R.missing:
        sys.exit(f"shards missing: {R.missing}")
    m = R.meta
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id, model, revision, query_template FROM embedding_generation
                        WHERE active AND encoder_device = 'gpu'""")
        active = cur.fetchone()
        if active is None or (active[1], active[2], active[3]) != (m["model"], m["revision"], m["query_template"]):
            sys.exit(f"the runs must be the active GPU generation's model, commit and template; active: {active}")
        ref = np.load(encoder_dir() / "reference_q.npy").astype(np.float32)
        ref /= np.linalg.norm(ref, axis=1, keepdims=True)
        agree = float((ref * R.dev_q[: len(ref)]).sum(1).min())
        if agree < 0.999:
            sys.exit(f"the runs' dev questions do not reproduce the generation's (cosine {agree:.5f})")
        exported = export_texts(a.ds)
        cur.execute(f"""SELECT c.id, c.context_prefix, substr(p.text, c.char_start + 1, c.char_end - c.char_start)
                          FROM judgment_chunk c
                          JOIN judgment_paragraph p ON p.id = c.paragraph_id AND p.decided_on = c.decided_on
                         WHERE c.id = ANY(%s)
                           AND NOT EXISTS (SELECT 1 FROM {TABLE} e WHERE e.chunk_id = c.id)""",
                    ([int(i) for i in ids],))
        keep = set()
        for cid, prefix, text in cur.fetchall():
            if passage_text(prefix, text) != exported[cid]:
                sys.exit(f"judgment chunk {cid}: its text is not the text the run embedded -- vectors are never "
                         "paired with other text")
            keep.add(cid)
        cur.execute(f"SELECT count(*) FROM {TABLE} WHERE chunk_id = ANY(%s)", ([int(i) for i in ids],))
        already = cur.fetchone()[0]
        gone = len(ids) - len(keep) - already
        print(f"checks passed: {len(keep)} of {len(ids)} exported judgment chunks to load ({gone} removed by a re-read "
              f"since the export, {already} already held), {m['model']}@{m['revision'][:12]}, generation {active[0]}, "
              f"dev questions cosine {agree:.5f}, runs {R.agreement}")
        if not a.apply:
            print("dry run (nothing written); pass --apply")
            return 0
        gen, n = active[0], 0
        for s in sorted(R.shards):
            lo, hi = R.bounds[s], R.bounds[s + 1]
            B = shard_bits(R.shards[s]) + ord("0")
            w = 0
            with cur.copy(f"COPY {TABLE} (chunk_id, generation_id, bits) FROM STDIN") as cp:
                for i in range(hi - lo):
                    if int(ids[lo + i]) in keep:
                        cp.write_row((int(ids[lo + i]), gen, B[i].tobytes().decode("ascii")))
                        w += 1
            n += w
            print(f"  shard {s}: {w} of {hi - lo} rows", flush=True)
        if n != len(keep):
            raise SystemExit(f"wrote {n} of {len(keep)}; rolled back")
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (INDEX,))
        if not cur.fetchone()[0]:
            t = time.time()
            cur.execute("SET LOCAL maintenance_work_mem = '1GB'")
            cur.execute("SET LOCAL max_parallel_maintenance_workers = 2")
            cur.execute(f"CREATE INDEX {INDEX} ON {TABLE} USING hnsw (bits bit_hamming_ops) "
                        "WITH (m = 16, ef_construction = 64)")
            cur.execute(f"COMMENT ON INDEX {INDEX} IS 'Dense judgment candidates of the GPU generation (D-158): HNSW "
                        "over sign-binarised 4096-d vectors, Hamming distance. Built by the loader after the first load.'")
            print(f"  {INDEX} built in {time.time() - t:.0f}s", flush=True)
        conn.commit()
    print(f"generation {gen}: {n} judgment vectors written in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
