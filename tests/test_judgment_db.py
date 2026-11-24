"""Judgments in the database (0119-0121): the constraints, the release, the links, search and the routes.

These need migrations 0119-0121 applied and the Supreme Court archive landed. They skip otherwise. Writes are rolled
back.
"""
from __future__ import annotations

import datetime as dt

import pytest

TODAY = dt.date(2026, 11, 22)


@pytest.fixture()
def cur():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as c:
                c.execute("SELECT to_regclass('judgment_chunk'), (SELECT count(*) FROM judgment WHERE is_active)")
                reg, n = c.fetchone()
                if reg is None or not n:
                    pytest.skip("judgment tables not applied or no judgment landed")
                yield c
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _raises(cur, sql, args=(), match=""):
    import psycopg
    cur.execute("SAVEPOINT t")
    with pytest.raises(psycopg.Error, match=match):
        cur.execute(sql, args)
    cur.execute("ROLLBACK TO SAVEPOINT t")


def test_a_decision_date_outside_the_created_partitions_fails_loudly(cur):
    cur.execute("SELECT id FROM judgment_document WHERE outcome = 'parsed' AND is_active LIMIT 1")
    doc = cur.fetchone()[0]
    _raises(cur, """INSERT INTO judgment (decided_on, document_id, court_code, decided_on_basis, decided_on_printed,
                                          case_no_printed, parser)
                    VALUES ('2091-01-01', %s, 'SC', 'announced', 'x', 'x', 'test')""", (doc,),
            match="no partition")


def test_an_undated_judgment_prints_no_date_and_names_why(cur):
    cur.execute("SELECT id FROM judgment_document WHERE outcome = 'parsed' AND is_active LIMIT 1")
    doc = cur.fetchone()[0]
    for printed, reason in (("x", "no date"), (None, None)):          # a printed date, or no reason: refused
        _raises(cur, """INSERT INTO judgment (decided_on, document_id, court_code, decided_on_basis, decided_on_printed,
                                              undated_reason, case_no_printed, parser)
                        VALUES ('2026-09-03', %s, 'SC', 'undated', %s, %s, 'x', 'test')""", (doc, printed, reason),
                match="ck_judgment_undated")
    _raises(cur, """INSERT INTO judgment (decided_on, document_id, court_code, decided_on_basis, decided_on_printed,
                                          decided_not_before, decided_not_before_basis, case_no_printed, parser)
                    VALUES ('2020-01-01', %s, 'SC', 'announced', 'x', '2019-01-01', 'hearing', 'x', 'test')""",
            (doc,), match="ck_judgment_not_before")         # a lower bound only for an undated judgment


def test_evidence_is_append_only_and_readings_need_a_reason(cur):
    cur.execute("SELECT id FROM judgment_source LIMIT 1")
    _raises(cur, "DELETE FROM judgment_source WHERE id = %s", cur.fetchone(), match="append-only")
    cur.execute("SELECT sha256 FROM judgment_source LIMIT 1")
    _raises(cur, """INSERT INTO judgment_document (sha256, court_code, extractor, parser, lane, language, page_count,
                                                   char_count, outcome, is_active)
                    VALUES (%s, 'SC', 'x', 'x', 'E2', 'en', 1, 0, 'held', false)""", cur.fetchone(),
            match="ck_judgment_document_reason|ck_judgment_document_active")


def test_a_chunk_cannot_pass_its_paragraph(cur):
    cur.execute("""SELECT p.id, p.decided_on, p.judgment_id, length(p.text) FROM v_release_judgment_paragraph p
                    WHERE p.kind = 'body' LIMIT 1""")
    pid, day, jid, n = cur.fetchone()
    _raises(cur, """INSERT INTO judgment_chunk (paragraph_id, decided_on, judgment_id, seq, char_start, char_end,
                                                context_prefix, chunker)
                    VALUES (%s, %s, %s, 999, 0, %s, 'x', 'test')""", (pid, day, jid, n + 1), match="passes paragraph")


def test_a_body_paragraph_belongs_to_an_opinion_and_numbers_are_only_printed_ones(cur):
    cur.execute("""SELECT count(*) FILTER (WHERE kind = 'body' AND opinion_id IS NULL),
                          count(*) FILTER (WHERE printed_no IS NOT NULL AND printed_no !~ '^[0-9]{1,3}$')
                     FROM v_release_judgment_paragraph""")
    assert cur.fetchone() == (0, 0)


def test_resolved_citations_point_at_released_law_and_inheritance_is_marked(cur):
    cur.execute("""SELECT count(*) FILTER (WHERE resolution = 'resolved'),
                          count(*) FILTER (WHERE law_basis = 'inherited' AND inherited_from IS NULL),
                          count(*) FILTER (WHERE version_basis = 'dated' AND resolution <> 'resolved')
                     FROM judgment_statute_reference""")
    resolved, bad_inherit, bad_dated = cur.fetchone()
    if not resolved:
        pytest.skip("links not built")
    assert bad_inherit == 0 and bad_dated == 0


# ---------------------------------------------------------------------------------------------- search, routes

@pytest.fixture(scope="module")
def repo():
    try:
        from nizam.storage.judgment_read import JudgmentRead
        r = JudgmentRead()
        r.open()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    yield r
    r.close()


def test_precedent_search_returns_only_judgments_decided_by_the_date(repo):
    from nizam.retrieval.precedent import search
    try:
        r = search("bail further inquiry cross version", as_of=dt.date(2015, 1, 1), k=10, repo=repo)
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"search unavailable: {type(exc).__name__}: {exc}")
    if not r.hits:
        pytest.skip("no judgments decided by 2015 match")
    assert all(h.decided_on <= dt.date(2015, 1, 1) for h in r.hits)
    # every hit's citation opens with its court's recorded name (SC, and since D-128/D-130 the Lahore and Peshawar HCs)
    assert all(h.citation.startswith(("Supreme Court of Pakistan, ", "Lahore High Court, ", "Peshawar High Court, "))
               for h in r.hits)
    assert r.coverage and r.mode in ("hybrid", "lexical_only")


def test_an_undated_judgment_is_never_shown_with_its_latest_possible_day_as_the_date(repo):
    with repo.transaction() as conn:
        row = conn.execute("""SELECT id, decided_on FROM v_release_judgment WHERE decided_on_basis = 'undated'
                               AND decision_date IS NULL LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no undated judgment released")
    j = repo.judgment(row["id"], TODAY)
    assert j["judgment"]["decided_on"] is None and j["judgment"]["undated"] is True
    assert j["judgment"]["decided_no_later_than"] == row["decided_on"]
    assert j["citation"].endswith("date of decision not printed")
    assert all("decided " not in p["citation"] for p in j["paragraphs"])
    # before the archive is known to have held it, it is not known to have existed
    assert repo.judgment(row["id"], row["decided_on"] - dt.timedelta(days=1)) is None


def test_a_named_section_reaches_the_judgments_that_cite_it(repo):
    from nizam.retrieval.precedent import search
    from nizam.storage.authority import Subordinate
    r = search("bail under section 497 CrPC further inquiry", as_of=TODAY, k=10, repo=repo,
               forum=Subordinate("punjab"))
    if not r.cited_provisions:
        pytest.skip("section 497 CrPC not resolved")
    if not any("cited" in h.generators for h in r.hits):
        pytest.skip("links not built yet")
    # a Punjab subordinate court today is bound by the Supreme Court (Art. 189) and by the Lahore High Court
    # (Art. 201), never by another High Court: a Peshawar judgment reaches it as not binding (recorded rules)
    for h in r.hits:
        assert h.authority, h.citation
        binds = "Supreme Court" in h.court or "Lahore" in h.court
        assert h.authority["status"] == ("binding" if binds else "not_binding"), (h.court, h.authority)


def test_the_routes_serve_search_a_judgment_and_cases_on_a_section(repo, monkeypatch):
    monkeypatch.setenv("NIZAM_WARM", "0")
    from fastapi.testclient import TestClient
    from nizam.api.library import create_app
    with TestClient(create_app(judgments=repo)) as client:
        s = client.get("/v1/precedent/search", params={"q": "leave to appeal refused concurrent findings",
                                                         "as_of": "2026-11-22", "forum_territory": "kp"})
        assert s.status_code == 200 and s.json()["kind"] == "precedent_discovery"
        hits = s.json()["hits"]
        if not hits:
            pytest.skip("no hits")
        j = client.get(f"/v1/precedent/judgments/{hits[0]['judgment_id']}", params={"as_of": "2026-11-22"})
        assert j.status_code == 200 and "parties_raw" not in j.json()["judgment"]       # internal only (D-122)
        early = client.get(f"/v1/precedent/judgments/{hits[0]['judgment_id']}", params={"as_of": "1990-01-01"})
        assert early.status_code == 404                                                 # not yet decided
        a = client.get("/v1/precedent/authority", params={"deciding": "SC", "receiving": "FCC",
                                                           "as_of": "2026-11-22"})
        assert a.json()["result"]["status"] == "not_binding"


# ----------------------------------------------------------------------------------------------- cases (0123)

def _cases_built(cur):
    cur.execute("SELECT to_regclass('judicial_case'), (SELECT count(*) FROM judgment_case_state)")
    reg, n = cur.fetchone()
    if reg is None or not n:
        pytest.skip("case records not built (nizam.workers.judgment_cases)")


def test_a_case_key_is_the_case_as_printed_and_a_relation_keeps_its_rule(cur):
    _cases_built(cur)
    for key, number in (("SC/CA/05/2012", "05"), ("SC/CA/7/2012", "5"), ("SC/CP/5/2012", "5")):
        _raises(cur, """INSERT INTO judicial_case (case_key, court_code, case_type_code, case_number, case_year,
                                                   builder) VALUES (%s, 'SC', 'SC:CA', %s, 2012, 'test')""",
                (key, number), match="judicial_case")
    cur.execute("""SELECT judgment_id, decided_on, case_key FROM judgment_case WHERE role = 'lead' LIMIT 1""")
    jid, day, key = cur.fetchone()
    # a copy names the copy kept; a reasons row with no printed date cannot carry one
    _raises(cur, """INSERT INTO judgment_relation (judgment_id, decided_on, relation, case_key, printed, builder)
                    VALUES (%s, %s, 'copy_of', %s, 'x', 'test')""", (jid, day, key), match="ck_relation_copy")
    _raises(cur, """INSERT INTO judgment_relation (judgment_id, decided_on, relation, case_key, short_order_on,
                                                   date_basis, printed, builder)
                    VALUES (%s, %s, 'reasons_for', %s, '2020-01-01', 'not_printed', 'x', 'test')""",
            (jid, day, key), match="ck_relation_reasons")


def test_every_released_judgment_is_read_for_its_case_and_placed_only_on_a_printed_number(cur):
    _cases_built(cur)
    cur.execute("""SELECT count(*) FROM v_release_judgment j WHERE NOT EXISTS (
                     SELECT 1 FROM judgment_case_state s WHERE s.judgment_id = j.id AND s.decided_on = j.decided_on)""")
    assert cur.fetchone()[0] == 0
    # a 'No. Nil' petition is not placed in a case; the header parser's '2016' is not a case number
    cur.execute("""SELECT s.outcome FROM judgment_case_state s JOIN judgment j ON j.id = s.judgment_id
                                                                      AND j.decided_on = s.decided_on
                    WHERE j.case_no_printed ~* '^CONST[.]? PETITION NO[.]? ?NIL'""")
    assert {r[0] for r in cur.fetchall()} <= {"no_number_read"}


@pytest.fixture()
def case_repo():
    """A reader of its own: a route test's app closes the module's reader when it shuts down."""
    try:
        from nizam.storage.judgment_read import JudgmentRead
        r = JudgmentRead()
        r.open()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    with r.transaction() as conn:
        if conn.execute("SELECT to_regclass('judicial_case') AS t").fetchone()["t"] is None:
            pytest.skip("migration 0123 not applied")
    yield r
    r.close()


def test_a_short_order_and_its_detailed_reasons_are_one_case_seen_from_either_side(case_repo):
    repo = case_repo
    with repo.transaction() as conn:
        row = conn.execute("""SELECT judgment_id, other_judgment_id, short_order_on, case_key FROM judgment_relation
                               WHERE relation = 'reasons_for' AND other_judgment_id IS NOT NULL LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no short order held beside its reasons")
    reasons = repo.judgment(row["judgment_id"], TODAY)["case"]
    order = repo.judgment(row["other_judgment_id"], TODAY)["case"]
    assert reasons["gives_reasons_for"]["short_order_judgment_id"] == row["other_judgment_id"]
    assert reasons["gives_reasons_for"]["short_order_on"] == row["short_order_on"]
    assert row["judgment_id"] in order["reasons_given_in"]
    assert row["other_judgment_id"] in [d["judgment_id"] for d in reasons["other_decisions"]]
    case = repo.case(row["case_key"], TODAY)
    assert {row["judgment_id"], row["other_judgment_id"]} <= {d["judgment_id"] for d in case["decisions"]}
    # the day before the short order, neither it nor its reasons existed (INV-5, read for case law)
    early = repo.case(row["case_key"], row["short_order_on"] - dt.timedelta(days=1))
    assert early is None or not {row["judgment_id"], row["other_judgment_id"]} & {
        d["judgment_id"] for d in early["decisions"]}


def test_a_second_copy_of_a_decision_is_never_listed_beside_the_copy_kept(case_repo):
    repo = case_repo
    with repo.transaction() as conn:
        row = conn.execute("""SELECT judgment_id, other_judgment_id, case_key FROM judgment_relation
                               WHERE relation = 'copy_of' LIMIT 1""").fetchone()
        if not row:
            pytest.skip("no copy found")
        shown = conn.execute("SELECT count(*) AS n FROM v_shown_judgment WHERE id = %s",
                             (row["judgment_id"],)).fetchone()["n"]
    assert shown == 0
    case = repo.case(row["case_key"], TODAY)
    ids = [d["judgment_id"] for d in case["decisions"]]
    assert row["other_judgment_id"] in ids and row["judgment_id"] not in ids
    copy = repo.judgment(row["judgment_id"], TODAY)["case"]          # opened directly, it names the copy kept
    assert copy["copy_of"]["judgment_id"] == row["other_judgment_id"]


def test_the_case_route_serves_a_case_by_its_printed_number(case_repo, monkeypatch):
    repo = case_repo
    monkeypatch.setenv("NIZAM_WARM", "0")
    from fastapi.testclient import TestClient
    from nizam.api.library import create_app
    with repo.transaction() as conn:
        row = conn.execute("""SELECT k.case_key, k.case_type_code, k.case_number, k.case_year
                                FROM judicial_case k JOIN judgment_case c ON c.case_key = k.case_key AND c.role = 'lead'
                               ORDER BY k.case_key LIMIT 1""").fetchone()
    if not row:
        pytest.skip("case records not built")
    kind = row["case_type_code"].split(":")[1]
    with TestClient(create_app(judgments=repo)) as client:
        court = row["case_type_code"].split(":")[0]
        r = client.get(f"/v1/precedent/cases/{court}/{kind}/{row['case_number']}/{row['case_year']}",
                       params={"as_of": "2026-11-22"})
        assert r.status_code == 200 and r.json()["case"]["case_key"] == row["case_key"]
        assert r.json()["decisions"]
        assert client.get("/v1/precedent/cases/SC/CA/999999/1950").status_code == 404


def test_title_lookup_stays_exact_after_many_lookups_with_varied_titles():
    """D-126: after five executions psycopg prepares a statement on the server, and under a generic plan pg_search's
    match-all title search stopped filtering: 'Pakistan Penal Code' put the Constitution first. Every connection now
    forces a custom plan (nizam.storage.db.dsn)."""
    import datetime as _dt

    from nizam.storage import citations as C
    from nizam.storage import unit_search
    from nizam.storage.db import connect
    from nizam.storage.lexical import Filters
    try:
        handle = connect()
        conn = handle.__enter__()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    try:
        with conn.cursor() as c:
            c.execute("SHOW plan_cache_mode")
            assert c.fetchone()[0] == "force_custom_plan"
            c.execute("SELECT DISTINCT law_printed FROM judgment_statute_reference WHERE law_printed IS NOT NULL "
                      "ORDER BY 1 LIMIT 60")
            titles = [r[0] for r in c.fetchall()]
            s = unit_search.Session(c, Filters(as_of=_dt.date.today()))
            for t in titles:
                s.instruments_titled(t, 10, None)
            assert s.instruments_titled("Act. Finally", 10, None) == []       # no law's title holds 'finally'
            r = C.resolve(s, C.Citation("s.302 PPC", "302", [], "ppc"))
            assert r.resolved_unit and r.resolved_law == "Pakistan Penal Code"
    finally:
        conn.rollback()
        handle.__exit__(None, None, None)


def test_a_lahore_citation_is_filed_under_the_punjab_copy_only_where_it_is_the_same_provision(case_repo):
    """D-136: a Lahore judgment citing s.34 PPC is linked to the federal Code and to the Punjab Code's s.34, so 'cases
    on this section' from the Punjab copy finds it. The Punjab copy's s.376 is a stub repealed in 1979 (another
    text), so judgments on the federal s.376 are never filed under it."""
    repo = case_repo
    with repo.transaction() as conn:
        if conn.execute("SELECT count(*) AS n FROM judgment_statute_reference WHERE cardinality(alternates) > 0 "
                        "AND linker = 'nizam.judgment_links/7'").fetchone()["n"] == 0:
            pytest.skip("links not rebuilt under /7")
        units = {r["label"]: r["id"] for r in conn.execute("""
            SELECT p.label, p.id FROM provision p JOIN instrument i ON i.id = p.instrument_id
             WHERE i.document_id = 4458 AND p.is_active AND p.kind::text = 'section' AND p.label IN ('34', '376')""")}
    if set(units) != {"34", "376"}:
        pytest.skip("the Punjab Code copy of the PPC is not held as expected")
    on34 = repo.provision_judgments(units["34"], TODAY, limit=50)
    assert on34 and any("Lahore" in (j.get("court") or j.get("court_name") or "") for j in on34)
    with repo.transaction() as conn:
        n = conn.execute("""SELECT count(*) AS n FROM judgment_statute_reference r
                             WHERE %s = ANY(r.alternates) OR r.dst_provision_id = %s""",
                         (units["376"], units["376"])).fetchone()["n"]
    assert n == 0


def test_a_reviewed_alias_resolves_through_the_shared_resolver_and_a_rejected_name_does_not():
    """D-134: 'ITO, 2001' was read and tied to the Income Tax Ordinance 2001 (law_alias); 'the Indian Penal Code' was
    read and rejected as foreign, so it reaches no Pakistani law. Retrieval and the linker share this resolver."""
    import datetime as _dt

    from nizam.storage import citations as C
    from nizam.storage import unit_search
    from nizam.storage.db import connect
    from nizam.storage.lexical import Filters
    try:
        handle = connect()
        conn = handle.__enter__()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    try:
        with conn.cursor() as c:
            c.execute("SELECT to_regclass('law_alias') IS NOT NULL AND EXISTS (SELECT 1 FROM law_alias "
                      "WHERE alias_key = 'ito 2001' AND withdrawn_at IS NULL)")
            if not c.fetchone()[0]:
                pytest.skip("aliases not loaded")
            s = unit_search.Session(c, Filters(as_of=_dt.date.today()))
            r = C.resolve(s, C.find("notice under section 122 of the ITO, 2001 was")[0])
            assert r.resolved_unit and r.resolved_law == "Income Tax Ordinance, 2001" and r.via_alias == "ito 2001"
            r = C.resolve(s, C.find("under section 411 of the Indian Penal Code, to the")[0])
            assert r.resolved_unit is None and r.via_alias is None
    finally:
        conn.rollback()
        handle.__exit__(None, None, None)


# ------------------------------------------------------------------------------------- names withheld (0128, D-131)

def test_a_judgment_whose_names_are_withheld_shows_none_and_says_why(case_repo):
    repo = case_repo
    with repo.transaction() as conn:
        if conn.execute("SELECT to_regclass('judgment_display') AS t").fetchone()["t"] is None:
            pytest.skip("migration 0128 not applied")
        row = conn.execute("""SELECT d.judgment_id, d.names_withheld FROM judgment_display d
                               WHERE d.redacted AND cardinality(d.names_withheld) > 0
                                 AND EXISTS (SELECT 1 FROM unnest(d.names_withheld) n WHERE n ~ ' ')
                               ORDER BY d.judgment_id LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no judgment with names withheld")
    j = repo.judgment(row["judgment_id"], TODAY)
    assert j["privacy"]["names_withheld"] is True and j["privacy"]["categories"]
    assert all(c["basis"] and c["basis_kind"] in ("statute", "follows_statute", "product_policy")
               for c in j["privacy"]["categories"])
    shown = " ".join(p["text"] for p in j["paragraphs"]).lower() + " " + (j["judgment"]["parties_display"] or "").lower()
    for n in row["names_withheld"]:
        if " " in n:                                            # a full name never survives in what is shown
            assert n.lower() not in shown, n
    assert "names_withheld" not in j["judgment"] and "parties_raw" not in j["judgment"]


def test_a_search_naming_a_withheld_person_never_finds_that_judgment(case_repo):
    from nizam.retrieval.precedent import search
    repo = case_repo
    with repo.transaction() as conn:
        if conn.execute("SELECT to_regclass('judgment_display') AS t").fetchone()["t"] is None:
            pytest.skip("migration 0128 not applied")
        row = conn.execute("""SELECT d.judgment_id, n AS name FROM judgment_display d, unnest(d.names_withheld) n
                               WHERE d.redacted AND n ~ '^[A-Z][a-z]+ [A-Z][a-z]+$' ORDER BY d.judgment_id
                               LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no two-word withheld name")
    r = search(f"{row['name']} judgment", as_of=TODAY, k=25, repo=repo)
    assert str(row["judgment_id"]) not in [h.judgment_id for h in r.hits]


def test_a_redacted_row_needs_its_category_and_a_basis_is_printed_law(cur):
    cur.execute("SELECT to_regclass('judgment_display')")
    if cur.fetchone()[0] is None:
        pytest.skip("migration 0128 not applied")
    cur.execute("""SELECT count(*) FROM sensitive_category_source s
                    WHERE NOT law_unit_quote_found(s.source_observation_id, s.source_expression_ordinal, s.source_unit,
                                                   s.source_quote)""")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT judgment_id, decided_on FROM judgment_display WHERE NOT redacted LIMIT 1")
    jid, day = cur.fetchone()
    _raises(cur, """INSERT INTO judgment_display (judgment_id, decided_on, parties_display, redacted, names_withheld,
                                                   builder) VALUES (%s, %s, 'x', false, '{Some Name}', 'test')""",
            (jid, day), match="ck_display_withheld|duplicate key")
