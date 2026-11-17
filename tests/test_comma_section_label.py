"""Rule `reviewed_comma_section_label` (doc 11383 p16, D-076): the Gazette printed the 27th Amendment's s.45 as
'45, Amendment of Article 206 ...' -- a comma for the stop. A reviewed block opens that section only when its number
follows the section open before it; anything else fails closed."""
import pytest

from nizam.corpus.segment import segment

BLOCKS = [
    {"id": 1, "page_no": 1, "text": "44. Amendment of Article 205 of the Constitution.— In the Constitution, in "
                                    "Article 205, the words “the Federal Constitutional Court or” shall be inserted."},
    {"id": 2, "page_no": 1, "text": "45, Amendment of Article 206 of the Constitution.— In the Constitution, in "
                                    "Article 206,-"},
    {"id": 3, "page_no": 1, "text": "(a) in clause (1), the words “Federal Constitutional Court or of the” shall be "
                                    "inserted;"},
]


def test_reviewed_comma_label_opens_the_next_section():
    parsed = segment([dict(b) for b in BLOCKS], structural_overrides={"source_comma_label_section_blocks": [2]})
    sections = [n for n in parsed.flatten() if n.kind == "section"]
    assert [s.label for s in sections] == ["44", "45"]
    s45 = sections[1]
    assert s45.first_block == 2 and "Article 206" in (s45.heading or "") + s45.text
    assert any(c.kind == "clause" and c.label == "a" for c in s45.children)


def test_without_review_the_comma_label_opens_nothing():
    parsed = segment([dict(b) for b in BLOCKS])
    assert [n.label for n in parsed.flatten() if n.kind == "section"] == ["44"]


def test_a_comma_label_out_of_sequence_fails_closed():
    blocks = [dict(b) for b in BLOCKS]
    blocks[1]["text"] = blocks[1]["text"].replace("45,", "47,", 1)
    with pytest.raises(ValueError, match="comma label section"):
        segment(blocks, structural_overrides={"source_comma_label_section_blocks": [2]})
