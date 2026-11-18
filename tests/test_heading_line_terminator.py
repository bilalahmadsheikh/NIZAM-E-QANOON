"""Rule `reviewed_heading_line` (agK3 rule C), widened 18 Nov 2026 (D-083): the printed heading may close with its
terminator -- 'Custody, preservation, etc. of certain antiquities.- (1) where ...' (AJK Antiquities Act 1986, doc
10935 s.5) -- which leaves the text with it; the heading is the words before. Pure: segment() over hand-made blocks."""
import pytest

from nizam.corpus.segment import segment

OD = {"export": ".artifacts/x.json", "document_id": 10935, "question_id": "q1"}


def _blocks(second):
    return [
        {"id": 1, "page_no": 1, "y0": 100.0, "page_height": 792.0, "x0": 140.0, "x1": 560.0,
         "text": "4. \nDispute as to whether any product, etc. is an antiquity. If any question arises whether any "
                 "product is an antiquity it shall be referred to the Government."},
        {"id": 2, "page_no": 1, "y0": 160.0, "page_height": 792.0, "x0": 140.0, "x1": 560.0, "text": second},
        {"id": 3, "page_no": 1, "y0": 260.0, "page_height": 792.0, "x0": 140.0, "x1": 560.0,
         "text": "6. \nAccidental discovery.- Whoever finds any antiquity shall inform the Director General."},
    ]


S5 = ("5. \nCustody, preservation, etc. of certain antiquities.- (1) where the Director General receives any "
      "information he shall take steps. \n(2) Where the owner is not traceable the Director General may act.")


def _section(seg, label):
    return next(n for n in seg.flatten() if n.kind == "section" and n.label == label)


def _spec(label, block, heading):
    return {"source_heading_lines": [{"label": label, "source_block_id": block, "heading": heading,
                                      "owner_decision": OD}]}


def test_a_heading_closed_by_its_terminator_leaves_the_text_without_it():
    seg = segment(_blocks(S5), structural_overrides=_spec("5", 2, "Custody, preservation, etc. of certain antiquities"))
    s5 = _section(seg, "5")
    assert s5.heading == "Custody, preservation, etc. of certain antiquities"
    text = " ".join(s5.text_parts + [p for c in s5.children for p in c.text_parts])
    assert "Custody" not in text and ".-" not in text and "receives any information" in text


def test_a_terminator_followed_by_text_on_the_same_line():
    seg = segment(_blocks(S5), structural_overrides=_spec("6", 3, "Accidental discovery"))
    s6 = _section(seg, "6")
    assert s6.heading == "Accidental discovery"
    assert " ".join(s6.text_parts).startswith("Whoever finds any antiquity")


def test_words_that_run_on_without_a_terminator_still_fail_closed():
    with pytest.raises(ValueError, match="lacks exact source evidence"):
        segment(_blocks(S5), structural_overrides=_spec("5", 2, "Custody, preservation, etc. of certain antiq"))
