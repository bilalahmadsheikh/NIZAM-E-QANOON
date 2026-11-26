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
OUTER_KINDS = ("schedule", "form", "appendix", "annexure", "preamble", "notification")   # notification: D-115
# where a law runs (nzq.territory) -> whose law can run there; federal law does not reach AJK or GB (0086)
TERRITORY_JURISDICTIONS = {"punjab": ("punjab", "fed"), "sindh": ("sindh", "fed"), "kp": ("kp", "fed"),
                           "balochistan": ("balochistan", "fed"), "ict": ("fed", "ict"),
                           "ajk": ("ajk",), "gb": ("gb",)}


DENSE_OVERFETCH = 3          # chunks read per provision wanted (several chunks of one long provision collapse)
# a scope holding at most this many chunks is scanned exactly (docs/04 §9.1). Its cost depends on the host's cores
# (Postgres scans it in parallel), so a deployment may override it: NIZAM_EXACT_SCAN_CHUNKS. Measured, D-098.
EXACT_SCAN_CHUNKS = int(os.environ.get("NIZAM_EXACT_SCAN_CHUNKS", "120000"))
_ELIGIBLE: dict = {}         # {generation id: {jurisdiction: chunks with a vector}}
# what the reranker reads per unit (docs/04 §5.1): ~400 tokens of the unit's words after its prefix, inside a
# 512-token cross-encoder with the question; a unit's first nodes in printed order carry its rule (D-101)
PASSAGE_CHARS = 1600
PASSAGE_NODES = 40


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
    def __init__(self, cur, filters: Filters, prefer: tuple[str, ...] = ("fed",)):
        """`prefer`: the jurisdictions a bare law title resolves to first, in order. Federal law by default; a High
        Court's judgment linker passes its own territory, then federal (docs/PRECEDENT-MODEL.md §4.1, D-128)."""
        self.cur = cur
        self.filters = filters
        self.prefer = list(prefer)
        j = filters.jurisdictions
        if j is None and filters.territory:
            j = TERRITORY_JURISDICTIONS.get(filters.territory)
        self.juris = list(j) if j else None
        self.last_dense_mode = None
        self._law_aliases: dict[str, tuple[str, tuple[str, ...]]] | None = None

    def law_alias(self, key: str) -> tuple[str, tuple[str, ...]] | None:
        """(title words, jurisdictions) of the law a reviewed alias key names (law_alias, D-134), else None. The
        active rows are read once per session."""
        if self._law_aliases is None:
            self.cur.execute("SELECT alias_key, title_words, jurisdiction FROM law_alias WHERE withdrawn_at IS NULL")
            self._law_aliases = {r[0]: (r[1], (r[2],)) for r in self.cur.fetchall()}
        return self._law_aliases.get(key)

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

    def generation_for(self, info) -> dict | None:
        """the ACTIVE embedding generation whose space this query encoder makes -- same model, commit, pooling and
        query template -- or None. Up to two are active, one per encoder device (0112, D-099): the GPU generation
        (Qwen3-Embedding-8B, its encoder on the GPU host; vectors in chunk_embedding_gpu) and the CPU generation
        (bge-m3, in-process; chunk.embedding). The encoder decides which space is searched, so a query can never be
        compared with another model's passages (docs/03 §3)."""
        self.cur.execute("""SELECT id, model, revision, pooling, query_template, dims, storage, rescore_dims
                              FROM embedding_generation WHERE active ORDER BY id""")
        keys = ("id", "model", "revision", "pooling", "query_template", "dims", "storage", "rescore_dims")
        for r in self.cur.fetchall():
            g = dict(zip(keys, r))
            if (g["model"], g["revision"], g["pooling"], g["query_template"]) == \
                    (info.model, info.revision, info.pooling, info.query_template):
                return g
        return None

    def dense_hits(self, qvec, n: int, gen: dict) -> list[Hit]:
        """nearest chunks to the question in generation `gen`'s space, the best provision per chunk, active, best
        first. `qvec` is the question's unit float vector from that generation's encoder.

        Candidates come by Hamming distance on the stored sign bits (the first gen['dims'] dimensions); the score is
          * 1 - distance/(dims/2): the cosine between the two +-1 sign vectors, or
          * with gen['rescore_dims'] (the GPU generation, 0112): the cosine between the float question and the
            chunk's stored halfvec of the first rescore_dims dimensions -- the Hamming window re-ranked at precision.
        Either is a similarity, higher is better, so unitScore = max + 0.15 x second best treats it like any score.

        docs/04 §9.1's adaptive execution, with the scope applied INSIDE the scan (docs/04 §4.2: chunk.jurisdiction,
        0110, or chunk_embedding_gpu.jurisdiction, 0112):
          * a scope holding few chunks (<= EXACT_SCAN_CHUNKS) is scanned exactly: deterministic recall;
          * otherwise HNSW with hnsw.iterative_scan = strict_order, which keeps walking the graph until the window
            holds that many chunks IN SCOPE; ef_search = the window (pgvector caps it at 1000).
        """
        w = min(1000, n * DENSE_OVERFETCH)
        width, rdims = int(gen["dims"]), gen.get("rescore_dims")
        gpu = gen["storage"] == "chunk_embedding_gpu"
        # sign of each dimension, first first (numpy.packbits order; 0 is not positive -- nizam.inference.to_bits)
        p = dict(q="".join("1" if x > 0 else "0" for x in qvec[:width]), j=self.juris, w=w)
        if gpu:
            src, col, cid, jur = "chunk_embedding_gpu e", "e.bits", "e.chunk_id", "e.jurisdiction"
        else:
            src, col, cid, jur = "chunk e", "e.embedding", "e.id", "e.jurisdiction"
        exact = self.juris is not None and self.eligible_chunks(gen) <= EXACT_SCAN_CHUNKS
        if exact:
            self.last_dense_mode = "exact"
            order = f"bit_count({col} # %(q)s::bit({width})), {cid}"
            where = f"WHERE {jur} = ANY(%(j)s::text[]) AND {col} IS NOT NULL"
        else:
            self.last_dense_mode = "hnsw"
            self.cur.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(max(100, w)),))
            self.cur.execute("SELECT set_config('hnsw.iterative_scan', 'strict_order', true)")
            order = f"{col} <~> %(q)s::bit({width})"
            where = f"WHERE {jur} = ANY(%(j)s::text[])" if self.juris is not None else ""
        if rdims:
            vec = qvec[:rdims] / max(float((qvec[:rdims] ** 2).sum()) ** 0.5, 1e-12)
            p["h"] = "[" + ",".join(f"{float(x):.6g}" for x in vec) + "]"
            score = f"1 - (s.half <=> %(h)s::halfvec({rdims}))"
            half = ", e.half"
        else:
            score = f"1 - s.d / {width / 2.0}"
            half = ""
        # the window first (MATERIALIZED keeps the index scan and its LIMIT together), then each chunk's version
        self.cur.execute(f"""
            WITH s AS MATERIALIZED (
              SELECT {cid} AS chunk_id, bit_count({col} # %(q)s::bit({width}))::float AS d{half}
                FROM {src} {where} ORDER BY {order} LIMIT %(w)s)
            SELECT c.version_id, ({score})::float FROM s JOIN chunk c ON c.id = s.chunk_id""", p)
        rows = self.cur.fetchall()
        if not rows:
            return []
        best: dict = {}
        for vid, sim in rows:                        # the best chunk of each version
            if vid not in best or sim > best[vid]:
                best[vid] = sim
        self.cur.execute("""
            SELECT v.id, p.id::text, p.path::text, p.instrument_id::text FROM provision_version v
              JOIN provision p ON p.id = v.provision_id AND p.is_active
             WHERE v.id = ANY(%s::uuid[])""", (list(best),))
        per: dict = {}
        for vid, pid, path, inst in self.cur.fetchall():
            sim = best[vid]
            if pid not in per or sim > per[pid][0]:
                per[pid] = (sim, path, inst)
        hits = [Hit(pid, path, inst, sim) for pid, (sim, path, inst) in per.items()]
        hits.sort(key=lambda h: (-h.score, h.provision_id))
        return hits[:n]

    def eligible_chunks(self, gen: dict) -> int:
        """chunks with a vector of generation `gen` in the session's jurisdictions (all, when unscoped); counted
        once per generation and process"""
        key = gen["id"]
        if key not in _ELIGIBLE:
            if gen["storage"] == "chunk_embedding_gpu":
                self.cur.execute("""SELECT jurisdiction, count(*) FROM chunk_embedding_gpu
                                     WHERE generation_id = %s GROUP BY 1""", (key,))
            else:
                self.cur.execute("SELECT jurisdiction, count(*) FROM chunk WHERE embedding IS NOT NULL GROUP BY 1")
            _ELIGIBLE[key] = dict(self.cur.fetchall())
        counts = _ELIGIBLE[key]
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
        prefer = self.prefer
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

    def instrument_titles(self, instrument_ids: list[str]) -> dict[str, list[str]]:
        """{instrument id: [short title, display title]}: a printed name is fitted against both (D-149), since a
        display title can drop the acronym the short title prints ('Federal Investigation Agency Act (FIA), 1974')."""
        self.cur.execute("""SELECT id::text, short_title, display_title FROM instrument
                             WHERE id = ANY(%s::uuid[])""", (list(instrument_ids),))
        return {r[0]: [t for t in r[1:] if t] for r in self.cur.fetchall()}

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

    def instrument_jurisdictions(self, instrument_ids: list[str]) -> dict[str, str]:
        """{instrument id: its jurisdiction (fed, punjab, sindh, kp, balochistan, ajk, gb)} -- the gate's place veto
        (D-102: a question with no territory whose best units are provincial laws of two provinces)"""
        if not instrument_ids:
            return {}
        self.cur.execute("SELECT id::text, jurisdiction::text FROM instrument WHERE id = ANY(%s::uuid[])",
                         (list(set(instrument_ids)),))
        return dict(self.cur.fetchall())

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

    def unit_passages(self, cands: list[tuple[str, str]], max_chars: int = PASSAGE_CHARS,
                      max_nodes: int = PASSAGE_NODES) -> dict[str, str]:
        """{unit id: what the reranker reads for it} for [(unit id, version id)] -- the gated candidates (docs/04
        §5.1: the question with the unit's heading, hierarchical prefix and words). The passage is the context prefix
        the unit's first operative version was embedded with (chunk.context_prefix: title | division | unit and
        heading), a newline, then the unit's OPERATIVE nodes in printed order -- read through operative_provision at
        this session's as_of and territory (INV-5), so a repealed or not-yet-commenced sub-section never reaches the
        reranker -- each as 'label heading text', cut at a word boundary after max_chars. A unit whose nodes are all
        unserved yields its prefix alone (the gate already required one operative node, so this is rare)."""
        if not cands:
            return {}
        uids = [c[0] for c in cands]
        self.cur.execute("""
            SELECT u.uid::text, c.context_prefix, coalesce(o.instrument_title, '')
              FROM unnest(%s::uuid[], %s::uuid[]) AS u(uid, vid)
              LEFT JOIN chunk c ON c.version_id = u.vid AND c.seq = 0
              LEFT JOIN LATERAL (SELECT op.instrument_title FROM operative_provision op
                                  WHERE op.version_id = u.vid LIMIT 1) o ON true""",
                         (uids, [c[1] for c in cands]))
        prefix = {uid: (pfx or title) for uid, pfx, title in self.cur.fetchall()}
        self.cur.execute("""
            SELECT u.uid::text, n.label, n.heading, n.body
              FROM unnest(%s::uuid[]) WITH ORDINALITY AS u(uid, i)
              JOIN provision p ON p.id = u.uid
              CROSS JOIN LATERAL (
                SELECT o.label, o.heading, coalesce(nullif(o.text_en, ''), o.text_ur, '') AS body, o.ordinal, o.path
                  FROM operative_provision o
                 WHERE o.instrument_id = p.instrument_id AND o.path <@ p.path
                   AND (%s::text[] IS NULL OR o.jurisdiction = ANY(%s::text[]))
                 ORDER BY o.ordinal, o.path LIMIT %s) n
             ORDER BY u.i, n.ordinal, n.path""", (uids, self.juris, self.juris, int(max_nodes)))
        body: dict[str, list[str]] = {uid: [] for uid in uids}
        size = dict.fromkeys(uids, 0)
        for uid, label, heading, text in self.cur.fetchall():
            if size[uid] >= max_chars:
                continue
            line = " ".join(" ".join(x.split()) for x in (label or "", heading or "", text or "") if x and x.strip())
            if not line:
                continue
            body[uid].append(line)
            size[uid] += len(line) + 1
        out = {}
        for uid in uids:
            words = "\n".join(body[uid])
            if len(words) > max_chars:
                cut = words.rfind(" ", 0, max_chars)
                words = words[: cut if cut > max_chars // 2 else max_chars]
            out[uid] = (prefix.get(uid) or "") + "\n" + words
        return out


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
