"""Deriving instrument.duplicate_of from the source-level incompleteness record.

The record is durable and the flag is not: re-segmentation retires instrument
rows, so the flag is re-applied from the record after every replay. These are
the cases where re-applying it would be wrong.
"""
from tools.apply_source_incompleteness import decide

TRUNCATED = "a714681a-964d-4c65-9e86-8299d761f65a"   # document 127
COMPLETE = "de3b8762-b3f6-42bc-86e2-44300cd8a89a"    # document 3573
SOMETHING_ELSE = "00000000-0000-0000-0000-000000000001"


def test_a_fresh_replay_gets_the_flag_reapplied():
    action, _why = decide(TRUNCATED, COMPLETE, already=None)
    assert action == "set"


def test_running_it_twice_changes_nothing():
    action, _why = decide(TRUNCATED, COMPLETE, already=COMPLETE)
    assert action == "done"


def test_it_never_retires_a_tree_in_favour_of_nothing():
    # If the complete document's own instrument has not been rebuilt yet, both
    # copies of the Act would disappear from the release. Refuse.
    action, why = decide(TRUNCATED, None, already=None)
    assert action == "skip"
    assert "nothing" in why


def test_a_truncated_document_with_no_instrument_is_left_alone():
    action, _why = decide(None, COMPLETE, already=None)
    assert action == "skip"


def test_it_does_not_overwrite_someone_else_s_resolution():
    # Instrument identity resolution may already have pointed this tree
    # somewhere. That is a decision with its own evidence; do not silently
    # replace it.
    action, why = decide(TRUNCATED, COMPLETE, already=SOMETHING_ELSE)
    assert action == "skip"
    assert SOMETHING_ELSE in why
