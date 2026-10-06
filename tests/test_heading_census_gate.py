"""What A11 rests on: a recorded census, and proof it describes THIS corpus.

A11 is the only criterion whose number is not computed where the audit computes
its numbers. It has to be: written as SQL with guards 1-3 plus prefix
containment and no token comparison, the rule reported 472 rows in 221
documents against a true count of 101, concentrated in the CrPC, the Customs
Act, the PAF Act, the Army Act, the Constitution and the PPC -- every one of
them one name spelt two ways. So the value is read from
`heading_mislabel_census` (migration 0053), and everything below guards the two
things that makes newly possible to get wrong:

  * a stored count that disagrees with its own findings, and
  * a stored count that describes a corpus that is no longer there.

The second is the whole reason the table has a digest. Four of these tests need
the corpus; they write inside a transaction and roll it back, so nothing is
recorded.
"""
from __future__ import annotations

import pytest

from tools.census_heading_mislabel import find_hits

DIGEST_STATE = "SELECT corpus_digest, scope_provisions, active_instruments " \
               "FROM v_heading_mislabel_corpus_state"

CURRENT = """
SELECT census_id, never_measured, is_stale, mislabelled,
       mislabelled_documents, variant_spellings
  FROM v_heading_mislabel_census_current
"""

INSERT_CENSUS = """
INSERT INTO heading_mislabel_census
       (measured_by, detector, detector_sha256, corpus_digest,
        scope_provisions, active_instruments)
VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
"""

INSERT_FINDING = """
INSERT INTO heading_mislabel_finding
       (census_id, provision_id, instrument_id, document_id, short_title,
        kind, label, first_page, tree_heading, printed_name, block_excerpt,
        finding_class, similarity, toc_linked)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

SHA = "0" * 64


@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('heading_mislabel_census')")
                if cur.fetchone()[0] is None:
                    pytest.skip("migration 0053 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _record(cur, digest: str, findings: list[tuple[str, str, str]]) -> int:
    cur.execute(DIGEST_STATE)
    _live, scope, instruments = cur.fetchone()
    cur.execute(INSERT_CENSUS, ("pytest", "tests/test_heading_census_gate.py",
                                SHA, digest, scope, instruments))
    census_id = int(cur.fetchone()[0])
    for n, (provision, tree_heading, finding_class) in enumerate(findings):
        cur.execute(INSERT_FINDING, (
            census_id, provision, "00000000-0000-0000-0000-0000000000ff",
            9000 + n, "Example Act", "section", str(n + 1), 4,
            tree_heading, "Fee for the issue of driving licence", "4. Fee ...",
            finding_class, 0.2, True))
    return census_id


# --------------------------------------------------------------------------
# round trip


def test_the_census_reports_the_findings_it_stored(conn):
    """The header carries no counts, so a header cannot outvote its findings.

    A denormalised `mislabelled` column would be a second place for the truth
    to live, and the first thing to drift. Every number A11 prints is derived
    from `heading_mislabel_finding` -- this writes two of each class and reads
    them back through the view the criterion actually queries.
    """
    with conn.cursor() as cur:
        cur.execute(DIGEST_STATE)
        live = cur.fetchone()[0]
        census_id = _record(cur, live, [
            ("00000000-0000-0000-0000-000000000001", "Wrong Name One",
             "different_name"),
            ("00000000-0000-0000-0000-000000000002", "Wrong Name Two",
             "different_name"),
            ("00000000-0000-0000-0000-000000000003", "Issus of process",
             "variant_spelling"),
        ])
        cur.execute(CURRENT)
        got_id, never, stale, mislabelled, documents, variants = cur.fetchone()

    assert got_id == census_id
    assert never is False
    assert stale is False
    assert mislabelled == 2
    assert documents == 2
    assert variants == 1


def test_a_census_that_found_nothing_is_not_the_same_as_no_census(conn):
    """The state A11 is meant to reach must be distinguishable from silence.

    With counts derived from findings, "no rows" is the answer both to "clean"
    and to "never ran". `never_measured` is what separates them, and it is why
    the header exists as a row of its own.
    """
    with conn.cursor() as cur:
        cur.execute(DIGEST_STATE)
        live = cur.fetchone()[0]
        _record(cur, live, [])
        cur.execute(CURRENT)
        _id, never, stale, mislabelled, _documents, _variants = cur.fetchone()

    assert never is False
    assert stale is False
    assert mislabelled == 0


# --------------------------------------------------------------------------
# staleness


def test_a_census_of_another_corpus_reads_as_stale(conn):
    """The crux. A number measured before a replay must not report a pass.

    Three watermarks were tried. The count of active instruments cannot see a
    re-segmentation at all -- appending a revision retires one instrument and
    adds its replacement, so the count is identical. A max(created_at) clock
    advances on a run but cannot see a duplicate resolution, a retirement with
    no replacement, or a restore that moves the corpus backwards. The digest is
    of the census population itself, so it changes in both directions; this
    perturbs it by one character and expects the view to notice.
    """
    with conn.cursor() as cur:
        cur.execute(DIGEST_STATE)
        live = cur.fetchone()[0]
        other = ("b" if live[0] != "b" else "c") + live[1:]
        _record(cur, other, [("00000000-0000-0000-0000-000000000004",
                              "Wrong Name", "different_name")])
        cur.execute(CURRENT)
        _id, never, stale, mislabelled, _documents, _variants = cur.fetchone()

    assert never is False
    assert stale is True
    # The count survives being stale: A11 prints it, labelled and dated, rather
    # than hiding it. What it must not do is pass.
    assert mislabelled == 1


def test_the_live_watermark_is_the_population_not_a_proxy(conn):
    """It digests the census scope, and agrees with counting that scope."""
    with conn.cursor() as cur:
        cur.execute(DIGEST_STATE)
        digest, scope, instruments = cur.fetchone()
        cur.execute("""
            SELECT count(*) FROM provision p
              JOIN instrument i ON i.id = p.instrument_id
                               AND i.is_active AND i.duplicate_of IS NULL
             WHERE p.is_active AND p.first_block IS NOT NULL
               AND p.heading IS NOT NULL AND btrim(p.heading) <> ''
               AND p.kind::text IN
                   ('section','article','rule','regulation','paragraph')
        """)
        counted = cur.fetchone()[0]

    assert len(digest) == 32
    assert scope == counted
    assert instruments > 0


# --------------------------------------------------------------------------
# the two residual shapes, as the detector sees them
#
# Both are a SCHEDULE ROW segmented as a section and then given the real
# section's name. They are pure-function cases: the detector must call each a
# `different_name`, because that is what A11 counts, and must not be talked out
# of it by the guards that exist for one name spelt two ways.


def _row(*, printed: str, heading: str, label: str, doc: int = 1683):
    return (doc, "Example Act", "00000000-0000-0000-0000-000000000002", label,
            6, "00000000-0000-0000-0000-000000000003", "section", heading,
            printed, 1)


def test_doc_1683_second_schedule_row_wearing_the_bodys_marginal_note():
    """Page 6 is the SECOND SCHEDULE (Section 5); its row 4 is not section 4."""
    hits = find_hits([_row(
        label="4",
        printed="4. Fee for the issue of driving licence, under clause (i) "
                "of rule 26— 100",
        heading="Amendment of W. P. Act No. XXXII of 1958.",
    )])
    assert [h["class"] for h in hits] == ["different_name"]
    assert hits[0]["printed_name"].startswith("Fee for the issue")


def test_doc_4139_third_schedule_row_wearing_the_first_schedules_name():
    """Page 21 prints "15. Office Assistant - cum- Storekeeper"."""
    hits = find_hits([_row(
        doc=4139, label="15",
        printed="15. Office Assistant – Director Intermediate with "
                "minimum 2nd class cum- Storekeeper and 5 years experience.",
        heading="Security Supervisor 11 1",
    )])
    assert [h["class"] for h in hits] == ["different_name"]
    assert hits[0]["printed_name"] == "Office Assistant"


def test_one_name_spelt_two_ways_is_still_not_a_residual():
    """The guard that keeps the two above from being 62 CrPC sections."""
    assert find_hits([_row(
        label="17", doc=4501,
        printed="17. Subordination of Magistrates and Benches to Sessions "
                "Judge.— All Magistrates appointed under section 12 ...",
        heading="Subordination of 6[* * *] Magistrates and Benches to "
                "Sessions Judge",
    )]) == []
