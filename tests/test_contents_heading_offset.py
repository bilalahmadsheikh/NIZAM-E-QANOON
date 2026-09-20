"""A printed contents list may not rename a section the body has already named.

These are regressions for the worst defect found in the corpus so far: a
citation that resolves to the right text under the wrong name. Nothing flags
it. The contents-gap queue cannot see it -- a contents list running at an
offset to the body still finds a same-numbered provision for every entry, so it
produces no unmatched entry and no gap -- and five of the eleven worst affected
documents have an empty gap queue.

Doc 4499, the Industrial Relations Act, 2008, is the case these are built from.
Page 30 prints

    37. Penalty for obstructing inspector. Whoever willfully obstructs ...
    38. Penalty for contravening section 34 or section 35, etc.

and the printed contents on page 2 lists those same two sections at 36 and 37,
because the contents omits a section the body enacts. Pairing on the number
alone gave section 37 the name of 38, and 38 the name of "WORKS COUNCIL", for
twenty-four consecutive sections. Doc 3508 (Kalam Bibi International Women
Institute Bannu Act, 2023) repeats it for twenty, doc 3387 (COVID-19
(Prevention of Hoarding) Act, 2021) for ten.

`./nz mislabelled-headings` is the census; `./nz contents-offset` finds the
documents whose lists run at a constant offset. Doc 02 §5.1.
"""
from __future__ import annotations

import pytest

from nizam.corpus import segment as _segment_module
from nizam.corpus.segment import segment

# The repair is delivered as `.patch_offset.py`, not as a direct edit to
# `nizam/corpus/segment.py`. These tests describe the candidate, so they skip --
# loudly -- until it is applied, rather than failing a suite that is green on
# the segmenter as it actually stands.
pytestmark = pytest.mark.skipif(
    not hasattr(_segment_module, "_names_another_section"),
    reason="heading-offset repair not applied: run `python .patch_offset.py --apply`")


def blocks(*texts: str, page: int = 1) -> list[dict]:
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0}
            for i, t in enumerate(texts)]


def headings(seg) -> dict[str, str | None]:
    return {n.label: n.heading for n in seg.flatten()
            if n.kind in ("section", "article")}


@pytest.mark.parametrize(
    ("printed", "promised"),
    [
        ("In trument executed in", "Instruments executed in Pakistan"),
        ("Immunity of per on attending court-martial",
         "Immunity of persons attending court-martial"),
        ("Commis sioner", "Commissioner"),
        ("Court-fees payable", "Courtfees payable"),
        ("Personcommittingqatl", "Person committing qatl"),
    ],
)
def test_extraction_variants_are_the_same_printed_name(printed, promised):
    assert not _segment_module._names_another_section(printed, promised)


@pytest.mark.parametrize(
    ("printed", "promised"),
    [
        ("Application for mineral permit", "Power of Delegation"),
        ("Power to make Regulations", "Execution or re-erection building"),
        ("Application to Environmental Protection Tribunal or Court",
         "Appointment to Environmental Protection Tribunal or Court"),
    ],
)
def test_genuinely_different_names_still_refuse_the_contents_heading(
        printed, promised):
    assert _segment_module._names_another_section(printed, promised)


# ------------------------------------------------- the offset itself
def test_an_offset_contents_list_does_not_rename_the_sections_after_it():
    """Doc 4499's shape: the contents omits section 4, so from there on every
    entry carries the number of the section before the one it names."""
    toc = ["CONTENTS",
           "1. Short title.",
           "2. Definitions.",
           "3. Appointment of inspector.",
           "4. Penalty for obstructing inspector.",
           "5. Penalty for contravening section 3.",
           "6. Works council.",
           "7. Functions of works council."]
    body = ["1. Short title. This Act may be called the Test Act.",
            "2. Definitions. In this Act, the following words have the meaning given.",
            "3. Appointment of inspector. The Government may appoint an inspector.",
            "4. Joint management board. Every company shall constitute a board.",
            "5. Penalty for obstructing inspector. Whoever obstructs an inspector shall be fined.",
            "6. Penalty for contravening section 3. Whoever contravenes section 3 shall be fined.",
            "7. Works council. Every establishment shall constitute a works council.",
            "8. Functions of works council. The functions of the council shall be to promote."]
    got = headings(segment(blocks(*toc, *body)))

    # every section keeps the name its own printed block gives it
    assert got["4"] == "Joint management board"
    assert got["5"] == "Penalty for obstructing inspector"
    assert got["6"] == "Penalty for contravening section 3"
    assert got["7"] == "Works council"
    # and no section wears the name of the one after it
    assert got["4"] != "Penalty for obstructing inspector."
    assert got["5"] != "Penalty for contravening section 3."


def test_the_section_the_contents_omits_keeps_its_own_words_as_text():
    """Nothing printed may leave the database: the name the body prints is a
    heading, and what follows it is still the provision's text."""
    toc = ["CONTENTS", "1. Short title.", "2. Penalty for obstruction."]
    body = ["1. Short title. This Act may be called the Test Act.",
            "2. Joint management board. Every company shall constitute a board."]
    seg = segment(blocks(*toc, *body))
    two = next(n for n in seg.flatten() if n.label == "2")
    assert two.heading == "Joint management board"
    assert "Every company shall constitute a board" in two.text


# ------------------------------------------------- what must not change
def test_a_contents_list_that_agrees_still_supplies_the_heading():
    toc = ["CONTENTS", "1. Short title and commencement.", "2. Definitions."]
    body = ["1. Short title and commencement. This Act may be called the Test Act.",
            "2. Definitions. In this Act, the following words have the meaning given."]
    got = headings(segment(blocks(*toc, *body)))
    assert got["1"] == "Short title and commencement."
    assert got["2"] == "Definitions."


def test_a_marginal_note_layout_still_takes_its_heading_from_the_contents():
    """Where the number and the enacted words share a column and the heading is
    a separate block, the contents entry is the only heading source there is."""
    toc = ["CONTENTS", "1. Short title.", "2. Power to appoint an inspector."]
    body = ["1. Short title. This Act may be called the Test Act.",
            "2. The Government may, by notification in the official Gazette, "
            "appoint any person to be an inspector for the purposes of this Act."]
    got = headings(segment(blocks(*toc, *body)))
    assert got["2"] == "Power to appoint an inspector."


def test_a_bare_schedule_row_is_still_not_named_from_its_own_words():
    """A row that is a name with nothing enacted after it stays unnamed: its
    words are the evidence that distinguishes it from the real section 1."""
    toc = ["CONTENTS"] + [f"{n}. Main heading {n}." for n in range(1, 9)]
    body = [f"{n}. Main heading {n}. Enacted text." for n in range(1, 9)]
    table = ["1. Total dye content, percent by mass."]
    seg = segment(blocks(*toc, *body, *table))
    rows = [n for n in seg.flatten()
            if n.label == "1" and "dye content" in (n.text or "").lower()]
    assert len(rows) == 1
    assert rows[0].heading is None


def test_a_differently_numbered_schedule_does_not_rename_its_rows():
    """Doc 4139's shape: the First Schedule was read as the contents list and
    its row 3 is "Research Officer", while the Third Schedule's row 3 is
    "Administrative Officer". The row's own word wins."""
    toc = ["CONTENTS",
           "1. Director.",
           "2. Assistant Director.",
           "3. Research Officer.",
           "4. Security Officer."]
    body = ["1. Director. Ph.D. in Anthropology with ten years experience.",
            "2. Assistant Director. Master degree in second class.",
            "3. Administrative Officer",
            "4. Security Officer. Ex-serviceman of appropriate rank."]
    got = headings(segment(blocks(*toc, *body)))
    assert got.get("3") != "Research Officer."
