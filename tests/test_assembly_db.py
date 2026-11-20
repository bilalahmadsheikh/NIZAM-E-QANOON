"""D-107 against the corpus: evidence assembly (docs/04 §7). Asserts the RULES -- every node served is law at the
date and place (INV-5); a bundle unit never vanishes without a recorded reason; items are whole, citable units in the
law's own order, with citations rendered from records (INV-1) -- and the defects found on dev, as regressions.
Invented questions and hand-picked units only: the golden test split is assembled once, elsewhere."""
from __future__ import annotations

from datetime import date

import pytest

from nizam.retrieval import gate as G
from nizam.retrieval.assembly import ROLE_RANK, assemble
from nizam.retrieval.query import parse
from nizam.storage.lexical import Filters

AS_OF = date(2026, 11, 16)
PUNJAB = Filters(as_of=AS_OF, territory="punjab")
WOMEN_PROPERTY_S4 = "87dac419-ea29-43a2-b70d-3cb09faafdf2"    # Punjab Enforcement of Women's Property Rights Act 2021


@pytest.fixture(scope="module")
def db():
    try:
        from nizam.storage.db import connect
        with connect() as c, c.cursor() as cur:
            cur.execute("SELECT 1 FROM provision WHERE id = %s", (WOMEN_PROPERTY_S4,))
            if cur.fetchone() is None:
                pytest.skip("the corpus does not hold the fixture unit")
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    return connect


def _one(db, sql, args=()):
    with db() as c, c.cursor() as cur:
        cur.execute(sql, args)
        row = cur.fetchone()
    if row is None:
        pytest.skip("fixture not found in this corpus")
    return row


def _ctx(units, filters, q="question"):
    items = tuple(G.BundleItem(u, "", "", i + 1, None, 0.0, False) for i, u in enumerate(units))
    return G.GroundingContext(parse(q), filters, items, 1.0, 0.5, {"decision": "pass"}, {})


def _operative(db, filters, version_ids):
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                    (filters.as_of.isoformat(), filters.territory or ""))
        cur.execute("SELECT version_id::text FROM operative_provision WHERE version_id = ANY(%s::uuid[])",
                    (list(version_ids),))
        return {r[0] for r in cur.fetchall()}


def _check_packet(db, out, bundle):
    ev = out.evidence
    assert ev, "a passing context carries evidence"
    vids = [nd[1] for it in ev for nd in it.nodes]
    assert _operative(db, out.filters, vids) == set(vids)                          # INV-5, asked independently
    assert all(it.role in ROLE_RANK and it.citation and it.text for it in ev)      # INV-1: rendered, never blank
    accounted = {it.unit_id for it in ev} | {it.provision_id for it in ev}
    accounted |= {o["provision"] for o in out.coverage["omitted"]} | set(out.coverage["not_operative"])
    accounted |= {d["division"] for d in out.coverage.get("divisions", [])}
    assert set(bundle) <= accounted                                                  # nothing vanishes silently
    order = [it.order for it in ev]
    assert order == sorted(order)                                                    # the law's own order
    laws = [it.instrument_id for it in ev]
    assert all(laws.index(x) <= i and (laws.index(x) == i or laws[i - 1] == x) for i, x in enumerate(laws))
    assert out.coverage["used_chars"] <= out.coverage["budget_chars"] or out.coverage["over_budget"]


def test_a_unit_is_assembled_whole_with_its_definitions_and_the_section_it_names(db):
    out = assemble(_ctx([WOMEN_PROPERTY_S4], PUNJAB))
    _check_packet(db, out, [WOMEN_PROPERTY_S4])
    gov = [it for it in out.evidence if it.role == "governing"]
    assert [it.unit_id for it in gov] == [WOMEN_PROPERTY_S4]
    assert gov[0].citation.endswith("Act, 2021, s. 4") and "Provided that" in gov[0].text   # the proviso is in
    defs = {it.citation.rsplit(", ", 1)[-1] for it in out.evidence if it.role == "definition"}
    assert {"s. 2(a)", "s. 2(c)", "s. 2(e)"} <= defs          # complainant, Ombudsperson, property: s.4 uses them
    assert any(it.role == "reference" and it.citation.endswith("s. 5") for it in out.evidence)
    assert gov[0].law["jurisdiction"] == "punjab" and gov[0].source["sha256"] and gov[0].source["pages"]


def test_a_unit_that_is_not_law_in_the_territory_is_not_served(db):
    # the federal Enforcement of Women's Property Rights Act 2020 extends to Islamabad only: not law in Punjab
    (ict,) = _one(db, """SELECT p.id::text FROM provision p JOIN instrument i ON i.id = p.instrument_id
                          WHERE i.is_active AND i.duplicate_of IS NULL AND i.jurisdiction = 'fed'
                            AND i.short_title ILIKE 'Enforcement of Women%%Property Rights Act%%' AND i.year = 2020
                            AND p.is_active AND p.kind = 'section' AND p.label = '4'""")
    assert assemble(_ctx([ict], PUNJAB)) is None
    mixed = assemble(_ctx([ict, WOMEN_PROPERTY_S4], PUNJAB))
    assert mixed.coverage["not_operative"] == [ict]
    assert ict not in {it.unit_id for it in mixed.evidence}


def test_a_constitution_is_cited_by_article(db):
    (art,) = _one(db, """SELECT p.id::text FROM provision p JOIN instrument i ON i.id = p.instrument_id
                          WHERE i.is_active AND i.duplicate_of IS NULL AND i.kind = 'constitution'
                            AND i.jurisdiction = 'fed' AND p.is_active AND p.kind = 'section' AND p.label = '25'
                          LIMIT 1""")
    out = assemble(_ctx([art], Filters(as_of=AS_OF)))
    _check_packet(db, out, [art])
    gov = next(it for it in out.evidence if it.role == "governing")
    assert gov.citation.endswith("Art. 25") and "Section" not in gov.inclusion_reason


def test_a_chapter_definition_stays_in_its_chapter(db):
    # Art. 203B defines 'Court' as the Federal Shariat Court 'In this Chapter' (3A); the tree folds 3A into Chapter 3,
    # so the rule 'only units printed after the definition' is what keeps it off the High Courts' Art. 192
    (art,) = _one(db, """SELECT p.id::text FROM provision p JOIN instrument i ON i.id = p.instrument_id
                          WHERE i.is_active AND i.duplicate_of IS NULL AND i.kind = 'constitution'
                            AND i.jurisdiction = 'fed' AND p.is_active AND p.kind = 'section' AND p.label = '192'
                          LIMIT 1""")
    out = assemble(_ctx([art], Filters(as_of=AS_OF)))
    _check_packet(db, out, [art])
    assert not any("Art. 203B" in it.citation for it in out.evidence if it.role == "definition")


def test_a_flattened_definition_carries_its_sub_items(db):
    # Copyright Ordinance 1962 s.2(m) 'Government work' ... 'control of__': its (i) and (ii) are siblings in the tree
    (unit,) = _one(db, """SELECT p.id::text FROM provision p JOIN instrument i ON i.id = p.instrument_id
                           WHERE i.is_active AND i.duplicate_of IS NULL AND i.short_title ~* '^Copyright Ordinance'
                             AND i.year = 1962 AND p.is_active AND p.kind = 'section' AND p.label = '22' LIMIT 1""")
    out = assemble(_ctx([unit], Filters(as_of=AS_OF, jurisdictions=("fed",))))
    _check_packet(db, out, [unit])
    gw = [it for it in out.evidence if it.role == "definition" and "Government work" in it.text]
    if not gw:
        pytest.skip("section 22 does not use 'Government work' in this corpus")
    assert "department of the Government" in gw[0].text and len(gw[0].nodes) >= 3


def test_a_chapter_in_the_bundle_is_replaced_by_its_sections(db):
    # retrieval maps a match on a Chapter's heading to the Chapter; INV-4: its sections are the citable units
    (chap,) = _one(db, """SELECT p.id::text FROM provision p JOIN instrument i ON i.id = p.instrument_id
                           WHERE i.is_active AND i.duplicate_of IS NULL AND i.jurisdiction = 'fed'
                             AND i.short_title ILIKE 'Sales Tax Act%%' AND i.year = 1990
                             AND p.is_active AND p.kind = 'chapter' AND p.label = 'II' LIMIT 1""")
    out = assemble(_ctx([chap], Filters(as_of=AS_OF, jurisdictions=("fed",))))
    _check_packet(db, out, [chap])
    assert chap not in {it.unit_id for it in out.evidence}
    gov = [it for it in out.evidence if it.role == "governing"]
    assert 1 <= len(gov) <= 5 and all(", s. " in it.citation for it in gov)
    assert all(len(it.text) >= 40 for it in gov)                                  # no '[Omitted]' stubs
    div = out.coverage["divisions"][0]
    assert div["division"] == chap and div["taken"] == len(gov)


def test_the_port_returns_an_assembled_context(db, monkeypatch):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "cpu")
    monkeypatch.setenv("NIZAM_RERANK_PROFILE", "cpu")
    if not G.CALIBRATION.exists():
        pytest.skip("no gate calibration shipped")
    f = Filters(as_of=AS_OF, jurisdictions=("punjab", "fed"))
    out = G.retrieve("My brothers in Lahore will not give my share of our father's house. Can a woman complain "
                     "to the Ombudsperson?", f)
    assert type(out) in (G.GroundingContext, G.Abstention)
    if isinstance(out, G.GroundingContext):
        _check_packet(db, out, [b.unit_id for b in out.items])
        assert out.coverage["assembly_ms"] > 0 and out.coverage["not_built"]
        bare = G.retrieve("My brothers in Lahore will not give my share of our father's house. Can a woman "
                          "complain to the Ombudsperson?", f, assemble=False)
        assert isinstance(bare, G.GroundingContext) and bare.evidence == ()
