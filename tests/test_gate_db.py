"""D-102 against the corpus: the retrieval port end to end -- the question parsed, vetoed or searched, reranked, gated.
Asserts the RULES (two values; a passing context holds only operative units of the bundle, with its decision recorded;
an unreranked result is gated only by its own calibration; no province guessed), never today's counts. Invented
questions only: the golden test split is scored once, elsewhere."""
from __future__ import annotations

from datetime import date

import pytest

from nizam.retrieval import gate as G
from nizam.storage.lexical import Filters

AS_OF = date(2026, 11, 16)


@pytest.fixture(scope="module")
def live():
    try:
        from nizam.storage.db import connect
        with connect() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunk LIMIT 1")
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    if not G.CALIBRATION.exists():
        pytest.skip("no gate calibration shipped")
    return connect


def _operative(connect, filters, items):
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                    (filters.as_of.isoformat(), filters.territory or ""))
        cur.execute("SELECT count(DISTINCT version_id) FROM operative_provision WHERE version_id = ANY(%s::uuid[])",
                    ([i.version_id for i in items],))
        return cur.fetchone()[0]


@pytest.mark.parametrize("q,filters", [
    ("Can my landlord in Lahore evict me for not paying rent?", Filters(as_of=AS_OF, jurisdictions=("punjab", "fed"))),
    ("s.302 PPC", Filters(as_of=AS_OF, jurisdictions=("fed",))),
    ("What is the gold price today?", Filters(as_of=AS_OF, jurisdictions=("fed",))),
])
def test_the_port_is_two_valued_and_a_context_is_operative(live, monkeypatch, q, filters):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "cpu")
    monkeypatch.setenv("NIZAM_RERANK_PROFILE", "cpu")
    out = G.retrieve(q, filters)
    assert type(out) in (G.GroundingContext, G.Abstention)
    assert out.gate["decision"] in ("pass", "abstain") and out.gate["calibration"]
    if isinstance(out, G.GroundingContext):
        assert 0 < len(out.items) <= G.BUNDLE and out.confidence >= out.threshold
        assert _operative(live, filters, out.items) == len({i.version_id for i in out.items})     # INV-5
        assert out.gate["features"]["top"] is not None and "rerank" in out.trace                   # INV-3
    else:
        assert out.public_reason and out.suggestions


def test_vetoes_answer_without_searching(live):
    f = Filters(as_of=AS_OF, jurisdictions=("fed",))
    assert G.retrieve("What did the Supreme Court decide in the Panama Papers case?", f).code == "CORPUS_GAP"
    assert G.retrieve("What is the punishment for theft in Dubai?", f).code == "CORPUS_GAP"


def test_unreranked_is_gated_only_by_its_own_calibration(live, monkeypatch):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "cpu")
    monkeypatch.setenv("NIZAM_RERANK_PROFILE", "off")
    out = G.retrieve("Can my landlord in Lahore evict me for not paying rent?",
                     Filters(as_of=AS_OF, jurisdictions=("punjab", "fed")))
    if "unreranked" in G.calibration()["modes"]:
        assert out.gate.get("mode") == "unreranked"
    else:
        assert isinstance(out, G.Abstention) and out.code == "RETRIEVAL_DEGRADED"


def test_no_province_is_guessed_for_an_unplaced_question(live, monkeypatch):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "cpu")
    monkeypatch.setenv("NIZAM_RERANK_PROFILE", "cpu")
    out = G.retrieve("Can my landlord evict me for not paying rent?", Filters(as_of=AS_OF))
    if isinstance(out, G.GroundingContext):
        from nizam.storage import unit_search
        with unit_search.session(out.filters) as s:
            j = s.instrument_jurisdictions([i.instrument_id for i in out.items[:G.CONC_OF]])
        assert len(set(j.values()) - {"fed"}) <= 1
    else:
        assert out.code in ("JURISDICTION_UNRESOLVED", "INSUFFICIENT_EVIDENCE")
