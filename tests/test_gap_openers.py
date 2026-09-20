r"""Openers found by reading the contents-gap census, 19-20 Sep 2026.

`tools/census_gap_causes.py` classes every pending contents gap by the shape the
promised label is printed in. The `period` class -- "the label AND the heading
are printed plainly and the tree still lacks the section" -- is the one that
should be pure parser defect, and 23 gaps were in it. Reading all 23 against
source found one general shape, and it is here.

A digit set against an amendment bracket is a MARKER, not a label level. The
compound-label rule exists for ``10.3`` and ``10.3.3``, the hierarchical unit
building regulations cite, and its ``\s*\.\s*`` between levels collects any
whitespace. What that actually gathers in this corpus is the footnote or
amendment marker printed after a section's stop, so section 5 of the KP
Employees of Transport Department (Regularization of Services) Act 2017 -- the
only operative section that Act has -- lives in the tree as "5. 1", which no
citation can reach.

The guards below are the other half of the rule and matter as much as the
repair: the Punjab Excise Manual prints a genuine ``5.30 [4]``, and a tariff
table prints ``24.`` over ``16 Rs 1,000,000``. Both must come through unchanged.
"""
from __future__ import annotations

from nizam.corpus.segment import classify, segment


def blocks(*texts: str, page: int = 1) -> list[dict]:
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0}
            for i, t in enumerate(texts)]


# ------------------------------------------------- the marker is not a level
def test_marker_on_the_next_line_is_not_a_second_label_level():
    """Document 2686 page 4, the KP Employees of Transport Department
    (Regularization of Services) Act 2017. PyMuPDF puts the superscript on its
    own line, and the section became "5. 1".
    """
    found = classify(
        "5. \n1 [Regularization of Services of PBT Employees.---Notwithstanding "
        "anything \ncontained in any other relevant law or rules, all PBT "
        "employees shall be deemed validly appointed. \n")
    assert found is not None
    assert (found[0], found[1]) == ("section", "5"), found[:2]
    assert found[2].startswith("1 [Regularization"), found[2][:40]


def test_marker_after_a_space_is_not_a_second_label_level():
    """Document 4348 page 16, the Provincial Employees' Social Insurance
    Ordinance. Same apparatus, printed on the same line.
    """
    found = classify(
        "23. 2 [ Invalidity pension]. —(1) An insured person who sustains "
        "invalidity shall be \nentitled to invalidity pension. \n")
    assert (found[0], found[1]) == ("section", "23"), found[:2]


def test_two_markers_in_one_opener_keep_the_printed_section_number():
    """Document 2893 page 5, the Punjab Waqf Properties Ordinance: the heading
    carries marker 7 and its first subsection carries marker 8.
    """
    found = classify(
        "3. 7 [Chief Administrator].– 8 [(1) Secretary to the Government, "
        "Auqaf and Religious Affairs Department shall be the Chief "
        "Administrator.] \n")
    assert (found[0], found[1]) == ("section", "3"), found[:2]


def test_omitted_section_behind_two_brackets_is_still_citable():
    """Document 4451 page 49, the Customs Act 1969: ``15[20. 112 [Omitted]``.
    Section 20 is omitted and must remain a citable placeholder, not "20. 112".
    """
    found = classify("15[20. 112 [Omitted]\n")
    assert (found[0], found[1]) == ("section", "20"), found[:2]


def test_the_marked_section_reaches_the_tree():
    """The classifier is not the tree. `classify` never sees a block -- it sees
    the pieces `subdivide` cut it into -- so the opener is asserted end to end.
    """
    seg = segment(blocks(
        "AN ACT to provide for the regularization of services.\n"
        "It is hereby enacted as follows:",
        "1. Short title and commencement.--- (1) This Act may be called the "
        "Example Act, 2017.",
        "5. \n1 [Regularization of Services of PBT Employees.---Notwithstanding "
        "anything contained in any other law, all PBT employees holding the "
        "post shall be deemed to have been so validly appointed.] \n",
    ))
    labels = [n.label for n in seg.root.children if n.kind == "section"]
    assert "5" in labels, labels
    assert "5. 1" not in labels, labels


# ------------------------------------------------------------------- guards
def test_a_tight_compound_label_keeps_its_amendment_bracket():
    """Punjab Excise Manual, document 4017 page 10, prints rules 5.28, 5.29,
    5.30, 5.31, and rule 5.30 opens ``5.30 [4] (a) [The fee shall be fixed``.
    That is a real compound label standing against a real amendment bracket.
    The bracket alone cannot tell the two apart -- the tight dot can.
    """
    found = classify(
        "5.30 [4] (a) [The fee shall be fixed at the current rates of vend fee "
        "of actual sales \nafter every 10 days]. \n")
    assert (found[0], found[1]) == ("section", "5.30"), found[:2]


def test_ordinary_hierarchical_labels_are_untouched():
    for text, label in (
            ("10.3 Structural design shall conform to the code. \n", "10.3"),
            ("10.3.3 Foundations shall be designed for the soil report. \n",
             "10.3.3"),
            # the whitespace-padded citation `subdivide_spans` already assumes
            ("6 . 2 . Something about the rule. \n", "6 . 2"),
    ):
        found = classify(text)
        assert found is not None and found[1] == label, (text, found)


def test_a_fee_table_does_not_become_a_section():
    """Page 23 of document 3344 prints a fee table as ``24.`` over
    ``16 Rs 1,000,000``. An earlier and looser form of this repair -- refusing
    the newline inside the label outright -- invented six sections here, and 479
    pieces in 90 documents moved with them. The rule was narrowed to the bracket
    because of this page.
    """
    assert classify("24. \n16 Rs 1,000,000 \n") is None
    assert classify("25. \n17 Rs 1,000,000 \n") is None


def test_a_column_of_page_numbers_is_unchanged():
    """``1.`` ``2.`` ``3.`` ``4.`` in one block is a numbering column, and it is
    left exactly as the current parser reads it: this repair is about the
    bracket, and must move nothing that has none.
    """
    found = classify("1. \n2. \n3. \n4. \n")
    assert found is not None and found[1] == "1. 2. 3. 4", found
