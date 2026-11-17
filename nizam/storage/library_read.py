"""Bounded preview of the release views (docs/07 §2–3, INV-4/5).

No DDL, replay, adjudication, or corpus writes. No whole-tree queries on taps.
The pool has an explicit connection/queue budget independent of mobile users.

Historical expressions (migration 0064). An instrument an active manifest
declares historical -- owner decision 'historical-expression', e.g. document
4434 e0, the Constitution as amended to the 22nd Amendment -- is listed and
opened only for an `as_of` inside its window [valid_from, valid_to); at any
other date, today included, every read below answers as if it did not exist,
so it is never offered as current law (INV-5). `children()` and `provision()`
inherit the gate through `_instrument`. Without an `as_of` the API asks for
today, so a historical text is not discoverable by default (docs/SCHEMA.md).
The current expression of the same work is resolved at read time from its
stable key, on single-instrument opens only. Each read has a `_name(conn, ...)`
form over a connection, so a test can run the exact SQL inside a rolled-back
transaction.
"""
import re
from contextlib import contextmanager
from datetime import date
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from nizam.storage.db import dsn

# The instrument-level as_of gate (0064). A plain instrument has no row in
# v_instrument_historical and passes at every date.
HISTORICAL_GATE = "(h.instrument_id IS NULL OR h.historical_validity @> %(as_of)s::date)"

# The rendered name is the reviewed display title (migration 0070) when one stands, else the catalogue short title.
_INSTRUMENT_COLUMNS = """
    i.id, coalesce(i.display_title, i.short_title) AS title, i.kind::text, i.year, i.jurisdiction::text,
    i.status::text, i.source_url, i.document_id, i.source_sha256 AS source_hash,
    h.instrument_id IS NOT NULL AS historical,
    h.valid_from::text AS valid_from, h.valid_to::text AS valid_to,
    (SELECT m.currency FROM mv_instrument_serving m WHERE m.instrument_id = i.id) AS currency,
    (SELECT m.currency_reason FROM mv_instrument_serving m WHERE m.instrument_id = i.id) AS currency_reason"""


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

    @staticmethod
    def _instruments(conn, *, q: str, jurisdiction: str, kind: str,
                     after: list | None, limit: int, as_of: date):
        """Ordered by (titles starting with the query first, title, id) and continued by keyset on that triple
        (migration 0104 indexes the rendered title). `after` is the last row's [rank, sort title, id]."""
        esc = q.lower().replace('!', '!!').replace('%', '!%').replace('_', '!_')
        # Filter and order the serving snapshot (0094/0105: released, served laws only, rendered titles), then
        # fetch instrument details for this page alone. Rank: 0 = the title starts with the query, 1 = it contains
        # it, 2 = an amending law ('... (Amendment) ...') -- so 'penal code' finds the Code before its amendments.
        # Sort key ignores a leading number or 'The' ('21.The Inland ...', 'The Contract Act' under C).
        rows = conn.execute(f"""
            WITH t AS (
                SELECT m.instrument_id AS id,
                       -- strip only leading digits, punctuation and 'the'; never letters of any script (an Urdu
                       -- title stripped to '' sorted first)
                       regexp_replace(lower(m.instrument_title), '^[0-9[:space:][:punct:]]*(the\\s+)?', '')
                       AS sort_title,
                       lower(m.instrument_title) ~ '\\mamend' AS amending
                  FROM mv_instrument_serving m
                 WHERE (%(q)s = '' OR lower(m.instrument_title) LIKE %(contains)s ESCAPE '!')
                   AND (%(jurisdiction)s = '' OR m.jurisdiction = %(jurisdiction)s)
                   AND (%(kind)s = '' OR m.instrument_kind = %(kind)s)),
            ranked AS (
                SELECT id, sort_title,
                       CASE WHEN amending THEN 2 WHEN sort_title LIKE %(prefix)s ESCAPE '!' THEN 0 ELSE 1 END
                       AS sort_rank
                  FROM t),
            page AS (
                SELECT * FROM ranked
                 WHERE %(after_rank)s::int IS NULL
                    OR (sort_rank, sort_title, id) > (%(after_rank)s::int, %(after_title)s::text, %(after_id)s::uuid)
                 ORDER BY sort_rank, sort_title, id LIMIT %(limit)s)
            SELECT {_INSTRUMENT_COLUMNS}, NULL::uuid AS current_instrument_id, p.sort_rank, p.sort_title
              FROM page p JOIN instrument i ON i.id = p.id
              LEFT JOIN v_instrument_historical h ON h.instrument_id = i.id
             WHERE {HISTORICAL_GATE}
             ORDER BY p.sort_rank, p.sort_title, p.id
        """, dict(q=q, contains='%' + esc + '%', prefix=esc + '%',
                  jurisdiction=jurisdiction, kind=kind, limit=limit, as_of=as_of,
                  after_rank=after[0] if after else None, after_title=after[1] if after else None,
                  after_id=after[2] if after else None)).fetchall()
        return rows

    def instruments(self, *, q: str, jurisdiction: str, kind: str,
                    after: list | None, limit: int, as_of: date):
        with self.transaction() as conn:
            return self._instruments(conn, q=q, jurisdiction=jurisdiction, kind=kind,
                                     after=after, limit=limit, as_of=as_of)

    @staticmethod
    def _instrument(conn, instrument_id: UUID, as_of: date, *, resolve_current: bool = False):
        """The released instrument, if it is readable at `as_of`; the current
        expression of its work is resolved (to the active, released revision of
        the stable key) only when `resolve_current` -- a single-instrument open."""
        current = ("""(SELECT c.id FROM v_release_instrument c
                        WHERE c.source_observation_id = h.current_source_observation_id
                          AND c.expression_ordinal = h.current_expression_ordinal)"""
                   if resolve_current else "NULL::uuid")
        return conn.execute(f"""
            SELECT {_INSTRUMENT_COLUMNS}, {current} AS current_instrument_id
              FROM v_release_instrument i
              LEFT JOIN v_instrument_historical h ON h.instrument_id = i.id
             WHERE i.id = %(id)s AND {HISTORICAL_GATE}
        """, dict(id=instrument_id, as_of=as_of)).fetchone()

    @staticmethod
    def _historical_window(conn, instrument_id: UUID):
        """The window of a released historical instrument, whatever the date --
        so a closed-door open can say why, rather than a bare 404."""
        return conn.execute("""
            SELECT h.valid_from::text AS valid_from, h.valid_to::text AS valid_to
              FROM v_instrument_historical h
              JOIN v_release_instrument i ON i.id = h.instrument_id
             WHERE h.instrument_id = %s
        """, (instrument_id,)).fetchone()

    def instrument(self, instrument_id: UUID, *, as_of: date):
        with self.transaction() as conn:
            return self._instrument(conn, instrument_id, as_of, resolve_current=True)

    def historical_window(self, instrument_id: UUID):
        with self.transaction() as conn:
            return self._historical_window(conn, instrument_id)

    def _children(self, conn, instrument_id: UUID, *, parent: UUID | None,
                  after: tuple[int, str] | None, limit: int, as_of: date):
        if not self._instrument(conn, instrument_id, as_of):
            return None
        if parent and not conn.execute(
            "SELECT 1 FROM v_release_provision WHERE id=%s AND instrument_id=%s",
            (parent, instrument_id)).fetchone():
            return None
        # Parent already passed the release boundary in this same snapshot.
        # No recursive subtree, version text, or total count in list responses.
        rows = conn.execute("""
            SELECT p.id, p.instrument_id, p.parent_id, p.label, p.heading,
                   p.marginal_note, p.kind::text, p.ordinal, p.first_page, p.path::text AS path,
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
        self._add_captions(conn, instrument_id, rows, as_of)
        return rows

    # ------------------------------------------------------------------ division captions (17 Nov 2026)
    # A Part or Chapter whose printed title line the parser kept as the division's own words ('PART I' then
    # 'INTRODUCTORY') has no heading, so lists showed it as 'Part I' alone. Its caption is its heading, else that
    # short served text -- the rule the law page's chapter groups already follow (D-065). Read through
    # operative_provision as at the date (INV-5), with the instrument and paths as values (see unit text below).
    CAPTION_KINDS = ('part', 'chapter', 'division', 'title', 'schedule', 'annexure', 'appendix')
    CAPTION_CHARS = 120

    def _add_captions(self, conn, instrument_id: UUID, rows: list[dict], as_of: date):
        need = [r['path'] for r in rows if r['kind'] in self.CAPTION_KINDS and not r.get('heading')]
        served = {}
        if need:
            conn.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', '', true)",
                         (as_of.isoformat(),))
            served = {r['path']: ' '.join((r['text'] or '').split()) for r in conn.execute("""
                SELECT path::text AS path, CASE WHEN text_language IN ('ur', 'sd') THEN text_ur ELSE text_en END AS text
                  FROM operative_provision WHERE instrument_id = %s AND path = ANY(%s::ltree[])
            """, (instrument_id, need)).fetchall()}
        for r in rows:
            own = served.get(r.pop('path'), '')
            r['caption'] = r.get('heading') or (own if 0 < len(own) <= self.CAPTION_CHARS else None)

    def children(self, instrument_id: UUID, *, parent: UUID | None,
                 after: tuple[int, str] | None, limit: int, as_of: date):
        with self.transaction() as conn:
            return self._children(conn, instrument_id, parent=parent, after=after,
                                  limit=limit, as_of=as_of)

    def _provision(self, conn, provision_id: UUID, *, as_of: date, with_version: bool = True):
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
        row['instrument'] = self._instrument(conn, row['instrument_id'], as_of,
                                             resolve_current=True)
        if not row['instrument']:
            return None
        # Same-snapshot release check above is mandatory. Separating it
        # avoids expanding the expensive release proof twice in one join.
        # The segmenter writes every expression's text to text_en; an Urdu or Sindhi expression (instrument
        # text_language, measured, migration 0070) is served as text_ur and never as English.
        version = None if not with_version else conn.execute("""
            SELECT CASE WHEN i.text_language IN ('ur', 'sd') THEN NULL ELSE v.text_en END AS text_en,
                   CASE WHEN i.text_language IN ('ur', 'sd') THEN coalesce(v.text_ur, v.text_en)
                        ELSE v.text_ur END AS text_ur,
                   i.text_language,
                   v.operation::text,
                   lower(v.validity)::text AS valid_from, upper(v.validity)::text AS valid_to
              FROM provision_version v
              JOIN provision p ON p.id = v.provision_id
              JOIN instrument i ON i.id = p.instrument_id
             WHERE v.provision_id=%s AND v.validity @> %s::date
        """, (provision_id, as_of)).fetchone()
        row.update(version or dict(text_en=None,text_ur=None,text_language=None,operation=None,
                                   valid_from=None,valid_to=None))
        # Ancestors are a short path, not the entire instrument tree.
        row['ancestors'] = conn.execute("""
            SELECT a.id, a.label, a.heading, a.kind::text, a.path::text AS path
              FROM provision a JOIN provision p ON p.id=%s
             WHERE a.instrument_id=p.instrument_id AND a.is_active
               AND a.path @> p.path AND a.id<>p.id
             ORDER BY nlevel(a.path)
        """, (provision_id,)).fetchall()
        self._add_captions(conn, row['instrument_id'], row['ancestors'], as_of)
        return row

    def provision(self, provision_id: UUID, *, as_of: date):
        with self.transaction() as conn:
            return self._provision(conn, provision_id, as_of=as_of)

    # ------------------------------------------------------------------ unit text (17 Nov 2026)
    # A unit and everything under it, as `operative_provision` serves it (INV-5: never the base table): the reader
    # shows a section the way the statute prints it -- sub-sections, clauses, provisos -- in ONE request instead of
    # one tap and one round trip per sub-unit. Bounded by UNIT_NODE_LIMIT; `truncated` says when more exist.
    #
    # The view is queried with the instrument id and path as VALUES, resolved first: joined from a CTE the planner
    # evaluated operative_provision over every law (47 s for one section); with values it is ~10 ms.
    UNIT_NODE_LIMIT = 400

    @staticmethod
    def _law_status(conn, instrument_id: UUID):
        """The law-level serving record (mv_instrument_serving, migrations 0093-0095); None for an as-made text that
        is served through its consolidated twin (0075)."""
        return conn.execute("""
            SELECT currency, currency_reason, not_current_from::text, law_repealed_on::text AS repealed_on,
                   enacted_on::text, commenced_on::text, territory_reach, extent_basis, territory_exits
              FROM mv_instrument_serving WHERE instrument_id = %s
        """, (instrument_id,)).fetchone()

    def _unit_text(self, conn, provision_id: UUID, *, as_of: date, territory: str | None):
        # the head carries identity, ancestors and the instrument; its words come from the served nodes below
        head = self._provision(conn, provision_id, as_of=as_of, with_version=False)
        if head is None:
            return None
        root = conn.execute("SELECT path::text FROM provision WHERE id = %s", (provision_id,)).fetchone()
        conn.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                     (as_of.isoformat(), territory or ''))
        rows = conn.execute("""
            SELECT provision_id AS id, parent_id, provision_kind AS kind, label, heading, marginal_note,
                   nlevel(path) - nlevel(%(root)s::ltree) AS depth, first_page,
                   text_en, text_ur, text_language, operation, survives_repeal
              FROM operative_provision
             WHERE instrument_id = %(instrument)s AND path <@ %(root)s::ltree
             ORDER BY ordinal, path
             LIMIT %(limit)s
        """, dict(instrument=head['instrument_id'], root=root['path'], limit=self.UNIT_NODE_LIMIT + 1)).fetchall()
        law = self._law_status(conn, head['instrument_id'])
        not_served, not_served_from = None, None
        # a heading-only unit (a section whose words are all in its sub-sections) has no version of its own: it is
        # served when anything under it is; only an empty subtree needs a reason
        if not rows:
            not_served, not_served_from = self._why_not_served(conn, head, root['path'], law, as_of, territory)
        return dict(item=head, law=law, nodes=rows[:self.UNIT_NODE_LIMIT],
                    truncated=len(rows) > self.UNIT_NODE_LIMIT,
                    not_served=not_served, not_served_from=not_served_from)

    @staticmethod
    def _why_not_served(conn, head, root_path, law, as_of: date, territory: str | None):
        """Why the unit is not served at `as_of` in `territory`, from the same records the view reads. A reason code,
        never a guess; 'no_text_for_date' is the honest remainder (e.g. text known only from its capture date)."""
        if law is None:
            return 'served_through_consolidated_text', None
        iso = as_of.isoformat()
        if law['repealed_on'] and law['repealed_on'] <= iso:
            return 'law_repealed', law['repealed_on']
        if law['currency'] in ('not_current', 'historical') and law['not_current_from'] \
                and law['not_current_from'] <= iso:
            return f"law_{law['currency']}", law['not_current_from']
        if (law['enacted_on'] and law['enacted_on'] > iso) or (law['commenced_on'] and law['commenced_on'] > iso):
            return 'law_not_yet_in_force', law['commenced_on'] or law['enacted_on']
        if territory and territory not in (law['territory_reach'] or []):
            return 'law_does_not_run_in_territory', None
        exit_on = (law['territory_exits'] or {}).get(territory) if territory else None
        if exit_on and exit_on <= iso:
            return 'law_repealed_in_territory', exit_on
        cut = conn.execute("""
            SELECT min(effective_from)::text AS d FROM mv_provision_repeal
             WHERE instrument_id = %s AND %s::ltree <@ path AND effective_from <= %s
               AND (territory_key = '*' OR territory_key = %s)
        """, (head['instrument_id'], root_path, as_of, territory or '*')).fetchone()
        if cut and cut['d']:
            return 'unit_repealed', cut['d']
        return 'no_text_for_date', None

    def unit_text(self, provision_id: UUID, *, as_of: date, territory: str | None = None):
        with self.transaction() as conn:
            return self._unit_text(conn, provision_id, as_of=as_of, territory=territory)

    # ------------------------------------------------------------------ section index (17 Nov 2026)
    # Every served section-level unit of a law, in printed order, with its Part/Chapter, a short preview of its own
    # words and a citation rendered from the records (INV-1). One pass over operative_provision for the law (the
    # PPC: 1,373 served units, 2.3 s cold, ~30 ms warm), then cached per (law, as_of, territory) so pages are slices
    # of a list -- a reader scrolling 642 sections never waits on the database again.
    # a preamble is listed too, first: it precedes the enacting text by definition, though 477 released laws carry an
    # ordinal after their first section (the segmenter numbers it after the opening chapter's subtree)
    # an annexure or appendix carries law text as a schedule does (the Constitution's Annex, D-069)
    SECTION_KINDS = ('preamble', 'section', 'article', 'rule', 'regulation', 'schedule', 'annexure', 'appendix')
    CONTAINER_KINDS = ('part', 'chapter', 'division', 'title')
    PREVIEW_CHARS = 300
    _index_cache: dict = {}
    _INDEX_TTL = 600.0
    _INDEX_MAX = 64

    @classmethod
    def _cached(cls, key):
        import time
        hit = cls._index_cache.get(key)
        if hit and time.monotonic() - hit[0] < cls._INDEX_TTL:
            return hit[1]
        return None

    @classmethod
    def _remember(cls, key, value):
        import time
        if len(cls._index_cache) >= cls._INDEX_MAX:
            oldest = min(cls._index_cache, key=lambda k: cls._index_cache[k][0])
            cls._index_cache.pop(oldest, None)
        cls._index_cache[key] = (time.monotonic(), value)

    def _section_index(self, conn, instrument_id: UUID, *, as_of: date, territory: str | None):
        key = (str(instrument_id), as_of.isoformat(), territory or '')
        if (hit := self._cached(key)) is not None:
            return hit
        inst = self._instrument(conn, instrument_id, as_of)
        if not inst:
            return None
        conn.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                     (as_of.isoformat(), territory or ''))
        rows = conn.execute("""
            SELECT provision_id AS id, path::text AS path, provision_kind AS kind, label, heading, marginal_note,
                   ordinal, first_page, CASE WHEN text_language IN ('ur', 'sd') THEN text_ur ELSE text_en END AS text,
                   survives_repeal
              FROM operative_provision WHERE instrument_id = %s ORDER BY ordinal, path
        """, (instrument_id,)).fetchall()
        # structural units (sections whose words are all in sub-sections) carry no version, so they are not in the
        # served rows; their identity comes from the tree, and they are listed when anything under them is served
        tree = {r['path']: r for r in conn.execute("""
            SELECT id, path::text AS path, kind::text AS kind, label, heading, marginal_note, ordinal, first_page
              FROM provision WHERE instrument_id = %s AND is_active
        """, (instrument_id,)).fetchall()}
        served = {r['path']: r for r in rows}
        law = self._law_status(conn, instrument_id)
        # pass 1: the outermost section-level units that have anything served under them
        section_paths = set()
        for path in sorted({p for r in rows for p in self._prefixes(r['path'])} & set(tree),
                           key=lambda p: (tree[p]['ordinal'], p)):
            if tree[path]['kind'] in self.SECTION_KINDS and not any(
                    a in section_paths for a in self._prefixes(path)[:-1]):
                section_paths.add(path)
        # pass 2: each served row's words go to its section, in printed order, until the preview is long enough
        words: dict[str, list[str]] = {}
        for r in rows:
            owner = next((a for a in self._prefixes(r['path']) if a in section_paths), None)
            if owner is None or not (r['text'] or '').strip():
                continue
            bucket = words.setdefault(owner, [])
            if sum(len(w) for w in bucket) >= self.PREVIEW_CHARS:
                continue
            lab = r['label'] if r['path'] != owner and r['kind'] in ('subsection', 'clause') else None
            bucket.append((f'({lab}) ' if lab else '') + ' '.join(r['text'].split()))
        sections, by_path = [], {}
        for path in sorted(section_paths, key=lambda p: (tree[p]['kind'] != 'preamble', tree[p]['ordinal'], p)):
            node = tree[path]
            group = next((tree[a] for a in reversed(self._prefixes(path)[:-1])
                          if a in tree and tree[a]['kind'] in self.CONTAINER_KINDS), None)
            # a chapter's title is its heading, or -- where the parser stored the printed title line as the chapter's
            # own words ('INTRODUCTION', 'OF ABETMENT') -- that short served text
            group_title = None
            if group:
                own = ' '.join((served.get(group['path'], {}).get('text') or '').split())
                group_title = group['heading'] or (own if 0 < len(own) <= 120 else None)
            # a preview only: leading print artefacts ('__', a dash after the heading) are trimmed here; the reader
            # serves the full text unchanged
            preview = re.sub(r'^[\s_–—\-:.]+', '', ' '.join(words.get(path, [])))
            item = dict(id=node['id'], kind=node['kind'], label=node['label'],
                        heading=node['heading'] or node['marginal_note'], ordinal=node['ordinal'],
                        first_page=node['first_page'],
                        preview=preview[:self.PREVIEW_CHARS] + ('…' if len(preview) > self.PREVIEW_CHARS else ''),
                        group=(' '.join(x for x in (group['kind'].title(), group['label'] or '') if x)
                               + (f" — {group_title}" if group_title else '')) if group else None,
                        citation=render_citation(inst['title'], inst['year'], node['kind'], node['label'],
                                                 inst['kind']),
                        survives_repeal=bool(served.get(path, {}).get('survives_repeal')))
            by_path[path] = item
            sections.append(item)
        value = dict(instrument=inst, law=law, sections=sections)
        self._remember(key, value)
        return value

    @staticmethod
    def _prefixes(path: str) -> list[str]:
        parts = path.split('.')
        return ['.'.join(parts[:i]) for i in range(4, len(parts) + 1)]

    def instruments_by_document(self, document_ids: list[int], *, as_of: date):
        """Released instruments of the given documents readable at `as_of` (for editorial collections)."""
        with self.transaction() as conn:
            return conn.execute(f"""
                SELECT {_INSTRUMENT_COLUMNS}, NULL::uuid AS current_instrument_id
                  FROM v_release_instrument i
                  LEFT JOIN v_instrument_historical h ON h.instrument_id = i.id
                 WHERE i.document_id = ANY(%(docs)s) AND {HISTORICAL_GATE}
            """, dict(docs=list(document_ids), as_of=as_of)).fetchall()

    def constitution_family(self, *, documents: list[int], title_pattern: str, constitution_document: int,
                            as_of: date):
        """Released instruments readable at `as_of` that belong to the Constitution's page (nizam/api/collections.py):
        the pinned documents and every title matching `title_pattern`, each with `amends_units` -- how many recorded
        `amends` edges (legal_edge, 0079/0089) run from it into the Constitution's served text."""
        with self.transaction() as conn:
            rows = conn.execute(f"""
                SELECT {_INSTRUMENT_COLUMNS}, NULL::uuid AS current_instrument_id, i.expression_ordinal
                  FROM v_release_instrument i
                  LEFT JOIN v_instrument_historical h ON h.instrument_id = i.id
                 WHERE {HISTORICAL_GATE}
                   AND (i.document_id = ANY(%(docs)s) OR coalesce(i.display_title, i.short_title) ~* %(pattern)s)
            """, dict(docs=list(documents), pattern=title_pattern, as_of=as_of)).fetchall()
            # ids as values, resolved from the rows above: a subquery over the release view here took 20.8 s, the
            # value arrays ~1 s (the reader's VALUES lesson, docs/MOBILE-LIBRARY-PREVIEW.md)
            targets = [r['id'] for r in rows if r['document_id'] == constitution_document]
            counts = {r['src_instrument']: r['count'] for r in conn.execute("""
                SELECT e.src_instrument, count(*)::int AS count FROM legal_edge e
                 WHERE e.kind = 'amends' AND e.dst_instrument = ANY(%s::uuid[]) AND e.src_instrument = ANY(%s::uuid[])
                 GROUP BY 1
            """, (targets, [r['id'] for r in rows])).fetchall()} if targets else {}
        for r in rows:
            r['amends_units'] = counts.get(r['id'], 0)
        return rows

    def neighbours(self, provision_id: UUID, *, as_of: date, territory: str | None = None):
        """The units before and after `provision_id` in its law's section index (printed order, preamble first) at
        `as_of` in `territory`, with its position; None when the unit's law is not released. A unit that is not
        itself listed (a sub-section, a Part) has no neighbours: the reader offers its sub-units instead."""
        with self.transaction() as conn:
            head = conn.execute("SELECT instrument_id FROM provision WHERE id = %s AND is_active",
                                (provision_id,)).fetchone()
            if not head:
                return None
            index = self._section_index(conn, head['instrument_id'], as_of=as_of, territory=territory)
        return neighbours_in(index['sections'], provision_id) if index else None

    def section_index(self, instrument_id: UUID, *, as_of: date, territory: str | None = None):
        with self.transaction() as conn:
            return self._section_index(conn, instrument_id, as_of=as_of, territory=territory)


def neighbours_in(items: list[dict], provision_id) -> dict:
    """`provision_id`'s neighbours in a section index (printed order); no neighbours when it is not listed."""
    at = next((i for i, s in enumerate(items) if str(s['id']) == str(provision_id)), None)
    if at is None:
        return dict(previous=None, next=None, position=None, total=len(items))
    return dict(previous=items[at - 1] if at > 0 else None, next=items[at + 1] if at + 1 < len(items) else None,
                position=at + 1, total=len(items))


_CITE_KIND = {'section': 's.', 'article': 'Art.', 'rule': 'r.', 'regulation': 'reg.', 'schedule': 'Schedule'}


def render_citation(title: str | None, year: int | None, kind: str, label: str | None,
                    instrument_kind: str | None = None) -> str | None:
    """A citation rendered from database fields only (INV-1): '<law title>[, <year>], s. <label>'. The year is added
    only when the stored title does not already print it. Returns None without a title or label -- never guessed.
    A constitution numbers Articles: the segmenter stores its numbered units as `section`, and the instrument's
    stored kind (`constitution`) decides the word (DECISION-LOG D-070)."""
    if not title or not (label or kind == 'preamble'):
        return None
    name = title.strip().rstrip('.')
    if year and str(year) not in name:
        name = f'{name}, {year}'
    if kind == 'preamble':
        return f"{name}, Preamble"
    if kind == 'section' and instrument_kind == 'constitution':
        kind = 'article'
    return f"{name}, {_CITE_KIND.get(kind, kind)} {label}"
