"""operative_provision serves a law where and when its own text says (migrations 0095-0100), read from the corpus.

Pins the four facts golden set 3 exposed and the bug the first fix introduced:
  * a law with no territorial repeal is still served in every territory it reaches (0100: the exit test was not
    NULL-safe and served nothing in any territory);
  * the Child Marriage Restraint Act, 1929 (federal text, doc 2693) has left Punjab, ICT and Balochistan, not KP;
  * the Hindu Marriage Act, 2017 (doc 3483) runs where its s.1 says -- ICT, not Sindh;
  * a text with no amendment evidence is served before its capture: the Anti-Rape Ordinance, 2020 (doc 5366) at
    1 March 2021, and the Act of 2021 (doc 3070) not yet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="module")
def cur():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle, handle.cursor() as c:
            c.execute("SELECT to_regclass('mv_provision_text_known_from')")
            if c.fetchone()[0] is None:
                pytest.skip("migration 0096 is not applied")
            c.execute("SET statement_timeout = 0")
            yield c
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def served(cur, doc: int, label: str, territory: str, as_of: str = "2026-11-16") -> bool:
    cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)", (as_of, territory))
    cur.execute("""SELECT EXISTS (SELECT 1 FROM operative_provision o
                                   WHERE o.document_id = %s
                                     AND o.path <@ (SELECT p.path FROM provision p
                                                      JOIN v_release_instrument i ON i.id = p.instrument_id
                                                     WHERE i.document_id = %s AND p.is_active AND p.label = %s
                                                     ORDER BY nlevel(p.path), p.ordinal LIMIT 1))""",
                (doc, doc, label))
    return cur.fetchone()[0]


def test_a_law_without_exits_is_served_in_each_territory(cur):
    for territory in ("punjab", "sindh", "kp", "balochistan", "ict"):
        assert served(cur, 4441, "379", territory), territory          # PPC s.379


def test_the_1929_act_has_left_the_territories_that_repealed_it(cur):
    for territory in ("punjab", "ict", "balochistan"):
        assert not served(cur, 2693, "4", territory), territory
    assert served(cur, 2693, "4", "kp")


def test_the_hindu_marriage_act_runs_where_its_section_1_says(cur):
    assert served(cur, 3483, "4", "ict")
    assert not served(cur, 3483, "4", "sindh")


def test_a_text_without_amendment_evidence_is_served_before_capture(cur):
    assert served(cur, 5366, "4", "punjab", "2021-03-01")
    assert not served(cur, 3070, "4", "punjab", "2021-03-01")
    assert not served(cur, 5366, "4", "punjab", "2026-11-16")       # lapsed 2021
