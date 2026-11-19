"""load_embeddings_gpu.py : load the GPU generation's vectors (Qwen3-Embedding-8B shard runs, D-099) into
chunk_embedding_gpu (0113), beside the CPU generation in chunk.embedding, which is untouched.

  python tools/load_embeddings_gpu.py DS_DIR RUN_DIR... --evidence JSON... [--apply]
      a whole generation: DS_DIR is the export the runs embedded (tools/kaggle/embed_inputs.py), RUN_DIR the fetched
      kernel outputs (every shard, once). The stored forms are the table's own column types: bits bit(W) is the sign
      of the first W dimensions, half halfvec(D) the first D dimensions (0113).
  python tools/load_embeddings_gpu.py --topup DS_DIR RUN_DIR [--apply]
      a replay's new chunks: DS_DIR from tools/embed_topup.py, RUN_DIR the kernel run over it. Same model, commit and
      template as the active GPU generation, and its dev questions must reproduce the generation's (cosine >= 0.999).

Refuses, before writing anything, unless the shards verify (tools/kaggle/shards.py) and the export's chunk ids are
EXACTLY the chunks the database holds (a whole load) or exactly the chunks lacking a GPU vector (a top-up) -- a replay
between export and load would otherwise pair vectors with other text. Then ONE transaction: the previous GPU
generation is deactivated (the CPU generation stays active: one per device, 0112), the new one recorded active with
its selection evidence, the table emptied and refilled, and the HNSW index rebuilt from its own definition (dropped
first: a graph grown row by row over a million inserts is slow and worse connected). Dry run by default.

With --apply it also writes the GPU query encoder's bundle (nizam.inference.remote) to NIZAM_GPU_ENCODER_DIR (default
<CORPUS_ROOT>/models/encoder-gpu): encoder.json, the run's dev question vectors as reference_q.npy and their texts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np  # noqa: E402

from nizam.storage.db import connect  # noqa: E402
from tools.kaggle.shards import load_ds, verified_runs  # noqa: E402

INDEX = "ix_chunk_embedding_gpu_hnsw"


def column_dims(cur) -> tuple[int, int]:
    cur.execute("""SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a
                    WHERE a.attrelid = 'chunk_embedding_gpu'::regclass AND a.attname IN ('bits', 'half')""")
    t = dict(cur.fetchall())
    if "bits" not in t:
        sys.exit("chunk_embedding_gpu does not exist: apply migration 0113 first")
    w = int(t["bits"].split("(")[1].rstrip(")"))
    d = int(t["half"].split("(")[1].rstrip(")")) if "half" in t else 0
    return w, d


def encoder_dir() -> Path:
    if os.environ.get("NIZAM_GPU_ENCODER_DIR"):
        return Path(os.environ["NIZAM_GPU_ENCODER_DIR"])
    return Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data")) / "models" / "encoder-gpu"


def copy_rows(cur, gen, ids, juris, R, width, rdims):
    """COPY every shard's rows; returns rows written"""
    n = 0
    fmt = "[" + ",".join(["%.5g"] * rdims) + "]" if rdims else None
    # the half column exists only when the table stores a rescoring prefix (0113 stores bits only)
    cols = "chunk_id, generation_id, jurisdiction, bits" + (", half" if rdims else "")
    for s in sorted(R.shards):
        lo, hi = R.bounds[s], R.bounds[s + 1]
        X = np.load(R.shards[s])
        bits = ((X[:, :width] > 0).astype(np.uint8) + ord("0"))
        with cur.copy(f"COPY chunk_embedding_gpu ({cols}) FROM STDIN") as cp:
            for i in range(hi - lo):
                row = (int(ids[lo + i]), gen, juris[lo + i], bits[i].tobytes().decode("ascii"))
                cp.write_row(row + (fmt % tuple(X[i, :rdims].astype(np.float32).tolist()),) if rdims else row)
        n += hi - lo
        print(f"  shard {s}: {hi - lo} rows", flush=True)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ds", type=Path); ap.add_argument("runs", nargs="+")
    ap.add_argument("--topup", action="store_true"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--evidence", type=Path, action="append", default=[])
    a = ap.parse_args()
    t0 = time.time()
    ids, _units, jidx, jnames = load_ds(a.ds)
    juris = [jnames[j] for j in jidx]
    R = verified_runs(ids, a.runs)
    if R.missing:
        sys.exit(f"shards missing: {R.missing}")
    m = R.meta
    evidence = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in a.evidence}   # read now: a dry run checks
    with connect() as conn, conn.cursor() as cur:
        width, rdims = column_dims(cur)
        cur.execute("SELECT DISTINCT chunker FROM chunk")
        chunkers = [r[0] for r in cur.fetchall()]
        if len(chunkers) != 1:
            sys.exit(f"more than one chunker in the table: {chunkers}")
        cur.execute("""SELECT id, model, revision, query_template FROM embedding_generation
                        WHERE active AND encoder_device = 'gpu'""")
        active = cur.fetchone()
        if a.topup:
            if active is None or (active[1], active[2], active[3]) != (m["model"], m["revision"], m["query_template"]):
                sys.exit(f"a top-up must be the active GPU generation's model, commit and template; active: {active}")
            ref = np.load(encoder_dir() / "reference_q.npy").astype(np.float32)
            ref /= np.linalg.norm(ref, axis=1, keepdims=True)
            agree = float((ref * R.dev_q[: len(ref)]).sum(1).min())
            if agree < 0.999:
                sys.exit(f"the top-up run's dev questions do not reproduce the generation's (cosine {agree:.5f})")
            cur.execute("""SELECT c.id, c.jurisdiction FROM chunk c WHERE NOT EXISTS
                             (SELECT 1 FROM chunk_embedding_gpu e WHERE e.chunk_id = c.id) ORDER BY c.id""")
        else:
            cur.execute("SELECT id, jurisdiction FROM chunk ORDER BY id")
        db = cur.fetchall()
        if [r[0] for r in db] != sorted(int(i) for i in ids):
            sys.exit(f"the export's {len(ids)} chunk ids are not the {'chunks lacking a GPU vector' if a.topup else 'chunks'}"
                     f" the database holds ({len(db)}): re-export and re-embed -- vectors are never paired with other text")
        dbj = {r[0]: r[1] for r in db}
        if any(dbj[int(i)] != j for i, j in zip(ids, juris)):
            sys.exit("a chunk's jurisdiction differs from the export's")
        print(f"checks passed: {len(ids)} chunks, {m['model']}@{m['revision'][:12]}, storing bit({width})"
              f"{f' + halfvec({rdims})' if rdims else ''}{' (top-up of generation %d)' % active[0] if a.topup else ''}")
        if not a.apply:
            print("dry run (nothing written); pass --apply")
            return 0
        if a.topup:
            gen = active[0]
            n = copy_rows(cur, gen, ids, juris, R, width, rdims)
        else:
            indexdef = None
            if _index_exists(cur):
                cur.execute("SELECT pg_get_indexdef(%s::regclass)", (INDEX,))
                indexdef = cur.fetchone()[0]
            if indexdef:
                cur.execute(f"DROP INDEX {INDEX}")
            cur.execute("UPDATE embedding_generation SET active = false WHERE active AND encoder_device = 'gpu'")
            selection = {"bake_off": "evals/shard_dense_eval.py and evals/lexical_benchmark.py, golden DEV split only",
                         "runs": [str(r) for r in a.runs], "agreement": R.agreement, "evidence": evidence,
                         "throughput": m.get("smoke_throughput")}
            cur.execute("""INSERT INTO embedding_generation (model, revision, dims, quantization, pooling, query_template,
                                  passage_source, max_tokens, chunker, chunk_count, selection, active, encoder_device,
                                  storage, rescore_dims, vector_dims)
                           VALUES (%s, %s, %s, 'binary_sign', %s, %s, 'context_prefix + newline + span text', %s, %s,
                                   %s, %s::jsonb, true, 'gpu', 'chunk_embedding_gpu', %s, %s) RETURNING id""",
                        (m["model"], m["revision"], width, m["pooling"], m["query_template"], m["max_tokens"],
                         chunkers[0], len(ids), json.dumps(selection), rdims or None, m["dims"]))
            gen = cur.fetchone()[0]
            cur.execute("TRUNCATE chunk_embedding_gpu")
            n = copy_rows(cur, gen, ids, juris, R, width, rdims)
            if indexdef:
                t = time.time()
                cur.execute("SET LOCAL maintenance_work_mem = '1GB'")
                cur.execute("SET LOCAL max_parallel_maintenance_workers = 2")
                cur.execute(indexdef)
                print(f"  {INDEX} rebuilt in {time.time() - t:.0f}s")
        cur.execute("SELECT count(*) FROM chunk_embedding_gpu WHERE generation_id = %s", (gen,))
        have = cur.fetchone()[0]
        want = len(db) if a.topup else len(ids)
        if (a.topup and n != want) or (not a.topup and have != want):
            raise SystemExit(f"wrote {n}, table holds {have}, expected {want}; rolled back")
        conn.commit()
    if not a.topup:
        write_bundle(m, R, a.ds)
    print(f"generation {gen}: {n} vectors written in {time.time() - t0:.0f}s")
    return 0


def _index_exists(cur) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (INDEX,))
    return bool(cur.fetchone()[0])


def write_bundle(m: dict, R, ds: Path) -> None:
    d = encoder_dir()
    d.mkdir(parents=True, exist_ok=True)
    dev = json.loads((ds / "dev.json").read_text(encoding="utf-8"))
    (d / "encoder.json").write_text(json.dumps({
        "model": m["model"], "revision": m["revision"], "pooling": m["pooling"], "query_template": m["query_template"],
        "max_tokens": m["max_tokens"], "dims": m["dims"], "normalised": True}, indent=1), encoding="utf-8")
    np.save(d / "reference_q.npy", R.dev_q.astype(np.float32))
    (d / "reference_questions.json").write_text(json.dumps([c["q"] for c in dev], ensure_ascii=False, indent=0),
                                                encoding="utf-8")
    print(f"GPU encoder bundle written to {d}")


if __name__ == "__main__":
    raise SystemExit(main())
