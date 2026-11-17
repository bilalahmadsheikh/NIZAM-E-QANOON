"""Rule `reviewed_chapter_opener`, the inserted-chapter print form (doc 4441, the Pakistan Penal Code, 17 Nov 2026).

An amendment-inserted chapter prints as '2[CHAPTER VA' with its title in the next block. Unreviewed, the line is read as
the previous section's text and the chapter's sections fall under the chapter before it. Named on a page review, the
block opens the chapter; nothing changes for a block that is not named.
"""
import copy

import pytest

from nizam.corpus import segment as S


def block(bid, text, page=58, y=120):
    return dict(id=bid, text=text, page_no=page, y0=y, page_height=792, x0=70, x1=560)


# the opener blocks' texts as the PPC's text layer stores them, and the label each must give
OPENERS = [("2[CHAPTER VA \n", "VA"), ("2[CHAPTER IXA \n", "IXA"), ("1[CHAPTER XVI A] \n", "XVIA"),
           ("2[CHAPTER XVII A \n", "XVIIA"), ("1[CHAPTER XVII B \n", "XVIIB"), ("2[CHAPTER XXA \n", "XXA")]


def ppc_blocks(opener):
    return [block(1, "120. Concealing design to commit offence punishable with imprisonment. Whoever "
                     "intending to facilitate the commission of an offence shall be punished.", y=60),
            block(798916, opener),
            block(798917, "CRIMINAL CONSPIRACY \n", y=160),
            block(798918, "120A. Definition of criminal conspiracy. When two or more persons agree to do an "
                          "illegal act, such an agreement is designated a criminal conspiracy.", y=200)]


@pytest.mark.parametrize("opener,label", OPENERS, ids=[l for _o, l in OPENERS])
def test_reviewed_inserted_chapter_opens_and_owns_the_next_section(opener, label):
    blocks = ppc_blocks(opener)
    original = copy.deepcopy(blocks)
    seg = S.segment(blocks, detect_contents=False,
                    structural_overrides={"source_chapter_opener_blocks": [798916]})
    chapter = next(n for n in seg.flatten() if n.kind == "chapter")
    assert chapter.label == label and chapter.first_block == 798916
    assert [n.label for n in chapter.children if n.kind == "section"] == ["120A"]
    s120 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "120")
    # the heading line no longer ends section 120's text
    assert "CHAPTER" not in (s120.text or "")
    assert blocks == original


def test_unreviewed_inserted_chapter_does_not_open():
    seg = S.segment(ppc_blocks(OPENERS[0][0]), detect_contents=False)
    assert not any(n.kind == "chapter" for n in seg.flatten())


@pytest.mark.parametrize("text", ["2[CHAPTER VA unrelated prose that follows on the same line \n",
                                  "[CHAPTER V AB \n", "2[SCHEDULE VA \n"])
def test_reviewed_opener_refuses_a_block_that_is_not_an_inserted_chapter(text):
    with pytest.raises(ValueError, match="source.chapter|source_chapter"):
        S.segment(ppc_blocks(text), detect_contents=False,
                  structural_overrides={"source_chapter_opener_blocks": [798916]})
