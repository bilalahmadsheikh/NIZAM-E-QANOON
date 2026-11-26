"""Read side for judgments (docs/PRECEDENT-MODEL.md §4, §6; D-118, D-119, D-121, D-122).

Everything here reads the release views (v_release_judgment, v_release_judgment_paragraph). A citation to a
precedent is rendered from records only (INV-1): the court's recorded name, the case number as printed, the decision
date, and the printed paragraph number, else the page. A number the judgment does not print is never shown.

`before` on every search is the research date (as_of): a judgment decided after it did not exist on that date and
is never returned (the INV-5 rule, read for case law).

Cases (D-125): a judgment is shown with the case it decides (judgment_case, keyed by the case as printed), the other
decisions in that case, and which of them gives the reasons for which short order. A second copy of one decision
(judgment_relation 'copy_of') is read through v_shown_judgment, so it is never listed or returned beside the copy
kept; opened directly, it says which copy is kept.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from nizam.storage import privacy as PV
from nizam.storage.db import dsn
from nizam.storage.library_read import render_citation


def render_judgment_citation(court_name: str, case_no_printed: str, decided_on: date | None,
                             printed_no: str | None = None, page: int | None = None, kind: str = "body") -> str:
    """'<court>, <case as printed>, decided <d Mon yyyy>[, para N | , footnote N | , p. N]' from records only.

    `decided_on` is the decision date, None for an undated judgment (D-124): then 'date of decision not printed'."""
    case = " ".join((case_no_printed or "").split()).rstrip(".")
    when = (f"decided {decided_on.day} {decided_on.strftime('%b %Y')}" if decided_on
            else "date of decision not printed")
    out = f"{court_name}, {case}, {when}"
    if kind == "footnote":
        out += f", footnote {printed_no}" if printed_no else (f", p. {page}" if page else "")
    elif printed_no:
        out += f", para {printed_no}"
    elif page:
        out += f", p. {page}"
    return out


def dates_shown(row: dict) -> dict:
    """The decision date as shown, from a row carrying decided_on (the column) and decided_on_basis (D-124).

    For an undated judgment the column holds the latest possible day, which is the research-date filter and never
    the decision date: it is shown as decided_no_later_than, beside decided_not_before when the judgment allows one."""
    undated = row.get("decided_on_basis") == "undated"
    return dict(decided_on=None if undated else row["decided_on"], undated=undated,
                decided_no_later_than=row["decided_on"] if undated else None,
                decided_not_before=row.get("decided_not_before") if undated else None,
                undated_reason=row.get("undated_reason") if undated else None)


# appeal outcomes that reverse or disturb the judgment below: shown only when lawyer_verified (PRECEDENT-MODEL §2)
NEGATIVE_OUTCOMES = frozenset({"set_aside", "reversed", "modified", "remanded"})
TREATMENT_NEGATIVE = frozenset({"overruled", "per_incuriam", "disapproved"})      # nizam.storage.treatment.NEGATIVE


class JudgmentRead:
    def __init__(self, pool: ConnectionPool | None = None):
        self.pool = pool or ConnectionPool(dsn(), min_size=0, max_size=3, max_waiting=12, timeout=3, open=False,
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
    def tuple_cursor(conn):
        """A cursor returning tuples, for readers written against tuple rows (unit_search.Session, authority.load)."""
        from psycopg.rows import tuple_row
        return conn.cursor(row_factory=tuple_row)

    # ------------------------------------------------------------------------------------------- generators

    @staticmethod
    def bm25_paragraphs(conn, q: str, n: int, before: date, court: str | None = None) -> list[dict]:
        """Best BM25 paragraphs (body and footnote) of released judgments decided on or before `before`.

        The index's best window is taken first, then filtered to the release by id; one statement joining the
        release view would make the planner expand it (the statute lesson, D-095)."""
        rows = conn.execute("""SELECT id, decided_on, pdb.score(id) AS score FROM judgment_paragraph
                                WHERE text ||| %s AND kind IN ('body', 'footnote') AND decided_on <= %s
                                ORDER BY score DESC, id LIMIT %s""", (q, before, n * 4)).fetchall()
        return JudgmentRead._released(conn, rows, n, court)

    @staticmethod
    def dense_paragraphs(conn, bits: str, n: int, before: date, court: str | None = None,
                         ef_search: int = 200) -> list[dict]:
        """Nearest judgment chunks by Hamming distance on the CPU generation's sign bits, folded to paragraphs."""
        conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef_search),))
        rows = conn.execute("""SELECT paragraph_id AS id, decided_on, -(embedding <~> %s::bit(1024)) AS score
                                 FROM judgment_chunk WHERE embedding IS NOT NULL
                                ORDER BY embedding <~> %s::bit(1024) LIMIT %s""",
                            (bits, bits, n * 6)).fetchall()
        best: dict = {}
        for r in rows:
            if r["decided_on"] <= before and (r["id"] not in best or r["score"] > best[r["id"]]["score"]):
                best[r["id"]] = r
        return JudgmentRead._released(conn, sorted(best.values(), key=lambda r: -r["score"]), n, court)

    @staticmethod
    def gpu_vectors_held(conn) -> bool:
        """whether the GPU generation's judgment vectors are loaded (0141, D-158); A33 keeps them complete once they are"""
        return conn.execute("SELECT EXISTS (SELECT 1 FROM judgment_chunk_embedding_gpu) AS h").fetchone()["h"]

    @staticmethod
    def dense_paragraphs_gpu(conn, bits: str, n: int, before: date, court: str | None = None,
                             ef_search: int = 200) -> list[dict]:
        """Nearest judgment chunks by Hamming distance on the GPU generation's 4096 sign bits (D-158), folded to
        paragraphs: the statutes' GPU space, so the question vector is the one statute retrieval uses."""
        conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef_search),))
        rows = conn.execute("""SELECT c.paragraph_id AS id, c.decided_on, -(e.bits <~> %s::bit(4096)) AS score
                                 FROM judgment_chunk_embedding_gpu e JOIN judgment_chunk c ON c.id = e.chunk_id
                                ORDER BY e.bits <~> %s::bit(4096) LIMIT %s""",
                            (bits, bits, n * 6)).fetchall()
        best: dict = {}
        for r in rows:
            if r["decided_on"] <= before and (r["id"] not in best or r["score"] > best[r["id"]]["score"]):
                best[r["id"]] = r
        return JudgmentRead._released(conn, sorted(best.values(), key=lambda r: -r["score"]), n, court)

    @staticmethod
    def citing_paragraphs(conn, provision_ids: list[str], n: int, before: date, court: str | None = None) -> list[dict]:
        """Paragraphs that cite one of these provisions (or a unit inside one), applying or construing it first."""
        if not provision_ids:
            return []
        # the provisions and their sub-units; a citation linked to any copy of one of them counts (alternates, D-136).
        # The window is of JUDGMENTS, each by its best citing paragraph: counted in paragraphs, a few judgments with
        # many citing paragraphs crowded the rest out (D-137)
        rows = conn.execute("""
            WITH u AS (SELECT array_agg(p.id) AS ids FROM provision t
                         JOIN provision p ON p.instrument_id = t.instrument_id AND p.path <@ t.path
                        WHERE t.id = ANY(%s::uuid[])),
                 c AS (SELECT r.judgment_id, r.paragraph_id, r.decided_on,
                              max(CASE r.role WHEN 'interpreted' THEN 3 WHEN 'quoted' THEN 3 WHEN 'challenged' THEN 3
                                              WHEN 'charge' THEN 1 ELSE 2 END) AS score,
                              count(*) AS mentions
                         FROM judgment_statute_reference r, u
                        WHERE r.decided_on <= %s AND (r.dst_provision_id = ANY(u.ids) OR r.alternates && u.ids)
                        GROUP BY 1, 2, 3),
                 b AS (SELECT DISTINCT ON (judgment_id) * FROM c
                        ORDER BY judgment_id, score DESC, mentions DESC, paragraph_id)
            SELECT paragraph_id AS id, decided_on, score FROM b
             ORDER BY score DESC, decided_on DESC LIMIT %s""",
            (provision_ids, before, n * 4)).fetchall()
        return JudgmentRead._released(conn, rows, n, court)

    @staticmethod
    def _released(conn, rows: list[dict], n: int, court: str | None) -> list[dict]:
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        # v_shown_judgment: a second copy of a decision is never a hit beside the copy kept (D-125)
        live = {r["id"]: r for r in conn.execute("""
            SELECT p.id, p.decided_on, p.judgment_id FROM v_release_judgment_paragraph p
              JOIN v_shown_judgment j ON j.id = p.judgment_id AND j.decided_on = p.decided_on
             WHERE p.id = ANY(%s::uuid[]) AND (%s::text IS NULL OR j.court_code = %s)""",
            (ids, court, court)).fetchall()}
        out = []
        for r in rows:
            if r["id"] in live:
                out.append(dict(r, judgment_id=live[r["id"]]["judgment_id"]))
            if len(out) >= n:
                break
        return out

    # ---------------------------------------------------------------------------------------------- privacy

    @staticmethod
    def privacy_of(conn, judgment_ids: list) -> dict:
        """judgment id -> {parties_display, redacted, names (internal), categories [{code, name, basis_kind, basis}]}
        (D-131). names is used here to redact and to guard search, and is never returned to a caller."""
        if not judgment_ids:
            return {}
        rows = conn.execute("""
            SELECT d.judgment_id, d.parties_display, d.redacted, d.names_withheld,
                   coalesce(json_agg(json_build_object('code', c.code, 'name', c.name, 'basis_kind', c.basis_kind,
                                                       'basis', c.basis_note) ORDER BY c.code)
                            FILTER (WHERE c.code IS NOT NULL), '[]') AS categories
              FROM judgment_display d
              LEFT JOIN judgment_sensitivity s ON s.judgment_id = d.judgment_id AND s.decided_on = d.decided_on
              LEFT JOIN sensitive_category c ON c.code = s.category
             WHERE d.judgment_id = ANY(%s::uuid[])
             GROUP BY 1, 2, 3, 4""", (list(judgment_ids),)).fetchall()
        return {r["judgment_id"]: dict(parties_display=r["parties_display"], redacted=r["redacted"],
                                       names=r["names_withheld"], categories=r["categories"]) for r in rows}

    @staticmethod
    def shown_text(text: str, privacy: dict | None) -> str:
        """The text a caller may see: withheld names replaced (D-131)."""
        if not privacy or not privacy["redacted"]:
            return text
        # a victim's identity is protected by statute (PPC s.376A): in a sexual-offence judgment a one-word name is
        # withheld even when it is a common word; elsewhere 'Ali' alone is not blanked everywhere
        sexual = any(c["code"] == "sexual_offence" for c in privacy["categories"])
        return PV.redact(text, privacy["names"], frozenset() if sexual else PV.common_words())

    @staticmethod
    def privacy_public(privacy: dict | None) -> dict:
        """What a caller is told: whether names are withheld, and why, with each category's recorded basis."""
        if not privacy:
            return dict(names_withheld=False, categories=[])
        return dict(names_withheld=privacy["redacted"], categories=privacy["categories"])

    # ---------------------------------------------------------------------------------------------- details

    @staticmethod
    def paragraph_hits(conn, paragraph_ids: list) -> dict:
        """Everything a precedent hit shows, by paragraph id, rendered from records."""
        rows = conn.execute("""
            SELECT p.id, p.kind, p.printed_no, p.page_first, p.text, j.id AS judgment_id, j.decided_on, j.court_code,
                   c.name AS court_name, j.case_no_printed, j.case_type_code, j.disposition, j.reported_flag,
                   j.bench_size, ct.name AS case_type_name, o.kind AS opinion_kind, j.decided_on_basis,
                   j.decided_not_before, j.undated_reason,
                   (SELECT c.case_key FROM judgment_case c WHERE c.judgment_id = j.id AND c.decided_on = j.decided_on
                                                             AND c.role = 'lead') AS case_key,
                   (SELECT r.short_order_on FROM judgment_relation r WHERE r.judgment_id = j.id
                       AND r.decided_on = j.decided_on AND r.relation = 'reasons_for') AS reasons_for_short_order_on,
                   EXISTS (SELECT 1 FROM judgment_relation r WHERE r.judgment_id = j.id AND r.decided_on = j.decided_on
                                                               AND r.relation = 'reasons_for') AS gives_reasons
              FROM v_release_judgment_paragraph p
              JOIN judgment j ON j.id = p.judgment_id AND j.decided_on = p.decided_on
              JOIN court c ON c.code = j.court_code
              LEFT JOIN case_type ct ON ct.code = j.case_type_code
              LEFT JOIN judgment_opinion o ON o.id = p.opinion_id
             WHERE p.id = ANY(%s::uuid[])""", (list(paragraph_ids),)).fetchall()
        priv = JudgmentRead.privacy_of(conn, list({r["judgment_id"] for r in rows}))
        out = {}
        for r in rows:
            r.update(dates_shown(r))
            r["citation"] = render_judgment_citation(r["court_name"], r["case_no_printed"], r["decided_on"],
                                                     r["printed_no"], r["page_first"], r["kind"])
            p = priv.get(r["judgment_id"])
            r["text"] = JudgmentRead.shown_text(r["text"], p)
            r["parties_display"] = p["parties_display"] if p else None
            r["privacy"] = JudgmentRead.privacy_public(p)
            r["_names_withheld"] = p["names"] if p and p["redacted"] else []     # internal: the search guard only
            out[r["id"]] = r
        return out

    @staticmethod
    def statutes_cited(conn, judgment_ids: list, as_of: date) -> dict:
        """Per judgment: the provisions it cites that resolved, with whether the text the court read is still the
        operative text on `as_of` (amended_since / repealed_since are computed here, never stored)."""
        if not judgment_ids:
            return {}
        conn.execute("SELECT set_config('nzq.as_of', %s, true)", (as_of.isoformat(),))
        rows = conn.execute("""
            SELECT r.judgment_id, r.dst_provision_id, r.dst_version_id, r.version_basis, r.role, r.raw,
                   p.label, p.kind::text AS kind, i.short_title, i.year, i.kind::text AS instrument_kind,
                   (SELECT op.version_id FROM operative_provision op WHERE op.provision_id = r.dst_provision_id
                     LIMIT 1) AS operative_version,
                   EXISTS (SELECT 1 FROM operative_provision op WHERE op.instrument_id = p.instrument_id
                                                                  AND op.path <@ p.path) AS served_now,
                   r.law_basis
              FROM judgment_statute_reference r
              JOIN provision p ON p.id = r.dst_provision_id
              JOIN instrument i ON i.id = p.instrument_id
             WHERE r.judgment_id = ANY(%s::uuid[]) AND r.resolution = 'resolved'
             ORDER BY r.judgment_id, r.char_start""", (list(judgment_ids),)).fetchall()
        out: dict = {}
        for r in rows:
            seen = out.setdefault(r["judgment_id"], {})
            key = r["dst_provision_id"]
            if key in seen:
                seen[key]["mentions"] += 1
                continue
            r["citation"] = render_citation(r["short_title"], r["year"], r["kind"], r["label"], r["instrument_kind"])
            if not r["served_now"]:
                r["status_now"] = "not_operative"            # repealed, uncommenced or out of extent on as_of
            elif r["dst_version_id"] and r["operative_version"] != r["dst_version_id"]:
                r["status_now"] = "amended_since"
            elif r["version_basis"] == "not_dated":
                r["status_now"] = "text_at_decision_not_held"
            else:
                r["status_now"] = "same_text"
            r["mentions"] = 1
            seen[key] = r
        return {j: list(v.values()) for j, v in out.items()}

    def judgment(self, judgment_id, as_of: date) -> dict | None:
        with self.transaction() as conn:
            j = conn.execute("""SELECT j.*, c.name AS court_name, ct.name AS case_type_name, s.source_url
                                  FROM v_release_judgment j JOIN court c ON c.code = j.court_code
                                  LEFT JOIN case_type ct ON ct.code = j.case_type_code
                                  LEFT JOIN LATERAL (SELECT source_url FROM judgment_source x
                                                      JOIN judgment_document d ON d.sha256 = x.sha256
                                                     WHERE d.id = j.document_id AND x.source_url IS NOT NULL
                                                     ORDER BY x.id LIMIT 1) s ON true
                                 WHERE j.id = %s""", (judgment_id,)).fetchone()
            if not j or j["decided_on"] > as_of:
                return None
            paras = conn.execute("""SELECT p.id, p.kind, p.printed_no, p.page_first, p.text, o.ordinal AS opinion,
                                           o.kind AS opinion_kind
                                      FROM judgment_paragraph p LEFT JOIN judgment_opinion o ON o.id = p.opinion_id
                                     WHERE p.judgment_id = %s AND p.decided_on = %s
                                       AND p.kind IN ('body', 'footnote')
                                     ORDER BY p.ordinal""", (j["id"], j["decided_on"])).fetchall()
            shown = dates_shown(j)
            for p in paras:
                p["citation"] = render_judgment_citation(j["court_name"], j["case_no_printed"], shown["decided_on"],
                                                         p["printed_no"], p["page_first"], p["kind"])
            opinions = conn.execute("""SELECT ordinal, kind, heading_printed, author_printed FROM judgment_opinion
                                        WHERE judgment_id = %s ORDER BY ordinal""", (j["id"],)).fetchall()
            lineage = conn.execute("""SELECT relation, lower_court_code, lower_court_printed, lower_case_printed,
                                             lower_decided_on, outcome, review_status
                                        FROM judgment_lineage WHERE upper_judgment_id = %s""", (j["id"],)).fetchall()
            cases = conn.execute("""SELECT r.raw, r.reporter_series, r.reporter_year, r.reporter_page, r.resolution,
                                           r.dst_judgment_id, r.dst_case_key FROM judgment_case_reference r
                                     WHERE r.judgment_id = %s ORDER BY r.char_start""", (j["id"],)).fetchall()
            statutes = self.statutes_cited(conn, [j["id"]], as_of).get(j["id"], [])
            case = self._case_of(conn, j, as_of)
            priv = self.privacy_of(conn, [j["id"]]).get(j["id"])
        for p in paras:                                             # withheld names replaced (D-131)
            p["text"] = self.shown_text(p["text"], priv)
        j.pop("parties_raw", None)                                  # internal only (D-122)
        j.pop("decision_date", None)
        j["parties_display"] = priv["parties_display"] if priv else None
        j.update(shown)                                             # never the latest-possible day as the date
        return dict(judgment=j, opinions=opinions, paragraphs=paras, lineage=lineage, cases_cited=cases,
                    statutes_cited=statutes, case=case, privacy=self.privacy_public(priv),
                    citation=render_judgment_citation(j["court_name"], j["case_no_printed"], shown["decided_on"]))

    # ------------------------------------------------------------------------------------------------ cases

    @staticmethod
    def _relations(conn, ids: list) -> tuple[dict, dict]:
        """(judgment -> its reasons_for / copy_of rows, judgment -> the judgments relating to it), for `ids`."""
        rows = conn.execute("""SELECT judgment_id, relation, other_judgment_id, short_order_on, date_basis, printed,
                                      score FROM judgment_relation
                                WHERE judgment_id = ANY(%s::uuid[]) OR other_judgment_id = ANY(%s::uuid[])""",
                            (ids, ids)).fetchall()
        own: dict = {}
        incoming: dict = {}
        for r in rows:
            own.setdefault(r["judgment_id"], {})[r["relation"]] = r
            if r["other_judgment_id"]:
                incoming.setdefault(r["other_judgment_id"], []).append(r)
        return own, incoming

    @staticmethod
    def _decision(r: dict, own: dict, incoming: dict) -> dict:
        """One decision of a case, as shown: its citation and dates from records, and how it relates to the others
        (it gives the reasons for a short order; it is a short order whose reasons another judgment gives)."""
        shown = dates_shown(r)
        reasons = own.get(r["id"], {}).get("reasons_for")
        return dict(judgment_id=r["id"], **shown, case_no_printed=r["case_no_printed"],
                    citation=render_judgment_citation(r["court_name"], r["case_no_printed"], shown["decided_on"]),
                    gives_reasons_for=(dict(short_order_on=reasons["short_order_on"],
                                            date_basis=reasons["date_basis"],
                                            short_order_judgment_id=reasons["other_judgment_id"],
                                            printed=reasons["printed"]) if reasons else None),
                    reasons_given_in=[x["judgment_id"] for x in incoming.get(r["id"], [])
                                      if x["relation"] == "reasons_for"])

    def _case_decisions(self, conn, keys: list[str], as_of: date) -> list[dict]:
        """The decisions shown in these cases that existed on `as_of`, oldest first, undated last."""
        rows = conn.execute("""
            SELECT j.id, j.decided_on, j.decided_on_basis, j.decided_not_before, j.undated_reason,
                   j.case_no_printed, c.name AS court_name
              FROM v_shown_judgment j JOIN court c ON c.code = j.court_code
             WHERE EXISTS (SELECT 1 FROM judgment_case m WHERE m.judgment_id = j.id AND m.decided_on = j.decided_on
                                                           AND m.case_key = ANY(%s))
               AND j.decided_on <= %s
             ORDER BY j.decided_on_basis = 'undated', j.decided_on, j.id""", (keys, as_of)).fetchall()
        own, incoming = self._relations(conn, [r["id"] for r in rows])
        return [self._decision(r, own, incoming) for r in rows]

    def _case_of(self, conn, j: dict, as_of: date) -> dict:
        """The case record of a judgment (D-125): the cases it decides, the other decisions in them, its reasons
        statement, and whether it is a second copy of another decision. A judgment the builder could not place in a
        case says why, rather than showing none."""
        state = conn.execute("""SELECT outcome, case_line_read FROM judgment_case_state
                                 WHERE judgment_id = %s AND decided_on = %s""", (j["id"], j["decided_on"])).fetchone()
        keys = conn.execute("""SELECT c.case_key, c.role, k.case_number, k.case_year, ct.name AS case_type_name
                                 FROM judgment_case c JOIN judicial_case k ON k.case_key = c.case_key
                                 LEFT JOIN case_type ct ON ct.code = k.case_type_code
                                WHERE c.judgment_id = %s AND c.decided_on = %s
                                ORDER BY c.role = 'lead' DESC, c.case_key""", (j["id"], j["decided_on"])).fetchall()
        own, incoming = self._relations(conn, [j["id"]])
        mine = self._decision(dict(j, id=j["id"]), own, incoming)
        copy = own.get(j["id"], {}).get("copy_of")
        decisions = [d for d in self._case_decisions(conn, [k["case_key"] for k in keys], as_of)
                     if d["judgment_id"] != j["id"]] if keys else []
        return dict(status=(state["outcome"] if state else "not_built"),
                    case_line_read=(state["case_line_read"] if state else None),
                    cases_decided=keys, other_decisions=decisions,
                    gives_reasons_for=mine["gives_reasons_for"], reasons_given_in=mine["reasons_given_in"],
                    copy_of=(dict(judgment_id=copy["other_judgment_id"], score=copy["score"]) if copy else None),
                    copies=[x["judgment_id"] for x in incoming.get(j["id"], []) if x["relation"] == "copy_of"])

    def case(self, case_key: str, as_of: date) -> dict | None:
        """One case (D-125): its record, every decision in it that existed on `as_of`, and the judgments that cite
        it. None when the case is not held or none of its decisions existed on that date."""
        with self.transaction() as conn:
            k = conn.execute("""SELECT k.case_key, k.court_code, c.name AS court_name, k.case_type_code,
                                       ct.name AS case_type_name, ct.kind AS case_kind, k.case_number, k.case_year
                                  FROM judicial_case k JOIN court c ON c.code = k.court_code
                                  LEFT JOIN case_type ct ON ct.code = k.case_type_code
                                 WHERE k.case_key = %s""", (case_key,)).fetchone()
            if not k:
                return None
            decisions = self._case_decisions(conn, [case_key], as_of)
            if not decisions:
                return None
            cited = conn.execute("""
                SELECT r.judgment_id, j.decided_on, j.decided_on_basis, j.decided_not_before, j.undated_reason,
                       j.case_no_printed, c.name AS court_name, count(*) AS mentions
                  FROM judgment_case_reference r
                  JOIN v_shown_judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                  JOIN court c ON c.code = j.court_code
                 WHERE r.dst_case_key = %s AND r.resolution = 'resolved' AND j.decided_on <= %s
                 GROUP BY 1, 2, 3, 4, 5, 6, 7
                 ORDER BY j.decided_on_basis = 'undated', j.decided_on DESC LIMIT 50""", (case_key, as_of)).fetchall()
        cited_by = []
        for r in cited:
            shown = dates_shown(r)
            cited_by.append(dict(judgment_id=r["judgment_id"], mentions=r["mentions"], **shown,
                                 citation=render_judgment_citation(r["court_name"], r["case_no_printed"],
                                                                   shown["decided_on"])))
        return dict(case=k, decisions=decisions, cited_by=cited_by)

    def provision_judgments(self, provision_id, as_of: date, limit: int = 20) -> list[dict]:
        """'Cases on this section': released judgments citing the provision or a unit inside it, newest first."""
        with self.transaction() as conn:
            rows = conn.execute("""
                WITH u AS (SELECT array_agg(p.id) AS ids FROM provision t
                             JOIN provision p ON p.instrument_id = t.instrument_id AND p.path <@ t.path
                            WHERE t.id = %s)
                SELECT r.judgment_id, r.decided_on, count(*) AS mentions,
                       array_agg(DISTINCT r.role) AS roles, min(r.paragraph_id::text) AS first_paragraph,
                       bool_or(j.decided_on_basis = 'undated') AS undated
                  FROM judgment_statute_reference r
                  JOIN judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                  CROSS JOIN u
                 WHERE r.decided_on <= %s
                   AND (r.dst_provision_id = ANY(u.ids) OR r.alternates && u.ids)   -- any copy (D-136)
                 GROUP BY 1, 2 ORDER BY 6, r.decided_on DESC LIMIT %s""",   # newest dated first, undated last
                (provision_id, as_of, limit * 2)).fetchall()
            if not rows:
                return []
            meta = {r["id"]: r for r in conn.execute("""
                SELECT j.id, j.decided_on, j.case_no_printed, j.disposition, j.reported_flag, c.name AS court_name,
                       ct.name AS case_type_name, j.decided_on_basis, j.decided_not_before, j.undated_reason,
                       (SELECT m.case_key FROM judgment_case m WHERE m.judgment_id = j.id
                           AND m.decided_on = j.decided_on AND m.role = 'lead') AS case_key
                  FROM v_shown_judgment j JOIN court c ON c.code = j.court_code
                  LEFT JOIN case_type ct ON ct.code = j.case_type_code
                 WHERE j.id = ANY(%s::uuid[])""", ([r["judgment_id"] for r in rows],)).fetchall()}
            priv = self.privacy_of(conn, [r["judgment_id"] for r in rows])
        out = []
        for r in rows:
            m = meta.get(r["judgment_id"])
            if m:
                shown = dates_shown(m)
                p = priv.get(r["judgment_id"])
                out.append(dict(judgment_id=r["judgment_id"], mentions=r["mentions"], case_key=m["case_key"],
                                parties_display=p["parties_display"] if p else None,
                                names_withheld=bool(p and p["redacted"]),
                                roles=sorted(r["roles"]), court=m["court_name"], case_type=m["case_type_name"],
                                disposition=m["disposition"], reported=m["reported_flag"], **shown,
                                citation=render_judgment_citation(m["court_name"], m["case_no_printed"],
                                                                  shown["decided_on"])))
            if len(out) >= limit:
                break
        return out

    def citing_judgments(self, judgment_id, as_of: date, limit: int = 20) -> list[dict]:
        """'Cited by': released judgments, decided on or before `as_of`, that cite the case this judgment decides, by
        its case number or by a reporter citation the court publishes for it (D-150); newest first. A citation in a
        judgment of the same case (its own_case) is not 'cited by'."""
        with self.transaction() as conn:
            rows = conn.execute("""
                WITH mine AS (SELECT c.case_key FROM judgment_case c
                               JOIN judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on
                              WHERE j.id = %s)
                SELECT r.judgment_id, r.decided_on, count(*) AS mentions, min(r.raw) AS printed,
                       bool_or(r.reporter_series IS NOT NULL) AS by_report,
                       bool_or(j.decided_on_basis = 'undated') AS undated
                  FROM judgment_case_reference r
                  JOIN judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                 WHERE r.resolution = 'resolved' AND r.decided_on <= %s AND r.judgment_id <> %s
                   AND (r.dst_judgment_id = %s OR r.dst_case_key IN (SELECT case_key FROM mine))
                 GROUP BY 1, 2 ORDER BY 6, r.decided_on DESC LIMIT %s""",
                (judgment_id, as_of, judgment_id, judgment_id, limit * 2)).fetchall()
            if not rows:
                return []
            meta = {r["id"]: r for r in conn.execute("""
                SELECT j.id, j.decided_on, j.case_no_printed, j.disposition, j.reported_flag, c.name AS court_name,
                       ct.name AS case_type_name, j.decided_on_basis, j.decided_not_before, j.undated_reason,
                       (SELECT m.case_key FROM judgment_case m WHERE m.judgment_id = j.id
                           AND m.decided_on = j.decided_on AND m.role = 'lead') AS case_key
                  FROM v_shown_judgment j JOIN court c ON c.code = j.court_code
                  LEFT JOIN case_type ct ON ct.code = j.case_type_code
                 WHERE j.id = ANY(%s::uuid[])""", ([r["judgment_id"] for r in rows],)).fetchall()}
            priv = self.privacy_of(conn, [r["judgment_id"] for r in rows])
            # how each citing judgment treats this case, in its own words (D-160); a negative treatment only once a
            # lawyer has verified it (PRECEDENT-MODEL §2), else it is counted as awaiting review
            treated: dict = {}
            for t in conn.execute("""
                    SELECT t.judgment_id, t.treatment, t.review_status FROM case_treatment t
                     WHERE t.judgment_id = ANY(%s::uuid[]) AND t.review_status <> 'rejected'
                       AND t.dst_case_key IN (SELECT c.case_key FROM judgment_case c
                                               JOIN judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on
                                              WHERE j.id = %s)""",
                    ([r["judgment_id"] for r in rows], judgment_id)).fetchall():
                treated.setdefault(t["judgment_id"], []).append(t)
        out = []
        for r in rows:
            ts = treated.get(r["judgment_id"], [])
            shown_t = sorted({t["treatment"] for t in ts
                              if t["treatment"] not in TREATMENT_NEGATIVE or t["review_status"] == "lawyer_verified"})
            pending = sum(1 for t in ts
                          if t["treatment"] in TREATMENT_NEGATIVE and t["review_status"] != "lawyer_verified")
            m = meta.get(r["judgment_id"])
            if m:
                shown = dates_shown(m)
                p = priv.get(r["judgment_id"])
                out.append(dict(judgment_id=r["judgment_id"], mentions=r["mentions"], case_key=m["case_key"],
                                cited_as=r["printed"], by_reporter_citation=r["by_report"],
                                treatments=shown_t, treatments_awaiting_review=pending,
                                parties_display=p["parties_display"] if p else None,
                                names_withheld=bool(p and p["redacted"]),
                                court=m["court_name"], case_type=m["case_type_name"],
                                disposition=m["disposition"], reported=m["reported_flag"], **shown,
                                citation=render_judgment_citation(m["court_name"], m["case_no_printed"],
                                                                  shown["decided_on"])))
            if len(out) >= limit:
                break
        return out

    def later_history(self, judgment_id, as_of: date) -> list[dict]:
        """What happened to this judgment's case above it (D-159): released judgments decided on or before `as_of`
        whose appeal chain (judgment_lineage_link) names it -- `matched` 'judgment' when the upper court's printed
        case and date single it out, 'case' when only its case is named (several decisions, or an undated copy).
        The outcome is the upper court's own (affirmed, set aside, remanded, leave refused ...), oldest first; a
        later history is never inferred from anything else."""
        with self.transaction() as conn:
            rows = conn.execute("""
                WITH mine AS (SELECT c.case_key FROM judgment_case c
                               JOIN judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on
                              WHERE j.id = %s)
                SELECT k.upper_judgment_id, k.upper_decided_on, l.relation, l.outcome, l.review_status,
                       l.lower_case_printed, l.lower_decided_on,
                       CASE WHEN k.lower_judgment_id = %s THEN 'judgment' ELSE 'case' END AS matched
                  FROM judgment_lineage_link k JOIN judgment_lineage l ON l.id = k.lineage_id
                 WHERE k.upper_decided_on <= %s AND k.upper_judgment_id <> %s
                   AND (k.lower_judgment_id = %s
                        OR (k.resolution = 'case_held' AND k.lower_case_key IN (SELECT case_key FROM mine)))
                 ORDER BY k.upper_decided_on""",
                (judgment_id, judgment_id, as_of, judgment_id, judgment_id)).fetchall()
            # the court below's own record of what the court above did (0144): a second source, labelled, shown
            # only when the court above had decided by `as_of`
            recorded = conn.execute("""
                SELECT o.upper_court_code, c.name AS court_name, o.outcome, o.outcome_printed, o.upper_decided_on,
                       o.source_id, o.upper_file_url
                  FROM judgment_recorded_outcome o JOIN court c ON c.code = o.upper_court_code
                 WHERE o.judgment_id = %s AND o.upper_decided_on <= %s
                 ORDER BY o.upper_decided_on""", (judgment_id, as_of)).fetchall()
            if not rows and not recorded:
                return []
            meta = {r["id"]: r for r in conn.execute("""
                SELECT j.id, j.decided_on, j.case_no_printed, j.disposition, c.name AS court_name,
                       j.decided_on_basis, j.decided_not_before, j.undated_reason
                  FROM v_shown_judgment j JOIN court c ON c.code = j.court_code
                 WHERE j.id = ANY(%s::uuid[])""", ([r["upper_judgment_id"] for r in rows],)).fetchall()}
        out = []
        for r in rows:
            m = meta.get(r["upper_judgment_id"])
            if not m:
                continue
            shown = dates_shown(m)
            # a reversal read by machine is shown only once a lawyer verifies it (PRECEDENT-MODEL §2, docs/06 §5.1):
            # until then the later decision is listed and its outcome is withheld, marked so
            withheld = r["outcome"] in NEGATIVE_OUTCOMES and r["review_status"] != "lawyer_verified"
            out.append(dict(source="upper_judgment", judgment_id=r["upper_judgment_id"], court=m["court_name"],
                            relation=r["relation"], outcome=None if withheld else r["outcome"],
                            outcome_withheld="awaiting lawyer review" if withheld else None, matched=r["matched"],
                            below_as_printed=r["lower_case_printed"], below_dated=r["lower_decided_on"], **shown,
                            citation=render_judgment_citation(m["court_name"], m["case_no_printed"],
                                                              shown["decided_on"])))
        for r in recorded:
            # no judgment of the court above is held: there is no citation to render, only the record and its source.
            # The outcome is the court's own published record, not a machine reading, so the review rule for read
            # reversals does not hold it back; it is labelled as the court's record
            out.append(dict(source="court_record", recorded_by=r["source_id"], judgment_id=None, court=r["court_name"],
                            relation=None, outcome=r["outcome"], outcome_printed=r["outcome_printed"],
                            matched="judgment", decided_on=r["upper_decided_on"], citation=None,
                            upper_file_url=r["upper_file_url"]))
        return out

    def coverage(self) -> list[dict]:
        with self.transaction() as conn:
            return conn.execute("""SELECT court_code, year, judgments_released, first_decided, last_decided
                                     FROM v_judgment_coverage ORDER BY court_code, year""").fetchall()
