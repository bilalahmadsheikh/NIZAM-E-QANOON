"""Tests for agent JG's rule `reviewed_unstopped_rule_opener` (doc 4497 E28, the National Accountability Ordinance
1999, pp861 and 884), an extension of rule `reviewed_printed_rule_opener` (key source_printed_rule_openers; ported as segmenter
group 30, 17 Oct 2026; from claude/agJF/test_jg_rule_h_DRAFT.py b5cbeed5). Pure: segment() over
hand-made blocks shaped like E28, under the DEFAULT profile (doc 4497 has 28 released default-profile siblings)."""
import pytest

from nizam.corpus.segment import segment


def _b(i, text, page=1, y=100.0):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": 210.0, "x1": 488.0, "text": text}


BODY = [
    _b(1, "31D.  Notwithstanding anything contained in this Ordinance, no inquiry shall be initiated. \n", y=60.0),
    _b(2, " 3[31E The Chairman NAB or the Court may in the facts and \ncircumstances of a case take such measures. \n",
       y=90.0),
    _b(3, "32 (a) Any 5[person convicted may, within ten days, prefer an appeal to the High Court. \n", y=120.0),
    _b(4, "(b) \nAll Appeals shall be heard by a Bench of not less than two judges. \n", y=150.0),
    _b(5, "33.  Any and all proceedings pending shall stand transferred. \n", y=180.0),
]
OPENERS = [{"source_block_id": 2, "label": "31E", "source_prefix": "3[31E The Chairman NAB"},
           {"source_block_id": 3, "label": "32", "source_prefix": "32 (a) Any 5[person"}]


def _sections(seg):
    return [n.label for n in seg.flatten() if n.kind == "section"]


def test_unstopped_section_labels_open_in_the_default_profile():
    seg = segment(BODY, structural_overrides={"source_printed_rule_openers": OPENERS})
    assert _sections(seg) == ["31D", "31E", "32", "33"]
    s31e = next(n for n in seg.flatten() if n.kind == "section" and n.label == "31E")
    assert (s31e.text or "").startswith("The Chairman NAB or the Court")
    s32 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "32")
    assert "prefer an appeal" in " ".join([s32.text or ""] + [c.text or "" for c in s32.children])
    s31d = next(n for n in seg.flatten() if n.kind == "section" and n.label == "31D")
    assert "31E" not in (s31d.text or "") and "prefer an appeal" not in (s31d.text or "")


def test_inert_without_the_key():
    assert "31E" not in _sections(segment(BODY)) and "32" not in _sections(segment(BODY))


def test_an_unstopped_label_before_a_lower_case_word_is_refused():
    bad = [{"source_block_id": 3, "label": "32", "source_prefix": "32 (a) Any 5[person"},
           {"source_block_id": 1, "label": "31", "source_prefix": "31D.  Notwithstanding"}]
    with pytest.raises(ValueError):   # '31D.' does not print the label '31' then a stop
        segment(BODY, structural_overrides={"source_printed_rule_openers": bad})
    lower = [{"source_block_id": 3, "label": "32", "source_prefix": "32 (a) Any 5[person"}]
    blocks = BODY[:2] + [_b(3, "32 of the Code shall apply to every such appeal before the Court. \n", y=120.0)] + BODY[3:]
    with pytest.raises(ValueError):   # prefix not printed in the block
        segment(blocks, structural_overrides={"source_printed_rule_openers": lower})
    with pytest.raises(ValueError):   # '32 of' -- no capital or '(' after the spaces: still malformed
        segment(blocks, structural_overrides={"source_printed_rule_openers": [
            {"source_block_id": 3, "label": "32", "source_prefix": "32 of the Code shall apply"}]})


def test_a_prefix_not_in_its_block_fails_closed():
    with pytest.raises(ValueError):
        segment(BODY, structural_overrides={"source_printed_rule_openers": [
            {"source_block_id": 4, "label": "32", "source_prefix": "32 (a) Any 5[person"}]})


CLAUSES = [
    _b(10, "8. (a) The President may appoint a Prosecutor General Accountability. \n", y=60.0),
    _b(11, "(b) \nThe Prosecutor General shall give advice to the Chairman NAB. \n", y=90.0),
    _b(12, "(c)    The Prosecutor General may appoint Special Prosecutors.] \n", y=120.0),
    _b(13, "1 (d)   In case the Prosecutor General Accountability is absent \nany other Law Officer shall act.] \n",
       page=2, y=60.0),
    _b(14, "9.  (a)  A holder of a public office is said to commit the offence of corruption. \n", page=2, y=100.0),
]
CLAUSE_OPENER = [{"source_block_id": 13, "label": "d", "kind": "clause",
                  "source_prefix": "1 (d)   In case the Prosecutor"}]


def _clauses(seg, section):
    sec = next(n for n in seg.flatten() if n.kind == "section" and n.label == section)
    return {c.label: c for c in sec.children if c.kind == "clause"}


def test_a_clause_behind_its_note_marker_opens():
    seg = segment(CLAUSES, structural_overrides={"source_printed_rule_openers": CLAUSE_OPENER})
    cl = _clauses(seg, "8")
    assert "d" in cl and (cl["d"].text or "").startswith("In case the Prosecutor General")
    assert "In case" not in (cl["c"].text or "") and not (cl["c"].text or "").rstrip().endswith("1")


def test_clause_marker_inert_without_the_key():
    assert "d" not in _clauses(segment(CLAUSES), "8")


def test_a_stopped_opener_still_opens_as_before():
    stopped = [_b(20, "4. \nThis Ordinance extends to the whole of Pakistan. \n", y=60.0),
               _b(21, "5. In this Ordinance, unless the context otherwise requires. \n", y=90.0)]
    seg = segment(stopped, structural_overrides={"source_printed_rule_openers": [
        {"source_block_id": 21, "label": "5", "source_prefix": "5. In this Ordinance"}]})
    assert _sections(seg) == ["4", "5"]


# Extension (lead 17 Oct, E28 p871 s.18(c)): a substituted clause label printed closed in its own bracket, '7[(c)]'.
CLOSED = [
    _b(30, "18.    (a) The Court shall not take cognizance of any offence. \n", y=60.0),
    _b(31, "(b) \nA reference shall be initiated by the National Accountability Bureau. \n", y=90.0),
    _b(32, "7[(c)] \nWhere the Chairman NAB is of the opinion that it is necessary, he shall refer the matter.] \n",
       y=120.0),
    _b(33, "(d) \nThe responsibility for inquiry shall rest on the NAB. \n", y=150.0),
]
CLOSED_OPENER = [{"source_block_id": 32, "label": "c", "kind": "clause",
                  "source_prefix": "7[(c)] \nWhere the Chairman"}]


def test_a_closed_bracket_label_takes_its_bracket():
    seg = segment(CLOSED, structural_overrides={"source_printed_rule_openers": CLOSED_OPENER})
    cl = _clauses(seg, "18")
    assert (cl["c"].text or "").startswith("Where the Chairman NAB")
    assert (cl["c"].text or "").rstrip().endswith("refer the matter.]")


def test_closed_bracket_inert_without_the_key():
    cl = _clauses(segment(CLOSED), "18")
    assert not (cl.get("c") and (cl["c"].text or "").startswith("Where"))


# s.8 (E28 p860): '8.  1[(a) (i) The President ...' -- clause (a) and its first item (i) on the section's first line.
FUSED = [
    _b(40, "8.  1[(a) (i) The President of Pakistan may appoint any person as Prosecutor General. \n", y=60.0),
    _b(41, " \n(ii)     The Prosecutor General shall hold independent office. \n", y=90.0),
    _b(42, " \n(b) \nThe Prosecutor General shall give advice to the Chairman NAB. \n", y=120.0),
]
FUSED_OPENERS = [{"source_block_id": 40, "label": "a", "kind": "clause", "source_prefix": "1[(a) (i) The President"},
                 {"source_block_id": 40, "label": "i", "kind": "clause", "source_prefix": "(i) The President"}]


def test_a_fused_clause_and_item_both_open():
    seg = segment(FUSED, structural_overrides={"source_printed_rule_openers": FUSED_OPENERS})
    sec = next(n for n in seg.flatten() if n.kind == "section" and n.label == "8")
    labels = [n.label for n in seg.flatten() if n.kind == "clause"]
    assert labels[:2] == ["a", "i"] and "ii" in labels and "b" in labels
    assert not (sec.text or "").strip()
    cl_i = next(n for n in seg.flatten() if n.kind == "clause" and n.label == "i")
    assert (cl_i.text or "").startswith("The President of Pakistan")


def test_fused_openers_fail_closed_out_of_order():
    with pytest.raises(ValueError):   # (i) cut first leaves no '1[(a) (i) The President' to cut
        segment(FUSED, structural_overrides={"source_printed_rule_openers": FUSED_OPENERS[::-1]})
