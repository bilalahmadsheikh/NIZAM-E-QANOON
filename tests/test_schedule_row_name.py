"""A schedule row must not wear the section's name that shares its number.

These are the two provisions A11 still counts, and the shape behind both. They
are guards on `.patch_schedule_row_name.py`, which is measured and handed over
but NOT applied -- parser changes are batched into one replay. Until it lands
the tests skip rather than fail, because a red test for work deliberately not
yet applied teaches a suite to be ignored.

MEASURED before hand-over, against a trace of every question the entry linker
asks this guard over all 4,599 segmentable documents: 14 headings newly
refused in 9 documents, 0 newly accepted -- and each of the fourteen read
against its page.
"""
from __future__ import annotations

import pytest

from nizam.corpus import segment as S

pytestmark = pytest.mark.skipif(
    not hasattr(S, "_source_closed_name_disagrees"),
    reason=".patch_schedule_row_name.py is not applied",
)


def refuses(own: str, promised: str) -> bool:
    """Does the linker decline to paste `promised` onto a unit reading `own`?"""
    return S._names_another_section(own, promised)


# --------------------------------------------------------------------------
# the two residuals


def test_doc_1683_fee_schedule_row_keeps_its_own_name():
    """Page 6 is the SECOND SCHEDULE (Section 5), and row 4 is not section 4.

    Thirteen words, closed by a dash and never by a full stop, so the shipped
    span to the first stop is the whole row and its twelve-word cap declines to
    judge. The tree gave it the body's marginal note.
    """
    assert refuses(
        "Fee for the issue of driving licence, under clause (i) of rule "
        "26— 100 \n",
        "Amendment of W. P. Act No. XXXII of 1958.")


def test_doc_4139_staffing_schedule_row_keeps_its_own_name():
    """Page 21 prints "15. Office Assistant - cum- Storekeeper".

    PyMuPDF merges the table's remaining columns -- qualification, method of
    recruitment, age -- into the same node, so the span to the first stop is
    nineteen words of recruitment policy. The row's name ended at the dash.
    """
    assert refuses(
        "Office Assistant – Director Intermediate with minimum 2nd class "
        "cum- Storekeeper and 5 years experience in noting and drafting. "
        "Computer knowledge is must. i) By promotion on the basis of "
        "seniority-cum-fitness from amongst Senior clerks working in the "
        "Museum.",
        "Security Supervisor 11 1")


def test_doc_4043_contents_running_one_row_ahead_of_the_body():
    """The doc 4499 offset shape, arriving through a dash-closed name.

    The Apprenticeship Rules' contents promises "Following procedure" for the
    rule the page names "Procedure for the selection of apprentices", and the
    two-word phrase does occur in that rule's body -- inside "Following
    procedure shall be observed by the employers". A span that enacts is not a
    printed name, which is what keeps the coincidence from corroborating it.
    """
    assert refuses(
        "Procedure for the selection of apprentices: – Following "
        "procedure shall be observed by the employers for the selection of "
        "apprentices:–",
        "Following procedure")


# --------------------------------------------------------------------------
# the four things that must NOT change
#
# Each was a measured regression while the rule was being narrowed. A guard
# with a remembered counter-example is a test; one without is a guess.


def test_a_fused_marginal_note_corroborates_the_contents_list():
    """Doc 2384: the note is printed after the operative opener, in the block.

    The source is AGREEING with the contents here, not contradicting it, and
    refusing the heading would lose a correct name.
    """
    assert not refuses(
        "Any person who unlawfully and maliciously – Punishment for "
        "attempt to cause explosion, or for making or keeping explosive with "
        "intent to endanger life or property.",
        "Punishment for attempt to cause explosion, or for making or keeping "
        "explosive with intent to endanger life or property.")


def test_a_note_wedged_into_the_middle_of_a_sentence_still_corroborates():
    """Doc 3708 s.45 sets the note inside the sentence rather than beside it.

    Three consecutive words of the promised name is the floor for reading a run
    inside prose as the name itself; two is the coincidence doc 4043 prints.
    """
    assert not refuses(
        "Entries in a record-of-rights or in a periodical record, variations "
        "of entries in records. except entries made-in periodical records by "
        "Patwaris under clause (a) of section 44 ...",
        "Restriction on variations of entries in records.")


def test_operative_words_are_not_a_name_however_long_the_span():
    """Doc 893: a penalty's opening words carry no word on the narrower list.

    This is why the longer span uses the census's operative vocabulary and not
    this file's.
    """
    assert not refuses(
        "Any owner of a boiler who refuses or without reasonable excuse "
        "neglects ―",
        "Minor Penalties.")


def test_an_amending_opener_is_not_a_name():
    """Every Sindh and Punjab Finance Act prints its sections this way."""
    assert not refuses(
        "In the said Act, in section 13 – Amendment of section 13 of Act "
        "No.XXVII of 1997.",
        "Amendment of section 13 of Act No.XXVII of 1997.")


def test_one_lost_glyph_is_still_one_name():
    """Doc 4458 prints "contrary to law" against a contents "contrary to taw".

    Three letters is below the token comparison's fuzzy floor, so whole-name
    similarity is what catches it.
    """
    assert not refuses(
        "Public servant in judicial proceeding corruptly making report, etc., "
        "contrary to law.– Whoever, being a public servant, corruptly or "
        "maliciously makes or pronounces ...",
        "Public servant in judicial proceeding corruptly making report, etc., "
        "contrary to taw")


def test_editorial_apparatus_never_reads_as_a_name():
    """Doc 2366: the span must keep closing at its first full stop."""
    assert not refuses("Add. by Punjab Act IV of 1944, s. 4.",
                       "Short title and commencement.")
