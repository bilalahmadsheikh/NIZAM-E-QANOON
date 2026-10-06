"""The reader's words survive a re-attachment unchanged: no DB required.

`observed` is what a person or an assistant saw on a rendered page. Until
21 Sep 2026 `tools/reattach_orphaned_adjudications.py` appended its own
provenance to it on every carry, so a decision that survived three replays
reached 1,458 characters around an 861-character kernel. These are the
regressions for that: the note is recovered, never compounded, and the
provenance travels as structured evidence beside it.
"""
from tools.reattach_orphaned_adjudications import (
    REATTACH_BASIS, exact_ambiguous_match, reader_words)

NOTE = (" [RE-ATTACHED after a replay: matched on document_id + source_block_id,"
        " which is stable across re-segmentation where candidate_id is not."
        " The printed page this observation describes has not changed.]")

# The real specimen: document 1154, source block 56861, printed label '2'.
KERNEL = (
    "Page 2 of the The West Pakistan Requisitioned Land (Continuance) Act, "
    "1958. prints section 1 with '(2) It extends to the whole of 2[Province of "
    "the Khyber Pakhtunkhwa] except...' and '(3) It shall come into force at "
    "once.', then '2. In this Act, unless there is anything repugnant in the "
    "subject or context.--' with definitions (i) to (iii), marginal note "
    "'Definitions.'.")


def test_a_clean_observation_is_returned_untouched():
    assert reader_words(KERNEL) == KERNEL


def test_one_appended_note_is_taken_back_off():
    assert reader_words(KERNEL + NOTE) == KERNEL


def test_three_appended_notes_are_all_taken_back_off():
    # The measured shape: 861 -> 1060 -> 1259 -> 1458, +199 per replay.
    inflated = KERNEL + NOTE + NOTE + NOTE
    assert len(inflated) - len(KERNEL) == 3 * len(NOTE)
    assert reader_words(inflated) == KERNEL


def test_carrying_forward_is_idempotent_in_length():
    # The property that was broken: carrying a decision forward N times must
    # not make its observation longer N times.
    observed = KERNEL
    for _ in range(10):
        observed = reader_words(observed)
    assert observed == KERNEL


def test_a_note_in_the_middle_is_removed_without_eating_the_reading():
    assert reader_words("Before." + NOTE + " After.") == "Before. After."


def test_the_earlier_18_september_wording_is_stripped_too():
    # 335 of the 1,439 inflated rows carry this older variant. The pattern
    # matches the SHAPE of an appended note, not one fixed sentence, so a
    # wording that changed again would still be recovered.
    older = (" [RE-ATTACHED after the 18 Sep replay: matched on "
             "document+source_block_id, which is stable across "
             "re-segmentation where candidate_id is not.]")
    assert reader_words(KERNEL + older) == KERNEL
    assert reader_words(KERNEL + older + NOTE) == KERNEL


def test_square_brackets_in_the_reading_itself_are_preserved():
    # Statutory text is full of amendment markers -- '2[Province of the Khyber
    # Pakhtunkhwa]', '1[18* * *]'. Stripping must not touch them.
    text = "Page 7 prints 1[18* * *] with the footnote 'Section-18 omitted'."
    assert reader_words(text) == text
    assert reader_words(text + NOTE) == text


def test_an_empty_or_missing_observation_is_an_empty_string():
    assert reader_words(None) == ""
    assert reader_words("") == ""
    assert reader_words(NOTE) == ""


def test_the_basis_is_stated_once_as_a_field_not_as_prose():
    # It is carried in evidence.reattachment.basis. It must not be phrased as
    # something that would read as part of the observation.
    assert "RE-ATTACHED" not in REATTACH_BASIS
    assert not REATTACH_BASIS.startswith("[")
    assert "source_block_id" in REATTACH_BASIS


def test_multi_label_block_requires_one_exact_source_fingerprint():
    rows = [
        {"old_candidate_id": "old", "new_candidate_id": "new-2"},
        {"old_candidate_id": "old", "new_candidate_id": "new-1"},
    ]
    fingerprints = {
        "old": (1696, 109295, "2", 3, 109284, (109295, 220)),
        "new-2": (1696, 109295, "2", 3, 109284, (109295, 220)),
        "new-1": (1696, 109295, "1", 3, 109281, (109295, 220)),
    }
    assert exact_ambiguous_match(rows, fingerprints) is rows[0]


def test_multi_label_block_refuses_missing_or_duplicate_matches():
    rows = [
        {"old_candidate_id": "old", "new_candidate_id": "new-1"},
        {"old_candidate_id": "old", "new_candidate_id": "new-2"},
    ]
    assert exact_ambiguous_match(rows, {"new-1": ("same",)}) is None
    assert exact_ambiguous_match(
        rows, {"old": ("same",), "new-1": ("other",),
               "new-2": ("other",)}) is None
    assert exact_ambiguous_match(
        rows, {"old": ("same",), "new-1": ("same",),
               "new-2": ("same",)}) is None
