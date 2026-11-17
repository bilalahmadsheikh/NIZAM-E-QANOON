"""operative_provision stops serving a unit a later law repeals (migration 0102), read from the corpus.

  * the Electronic Transactions Ordinance, 2002 (doc 3526) s.36 is served on 1 January 2015 and not today: the
    Prevention of Electronic Crimes Act, 2016 s.55 omits sections 36 and 37;
  * the Sindh Finance Act, 1994 (doc 2307) s.9, still printed in the held consolidated text, is not served today:
    the Sindh Development and Maintenance of Infrastructure Cess Act, 2017 repeals it -- served as law until 0102;
  * a repealed unit takes its subtree with it, and the rest of the law is still served.
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
            c.execute("SELECT to_regclass('mv_provision_repeal')")
            if c.fetchone()[0] is None:
                pytest.skip("migration 0102 is not applied")
            c.execute("SET statement_timeout = 0")
            yield c
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def served(cur, doc: int, rel: str, as_of: str, territory: str | None = None) -> bool:
    cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                (as_of, territory or ""))
    cur.execute("""SELECT EXISTS (SELECT 1 FROM operative_provision o
                                   WHERE o.document_id = %s AND subpath(o.path, 3)::text = %s)""", (doc, rel))
    return cur.fetchone()[0]


def test_a_section_omitted_by_a_later_act_is_served_before_and_not_after(cur):
    assert served(cur, 3526, "ch_8.s_36", "2015-01-01")
    assert not served(cur, 3526, "ch_8.s_36", "2026-11-17")


def test_a_repealed_section_the_consolidation_still_prints_is_not_served(cur):
    assert not served(cur, 2307, "s_9", "2026-11-17", "sindh")


def test_the_rest_of_the_law_is_still_served(cur):
    cur.execute("SELECT set_config('nzq.as_of', '2026-11-17', true), set_config('nzq.territory', 'sindh', true)")
    cur.execute("""SELECT count(*) FROM operative_provision WHERE document_id = 2307""")
    assert cur.fetchone()[0] > 0


def test_every_standing_repealed_unit_and_its_subtree_is_unserved_today(cur):
    cur.execute("SELECT set_config('nzq.as_of', '2026-11-17', true), set_config('nzq.territory', '', true)")
    cur.execute("""SELECT count(*) FROM operative_provision o
                     JOIN mv_provision_repeal r ON r.instrument_id = o.instrument_id AND o.path <@ r.path
                    WHERE r.territory_key = '*'""")
    assert cur.fetchone()[0] == 0


def test_a_unit_a_whole_repeal_excepts_stays_served_and_says_so(cur):
    # Companies Act, 2017 s.509(1): the Companies Ordinance, 1984 is repealed 'except Part VIIIA consisting of
    # sections 282A to 282N' -- before 0103 the Ordinance was not current and Part VIIIA was served nowhere
    cur.execute("SELECT set_config('nzq.as_of', '2026-11-17', true), set_config('nzq.territory', '', true)")
    cur.execute("""SELECT subpath(path, 3)::text, survives_repeal FROM operative_provision
                    WHERE document_id = 4495 AND subpath(path, 3)::text IN ('pt_VIII.s_282_A', 'pt_VIII.s_282_N',
                                                                            'pt_VIII.s_282', 'pt_IX.s_283')""")
    got = dict(cur.fetchall())
    assert got == {"pt_VIII.s_282_A": True, "pt_VIII.s_282_N": True}


def test_a_sub_section_excepted_from_a_repeal_is_served_without_its_repealed_siblings(cur):
    # PIA Corporation (Conversion) (Repeal) Act s.2(1): the 2016 Act is repealed 'except sub-section (1) of section 7';
    # the held text keeps s.7(1) as section 7's own words and s.7(2) as its child
    assert served(cur, 4188, "s_7", "2026-11-17")
    assert not served(cur, 4188, "s_7.ss_2", "2026-11-17")
    assert not served(cur, 4188, "s_1", "2026-11-17")
