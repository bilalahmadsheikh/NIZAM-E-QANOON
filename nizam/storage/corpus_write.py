"""The write side of ICorpusWrite for L1 extraction output (Document 03 §6).

One document lands in one transaction: blob, document, pages, blocks. A partial
extraction is worse than none, because segmentation would then read a document
that is silently missing pages.

Re-extracting the same bytes with the same extractor replaces the previous
document rather than adding a second one, so the pipeline is resumable and
re-runnable — Document 09a §6: "Every stage writes its state to the database, so
an interrupted run continues rather than restarting."
"""
from __future__ import annotations

from nizam.shared.corpus_types import ExtractedDocument
from nizam.storage.db import connect


def blobs_needing_extraction(limit: int | None = None,
                             source_id: str | None = None,
                             retry_failed: bool = False) -> list[tuple[str, str, int]]:
    """The extraction work list, from the v_extract_queue view (migration 0003).

    By default a blob that already failed is not retried: re-running the same
    extractor over the same bytes produces the same rejection, and burying the
    real work under 150 repeated failures helps nobody. `retry_failed` is for
    after the extractor changes.

    Returns (sha256, object_key, byte_length).
    """
    where = []
    params: list = []
    if source_id:
        where.append("source_id = %s")
        params.append(source_id)
    if not retry_failed:
        where.append("last_outcome IS DISTINCT FROM 'rejected'")
    q = "SELECT sha256, object_key, byte_length FROM v_extract_queue"
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY byte_length"
    if limit:
        q += " LIMIT %s"
        params.append(limit)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(q, params)
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def blobs_for_reextraction(sha_prefix: str | None = None,
                           source_id: str | None = None,
                           limit: int | None = None) -> list[tuple[str, str, int]]:
    """Explicit repair work list, including blobs with an active extraction."""
    where = ["1=1"]
    params: list = []
    if sha_prefix:
        where.append("sha256 LIKE %s")
        params.append(sha_prefix + "%")
    if source_id:
        where.append("source_id=%s")
        params.append(source_id)
    q = ("SELECT sha256,object_key,byte_length FROM blob WHERE "
         + " AND ".join(where) + " ORDER BY byte_length")
    if limit:
        q += " LIMIT %s"
        params.append(limit)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(q, params)
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def record_attempt(sha256: str, extractor: str, outcome: str, *,
                   lane: str | None = None, document_id: int | None = None,
                   reason: str | None = None, detail: dict | None = None,
                   duration_ms: int | None = None) -> None:
    """Persist one extraction attempt, successful or not (doc 02 §8)."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extraction_attempt
                (sha256, extractor, lane, outcome, document_id, reason, detail, duration_ms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (sha256, extractor, lane, outcome, document_id, reason,
             _json(detail or {}), duration_ms),
        )


def register_blob(sha256: str, source_id: str, object_key: str,
                  byte_length: int, media_type: str = "application/pdf") -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO blob (sha256, source_id, object_key, byte_length, media_type, first_seen)
            SELECT %s, %s, %s, %s, %s, min(fetched_at)
              FROM source_observation WHERE sha256 = %s
            ON CONFLICT (sha256) DO NOTHING
            """,
            (sha256, source_id, object_key, byte_length, media_type, sha256),
        )


def save_document(doc: ExtractedDocument) -> int:
    """Persist one extracted revision atomically. Returns its document id.

    Migration 0012 makes extraction append-only. The former active expression
    is retired, not deleted, so its pages and blocks remain exact audit evidence.
    A failure anywhere in the copy rolls this transaction back and restores the
    former active revision.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM document
             WHERE sha256=%s AND language=%s AND publication_role=%s AND is_active
             FOR UPDATE
            """,
            (doc.sha256, doc.language, doc.publication_role),
        )
        previous = cur.fetchone()
        previous_id = previous[0] if previous else None
        if previous_id is not None:
            cur.execute(
                "UPDATE document SET is_active=false, retired_at=now() WHERE id=%s",
                (previous_id,),
            )
        cur.execute(
            """
            INSERT INTO document (sha256, language, publication_role, page_count,
                                  char_count, printable_ratio, empty_pages, lane,
                                  extractor, extractor_config, pdf_metadata,
                                  supersedes_document_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (doc.sha256, doc.language, doc.publication_role, doc.page_count,
             doc.char_count, doc.printable_ratio, doc.empty_pages, doc.lane,
             doc.extractor, _json(doc.extractor_config), _json(doc.pdf_metadata),
             previous_id),
        )
        document_id = cur.fetchone()[0]

        with cur.copy(
            "COPY page (document_id, page_no, width, height, char_count, lane,"
            " crop_box, media_box) FROM STDIN"
        ) as cp:
            for p in doc.pages:
                cp.write_row((document_id, p.page_no, p.width, p.height, p.char_count,
                              p.lane, list(p.crop_box) if p.crop_box else None,
                              list(p.media_box) if p.media_box else None))

        with cur.copy(
            "COPY text_block (document_id, page_no, block_no, reading_order,"
            " x0, y0, x1, y1, text, script, confidence, inside_cropbox) FROM STDIN"
        ) as cp:
            for b in doc.blocks:
                cp.write_row((document_id, b.page_no, b.block_no, b.reading_order,
                              b.x0, b.y0, b.x1, b.y1, b.text, b.script, b.confidence,
                              b.inside_cropbox))

        return document_id


def _json(value: dict) -> str:
    import json
    return json.dumps(value, ensure_ascii=False)


def document_summary(document_id: int) -> dict:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.sha256, d.page_count, d.char_count, d.printable_ratio,
                   d.empty_pages, d.lane, d.extractor,
                   (SELECT count(*) FROM page p WHERE p.document_id = d.id),
                   (SELECT count(*) FROM text_block b WHERE b.document_id = d.id)
              FROM document d WHERE d.id = %s
            """,
            (document_id,),
        )
        r = cur.fetchone()
        keys = ("id", "sha256", "page_count", "char_count", "printable_ratio",
                "empty_pages", "lane", "extractor", "pages_stored", "blocks_stored")
        return dict(zip(keys, r))
