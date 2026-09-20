"""The truncation detector's pure functions, on the pages that broke it.

Every case here is a real block from the corpus, quoted as the extractor stored
it. Three of them are the documents that proved the first version wrong in both
directions: 127 and 2205 were truncated and not reported, 3291 was complete and
was.
"""
from tools.find_truncated_acquisitions import (
    body_ceiling,
    ends_a_sentence,
    is_footnote,
    is_prose,
    last_prose_block,
    opener_label,
)

# Document 2205, page 8: the page's editorial apparatus, which the first
# version read as the end of the law. It ends in a clean full stop under a
# section that breaks off mid-clause.
CONVEYANCES_FOOTNOTES = (
    "1. Ins. by Sind 7 of 1928, s. 6.  \n"
    "2. Subs.  by the Sind Laws (Adaptation, Revision, Repeal and "
    "Declaration) Ordinance, 1955 (Sind \n5 of 1955), s. 7, Sch. III, for "
    "“City of Bombay”. \n"
    "3. Subs. ibid., s. 7, Sch. III, for “Commissioner of Police.” \n"
    "4. Subs. by the A.O., 1937, “G, in C.”. \n"
    "5. Added by the Sind 7 of 1928, s. 7. \n"
)

# Document 2205, page 8: where the law actually stops.
CONVEYANCES_TAIL = (
    "(3) \nEvery such driver shall on demand produce such list for the \n"
    "information of any hirer of, or passenger travelling in, the conveyance  \n \n"
)

# Document 3291, page 20: the last prose of a COMPLETE statutory instrument.
TARIFF_TAIL = (
    "(2) In imposing any 25fine under these rules, the Authority shall keep "
    "in view the principle of proportionality of the fine to the gravity of "
    "the contravention and shall allow the person liable to be penalized to "
    "show cause, orally or in writing and in the manner deemed fit by the "
    "Authority, as to why the fine may not be imposed."
)

# Document 3291, page 20: what follows it.
TARIFF_SIGNATURE = "Secretary"
TARIFF_AUTHORITY = "National Electric Power Regulatory Authority"
TARIFF_FOOTNOTES = (
    "22 Substituted vide Notification No. S.R.O 732(i)2014, dated Islamabad, "
    "the 12th August, 2014. 23 ibid 24 Printed in the Notification as "
    "“contuse” 25 Printed in the Notification as “find”"
)


def test_editorial_footnotes_are_not_the_law():
    # Each numbered note in document 2205's apparatus, as it opens. A note's
    # continuation lines are not tested: the classifier reads blocks, and a
    # block is recognised from where it starts.
    for note in ("1. Ins. by Sind 7 of 1928, s. 6.",
                 "2. Subs.  by the Sind Laws (Adaptation, Revision, Repeal "
                 "and Declaration) Ordinance, 1955",
                 "3. Subs. ibid., s. 7, Sch. III, for “Commissioner of "
                 "Police.”",
                 "4. Subs. by the A.O., 1937, “G, in C.”.",
                 "5. Added by the Sind 7 of 1928, s. 7."):
        assert is_footnote(note), note
    assert is_footnote(CONVEYANCES_FOOTNOTES)


def test_amendment_footnote_without_a_stop_after_the_number():
    assert is_footnote("22 Substituted vide Notification No. S.R.O 732(i)2014")
    assert is_footnote("23 ibid")
    assert is_footnote("1 Subs vide the Khyber Pakhtunkhwa Act No. V of 2011")
    assert is_footnote("2 Sub. Ibid, for “Gazette of India”")


def test_the_gazette_provenance_note_is_a_footnote():
    assert is_footnote(
        "1 This Act was passed by the Provincial Assembly of Balochistan on "
        "26th March, 2016, assented to by the Governor of Balochistan on "
        "29th March, 2016; and published in the Balochistan Gazette.")


def test_a_real_section_one_is_never_a_footnote():
    # The trap that took "for", "see" and "this Act" out of the verb list.
    assert not is_footnote(
        "1. This Act may be called the Agricultural Produce Cess Act, 1940.")
    assert not is_footnote(
        "1. For the purposes of this Act, a person shall be deemed to be a "
        "resident of Pakistan.")
    assert not is_footnote(
        "3. Imposition of lac cess. There shall be levied and collected on "
        "all lac and refuse lac exported from Pakistan a cess.")


def test_a_curly_quote_closes_a_sentence():
    # Document 3291 was reported as truncated because this did not.
    assert ends_a_sentence(TARIFF_FOOTNOTES)
    assert ends_a_sentence("Printed in the Notification as “find”")


def test_an_unfinished_clause_does_not_close_a_sentence():
    assert not ends_a_sentence(CONVEYANCES_TAIL)
    assert not ends_a_sentence(
        "5.\nThe administration and management of the affairs of the \n")


def test_the_tail_test_walks_past_the_apparatus_to_the_law():
    # Document 2205: the law stops mid-clause under a footnote that does not.
    found = last_prose_block([TARIFF_TAIL, CONVEYANCES_TAIL,
                              CONVEYANCES_FOOTNOTES])
    assert found == CONVEYANCES_TAIL
    assert not ends_a_sentence(found)


def test_the_tail_test_walks_past_a_signature_block():
    # Document 3291: complete, and must not be reported.
    found = last_prose_block([TARIFF_TAIL, TARIFF_SIGNATURE, TARIFF_AUTHORITY,
                              TARIFF_FOOTNOTES])
    assert found == TARIFF_TAIL
    assert ends_a_sentence(found)


def test_a_schedule_table_row_is_not_continuing_prose():
    # Document 3387's last line: a commodity table, not an unfinished sentence.
    assert not is_prose(
        "8 Salt 24 Poultry food 9 Potatoes 25 Surgical gloves 10 Onion "
        "26 Masks 11 Tomato 27 Sanitizers")
    # Document 4522's last line: a printer's imprint.
    assert not is_prose("Rarase Printed at the Sindh Gorerament nt Press "
                        "7-05-2021 and Published by")


def test_a_marginal_heading_above_the_label_still_opens_a_section():
    # Document 33, the last block it holds.
    assert opener_label(
        "Administration of \n5.\nThe administration and management of the "
        "affairs of the \n") == 5
    assert opener_label(
        "Definitions.\n2.\nIn this Act, unless there is anything repugnant "
        "in the subject or context–") == 2


def test_a_footnote_split_across_lines_is_not_an_opener():
    # This is what collapsed the body ceiling corpus-wide: the first line is
    # "1." and reads as section 1 until the newline is closed up.
    assert opener_label(
        "1. \nFor statement of Objects and Reasons, see B.G.G., 1919, "
        "Pt. V, p.945; for the Report \n") is None
    assert opener_label(
        "1. \nSubs. by the Sind Laws (Adaptation, Revision, Repeal and "
        "Declaration) Ordinance, \n1955") is None


def test_an_ordinary_opener_is_read():
    assert opener_label("27. Penalty.— (1) Subject to sub-rule (2), any "
                        "person who contravenes") == 27
    assert opener_label("1. \n(1) \nThis \nAct \nmay \nbe \ncalled the "
                        "2[Sind] \nPublic Conveyances Act, 1920.") == 1


def test_the_schedule_restarts_the_numbering_and_ends_the_body():
    # Document 127: sections 1 and 2, then a Schedule numbered 1 to 15. The
    # tree read the ceiling as 15 and hid the truncation.
    labels = [1, 2] + list(range(1, 16))
    assert body_ceiling(labels) == 2


def test_an_isolated_low_label_is_noise_not_a_restart():
    # Document 2205: an unrecognised footnote drops a 1 into the run, and the
    # labels after it rejoin the body's own ascent.
    assert body_ceiling([1, 2, 3, 4, 5, 6, 7, 8, 1, 9, 10, 11, 12]) == 12


def test_a_clean_body_reaches_its_own_top():
    assert body_ceiling(list(range(1, 28))) == 27


def test_no_openers_means_no_ceiling():
    assert body_ceiling([]) == 0
