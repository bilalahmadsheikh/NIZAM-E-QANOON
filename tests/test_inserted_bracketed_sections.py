"""Source-derived boundaries for two inserted sections lost inside prior clauses."""

from nizam.corpus.segment import classify, subdivide


def test_nested_amendment_brackets_open_inserted_section():
    # Sindh Service Tribunals Act, doc 1375 p6, source block 78010.
    text = (
        "(3) No court-fee shall be payable for a Tribunal.\n\n"
        "3[4[5-A]. (1) The Chairman shall be the Accounting Officer."
    )
    pieces = subdivide(text)
    assert len(pieces) == 3
    assert classify(pieces[1])[:2] == ("section", "5-A")
    assert classify(pieces[2])[:2] == ("subsection", "1")


def test_quoted_amendment_opens_inserted_section():
    # KP Authority Act, doc 1768 p11, source block 116240.
    text = (
        "(2) The Authority may invest the money.\n\n"
        "\u201c2[22-A. Recovery of Authority dues.\n"
        "(1) The dues shall be recoverable."
    )
    pieces = subdivide(text)
    assert len(pieces) == 3
    assert classify(pieces[1])[:2] == ("section", "22-A")
    assert classify(pieces[2])[:2] == ("subsection", "1")


def test_plain_prose_reference_is_not_an_inserted_section():
    assert classify("The amendment inserted 3[4[5-A].") is None
    assert classify("\u201c2[22-A] is mentioned in the note.") is None
