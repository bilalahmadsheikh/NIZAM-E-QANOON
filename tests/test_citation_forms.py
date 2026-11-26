"""Printed law-name forms the resolver reads since D-164: a schedule's article names its Act, and a hyphen a title
prints is the same name printed whole. Database tests through the linker's own resolver."""
from __future__ import annotations

import pytest

from nizam.storage import judgment_linking as JL


@pytest.fixture(scope="module")
def resolver():
    try:
        from nizam.storage.db import connect
        from nizam.workers.judgment_links import Resolver
        cm = connect()
        conn = cm.__enter__()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    cur = conn.cursor()
    yield lambda territory: Resolver(cur, territory)
    conn.rollback()
    cm.__exit__(None, None, None)


def _one(text):
    cits = JL.statute_citations(text)
    assert cits, text
    return cits[0]


def test_an_article_of_a_schedule_names_the_act_and_its_schedule(resolver):
    r = resolver(None).resolve(_one("as provided by Article 151 of the First Schedule to the Limitation Act, 1908."))
    assert r.resolved_unit is not None and "Limitation" in (r.resolved_law or "")


def test_a_schedule_article_sharing_a_section_label_is_never_chosen_between(resolver):
    # the federal copy holds both s.29 and Article 29 as sections: not chosen between, unresolved
    r = resolver(None).resolve(_one("under Article 29 of the First Schedule to the Limitation Act, 1908."))
    assert r.resolved_unit is None or ".sch_" in (r.resolved_unit.path or "")


def test_a_hyphenated_title_is_the_same_name_printed_whole(resolver):
    r = resolver("sindh").resolve(_one("Section 70 of the Cooperative Societies Act, 1925 provides"))
    assert r.resolved_unit is not None and "operative" in (r.resolved_law or "").lower()
