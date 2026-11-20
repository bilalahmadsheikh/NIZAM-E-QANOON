"""L2 reads for L3's evidence assembly (docs/04 §7): whole units, the ancestors of a node, the sections of a Part or
Chapter, the derived links (provision_reference and provision_definition, D-108), printed amendment notes, the
instruments a section empowers, and each law's facts and source.

Text and law facts come ONLY from operative_provision, as at the session's date and in its territory (INV-5). The
view is asked about version ids and nothing else. Structure (ids, paths, labels, pages, order) comes from the base
tables, where it is a cheap pre-filter, never a substitute for the view: a node the view does not return is not law
at that date and is left out. This is the pattern of nizam.storage.lexical and unit_search (D-095, D-097).

Measured 20 Nov 2026 (D-107), 10 sections of the Income Tax Ordinance 2001 (59 versions):
  * the view by version ids: 7 ms under a generic plan, 35 ms under a custom one. The planner prices each array
    element at plan time, so a custom plan's cost grows with the list (108 ms planning for 200 ids);
  * the view joined per unit by instrument and path (LATERAL): 20 s. That is the "join trap"; never do it here.
So this session plans generically. It reads no pg_search index, so the custom-plan rule of unit_search.session
(pg_search drops its match filter under a generic plan, D-097) does not apply.

Nothing here decides what is relevant: L3 (nizam.retrieval.assembly) chooses. The links are built from the release
by nizam.workers.links; operative status of whatever they point at is asked here, at the reader's as_of.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date

from nizam.storage.db import connect
from nizam.storage.lexical import Filters
from nizam.storage.unit_search import OUTER_KINDS, TERRITORY_JURISDICTIONS, UNIT_KINDS

DIVISION_KINDS = ("part", "chapter")
_GENERAL_CLAUSES: dict[str, str] = {}     # {jurisdiction: General Clauses Act id}, read once per process
_DELEGATIONS: dict = {}                   # the empowers records, read once per process (they change with a release)


@dataclass(frozen=True)
class Node:
    """one operative node, as the view gives it at the session's date and place"""
    provision_id: str
    version_id: str
    path: str
    kind: str
    label: str
    heading: str | None
    marginal_note: str | None
    text: str
    language: str | None
    first_page: int | None
    last_page: int | None
    ordinal: int


@dataclass(frozen=True)
class Ancestor:
    provision_id: str
    path: str
    kind: str
    label: str
    heading: str | None
    depth: int


@dataclass(frozen=True)
class LawFacts:
    """what operative_provision says of a law, at the session's date and territory"""
    instrument_id: str
    title: str
    kind: str
    number: str | None
    year: int | None
    jurisdiction: str
    status: str | None
    currency: str | None
    currency_reason: str | None
    enacted_on: date | None
    commenced_on: date | None
    text_known_from: date | None
    text_known_from_basis: str | None
    commencement_coverage: str | None
    extent_coverage: str | None
    invalidation_coverage: str | None
    source_url: str | None
    document_id: int | None
    source_sha256: str | None = None


@dataclass(frozen=True)
class Unit:
    unit_id: str
    instrument_id: str
    path: str
    kind: str
    label: str
    heading: str | None
    marginal_note: str | None
    ordinal: int
    nodes: tuple            # Node, operative only, printed order; the unit's own node first when it has words


@dataclass(frozen=True)
class AmendmentNote:
    provision_id: str
    printed: str             # the footnote as printed, whitespace folded
    operations: tuple
    effective_from: date | None
    amending_instrument_id: str | None


@dataclass(frozen=True)
class Delegated:
    enabling_provision_id: str
    instrument_id: str
    title: str
    kind: str
    year: int | None


class EvidenceSession:
    def __init__(self, cur, filters: Filters):
        self.cur = cur
        self.filters = filters
        j = filters.jurisdictions
        if j is None and filters.territory:
            j = TERRITORY_JURISDICTIONS.get(filters.territory)
        self.juris = list(j) if j else None
        self._facts: dict[str, LawFacts] = {}

    # --- the view, by version ids only ------------------------------------------------------------------------
    def _operative(self, version_ids) -> dict[str, dict]:
        """{version id: its operative row} for those of `version_ids` that are law at the session's date and place"""
        ids = list({v for v in version_ids if v})
        if not ids:
            return {}
        self.cur.execute("""
            SELECT o.version_id::text, o.heading, o.marginal_note,
                   coalesce(nullif(o.text_en, ''), o.text_ur, '') AS body, o.text_language, o.first_page,
                   o.instrument_id::text, o.instrument_title, o.instrument_kind, o.instrument_number,
                   o.instrument_year, o.jurisdiction, o.instrument_status, o.currency, o.currency_reason,
                   o.enacted_on, o.commenced_on, o.text_known_from, o.text_known_from_basis,
                   o.commencement_coverage, o.extent_coverage, o.invalidation_coverage, o.source_url, o.document_id
              FROM operative_provision o
             WHERE o.version_id = ANY(%s::uuid[])
               AND (%s::text[] IS NULL OR o.jurisdiction = ANY(%s::text[]))""", (ids, self.juris, self.juris))
        cols = [d[0] for d in self.cur.description]
        out = {}
        for r in self.cur.fetchall():
            row = dict(zip(cols, r))
            out[row["version_id"]] = row
            iid = row["instrument_id"]
            if iid not in self._facts:
                self._facts[iid] = LawFacts(
                    iid, row["instrument_title"], row["instrument_kind"], row["instrument_number"],
                    row["instrument_year"], row["jurisdiction"], row["instrument_status"], row["currency"],
                    row["currency_reason"], row["enacted_on"], row["commenced_on"], row["text_known_from"],
                    row["text_known_from_basis"], row["commencement_coverage"], row["extent_coverage"],
                    row["invalidation_coverage"], row["source_url"], row["document_id"])
        return out

    def _nodes(self, rows, live) -> list[tuple[str, Node]]:
        """[(group key, Node)] for structure rows (key, id, path, kind, label, first_page, last_page, ordinal, vid)
        whose version the view returned"""
        out = []
        for key, pid, path, kind, label, fp, lp, ordinal, vid in rows:
            o = live.get(vid)
            if o is not None:
                out.append((key, Node(pid, vid, path, kind, label, o["heading"], o["marginal_note"], o["body"] or "",
                                      o["text_language"], o["first_page"] or fp, lp, ordinal)))
        return out

    def facts(self, instrument_ids) -> dict[str, LawFacts]:
        """facts of the laws already read through the view in this session, with the source file's sha256 added
        from the instrument record (identity, not law)"""
        ids = [i for i in set(instrument_ids) if i in self._facts]
        missing = [i for i in ids if self._facts[i].source_sha256 is None]
        if missing:
            self.cur.execute("SELECT id::text, source_sha256 FROM instrument WHERE id = ANY(%s::uuid[])", (missing,))
            for iid, sha in self.cur.fetchall():
                self._facts[iid] = replace(self._facts[iid], source_sha256=(sha or "").strip() or None)
        return {i: self._facts[i] for i in ids}

    # --- whole units and subtrees -----------------------------------------------------------------------------
    def _subtree_rows(self, provision_ids):
        # measured 21 Nov 2026 (D-108): this form, the provision_ancestor closure and a LATERAL all take 14-18 ms for
        # a 605-row bundle; the cost is fetching the rows, not the plan
        self.cur.execute("""
            SELECT u.id::text, d.id::text, d.path::text, d.kind::text, d.label, d.first_page, d.last_page,
                   d.ordinal, pv.id::text
              FROM provision u
              JOIN provision d ON d.instrument_id = u.instrument_id AND d.path <@ u.path AND d.is_active
              JOIN provision_version pv ON pv.provision_id = d.id
             WHERE u.id = ANY(%s::uuid[]) AND u.is_active
             ORDER BY u.id, d.ordinal, d.path, pv.id""", (list(set(provision_ids)),))
        return self.cur.fetchall()

    def units(self, unit_ids) -> dict[str, Unit]:
        """{unit id: the unit with every operative node of its subtree, printed order}. A unit with no operative
        node is absent: it is not law at the session's date and place."""
        if not unit_ids:
            return {}
        rows = self._subtree_rows(unit_ids)
        nodes: dict[str, list[Node]] = {}
        for uid, node in self._nodes(rows, self._operative(r[8] for r in rows)):
            nodes.setdefault(uid, []).append(node)
        if not nodes:
            return {}
        self.cur.execute("""SELECT id::text, instrument_id::text, path::text, kind::text, label, heading,
                                   marginal_note, ordinal FROM provision WHERE id = ANY(%s::uuid[])""",
                         (list(nodes),))
        return {r[0]: Unit(*r, tuple(nodes[r[0]])) for r in self.cur.fetchall()}

    def subtrees(self, provision_ids) -> dict[str, tuple]:
        """{provision id: (Node, ...)}: a node and its operative descendants, printed order -- a definition whose
        words continue in sub-clauses ('"employer" means-- (i) ... (ii) ...')"""
        if not provision_ids:
            return {}
        rows = self._subtree_rows(provision_ids)
        out: dict[str, list] = {}
        for pid, node in self._nodes(rows, self._operative(r[8] for r in rows)):
            out.setdefault(pid, []).append(node)
        return {k: tuple(v) for k, v in out.items()}

    def ancestors(self, provision_ids) -> dict[str, tuple]:
        """{provision id: (Ancestor, ...)} outermost first, the provision itself last: the structure above a node
        (Parts, Chapters, its section, sub-sections), with printed labels and headings"""
        if not provision_ids:
            return {}
        self.cur.execute("""
            SELECT c.id::text, a.id::text, a.path::text, a.kind::text, a.label, a.heading, nlevel(a.path)
              FROM provision c
              JOIN provision_ancestor pa ON pa.provision_id = c.id
              JOIN provision a ON a.instrument_id = c.instrument_id AND a.path = pa.ancestor_path AND a.is_active
             WHERE c.id = ANY(%s::uuid[])
             ORDER BY c.id, nlevel(a.path)""", (list(set(provision_ids)),))
        out: dict[str, list] = {}
        for cid, *rest in self.cur.fetchall():
            out.setdefault(cid, []).append(Ancestor(*rest))
        return {k: tuple(v) for k, v in out.items()}

    def units_of(self, provision_ids) -> dict[str, tuple[str, str]]:
        """{provision id: (its unit id, the unit's path)}: the innermost section, article or order above it, else its
        outermost schedule, form, appendix, annexure or preamble, else itself (unit_search's rule)"""
        out = {}
        for pid, chain in self.ancestors(provision_ids).items():
            inner = [a for a in chain if a.kind in UNIT_KINDS]
            outer = [a for a in chain if a.kind in OUTER_KINDS]
            pick = inner[-1] if inner else (outer[0] if outer else chain[-1])
            out[pid] = (pick.provision_id, pick.path)
        return out

    # --- the sections a Part or Chapter holds -------------------------------------------------------------------
    def units_within(self, instrument_id: str, path: str) -> list[str]:
        """the sections, articles and orders inside a Part or Chapter, printed order: the outermost ones (a rule
        inside an order is part of the order)"""
        self.cur.execute("""
            SELECT p.id::text FROM provision p
             WHERE p.instrument_id = %s AND p.is_active AND p.path <@ %s::ltree AND p.path <> %s::ltree
               AND p.kind::text = ANY(%s)
               AND NOT EXISTS (SELECT 1 FROM provision a WHERE a.instrument_id = p.instrument_id AND a.is_active
                                 AND a.path @> p.path AND a.path <> p.path AND a.path <@ %s::ltree
                                 AND a.path <> %s::ltree AND a.kind::text = ANY(%s))
             ORDER BY p.ordinal, p.id""",
                         (instrument_id, path, path, list(UNIT_KINDS), path, path, list(UNIT_KINDS)))
        return [r[0] for r in self.cur.fetchall()]

    # --- the derived links (0114, D-108): read, never computed per question ---------------------------------------
    def references_from(self, provision_ids) -> list[tuple]:
        """[(src provision, kind, target, label, other_law, dst unit, dst law)] for the resolved references made by
        these provisions (provision_reference); the destination's operative status is the caller's to ask"""
        if not provision_ids:
            return []
        # printed order: the node's place in the law, its heading before its words, then position in the words --
        # a per-unit cap then keeps the references a reader meets first ('[See section 5]' above a schedule)
        self.cur.execute("""
            SELECT r.src_provision_id::text, r.kind::text, r.target, r.label, r.other_law, r.dst_unit_id::text,
                   r.dst_instrument_id::text
              FROM provision_reference r JOIN provision p ON p.id = r.src_provision_id
             WHERE r.src_provision_id = ANY(%s::uuid[]) AND r.dst_unit_id IS NOT NULL
             ORDER BY p.ordinal, NOT r.in_heading, r.char_start, r.id""", (list(set(provision_ids)),))
        return self.cur.fetchall()

    def prevailing_over(self, unit_ids) -> list[tuple]:
        """[(unit named, src provision)]: provisions that say 'notwithstanding' a unit -- they prevail over it
        (docs/03b), so a reader of the unit must see them"""
        if not unit_ids:
            return []
        self.cur.execute("""
            SELECT r.dst_unit_id::text, r.src_provision_id::text FROM provision_reference r
             WHERE r.dst_unit_id = ANY(%s::uuid[]) AND r.kind = 'notwithstanding'
             ORDER BY r.dst_unit_id, r.src_provision_id""", (list(set(unit_ids)),))
        return self.cur.fetchall()

    def definitions_of(self, instrument_ids) -> list[dict]:
        """the definitions of these laws (provision_definition), each with its scope's path"""
        if not instrument_ids:
            return []
        self.cur.execute("""
            SELECT d.provision_id::text, d.version_id::text, d.instrument_id::text, d.unit_id::text, d.term,
                   d.term_key, d.scope, sp.path::text AS scope_path, d.after_ordinal, d.empty,
                   d.continuation::text[] AS continuation, p.path::text AS path, p.ordinal
              FROM provision_definition d
              JOIN provision p ON p.id = d.provision_id
              LEFT JOIN provision sp ON sp.id = d.scope_provision_id
             WHERE d.instrument_id = ANY(%s::uuid[])
             ORDER BY d.instrument_id, p.ordinal, d.id""", (list(set(instrument_ids)),))
        cols = [c[0] for c in self.cur.description]
        return [dict(zip(cols, r)) for r in self.cur.fetchall()]

    def _delegations(self) -> dict:
        """the empowers records (v_delegation_current, 0089), read once per process: they change only with a
        release. Whether a delegated instrument is law at as_of is still asked of the view on every call."""
        if not _DELEGATIONS:
            self.cur.execute("""
                SELECT d.enabling_provision_id::text, d.delegated_instrument_id::text, d.enabling_instrument_id::text,
                       coalesce(nullif(i.display_title, ''), i.short_title), i.kind::text, i.year,
                       (SELECT array_agg(v.id::text) FROM (
                           SELECT pv.id FROM provision p JOIN provision_version pv ON pv.provision_id = p.id
                            WHERE p.instrument_id = i.id AND p.is_active ORDER BY p.ordinal, pv.id LIMIT 8) v)
                  FROM v_delegation_current d JOIN instrument i ON i.id = d.delegated_instrument_id
                 WHERE d.assertion = 'recorded' AND i.is_active AND i.duplicate_of IS NULL
                 ORDER BY i.year DESC NULLS LAST, i.id""")
            by_section: dict = {}
            parents: dict = {}
            for sec, dele, enab, title, kind, year, vids in self.cur.fetchall():
                if sec:
                    by_section.setdefault(sec, []).append((dele, title, kind, year, tuple(vids or ())))
                parents.setdefault(dele, set()).add(enab)
            _DELEGATIONS.update(by_section=by_section, parents=parents)
        return _DELEGATIONS

    def parent_laws(self, instrument_ids) -> dict[str, str]:
        """{subordinate instrument: the one released law its enacting formula names} (empowers, 0089)"""
        parents = self._delegations()["parents"]
        return {i: next(iter(parents[i])) for i in set(instrument_ids) if len(parents.get(i, ())) == 1}

    def general_clauses(self) -> dict[str, str]:
        """{jurisdiction: its own General Clauses Act} among released laws (not an amending Act): defaults_from
        (docs/03b) where the law does not define a word. Only where the corpus holds the jurisdiction's own Act
        (D-108): fed -> the General Clauses Act, 1897; a province -> its copy of the 1956 Act; none is guessed.
        Read once per process: it changes only with a release (a stale id only finds no definitions)."""
        if _GENERAL_CLAUSES:
            return dict(_GENERAL_CLAUSES)
        self.cur.execute("""
            SELECT jurisdiction::text, id::text, year FROM v_release_instrument
             WHERE duplicate_of IS NULL
               AND coalesce(nullif(display_title, ''), short_title)
                   ~* '^(the )?((punjab|sindh|west pakistan|khyber pakhtunkhwa|balochistan) )?general clauses act'
               AND coalesce(nullif(display_title, ''), short_title) !~* '(amendment|extension)'""")
        best: dict[str, tuple] = {}
        for juris, iid, year in self.cur.fetchall():
            if juris == "fed" and year != 1897:
                continue                       # federal law: the 1897 Act (the 1887 text is historical)
            best.setdefault(juris, (iid, year))
        _GENERAL_CLAUSES.update({j: v[0] for j, v in best.items()})
        return dict(_GENERAL_CLAUSES)

    def nodes_of(self, provision_ids) -> dict[str, "Node"]:
        """{provision id: its operative node}, the node alone (no subtree)"""
        if not provision_ids:
            return {}
        self.cur.execute("""
            SELECT p.id::text, p.id::text, p.path::text, p.kind::text, p.label, p.first_page, p.last_page,
                   p.ordinal, pv.id::text
              FROM provision p JOIN provision_version pv ON pv.provision_id = p.id
             WHERE p.id = ANY(%s::uuid[]) AND p.is_active""", (list(set(provision_ids)),))
        rows = self.cur.fetchall()
        return {k: n for k, n in self._nodes(rows, self._operative(r[8] for r in rows))}

    # --- notes and links ----------------------------------------------------------------------------------------
    def amendment_notes(self, provision_ids, instrument_ids) -> dict[str, tuple]:
        """{provision id: (AmendmentNote, ...)}: the printed amendment footnotes bound to these provisions
        (v_amendment_reference_current, 0072-0084), in printed order. The laws' source observations are passed
        too: the view's DISTINCT ON is keyed by observation, so that filter is pushed inside it (170 -> 60 ms on
        the Succession Act, 20 Nov 2026); the target filter alone makes it read every footnote."""
        if not provision_ids or not instrument_ids:
            return {}
        self.cur.execute("SELECT DISTINCT source_observation_id FROM instrument WHERE id = ANY(%s::uuid[])",
                         (list(set(instrument_ids)),))
        observations = [r[0] for r in self.cur.fetchall()]
        self.cur.execute("""
            SELECT a.target_provision_id::text, a.footnote_text, a.operations, a.effective_from,
                   a.amending_instrument_id::text
              FROM v_amendment_reference_current a
             WHERE a.source_observation_id = ANY(%s::bigint[])
               AND a.target_provision_id = ANY(%s::uuid[]) AND a.assertion = 'recorded'
             ORDER BY a.target_provision_id, a.source_page, a.entry_ordinal, a.id""",
                         (observations, list(set(provision_ids))))
        out: dict[str, list] = {}
        for pid, text, ops, eff, amending in self.cur.fetchall():
            out.setdefault(pid, []).append(AmendmentNote(pid, " ".join((text or "").split()), tuple(ops or ()),
                                                         eff, amending))
        return {k: tuple(v) for k, v in out.items()}

    def delegated(self, provision_ids, limit: int = 5) -> dict[str, tuple]:
        """{enabling provision id: (Delegated, ...)}: instruments made under these sections (v_delegation_current,
        0089) that are law at the session's date and place -- checked through the view by each instrument's first
        versions -- up to `limit` per section, most recent first"""
        by_section = self._delegations()["by_section"]
        rows = [(pid, *r) for pid in set(provision_ids or ()) for r in by_section.get(pid, ())]
        if not rows:
            return {}
        live = set(self._operative(v for r in rows for v in r[5]))
        out: dict[str, list] = {}
        for pid, iid, title, kind, year, vids in rows:
            if live.intersection(vids) and len(out.setdefault(pid, [])) < limit:
                out[pid].append(Delegated(pid, iid, title, kind, year))
        return {k: tuple(v) for k, v in out.items() if v}


@contextmanager
def session(filters: Filters, connect_fn=connect):
    """one read-only transaction with nzq.as_of and nzq.territory set (INV-5), generic plans; rolled back on exit"""
    if type(filters.as_of) is not date:
        raise ValueError("as_of is mandatory (INV-5) and is a date, not a datetime")
    with connect_fn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL client_min_messages = error")
        cur.execute("SET LOCAL plan_cache_mode = force_generic_plan")   # see the module note; no pg_search here
        cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                    (filters.as_of.isoformat(), filters.territory or ""))
        try:
            yield EvidenceSession(cur, filters)
        finally:
            conn.rollback()
