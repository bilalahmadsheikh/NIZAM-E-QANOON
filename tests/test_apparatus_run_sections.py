"""A footnote run must not hold a citable section slot -- and must not take one.

A completed 200-page reading of the S7 repeated-label queue found 87 of 200
decisions (43.5%) were not legal collisions at all: both blocks were apparatus,
so the disposition demoted one footnote in favour of another and left a
footnote standing as a citable section.  That is INV-4 breakage produced by
L1, wearing an L2 disposition.

These are the regressions for the three shapes the corpus prints, and -- the
half that matters more -- the guards that keep real law out of the demotion.
The asymmetry is deliberate and is stated in `_run_member_is_apparatus`: an
apparatus row wrongly left citable is a visible queue entry, while a section
wrongly demoted is silently uncitable law.

Source-derived from documents 2366 (Punjab Land Preservation Act, page 6),
4403 (Khyber Pakhtunkhwa Court Fees, page 7) and 1927 (the same Act's Pakistan
Code printing, page 13).  Doc 02 sections 5.1-5.2; doc 03 section 2A.

These are guards on `.patch_apparatus.py`, which is measured and handed over
but NOT applied -- parser changes are batched into one replay.  Until it lands
they skip rather than fail: a red test for work deliberately not yet applied
teaches a suite to be ignored.
"""
from __future__ import annotations

import pytest

from nizam.corpus import segment as S

pytestmark = pytest.mark.skipif(
    not hasattr(S, "_run_member_is_apparatus"),
    reason=".patch_apparatus.py is not applied",
)

segment = S.segment
_is_footnote_run = S._is_footnote_run
_every_inline_note_is_apparatus = getattr(
    S, "_every_inline_note_is_apparatus", None)
_run_member_is_apparatus = getattr(S, "_run_member_is_apparatus", None)
_without_trailing_inline_footnotes = getattr(
    S, "_without_trailing_inline_footnotes", None)


def blocks(*texts: str, page: int = 1) -> list[dict]:
    """Blocks as the extractor hands them over: id, text, page, geometry."""
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0, "x0": 94.0, "x1": 500.0}
            for i, t in enumerate(texts)]


def citable(seg) -> dict[str, str]:
    """label -> first 40 characters of the text each citable node opens on."""
    out: dict[str, str] = {}

    def walk(node):
        for child in node.children:
            if child.kind in ("section", "article"):
                out.setdefault(str(child.label),
                               " ".join(child.text_parts)[:40])
            walk(child)

    walk(seg.root)
    return out


# ------------------------------------------------ source 1a: one note, one block
NOTE_RUN_PAGE = (
    "1. \nAdd. by Punjab Act IV of 1944, s. 4.",
    "2. \nSubs, ibid, for the words “or goats”.",
    "3. \nIns. ibid, s. 6.",
    "4. \nFor notification see Punjab Local Roles and Orders.",
    "5. \nSubs. for the words “Local Government”, by A. O., 1937.",
)


def test_a_page_footnote_run_set_one_note_per_block_opens_no_section():
    """Doc 2366 page 6.  No block holds more than one note, so no block-level
    test can see the run; the page-level one already proved it for the
    contents reader and now proves it for the body.
    """
    seg = segment(blocks(*NOTE_RUN_PAGE))
    assert citable(seg) == {}


def test_a_provision_numbered_into_the_run_keeps_its_section():
    """The run is evidence about the PAGE.  Section 6 continues the ascending
    numbering and so belongs to the run by shape alone -- and stays a section,
    because it carries operative modality and names no amending instrument.
    This is the guard, measured: without it the demotion takes real law.
    """
    seg = segment(blocks(
        *NOTE_RUN_PAGE,
        "6. Every order made under sections 4, 5 or 5-A shall be published "
        "in the official Gazette and shall take effect from that date.",
    ))
    assert set(citable(seg)) == {"6"}


# ---------------------------------------------- source 1b: whole run, one block
INLINE_RUN = (
    "1.Now the Code of Civil Procedure, 1908 (V of 1908).\n"
    "2 Deleted vide Khyber Pakhtunkhwa Act No. III of 2009\n"
    "3.Subs, by W.P. Ord XLIX of 1969 s.4 (a).\n"
)


def test_an_inline_footnote_run_is_not_cut_into_sections():
    """Doc 4403 page 7.  The body walk used to ask `_is_footnote_run` only in
    its `split_numbers_only` form, which answers for the number-alone layout
    and not for this one, so `subdivide` handed markers 1, 2 and 3 to the
    grammar as section numbers.
    """
    seg = segment(blocks(
        "5. The court fee payable shall be computed under this Chapter.",
        INLINE_RUN,
        "6. Nothing in this Act shall apply to a document executed before "
        "the commencement of this Act.",
    ))
    assert set(citable(seg)) == {"5", "6"}


def test_the_inline_run_is_still_recognised_without_the_body_guard():
    """The guard narrows the BODY's question only.  The contents reader keeps
    asking the unguarded one, where a wrong answer costs a TOC gap rather than
    a provision.
    """
    assert _is_footnote_run(INLINE_RUN)
    assert _is_footnote_run(INLINE_RUN, require_every_item=True)


# -------------------------------------------------------------------- guards
def test_one_operative_item_refuses_the_whole_block():
    """Two good notes cannot vouch for a third item's law.  An amending Act
    states its amendments as its own numbered sections, which read exactly
    like notes; the unquoted modality is what tells them apart.
    """
    text = ("1. Now the Code of Civil Procedure, 1908.\n"
            "2. Subs. by Act II of 1956.\n"
            "3. Ins. by Act III of 1957.\n"
            "4. The Collector shall, by notification under the Act, fix the "
            "limits of the area concerned.\n")
    assert _is_footnote_run(text)
    assert not _is_footnote_run(text, require_every_item=True)
    assert not _every_inline_note_is_apparatus(
        [line for line in text.split("\n") if line.strip()])
    # The block is therefore subdivided as before and item 4 keeps its
    # section.  Items 2 and 3 are still demoted, one piece at a time, by the
    # `_FOOTNOTE` test that was always there; item 1 is left a phantom
    # section.  That residue is the price of abstaining, and it is the right
    # price: the alternative is a rule that takes item 4 with it.
    assert "4" in citable(segment(blocks(text)))


def test_notes_below_a_provision_cannot_vouch_for_the_provision_above_them():
    text = ("The Government shall publish the rules in the official Gazette.\n"
            "1. Subs. by Act I of 1955.\n"
            "2. Ins. by Act II of 1956.\n"
            "3. Subs. by Act III of 1957.\n")
    assert _is_footnote_run(text)
    assert not _is_footnote_run(text, require_every_item=True)


def test_trailing_notes_are_not_served_as_a_deleted_sections_text():
    """Doc 4432 p37: sections 62/63 and ten notes share one source block."""
    text = (
        "63.  * * * * ]\n\n"
        "1 Substituted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n"
        "2 Substituted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n"
        "3 Deleted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n"
    )
    assert _without_trailing_inline_footnotes(text) == "63.  * * * * ]"
    parsed = segment(blocks(text))
    assert citable(parsed)["63"] == "* * * * ]"


def test_one_operative_trailing_item_vetoes_the_inline_cut():
    text = (
        "63. The Council may make rules.\n"
        "1 Substituted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n"
        "2 Inserted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n"
        "3 The Government shall publish the rules in the official Gazette.\n"
    )
    assert _without_trailing_inline_footnotes(text) == text


def test_a_provision_repealed_in_situ_stays_citable_inside_a_run():
    """Doc 1927 page 13 and doc 3892 page 49.  A provision repealed in place
    prints its own name in brackets and then the repeal formula -- word for
    word the vocabulary of an editorial note.  It is a section, and a repealed
    section must stay citable for INV-5 to answer "as at a date".  The
    bracketed opening is the discriminator: a note names no provision.
    """
    repealed = ("12. [Condition as to sale of land acquired under the Act and "
                "obligation of Local Government to keep account of moneys "
                "expended on such land.]---Repealed by Punjab Act VIII of "
                "1926, s. 5.")
    assert not _run_member_is_apparatus(repealed)
    seg = segment(blocks(
        "10. \nSubs. by Punjab Act IV of 1944, s. 4.",
        "11. \nIns. ibid.",
        repealed,
        "13. \nSubs. for the word “Gazette” by A. O., 1937.",
    ))
    assert set(citable(seg)) == {"12"}


def test_an_ordinary_numbered_section_list_is_not_a_run():
    """The run shape alone cannot be the test: a contents list and a statute's
    opening sections are numbered and ascending too.  The vocabulary is what
    separates them, and these carry none of it.
    """
    seg = segment(blocks(
        "1. Short title.\n2. Definitions.\n3. Notice of disease.\n"
        "4. Powers of the inspector.\n"))
    assert set(citable(seg)) == {"1", "2", "3", "4"}


def test_editorial_vocabulary_needs_a_named_instrument():
    """`substituted` on its own is what an amending section says.  What an
    editorial note always adds is the instrument that did the amending.
    """
    assert _run_member_is_apparatus("7. Subs. by the Finance Act, 2006.")
    assert _run_member_is_apparatus(
        "3. The word “Sind” omitted ibid, s. 3 (iii) (w.e.f. 30th May, 1951).")
    assert not _run_member_is_apparatus(
        "3. In section 5 of the said Act, for the word “five” the word "
        "“ten” is substituted.")
    assert not _run_member_is_apparatus(
        "39. When no drawback allowed.- No drawback shall be allowed on goods "
        "entered for exportation.")


def test_an_announced_quotation_of_old_text_does_not_carry_its_modality():
    """Doc 2034 page 5 prints the replaced text without quotation marks,
    announced by "which read as".  The announcement is the quotation mark --
    but only after an editorial verb and instrument have already appeared, so
    an operative rule that merely says "read as follows" keeps its veto.
    """
    assert _run_member_is_apparatus(
        "2. Subs by the W.P. Ordinance 3 of 1968, s.2 for the amended "
        "sub-section (1) which read as the Commissioner shall be the court of "
        "wards for the Province.")
    assert not _run_member_is_apparatus(
        "9. The rules which read as follows shall apply to every society.")


def test_the_editorial_cross_reference_frame_needs_its_see():
    assert _run_member_is_apparatus(
        "5. For delegation of powers to Deputy Commissioner in Khyber "
        "Pakhtunkhwa, see Gazettee of India, 1905, Part II p. 458.")
    assert not _run_member_is_apparatus(
        "7. For the purposes of this Act, the Collector shall see that the "
        "land is surveyed.")
