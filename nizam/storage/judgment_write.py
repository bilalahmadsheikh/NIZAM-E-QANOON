"""The write side for judgments (migration 0119, docs/PRECEDENT-MODEL.md §3).

One document is written in one transaction: its reading (whatever came of it), its blocks, and, when it parsed, the
judgment with its opinions, paragraphs and lineage. A partial write is worse than none, because a judgment missing
paragraphs would be cited as if whole.

Re-reading the same bytes retires the active reading and its judgment (is_active, retired_at). Nothing is deleted.
"""
from __future__ import annotations

import json
import uuid

from nizam.storage.db import connect


def reference_data() -> tuple[dict[str, str], dict[str, tuple[str, list[str]]]]:
    """Court aliases (folded alias -> court code) and case types (code -> (kind, printed forms))."""
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT alias_key, court_code FROM court_alias WHERE withdrawn_at IS NULL")
        aliases = dict(cur.fetchall())
        cur.execute("SELECT code, kind, printed_forms FROM case_type")
        types = {code: (kind, list(forms)) for code, kind, forms in cur.fetchall()}
    return aliases, types


def record_sources(rows: list[dict]) -> int:
    """judgment_source rows for every archive member seen; an exact repeat is skipped. Returns rows added."""
    if not rows:
        return 0
    with connect() as c, c.cursor() as cur:
        added = 0
        for r in rows:
            cur.execute("""INSERT INTO judgment_source (source_id, court_code, archive, member, source_url, url_status,
                                                        sha256, byte_length, object_key, observed_at)
                           VALUES (%(source_id)s, %(court_code)s, %(archive)s, %(member)s, %(source_url)s,
                                   %(url_status)s, %(sha256)s, %(byte_length)s, %(object_key)s, %(observed_at)s)
                           ON CONFLICT (archive, member, sha256) DO NOTHING""", r)
            added += cur.rowcount
    return added


def unread_hashes(court_code: str, archive: str, parser: str | None = None,
                  held_gate: str | None = None) -> list[str]:
    """Hashes of this archive's members with no active reading, or (with `parser`) none by that parser.

    With `held_gate` ('J1'): only members whose active reading is held at that gate, to re-read them after the
    gate's rule changed without retiring any released judgment (D-124)."""
    with connect() as c, c.cursor() as cur:
        if held_gate:
            cur.execute("""SELECT DISTINCT s.sha256 FROM judgment_source s
                             JOIN judgment_document d ON d.sha256 = s.sha256 AND d.is_active
                            WHERE s.court_code = %s AND s.archive = %s AND d.outcome = 'held'
                              AND (%s = 'any' OR d.hold_reason LIKE %s) ORDER BY 1""",
                        (court_code, archive, held_gate, held_gate + ":%"))   # 'any': every held reading (D-138)
            return [r[0] for r in cur.fetchall()]
        cur.execute("""SELECT DISTINCT s.sha256 FROM judgment_source s
                        WHERE s.court_code = %s AND s.archive = %s
                          AND NOT EXISTS (SELECT 1 FROM judgment_document d WHERE d.sha256 = s.sha256 AND d.is_active
                                            AND (%s::text IS NULL OR d.parser = %s))
                        ORDER BY 1""", (court_code, archive, parser, parser))
        return [r[0] for r in cur.fetchall()]


def save_reading(*, sha256: str, court_code: str, extractor: str, parser: str, lane: str, language: str,
                 page_count: int, char_count: int, blocks: list, outcome: str, reason: str | None,
                 detail: dict, parsed=None) -> tuple[int, str]:
    """Write one reading, and its judgment when parsed. Returns (document id, final outcome).

    A parsed reading whose folded body text matches an active parsed reading of different bytes is recorded as a
    duplicate of it (gate J6), and no second judgment is written.
    """
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM judgment_document WHERE sha256 = %s AND is_active FOR UPDATE", (sha256,))
        prev = cur.fetchone()
        prev_id = prev[0] if prev else None
        if prev_id is not None:
            cur.execute("UPDATE judgment_document SET is_active = false, retired_at = now() WHERE id = %s", (prev_id,))
            cur.execute("UPDATE judgment SET is_active = false, retired_at = now() WHERE document_id = %s AND is_active",
                        (prev_id,))
        duplicate_of = None
        body_sha = parsed.body_sha256 if parsed is not None else None
        if parsed is not None and parsed.decided_on is None:
            # undated (D-124): decided_on holds the latest possible day, the day the court's archive was first
            # observed holding these bytes; it is the research-date filter, never shown as the decision date
            cur.execute("SELECT min(observed_at)::date FROM judgment_source WHERE sha256 = %s", (sha256,))
            latest = cur.fetchone()[0]
            late = [d for d in (parsed.hearing_on, parsed.decided_not_before) if d and latest and d > latest]
            if latest is None or late:
                outcome, parsed = "held", None
                reason = ("J1: undated, and no archive observation bounds it" if latest is None else
                          f"J1: undated, and the hearing or case year printed ({late[0]}) is after the archive held "
                          f"the file ({latest})")
            else:
                parsed.decided_on = latest
        if parsed is not None:
            cur.execute("""SELECT id FROM judgment_document WHERE body_sha256 = %s AND is_active AND outcome = 'parsed'
                            ORDER BY id LIMIT 1""", (body_sha,))
            dup = cur.fetchone()
            if dup:
                duplicate_of, outcome = dup[0], "duplicate"
                reason = f"J6: the same body text as document {dup[0]}"
        cur.execute("""INSERT INTO judgment_document (sha256, court_code, extractor, parser, lane, language, page_count,
                                                      char_count, outcome, hold_reason, duplicate_of_document,
                                                      body_sha256, detail, supersedes_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (sha256, court_code, extractor, parser, lane, language, page_count, char_count, outcome,
                     None if outcome == "parsed" else (reason or outcome), duplicate_of, body_sha,
                     json.dumps(detail, ensure_ascii=False, default=str), prev_id))
        doc_id = cur.fetchone()[0]
        if blocks:
            with cur.copy("COPY judgment_block (document_id, reading_order, page_no, x0, y0, x1, y1, text) "
                          "FROM STDIN") as cp:
                for b in blocks:
                    cp.write_row((doc_id, b.reading_order, b.page_no, b.x0, b.y0, b.x1, b.y1, b.text))
        if outcome == "parsed":
            _write_judgment(cur, doc_id, parsed, parser)
        return doc_id, outcome


def _write_judgment(cur, doc_id: int, j, parser: str) -> None:
    jid = uuid.uuid4()
    d = j.decided_on
    cur.execute("""INSERT INTO judgment (id, decided_on, document_id, court_code, seat, decided_on_basis,
                                         decided_on_printed, hearing_on, jurisdiction_printed, case_no_printed,
                                         case_type_code, case_number, case_year, bench_printed, bench_size,
                                         reported_flag, disposition, disposition_printed, parties_raw, parser,
                                         undated_reason, decided_not_before, decided_not_before_basis)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (jid, d, doc_id, j.court_code, j.seat, j.decided_on_basis, j.decided_on_printed, j.hearing_on,
                 j.jurisdiction_printed, j.case_no_printed, j.case_type_code, j.case_number, j.case_year,
                 j.bench_printed, len(j.bench_printed) or None, j.reported_flag, j.disposition,
                 j.disposition_printed, j.parties_raw, parser,
                 j.undated_reason[:500] if j.undated_reason else None, j.decided_not_before,
                 j.decided_not_before_basis))
    op_ids = [uuid.uuid4() for _ in j.opinions]
    for k, (oid, o) in enumerate(zip(op_ids, j.opinions)):
        cur.execute("""INSERT INTO judgment_opinion (id, judgment_id, decided_on, ordinal, kind, heading_printed,
                                                     author_printed) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (oid, jid, d, k, o.kind, o.heading_printed, o.author_printed))
    header_id = None
    with cur.copy("COPY judgment_paragraph (id, decided_on, judgment_id, opinion_id, ordinal, kind, printed_no, "
                  "page_first, page_last, first_block, last_block, text) FROM STDIN") as cp:
        for k, p in enumerate(j.paragraphs):
            pid = uuid.uuid4()
            if p.kind == "header" and header_id is None:
                header_id = pid
            cp.write_row((pid, d, jid, op_ids[p.opinion] if p.kind == "body" else None, k, p.kind, p.printed_no,
                          p.page_first, p.page_last, p.first_block, p.last_block, p.text))
    for ln in j.lineage:
        cur.execute("""INSERT INTO judgment_lineage (upper_judgment_id, upper_decided_on, relation, lower_court_code,
                                                     lower_court_printed, lower_case_printed, lower_decided_on,
                                                     outcome, source_paragraph_id, method, parser)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'grammar',%s)""",
                    (jid, d, ln.relation, ln.lower_court_code, ln.lower_court_printed, ln.lower_case_printed,
                     ln.lower_decided_on, ln.outcome, header_id, parser))
