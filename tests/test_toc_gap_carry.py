"""A replay carries a contents-gap decision only onto an exactly identical entry (lead decision 11 Oct, doc 2205).

`nizam.storage.legal_write._carry_toc_gap_decisions`, called by save() before the release-gate check. The
identity is the printed row -- label, heading, entry kind, page -- unresolved, with the same target, matched
exactly once in the old and in the new tree. The source anchor (block, offset) is deliberately not part of it:
fix K moved 2205's anchors and nothing else. Everything runs in a transaction that is rolled back.
"""
from __future__ import annotations

import json

import pytest

from nizam.storage import legal_write

ORDINALS = (95, 96)   # expression ordinals no document uses; every row is rolled back


@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _target(cur, observation=None):
    cur.execute("""
        SELECT i.document_id, i.source_observation_id, i.source_sha256, i.jurisdiction::text,
               b.id, b.page_no
          FROM instrument i
          JOIN LATERAL (SELECT id, page_no FROM text_block WHERE document_id=i.document_id
                         ORDER BY reading_order LIMIT 1) b ON true
         WHERE i.is_active AND i.expression_ordinal=0 AND i.duplicate_of IS NULL
           AND (%(obs)s::bigint IS NULL OR i.source_observation_id=%(obs)s)
           AND NOT EXISTS (SELECT 1 FROM instrument x WHERE x.source_observation_id=i.source_observation_id
                            AND x.expression_ordinal = ANY(%(ords)s))
         ORDER BY i.document_id LIMIT 1""", {"obs": observation, "ords": list(ORDINALS)})
    row = cur.fetchone()
    if row is None:
        pytest.skip("no instrument to borrow provenance from")
    return dict(zip(("document", "observation", "sha", "jurisdiction", "block", "page"), row))


def _instrument(cur, t, ordinal):
    cur.execute("""
        INSERT INTO instrument (jurisdiction, kind, year, short_title, source_sha256, document_id,
                                source_observation_id, expression_ordinal, expression_role)
        VALUES (%s, 'act', 1920, 'pytest toc carry', %s, %s, %s, %s, 'embedded') RETURNING id""",
                (t["jurisdiction"], t["sha"], t["document"], t["observation"], ordinal))
    return cur.fetchone()[0]


def _entries(cur, t, instrument, rows):
    """rows: (ordinal, label, heading) -- unresolved section entries on the target's page."""
    ids = {}
    for ordinal, label, heading in rows:
        cur.execute("""
            INSERT INTO instrument_toc_entry (instrument_id, ordinal, printed_label, printed_heading,
                                              entry_kind, match_method, source_block_id, source_page)
            VALUES (%s, %s, %s, %s, 'section', 'unmatched', %s, %s) RETURNING id""",
                    (instrument, ordinal, label, heading, t["block"], t["page"]))
        ids[ordinal] = cur.fetchone()[0]
    return ids


def _absent(cur, t, instrument, entry, label):
    evidence = {"assistant_page_review": True, "render_artifact": "pytest.png", "render_sha256": "0" * 64,
                "observed": "pytest: the page prints no such section"}
    cur.execute("""
        INSERT INTO toc_gap_adjudication (instrument_id, document_id, toc_entry_id, printed_label, resolution,
                                          source_page, evidence, rationale, decided_by)
        VALUES (%s, %s, %s, %s, 'absent_in_source', %s, %s, 'pytest reading', 'pytest') RETURNING id""",
                (instrument, t["document"], entry, label, t["page"], json.dumps(evidence)))
    return cur.fetchone()[0]


def _carried(cur, instrument):
    cur.execute("""SELECT e.printed_label, a.resolution, a.evidence
                     FROM toc_gap_adjudication a JOIN instrument_toc_entry e ON e.id=a.toc_entry_id
                    WHERE a.instrument_id=%s ORDER BY e.ordinal""", (instrument,))
    return cur.fetchall()


def test_an_exactly_identical_entry_carries_its_decision(conn):
    with conn.cursor() as cur:
        t = _target(cur)
        old, new = _instrument(cur, t, ORDINALS[0]), _instrument(cur, t, ORDINALS[1])
        old_ids = _entries(cur, t, old, [(1, "21", "Penalty."), (2, "22", "Repeal.")])
        new_ids = _entries(cur, t, new, [(1, "21", "Penalty."), (2, "22", "Repeal.")])
        decision = _absent(cur, t, old, old_ids[1], "21")
        report = legal_write._carry_toc_gap_decisions(cur, old, new, t["document"])
        assert report == {"carried": ["21"], "refused": []}
        (label, resolution, evidence), = _carried(cur, new)
        assert (label, resolution) == ("21", "absent_in_source")
        carry = evidence["carried_by_replay"]
        assert carry["adjudication_id"] == str(decision)
        assert (carry["toc_entry_id"], carry["new_toc_entry_id"]) == (old_ids[1], new_ids[1])
        assert evidence["observed"] == "pytest: the page prints no such section"
        # append-only: the old row is untouched
        cur.execute("SELECT toc_entry_id, evidence ? 'carried_by_replay' FROM toc_gap_adjudication WHERE id=%s",
                    (decision,))
        assert cur.fetchone() == (old_ids[1], False)


def test_a_near_match_carries_nothing(conn):
    # same label, different heading: not the same printed row
    with conn.cursor() as cur:
        t = _target(cur)
        old, new = _instrument(cur, t, ORDINALS[0]), _instrument(cur, t, ORDINALS[1])
        old_ids = _entries(cur, t, old, [(1, "21", "Penalty.")])
        _entries(cur, t, new, [(1, "21", "Penalties.")])
        _absent(cur, t, old, old_ids[1], "21")
        report = legal_write._carry_toc_gap_decisions(cur, old, new, t["document"])
        assert report["carried"] == [] and report["refused"] == [("21", "not exactly one identical entry")]
        assert _carried(cur, new) == []


def test_an_ambiguous_match_carries_nothing(conn):
    with conn.cursor() as cur:
        t = _target(cur)
        old, new = _instrument(cur, t, ORDINALS[0]), _instrument(cur, t, ORDINALS[1])
        # two identical new rows
        old_ids = _entries(cur, t, old, [(1, "21", "Penalty.")])
        _entries(cur, t, new, [(1, "21", "Penalty."), (2, "21", "Penalty.")])
        _absent(cur, t, old, old_ids[1], "21")
        assert legal_write._carry_toc_gap_decisions(cur, old, new, t["document"])["carried"] == []
        assert _carried(cur, new) == []
        # two identical old rows, one new
        old2 = _instrument(cur, t, 94)
        old2_ids = _entries(cur, t, old2, [(1, "22", "Repeal."), (2, "22", "Repeal.")])
        new2 = _instrument(cur, t, 93)
        _entries(cur, t, new2, [(1, "22", "Repeal.")])
        _absent(cur, t, old2, old2_ids[1], "22")
        assert legal_write._carry_toc_gap_decisions(cur, old2, new2, t["document"])["carried"] == []


def test_a_changed_target_carries_nothing(conn):
    # other_instrument naming the tree being replaced, or no live instrument at all
    with conn.cursor() as cur:
        t = _target(cur)
        old, new = _instrument(cur, t, ORDINALS[0]), _instrument(cur, t, ORDINALS[1])
        old_ids = _entries(cur, t, old, [(1, "21", "Penalty.")])
        _entries(cur, t, new, [(1, "21", "Penalty.")])
        cur.execute("""
            INSERT INTO toc_gap_adjudication (instrument_id, document_id, toc_entry_id, printed_label, resolution,
                                              source_page, evidence, rationale, decided_by)
            VALUES (%s, %s, %s, '21', 'other_instrument', %s, %s, 'pytest', 'pytest')""",
                    (old, t["document"], old_ids[1], t["page"], json.dumps({"other_instrument_id": str(old)})))
        report = legal_write._carry_toc_gap_decisions(cur, old, new, t["document"])
        assert report == {"carried": [], "refused": [("21", "target changed")]}


def test_the_2205_shape_carries_eighteen_source_incomplete_rows(conn):
    # doc 2205 (Sind Public Conveyances Act, 1920, observation 3341): contents rows 21-38 printed, the copy ends
    # in section 20; each closed source_incomplete against source_incompleteness 12. The replay moves anchors only.
    with conn.cursor() as cur:
        cur.execute("""SELECT id FROM v_source_incompleteness_latest
                        WHERE source_observation_id=3341 AND resolution='no_complete_copy_acquired'""")
        row = cur.fetchone()
        if row is None:
            pytest.skip("doc 2205's source_incompleteness record is not in this database")
        incompleteness = row[0]
        t = _target(cur, observation=3341)
        old, new = _instrument(cur, t, ORDINALS[0]), _instrument(cur, t, ORDINALS[1])
        rows = [(n, str(n), f"Heading of section {n}.") for n in range(21, 39)]
        old_ids = _entries(cur, t, old, rows)
        new_ids = _entries(cur, t, new, [(n + 100, label, heading) for n, label, heading in rows])  # ordinals move
        evidence = {"assistant_page_review": True, "render_artifact": "pytest.png", "render_sha256": "0" * 64,
                    "observed": "pytest: the copy ends in section 20", "source_incompleteness_id": incompleteness}
        for n, label, _ in rows:
            cur.execute("""
                INSERT INTO toc_gap_adjudication (instrument_id, document_id, toc_entry_id, printed_label,
                                                  resolution, source_page, evidence, rationale, decided_by)
                VALUES (%s, %s, %s, %s, 'source_incomplete', %s, %s, 'pytest', 'pytest')""",
                        (old, t["document"], old_ids[n], label, t["page"], json.dumps(evidence)))
        report = legal_write._carry_toc_gap_decisions(cur, old, new, t["document"])
        assert report["refused"] == [] and sorted(report["carried"], key=int) == [str(n) for n in range(21, 39)]
        carried = _carried(cur, new)
        assert [(label, resolution) for label, resolution, _ in carried] == \
            [(str(n), "source_incomplete") for n in range(21, 39)]
        assert all(e["source_incompleteness_id"] == incompleteness for _, _, e in carried)
        assert {e["carried_by_replay"]["new_toc_entry_id"] for _, _, e in carried} == set(new_ids.values())
