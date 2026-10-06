"""A reviewed S7 decision must steer the parser that raised it, and only it.

405 of the 932 pending S7 units had already been judged by someone reading the
rendered page and could never clear: `v_structural_adjudication_pending`
(migration 0036) keeps every candidate whose latest resolution is not
`accept_non_citable`, and no code carried the other resolutions out. A replay
retired the candidate, made a fresh one with a new id, and orphaned the
reading back into the queue.

These are the guards on the mechanism that ends that. Four of them are pure --
blocks in, a tree out, readings supplied by hand -- and one needs the corpus,
because what it protects is a WHERE clause.
"""
from __future__ import annotations

import pytest

from nizam.corpus.segment import segment
from nizam.workers.segment import build


def blocks(*texts: str, page: int = 1) -> list[dict]:
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0}
            for i, t in enumerate(texts)]


# The shape the parser gets wrong often enough to matter: one label printed
# twice under a chapter, where both prints carry text, so the tie falls to
# source order and the FIRST print keeps the citation. Five of the first ten
# S7 readings ever taken found the first print was the apparatus.
COLLIDING = (
    "CHAPTER I",
    "1. Application. This Chapter applies.",
    "2. Main rule. The principal rule applies.",
    "1. Table row one. Preserved schedule-like content.",
    "1. Table row two. Preserved schedule-like content.",
)


def reading(block_id: int, label: str, resolution: str) -> dict:
    """One row shaped as `legal_write.structural_resolutions_for` returns it."""
    return {"source_block_id": block_id, "printed_label": label,
            "resolution": resolution, "review_basis": "source_verified"}


def kinds(seg) -> list[tuple]:
    chapter = next(n for n in seg.root.children if n.kind == "chapter")
    return [(n.kind, n.label, n.first_block) for n in chapter.children]


def test_the_parser_without_a_reading_keeps_the_first_print():
    """The baseline these tests move away from, stated rather than assumed."""
    assert kinds(segment(blocks(*COLLIDING))) == [
        ("section", "1", 1), ("section", "2", 2),
        ("clause", "1", 3), ("clause", "1", 4)]


def test_restore_citable_moves_the_citation_and_survives_a_rebuild():
    """A reviewer named which print is the section; the tree must agree.

    The unit named stays citable, the print the parser had kept is demoted in
    its place, and neither is raised as a fresh question -- the same reading
    that named one the section named the other not-the-section. Segmenting
    twice from the same blocks gives the same tree, which is the whole point:
    the decision is anchored to a source block, not to a candidate id that the
    replay regenerates.
    """
    readings = [reading(3, "1", "restore_citable")]
    first = segment(blocks(*COLLIDING), structural_resolutions=readings)
    again = segment(blocks(*COLLIDING), structural_resolutions=readings)

    assert kinds(first) == [
        ("clause", "1", 1), ("section", "2", 2),
        ("section", "1", 3), ("clause", "1", 4)]
    assert kinds(again) == kinds(first)

    # The collision is still in the ledger -- every repair and safety check
    # above it must still see it -- but the two prints the reading settled
    # carry the reason they will not be asked about again.
    settled = {d["candidate"].first_block: d["settled_by_review"]
               for d in first.repeated_label_decisions}
    assert settled == {1: "restore_citable", 4: None}
    assert first.repeated_labels_demoted == 2


def test_reject_candidate_stops_the_candidate_being_raised():
    """A rate cell read as a section is not a collision to adjudicate.

    The tree is untouched -- the unit was already demoted and stays demoted --
    and what is withheld is only the candidate row, which would otherwise come
    back pending after every replay, forever.
    """
    plain = blocks(*COLLIDING)
    before, _ = build(1, "s" * 64, 1, "fed", "An Act", "1960", None,
                      plain, "2026-01-01", profile="default")
    after, seg = build(1, "s" * 64, 1, "fed", "An Act", "1960", None,
                       plain, "2026-01-01", profile="default",
                       structural_resolutions=[
                           reading(3, "1", "reject_candidate")])

    assert [(r["kind"], r["label"]) for r in before.provisions] == \
           [(r["kind"], r["label"]) for r in after.provisions]
    assert len(before.structural_decisions) == 2
    assert len(after.structural_decisions) == 1
    assert after.structural_decisions[0]["source_block_id"] == 4
    assert [e["resolution"] for e in seg.structural_reviews_enacted] == \
           ["reject_candidate"]


def test_a_reading_whose_block_is_gone_is_ignored_not_misapplied():
    """The replay may have removed the collision the reading described.

    Then there is nothing to anchor to and nothing to do. The danger is the
    other behaviour -- falling back to the printed label alone, which matches
    more rows, cannot tell two collisions on one label apart, and would follow
    a label the replay moved to a different node.
    """
    stale = [reading(9_999, "1", "restore_citable"),
             reading(9_998, "1", "reject_candidate")]
    steered = segment(blocks(*COLLIDING), structural_resolutions=stale)
    assert kinds(steered) == kinds(segment(blocks(*COLLIDING)))
    assert steered.structural_reviews_enacted == []
    assert all(d["settled_by_review"] is None
               for d in steered.repeated_label_decisions)


def test_a_reading_on_a_label_the_block_does_not_print_is_ignored():
    """The block is half the key; the printed label is the other half.

    One text block can open several colliding units -- document 3757's block
    468186 opens three -- so a reading anchored to the block alone would settle
    units its reviewer never looked at.
    """
    wrong_label = [reading(3, "7", "restore_citable")]
    steered = segment(blocks(*COLLIDING), structural_resolutions=wrong_label)
    assert kinds(steered) == kinds(segment(blocks(*COLLIDING)))
    assert steered.structural_reviews_enacted == []


def test_two_restored_prints_of_one_label_are_refused_not_guessed():
    """Two claims to be the same section are a question, not an instruction."""
    both = [reading(3, "1", "restore_citable"),
            reading(4, "1", "restore_citable")]
    steered = segment(blocks(*COLLIDING), structural_resolutions=both)
    assert kinds(steered) == kinds(segment(blocks(*COLLIDING)))
    assert steered.structural_reviews_enacted == []
    assert [r["reason"] for r in steered.structural_reviews_refused] == [
        "two prints of one label are both restored"]


def test_rejecting_the_print_the_parser_kept_is_refused_and_recorded():
    """`reject_candidate` demotes nothing.

    The reading says the unit is apparatus; it does not say which of its
    siblings is the section. Forcing the demotion would remove a citable unit
    on an inference the reading does not carry (INV-4), so the parse stands and
    the disagreement is reported instead of being silently dropped.
    """
    on_canonical = [reading(1, "1", "reject_candidate")]
    steered = segment(blocks(*COLLIDING), structural_resolutions=on_canonical)
    assert kinds(steered) == kinds(segment(blocks(*COLLIDING)))
    assert [r["reason"] for r in steered.structural_reviews_refused] == [
        "the rejected print is the canonical unit"]


def test_a_swap_that_would_move_the_citation_onto_a_stub_is_refused():
    """`restore_citable` is one word for two different findings.

    Document 2629 is the first: the parser kept a footnote on page 11 that had
    swallowed 5,249 characters and demoted the real rule 14, 659 characters on
    page 17. Document 3216 is the second: page 23 of the Punjab Excise rules
    prints two rules both numbered 9.115 and the reviewer's own words are
    "Both are operative" -- swapping there would move the citation off 2,373
    characters of operative rule onto 316 and demote the rest. Nothing in the
    resolution separates them, so the parse fails closed on the same shape
    `tools/adjudicate_s7_from_source.py` refuses an `accept_non_citable` on.
    """
    both_operative = blocks(
        "CHAPTER I",
        "1. Grant of a pass. " + "A pass may be granted in the following "
        "circumstances and subject to the following conditions. " * 9,
        "2. Main rule. The principal rule applies.",
        "1. Fusel oil. A sample shall be forwarded to the examiner.",
    )
    readings = [reading(3, "1", "restore_citable")]
    steered = segment(both_operative, structural_resolutions=readings)

    assert kinds(steered) == kinds(segment(both_operative))
    refused = steered.structural_reviews_refused
    assert [r["reason"] for r in refused] == [
        "the swap would move the citation onto a stub"]
    assert refused[0]["chars_losing"] >= 500
    assert refused[0]["chars_gaining"] * 2 < refused[0]["chars_losing"]
    assert steered.structural_reviews_enacted == []


def test_the_guard_does_not_block_a_swap_between_comparable_units():
    """It is a stub guard, not a size preference.

    Where both prints carry comparable text the reading decides, which is the
    ordinary inverted case: the parser had no way to tell them apart and the
    reviewer did, by opening the page.
    """
    comparable = blocks(
        "CHAPTER I",
        "1. Application. This Chapter applies to every licensed factory.",
        "2. Main rule. The principal rule applies.",
        "1. Registers. Every occupier shall keep the prescribed registers.",
    )
    steered = segment(comparable,
                      structural_resolutions=[reading(3, "1",
                                                      "restore_citable")])
    assert [(n.kind, n.first_block) for n in
            next(c for c in steered.root.children
                 if c.kind == "chapter").children] == [
        ("clause", 1), ("section", 2), ("section", 3)]
    assert steered.structural_reviews_refused == []


# --------------------------------------------------------------- the corpus
#
# What follows protects a WHERE clause, so it cannot be written against
# fabricated blocks. It skips rather than fails where the corpus is not up:
# a machine that has no database has not disproved anything.
def _resolutions():
    try:
        from nizam.storage import legal_write
        from nizam.storage.db import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    return legal_write, connect


def test_a_machine_decision_never_steers_the_parser():
    """A program approving its own output is not a review.

    11,212 of the 14,308 S7 decisions in this corpus are `machine_evidenced`,
    and every one of them is `accept_non_citable` -- so the resolution filter
    alone would hide a broken basis filter, and the two have to be shown apart.
    This records a machine `restore_citable` against a real candidate, runs the
    lookup's own predicate over it, and rolls the row back. Nothing is written.
    """
    legal_write, connect = _resolutions()
    with connect(autocommit=False) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.id, c.document_id, c.source_block_id,
                   lower(regexp_replace(c.printed_label,'\\s+','','g'))
              FROM segmentation_structural_candidate c
             WHERE NOT EXISTS (SELECT 1
                                 FROM v_structural_adjudication_latest a
                                WHERE a.candidate_id = c.id)
             LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("no unadjudicated candidate to test against")
        candidate_id, document_id, block_id, label_key = row

        before = cur.execute(legal_write._STRUCTURAL_RESOLUTIONS_SQL,
                             (document_id,)).fetchall()
        cur.execute("""
            INSERT INTO segmentation_structural_adjudication
                (candidate_id,resolution,review_basis,method,rationale,
                 evidence,decided_by)
            VALUES (%s,'restore_citable','machine_evidenced',
                    'tests.structural_review/1',
                    'a machine decision, rolled back by the test that made it',
                    '{}'::jsonb,'tests.structural_review/1')
        """, (candidate_id,))
        after = cur.execute(legal_write._STRUCTURAL_RESOLUTIONS_SQL,
                            (document_id,)).fetchall()
        try:
            assert after == before
            assert (block_id, label_key) not in {(r[0], r[2]) for r in after}
        finally:
            conn.rollback()


def test_every_returned_row_is_reviewed_and_enactable():
    """The lookup returns only what a reviewer said and the parser can do.

    `reparent` is returned only when its reviewed evidence records exact source
    and parent blocks. `split_instrument` remains excluded because splitting a
    document is not a parser operation.
    """
    legal_write, connect = _resolutions()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT c.document_id
              FROM v_structural_adjudication_latest a
              JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
             WHERE a.review_basis IN ('source_verified','human_verified')
             ORDER BY 1 LIMIT 40
        """)
        documents = [row[0] for row in cur.fetchall()]
    if not documents:
        pytest.skip("no source-verified decision in this corpus")

    seen = 0
    for document_id in documents:
        for row in legal_write.structural_resolutions_for(document_id):
            seen += 1
            assert row["review_basis"] in ("source_verified", "human_verified")
            assert row["resolution"] in (
                "restore_citable", "reparent", "reject_candidate")
            if row["resolution"] == "reparent":
                reparents = (row["evidence"].get("structural_overrides") or {}).get(
                    "source_reparent_blocks")
                assert isinstance(reparents, list) and reparents
                assert all(item.get("source_block_id")
                           and item.get("parent_block_id")
                           for item in reparents)
            assert row["source_block_id"] is not None
    assert seen, "40 reviewed documents returned no enactable reading"
