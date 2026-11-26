"""L5 precedent context (D-173, docs/ANSWER-COMPOSITION §5 stage 3): the law join, authority, adverse status, the
version note and coverage. The database tests skip when the corpus is not reachable."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from nizam.domain.precedent import PrecedentAbstention, PrecedentContext, context_for, seed_from

TODAY = dt.date(2026, 11, 27)


def test_only_known_codes_abstain():
    with pytest.raises(ValueError):
        PrecedentAbstention("LOW_CONFIDENCE", "x", [])
    assert PrecedentAbstention("NO_PRECEDENT_FOUND", "x", []).code == "NO_PRECEDENT_FOUND"


def test_as_of_is_mandatory():
    with pytest.raises(ValueError):
        context_for("bail", as_of=dt.datetime(2026, 11, 27))


def test_the_seed_comes_from_a_passed_context_or_the_nearest_units_never_from_a_veto():
    from nizam.retrieval.gate import GroundingContext
    item = SimpleNamespace(unit_id="u1")
    ctx = GroundingContext.__new__(GroundingContext)
    object.__setattr__(ctx, "items", (item, SimpleNamespace(unit_id="u2")))
    assert seed_from(ctx) == dict(seed_units=["u1", "u2"], seed_kind="context")
    assert seed_from(SimpleNamespace(nearest=(item,))) == dict(seed_units=["u1"], seed_kind="nearest")
    assert seed_from(SimpleNamespace(nearest=())) == dict(seed_units=[], seed_kind="none")    # a veto searched nothing
    assert seed_from(None)["seed_kind"] == "none"


# ------------------------------------------------------------------------------------------------------ database

@pytest.fixture(scope="module")
def repo():
    try:
        from nizam.storage.judgment_read import JudgmentRead
        r = JudgmentRead()
        r.open()
        with r.transaction() as conn:
            if not conn.execute("SELECT EXISTS (SELECT 1 FROM v_release_judgment) AS h").fetchone()["h"]:
                pytest.skip("no judgment released")
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    yield r
    r.close()


@pytest.fixture(scope="module")
def s497(repo):
    from nizam.retrieval.precedent import search
    r = search("section 497 CrPC", as_of=TODAY, k=1, repo=repo)
    if not r.cited_provisions:
        pytest.skip("section 497 CrPC not resolved")
    return r.cited_provisions[0]["provision_id"]


def test_the_law_join_reaches_judgments_the_question_does_not_name(repo, s497):
    from nizam.storage.authority import Subordinate
    q = "When does a case call for further inquiry so that the accused gets bail?"      # names no section
    ctx = context_for(q, as_of=TODAY, forum=Subordinate("punjab"), seed_units=[s497], seed_kind="context", k=10,
                      repo=repo, law_join=True)
    assert isinstance(ctx, PrecedentContext) and not ctx.gated          # discovery until the precedent gate (S2)
    assert ctx.trace["search"]["generators"].get("law"), "the law generator ran"
    assert any("law" in i.generators for i in ctx.items)
    for i in ctx.items:
        assert (i.decided_on or i.decided_no_later_than) <= TODAY                       # INV-5
        assert i.authority and i.authority["status"] in ("binding", "not_binding", "not_recorded")
        assert set(i.interprets) <= {s497}
        assert set(i.interprets.values()) <= {"earlier_text", "same_text", "not_dated"}
        assert isinstance(i.awaiting_review, tuple)
    assert ctx.coverage                                                  # nothing found is "in this coverage"


def test_without_a_seed_it_is_the_search_alone(repo):
    ctx = context_for("further inquiry bail", as_of=TODAY, k=5, repo=repo)
    if isinstance(ctx, PrecedentAbstention):
        pytest.skip("nothing found")
    assert "law" not in ctx.trace["search"]["generators"] and ctx.seed["kind"] == "none"


def test_by_default_the_seed_marks_judgments_but_does_not_choose_them(repo, s497):
    q = "When does a case call for further inquiry so that the accused gets bail?"
    plain = context_for(q, as_of=TODAY, k=5, repo=repo)
    seeded = context_for(q, as_of=TODAY, seed_units=[s497], seed_kind="context", k=5, repo=repo)
    if isinstance(plain, PrecedentAbstention):
        pytest.skip("nothing found")
    assert [i.judgment_id for i in seeded.items] == [i.judgment_id for i in plain.items]   # D-173: join off
    assert "law" not in seeded.trace["search"]["generators"] and seeded.trace["law_join"] is False
    assert all(set(i.interprets) <= {s497} for i in seeded.items)


def test_a_verified_adverse_judgment_is_excluded_and_a_machine_reading_is_only_carried(repo, s497, monkeypatch):
    q = "When does a case call for further inquiry so that the accused gets bail?"
    first = context_for(q, as_of=TODAY, seed_units=[s497], seed_kind="context", k=5, repo=repo)
    if isinstance(first, PrecedentAbstention):
        pytest.skip("nothing found")
    bad, pending = first.items[0].judgment_id, first.items[1].judgment_id if len(first.items) > 1 else None
    real = repo.adverse_status

    def fake(jids, as_of):
        out = real(jids, as_of)
        if bad in out:
            out[bad] = {"verified": [dict(kind="treatment", what="overruled", by="x", on=TODAY)],
                        "awaiting_review": []}
        if pending in out:
            out[pending] = {"verified": [], "awaiting_review": [dict(kind="appeal", what="set_aside", by="y",
                                                                       on=TODAY)]}
        return out
    monkeypatch.setattr(repo, "adverse_status", fake)
    ctx = context_for(q, as_of=TODAY, seed_units=[s497], seed_kind="context", k=5, repo=repo)
    assert bad not in [i.judgment_id for i in ctx.items]
    assert any(e["judgment_id"] == bad for e in ctx.trace["excluded_adverse"])
    if pending:
        carried = [i for i in ctx.items if i.judgment_id == pending]
        assert carried and carried[0].awaiting_review[0]["what"] == "set_aside"     # carried, not acted on


def test_adverse_status_reads_only_what_existed_by_the_date(repo):
    with repo.transaction() as conn:
        row = conn.execute("""SELECT k.lower_judgment_id::text AS j, k.upper_decided_on AS d
                                FROM judgment_lineage_link k JOIN judgment_lineage l ON l.id = k.lineage_id
                               WHERE k.lower_judgment_id IS NOT NULL
                                 AND l.outcome IN ('set_aside','reversed','modified','remanded') LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no linked adverse appeal outcome")
    after = repo.adverse_status([row["j"]], row["d"])[row["j"]]
    assert after["verified"] or after["awaiting_review"]
    before = repo.adverse_status([row["j"]], row["d"] - dt.timedelta(days=1))[row["j"]]
    assert not [x for x in before["verified"] + before["awaiting_review"] if x["on"] == row["d"]]


def test_the_law_join_orders_by_the_question_and_keeps_to_the_date(repo, s497):
    from nizam.inference.encoder import encoder
    try:
        bits = encoder().bits("when does a bail case call for further inquiry")
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"no CPU encoder: {type(exc).__name__}")
    as_of = dt.date(2020, 1, 1)
    with repo.transaction() as conn:
        rows = repo.citing_paragraphs_by_question(conn, [s497], bits, 20, as_of)
    if not rows:
        pytest.skip("no citing paragraph by 2020")
    assert all(r["decided_on"] <= as_of for r in rows)
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)                        # nearest first
    assert len({r["judgment_id"] for r in rows}) == len(rows)            # one paragraph per judgment
