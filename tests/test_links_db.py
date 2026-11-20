"""D-108 against the corpus: the derived link tables (0114, 0115). Asserts the RULES on known provisions -- the phrase
is the edge kind, a reference resolves in its own law or the law it names, a definition keeps its scope and its
flattened sub-items, a schedule's heading is read -- never today's counts (audit A23 owns completeness)."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def cur():
    from nizam.storage.db import connect
    try:
        ctx = connect()
        conn = ctx.__enter__()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    try:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM provision_link_state")
        if c.fetchone()[0] == 0:
            pytest.skip("the link tables are not built (python -m nizam.workers.links --apply)")
        yield c
    finally:
        ctx.__exit__(None, None, None)


def _unit(cur, title_re, label, year=None, kind="section"):
    cur.execute("""SELECT p.id FROM provision p JOIN instrument i ON i.id = p.instrument_id
                    WHERE i.is_active AND i.duplicate_of IS NULL AND i.short_title ~* %s
                      AND (%s::int IS NULL OR i.year = %s) AND p.is_active AND p.kind::text = %s AND p.label = %s
                    ORDER BY i.jurisdiction = 'fed' DESC LIMIT 1""", (title_re, year, year, kind, label))
    r = cur.fetchone()
    if r is None:
        pytest.skip(f"{title_re} {label} not in this corpus")
    return r[0]


def _refs_from(cur, unit):
    cur.execute("""SELECT r.kind::text, r.dst_unit_id, r.in_heading FROM provision_reference r
                    JOIN provision n ON n.id = r.src_provision_id JOIN provision u ON u.id = %s
                   WHERE n.instrument_id = u.instrument_id AND n.path <@ u.path""", (unit,))
    return cur.fetchall()


def test_a_non_obstante_clause_is_a_notwithstanding_edge(cur):
    # Registration Act 1908 s.30(2): 'Notwithstanding anything contained in section 28 ...'
    s30, s28 = _unit(cur, r"^Registration Act", "30", 1908), _unit(cur, r"^Registration Act", "28", 1908)
    assert ("notwithstanding", s28, False) in _refs_from(cur, s30)


def test_a_reference_into_another_law_resolves_to_that_law(cur):
    # CrPC s.140: 'the penalty provided by section 188 of the Pakistan Penal Code'
    crpc140 = _unit(cur, r"^(The )?Code of Criminal Procedure", "140", 1898)
    ppc188 = _unit(cur, r"^Pakistan Penal Code", "188")
    assert ppc188 in {dst for _k, dst, _h in _refs_from(cur, crpc140)}


def test_a_schedule_heading_names_its_section(cur):
    # The Family Courts Act 1964's Schedule prints '[see SECTION 5]' as its heading (0115)
    sched = _unit(cur, r"^The Family Courts Act", "SCHEDULE", 1964, kind="schedule")
    s5 = _unit(cur, r"^The Family Courts Act", "5", 1964)
    assert ("refers_to", s5, True) in _refs_from(cur, sched)


def test_definitions_keep_their_scope_and_flattened_sub_items(cur):
    cur.execute("""SELECT d.scope, cardinality(d.continuation), d.empty FROM provision_definition d
                    JOIN instrument i ON i.id = d.instrument_id
                   WHERE i.is_active AND i.short_title ~* '^Copyright Ordinance' AND i.year = 1962
                     AND d.term_key = 'government work'""")
    row = cur.fetchone()
    if row is None:
        pytest.skip("Copyright Ordinance 1962 not in this corpus")
    assert row[0] == "law" and row[1] >= 2 and row[2] is False        # its (i), (ii) are siblings in the tree
    # PPC s.489A Explanation: 'For the purposes of this section ... "bank-note" means' -> its own unit only
    cur.execute("""SELECT d.scope FROM provision_definition d JOIN instrument i ON i.id = d.instrument_id
                    WHERE i.is_active AND i.short_title ~* '^Pakistan Penal Code' AND d.term_key ~ '^bank.?note$'""")
    scopes = {r[0] for r in cur.fetchall()}
    if scopes:
        assert scopes == {"unit"}


def test_an_amending_law_contributes_no_definitions(cur):
    # the rule reads the law's own title (display title): a consolidated text whose portal label says
    # '(Amendment-2026)' is the law as amended, and keeps its definitions
    cur.execute("""SELECT count(*) FROM provision_definition d JOIN instrument i ON i.id = d.instrument_id
                    WHERE coalesce(nullif(i.display_title, ''), i.short_title)
                          ~* '\\m(amendment|amending|adaptation|repealing)\\M|\\mfinance (act|ordinance)\\M'""")
    assert cur.fetchone()[0] == 0
