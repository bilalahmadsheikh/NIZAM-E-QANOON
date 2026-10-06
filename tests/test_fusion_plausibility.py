"""When absence from the contents is evidence of superscript fusion, and when it is not.

``_repair_label`` undoes the fusion PyMuPDF produces when a superscript footnote
marker is glued to the number that follows it -- section 366 carrying footnote 1
arrives as "1366".  Its arbiter is the printed contents list: if the label as
read is absent from the contents and the label minus its leading digit(s) is
present, the leading digits were a marker.

An incomplete contents defeats that.  Six cases from a 200-page rendered-source
audit are pinned below, each a printed label stored as its trailing digit and
made to collide with the document's real short-numbered provision.  The body
already held the evidence that settles every one of them:

* COLLISION -- the stripped label had already been read.  Stripping does not
  recover a section; it manufactures a duplicate and demotes one of the two.
* SEQUENCE -- the reading sits one to nine past the highest number the body has
  read.  A marker m glued in front of the next section's number n reads as
  m * 10**len(n) + n, at least ten past, so no fusion can land there.

Both need the body's ``seen`` set, so neither touches the contents-boundary
scorers, which call ``_repair_label`` without one.  That is deliberate: a guard
on the contents' reach (the "magnitude" rule, .patch_fusion.py edit A) was
measured corpus-wide and moved contents boundaries in doc 1910 and doc 2674,
and it kept a genuine fusion -- doc 2674's "46" -- that is pinned below.

This file is the regression set for ``.patch_fusion.py``; the narrower cases
that never leave the contents-corroborated branch stay in tests/test_segment.py.
"""
from __future__ import annotations

from nizam.corpus.segment import _repair_label

# ------------------------------------------------------------ doc 3868
# Sindh Mining Concession Rules 2002.  The accepted contents list prints
# 1, 2, 4-7 and 44-72 -- it stops at 72 and omits 51 -- while the body runs
# past rule 117.  Headings are the source's own, misprints included.
MINING = {
    "1": "Short title, commencement and extent",
    "2": "Definitions",
    "4": "Mines Committee",
    "5": "Power of Delegation",
    "6": "confidentiality",
    "7": "Immunity of officers, etc.",
    **{str(n): f"rule {n}" for n in range(44, 51)},
    **{str(n): f"rule {n}" for n in range(52, 73)},
}

# ------------------------------------------------------------ doc 4594
# Sindh Prisons and Corrections Services Rules 2019, a degraded gazette scan.
# Its accepted contents list is THREE rows while the body runs past rule 600.
PRISONS = {
    "3": "Construction and administration of High Security Prison.",
    "10": "Prisoner to be kept in 8 separate cell on evellable capacity of Cell.",
    "12": "Security and Order of the Prisan, The Officer In-Charge shail",
}

# ------------------------------------------------------------ doc 2674
# The Elephants' Preservation Act 1879: ten sections, a complete contents.
ELEPHANTS = {
    "1": "Short title Local extent Commencement",
    "2": "[Repeal]",
    "3": "Killing and capture of wild elephants prohibited",
    "4": "Rights of Government with respect to certain elephants and tusks.",
    "5": "License to kill and capture wild elephants",
    "6": "Power of Provincial Government to declare what are main roads and "
         "canals, and to make rules as to licenses",
    "7": "Penalty for contravening section 3",
    "8": "License to be produced and shown on requisition of certain officers",
    "9": "Limitation of prosecution",
    "10": "Recovery of fees",
}


def test_rule_92_is_not_peeled_onto_rule_2_which_has_already_been_read():
    """doc 3868 p4: "92. Approval of transfer of mining permit" was stored as '2'.

    Page 4 continues the printed contents, which the parser reads as body
    because the accepted contents stops at 72.  By the time "92." is built as a
    unit, rule 2 has been read and so have 83-87 and 90: the strip is a
    collision, and 92 is two past the high-water mark.  The ``seen`` set is the
    one the tree builder actually passes at that point.
    """
    seen = {"1", "2", "4", "5", "59", "6", "7", "73", "78", "79", "80",
            "83", "84", "85", "86", "87", "90"}
    assert _repair_label("92", MINING, seen,
                         "Approval of transfer of mining permit \n") == "92"


def test_a_label_the_contents_omits_is_not_peeled_onto_a_rule_already_read():
    """doc 3868 p44: "51. Issue of Mining Lease" was stored as '1'.

    The contents prints 50 and 52 but not 51, so the hole around it is one
    wide and the "deliberate omission" reading applies.  The body settles it
    instead: rule 1 has already been read.
    """
    seen = {"1", "4", "5", "6", "7", "73", "78", "79", "80"}
    assert _repair_label("51", MINING, seen) == "51"


def test_three_row_contents_cannot_demote_four_rules_of_a_600_rule_document():
    """doc 4594 pp13, 16, 27, 28 -- all four stored as rule '3'.

    "43. Provision of funds", "63. Duty hours of Officer in charge",
    "143. Children born in prison" and "153. Examination of prisoners on
    admission" each peeled to 3, the one short number the three-row contents
    happens to print.  Rule 3 had been read on page 2 in every case.

    Page 13 carries a SECOND defect under this one: the page prints "39.
    Provision of funds", and the "43" is the scan's misreading of it
    (tools/evidence/recover-doc4594-ocr-rule-numbers.sql, source-verified).
    This test asserts only what ``_repair_label`` owes the label it is handed
    -- not to peel "43" to "3" -- and says nothing about 43 being right.  The
    number itself is a source correction, not a parser rule.
    """
    early = {"3", "4", "2", "16", "27", "31", "32", "38", "78"}
    assert _repair_label("43", PRISONS, early,
                         "Provision of funds, expenditure and accounts. ") == "43"
    mid = early | {"41", "42", "44", "47", "48", "56", "61", "62"}
    assert _repair_label("63", PRISONS, mid,
                         "Duty hours of Officer in charge.") == "63"
    late = mid | {"10", "102", "106", "111", "114", "115", "119", "124",
                  "126", "128", "134", "140", "142"}
    assert _repair_label("143", PRISONS, late,
                         "Children born in prisen, In the "
                         "¢vent-of @ child being born ina prison,") == "143"
    later = late | {"145", "146", "150"}
    assert _repair_label("153", PRISONS, later,
                         "Examination @f prisoners on admission and "
                         "release. ") == "153"


def test_a_collision_stops_the_strip_outright_not_one_digit_deeper():
    """A collision proves the leading digit belongs to the number.

    Measured with the loop merely skipping to the next strip length, "111"
    went on past a colliding "11" to "1" (doc 4388 p59) and "2015" past a
    colliding "15" to "5" (doc 2491 p5) -- a third value that neither the
    source nor the old repair ever produced.
    """
    toc = {"1": "a", "11": "b", "110": "c", "112": "d"}
    assert _repair_label("111", toc, {"11"}) == "111"


def test_a_reading_beyond_everything_the_document_evidences_is_left_alone():
    """Collision is decisive only inside the range the document has shown.

    doc 1910's Fourth Schedule prints "8. rule 38. Fee for duplicate
    certificate" and the parser carves "rule 38." out as a unit.  In a
    ten-section Act a 38 is not a provision number either way; keeping it
    citable tipped the contents-refutation count and filed the whole Act as
    contents.  So beyond both the contents' reach and the body's high-water
    mark (plus the one-to-nine sequence band) the old repair is untouched --
    and "2015", a footnote year, keeps the "15" it always got rather than the
    "5" an unbounded rule produced.
    """
    act = {str(n): f"section {n}" for n in range(1, 11)}
    assert _repair_label("38", act, {str(n) for n in range(1, 9)}) == "8"
    toc = {str(n): f"heading {n}" for n in range(1, 51)}
    assert _repair_label("2015", toc, {"3", "14", "15"}) == "15"


def test_a_reading_just_past_the_high_water_mark_is_the_next_section():
    """doc 3868 p5: "102. Rental and Renewal Fee" arrives straight after 101.

    Once rules 82 and 92 keep their numbers, rule 2 may not have been read
    when 102 arrives, so collision alone would let a contents reaching 72 peel
    it to 2.  102 is one past 101, and no footnote marker can put a fused
    reading there.
    """
    seen = {"1", "4", "5", "6", "7"} | {str(n) for n in range(73, 102)}
    assert _repair_label("102", MINING, seen, "Rental and Renewal Fee") == "102"


def test_genuine_fusion_in_a_ten_section_act_is_still_repaired():
    """doc 2674 p2 prints section 6 with footnote 4 glued on: "46.".

    Footnote 4 is "For rules under this section".  Sections 2-5 have been read
    and 6 has not, so there is no collision, and 46 is 41 past the high-water
    mark -- exactly the jump a marker produces.  This is the repair a guard on
    the contents' digit width broke: two digits against a contents reaching
    10 looked plausible.
    """
    heading = ("Power of Provincial Government to declare what are main "
               "roads and canals")
    assert _repair_label("46", ELEPHANTS, {"2", "3", "4", "5"}, heading) == "6"
    # The contents-boundary scorers call without a seen set; they must still
    # see it as section 6 or the boundary moves.
    assert _repair_label("46", ELEPHANTS) == "6"


def test_superscript_fusion_is_still_undone_when_the_reading_overflows():
    """Section 366 carrying footnote 1 arrives as "1366"."""
    dense = {str(n): f"heading {n}" for n in range(1, 501)}
    assert _repair_label("1366", dense) == "366"
    assert _repair_label("1500", dense) == "500"
    assert _repair_label("366", dense) == "366"
    # With the body at section 365: 1366 is 1001 past it, far outside the
    # one-to-nine window, and 366 has not been read, so neither guard fires.
    seen = {str(n) for n in range(1, 366)}
    assert _repair_label("1366", dense, seen) == "366"


def test_cpc_footnote_one_plus_section_25_still_resolves_to_25():
    """CPC page 20 emits footnote 1 + section 25 as "125.".

    The Code also has a genuine section 125, so the contents alone cannot
    settle it and printed order does.  With section 24A just read, 125 is not
    a numeric continuation (24A is not a number) and 25 is unseen.
    """
    toc = {"24A": "Appearance", "25": "Omitted", "125": "Omitted"}
    assert _repair_label("125", toc, {"24A"}) == "25"
    # ... and once section 25 has actually been read, "125." is section 125.
    assert _repair_label("125", toc, {"24A", "25"}) == "125"


def test_heading_evidence_still_outranks_printed_order():
    """A genuine three-digit section keeps its leading digit on heading proof."""
    railways = {"15": "Omitted", "16": "Omitted", "115": "Disposal of fines",
                "116": "Altering or defacing pass or ticket"}
    assert _repair_label(
        "116", railways, {"15", "115"},
        "Altering or defacing pass or ticket. If a passenger...") == "116"
    assert _repair_label(
        "79", {"8": "Alteration of pipes", "9": "Temporary entry",
               "78": "Omitted", "79": "Settlement of compensation"},
        {"8"}, "Temporary entry upon land for repairing an accident.") == "9"


def test_an_incomplete_contents_still_does_not_strip_an_in_range_rule():
    """The Sindh mining rules' hole between 7 and 44 is 14 wide."""
    assert _repair_label("21", MINING) == "21"
    assert _repair_label("22", MINING) == "22"
    assert _repair_label("44", MINING) == "44"


def test_no_contents_list_changes_nothing():
    assert _repair_label("21", {}) == "21"
    assert _repair_label("1366", {}) == "1366"
    assert _repair_label("143", {}) == "143"


def test_a_repair_never_lands_on_or_passes_through_a_label_already_read():
    """The rule both guards enforce, swept over three real contents lists.

    Whatever the repair returns is the label as read or a suffix of it.  For a
    reading the guards speak for -- up to the larger of the contents' reach and
    the body's high-water mark (collision), or one to nine past the body's
    high-water mark (sequence) -- that suffix has not been read, and no longer
    suffix on the way to it had been read either, which is what a deeper strip
    past a collision would violate.  Outside those the old repair stands.
    """
    for toc in (MINING, PRISONS, ELEPHANTS):
        printed = max(int(k) for k in toc if k.isdigit())
        for top in (5, 12, 60, 95, 150):
            seen = {str(n) for n in range(1, top + 1) if n % 7}
            high = max(int(v) for v in seen)
            for number in range(1, 700):
                label = str(number)
                result = _repair_label(label, toc, seen)
                if result == label:
                    continue
                assert label.endswith(result), (label, result)
                if not (number <= max(printed, high) or 0 < number - high < 10):
                    continue
                assert result not in seen, (label, result, top)
                for cut in range(1, len(label) - len(result)):
                    assert label[cut:] not in seen or label[cut:] not in toc, (
                        label, result, top)
