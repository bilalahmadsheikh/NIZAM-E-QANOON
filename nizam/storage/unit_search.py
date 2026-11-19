"""Storage reads for L3's fused lexical search (D-097): windows, unit mapping, the operative check -- one session.

L3 (nizam.retrieval) fuses ranked lists of LEGAL UNITS (docs/04 §5). These are the L2 reads it needs, on ONE
connection with as-at and territory set once (INV-5):

  body_hits      BM25 over provision text (ix_provision_version_bm25)
  heading_hits   BM25 over headings and marginal notes (ix_provision_bm25)
  title_hits     BM25 over instrument titles (ix_instrument_bm25)
  dense_hits     Hamming nearest chunks to the question's sign bits (ix_chunk_hnsw, or exact for a small scope), D-098
  label_units    a printed label in named instruments (space-folded literal: '462I' finds '462 I')
  child_by_label descend from a unit by printed labels ('302' -> '(b)')
  units_of       each provision's legal unit: its innermost section/article/order, else its outermost schedule,
                 form, appendix, annexure or preamble
  operative_units  THE INV-5 GATE: each unit's first operative node in printed order, read through
                 operative_provision as at the session's date and in its territory; a unit without one is dropped

Windows are CHEAP pre-filters, never a substitute for the gate: active provisions only, in the session's
jurisdictions. Measured 18 Nov 2026 (D-097): BM25's top 2,000 in ~210 ms, the base-table pre-filter in ~240 ms, while
asking the view about the same 2,000 ids took 1.3 s. So L3 fuses on the cheap windows and passes only its top units
through `operative_units`, refilling until it has k -- the order among operative units is the same as if the view had
filtered first, because filtering never reorders.

Nothing here returns text: identifiers and scores only (INV-1, INV-4).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

from nizam.storage.db import connect
from nizam.storage.lexical import SUBTREE_HEAD, Filters

UNIT_KINDS = ("section", "article", "order")
OUTER_KINDS = ("schedule", "form", "appendix", "annexure", "preamble")
# where a law runs (nzq.territory) -> whose law can run there; federal law does not reach AJK or GB (0086)
TERRITORY_JURISDICTIONS = {"punjab": ("punjab", "fed"), "sindh": ("sindh", "fed"), "kp": ("kp", "fed"),
                           "balochistan": ("balochistan", "fed"), "ict": ("fed", "ict"),
                           "ajk": ("ajk",), "gb": ("gb",)}


DENSE_OVERFETCH = 3          # chunks read per provision wanted (several chunks of one long provision collapse)
# a scope holding at most this many chunks is scanned exactly (docs/04 §9.1). Its cost depends on the host's cores
# (Postgres scans it in parallel), so a deployment may override it: NIZAM_EXACT_SCAN_CHUNKS. Measured, D-098.
EXACT_SCAN_CHUNKS = int(os.environ.get("NIZAM_EXACT_SCAN_CHUNKS", "120000"))
_ELIGIBLE: dict = {}         # {generation: id, counts: {jurisdiction: chunks with a vector}}


@dataclass(frozen=True)
class Hit:
    provision_id: str
    path: str
    instrument_id: str
    score: float


@dataclass(frozen=True)
class Unit:
    unit_id: str
    path: str
    instrument_id: str


class Session:
    def __init__(self, cur, filters: Filters):
        self.cur = cur
        self.filters = filters
        j = filters.jurisdictions
        if j is None and filters.territory:
            j = TERRITORY_JURISDICTIONS.get(filters.territory)
        self.juris = list(j) if j else None
        self.last_dense_mode = None

    # --- windows (cheap pre-filters: active, in jurisdiction; NOT operative-checked) ----------------------------
    def body_hits(self, q: str, n: int) -> list[Hit]:
        """best-scoring provision per matched version, active and in jurisdiction, best first"""
        self.cur.execute("""
            WITH w AS (SELECT v.id, v.provision_id, pdb.score(v.id) AS s FROM provision_version v
                        WHERE v.text_normalised ||| %(q)s ORDER BY s DESC, v.id LIMIT %(w)s)
            SELECT p.id::text, p.path::text, p.instrument_id::text, max(w.s) AS s
              FROM w JOIN provision p ON p.id = w.provision_id AND p.is_active
             WHERE (%(j)s::text[] IS NULL OR subltree(p.path, 0, 1)::text = ANY(%(j)s::text[]))
             GROUP BY 1, 2, 3 ORDER BY s DESC, 1 LIMIT %(n)s""", dict(q=q, w=n * 6, n=n, j=self.juris))
        return [Hit(*r) for r in self.cur.fetchall()]

    def heading_hits(self, q: str, n: int) -> list[Hit]:
        self.cur.execute("""
            SELECT p.id::text, p.path::text, p.instrument_id::text, pdb.score(p.id) AS s FROM provision p
             WHERE (p.heading ||| %(q)s OR p.marginal_note ||| %(q)s) AND p.is_active
               AND (%(j)s::text[] IS NULL OR subltree(p.path, 0, 1)::text = ANY(%(j)s::text[]))
             ORDER BY s DESC, p.id LIMIT %(n)s""", dict(q=q, n=n, j=self.juris))
        return [Hit(*r) for r in self.cur.fetchall()]

    def title_hits(self, q: str, n: int) -> list[tuple[str, float]]:
        """[(instrument id, score)] of active, non-duplicate instruments whose title matches, best first"""
        self.cur.execute("""
            SELECT i.id::text, pdb.score(i.id) AS s FROM instrument i
             WHERE (i.short_title ||| %(q)s OR i.display_title ||| %(q)s OR i.long_title ||| %(q)s)
               AND i.is_active AND i.duplicate_of IS NULL
               AND (%(j)s::text[] IS NULL OR i.jurisdiction::text = ANY(%(j)s::text[]))
             ORDER BY s DESC, i.id LIMIT %(n)s""", dict(q=q, n=n, j=self.juris))
        return [(r[0], float(r[1])) for r in self.cur.fetchall()]

    def active_generation(self) -> dict | None:
        """the active embedding_generation (0109): the model a query must be encoded by, or None"""
        self.cur.execute("""SELECT id, model, revision, pooling, query_template FROM embedding_generation
                             WHERE active""")
        r = self.cur.fetchone()
        return dict(zip(("id", "model", "revision", "pooling", "query_template"), r)) if r else None

    def dense_hits(self, qbits: str, n: int) -> list[Hit]:
        """nearest chunks by Hamming distance to the question's sign bits, the best provision per chunk, active, best
        first; score = 1 - distance/512, the cosine between the two +-1 sign vectors (a similarity, higher is better,
        so retrieval's unitScore = max + 0.15 x second best treats it like any other score). docs/04 §9.1's adaptive
        execution, on chunk.jurisdiction (0110) so the scope is
        applied INSIDE the scan, never after it (docs/04 §4.2):
          * a scope holding few chunks (<= EXACT_SCAN_CHUNKS) is scanned exactly: every chunk in scope, distance
            computed, deterministic recall;
          * otherwise HNSW (ix_chunk_hnsw, 0111) with hnsw.iterative_scan = strict_order, which keeps walking the
            graph until the window holds that many chunks IN SCOPE; ef_search = the window (pgvector caps it at 1000).
        """
        w = min(1000, n * DENSE_OVERFETCH)
        eligible = self.eligible_chunks()
        if self.juris is not None and eligible <= EXACT_SCAN_CHUNKS:
            self.last_dense_mode = "exact"
            self.cur.execute("""
                SELECT c.version_id, bit_count(c.embedding # %(q)s::bit(1024))::float AS d FROM chunk c
                 WHERE c.jurisdiction = ANY(%(j)s::text[]) AND c.embedding IS NOT NULL
                 ORDER BY d, c.id LIMIT %(w)s""", dict(q=qbits, j=self.juris, w=w))
        else:
            self.last_dense_mode = "hnsw"
            self.cur.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(max(100, w)),))
            self.cur.execute("SELECT set_config('hnsw.iterative_scan', 'strict_order', true)")
            scope = "WHERE c.jurisdiction = ANY(%(j)s::text[])" if self.juris is not None else ""
            self.cur.execute(f"""
                SELECT c.version_id, (c.embedding <~> %(q)s::bit(1024))::float AS d FROM chunk c {scope}
                 ORDER BY c.embedding <~> %(q)s::bit(1024) LIMIT %(w)s""", dict(q=qbits, j=self.juris, w=w))
        rows = self.cur.fetchall()
        if not rows:
            return []
        best: dict = {}
        for vid, d in rows:                          # the nearest chunk of each version
            if vid not in best or d < best[vid]:
                best[vid] = d
        self.cur.execute("""
            SELECT v.id, p.id::text, p.path::text, p.instrument_id::text FROM provision_version v
              JOIN provision p ON p.id = v.provision_id AND p.is_active
             WHERE v.id = ANY(%s::uuid[])""", (list(best),))
        per: dict = {}
        for vid, pid, path, inst in self.cur.fetchall():
            d = best[vid]
            if pid not in per or d < per[pid][0]:
                per[pid] = (d, path, inst)
        hits = [Hit(pid, path, inst, 1.0 - d / 512.0) for pid, (d, path, inst) in per.items()]
        hits.sort(key=lambda h: (-h.score, h.provision_id))
        return hits[:n]

    def eligible_chunks(self) -> int:
        """chunks with a vector in the session's jurisdictions (all, when unscoped); counted once per embedding
        generation and process, from ix_chunk_jurisdiction"""
        gen = self.active_generation()
        key = (gen or {}).get("id")
        if _ELIGIBLE.get("generation") != key:
            self.cur.execute("SELECT jurisdiction, count(*) FROM chunk WHERE embedding IS NOT NULL GROUP BY 1")
            _ELIGIBLE.clear()
            _ELIGIBLE.update(generation=key, counts=dict(self.cur.fetchall()))
        counts = _ELIGIBLE["counts"]
        return sum(counts.values()) if self.juris is None else sum(counts.get(j, 0) for j in self.juris)

    def instruments_titled(self, words: str, n: int = 10,
                           jurisdictions: tuple[str, ...] | None = None) -> list[tuple[str, str, int]]:
        """[(instrument id, title, laws citing it)] whose title holds ALL of `words` (stemmed), in `jurisdictions`
        (else the session's), most relied-on first (law_citation_count, D-075) -- how a citation's named law is
        resolved. The caller decides what an amending Act's title means; nothing is dropped here."""
        j = list(jurisdictions) if jurisdictions else self.juris
        # preference: a SERVED law (the copy the corpus answers from) before an unserved copy; then federal law
        # before a territory's law of the same title (provincial codes reprint federal Acts under their titles:
        # Contract Act 1872, MFLO 1961); then reliance. A title that NAMES its province is that province's only, so
        # it never meets a federal twin; the caller adds same-title territorial copies as alternates (D-097).
        prefer = ["fed"]
        self.cur.execute("""
            SELECT i.id::text, coalesce(nullif(i.display_title, ''), i.short_title),
                   coalesce(c.cited_by_laws, 0) AS rely
              FROM instrument i
              LEFT JOIN law_citation_count c ON c.document_id = i.document_id
                                            AND c.expression_ordinal = i.expression_ordinal
             WHERE (i.short_title &&& %(q)s OR i.display_title &&& %(q)s)
               AND i.is_active AND i.duplicate_of IS NULL
               AND (%(j)s::text[] IS NULL OR i.jurisdiction::text = ANY(%(j)s::text[]))
             ORDER BY EXISTS (SELECT 1 FROM mv_instrument_serving m WHERE m.instrument_id = i.id) DESC,
                      coalesce(array_position(%(prefer)s::text[], i.jurisdiction::text), 99),
                      rely DESC, pdb.score(i.id) DESC, i.id
             LIMIT %(n)s""", dict(q=words, n=n, j=j, prefer=prefer))
        return [(r[0], r[1], int(r[2])) for r in self.cur.fetchall()]

    def label_units(self, label: str, instrument_ids: list[str]) -> list[Unit]:
        folded = "".join((label or "").split()).lower()
        self.cur.execute("""
            SELECT p.id::text, p.path::text, p.instrument_id::text FROM provision p
             WHERE replace(p.label, ' ', '') === %s AND p.is_active AND p.instrument_id = ANY(%s::uuid[])
               AND p.kind::text = ANY(%s)
             ORDER BY array_position(%s::uuid[], p.instrument_id), p.ordinal, p.id""",
                         (folded, instrument_ids, list(UNIT_KINDS), instrument_ids))
        return [Unit(*r) for r in self.cur.fetchall()]

    def child_by_label(self, unit: Unit, labels: list[str]) -> Unit:
        """descend by printed labels ('1' then 'b' for s.302(1)(b)); stops at the deepest label found"""
        cur_unit = unit
        for lab in labels:
            self.cur.execute("""
                SELECT c.id::text, c.path::text, c.instrument_id::text FROM provision p
                  JOIN provision c ON c.parent_id = p.id AND c.is_active
                 WHERE p.id = %s AND lower(replace(c.label, ' ', '')) = lower(%s)
                 ORDER BY c.ordinal LIMIT 1""", (cur_unit.unit_id, lab))
            row = self.cur.fetchone()
            if row is None:
                break
            cur_unit = Unit(*row)
        return cur_unit

    def units_of(self, provision_ids: list[str]) -> dict[str, Unit]:
        if not provision_ids:
            return {}
        self.cur.execute("""
            SELECT c.id::text,
                   coalesce(
                     (SELECT a.id::text || '|' || a.path::text FROM provision a
                       WHERE a.instrument_id = c.instrument_id AND a.path @> c.path AND a.kind::text = ANY(%s)
                       ORDER BY nlevel(a.path) DESC LIMIT 1),
                     (SELECT a.id::text || '|' || a.path::text FROM provision a
                       WHERE a.instrument_id = c.instrument_id AND a.path @> c.path AND a.kind::text = ANY(%s)
                       ORDER BY nlevel(a.path) LIMIT 1),
                     c.id::text || '|' || c.path::text),
                   c.instrument_id::text
              FROM provision c WHERE c.id = ANY(%s::uuid[])""",
                         (list(UNIT_KINDS), list(OUTER_KINDS), provision_ids))
        out = {}
        for pid, v, inst in self.cur.fetchall():
            uid, upath = v.split("|", 1)
            out[pid] = Unit(uid, upath, inst)
        return out

    # --- THE INV-5 GATE ---------------------------------------------------------------------------------------
    def operative_units(self, units: list[Unit]) -> dict[str, str]:
        """{unit id: version id of its first operative node, in printed order}; units with none are absent"""
        if not units:
            return {}
        self.cur.execute("""
            SELECT u.uid::text, pv.id::text, s.ordinal, s.path::text
              FROM unnest(%s::uuid[], %s::ltree[], %s::uuid[]) AS u(uid, path, inst)
              CROSS JOIN LATERAL (
                SELECT d.id, d.ordinal, d.path FROM provision d
                 WHERE d.instrument_id = u.inst AND d.path <@ u.path AND d.is_active
                 ORDER BY d.ordinal, d.path LIMIT %s) s
              JOIN provision_version pv ON pv.provision_id = s.id
             ORDER BY u.uid, s.ordinal, s.path, pv.id""",
                         ([u.unit_id for u in units], [u.path for u in units], [u.instrument_id for u in units],
                          int(SUBTREE_HEAD)))
        subtree = self.cur.fetchall()
        if not subtree:
            return {}
        self.cur.execute("""SELECT o.version_id::text FROM operative_provision o
                             WHERE o.version_id = ANY(%s::uuid[])
                               AND (%s::text[] IS NULL OR o.jurisdiction = ANY(%s::text[]))""",
                         (list({r[1] for r in subtree}), self.juris, self.juris))
        operative = {r[0] for r in self.cur.fetchall()}
        live: dict[str, str] = {}
        for uid, vid, _o, _p in subtree:
            if vid in operative:
                live.setdefault(uid, vid)
        return live


@contextmanager
def session(filters: Filters, connect_fn=connect):
    """one read-only transaction with nzq.as_of and nzq.territory set (INV-5); rolled back on exit"""
    if type(filters.as_of) is not date:
        raise ValueError("as_of is mandatory (INV-5) and is a date, not a datetime")
    with connect_fn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL client_min_messages = error")      # pg_search planner notices are not errors
        # pg_search 0.25.6 under a GENERIC plan drops its match filter: psycopg prepares a statement after 5 runs and
        # Postgres goes generic after 5 more, so from the 11th run on one connection a title matching nothing
        # returned 5 arbitrary rows (reproduced 18 Nov 2026, D-097). Custom plans only, wherever pg_search is read.
        cur.execute("SET LOCAL plan_cache_mode = force_custom_plan")
        cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                    (filters.as_of.isoformat(), filters.territory or ""))
        try:
            yield Session(cur, filters)
        finally:
            conn.rollback()
