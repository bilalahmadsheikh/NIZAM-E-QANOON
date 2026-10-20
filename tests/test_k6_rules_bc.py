"""Agent K6's rules B and C (doc 4643, the owner-accepted Surya revision of 4472, Sindh Companies Profits (Workers'
Participation) Rules 2021; owner OCR review 16 Oct 2026). Ported by builder BZ (group 20) from
claude/agK6/agK6-rule.py. 4643 is a RELEASED DEFAULT observation and cannot be pinned to unreleased-v4, so both rules are
data-gated in EVERY profile and carry no profile name.

B `bare_serial_rows_reviewed_default` -- agent K4's rule M key `source_bare_serial_row_blocks` (a page-read block that is
  a run of consecutive bare serials 'N Text' is cut into rows N) is honoured in any profile, as
  printed_heading_reviewed_default is. Inert without the key.
C `reviewed_division_note` -- new key `source_division_note_blocks` [block ids]: a page-read 'Note:-' block inside an
  open schedule / annexure / appendix opens the division's Part 'Note'; the rest of the block is the Note's text and its
  '(a)', '(b)', '2.' are the Note's items, not rows of the division. Fails closed: a named block that does not open
  'Note:-', is not inside an open division, or is never reached raises.
"""
import pytest

from nizam.corpus import segment as S


def _b(i, text, y0, page=1):
    return {"id": i, "text": text, "page_no": page, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


NOTE = ("Note:- If the company incurs loss during a certain year it should invariably give the following information:- \n"
        "(a) Total amount of loss incurred in column (2). \n(b) Complete information in columns (4) to (7). \n"
        "2. The left out amount shall be deposited in the Fund. \n")


def _annexure(note=NOTE):
    return [_b(1, "1. \nShort title. These rules may be called the Test Rules. \n", 40.0),
            _b(2, "2. \nApplication. These rules apply to every company. \n", 60.0),
            _b(10, "ANNEXURE I \n", 100.0, page=2),
            _b(11, "1 Accounting year \n2 Profit before tax \n3 Amount allocated \n", 120.0, page=2),
            _b(12, note, 160.0, page=2)]


def _kids(seg, label):
    node = next(n for n in seg.flatten() if n.label == label and n.kind in ("annexure", "part"))
    return [(c.kind, c.label) for c in node.children]


@pytest.mark.parametrize("profile", ["default", "unreleased-v4"])
def test_B_bare_serial_rows_are_cut_in_any_profile(profile):
    kw = {} if profile == "default" else {"profile": profile}
    plain = S.segment(_annexure(), **kw)
    assert "1" not in [n.label for n in plain.flatten() if n.kind == "clause"]     # inert without the key
    seg = S.segment(_annexure(), structural_overrides={"source_bare_serial_row_blocks": [11]}, **kw)
    rows = [(n.label, n.text) for n in seg.flatten() if n.kind == "clause" and n.label in ("1", "3")]
    assert rows[0] == ("1", "Accounting year")


@pytest.mark.parametrize("profile", ["default", "unreleased-v4"])
def test_C_note_opens_the_divisions_part_note(profile):
    kw = {} if profile == "default" else {"profile": profile}
    seg = S.segment(_annexure(), structural_overrides={"source_bare_serial_row_blocks": [11],
                                                       "source_division_note_blocks": [12]}, **kw)
    assert _kids(seg, "ANNEXURE I") == [("clause", "1"), ("clause", "2"), ("clause", "3"), ("part", "Note")]
    assert _kids(seg, "Note") == [("clause", "a"), ("clause", "b"), ("clause", "2")]
    note = next(n for n in seg.flatten() if n.kind == "part" and n.label == "Note")
    assert note.text.startswith("If the company incurs loss")
    row3 = next(n for n in seg.flatten() if n.kind == "clause" and n.label == "3")
    assert row3.text == "Amount allocated"                                       # the Note no longer runs into row 3


def test_C_inert_without_the_key():
    seg = S.segment(_annexure(), structural_overrides={"source_bare_serial_row_blocks": [11]})
    assert "Note" not in [n.label for n in seg.flatten()]


def test_C_refuses_a_block_that_is_not_a_note():
    with pytest.raises(ValueError, match="is not a 'Note:-' inside an open division"):
        S.segment(_annexure("Remarks:- something. \n"), structural_overrides={"source_division_note_blocks": [12]})


def test_C_refuses_a_note_outside_a_division():
    blocks = _annexure()[:2] + [_b(12, NOTE, 160.0)]
    with pytest.raises(ValueError, match="is not a 'Note:-' inside an open division"):
        S.segment(blocks, structural_overrides={"source_division_note_blocks": [12]})


def test_C_refuses_a_block_never_reached():
    with pytest.raises(ValueError, match="not reached"):
        S.segment(_annexure(), structural_overrides={"source_division_note_blocks": [99]})


def test_C_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    assert "source_division_note_blocks" in STRUCTURAL_KEYS and "source_division_note_blocks" in STRUCTURAL_PATCH_KEYS
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {"source_division_note_blocks": [12]}}},
        {"evidence": {"structural_overrides": {"source_division_note_blocks": [7, 12]}}}])
    assert sorted(merged["source_division_note_blocks"]) == [7, 12]
    with pytest.raises(ValueError, match="source_division_note_blocks"):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {
            "source_division_note_blocks": ["x"]}}}])
