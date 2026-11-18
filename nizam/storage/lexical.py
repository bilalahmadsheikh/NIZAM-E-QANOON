"""The lexical port (docs/03 §5): ILexicalSearch with two implementations and one contract (D-095).

    A  Bm25LexicalSearch     ParadeDB pg_search 0.25.6, true BM25, stemmed English (ix_provision_version_bm25)
    B  TsRankLexicalSearch   portable: ts_rank_cd(..., 32) over websearch_to_tsquery (ix_provision_version_fts)

docs/03 §5: "No managed Postgres permits pg_search, so the fallback must exist, must work, and must have a measured
quality cost rather than an assumed one." Both implement `search(q, filters, k) -> list[Candidate]`; nothing else
differs, so the hosting decision stays reversible.

Every candidate is read THROUGH operative_provision, as at `filters.as_of` and in `filters.territory` (INV-5;
docs/03 §2A; docs/04: "never baked into the index"). Two steps, measured 18 Nov 2026:
  1. the index's best window of matching version ids, by score (BM25: ~30 ms);
  2. operative_provision asked about exactly those ids (`version_id = ANY(...)`, ~4 ms to execute).
Joining the view to the window in one statement made the planner expand the whole view (957,311 rows, 27 s): its
as-at filter reads a setting the planner cannot estimate. The indexes cover every version -- retired revisions repeat
the same words (12 of the top 80 BM25 matches for 'theft of moveable property' are operative) -- so the window
widens x4 until it yields k operative candidates or the matches run out; a filtered-out version can never crowd out
an operative one. A candidate names a provision and the version that matched (INV-4: no chunk id leaves L2).

Extra surfaces of implementation A for retrieval's field boosts (docs/04 §4.1): `headings` (heading and marginal note,
stemmed) and `labels` (the printed label, space-folded and lowercased: '462I' finds '462 I', D-094). A unit matched
there may have no version of its own (a section whose words are in its sub-sections); it is operative when any node
of its subtree is, and the candidate's version is that subtree's first operative node.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from nizam.storage.db import connect

MAX_WINDOW = 65536
SUBTREE_HEAD = 12      # nodes read per matched unit to find its first operative one (a repealed run longer than this
                       # at the head of a unit leaves the unit out of a heading result; its body still matches)


@dataclass(frozen=True)
class Filters:
    as_of: date                                    # INV-5: mandatory
    territory: str | None = None                   # operative_provision's nzq.territory
    jurisdictions: tuple[str, ...] | None = None   # stored values: fed, punjab, sindh, kp, balochistan, ajk, gb


@dataclass(frozen=True)
class Candidate:
    provision_id: str
    version_id: str
    instrument_id: str
    score: float
    rank: int


class Candidates(list):
    """A list of Candidate. `truncated` is True when the window reached MAX_WINDOW before yielding k operative
    candidates, so "no more matches" and "capped" are told apart in a replay (INV-3; review 18 Nov 2026)."""
    truncated: bool = False


class LexicalSearch(Protocol):
    name: str

    def search(self, q: str, filters: Filters, k: int) -> list[Candidate]: ...


def _check(filters: Filters, q: str, k: int) -> str | None:
    # a datetime is a date too; its time would ride into nzq.as_of (review 18 Nov 2026)
    if type(filters.as_of) is not date:
        raise ValueError("as_of is mandatory (INV-5) and is a date, not a datetime")
    q = " ".join((q or "").split())
    return q if q and k > 0 else None


def _as_of(cur, filters: Filters) -> None:
    cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                (filters.as_of.isoformat(), filters.territory or ""))


class _VersionWindow:
    """search() over a body index: MATCHES selects (version id, score) ordered by score, LIMIT %(n)s."""
    name = "?"
    MATCHES = ""

    def __init__(self, connect_fn=connect):
        self._connect = connect_fn

    def search(self, q: str, filters: Filters, k: int) -> list[Candidate]:
        q = _check(filters, q, k)
        if q is None:
            return Candidates()
        juris = list(filters.jurisdictions) if filters.jurisdictions else None
        n = max(k * 20, 400)      # ~85% of top matches are retired repeats of operative text (18 Nov 2026)
        with self._connect() as conn, conn.cursor() as cur:
            _as_of(cur, filters)
            while True:
                cur.execute(self.MATCHES, dict(q=q, n=n))
                window = cur.fetchall()                      # [(version_id, score)] best first
                cur.execute("""SELECT o.version_id::text, o.provision_id::text, o.instrument_id::text
                                 FROM operative_provision o
                                WHERE o.version_id = ANY(%s::uuid[])
                                  AND (%s::text[] IS NULL OR o.jurisdiction = ANY(%s::text[]))""",
                            ([str(v) for v, _s in window], juris, juris))
                live = {v: (p, i) for v, p, i in cur.fetchall()}
                hits = [(str(v), s) for v, s in window if str(v) in live]
                if len(hits) >= k or len(window) < n or n >= MAX_WINDOW:
                    break
                n *= 4
            conn.rollback()
        out = Candidates(Candidate(live[v][0], v, live[v][1], float(s), r) for r, (v, s) in enumerate(hits[:k], 1))
        out.truncated = len(hits) < k and len(window) >= n
        return out


class Bm25LexicalSearch(_VersionWindow):
    """Implementation A: ParadeDB BM25 (length-normalised, term-saturating), match-any, stemmed English."""
    name = "bm25"
    MATCHES = """SELECT v.id, pdb.score(v.id) AS s FROM provision_version v
                  WHERE v.text_normalised ||| %(q)s ORDER BY s DESC, v.id LIMIT %(n)s"""

    def headings(self, q: str, filters: Filters, k: int) -> list[Candidate]:
        """Units whose printed heading or marginal note matches (stemmed), operative as at the date."""
        return self._units("""SELECT p.id, p.path::text, p.instrument_id, pdb.score(p.id) AS s FROM provision p
                               WHERE (p.heading ||| %(q)s OR p.marginal_note ||| %(q)s) AND p.is_active
                               ORDER BY s DESC, p.id LIMIT %(n)s""", q, filters, k)

    def labels(self, label: str, filters: Filters, k: int = 50,
               instruments: tuple[str, ...] | None = None) -> list[Candidate]:
        """Units printed with this label ('302', '337A', '462I' == '462 I'), operative as at the date.

        An identity match, not a relevance one: every hit scores 1.0 and they come in instrument, then printed, order.
        A bare label ('1', '302') is printed in thousands of laws -- the caller names the law (`instruments`, as the
        citation fast path does once it has resolved one) or ranks the result itself."""
        folded = "".join((label or "").split()).lower()
        only = list(instruments) if instruments else None
        return self._units("""SELECT p.id, p.path::text, p.instrument_id, 1.0::real AS s FROM provision p
                               WHERE replace(p.label, ' ', '') === %(q)s AND p.is_active
                                 AND (%(only)s::uuid[] IS NULL OR p.instrument_id = ANY(%(only)s::uuid[]))
                               ORDER BY p.instrument_id, p.ordinal, p.id LIMIT %(n)s""", folded, filters, k,
                           extra=dict(only=only))

    def _units(self, matches: str, q: str, filters: Filters, k: int, extra: dict | None = None) -> list[Candidate]:
        q = _check(filters, q, k)
        if q is None:
            return Candidates()
        juris = list(filters.jurisdictions) if filters.jurisdictions else None
        n = max(k * 2, 100)       # unit matches are filtered to active provisions; most are operative
        with self._connect() as conn, conn.cursor() as cur:
            _as_of(cur, filters)
            while True:
                cur.execute(matches, dict(extra or {}, q=q, n=n))
                window = cur.fetchall()                      # [(provision id, path, instrument id, score)]
                # each matched unit's first SUBTREE_HEAD NODES in printed order, then their versions: the cap is on
                # nodes, so a much-amended node cannot fill it with its own versions (review 18 Nov 2026), and the
                # first operative one is the candidate's version; a Part heading never expands its whole subtree
                cur.execute("""SELECT u.pid::text, pv.id::text, s.ordinal, s.path::text
                                 FROM unnest(%s::uuid[], %s::ltree[], %s::uuid[]) AS u(pid, path, inst)
                                 CROSS JOIN LATERAL (
                                   SELECT d.id, d.ordinal, d.path FROM provision d
                                    WHERE d.instrument_id = u.inst AND d.path <@ u.path AND d.is_active
                                    ORDER BY d.ordinal, d.path LIMIT %s) s
                                 JOIN provision_version pv ON pv.provision_id = s.id
                                ORDER BY u.pid, s.ordinal, s.path, pv.id""",
                            ([str(w[0]) for w in window], [w[1] for w in window], [str(w[2]) for w in window],
                             int(SUBTREE_HEAD)))
                subtree = cur.fetchall()
                # ... then operative_provision asked about exactly those versions (the fast path; see the module)
                cur.execute("""SELECT o.version_id::text FROM operative_provision o
                                WHERE o.version_id = ANY(%s::uuid[])
                                  AND (%s::text[] IS NULL OR o.jurisdiction = ANY(%s::text[]))""",
                            (list({r[1] for r in subtree}), juris, juris))
                operative = {r[0] for r in cur.fetchall()}
                live: dict[str, str] = {}
                for pid, vid, _ordinal, _path in sorted((r for r in subtree if r[1] in operative),
                                                        key=lambda r: (r[0], r[2], r[3])):
                    live.setdefault(pid, vid)            # the subtree's first operative node, in printed order
                hits = [(str(p), str(i), s) for p, _path, i, s in window if str(p) in live]
                if len(hits) >= k or len(window) < n or n >= MAX_WINDOW:
                    break
                n *= 4
            conn.rollback()
        out = Candidates(Candidate(p, live[p], i, float(s), r) for r, (p, i, s) in enumerate(hits[:k], 1))
        out.truncated = len(hits) < k and len(window) >= n
        return out


class TsRankLexicalSearch(_VersionWindow):
    """Implementation B (docs/03 §5): ts_rank_cd with normalisation 32 over websearch_to_tsquery -- portable to any
    managed Postgres; an approximation of length normalisation, no term saturation, and the tsvector is computed per
    matched row (the expression is indexed, never stored), so its cost grows with the number of matches."""
    name = "ts_rank_cd"
    MATCHES = """SELECT v.id, ts_rank_cd(to_tsvector('english', v.text_normalised),
                                        websearch_to_tsquery('english', %(q)s), 32) AS s
                   FROM provision_version v
                  WHERE to_tsvector('english', v.text_normalised) @@ websearch_to_tsquery('english', %(q)s)
                  ORDER BY s DESC, v.id LIMIT %(n)s"""


class TsRankAnyLexicalSearch(_VersionWindow):
    """Implementation B', portable: B's ts_rank_cd(..., 32), but ANY term may match (the same English parse,
    plainto_tsquery, with its '&' turned into '|'), like BM25's match-any. Measured 18 Nov 2026 on golden sets 1-4:
    B as docs/03 §5 writes it (websearch_to_tsquery, every term required) returned nothing for 159 of 180 natural-
    language questions; a portable fallback has to accept a question as people type it (D-095)."""
    name = "ts_rank_cd_any"
    # cast, never re-parse: plainto_tsquery's lexemes are already stemmed, and to_tsquery would stem them again
    # ('provis' -> 'provi', 'purpos' -> 'purpo': 700 of 9,111 sampled lexemes), silently dropping those terms
    MATCHES = """WITH q AS (SELECT replace(plainto_tsquery('english', %(q)s)::text, ' & ', ' | ')::tsquery AS tq)
                 SELECT v.id, ts_rank_cd(to_tsvector('english', v.text_normalised), q.tq, 32) AS s
                   FROM provision_version v, q
                  WHERE to_tsvector('english', v.text_normalised) @@ q.tq
                  ORDER BY s DESC, v.id LIMIT %(n)s"""
