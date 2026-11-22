"""Chunks and vectors for released judgment paragraphs (docs/PRECEDENT-MODEL.md §6.1, D-121).

    uv run python -m nizam.workers.judgment_chunk [--apply] [--processes 3]

1. Chunks of a judgment no longer released (re-read, retired) are removed: the table is derived.
2. Each body and footnote paragraph of a released judgment without chunks is cut by the statutes' own span rule
   (nizam.storage.chunking.spans: at most 1,200 characters, preferring a sentence end). Each chunk carries a context
   prefix built from records only: court, case, decision date, and the printed paragraph or footnote number.
3. Each new chunk is embedded by the active CPU generation (bge-m3, D-098): the same model and vector space as the
   statute chunks, so one query vector searches both. The encoder must be that generation's model
   (check_generation refuses otherwise).

Header, closing and furniture paragraphs are not chunked: they hold names, counsel and signatures, not law.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

from nizam.storage.chunking import CHUNKER, PREFIX_MAX, passage_text, spans
from nizam.storage.db import connect

_ENC = None


def _prefix(court: str, case: str, day, kind: str, no: str | None, undated: bool = False) -> str:
    """`undated` (D-124): `day` is only the latest possible decision day and is never written as the date."""
    where = (f"para {no}" if no else "") if kind == "body" else (f"footnote {no}" if no else "footnote")
    when = "date not printed" if undated else day.strftime("%d %b %Y")
    parts = [court, " ".join(case.split())[:110], when] + ([where] if where else [])
    return " | ".join(parts)[:PREFIX_MAX]


def _embed(batch):
    global _ENC
    if _ENC is None:
        os.environ.setdefault("NIZAM_ENCODER_THREADS", "2")
        from nizam.inference.encoder import encoder
        _ENC = encoder()
    return [(key, _ENC.passage_bits(passage_text(pfx, text))) for key, pfx, text in batch]


def main() -> int:
    ap = argparse.ArgumentParser(description="judgment chunks and CPU vectors (D-121)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--processes", type=int, default=3)
    a = ap.parse_args()
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id, model, revision, pooling, query_template FROM embedding_generation
                        WHERE active AND storage = 'chunk.embedding'""")
        g = cur.fetchone()
        if g is None:
            raise SystemExit("no active CPU embedding generation (storage chunk.embedding)")
        generation = dict(zip(("id", "model", "revision", "pooling", "query_template"), g))
        from nizam.inference.encoder import check_generation, encoder
        check_generation(generation, encoder().info)

        cur.execute("""DELETE FROM judgment_chunk c WHERE NOT EXISTS (
                           SELECT 1 FROM v_release_judgment j WHERE j.id = c.judgment_id AND j.decided_on = c.decided_on)""")
        removed = cur.rowcount
        cur.execute("""SELECT p.id, p.decided_on, p.judgment_id, p.kind, p.printed_no, p.text, c.name, j.case_no_printed,
                              j.decided_on_basis = 'undated'
                         FROM v_release_judgment_paragraph p
                         JOIN v_release_judgment j ON j.id = p.judgment_id AND j.decided_on = p.decided_on
                         JOIN court c ON c.code = j.court_code
                        WHERE p.kind IN ('body', 'footnote')
                          AND NOT EXISTS (SELECT 1 FROM judgment_chunk k WHERE k.paragraph_id = p.id
                                                                         AND k.decided_on = p.decided_on)
                        ORDER BY p.decided_on, p.judgment_id, p.ordinal""")
        rows = cur.fetchall()
        pieces = []
        for pid, day, jid, kind, no, text, court, case, undated in rows:
            pfx = _prefix(court, case, day, kind, no, undated)
            for seq, sp in enumerate(spans(text)):
                pieces.append(((pid, day, jid, seq, sp.start, sp.end, pfx), pfx, text[sp.start:sp.end]))
        print(f"removed {removed} chunks of unreleased judgments; {len(rows)} paragraphs -> {len(pieces)} chunks "
              f"to embed with generation {generation['id']} ({generation['model']})", flush=True)
        if not a.apply:
            conn.rollback()
            print("dry run: nothing written (add --apply)")
            return 0
        conn.commit()
        batches = [pieces[i:i + 64] for i in range(0, len(pieces), 64)]
        done = 0
        with ProcessPoolExecutor(a.processes) as ex:
            for out in ex.map(_embed, batches):
                with cur.copy("COPY judgment_chunk (paragraph_id, decided_on, judgment_id, seq, char_start, char_end, "
                              "context_prefix, embedding, generation_id, chunker) FROM STDIN") as cp:
                    for (pid, day, jid, seq, s, e, pfx), bits in out:
                        cp.write_row((pid, day, jid, seq, s, e, pfx, bits, generation["id"], CHUNKER))
                conn.commit()
                done += len(out)
                if done % 2048 < 64:
                    rate = done / max(time.time() - t0, 1)
                    print(f"  {done}/{len(pieces)} chunks, {rate:.1f}/s", flush=True)
    print(f"done: {done} chunks in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
