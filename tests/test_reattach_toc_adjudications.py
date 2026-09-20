"""Re-attaching contents-gap decisions across a replay: no DB required.

The rules under test are the ones that make the repair safe rather than
convenient -- the anchor survives a regeneration, an ambiguous anchor refuses,
a contradicted decision is never carried, and a decision whose evidence points
at a regenerated identifier is refused rather than rewritten blind.
"""
import pytest

from tools.reattach_orphaned_toc_adjudications import (
    EXCLUSIONS, excluded_reason, norm, plan, reattached_evidence)


def orphan(**kw):
    """A standing decision whose instrument the replay retired."""
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "document_id": 900,
        "old_instrument_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "old_toc_entry_id": 11,
        "printed_label": "7",
        "resolution": "parser_defect",
        "source_page": 3,
        "evidence": {"defect_class": "printed_section_absent_from_tree"},
        "rationale": "read against the page",
        "decided_by": "test.reader/1",
        "old_source_block_id": 5001,
        "old_printed_heading": "Power to make rules.",
        "old_entry_source_page": 1,
        "old_ordinal": 7,
        "reresolved_provision_id": None,
    }
    row.update(kw)
    return row


def entry(**kw):
    """A contents entry of the instrument the replay created."""
    row = {
        "toc_entry_id": 91,
        "document_id": 900,
        "instrument_id": "bbbbbbbb-0000-0000-0000-000000000001",
        "ordinal": 7,
        "printed_label": "7",
        "printed_heading": "Power to make rules.",
        "source_block_id": 5001,
        "source_page": 1,
        "resolved": False,
        "is_pending_gap": True,
        "standing_adjudication_id": None,
        "standing_resolution": None,
        "standing_decided_by": None,
    }
    row.update(kw)
    return row


def bracketing(instrument="bbbbbbbb-0000-0000-0000-000000000001", n=12):
    """Resolved contents entries either side of ordinal 7, so the absence
    re-check's check 4 and check 5 both pass."""
    return [entry(toc_entry_id=800 + i, ordinal=i, printed_label=str(i),
                  printed_heading=f"Heading {i}.", source_block_id=6000 + i,
                  resolved=True, is_pending_gap=False, instrument_id=instrument)
            for i in range(1, n + 1) if i != 7]


# --- the anchor survives a regeneration -----------------------------------
def test_the_anchor_survives_regenerated_instrument_entry_and_ordinal_ids():
    # Everything our own pipeline regenerates has changed: the instrument uuid,
    # the toc entry id, and the ordinal. Only document, block, label and
    # heading are carried over from the source, and they are the anchor.
    result = plan([orphan()], [entry(toc_entry_id=4242, ordinal=9)])
    assert not result["refused"] and not result["finished"]
    (row,) = result["rebind"]
    assert row["new_toc_entry_id"] == 4242
    assert row["new_instrument_id"] == "bbbbbbbb-0000-0000-0000-000000000001"
    assert row["ordinal_moved"] is True


def test_a_moved_ordinal_is_not_an_obstacle_but_is_reported():
    (row,) = plan([orphan()], [entry(ordinal=7)])["rebind"]
    assert row["ordinal_moved"] is False


def test_the_replay_resolving_the_label_is_finished_not_lost():
    live = [entry(resolved=True, is_pending_gap=False, source_block_id=7777,
                  printed_heading="Power to make regulations.")]
    result = plan([orphan()], live)
    assert not result["rebind"] and not result["refused"]
    assert "no gap left" in result["finished"][0]["detail"]


def test_a_label_the_replay_dropped_is_refused_not_guessed():
    result = plan([orphan()], [entry(printed_label="8", source_block_id=9)])
    assert result["refused"][0]["kind"] == "no_match"


# --- an ambiguous anchor is refused ---------------------------------------
def test_two_entries_on_one_block_and_label_refuse_rather_than_guess():
    # One contents block routinely holds a dozen entries, which is why the
    # block alone cannot anchor a contents decision the way it anchors an S7
    # candidate. Here the heading also fails to separate them.
    live = [entry(toc_entry_id=91), entry(toc_entry_id=92, ordinal=8)]
    (refusal,) = plan([orphan()], live)["refused"]
    assert refusal["kind"] == "ambiguous"
    assert "matches 2" in refusal["detail"]


def test_block_and_heading_anchors_disagreeing_refuses():
    # The label appears twice: once on the old block under a different
    # heading, once elsewhere under the old heading. Each anchor is unique on
    # its own and they name different entries -- exactly the case a single
    # anchor would silently get wrong.
    live = [entry(toc_entry_id=91, printed_heading="Something else."),
            entry(toc_entry_id=92, source_block_id=5999, ordinal=8)]
    (refusal,) = plan([orphan()], live)["refused"]
    assert refusal["kind"] == "ambiguous"
    assert "disagree" in refusal["detail"]


def test_a_decision_with_no_contents_row_behind_it_cannot_be_anchored():
    stray = orphan(old_toc_entry_id=None, old_source_block_id=None,
                   old_printed_heading=None)
    (refusal,) = plan([stray], [entry()])["refused"]
    assert refusal["kind"] == "no_anchor"


def test_a_run_only_label_the_replay_stopped_reporting_is_finished():
    stray = orphan(old_toc_entry_id=None, old_source_block_id=None,
                   old_printed_heading=None, printed_label="14")
    result = plan([stray], [entry()])
    assert not result["refused"]
    assert "run-only" in result["finished"][0]["detail"]


# --- an excluded row is not rebound ---------------------------------------
def test_document_3149_absence_claims_are_never_carried_forward():
    # Pages 6 and 7 print the sections, marked deleted. The claim that the
    # source omits them is false, and the live entries already carry the
    # correct parser_defect.
    for label in ("14", "15", "16", "18"):
        excluded = orphan(document_id=3149, printed_label=label,
                          resolution="absent_in_source",
                          evidence={"human_page_review": True,
                                    "render_artifact": ["p6.png"]})
        live = [entry(document_id=3149, printed_label=label)] + [
            e | {"document_id": 3149} for e in bracketing()]
        (refusal,) = plan([excluded], live)["refused"]
        assert refusal["kind"] == "excluded"
        assert "CONTRADICTED BY THE PAGE" in refusal["detail"]


def test_document_4427_absence_claims_are_never_carried_forward():
    excluded = orphan(document_id=4427, printed_label="16",
                      resolution="absent_in_source",
                      evidence={"human_page_review": True,
                                "render_artifact": ["p15.png"]})
    live = [entry(document_id=4427, printed_label="16")] + [
        e | {"document_id": 4427} for e in bracketing()]
    (refusal,) = plan([excluded], live)["refused"]
    assert refusal["kind"] == "excluded"
    assert "CONTESTED READING" in refusal["detail"]


def test_the_exclusion_is_narrow_and_does_not_swallow_the_document():
    # Only the labels the page evidence names, only that resolution.
    assert excluded_reason(3149, "3", "absent_in_source") is None
    assert excluded_reason(3149, "14", "parser_defect") is None
    assert excluded_reason(900, "14", "absent_in_source") is None
    assert excluded_reason(3149, " 14 ", "absent_in_source")


def test_every_exclusion_states_its_page_evidence():
    for rule in EXCLUSIONS:
        assert rule["labels"] and rule["reason"]
        assert len(rule["reason"]) > 200, "an exclusion must argue, not assert"


# --- a newer reading always wins ------------------------------------------
def test_a_live_entry_that_already_carries_a_decision_is_left_alone():
    live = [entry(standing_adjudication_id="cccccccc-0000-0000-0000-0001",
                  standing_resolution="parser_defect",
                  standing_decided_by="claude.absent-class-page-review/1")]
    (refusal,) = plan([orphan()], live)["refused"]
    assert refusal["kind"] == "already_decided"
    assert "never stacks" in refusal["detail"]


def test_an_entry_that_is_no_longer_pending_is_refused():
    (refusal,) = plan([orphan()], [entry(is_pending_gap=False)])["refused"]
    assert refusal["kind"] == "not_a_gap"


def test_an_anchor_that_lands_on_a_now_resolved_entry_is_finished():
    # The anchor still matches -- same block, label and heading -- but the
    # replay linked the entry to a provision. That is the decision's work
    # completed, not lost, and it must not be reported as a refusal.
    live = [entry(resolved=True, is_pending_gap=False)]
    result = plan([orphan()], live)
    assert not result["rebind"] and not result["refused"]
    assert "no gap left" in result["finished"][0]["detail"]


# --- evidence that points at a regenerated identifier ----------------------
def test_found_elsewhere_with_an_unresolvable_provision_is_refused():
    dead = orphan(resolution="found_elsewhere",
                  evidence={"found_provision_id": "dddddddd-0000-0000-0000-1"})
    (refusal,) = plan([dead], [entry()])["refused"]
    assert refusal["kind"] == "dead_pointer"


def test_found_elsewhere_rewrites_the_provision_and_keeps_the_dead_id():
    live_provision = "eeeeeeee-0000-0000-0000-000000000002"
    ok = orphan(resolution="found_elsewhere",
                evidence={"found_provision_id": "dddddddd-0000-0000-0000-1"},
                reresolved_provision_id=live_provision)
    (row,) = plan([ok], [entry()])["rebind"]
    evidence = reattached_evidence(ok["evidence"], row)
    assert evidence["found_provision_id"] == live_provision
    assert (evidence["found_provision_id_before_replay"]
            == "dddddddd-0000-0000-0000-1")


def test_other_instrument_is_always_refused():
    row = orphan(resolution="other_instrument",
                 evidence={"other_instrument_id": "ffffffff-0000-0000-0000-1"})
    (refusal,) = plan([row], [entry()])["refused"]
    assert refusal["kind"] == "regenerated_pointer"


# --- the absence re-check -------------------------------------------------
def absence(**kw):
    return orphan(resolution="absent_in_source",
                  evidence={"assistant_page_review": True,
                            "render_artifact": ["p1.png"],
                            "render_sha256": ["ab"], "observed": "nothing"},
                  **kw)


def test_absence_survives_a_replay_that_left_the_document_intact():
    result = plan([absence()], [entry()] + bracketing())
    assert result["rebind"] and not result["refused"]


def test_absence_is_refused_where_the_body_no_longer_brackets_the_section():
    # check 4 of review_absent_sections: nothing after this entry resolves, so
    # the body no longer demonstrably covers where the section would sit.
    live = [entry()] + [e for e in bracketing() if e["ordinal"] < 7]
    (refusal,) = plan([absence()], live)["refused"]
    assert refusal["kind"] == "absence_recheck"
    assert "check 4" in refusal["detail"]


def test_absence_is_refused_on_a_document_that_now_looks_truncated():
    # check 5: a quarter or more of the contents list unresolved is the
    # truncated-copy shape, where the section is absent from the FILE.
    # The section is still bracketed by resolved entries, so check 4 holds and
    # only check 5 can refuse: 5 of 16 contents entries unresolved.
    live = [entry()] + bracketing(n=12) + [
        entry(toc_entry_id=700 + i, ordinal=20 + i, printed_label=f"g{i}",
              printed_heading=f"Gap {i}.", source_block_id=7000 + i)
        for i in range(4)]
    (refusal,) = plan([absence()], live)["refused"]
    assert refusal["kind"] == "absence_recheck"
    assert "check 5" in refusal["detail"]


def test_the_absence_recheck_can_be_measured_without_it_but_only_measured():
    live = [entry()] + [e for e in bracketing() if e["ordinal"] < 7]
    assert plan([absence()], live, recheck_absence=False)["rebind"]


# --- provenance -----------------------------------------------------------
def test_the_written_evidence_names_the_row_it_came_from():
    (row,) = plan([orphan()], [entry(toc_entry_id=4242)])["rebind"]
    evidence = reattached_evidence(orphan()["evidence"], row)
    assert evidence["defect_class"] == "printed_section_absent_from_tree"
    assert evidence["reattached_from"]["toc_entry_id"] == 11
    assert (evidence["reattached_from"]["adjudication_id"]
            == "00000000-0000-0000-0000-000000000001")
    assert "source_block_id" in evidence["reattached_from"]["anchor"]


@pytest.mark.parametrize("value,expected", [
    (None, ""), ("  7 ", "7"), ("Power to make rules.", "Power to make rules.")])
def test_norm_trims_and_nothing_else(value, expected):
    assert norm(value) == expected


def test_norm_does_not_fold_case_or_punctuation():
    # Two contents entries differing only in case are two entries. Folding
    # them would turn a refusal into a guess.
    assert norm("Short title.") != norm("SHORT TITLE.")


# --- migration 0052's identity, carried whole ------------------------------
def test_the_entry_source_page_is_part_of_the_identity():
    # Migration 0052 identifies a printed contents entry by source block,
    # printed label and printed heading with source_page carried along. An
    # entry whose page differs is a different entry, even on the same block.
    (refusal,) = plan([orphan()], [entry(source_page=4)])["refused"]
    assert refusal["kind"] == "no_match"


def test_the_ordinal_is_never_part_of_the_identity():
    # 0052 removed ordinal equality from the disposition supersession rule
    # because a replay moves it beneath every already-reviewed row. Nothing
    # here may reintroduce it.
    (row,) = plan([orphan()], [entry(ordinal=41)])["rebind"]
    assert row["ordinal_moved"] is True
