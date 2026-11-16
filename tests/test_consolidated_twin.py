"""consolidated_twin (migrations 0075/0076): an as-made text linked to its consolidated text.

Pure tests pin the recorder's title rule (renamed and abbreviated titles, and the number-series collisions it must
refuse). Database tests need 0075 applied and roll everything back.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import record_consolidated_twins as twins  # noqa: E402


def ov(a: str, b: str) -> float:
    return twins.overlap(twins.title_words(a), twins.title_words(b))


def test_a_renamed_title_that_keeps_its_words_passes():
    assert ov("The Transfer of Railways Order, 1962", "Railways Order, 1962") >= 0.75
    assert ov("The Province of West Pakistan Rangers Ordinance, 1959", "The Pakistan Rangers Ordinance, 1959") >= 0.75


def test_number_series_collisions_fail_the_title_test():
    # same number and year, different laws (federal vs West Pakistan series), 12 Nov 2026 near-miss list
    assert ov("The Obscene Publications Act, 1925", "Sikh Gurdwaras (Supplementary) Act, 1925") < 0.75
    assert ov("The West Pakistan Finance Act, 1958", "West Pakistan Agriculturists' Loans Act, 1958") < 0.75
    assert ov("The Sind Courts Act, 1926", "Naturalization Act, 1926") < 0.75


def test_reviewed_titles_are_only_the_two_evidenced_pairs():
    assert set(twins.REVIEWED_TITLES) == {(5171, 4253), (9024, 2305)}


@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('consolidated_twin')")
                if cur.fetchone()[0] is None:
                    pytest.skip("migration 0075 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _a_link(cur):
    # a link whose two texts carry no repeal, so the only thing keeping the as-made text out is the link itself
    cur.execute("""SELECT t.id, t.as_made_observation_id, t.as_made_expression_ordinal, t.consolidated_observation_id,
                          t.consolidated_expression_ordinal, t.as_made_instrument_id, t.consolidated_instrument_id
                     FROM v_consolidated_twin_current t
                     JOIN instrument a ON a.id = t.as_made_instrument_id
                     JOIN instrument c ON c.id = t.consolidated_instrument_id
                    WHERE a.status <> 'repealed' AND c.status <> 'repealed'
                    ORDER BY t.id LIMIT 1""")
    row = cur.fetchone()
    if row is None:
        pytest.skip("no consolidated twin recorded")
    return row


def _insert(cur, a_obs, a_ord, c_obs, c_ord, assertion="recorded"):
    cur.execute("""INSERT INTO consolidated_twin
                     (as_made_observation_id, as_made_expression_ordinal, consolidated_observation_id,
                      consolidated_expression_ordinal, as_made_title, consolidated_title, basis, assertion, method,
                      evidence, recorded_by)
                   VALUES (%s,%s,%s,%s,'t','t','same_title_year',%s,'test',
                           '{"reviewer_type":"test","owner_decision":"test"}','test')""",
                (a_obs, a_ord, c_obs, c_ord, assertion))


def test_append_only(conn):
    with conn.cursor() as cur:
        link = _a_link(cur)
        cur.execute("SAVEPOINT s")
        with pytest.raises(Exception, match="append-only"):
            cur.execute("UPDATE consolidated_twin SET basis = basis WHERE id = %s", (link[0],))
        cur.execute("ROLLBACK TO SAVEPOINT s")


def test_a_chain_is_refused(conn):
    with conn.cursor() as cur:
        _id, a_obs, a_ord, c_obs, c_ord, *_ = _a_link(cur)
        cur.execute("SAVEPOINT s")
        # the consolidated side may not become as-made of something else
        with pytest.raises(Exception):
            _insert(cur, c_obs, c_ord, a_obs, a_ord)
        cur.execute("ROLLBACK TO SAVEPOINT s")


def test_a_pair_of_different_years_is_refused(conn):
    with conn.cursor() as cur:
        _id, a_obs, a_ord, *_ = _a_link(cur)
        cur.execute("""SELECT source_observation_id, expression_ordinal FROM v_release_instrument
                        WHERE year <> (SELECT year FROM instrument WHERE source_observation_id = %s
                                         AND expression_ordinal = %s AND is_active AND duplicate_of IS NULL)
                        LIMIT 1""", (a_obs, a_ord))
        other = cur.fetchone()
        cur.execute("SAVEPOINT s")
        with pytest.raises(Exception, match="differ in jurisdiction, kind or year"):
            _insert(cur, other[0], other[1], a_obs, a_ord)
        cur.execute("ROLLBACK TO SAVEPOINT s")


def test_operative_serves_the_consolidated_text_only(conn):
    with conn.cursor() as cur:
        *_, as_made, consolidated = _a_link(cur)
        cur.execute("SET LOCAL nzq.as_of = '2026-11-12'")
        cur.execute("SELECT count(*) FROM operative_provision WHERE instrument_id = %s", (as_made,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM operative_provision WHERE instrument_id = %s", (consolidated,))
        assert cur.fetchone()[0] > 0
        # the as-made text stays released and citable
        cur.execute("SELECT count(*) FROM v_release_instrument WHERE id = %s", (as_made,))
        assert cur.fetchone()[0] == 1


def test_a_withdrawn_link_serves_the_as_made_text_again(conn):
    with conn.cursor() as cur:
        _id, a_obs, a_ord, c_obs, c_ord, as_made, _c = _a_link(cur)
        cur.execute("SAVEPOINT s")
        _insert(cur, a_obs, a_ord, c_obs, c_ord, assertion="withdrawn")
        cur.execute("SET LOCAL nzq.as_of = '2026-11-12'")
        # 0094: operative_provision reads the serving snapshot; a record change shows after a refresh (audit A16
        # fails until then). The refresh is transactional, so the savepoint rollback undoes it with the withdrawal.
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute("REFRESH MATERIALIZED VIEW mv_instrument_serving")
        cur.execute("SELECT count(*) FROM operative_provision WHERE instrument_id = %s", (as_made,))
        assert cur.fetchone()[0] > 0
        cur.execute("ROLLBACK TO SAVEPOINT s")


def test_a_repeal_recorded_on_the_as_made_text_repeals_the_consolidated_text(conn):
    # migration 0077: 0066 recorded the repeal of e.g. the Human Trafficking Ordinance 2002 on the as-made text only
    with conn.cursor() as cur:
        cur.execute("""SELECT t.consolidated_instrument_id, a.repealed_on
                         FROM v_consolidated_twin_current t JOIN instrument a ON a.id = t.as_made_instrument_id
                         JOIN instrument c ON c.id = t.consolidated_instrument_id
                        WHERE a.status = 'repealed' AND c.status <> 'repealed' LIMIT 1""")
        row = cur.fetchone()
        if row is None:
            pytest.skip("no as-made-only repeal")
        consolidated, repealed_on = row
        cur.execute("SELECT set_config('nzq.as_of', %s, true)", (str(repealed_on),))
        cur.execute("SELECT count(*) FROM operative_provision WHERE instrument_id = %s", (consolidated,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT set_config('nzq.as_of', '2026-11-12', true)")
        cur.execute("SELECT count(*) FROM operative_provision WHERE instrument_id = %s", (consolidated,))
        assert cur.fetchone()[0] == 0
