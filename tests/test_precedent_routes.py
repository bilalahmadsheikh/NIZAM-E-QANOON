"""D-184: the app's precedent routes, typed. The route rules are checked against a fake reader (no database): a
machine-read outcome is withheld until a lawyer verifies it, internal fields never leave the API, lists state what
they were drawn from, paging is exact, and a stale cursor is a 400 that tells the reader to refresh. The database
tests at the end check ordering and paging against nizam_clean and skip when it is not reachable."""
from __future__ import annotations

from datetime import date

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from nizam.api import precedent as R  # noqa: E402

JID = "11111111-1111-1111-1111-111111111111"
PID = "22222222-2222-2222-2222-222222222222"
DAY = date(2026, 11, 27)


def _card(i: int, **extra) -> dict:
    return dict(judgment_id=f"00000000-0000-0000-0000-{i:012d}", citation=f"Lahore High Court, W.P. {i} of 2025, "
                f"decided 1 Jan 2025", court="Lahore High Court", case_type="Writ Petition", case_key=None,
                decided_on=date(2025, 1, 1), undated=False, decided_no_later_than=None, decided_not_before=None,
                undated_reason=None, parties_display="A v. B", names_withheld=False, disposition="dismissed",
                reported=False, mentions=2, roles=["cited"], **extra)


class FakeRead:
    def __init__(self):
        self.asked = []

    def courts(self):
        return [dict(code="SC", name="Supreme Court of Pakistan", court_class="apex", judgments=3205,
                     first_decided=date(2002, 4, 10), last_decided=date(2026, 11, 19)),
                dict(code="BHC", name="High Court of Balochistan", court_class="high_court", judgments=0,
                     first_decided=None, last_decided=None)]

    def court_judgments(self, court, day, limit, after):
        self.asked.append(("court", court, after))
        return [_card(1), _card(2)], (False, date(2025, 1, 1), _card(2)["judgment_id"])

    def citing(self, scope, day, limit, order, offset):
        self.asked.append(("citing", scope[0], order, offset))
        items = [_card(i) for i in range(offset, min(offset + limit, 7))]
        return dict(items=items, total=7)

    def judicial_status(self, ident, day):
        return dict(verified=[], candidates_awaiting_review=2, coverage="only lawyer-verified readings are stated")

    def judgment(self, jid, as_of):
        if as_of < date(2025, 1, 1):
            return None
        head = dict(id=JID, court_code="LHC", court_name="Lahore High Court", seat="Lahore",
                    case_no_printed="W.P. 1 of 2025", case_type_name="Writ Petition", case_number="1", case_year=2025,
                    decided_on=date(2025, 1, 1), undated=False, decided_no_later_than=None, decided_not_before=None,
                    undated_reason=None, hearing_on=None, bench_printed=["Justice X"], bench_size=1,
                    disposition="dismissed", disposition_printed="Dismissed.", reported_flag=False,
                    neutral_citation=None, parties_display="A v. B", jurisdiction_printed=None, source_url=None,
                    parties_raw="internal", parser="nizam.judgment/17", document_id=9)
        return dict(
            judgment=head, citation="Lahore High Court, W.P. 1 of 2025, decided 1 Jan 2025",
            opinions=[dict(ordinal=1, kind="majority", heading_printed=None, author_printed="X, J.")],
            paragraphs=[dict(id="p1", kind="body", printed_no="1", page_first=1, text="The petition fails.",
                             opinion=1, opinion_kind="majority", citation="Lahore High Court, W.P. 1, para 1")],
            lineage=[dict(relation="appeal_from", lower_court_code=None, lower_court_printed="Civil Judge",
                          lower_case_printed="Suit 4 of 2020", lower_decided_on=date(2021, 1, 1),
                          outcome="set_aside", review_status="machine_candidate"),
                     dict(relation="appeal_from", lower_court_code=None, lower_court_printed="District Judge",
                          lower_case_printed="Appeal 9 of 2022", lower_decided_on=date(2023, 1, 1),
                          outcome="affirmed", review_status="lawyer_verified")],
            cases_cited=[dict(raw="PLD 2016 SC 1", resolution="resolved", dst_judgment_id=JID, dst_case_key=None),
                         dict(raw="PLD 2016 SC 1", resolution="resolved", dst_judgment_id=JID, dst_case_key=None),
                         dict(raw="2010 SCMR 9", resolution="not_held", dst_judgment_id=None, dst_case_key=None)],
            statutes_cited=[dict(dst_provision_id=PID, citation="Code of Civil Procedure, 1908, s. 12(2)", label="12",
                                 kind="section", short_title="Code of Civil Procedure", year=1908, role="interpreted",
                                 mentions=3, status_now="amended_since")],
            case=dict(status="placed", cases_decided=[], other_decisions=[], copy_of=None),
            privacy=dict(names_withheld=False, categories=[]))

    def citing_judgments(self, jid, day, limit):
        return [_card(5, treatments=["followed"], treatments_awaiting_review=1, cited_as="PLD 2016 SC 1")]

    def later_history(self, jid, day):
        return [dict(source="upper_judgment", judgment_id=JID, court="Supreme Court of Pakistan", relation="appeal",
                     outcome=None, outcome_withheld="awaiting lawyer review", decided_on=date(2026, 2, 1),
                     citation="Supreme Court of Pakistan, C.A. 1 of 2026, decided 1 Feb 2026")]


@pytest.fixture()
def app():
    a = FastAPI()
    fake = FakeRead()
    R.register(a, fake, lambda v: v or DAY)
    a.state.fake = fake
    return a


def test_a_machine_read_outcome_waits_for_a_lawyer_and_internal_fields_never_leave(app):
    j = TestClient(app).get(f"/v1/precedent/judgments/{JID}").json()
    below = {a["court_below"]: a for a in j["appeal_from"]}
    assert below["Civil Judge"]["outcome"] is None and below["Civil Judge"]["outcome_withheld"] is True
    assert below["District Judge"]["outcome"] == "affirmed" and below["District Judge"]["outcome_withheld"] is False
    assert not {"parties_raw", "parser", "document_id"} & set(j["judgment"])           # internal only (D-122)
    assert [c["raw"] for c in j["cases_cited"]] == ["PLD 2016 SC 1", "2010 SCMR 9"]     # each printed once
    assert j["statutes_cited"][0]["provision_id"] == PID and j["statutes_cited"][0]["status_now"] == "amended_since"
    assert j["note"].startswith("Judgments, as the courts published them")


def test_a_judgment_not_yet_decided_on_the_date_is_not_found(app):
    assert TestClient(app).get(f"/v1/precedent/judgments/{JID}", params={"as_of": "2020-01-01"}).status_code == 404


def test_citing_lists_page_exactly_and_default_to_the_newest(app):
    c = TestClient(app)
    first = c.get(f"/v1/law/provisions/{PID}/judgments", params={"limit": 3}).json()
    assert first["order"] == "recent" and first["total"] == 7 and first["next_offset"] == 3
    assert first["judicial_status"]["candidates_awaiting_review"] == 2
    last = c.get(f"/v1/law/provisions/{PID}/judgments", params={"limit": 3, "offset": 6}).json()
    assert len(last["items"]) == 1 and last["next_offset"] is None
    law = c.get(f"/v1/law/instruments/{PID}/judgments", params={"order": "relevant"}).json()
    assert law["scope"] == "instrument" and law["judicial_status"] is None
    assert ("citing", "instrument", "relevant", 0) in app.state.fake.asked
    assert c.get(f"/v1/law/provisions/{PID}/judgments", params={"order": "oldest"}).status_code == 422


def test_every_list_says_what_it_was_drawn_from(app):
    c = TestClient(app)
    courts = c.get("/v1/precedent/courts").json()
    assert courts["total_judgments"] == 3205 and courts["items"][1]["judgments"] == 0    # held none: listed, 0
    assert courts["coverage_note"].startswith("From 3,205 judgments of 1 courts held, decided 2002–2026")
    assert "not proof that nothing else was decided" in courts["coverage_note"]
    for path in (f"/v1/law/provisions/{PID}/judgments", f"/v1/precedent/judgments/{JID}/cited-by",
                 f"/v1/precedent/judgments/{JID}/history", "/v1/precedent/courts/SC/judgments"):
        assert "judgments" in c.get(path).json()["coverage_note"], path


def test_a_court_list_pages_by_cursor_and_a_bad_cursor_says_refresh(app):
    c = TestClient(app)
    page = c.get("/v1/precedent/courts/SC/judgments", params={"limit": 2}).json()
    nxt = page["next_cursor"]
    c.get("/v1/precedent/courts/SC/judgments", params={"after": nxt})
    assert app.state.fake.asked[-1] == ("court", "SC", (False, date(2025, 1, 1), _card(2)["judgment_id"]))
    bad = c.get("/v1/precedent/courts/SC/judgments", params={"after": "not-a-cursor"})
    assert bad.status_code == 400 and "Refresh" in bad.json()["detail"]
    assert c.get("/v1/precedent/courts/XX/judgments").status_code == 422


def test_history_and_cited_by_keep_the_verified_only_rule(app):
    c = TestClient(app)
    h = c.get(f"/v1/precedent/judgments/{JID}/history").json()["items"][0]
    assert h["outcome"] is None and h["outcome_withheld"] is True
    cb = c.get(f"/v1/precedent/judgments/{JID}/cited-by").json()["items"][0]
    assert cb["treatments"] == ["followed"] and cb["treatments_awaiting_review"] == 1


# ------------------------------------------------------------------------------------------- against nizam_clean

@pytest.fixture(scope="module")
def repo():
    try:
        from nizam.storage.judgment_read import JudgmentRead
        r = JudgmentRead()
        r.open()
        with r.transaction() as conn:
            if not conn.execute("SELECT count(*) AS n FROM judgment_statute_reference").fetchone()["n"]:
                pytest.skip("no judgment links built")
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    yield r
    r.close()


def _most_cited(repo):
    with repo.transaction() as conn:
        return conn.execute("""SELECT p.id, p.instrument_id FROM judgment_statute_reference r
                                 JOIN provision p ON p.id = r.dst_provision_id
                                GROUP BY 1, 2 ORDER BY count(*) DESC LIMIT 1""").fetchone()


def test_recent_is_newest_first_undated_last_and_pages_without_overlap(repo):
    row = _most_cited(repo)
    a = repo.citing(("provision", row["id"]), DAY, limit=15, order="recent")
    b = repo.citing(("provision", row["id"]), DAY, limit=15, order="recent", offset=15)
    items = a["items"] + b["items"]
    assert a["total"] == b["total"] >= len(items) > 0
    assert not {i["judgment_id"] for i in a["items"]} & {i["judgment_id"] for i in b["items"]}
    flags = [i["undated"] for i in items]
    assert flags == sorted(flags)                                       # dated first, undated last
    dated = [i["decided_on"] for i in items if not i["undated"]]
    assert dated == sorted(dated, reverse=True)
    assert all(i["decided_on"] is None or i["decided_on"] <= DAY for i in items)


def test_a_whole_law_holds_at_least_its_sections_decisions(repo):
    row = _most_cited(repo)
    unit = repo.citing(("provision", row["id"]), DAY, limit=1)["total"]
    law = repo.citing(("instrument", row["instrument_id"]), DAY, limit=1)["total"]
    assert law >= unit > 0


def test_a_court_list_is_newest_first_and_its_pages_do_not_overlap(repo):
    first, key = repo.court_judgments("SC", DAY, 10)
    second, _ = repo.court_judgments("SC", DAY, 10, key)
    assert first and second and key is not None
    assert not {i["judgment_id"] for i in first} & {i["judgment_id"] for i in second}
    dated = [i["decided_on"] for i in first + second if not i["undated"]]
    assert dated == sorted(dated, reverse=True)
    assert all(i["court"] == "Supreme Court of Pakistan" for i in first + second)


def test_the_court_index_counts_every_released_judgment(repo):
    rows = repo.courts()
    with repo.transaction() as conn:
        released = conn.execute("SELECT count(*) AS n FROM v_release_judgment").fetchone()["n"]
    assert sum(r["judgments"] for r in rows) == released
    assert {r["code"] for r in rows} >= {"SC", "LHC", "SHC", "IHC", "PHC", "BHC", "FSC", "FCC"}
