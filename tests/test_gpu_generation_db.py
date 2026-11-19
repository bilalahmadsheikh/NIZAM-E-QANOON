"""Migration 0113 / D-099 against the corpus: the GPU generation's table takes each vector's scope from its chunk, loses
a vector with its chunk, audit A22 sees a chunk left without one, and a Qwen3-Embedding-8B question reaches only the
8B space (never bge-m3's chunk.embedding). Every write is rolled back."""
import os
from datetime import date
from pathlib import Path

import pytest

TODAY = date(2026, 11, 20)
A22_MISSING = """SELECT count(*) FROM chunk c JOIN embedding_generation g ON g.active AND g.storage = 'chunk_embedding_gpu'
                  WHERE NOT EXISTS (SELECT 1 FROM chunk_embedding_gpu e
                                     WHERE e.chunk_id = c.id AND e.generation_id = g.id)"""


@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('chunk_embedding_gpu')")
                if cur.fetchone()[0] is None:
                    pytest.skip("migration 0113 is not applied")
                cur.execute("SELECT count(*) FROM embedding_generation WHERE active AND encoder_device = 'gpu'")
                if not cur.fetchone()[0]:
                    pytest.skip("no GPU generation is loaded (tools/load_embeddings_gpu.py)")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _one(cur):
    cur.execute("""SELECT e.chunk_id, e.generation_id, e.bits::text, c.jurisdiction
                     FROM chunk_embedding_gpu e JOIN chunk c ON c.id = e.chunk_id
                    WHERE c.jurisdiction <> 'fed' LIMIT 1""")
    return cur.fetchone()


def test_the_scope_is_the_chunks_whatever_the_writer_says(conn):
    with conn.cursor() as cur:
        cid, gen, bits, juris = _one(cur)
        cur.execute("DELETE FROM chunk_embedding_gpu WHERE chunk_id = %s", (cid,))
        cur.execute("INSERT INTO chunk_embedding_gpu (chunk_id, generation_id, jurisdiction, bits) "
                    "VALUES (%s, %s, 'fed', %s::bit(4096))", (cid, gen, bits))
        cur.execute("SELECT jurisdiction FROM chunk_embedding_gpu WHERE chunk_id = %s", (cid,))
        assert cur.fetchone()[0] == juris != "fed"


def test_a_vector_of_the_wrong_width_is_refused(conn):
    with conn.cursor() as cur:
        cid, gen, bits, _ = _one(cur)
        cur.execute("DELETE FROM chunk_embedding_gpu WHERE chunk_id = %s", (cid,))
        with pytest.raises(Exception, match="length"):
            cur.execute("INSERT INTO chunk_embedding_gpu (chunk_id, generation_id, jurisdiction, bits) "
                        "VALUES (%s, %s, '', %s::bit varying)", (cid, gen, bits[:1024]))


def test_removing_a_chunk_removes_its_vector_and_a22_sees_a_gap(conn):
    with conn.cursor() as cur:
        cur.execute(A22_MISSING)
        assert cur.fetchone()[0] == 0
        cid, *_ = _one(cur)
        cur.execute("DELETE FROM chunk WHERE id = %s", (cid,))
        cur.execute("SELECT count(*) FROM chunk_embedding_gpu WHERE chunk_id = %s", (cid,))
        assert cur.fetchone()[0] == 0                      # ON DELETE CASCADE
        cur.execute(A22_MISSING)
        assert cur.fetchone()[0] == 0                      # the chunk went with it: nothing is missing
        cid2, *_ = _one(cur)
        cur.execute("DELETE FROM chunk_embedding_gpu WHERE chunk_id = %s", (cid2,))
        cur.execute(A22_MISSING)
        assert cur.fetchone()[0] == 1                      # a chunk without its vector is A22's failure


def _bundle() -> Path:
    d = Path(os.environ.get("NIZAM_GPU_ENCODER_DIR")
             or Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data")) / "models" / "encoder-gpu")
    if not (d / "reference_q.npy").exists():
        pytest.skip(f"no GPU encoder bundle at {d}")
    return d


def test_an_8b_question_searches_only_the_8b_space(conn):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
    from precomputed_encoder import PrecomputedEncoder

    from nizam.storage.lexical import Filters
    from nizam.storage.unit_search import Session
    import json
    d = _bundle()
    enc = PrecomputedEncoder.from_bundle(d)
    q = json.loads((d / "reference_questions.json").read_text(encoding="utf-8"))[0]
    with conn.cursor() as cur:
        s = Session(cur, Filters(as_of=TODAY, jurisdictions=None))
        gen = s.generation_for(enc.info)
        assert gen["storage"] == "chunk_embedding_gpu" and gen["dims"] == 4096
        hits = s.dense_hits(enc.embed(q), 20, gen)
        assert hits and s.last_dense_mode == "hnsw"
        assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
        bge = enc.info.__class__("BAAI/bge-m3", enc.info.revision, enc.info.pooling, enc.info.query_template,
                                 enc.info.max_tokens, 1024)
        assert s.generation_for(bge) is None               # a revision/template from another space matches nothing
