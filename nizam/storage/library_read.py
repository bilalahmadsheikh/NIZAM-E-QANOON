"""Bounded preview of the release views (docs/07 §2–3, INV-4/5).

No DDL, replay, adjudication, or corpus writes. No whole-tree queries on taps.
The pool has an explicit connection/queue budget independent of mobile users.
"""
from contextlib import contextmanager
from datetime import date
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from nizam.storage.db import dsn


class LibraryRead:
    def __init__(self):
        self.pool = ConnectionPool(dsn(), min_size=0, max_size=3, max_waiting=12,
                                   timeout=3, open=False,
                                   kwargs={"row_factory": dict_row})

    def open(self):
        self.pool.open()

    def close(self):
        self.pool.close()

    @contextmanager
    def transaction(self):
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '12s'")
            yield conn

    def instruments(self, *, q: str, jurisdiction: str, kind: str,
                    after: str | None, limit: int, as_of: date):
        with self.transaction() as conn:
            return conn.execute("""
                SELECT i.id, i.short_title AS title, i.kind::text, i.year,
                       i.jurisdiction::text, i.status::text, i.source_url,
                       i.document_id, i.source_sha256 AS source_hash
                  FROM v_release_instrument i
                 WHERE (%(q)s = '' OR i.short_title ILIKE %(pattern)s ESCAPE '!')
                   AND (%(jurisdiction)s = '' OR i.jurisdiction::text = %(jurisdiction)s)
                   AND (%(kind)s = '' OR i.kind::text = %(kind)s)
                   AND (%(after)s::uuid IS NULL OR i.id > %(after)s::uuid)
                 ORDER BY i.id LIMIT %(limit)s
            """, dict(q=q, pattern='%' + q.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%',
                      jurisdiction=jurisdiction, kind=kind, after=after, limit=limit)).fetchall()

    @staticmethod
    def _instrument(conn, instrument_id: UUID):
        return conn.execute("""
            SELECT id, short_title AS title, kind::text, year, jurisdiction::text,
                   status::text, source_url, document_id, source_sha256 AS source_hash
              FROM v_release_instrument WHERE id = %s
        """, (instrument_id,)).fetchone()

    def instrument(self, instrument_id: UUID, *, as_of: date):
        with self.transaction() as conn:
            return self._instrument(conn, instrument_id)

    def children(self, instrument_id: UUID, *, parent: UUID | None,
                 after: tuple[int, str] | None, limit: int, as_of: date):
        with self.transaction() as conn:
            if not self._instrument(conn, instrument_id):
                return None
            if parent and not conn.execute(
                "SELECT 1 FROM v_release_provision WHERE id=%s AND instrument_id=%s",
                (parent, instrument_id)).fetchone():
                return None
            # Parent already passed the release boundary in this same snapshot.
            # No recursive subtree, version text, or total count in list responses.
            return conn.execute("""
                SELECT p.id, p.instrument_id, p.parent_id, p.label, p.heading,
                       p.marginal_note, p.kind::text, p.ordinal, p.first_page,
                       EXISTS(SELECT 1 FROM provision c WHERE c.parent_id=p.id
                              AND c.instrument_id=p.instrument_id AND c.is_active) AS has_children
                  FROM provision p
                 WHERE p.instrument_id=%(instrument)s AND p.is_active
                   AND p.parent_id IS NOT DISTINCT FROM %(parent)s::uuid
                   AND (%(ordinal)s::int IS NULL OR (p.ordinal,p.id) >
                        (%(ordinal)s::int,%(id)s::uuid))
                 ORDER BY p.ordinal,p.id LIMIT %(limit)s
            """, dict(instrument=instrument_id, parent=parent,
                      ordinal=after[0] if after else None, id=after[1] if after else None,
                      limit=limit)).fetchall()

    def provision(self, provision_id: UUID, *, as_of: date):
        with self.transaction() as conn:
            row = conn.execute("""
                SELECT p.id, p.instrument_id, p.parent_id, p.label, p.heading,
                       p.marginal_note, p.kind::text, p.ordinal, p.first_page,
                       EXISTS(SELECT 1 FROM provision c WHERE c.parent_id=p.id
                              AND c.instrument_id=p.instrument_id AND c.is_active) AS has_children
                  FROM provision p
                 WHERE p.id=%(id)s AND p.is_active
            """, dict(id=provision_id, as_of=as_of)).fetchone()
            if not row:
                return None
            row['instrument'] = self._instrument(conn, row['instrument_id'])
            if not row['instrument']:
                return None
            # Same-snapshot release check above is mandatory. Separating it
            # avoids expanding the expensive release proof twice in one join.
            version = conn.execute("""
                SELECT text_en, text_ur, operation::text,
                       lower(validity)::text AS valid_from, upper(validity)::text AS valid_to
                  FROM provision_version
                 WHERE provision_id=%s AND validity @> %s::date
            """, (provision_id, as_of)).fetchone()
            row.update(version or dict(text_en=None,text_ur=None,operation=None,valid_from=None,valid_to=None))
            # Ancestors are a short path, not the entire instrument tree.
            row['ancestors'] = conn.execute("""
                SELECT a.id, a.label, a.heading, a.kind::text
                  FROM provision a JOIN provision p ON p.id=%s
                 WHERE a.instrument_id=p.instrument_id AND a.is_active
                   AND a.path @> p.path AND a.id<>p.id
                 ORDER BY nlevel(a.path)
            """, (provision_id,)).fetchall()
            return row
