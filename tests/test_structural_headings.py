"""Structural headings the grammar did not recognise, so numbering collided.

Three shapes, all producing the same defect and all repaired the same way. The
grammar in `RULES` requires the literal word PART, CHAPTER or SECTION for a
division, and it reads a contents list only at the front of a document. Where a
document prints its divisions some other way, the heading becomes no node: it
lands in the TAIL of the preceding provision's text, and the numbering that
restarts under it collides with the numbering above it.

  1. ``I- General`` / ``II. Issue and Cancellation of Membership:`` -- a bare
     Roman numeral set as a display heading. Quaid-e-Azam Library Membership
     Rules 2001, document 3393, nine divisions and fourteen collisions; Part
     VII's whole operative sentence was inside Part VI rule 4 on page 6.
  2. ``THE SCHEDULE`` printed between the last contents entry and the first fall
     back to 1, so the contents region swallowed it and the schedule never
     opened. Sindh Universities and Institutes Laws (Amendment) Act 2025,
     document 4089, fifty collisions and five pages attached to no provision.
  3. ``C O N T E N T`` printed on the LAST page. Sindh Remand Home Rules 2011,
     document 3079, twenty collisions against the twenty rules it summarises.

Each repair is gated on CONSEQUENCE rather than on shape, because every one of
these shapes also occurs innocently: ``I.`` and ``II.`` are ordinary list
markers, a contents list may legitimately name a schedule, and a marker in
mid-document may head a genuine second contents list. So the tests below come in
pairs -- the shape with a collision is repaired, and the same shape without one
is left exactly as it was.

Pure, as the segmenter is: blocks in, a tree out, no database.
"""
from __future__ import annotations

from nizam.corpus.segment import (
    _centred_in_body_column, _contradicts_promise, _display_cased,
    _names_a_printed_entry, _roman_display_heading, _roman_display_part_run,
    _roman_number, segment,
)

# The body column of an ordinary single-column Pakistani gazette page, in points.
LEFT, RIGHT = 72.0, 527.0
CENTRE = (LEFT + RIGHT) / 2


def body(text: str, *, page: int = 1) -> dict:
    """A block set across the body column."""
    return {"text": text, "x0": LEFT, "x1": RIGHT, "page_no": page}


def centred(text: str, *, width: float = 100.0, page: int = 1) -> dict:
    """A short block centred in the body column -- a display heading."""
    return {"text": text, "x0": CENTRE - width / 2, "x1": CENTRE + width / 2,
            "page_no": page}


def indented(text: str, *, page: int = 1) -> dict:
    """A block indented as a sub-item: deeper than the column, not centred."""
    return {"text": text, "x0": 144.1, "x1": 229.5, "page_no": page}


def laid_out(*blocks: dict) -> list[dict]:
    """Give the blocks ids, reading order and a page height, as extraction does."""
    return [dict(block, id=i, y0=100.0 + 20 * i,
                 page_height=792.0) for i, block in enumerate(blocks)]


def labels(seg, kind: str = "section") -> list[str]:
    return [node.label for node in seg.flatten() if node.kind == kind]


# ------------------------------------------------------------ the shape tests
def test_roman_number_reads_only_well_formed_numerals():
    assert _roman_number("IX") == 9
    assert _roman_number("VIII") == 8
    assert _roman_number("IIII") is None      # not a numeral
    assert _roman_number("") is None
    assert _roman_number("Ordinary") is None


def test_display_cased_accepts_capitals_and_title_case():
    assert _display_cased("MEMBERSHIP FEE") == (True, True)
    # Document 3393 prints two of its nine Part headings in title case; the run
    # must survive them, so they read as display headings and are not counted
    # towards the run's upper-case share.
    assert _display_cased("Issue and Cancellation of Membership") == (True, False)
    assert _display_cased("General") == (True, False)
    # A sentence is not a heading.
    assert _display_cased("the Chief Librarian may suspend membership")[0] is False


def test_roman_display_heading_strips_a_printed_sub_letter():
    """Document 3393 page 4 prints ``III.  A.  MEMBERSHIP FEE``."""
    assert _roman_display_heading("III. \n A. \n MEMBERSHIP FEE \n") == (
        "III", "MEMBERSHIP FEE")
    assert _roman_display_heading("I- \n General \n") == ("I", "General")
    assert _roman_display_heading("I think the Librarian may refuse.") is None


def test_centring_separates_a_part_heading_from_a_list_marker():
    """The only thing that tells document 3393's two ``I.`` blocks apart.

    ``I- General`` is centred on the body column; ``I. Ordinary``, an item of
    its own rule 2 four lines above, is indented at x0 144.1 with its centre
    112.7pt to the left of the column's.
    """
    assert _centred_in_body_column(centred("I- General"), LEFT, RIGHT)
    assert not _centred_in_body_column(indented("I. Ordinary"), LEFT, RIGHT)
    # No geometry is not evidence of centring.
    assert not _centred_in_body_column({"text": "I- General"}, LEFT, RIGHT)


def test_a_run_must_start_at_one_and_reach_three():
    general, fees = ("GENERAL", "MEMBERSHIP FEE"), ("ADMISSION", "TIMINGS")
    # A stray "V." cannot open a division: a document with a real Part V prints
    # I to IV first.
    assert _roman_display_part_run(
        [(1, ("V", general[0])), (2, ("VI", general[1]))]) == frozenset()
    # Two is an ordinary two-item list, not a division scheme.
    assert _roman_display_part_run(
        [(1, ("I", general[0])), (2, ("II", general[1]))]) == frozenset()
    assert _roman_display_part_run(
        [(1, ("I", general[0])), (2, ("II", general[1])), (3, ("III", fees[0]))]
    ) == frozenset({1, 2, 3})
    # The run stops where the numerals stop being consecutive, and what is left
    # must still be long enough to be a division scheme.
    assert _roman_display_part_run(
        [(1, ("I", general[0])), (2, ("III", general[1])), (3, ("IV", fees[1]))]
    ) == frozenset()


# ------------------------------------------- 1. bare Roman display headings
ROMAN_DIVISIONS = laid_out(
    body("QUAID-E-AZAM LIBRARY MEMBERSHIP RULES 2001"),
    centred("I- \n General \n"),
    body("1. \n Membership.- Membership of the Library shall be open to the "
         "citizens of Pakistan and foreign nationals in terms of the "
         "conditions laid down below:"),
    body("2. \n Categories of Membership.- Membership will fall under the "
         "following categories and no other category shall be granted."),
    centred("II. \n GENERAL INSTRUCTIONS. \n", width=195.0, page=2),
    body("1. \n Private photography is not allowed inside the library except "
         "with the permission of the Chief Librarian.", page=2),
    body("2. \n A membership card shall be issued to each member in the "
         "prescribed manner. It shall be strictly non-transferable.", page=2),
    centred("III. \n SUGGESTION BOOK \n", width=159.0, page=3),
    body("A suggestion book shall be kept in the Library in which the members "
         "may record their suggestions for improving the general facilities.",
         page=3),
)


def test_bare_roman_display_headings_become_parts():
    """The numbering under each division is local to it, so nothing collides."""
    seg = segment(ROMAN_DIVISIONS)
    assert labels(seg, "part") == ["I", "II", "III"]
    assert seg.repeated_labels_demoted == 0
    assert seg.structural_repair == "roman_display_parts"
    # Every rule is still citable, each under its own division.
    parts = {node.label: [child.label for child in node.children
                          if child.kind == "section"]
             for node in seg.root.children if node.kind == "part"}
    assert parts == {"I": ["1", "2"], "II": ["1", "2"], "III": []}
    # ...and without the promotion the same document collides.
    assert segment(ROMAN_DIVISIONS,
                   structural_overrides={}).repeated_labels_demoted == 2


def test_the_part_heading_stops_burying_the_next_divisions_law():
    """In document 3393 Part VII's whole operative sentence was inside Part VI
    rule 4 on page 6.

    The heading is not a node, so it and everything after it were appended to
    the last provision that happened to be open. What the reader loses is not
    the heading: it is the sentence under it.
    """
    seg = segment(ROMAN_DIVISIONS)
    suggestion = "A suggestion book shall be kept in the Library"
    owner = [node for node in seg.flatten() if suggestion in node.text]
    assert len(owner) == 1, [node.label for node in owner]
    assert owner[0].kind == "part" and owner[0].label == "III"
    # and the rule above it keeps only its own words
    rule = next(node for node in seg.flatten()
                if node.kind == "section" and node.label == "2"
                and "membership card" in f"{node.heading or ''} {node.text}")
    assert suggestion not in rule.text
    # which is exactly what it did not do before the repair
    buried = segment(ROMAN_DIVISIONS, structural_overrides={})
    assert any(suggestion in node.text and node.label == "2"
               for node in buried.flatten())


def test_indented_roman_list_markers_are_not_promoted():
    """``I. Ordinary`` and ``II. Student`` are items of rule 2, not divisions.

    They pass every shape test a bare-Roman pattern can apply -- short, a
    numeral, a run starting at I -- and are refused on geometry alone.
    """
    seg = segment(laid_out(
        body("1. \n Membership.- Membership of the Library shall be open to "
             "the citizens of Pakistan in terms of the conditions below:"),
        body("2. \n Categories of Membership.- Membership will fall under the "
             "following categories:"),
        indented("I. \n Ordinary \n"),
        indented("II. \n Student \n"),
        indented("III. \n Honorary \n"),
        body("3. \n General:- The qualifications prescribed for various types "
             "of membership are mentioned as a yardstick only."),
    ))
    assert labels(seg, "part") == []
    assert seg.structural_repair is None


def test_a_roman_run_that_resolves_no_collision_is_left_alone():
    """Condition (iii). 654 blocks in 105 documents carry this shape; only the
    documents whose numbering actually restarts under it are touched."""
    seg = segment(laid_out(
        centred("I- \n General \n"),
        body("1. \n Short title.- These rules may be called the Example Rules, "
             "2001, and shall come into force at once."),
        centred("II. \n DEFINITIONS \n", width=120.0),
        body("2. \n Definitions.- In these rules, unless the context otherwise "
             "requires, the following expressions have the meanings given."),
        centred("III. \n PROCEDURE \n", width=120.0),
        body("3. \n Procedure.- An application shall be made in writing to the "
             "Secretary of the Board within thirty days."),
    ))
    assert labels(seg, "part") == []
    assert seg.repeated_labels_demoted == 0
    assert seg.structural_repair is None
    assert labels(seg) == ["1", "2", "3"]


# ------------------------------------ 2. the swallowed auxiliary heading
def test_contradicts_promise_is_silent_without_printed_words():
    """Absence of corroboration is not contradiction.

    A body that prints no heading is the ordinary case, and refusing the
    schedule exit there would swallow a whole Act into a false schedule -- the
    failure that exit exists to prevent.
    """
    assert not _contradicts_promise("", None, "Short title")
    assert not _contradicts_promise("Short title and commencement.", None,
                                    "Short title and commencement")
    # An amending instruction names the enactment amended, never its own subject
    assert _contradicts_promise("In section 2 -", None,
                                "Short title and Commencement")
    # ...and a row the contents prints under a DIFFERENT label proves the label
    # coincidence spurious: document 4089's serial 2 is its contents entry 4.
    assert _contradicts_promise(
        "The University of Karachi Act, 1972 (Sindh Act No.XXV of 1972).",
        None, "Amendment of certain laws.",
        {"2": "Amendment of certain laws.",
         "4": "The University of Karachi Act, 1972 (Sindh Act No.XXV of 1972)."},
        "2")


def amended_act(serial: str, name: str, *, page: int) -> list[dict]:
    """One left-column entry and the two right-column items under it.

    Serial 1 carries no number of its own, as document 4089's does not: its
    schedule sets the serial column in its own narrow column and PyMuPDF
    extracts the whole run -- ``1. 2. 3. 1.`` -- as a single block, so the first
    numbered unit after the printed contents is the first AMENDING ITEM. That is
    why `parse_contents` cannot cut before THE SCHEDULE.
    """
    entry = name if serial == "1" else f"{serial}. \n {name}"
    return [
        body(entry, page=page),
        body("1. \n In section 2 - after clause (c), the following new clause "
             "shall be inserted, namely, cadre officer means the officer "
             "belonging to PAS, Ex-PCS, PSS and PMS cadre;", page=page),
        body("2. \n In section 27 - for sub-section (1), the following shall "
             "be substituted, namely, there shall be a Vice Chancellor of the "
             "University appointed by the Chief Minister on the "
             "recommendations of the Search Committee.", page=page),
    ]


AMENDMENT_TABLE = laid_out(
    body("CONTENTS \n Sections \n"),
    body("1. Short title and Commencement \n 2. Amendment of certain laws. \n"
         "3. The University of Sindh Act, 1972 (Sindh Act No.XXIV of 1972). \n"
         "4. The University of Karachi Act, 1972 (Sindh Act No.XXV of 1972). \n"
         "5. The N.E.D. University of Engineering and Technology Act, 1977 "
         "(Sindh Act No.III of 1977). \n"
         "6. The Mehran University of Engineering and Technology Act, 1977 "
         "(Sindh Act No.IV of 1977). \n"),
    body("An ACT to amend certain laws relating to the Public Universities and "
         "Institutes in force in the Province of Sindh.", page=2),
    body("It is hereby enacted as follows:- \n", page=2),
    body("THE SCHEDULE \n", page=2),
    *amended_act("1", "The University of Sindh Act, 1972 (Sindh Act No.XXIV "
                      "of 1972).", page=2),
    *amended_act("2", "The University of Karachi Act, 1972 (Sindh Act No.XXV "
                      "of 1972).", page=3),
    *amended_act("3", "The N.E.D. University of Engineering and Technology "
                      "Act, 1977 (Sindh Act No.III of 1977).", page=4),
    *amended_act("4", "The Mehran University of Engineering and Technology "
                      "Act, 1977 (Sindh Act No.IV of 1977).", page=5),
)


SCHEDULE_BLOCK = next(block["id"] for block in AMENDMENT_TABLE
                      if block["text"].strip() == "THE SCHEDULE")
RESTORED = {"contents_boundary_block": SCHEDULE_BLOCK,
            "corroborate_schedule_exit": True}


def test_the_schedule_exit_is_refused_on_every_row_of_the_table():
    """The decision fix (2) turns on, taken over a whole printed table.

    "A schedule cannot contain a section the Act's own contents promises" is
    sound only where this unit IS that section. Both kinds of row in document
    4089's schedule share a label with a promise and neither is it: the items
    are amending instructions, and the entries reproduce the promise filed two
    places up the list.
    """
    contents = {"1": "Short title and Commencement",
                "2": "Amendment of certain laws.",
                "3": "The University of Sindh Act, 1972 (Sindh Act No.XXIV "
                     "of 1972).",
                "4": "The University of Karachi Act, 1972 (Sindh Act No.XXV "
                     "of 1972)."}
    rows = [("1", "In section 2 - after clause (c), a new clause is inserted"),
            ("2", "In section 27 - for sub-section (1), the following shall "
                  "be substituted"),
            ("2", "The University of Karachi Act, 1972 (Sindh Act No.XXV of "
                  "1972).")]
    for label, text in rows:
        assert _contradicts_promise(text, None, contents[label],
                                    contents, label), (label, text)
    # ...and the Act's own section 1, printed where the contents says it is,
    # still ends the schedule it follows.
    assert not _contradicts_promise(
        "Short title and Commencement.- This Act may be called the Sindh "
        "Universities and Institutes Laws (Amendment) Act, 2025.",
        None, contents["1"], contents, "1")


def test_a_schedule_row_the_contents_names_is_the_schedules_entry():
    """Filing every row as schedule content is correct and not sufficient: on
    its own it leaves document 4089 with no citable provision at all, the
    thirty Acts its own contents list promises included. The left column
    reproduces those promises verbatim and the right column never does, so the
    printed list is what separates the schedule's entries from its items.
    """
    contents = {"4": "The University of Karachi Act, 1972 (Sindh Act No.XXV "
                     "of 1972)."}
    assert _names_a_printed_entry(
        "The University of Karachi Act, 1972 (Sindh Act No.XXV of 1972).",
        contents)
    assert not _names_a_printed_entry("In section 27 -", contents)
    assert not _names_a_printed_entry("The University of Karachi Act", None)


def test_the_swallowed_heading_hands_its_pages_back_to_the_body():
    """Nothing printed may leave the database: pages 3 to 5 of document 4089
    carried role='contents' and were attached to no provision at all."""
    def contents_chars(seg):
        return sum(len(block["text"]) for block in AMENDMENT_TABLE
                   if seg.block_roles.get(block["id"], ("", None))[0]
                   == "contents")
    restored = segment(AMENDMENT_TABLE, structural_overrides=RESTORED)
    swallowed = segment(AMENDMENT_TABLE, structural_overrides={})
    assert contents_chars(restored) < contents_chars(swallowed)
    # and no block falls out of the ledger either way
    assert all(role != "unassigned" for role, _ in restored.block_roles.values())
    assert len(restored.block_roles) == len(AMENDMENT_TABLE)


# ---------------------------------------- 3. a contents list after the body
TRAILING_CONTENTS = laid_out(
    body("1. Short title and commencement,- These rules may be called the "
         "Sindh Remand Home Rules, 2011 and shall come into force at once."),
    body("2. Definitions.- In these rules, unless there is anything repugnant "
         "in the subject or context, Act means the Sind Children Act, 1955."),
    body("3. Government to declare a Remand Home.- Government may, by "
         "notification in the official Gazette, declare any particular place "
         "to be a Remand Home for the purposes of the Act.", page=2),
    body("4. Section of a Remand Home.- There shall be two sections of a "
         "Remand Home, one for the detention of children involved in the "
         "commission of an offence.", page=2),
    body("5. Superintendent of Remand Home.- The Superintendent shall be "
         "appointed by Government and shall not be below the rank of BS-17.",
         page=3),
    centred("C O N T E N T \n", width=306.0, page=4),
    body("1. \n Short title and commencement. \n 2. \n Definitions. \n"
         "3. \n Government to declare a Remand Home. \n"
         "4. \n Section of a Remand Home. \n"
         "5. \n Superintendent of Remand Home. \n", page=4),
)


def test_a_contents_list_printed_after_the_body_is_not_a_second_body():
    seg = segment(TRAILING_CONTENTS)
    assert seg.structural_repair == "trailing_contents_block"
    assert seg.repeated_labels_demoted == 0
    assert labels(seg) == ["1", "2", "3", "4", "5"]
    # The list is apparatus, and it is used as apparatus: it becomes the
    # document's contents, so the headings are known rather than inferred and
    # the acceptance test can run (doc 02 section 5).
    assert seg.toc_found and seg.agreement == 1.0
    assert seg.toc["3"] == "Government to declare a Remand Home."
    # Both of its blocks keep a role, and neither owns a provision.
    trailing = [TRAILING_CONTENTS[-1]["id"], TRAILING_CONTENTS[-2]["id"]]
    for block_id in trailing:
        role, node = seg.block_roles[block_id]
        assert role == "contents" and node is None


def test_every_rule_keeps_its_own_text_when_the_trailing_list_is_withdrawn():
    """The twenty phantoms carried no law -- their text IS the heading -- so
    removing them must not remove a character of the rules they summarise."""
    seg = segment(TRAILING_CONTENTS)
    rule = next(node for node in seg.flatten()
                if node.kind == "section" and node.label == "4")
    assert "two sections of a Remand Home" in rule.text


def test_a_document_with_no_collision_is_never_re_parsed():
    """The repair cannot run at all without a collision to resolve, so a
    document that has none is byte-identical before and after."""
    seg = segment(laid_out(
        body("1. Short title.- These rules may be called the Example Rules."),
        body("2. Definitions.- In these rules, Board means the Board of "
             "Governors constituted under section 3."),
        body("3. Powers of the Board.- The Board may, by order in writing, "
             "delegate any of its powers to the Secretary."),
    ))
    assert seg.structural_repair is None
    assert seg.repeated_labels_demoted == 0
    assert labels(seg) == ["1", "2", "3"]
