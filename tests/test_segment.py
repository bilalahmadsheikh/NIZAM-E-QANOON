"""Segmentation is pure -- blocks in, a tree out -- so it is tested without a database.

Two of these tests are regressions for bugs that cost real statutes. Both came
from the same misreading: that a block boundary drawn by a PDF layout engine is
also a legal boundary. Doc 02 §5.1 says the opposite in as many words --
"indentation and coordinates are evidence, not truth".
"""
from __future__ import annotations

from nizam.corpus.segment import (
    _classify_body, _reconcile_label_sets, _repair_label, classify, segment,
    subdivide,
)


def blocks(*texts: str, page: int = 1) -> list[dict]:
    """Blocks as the extractor hands them over: id, text, page, geometry."""
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0}
            for i, t in enumerate(texts)]


# --------------------------------------------------------------- granularity
def test_one_block_holding_several_sections_is_subdivided():
    """The Punjab Dourine Rules 1952 arrive as two typographic blocks holding
    seven sections. A grammar that only matches at a block start finds one.
    """
    seg = segment(blocks(
        "PUNJAB DOURINE RULES, 1952\n(Framed under section 14 of the Dourine Act, 1910)",
        "1. Short title.\n2. Definitions.\n3. Notice of disease.\n"
        "4. Isolation.\n5. Destruction.\n6. Compensation.\n7. Penalty.",
    ))
    labels = [n.label for n in seg.root.children if n.kind == "section"]
    assert labels == ["1", "2", "3", "4", "5", "6", "7"], labels


def test_section_after_bare_newline_is_subdivided_even_without_indent():
    """OCR can fuse a page-year line directly to the next section label."""
    seg = segment(blocks(
        "1. Short title. This Act may be called the Example Act,\n"
        "2025\n2. Commencement. This Act comes into force at once."
    ))
    assert [n.label for n in seg.root.children if n.kind == "section"] == ["1", "2"]


def test_bracketed_repeal_fused_to_preceding_section_is_subdivided():
    """A bracketed disposition remains a directly citable provision.

    Observation 502 page 2 prints section 3 as ``3. [Repeal.]`` inside the
    same extracted block as section 2. The bracket must not hide its boundary.
    """
    seg = segment(blocks(
        "1. Short title and commencement. This Act comes into force at once.\n"
        "2. Adviser not to be disqualified. The exemption applies;\n"
        "3. [Repeal.] Omitted by the Federal Laws Ordinance, 1981."
    ))
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        "1", "2", "3",
    ]


def test_roman_section_division_contains_its_restarted_numbering():
    """Financial regulations use SECTION-IV as a structural division."""
    seg = segment(blocks(
        "9. Income Tax deduction. Tax shall be deducted.",
        "SECTION – IV\nACCOUNTING POLICY",
        "1. Accounting Convention. Accounts use historical cost.",
        "2. Double Entry Accounting System. Transactions use double entry.",
        "SECTION – V\nPOWERS FOR RE-APPROPRIATION",
        "1. Re-appropriation. The Board has full powers.",
    ))
    assert [(n.kind, n.label) for n in seg.root.children] == [
        ("section", "9"), ("part", "IV"), ("part", "V"),
    ]
    assert [(n.kind, n.label) for n in seg.root.children[1].children] == [
        ("section", "1"), ("section", "2"),
    ]
    assert [(n.kind, n.label) for n in seg.root.children[2].children] == [
        ("section", "1"),
    ]


def test_decimal_label_does_not_consume_first_word_of_body():
    assert classify("5.3 A full year's depreciation will be charged.") == (
        "section", "5.3", "A full year's depreciation will be charged.",
    )
    assert classify("2.1 THE authority shall decide the matter.") == (
        "section", "2.1", "THE authority shall decide the matter.",
    )
    assert classify("5.3A. Inserted provision text.") == (
        "section", "5.3A", "Inserted provision text.",
    )
    assert classify("5.3 - A. Hyphenated inserted provision.") == (
        "section", "5.3 - A", "Hyphenated inserted provision.",
    )


def test_roman_section_division_rejects_wrong_global_toc_label_match():
    source = blocks(
        "CONTENTS",
        "1. Intro.\n2. Scope.\n3. Administration.\n"
        "4. Topic A.\n5. Topic E.",
        page=1,
    ) + blocks(
        "WHEREAS it is expedient to regulate the subject;",
        "1. Intro. Opening text.",
        "2. Scope. Application text.",
        "3. Administration. Administrative text.",
        "5. Topic F. Incidental same-numbered text.",
        "SECTION - II\nTOPIC A",
        "1. Topic A. Body text.\n2. Topic B. Body text.\n"
        "3. Topic C. Body text.\n4. Topic D. Body text.",
        page=2,
    )
    for block_id, block in enumerate(source):
        block["id"] = block_id
    seg = segment(source)
    entries = {entry["label"]: entry for entry in seg.toc_entries}
    # The only body label 5 says Topic F and precedes the Roman container, but
    # the document's TOC has already switched to its global display index at
    # entry 4. It still must not satisfy TOC 5 Topic E.
    assert entries["5"]["node"] is None


def test_restarted_number_after_decimal_child_stays_under_roman_division():
    source = blocks(
        "CONTENTS",
        "1. Intro.\n2. Scope.\n3. Administration.\n"
        "4. Authority.\n5. Funds.\n6. Banks.",
        page=1,
    ) + blocks(
        "WHEREAS it is expedient to regulate the subject;",
        "1. Intro. Opening text.\n2. Scope. Application text.\n"
        "3. Administration. Administrative text.\n"
        "4. Authority. Authority text.",
        "SECTION - III\nFUNDS",
        "3. Banks.\n3.1 Account opening. Body text.\n"
        "4. Budget. Body text.",
        page=2,
    )
    for block_id, block in enumerate(source):
        block["id"] = block_id
    seg = segment(source)
    division = next(node for node in seg.root.children
                    if node.kind == "part" and node.label == "III")
    local_four = next(node for node in division.children if node.label == "4")
    assert local_four.parent is division


def test_three_digit_amendment_markers_do_not_hide_inserted_sections():
    """Sales Tax Act 1990 page 30 prints superscript notes 189--192 directly
    before sections 3A--3B.  They are source apparatus, not label digits.
    """
    seg = segment(blocks(
        "189[3A. ***]\n190[3AA. ***]\n191[3AAA. ***]\n"
        "192[3B. Collection of excess sales tax etc. Enacted text."
    ))
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        "3A", "3AA", "3AAA", "3B",
    ]


def test_fused_source_history_note_is_not_section_one():
    bs = blocks(
        "1. Short title. This Act may be called the Example Act.",
        "2. Definitions. In this Act, prescribed means prescribed by rules.",
        "3. Duty. A duty shall be imposed.",
        "1This Act was assented to by the President on 10 June 1967; and was "
        "published in the Gazette of Pakistan.",
    )
    bs[-1]["y0"] = 700.0
    seg = segment(bs)
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["1", "2", "3"]
    assert seg.block_roles[bs[-1]["id"]][0] == "footnote"


def test_punctuated_amendment_footnote_is_not_section_one():
    bs = blocks(
        "1. Short title. This Act may be called the Example Act.",
        "2. Definitions. In this Act, prescribed means prescribed by rules.",
        "1 .\nIn Section 7, sub-section (1), for clause (vi) substituted "
        "vide Act No. XXXII of 1994.",
    )
    bs[-1]["y0"] = 700.0
    seg = segment(bs)
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["1", "2"]
    assert seg.block_roles[bs[-1]["id"]][0] == "footnote"


def test_punctuated_subs_vide_note_is_not_a_section():
    bs = blocks(
        "1. Short title. This Act may be called the Example Act.",
        "2. Definitions. In this Act, prescribed means prescribed by rules.",
        "3. Duty. The Board shall perform its duty.",
        "1. Subs Vide the Khyber Pakhtunkhwa Act IV of 2011.",
    )
    seg = segment(bs)
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["1", "2", "3"]
    assert seg.block_roles[bs[-1]["id"]][0] == "footnote"


def test_multi_note_gazette_footer_is_not_subdivided_into_sections():
    bs = blocks(
        "1. Short title. This Act may be called the Example Act.",
        "2. Definitions. In this Act, prescribed means prescribed by rules.",
        "1. For the applicable Rules, see the Balochistan Gazette No. 16.\n"
        "2 Section 6-A inserted by Ordinance XII of 1980.\n"
        "3 A new section 6-B inserted by Act IV of 2026.\n"
        "4 Numbered as sub section (1) by Act IV of 2026.",
        "1 New section 5-A inserted by Act II of 2013.\n"
        "2 S. No. ‘5-A’, substituted by Act VI of 2021.",
    )
    seg = segment(bs)
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["1", "2"]
    assert all(seg.block_roles[block["id"]][0] == "footnote"
               for block in bs[-2:])


def test_wrapped_rupee_amount_is_not_subdivided_into_a_section():
    from nizam.corpus.segment import subdivide

    text = (
        "and for every Rs. 500 or part thereof in excess of Rs.\n"
        "1000.\nTen rupees."
    )
    assert subdivide(text) == [text]


def test_fused_source_history_and_its_page_continuation_are_apparatus():
    bs = blocks(
        "3. Interpretation. Operative text.\n"
        "1For Statement of Objects and Reasons, see Gazette of India, 1876.",
        "This Act has been extended to the administered areas.\n"
        "2Subs. by the amending Act, s. 2.",
        "4. Next duty. Operative text.",
    )
    bs[2]["page_no"] = 2
    seg = segment(bs)
    sections = [node for node in seg.root.children if node.kind == "section"]
    assert [node.label for node in sections] == ["3", "4"]
    assert "Statement of Objects" not in sections[0].text
    assert seg.block_roles[bs[1]["id"]][0] == "footnote"


def test_section_citation_insertion_note_is_not_label_one_s():
    bs = blocks(
        "45. Delivery. The holder may deliver the instrument.",
        "1S. 45A ins. by the Negotiable Instruments Act, 1885, s. 3.",
    )
    seg = segment(bs)
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["45"]
    assert seg.block_roles[bs[1]["id"]][0] == "footnote"


def test_indented_dotted_subparts_follow_inline_parenthesized_one():
    bs = blocks(
        "CONTENTS", "1. Short title.", "2. Definitions.", "3. Duty.",
        "It is hereby enacted as follows:",
        "1. Short title.—(1) This Act may be called the Example Act.",
        "2. It extends to the whole of Pakistan.",
        "3. It shall come into force at once.",
        "2. Definitions. In this Act, prescribed means prescribed by rules.",
        "3. Duty. The Authority shall act.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 3 else 2
        block["x0"] = 162.0 if index in {6, 7} else 126.0
    seg = segment(bs)
    sections = [node for node in seg.root.children if node.kind == "section"]
    assert [node.label for node in sections] == ["1", "2", "3"]
    assert [node.label for node in sections[0].children] == ["2", "3"]
    assert all(node.kind == "subsection" for node in sections[0].children)
    assert seg.repeated_labels_demoted == 0


def test_dotted_resident_definition_items_are_not_sections():
    """Source-proved numbered lists remain under the definition they qualify.

    The Sindh Sales Tax on Services Act prints list items 1--3 with dots inside
    subsection (33), and item 3 continues after a page break.  They must not
    collide with the Act's citable sections 1 and 3.
    """
    bs = blocks(
        "CONTENTS", "1. Short title.", "2. Definitions.",
        "3. Taxable Service.", "It is hereby enacted as follows:",
        "1. Short title. This Act may be called the Example Act.",
        "2. Definitions. In this Actâ€”",
        "(33) resident meansâ€”", "(i) an individual is resident ifâ€”",
        "1. he has a place of business; or 2. has his permanent address here;",
        "(iii) a company is resident ifâ€”",
        "1. its office is here; or 2. it has a place of business;",
        "or", "3. its management is situated here;",
        "3. Taxable Service. A taxable service is listed in the Schedule.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 4 else (2 if index <= 12 else 3)
        block["x0"] = 180.0 if index in {9, 11, 13} else 72.0
    seg = segment(bs)
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["1", "2", "3"]
    assert seg.repeated_labels_demoted == 0
    assert seg.missing == []


def test_bracketed_starred_omission_without_full_stop_is_a_section():
    seg = segment(blocks(
        "CONTENTS", "30. Prior.", "31. Omitted.", "32. Following.",
        "It is hereby enacted as follows:",
        "30. Prior. Operative text.",
        "2[ 31***]",
        "32. Following. Operative text.",
    ))
    sections = [node for node in seg.root.children if node.kind == "section"]
    # What this test is for: "2[ 31***]" -- a starred omission with no full stop
    # after the number -- opens section 31.
    assert {node.label for node in sections} == {"30", "31", "32"}
    assert [node.label for node in sections].count("31") == 1

    # Order is deliberately NOT asserted. This fixture's "CONTENTS" is not
    # detected as one, so its three contents lines stay in the body and collide
    # with the three real openers. Canonical selection now prefers the
    # occurrence that carries law over the one that merely repeats the heading,
    # so section 30 resolves to the block holding "Operative text." rather than
    # to the bare contents line -- which reorders root.children and is the
    # point. Across the corpus that moves 440 citations in 72 documents off a
    # heading and onto the provision; tools/measure_canonical_choice.py counts
    # it, because the segmentation fingerprint cannot see it.
    thirty = next(node for node in sections if node.label == "30")
    assert "Operative text." in "".join(thirty.text_parts)


def test_fused_amendment_marker_does_not_hide_omitted_heading():
    from nizam.corpus.segment import _heading_supports

    assert _heading_supports("2[Omitted.]", "[Omitted]")


def test_full_numeric_sequence_wins_when_omitted_toc_row_was_not_parsed():
    from nizam.corpus.segment import _repair_label

    toc = {str(number): f"Heading {number}" for number in range(1, 16)}
    assert _repair_label(
        "16", toc, set(toc), "2[Omitted.]",
    ) == "16"


def test_superscript_note_marker_block_is_not_decimal_section():
    bs = blocks(
        "1. Duty. Duty is imposed at the notified rate.",
        "6.\n7:",
        "2. Exemption. Government may exempt a mineral.",
    )
    seg = segment(bs)
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["1", "2"]
    assert seg.block_roles[bs[1]["id"]][0] == "footnote"


def test_compiled_act_amendment_typography_is_repaired_only_with_toc_proof():
    toc = {"14AB": "Discontinuance", "14AC": "Bar on operations",
           "33": "Offences", "33A": "Omitted", "37A": "Power to inquire"}

    assert classify("321[14AB.Discontinuance of connections.")[1] == "14AB"
    assert classify("[33. Offences and penalties.")[1] == "33"
    assert classify("506[33A***].")[1] == "33A"
    assert _classify_body("32214AC. Bar on operations.", toc)[1] == "14AC"
    assert _classify_body("52337A. Power to inquire.", toc)[1] == "37A"
    assert _classify_body("52337A. Power to inquire.", {}) is None
    assert _classify_body("697[72A\n Reference to authorities.",
                          {"72A": "Reference to authorities"})[1] == "72A"
    assert _classify_body("697[72A\n Reference to authorities.", {}) is None
    assert _classify_body("3[l35A. Exemption of members.",
                          {"135A": "Exemption of members"})[1] == "135A"
    assert _repair_label("125", {"24A": "Appearance", "25": "Omitted",
                                  "125": "Omitted"}, {"24A"}) == "25"
    assert _repair_label("125", {"24A": "Appearance", "25": "Omitted",
                                  "125": "Omitted"}, {"24A", "25"}) == "125"
    # A valid three-digit section must not lose its leading digit merely
    # because an earlier omitted section shares the suffix.  The body's own
    # heading independently identifies the full label.
    railways_toc = {
        "15": "Omitted", "16": "Omitted", "115": "Disposal of fines",
        "116": "Altering or defacing pass or ticket",
    }
    assert _repair_label(
        "116", railways_toc, {"15", "115"},
        "Altering or defacing pass or ticket. If a passenger...",
    ) == "116"
    # The source renders this as superscript footnote 7 + section 9; extraction
    # fuses the glyphs to 79. Independent heading evidence selects section 9.
    assert _repair_label(
        "79", {"8": "Alteration of pipes", "9": "Temporary entry",
               "78": "Omitted", "79": "Settlement of compensation"},
        {"8"}, "Temporary entry upon land for repairing an accident.",
    ) == "9"
    assert len(subdivide(
        "Prior enacted text.\n321[14AB.Discontinuance of connections."
        "\n32214AC. Bar on operations."
    )) == 3


def test_source_verified_patch_changes_only_the_derived_parse():
    bs = blocks(
        "6. Administration. Existing enacted text.",
        "a: Functions of Director General. More enacted text.",
        "8. Licensing Authority. Existing enacted text.",
    )
    original = bs[1]["text"]
    seg = segment(bs, curation_patches=[{
        "id": "proof-patch", "page_no": 1,
        "match_text": "Functions of Director General",
        "before_text": "a:", "after_text": "7.",
    }])
    assert bs[1]["text"] == original, "extracted evidence must remain immutable"
    assert [n.label for n in seg.root.children if n.kind == "section"] == ["6", "7", "8"]
    assert seg.curation_patches_applied == 1


def test_a_two_block_document_is_not_rejected_out_of_hand():
    """There is deliberately no minimum-block guard: it judged the extractor's
    typography instead of the document's structure, and rejected two sound
    statutes for having "fewer than 3 blocks".
    """
    seg = segment(blocks("SOME RULES, 1996", "1. Short title.\n2. Application."))
    assert len([n for n in seg.root.children if n.kind == "section"]) == 2


# ------------------------------------------------------- the block ledger, C4
def test_every_block_is_assigned_a_role():
    """CORPUS-CRITERIA C4. A block the walk never reaches must still appear --
    as 'unassigned', which is the defect counter, not as nothing at all.
    """
    bs = blocks(
        "THE EXAMPLE ACT, 2020",
        "WHEREAS it is expedient to provide for examples;",
        "1. Short title. This Act may be called the Example Act, 2020.",
        "2. Definitions. In this Act, unless the context otherwise requires,",
        "Page 1 of 1",
    )
    seg = segment(bs)
    assert set(seg.block_roles) == {b["id"] for b in bs}


def test_no_character_is_lost_between_blocks_and_roles():
    """CORPUS-CRITERIA C5, at the unit the corpus-wide query measures."""
    bs = blocks(
        "THE EXAMPLE ACT, 2020",
        "1. Short title. This Act may be called the Example Act, 2020.",
        "2. Extent. It extends to the whole of Pakistan.",
        "Page 1 of 1",
    )
    seg = segment(bs)
    assert sum(len(b["text"]) for b in bs) == sum(
        len(next(x["text"] for x in bs if x["id"] == bid))
        for bid in seg.block_roles)


def test_text_before_the_first_provision_is_preface_not_discarded():
    """A title page and a gazette line are not enacted text, but they are text.
    Akoma Ntoso gives them a home; so does this.
    """
    seg = segment(blocks(
        "GOVERNMENT OF THE PUNJAB, LAW DEPARTMENT",
        "Notification No. SO(LAW)1-2/2020, dated 4th March 2020.",
        "1. Short title. This Act may be called the Example Act, 2020.",
    ))
    roles = [r for r, _ in seg.block_roles.values()]
    assert roles[:2] == ["preface", "preface"]
    assert "unassigned" not in roles


def test_a_running_header_is_classified_not_dropped():
    seg = segment(blocks(
        "1. Short title. This Act may be called the Example Act, 2020.",
        "Page 90 of 179",
    ))
    assert seg.block_roles[1][0] == "running_header"


# ------------------------------------------------------------- no invention
def test_a_document_with_no_provisions_yields_no_provisions():
    """Document #3420 is 21 pages of recruitment rules in ten columns. Inventing
    a section number for it would break INV-1 and A3 at once; the honest answer
    is an empty tree and every block marked 'unstructured' by the caller.
    """
    seg = segment(blocks(
        "NAME OF THE DEPARTMENT", "FUNCTIONAL UNIT", "NAME OF THE POST",
        "APPOINTING AUTHORITY", "MINIMUM QUALIFICATION FOR INITIAL RECRUITMENT",
    ))
    assert seg.root.children == []
    assert set(seg.block_roles) == {0, 1, 2, 3, 4}


# ------------------------------------------- cross-references are not headings
def test_a_schedule_cross_reference_does_not_open_a_schedule():
    """The Balochistan Wildlife Act 2014 defines a game animal as one "included
    in Schedule- I, which may be hunted under a valid licence". The layout
    engine breaks that line, so the next block *starts* with "Schedule- I" and
    the grammar saw a schedule heading -- which then swallowed sections 3 to 96.
    """
    seg = segment(blocks(
        "1. Short title. This Act may be called the Example Act.",
        '2. Definitions. (a) "Game animal" means a wild animal included in',
        "Schedule- I, which may be hunted under a valid licence;",
        "3. Prohibition. No person shall hunt a game animal.",
    ))
    kinds = [(n.kind, n.label) for n in seg.root.children]
    assert ("schedule", "Schedule") not in kinds
    assert ("section", "3") in kinds


def test_a_real_schedule_heading_still_opens_one():
    """The guard must not cost a genuine heading. A real one follows a finished
    sentence -- the difference is the full stop, not the words.
    """
    seg = segment(blocks(
        "1. Short title. This Act may be called the Example Act.",
        "2. Repeal. The earlier Act is hereby repealed.",
        "THE FIRST SCHEDULE",
        "1. Fees payable on an application.",
    ))
    assert any(n.kind == "schedule" for n in seg.root.children)


def test_letter_spaced_schedule_heading_contains_numbered_rows():
    """Letter-spaced display typography still opens the printed schedule."""
    seg = segment(blocks(
        "1. Short title. These rules may be called the Example Rules.",
        "2. Definitions. In these rules, unless the context otherwise requires.",
        "S C H E D U L E",
        "STATEMENT SHOWING THE POSTS IN THE VARIOUS CADRES",
        "1. Secretary.",
        "2. Chief Accountant.",
        "1. Driver.",
        "2. Conductor.",
    ))

    schedule = next(n for n in seg.root.children if n.kind == "schedule")
    assert [n.kind for n in schedule.children] == ["clause"] * 4
    assert [n.label for n in schedule.children] == ["1", "2", "1", "2"]
    assert seg.repeated_labels_demoted == 0


def test_rule_prefixed_numbers_are_citable_provisions():
    seg = segment(blocks(
        "Rule 1. Short title. These rules may be called the Example Rules.",
        "Rule 2: Definitions. In these rules, unless the context otherwise requires.",
        "Regulation 12-A.- Appeals. An appeal shall lie to the Authority.",
    ))

    assert [(n.kind, n.label) for n in seg.root.children] == [
        ("section", "1"), ("section", "2"), ("section", "12-A")]


def test_zero_root_table_values_are_not_legal_sections():
    assert classify("0.2") is None
    assert classify("0...117 Meat") is None


def test_numbered_note_does_not_become_a_section():
    seg = segment(blocks(
        "Rule 10. Petitions shall be sent to Government.",
        "Note. 1. A second petition requires fresh grounds.",
    ))
    sections = [n for n in seg.root.children if n.kind == "section"]
    assert [n.label for n in sections] == ["10"]
    assert "second petition" in sections[0].text


def test_toc_heading_is_not_copied_onto_a_mismatching_table_row():
    toc = ["CONTENTS"] + [f"{n}. Main heading {n}." for n in range(1, 9)]
    body = [f"{n}. Main heading {n}. Enacted text." for n in range(1, 9)]
    table = ["1. Total dye content, percent by mass."]
    seg = segment(blocks(*toc, *body, *table))
    rows = [n for n in seg.flatten()
            if n.label == "1" and "dye content" in n.text.lower()]
    assert len(rows) == 1
    assert rows[0].heading is None


def test_consecutive_rule_prefixed_numbers_inside_one_block_are_split():
    seg = segment(blocks(
        "Rule 820. The authority may prescribe prison labour.\n"
        "Rule 821.- The tasks shall be fixed in the appendix."
    ))

    assert [(n.kind, n.label) for n in seg.root.children] == [
        ("section", "820"), ("section", "821")]


def test_a_heading_after_a_page_break_still_opens():
    """A running header interrupts the printed line but not the sentence, and a
    heading that follows one is genuine.
    """
    seg = segment(blocks(
        "1. Short title. This Act may be called the Example Act.",
        "Page 9 of 26",
        "CHAPTER II",
        "2. Application. This Chapter applies to every licensee.",
    ))
    assert any(n.kind == "chapter" for n in seg.root.children)


# ------------------------------------------------- the printed contents list
def test_the_contents_list_is_carried_as_entries():
    """Migration 0011. Counting agreement tells you 7,801 sections are missing;
    only the entries tell you WHICH, and a number you cannot act on is not a
    measurement.
    """
    toc = ["CONTENTS"] + [f"{n}. Heading number {n}." for n in range(1, 12)]
    body = [f"{n}. Heading number {n}. Some enacted text here." for n in range(1, 12)]
    seg = segment(blocks(*toc, *body))
    assert seg.toc_found
    assert [e["label"] for e in seg.toc_entries] == [str(n) for n in range(1, 12)]
    assert all(e["node"] is not None for e in seg.toc_entries)
    assert all(e["method"] == "label" for e in seg.toc_entries)
    assert [e["source_block_id"] for e in seg.toc_entries] == list(range(1, 12))
    assert all(e["source_page"] == 1 for e in seg.toc_entries)


def test_contents_marker_inside_block_and_letter_spaced_is_source_evidence():
    """Real portals fuse title/marker into one block and letter-space markers."""
    toc = ["THE EXAMPLE ACT\nC O N T E N T S"] + [
        f"{n}. Heading number {n}." for n in range(1, 8)]
    body = [f"{n}. Heading number {n}. Enacted text." for n in range(1, 8)]
    seg = segment(blocks(*toc, *body))
    assert seg.toc_found
    assert len(seg.toc_entries) == 7


def test_division_word_can_be_a_numbered_toc_heading():
    """A newline before FORM must not erase the numbered source entry."""
    toc = ["CONTENTS"] + [
        f"{n}.\n{'FORM AND VERIFICATION.' if n == 3 else f'Heading {n}.'}"
        for n in range(1, 9)
    ]
    body = [
        f"{n}. {'FORM AND VERIFICATION.' if n == 3 else f'Heading {n}.'} Text."
        for n in range(1, 9)
    ]
    seg = segment(blocks(*toc, *body))
    assert [entry["label"] for entry in seg.toc_entries] == [
        str(n) for n in range(1, 9)
    ]
    assert seg.toc_entries[2]["heading"] == "FORM AND VERIFICATION."


def test_explicit_table_rows_do_not_become_competing_sections():
    """Rows 1..N under a printed TABLE stay owned by the governing section."""
    headings = {
        **{n: f"Heading {n}" for n in range(1, 7)},
        7: "Charge of tax",
        8: "Payment of tax",
    }
    toc = ["CONTENTS"] + [
        f"{n}. {headings[n]}." for n in range(1, 9)
    ]
    body = [
        f"{n}. {headings[n]}. Enacted text." for n in range(1, 8)
    ] + [
        "TABLE",
        "1. Liquid assets not repatriated 5%\n"
        "2. Immovable assets outside Pakistan 3%",
        "8. Payment of tax. Enacted text.",
    ]
    seg = segment(blocks(*toc, *body))
    top_sections = [
        node for node in seg.root.children if node.kind == "section"
    ]
    assert [node.label for node in top_sections] == [
        str(n) for n in range(1, 9)
    ]
    section_seven = next(node for node in top_sections if node.label == "7")
    assert [node.label for node in section_seven.children] == ["1", "2"]
    assert all(node.kind == "clause" for node in section_seven.children)
    assert seg.repeated_label_decisions == []


def test_late_contents_cannot_turn_an_earlier_body_into_contents():
    """Document 8514 has a contents page after a complete 104-page expression.

    Its later numbering agrees perfectly with the earlier body. Position still
    refutes the hypothesis: a late list cannot make preceding enacted law into
    front matter.
    """
    rows = []
    for n in range(1, 21):
        rows.append({"id": len(rows), "text": f"{n}. Enacted rule {n}. Text.",
                     "page_no": n, "y0": 100.0, "page_height": 792.0})
    rows.append({"id": len(rows), "text": "C O N T E N T S", "page_no": 21,
                 "y0": 100.0, "page_height": 792.0})
    for n in range(1, 21):
        rows.append({"id": len(rows), "text": f"{n}. Enacted rule {n}.",
                     "page_no": 21, "y0": 120.0, "page_height": 792.0})
    seg = segment(rows)
    # The concern this test exists for -- a late list must not make preceding
    # enacted law into front matter -- is asserted here and is unchanged.
    assert seg.body_starts_page == 1
    assert [n.label for n in seg.root.children if n.kind == "section"][:20] == [
        str(n) for n in range(1, 21)]
    assert seg.repeated_labels_demoted == 0

    # `toc_found` became True on 19 Sep 2026 and that is an improvement, not a
    # regression. The trailing-contents repair now recognises a contents list
    # printed AFTER the body, and it does so without moving the body: the
    # boundary is set to 0 and the body is cut at the marker, so pages 1-20
    # remain the body and only the late list is excluded from it. What the
    # document gains is twenty promises to check the body against -- agreement
    # 1.0000 here -- and the twenty collisions its rows used to cause are gone.
    #
    # The repair is tightly guarded: the marker must sit in the document's last
    # pages, every label it prints must ALREADY be a citable label above it, and
    # every repeated-label collision in the document must fall inside the region.
    # A genuine front contents list cannot satisfy those, and a late list that
    # promises anything the body does not already have is refused.
    assert seg.toc_found
    assert seg.agreement == 1.0


def test_repeated_printed_toc_labels_are_not_collapsed():
    toc = ["CONTENTS"] + [f"{n}. Main heading {n}." for n in range(1, 8)]
    toc += ["1. First schedule item.", "2. Second schedule item."]
    body = [f"{n}. Main heading {n}. Enacted text." for n in range(1, 8)]
    seg = segment(blocks(*toc, *body))
    assert seg.toc_found
    assert [e["label"] for e in seg.toc_entries].count("1") == 2
    assert [e["heading"] for e in seg.toc_entries if e["label"] == "1"] == [
        "Main heading 1.", "First schedule item."]


def test_a_section_promised_but_absent_is_an_unmatched_entry():
    """The gap must survive as a row, not vanish into a count."""
    toc = ["CONTENTS"] + [f"{n}. Heading number {n}." for n in range(1, 12)]
    body = [f"{n}. Heading number {n}. Some enacted text here."
            for n in range(1, 12) if n != 7]
    seg = segment(blocks(*toc, *body))
    gaps = [e for e in seg.toc_entries if e["node"] is None]
    assert [e["label"] for e in gaps] == ["7"]
    assert gaps[0]["heading"] == "Heading number 7."
    assert gaps[0]["method"] == "unmatched"


def test_source_verified_omission_becomes_an_empty_citable_version():
    """A printed omission is lifecycle metadata, never invented body text."""
    toc = ["CONTENTS"] + [
        f"{n}. {'[Omitted]' if n == 7 else f'Heading number {n}.'}"
        for n in range(1, 12)
    ]
    body = [f"{n}. Heading number {n}. Some enacted text here."
            for n in range(1, 12) if n != 7]
    source = blocks(*toc, *body)
    seg = segment(source, toc_dispositions=[{
        "id": 41,
        "toc_entry_ordinal": 6,
        "printed_label": "7",
        "printed_heading": "[Omitted]",
        "disposition": "omitted",
        "source_block_id": 7,
        "source_page": 1,
        "amending_instrument_id": None,
    }])
    entry = next(item for item in seg.toc_entries if item["label"] == "7")
    node = entry["node"]
    assert node is not None
    assert entry["method"] == "source_verified_disposition"
    assert node.kind == "section"
    assert node.text == ""
    assert node.operation == "omitted"
    assert node.amendment_note == "[Omitted]"
    assert node.toc_disposition_assertion_id == 41
    assert node.first_block == 7
    assert "7" not in seg.missing


def test_source_verified_trailing_omission_word_is_materialised():
    """A retained description may precede the lifecycle word in the TOC."""
    heading = "Exceptional first offenders or repeat offenders [omitted]"
    toc = ["CONTENTS"] + [
        f"{n}. {heading if n == 7 else f'Heading number {n}.'}"
        for n in range(1, 12)
    ]
    body = [
        f"{n}. Heading number {n}. Some enacted text here."
        for n in range(1, 12) if n != 7
    ]
    seg = segment(blocks(*toc, *body), toc_dispositions=[{
        "id": 43,
        "toc_entry_ordinal": 6,
        "printed_label": "7",
        "printed_heading": heading,
        "disposition": "omitted",
        "source_block_id": 7,
        "source_page": 1,
        "amending_instrument_id": None,
    }])
    entry = next(item for item in seg.toc_entries if item["label"] == "7")
    assert entry["method"] == "source_verified_disposition"
    assert entry["node"].operation == "omitted"
    assert entry["node"].amendment_note == heading


def test_stale_toc_disposition_coordinates_fail_closed():
    toc = ["CONTENTS"] + [f"{n}. Heading {n}." for n in range(1, 8)]
    body = [f"{n}. Heading {n}. Enacted text." for n in range(1, 8) if n != 4]
    import pytest
    with pytest.raises(ValueError, match="stale or unmatched TOC disposition"):
        segment(blocks(*toc, *body), toc_dispositions=[{
            "id": 42, "toc_entry_ordinal": 3, "printed_label": "4",
            "printed_heading": "Heading 4.", "disposition": "omitted",
            "source_block_id": 999, "source_page": 1,
            "amending_instrument_id": None,
        }])


# --------------------------------------------------- finding the body boundary
def test_a_refuted_contents_hypothesis_is_rejected():
    """The Punjab Distillery Rules print no contents list. The chooser took its
    best guess anyway -- scoring 0.064 -- and filed 24 pages of enacted text as
    a contents list, keeping 8 sections of 272. A boundary that scores that low
    is not a contents list read badly; it is a hypothesis the document refuted.
    """
    # 40 body sections, no contents list, then a short numbered schedule that
    # restarts at 1 -- the only fall in the document.
    body = [f"{n}. Rule number {n}. Some enacted text for rule {n}." for n in range(1, 41)]
    tail = [f"{n}. Form entry {n}." for n in range(1, 4)]
    seg = segment(blocks(*body, *tail))
    assert not seg.toc_found
    labels = [n.label for n in seg.root.children if n.kind == "section"]
    assert len(labels) >= 40, len(labels)


def test_a_contents_list_cannot_be_longer_than_its_body():
    """A contents list summarises a body, so a split leaving fewer numbered
    units after it than before it is upside down.
    """
    from nizam.corpus.segment import parse_contents
    body = [f"{n}. Rule number {n}. Enacted text." for n in range(1, 41)]
    tail = [f"{n}. Form entry {n}." for n in range(1, 4)]
    _, boundary, found = parse_contents(blocks(*body, *tail))
    assert not found and boundary == 0


def test_repeated_rows_after_body_are_siblings_not_an_unbounded_chain():
    """A trailing tariff/table can restart labels already used by the Act.

    Each row is retained as a provision-backed schedule_row, but one row cannot
    become the parent of the next. Observation 1397 exposed a 189-level chain
    and a 1,499-byte ltree path before this regression was added.
    """
    toc = ["CONTENTS"] + [f"{n}. Heading {n}." for n in range(1, 12)]
    body = [f"{n}. Heading {n}. Enacted text." for n in range(1, 12)]
    tail = [f"{n}. Tariff table row {n}." for n in range(1, 9)]
    seg = segment(blocks(*toc, *body, *tail))
    rows = [n for n in seg.flatten()
            if seg.block_roles[n.first_block][0] == "schedule_row"]
    assert len(rows) == len(tail)
    assert len({id(n.parent) for n in rows}) == 1
    assert max(n.depth for n in seg.flatten()) <= 5


def test_repeated_top_level_labels_without_contents_are_not_ambiguous_sections():
    """A notification's wage table restarts each occupation list at 1 without
    printing a SCHEDULE heading.  Keep every row, but only the first can be the
    instrument's section 1; later rows are explicit schedule-row clauses.
    """
    seg = segment(blocks(
        "1. Application. This notification applies to listed industries.",
        "2. Minimum wage. The minimum wage shall be prescribed.",
        "1. Production Manager 2. Mills Manager 3. Sales Manager",
        "1. Scale Man 2. Weigher 3. Line Sardar",
    ))
    top_sections = [n for n in seg.root.children
                    if n.kind == "section" and n.label == "1"]
    rows = [n for n in seg.root.children
            if n.kind == "clause" and n.label == "1"]
    assert len(top_sections) == 1
    assert len(rows) == 2
    assert seg.repeated_labels_demoted == 2
    assert all(seg.block_roles[n.first_block][0] == "schedule_row" for n in rows)


def test_repeated_sibling_labels_inside_a_chapter_are_preserved_but_not_citable_twice():
    seg = segment(blocks(
        "CHAPTER I",
        "1. Application. This Chapter applies.",
        "2. Main rule. The principal rule applies.",
        "1. Table row one. Preserved schedule-like content.",
        "1. Table row two. Preserved schedule-like content.",
    ))
    chapter = next(n for n in seg.root.children if n.kind == "chapter")
    assert [(n.kind, n.label) for n in chapter.children] == [
        ("section", "1"), ("section", "2"), ("clause", "1"), ("clause", "1")]
    assert seg.repeated_labels_demoted == 2


def test_dotted_regulation_labels_are_not_false_repeated_sections():
    """Dotted regulation numbers are complete printed citation labels.

    The former grammar stopped at the first dot, so 10.3, 10.3.1 and 10.4 all
    became sibling section 10; the collision guard then retyped two real legal
    units as schedule rows.  Keep the source labels and their text intact.
    """
    seg = segment(blocks(
        "10. General building requirements.",
        "10.3 Submission of plans and documents",
        "10.3.1 Plans. The builder shall submit the prescribed plans.",
        "10.4 Sanction or rejection of building plans",
    ))
    nodes = [n for n in seg.root.children if n.kind == "section"]
    assert [n.label for n in nodes] == ["10", "10.3", "10.3.1", "10.4"]
    assert seg.repeated_labels_demoted == 0
    assert "The builder shall submit" in nodes[2].text


def test_dotted_labels_with_spaces_and_terminal_period_are_preserved():
    seg = segment(blocks(
        "6. Main regulation.",
        "6 . 2 . Internal building requirements.",
        "6.2.1. Basement requirements apply.",
    ))
    assert [n.label.replace(" ", "") for n in seg.root.children
            if n.kind == "section"] == ["6", "6.2", "6.2.1"]
    assert seg.repeated_labels_demoted == 0


def test_path_disambiguation_cannot_collide_with_a_real_dotted_label():
    from nizam.corpus.segment import Node, Segmentation, assign_paths

    root = Node("instrument", "root")
    for label in ("2.4", "2", "2"):
        root.children.append(Node("clause", label, parent=root))
    seg = Segmentation(root=root, toc={}, body_starts_page=1, toc_found=False)
    paths = [path for _, path in assign_paths(seg, "fed.rules.y2021_o1")]
    assert len(paths) == len(set(paths)) == 3
    assert paths[0].endswith("cl_2_4")


def test_decimal_rates_tariff_codes_and_year_headers_are_not_sections():
    seg = segment(blocks(
        "1. Charging provision. Tax shall be charged at the prescribed rate.",
        "1.5 Percent",
        "9812.7900 Others 19.5%",
        "2025. SINDH ACT NO. XIV OF 2025.",
    ))
    assert [(n.kind, n.label) for n in seg.root.children] == [("section", "1")]
    assert seg.repeated_labels_demoted == 0


def test_fused_amendment_markers_are_footnotes_not_year_sections():
    seg = segment(blocks(
        "25. Powers of the Authority. The Authority may prescribe rules.",
        "16Substituted for the words ‘local authority’ by Act XIII of 2009.",
    ))
    assert [(n.kind, n.label) for n in seg.root.children] == [("section", "25")]
    assert seg.block_roles[1][0] == "footnote"


def test_amendment_footnote_citations_are_not_subdivided_into_sections():
    seg = segment(blocks(
        "2. Definitions. In this Act, the following definitions apply.",
        "7Substituted for the figure ‘1897’ by Act IX of 1937, s. 2. It was provided that the amendment applied prospectively.",
    ))
    assert [(n.kind, n.label) for n in seg.root.children] == [("section", "2")]
    assert seg.block_roles[1][0] == "footnote"
    assert seg.repeated_labels_demoted == 0


def test_forms_create_distinct_containers_for_restarted_item_numbers():
    seg = segment(blocks(
        "1. Application. These rules apply.",
        "FORM A",
        "1. Name of applicant __________________",
        "2. Address ____________________________",
        "FORM B",
        "1. Name of licensee ___________________",
        "2. Licence number _____________________",
    ))
    forms = [n for n in seg.root.children if n.kind == "form"]
    assert [n.label for n in forms] == ["FORM A", "FORM B"]
    assert [[c.label for c in form.children] for form in forms] == [
        ["1", "2"], ["1", "2"]]
    assert all(c.kind == "clause" for form in forms for c in form.children)
    assert seg.repeated_labels_demoted == 0


def test_cpc_order_is_preserved_beneath_schedule_with_its_rules():
    seg = segment(blocks(
        "1. Short title. This Act may be called the example Act.",
        "FIRST SCHEDULE",
        "ORDER VII",
        "1. Particulars to be contained in plaint.",
        "11. Rejection of plaint.",
    ))
    schedule = next(n for n in seg.root.children if n.kind == "schedule")
    order = next(n for n in schedule.children if n.kind == "order")
    assert order.label == "ORDER VII"
    assert [(n.kind, n.label) for n in order.children] == [
        ("clause", "1"), ("clause", "11")]


def test_explicit_enactment_moves_boundary_past_nested_order_contents():
    toc = ["THE EXAMPLE CODE, 1908", "CONTENTS"] + [
        f"{n}. Main section {n}." for n in range(1, 9)]
    order_contents = ["ORDER VII"] + [
        f"{n}. Printed order-rule heading {n}." for n in range(1, 13)]
    body = [
        "THE EXAMPLE CODE, 1908",
        "WHEREAS it is expedient to consolidate the law; It is hereby enacted as follows:",
    ] + [f"{n}. Main section {n}. Enacted text." for n in range(1, 9)]
    seg = segment(blocks(*toc, *order_contents, *body))
    # What this test is for: the enactment formula must move the boundary past
    # the nested Order contents so the Code's own sections 1-8 are the body.
    # That still holds, and those are the assertions below.
    assert seg.body_starts_page == 1
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        str(n) for n in range(1, 9)]
    assert seg.repeated_labels_demoted == 0

    # `toc_found` is deliberately False here, changed 19 Sep 2026. This fixture
    # lists ORDER VII's twelve rules in the contents and never prints them in
    # the body, so the contents hypothesis it produces keeps NONE of its twelve
    # promises -- post-walk agreement 0.0000. The refutation at the end of
    # segment() withdraws a hypothesis the body has disproved, which is what
    # this fixture describes. The three assertions above are unchanged, so the
    # behaviour the test exists to protect is unaffected; only the claim that a
    # contents list was found has gone, and it was a claim about a list whose
    # every entry was missing.
    #
    # A real Code prints those rules in its First Schedule: add them to this
    # fixture and agreement rises to 1.0000 and `toc_found` is True again.
    assert not seg.toc_found
    assert seg.agreement == 0.0


def test_enactment_recovers_body_before_later_schedule_number_restart():
    """A later Schedule 1..N must not outrank the enacted Rules 1..N.

    This is the Punjab Weights and Measures layout: contents, title/enacting
    formula, operative rules, then a technical schedule that restarts the same
    numbering. The numeric scorer can tie on the schedule, so the source's
    enacting formula must be allowed to move the boundary earlier.
    """
    toc = ["THE EXAMPLE RULES, 1976", "CONTENTS"] + [
        f"{n}. Main rule {n}." for n in range(1, 9)]
    body = [
        "THE EXAMPLE RULES, 1976",
        "In exercise of the powers conferred by the Act, the Governor is pleased "
        "to make the following rules, namely:-",
    ] + [f"{n}. Main rule {n}. Operative enacted text." for n in range(1, 9)]
    schedule = ["SCHEDULE I"] + [
        f"{n}. Technical specification {n}." for n in range(1, 9)]

    seg = segment(blocks(*toc, *body, *schedule))
    sections = [n for n in seg.root.children if n.kind == "section"]
    assert seg.toc_found
    assert [n.label for n in sections] == [str(n) for n in range(1, 9)]
    assert all((n.heading or "").startswith("Main rule") for n in sections)


def test_explicit_cross_referenced_schedule_stops_principal_body_scan():
    """Later Standing Order labels remain inside their printed Schedule."""
    toc = ["THE EXAMPLE ORDINANCE", "CONTENTS"] + [
        f"{n}. Main section {n}." for n in range(1, 11)
    ] + ["SCHEDULE STANDING ORDERS"] + [
        f"{n}. Standing order {n}." for n in range(1, 13)
    ]
    body = ["It is hereby enacted as follows:"] + [
        f"{n}. Main section {n}. Operative text." for n in range(1, 11)
    ] + ["SCHEDULE\nSTANDING ORDERS [SECTION 2(g)]"] + [
        f"{n}. Standing order {n}. Schedule text." for n in range(1, 13)
    ]
    bs = blocks(*toc, *body)
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index < len(toc) else 2

    seg = segment(bs)
    root_sections = [node for node in seg.root.children
                     if node.kind == "section"]
    schedule = next(node for node in seg.root.children
                    if node.kind == "schedule")
    assert [node.label for node in root_sections] == [
        str(n) for n in range(1, 11)
    ]
    assert [node.label for node in schedule.children] == [
        str(n) for n in range(1, 13)
    ]
    assert all(node.kind == "clause" for node in schedule.children)
    assert seg.repeated_labels_demoted == 0


def test_rulemaking_formula_plus_opening_toc_headings_proves_body():
    """A notification may not repeat the Rules title beside its formula."""
    toc = ["THE FOOD RULES, 2011", "CONTENTS"] + [
        f"{n}. Rule heading {n}." for n in range(1, 9)]
    body = [
        "GOVERNMENT OF THE PUNJAB",
        "In exercise of the powers conferred by the Ordinance, the Governor is "
        "pleased to make the following rules:",
    ] + [f"{n}. Rule heading {n}. Operative enacted text." for n in range(1, 9)]
    later_table = [f"{n}. Table characteristic {n}." for n in range(1, 9)]

    seg = segment(blocks(*toc, *body, *later_table))
    sections = [n for n in seg.root.children if n.kind == "section"]
    assert seg.toc_found
    assert [n.label for n in sections[:8]] == [str(n) for n in range(1, 9)]
    assert all((n.heading or "").startswith("Rule heading")
               for n in sections[:8])


def test_appended_different_act_enactment_does_not_move_body_boundary():
    toc = ["THE PRINCIPAL RULES, 1934", "CONTENTS"] + [
        f"{n}. Principal rule {n}." for n in range(1, 9)]
    body = [f"{n}. Principal rule {n}. Enacted text." for n in range(1, 9)]
    appendix = [
        "THE UNRELATED AMENDMENT ACT, 1960",
        "WHEREAS it is expedient to amend another law; It is hereby enacted as follows:",
        "1. Short title. This is the unrelated amendment.",
    ]
    seg = segment(blocks(*toc, *body, *appendix))
    sections = [n for n in seg.root.children if n.kind == "section"]
    assert [n.label for n in sections[:8]] == [str(n) for n in range(1, 9)]
    assert "Principal rule 1" in (sections[0].heading or "")


def test_repeated_title_plus_substantive_first_section_proves_body_without_whereas():
    toc = ["THE SERVICE RULES, 1994", "CONTENTS"] + [
        f"{n}. Rule heading {n}." for n in range(1, 9)]
    nested_contents = [f"{n}. Form item {n}." for n in range(1, 5)]
    body = ["THE SERVICE RULES, 1994"] + [
        f"{n}. Rule heading {n}. The appointing authority shall apply this rule."
        for n in range(1, 9)]
    seg = segment(blocks(*toc, *nested_contents, *body))
    assert seg.toc_found
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        str(n) for n in range(1, 9)]
    assert seg.repeated_labels_demoted == 0


def test_title_like_boundary_cannot_destroy_toc_agreement():
    toc = ["THE RELIEF ACT, 1958", "CONTENTS"] + [
        f"{n}. Main heading {n}." for n in range(1, 9)]
    body = [f"{n}. Main heading {n}. Enacted text." for n in range(1, 9)]
    later = [
        "THE RELIEF ACT, 1958",
        "1. Main heading 1. A later amendment quotes only this section at length.",
    ]
    seg = segment(blocks(*toc, *body, *later))
    assert seg.agreement == 1.0
    assert [n.label for n in seg.root.children if n.kind == "section"][:8] == [
        str(n) for n in range(1, 9)]


def test_consecutive_provisos_are_siblings_of_the_same_provision():
    seg = segment(blocks(
        "1. Conditions. A licence may be granted.",
        "Provided that the applicant is qualified;",
        "Provided that the prescribed fee is paid;",
        "Provided that the authority records reasons.",
    ))
    provisos = [n for n in seg.flatten() if n.kind == "proviso"]
    assert len(provisos) == 3
    assert len({id(n.parent) for n in provisos}) == 1
    assert all(n.parent.kind == "section" for n in provisos)


def test_a_two_column_contents_list_is_found():
    """The Cantonments Ordinance sets its contents as a table, so the number and
    the heading arrive as separate lines with no period. That made a 302-entry
    contents list invisible and cost 218 sections.
    """
    toc = [f"{n}\nHeading number {n}." for n in range(1, 21)]
    body = [f"{n}. Heading number {n}. Enacted text for section {n}."
            for n in range(1, 21)]
    seg = segment(blocks(*toc, *body))
    assert seg.toc_found
    assert seg.agreement >= 0.95, seg.agreement


def test_unmarked_two_page_contents_in_short_act_does_not_demote_body():
    """The ten-page Ferries Act prints an unmarked contents list on pages 1-2.

    Its body starts on page 3, beyond the old 20%-of-document front-matter
    cutoff. Exact label/heading repetition proves the boundary independently;
    the contents entries must not become the canonical legal sections.
    """
    bs: list[dict] = []
    ident = 0
    for n in range(1, 13):
        page = 1 if n <= 6 else 2
        bs.append({"id": ident, "text": f"{n}.\nHeading number {n}",
                   "page_no": page, "y0": 80.0 + n * 20,
                   "page_height": 792.0})
        ident += 1
    for n in range(1, 13):
        page = 3 + (n - 1) // 2
        bs.append({"id": ident,
                   "text": f"{n}. Heading number {n}. Enacted text for section {n}.",
                   "page_no": page, "y0": 100.0 + (n % 2) * 200,
                   "page_height": 792.0})
        ident += 1

    seg = segment(bs)
    assert seg.toc_found
    assert seg.body_starts_page == 3
    assert seg.agreement == 1.0
    assert seg.repeated_labels_demoted == 0
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        str(n) for n in range(1, 13)]


def test_enactment_correction_runs_before_unmarked_front_matter_gate():
    """A numbered list inside section 3 must not hide the real page-3 restart.

    Document 2552 prints an unmarked 1..22 contents list on pages 1-2.  The Act
    restarts at 1 after its repeated title and enactment on page 3, but section
    3 contains a numbered membership list on page 4.  Both restart candidates
    have perfect label agreement.  The ordinary tie-breaker chooses the later
    list, so the enacting formula must correct that provisional choice before
    the front-matter placement gate decides whether a TOC exists.
    """
    bs: list[dict] = []
    ident = 0
    headings = {n: f"Statutory heading number {n}" for n in range(1, 9)}
    for n in range(1, 9):
        bs.append({"id": ident, "text": f"{n}. {headings[n]}",
                   "page_no": 1 if n <= 4 else 2,
                   "y0": 80.0 + n * 20, "page_height": 792.0})
        ident += 1
    for text in (
        "THE EXAMPLE AUTHORITY ACT, 2026",
        "WHEREAS it is expedient to establish an Authority; "
        "It is hereby enacted as follows:",
    ):
        bs.append({"id": ident, "text": text, "page_no": 3,
                   "y0": 60.0 + ident * 5, "page_height": 792.0})
        ident += 1
    for n in range(1, 9):
        bs.append({"id": ident,
                   "text": f"{n}. {headings[n]}. Operative enacted text.",
                   "page_no": 3 if n <= 2 else 4 + (n - 3) // 2,
                   "y0": 100.0 + (n % 2) * 200, "page_height": 792.0})
        ident += 1
        if n == 3:
            for member in range(1, 9):
                bs.append({"id": ident,
                           "text": f"{member}. Member category {member}",
                           "page_no": 4, "y0": 320.0 + member * 20,
                           "page_height": 792.0})
                ident += 1

    seg = segment(bs)
    assert seg.toc_found
    assert seg.body_starts_page == 3
    sections = [n for n in seg.root.children if n.kind == "section"]
    assert sections[0].first_block == 10
    assert [n.label for n in sections] == [str(n) for n in range(1, 9)]


def test_serial_number_table_rows_belong_to_the_open_subsection():
    """A printed S. No./column grid is not a second set of Act sections."""
    toc = ["CONTENTS"] + [
        "1. Short title.",
        "2. Definitions.",
        "3. Authority.",
        "4. Powers of the Authority.",
    ]
    body = [
        "1. Short title. This Act may be called the Example Act.",
        "2. Definitions. In this Act, unless the context otherwise requires.",
        "3. Authority. (1) There shall be an Authority.",
        "(2) The Authority shall consist of the following, namely:",
        "S. No.\nMembership\nStatus\n(1)\n(2)\n(3)\n"
        "1. Prime Minister\nChairperson",
        "2. Finance Minister\nMember",
        "3. Secretary\nMember",
        "4. Managing Director\nMember",
        "4. Powers of the Authority. The Authority may exercise its powers.",
    ]

    seg = segment(blocks(*toc, *body))
    sections = [n for n in seg.root.children if n.kind == "section"]
    assert [n.label for n in sections] == ["1", "2", "3", "4"]
    authority = sections[2]
    rows = [n for n in seg.flatten()
            if n.kind == "clause" and n.label in {"1", "2", "3", "4"}]
    assert [n.label for n in rows] == ["1", "2", "3", "4"]
    def belongs_to_authority(row):
        parent = row.parent
        while parent is not None:
            if parent is authority:
                return True
            parent = parent.parent
        return False

    assert all(belongs_to_authority(row) for row in rows)
    assert seg.repeated_labels_demoted == 0


def test_front_numbered_table_with_same_labels_is_not_contents_without_heading_support():
    """High label overlap is insufficient when the predicted headings differ."""
    bs: list[dict] = []
    ident = 0
    for n in range(1, 9):
        bs.append({"id": ident, "text": f"{n}. Employee category {n}",
                   "page_no": 1 if n <= 4 else 2, "y0": 80.0 + n * 20,
                   "page_height": 792.0})
        ident += 1
    for n in range(1, 9):
        bs.append({"id": ident,
                   "text": f"{n}. Statutory power {n}. The authority shall act.",
                   "page_no": 3 + (n - 1) // 2,
                   "y0": 100.0 + (n % 2) * 200, "page_height": 792.0})
        ident += 1

    seg = segment(bs)
    assert not seg.toc_found
    assert seg.body_starts_page == 1
    assert seg.repeated_labels_demoted == 8


def test_page_footnotes_are_not_mistaken_for_a_two_column_contents():
    """Amendment footnotes wear the same shape -- a number, then capitalised
    text -- but restart on every page instead of ascending.
    """
    from nizam.corpus.segment import _twocol_run
    notes = [f"{n}\nInserted by the Finance Act, 200{n}." for n in (1, 2, 1, 2, 1, 2)]
    assert _twocol_run(blocks(*notes)) == []


def test_two_column_contents_keeps_bare_omitted_rows():
    """An official contents ledger may cite repealed slots as ``[Omitted]``.

    Those rows are still ground-truth citations and must remain between their
    enacted neighbours; they are not amendment-note apparatus.
    """
    from nizam.corpus.segment import _twocol_run

    entries = [
        f"{n}\n[Omitted]" if n in (6, 8) else f"{n}\nHeading number {n}"
        for n in range(1, 10)
    ]
    run = _twocol_run(blocks(*entries), {str(n) for n in range(1, 10)})
    assert [item[2] for item in run] == [str(n) for n in range(1, 10)]
    assert run[5][3] == "[Omitted]"


def test_two_column_contents_keeps_inserted_suffix_sequence_and_omissions():
    from nizam.corpus.segment import _twocol_run

    labels = [
        "12", "13", "14", "14A", "14B", "14C", "15", "16", "17",
        "18", "19", "19A", "20", "21", "21A", "22", "30", "31", "32",
        "33", "33A", "34",
    ]
    entries = [
        f"{label}\nOmitted." if label in {"31", "33A"}
        else f"{label}\nHeading {label}"
        for label in labels
    ]
    run = _twocol_run(blocks(*entries), set(labels))
    assert [item[2] for item in run] == labels


def test_detached_numbered_heading_and_same_number_body_are_one_section():
    seg = segment(blocks(
        "1. Short title and commencement.",
        "1. (1) This Act may be called the Example Act, 2026. "
        "(2) It shall come into force at once.",
        "2. Definitions.",
        "2. In this Act, unless there is anything repugnant in the subject or context—",
    ))
    sections = [n for n in seg.root.children if n.kind == "section"]
    assert [n.label for n in sections] == ["1", "2"]
    assert sections[0].heading == "Short title and commencement"
    assert sections[0].children[0].text.startswith("This Act may be called")
    assert sections[1].heading == "Definitions"
    assert sections[1].text.startswith("In this Act")
    assert seg.detached_heading_bodies_merged == 2
    assert seg.repeated_labels_demoted == 0


def test_nonadjacent_repeated_section_is_not_merged_into_heading_only_section():
    seg = segment(blocks(
        "1. Short title.",
        "2. Operative provision. The authority shall act.",
        "1. A later numbered table or compiled instrument row.",
    ))
    assert seg.detached_heading_bodies_merged == 0
    assert seg.repeated_labels_demoted == 1


def test_explicit_contents_plus_formula_and_marginal_headings_proves_body():
    bs = blocks(
        "THE HOSPITAL ACT, 2026", "CONTENTS",
        *[f"{n}. Heading number {n}." for n in range(1, 9)],
        "It is hereby enacted as follows:",
        "Heading number 1.", "1. (1) Operative text for section one.",
        "Heading number 2.", "2. Operative text for section two.",
        "Heading number 3.", "3. Operative text for section three.",
    )
    # Put body/formula on a later page so preceding marginal headings can be
    # distinguished from the contents entries by source page.
    for i, block in enumerate(bs):
        block["page_no"] = 1 if i < 10 else 2
    seg = segment(bs)
    assert seg.toc_found
    assert seg.body_starts_page == 2
    assert [n.label for n in seg.root.children if n.kind == "section"] == ["1", "2", "3"]


def test_formula_boundary_uses_same_page_heading_after_numbered_body():
    """A left marginal heading may follow its right-column operative block."""
    bs = blocks(
        "THE TECHNICAL EDUCATION ACT, 2026", "CONTENTS",
        "1. Short title, extent and commencement.",
        "2. Definitions.",
        "3. Constitution of the Board.",
        "4. Powers and functions of the Board.",
        "5. Term of office.",
        "THE TECHNICAL EDUCATION ACT, 2026",
        "It is hereby enacted as follows:",
        "1. (1) This Act may be called the Technical Education Act, 2026.",
        "Short title extent and commencement. 2. In this Act, definitions apply.",
        "3. Substituted by the Amendment Act, 2025.",
        "4. Substituted by the Amendment Act, 2025.",
        "Definitions. 3. The Government shall constitute a Board.",
        "Constitution of the Board. 4. The Board shall exercise its powers.",
        "Powers and functions of the Board. 5. Members shall hold office for three years.",
        "Term of office.",
    )
    for i, block in enumerate(bs):
        block["page_no"] = 1 if i < 7 else 2
    seg = segment(bs)
    assert seg.toc_found
    assert seg.body_starts_page == 2
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        "1", "2", "3", "4", "5",
    ]


def test_detached_marginal_heading_blocks_attach_to_next_section():
    bs = blocks(
        "CONTENTS",
        "1. First.", "2. Second.", "3. Third.",
        "4. Fixation of wage periods.", "5. Fifth.",
        "It is hereby enacted as follows:",
        "1. First. Operative one.",
        "2. Second. Operative two.",
        "3. Third. Operative three.",
        "Fixation of wage", "periods.",
        "4. (1) Every employer shall fix wage periods.",
        "5. Fifth. Operative five.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
        block["x0"], block["x1"] = 70.0, 430.0
    for index in (10, 11):
        bs[index]["x0"], bs[index]["x1"] = 450.0, 550.0
    seg = segment(bs)
    third = next(node for node in seg.root.children if node.label == "3")
    fourth = next(node for node in seg.root.children if node.label == "4")
    assert "Fixation of wage" not in third.text
    assert fourth.heading == "Fixation of wage periods."
    assert seg.block_roles[bs[10]["id"]] == ("heading", fourth)
    assert seg.block_roles[bs[11]["id"]] == ("heading", fourth)


def test_toc_proves_unpunctuated_section_in_marginal_layout():
    """Balochistan consolidations put the marginal heading and number/body in
    separate blocks, and sometimes omit the full stop after the number.  The
    ordered contents, matching marginal heading, and next expected label are
    joint evidence for a section; the bare number alone is not.
    """
    bs = blocks(
        "CONTENTS",
        "1. First power.", "2. Second power.", "3. Third power.",
        "4. Fourth power.", "5. Fifth power.",
        "It is hereby enacted as follows:",
        "First power.", "1. The authority shall do the first thing.",
        "Second power.", "2. The authority shall do the second thing.",
        "Third power.", "3\nThe authority shall do the third thing.",
        "Fourth power.", "4. The authority shall do the fourth thing.",
        "Fifth power.", "5. The authority shall do the fifth thing.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
    seg = segment(bs)
    assert seg.toc_found
    assert seg.missing == []
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        "1", "2", "3", "4", "5",
    ]


def test_fused_margin_recovery_only_touches_an_unresolved_toc_label():
    bs = blocks(
        "CONTENTS",
        "1. Short title.", "2. Definitions.", "3. Authority.",
        "4. Powers.", "5. Procedure.",
        "It is hereby enacted as follows:",
        "1. This Act may be called the Example Act.",
        # Real Balochistan fusion (document 362) places an additional printed
        # paragraph marker between the section number and its body.  The
        # ordinary inline-margin grammar intentionally does not guess through
        # that shape; the geometry+TOC path does.
        "Definitions.\n2. a. In this Act, prescribed means prescribed by rules.",
        "3. The Authority is established.", "4. The Authority may act.",
        "5. The prescribed procedure applies.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
        block["x0"], block["x1"] = 161.0, 520.0
    for index in range(7, len(bs)):
        bs[index]["x0"] = 214.0
    bs[8]["x0"], bs[8]["x1"] = 110.0, 526.0

    seg = segment(bs, split_fused_margins=True)
    section_two = next(node for node in seg.root.children if node.label == "2")
    assert seg.missing == []
    assert seg.marginal_notes_split == 1
    assert section_two.marginal_note == "Definitions."


def test_fusion_does_not_split_a_later_schedule_label_already_in_body():
    """Geometry cannot override an already-satisfied contents citation."""
    bs = blocks(
        "CONTENTS",
        "1. Short title.", "2. Definitions.", "3. Authority.",
        "4. Powers.", "5. Procedure.",
        "It is hereby enacted as follows:",
        "1. This Act may be called the Example Act.",
        "2. In this Act, prescribed means prescribed by rules.",
        "3. The Authority is established.", "4. The Authority may act.",
        "5. The prescribed procedure applies.",
        "SCHEDULE\nCHARITABLE PURPOSES",
        "Definitions. 2. Education and public welfare.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else (2 if index <= 11 else 3)
        block["x0"], block["x1"] = 161.0, 520.0
    for index in range(7, 12):
        bs[index]["x0"] = 214.0
    bs[-1]["x0"], bs[-1]["x1"] = 110.0, 526.0

    seg = segment(bs, split_fused_margins=True)
    assert seg.missing == []
    assert seg.marginal_notes_split == 0
    assert [node.label for node in seg.root.children
            if node.kind == "section"] == ["1", "2", "3", "4", "5"]


def test_toc_reconciliation_accepts_only_unambiguous_dash_typography():
    """Official editions interchange 53-A, 53A and 53 A, but decimal dots
    carry legal structure and must not be erased.  Ambiguous variants fail
    closed rather than choosing a provision.
    """
    matched_toc, matched_body = _reconcile_label_sets(
        {"53-A", "2.1"}, {"53A", "21"})
    assert matched_toc == {"53-A"}
    assert matched_body == {"53A"}

    matched_toc, matched_body = _reconcile_label_sets(
        {"5-A", "5A"}, {"5 A"})
    assert matched_toc == set()
    assert matched_body == set()


def test_toc_reconciliation_accepts_only_unambiguous_numeric_zero_padding():
    """A contents display label ``01`` denotes body section ``1``.

    The exact printed forms remain distinct evidence.  If both forms occur in
    the contents, normalization must fail closed instead of linking two rows to
    one citable provision.
    """
    matched_toc, matched_body = _reconcile_label_sets(
        {"01", "02", "10"}, {"1", "2", "10"})
    assert matched_toc == {"01", "02", "10"}
    assert matched_body == {"1", "2", "10"}

    matched_toc, matched_body = _reconcile_label_sets({"01", "1"}, {"1"})
    assert matched_toc == {"1"}
    assert matched_body == {"1"}


def test_toc_entry_links_across_dash_typography_without_relabelling_body():
    bs = blocks(
        "CONTENTS",
        "1-A. First.", "2-A. Second.", "3-A. Third.", "4-A. Fourth.",
        "5-A. Fifth.",
        "It is hereby enacted as follows:",
        "1A. First. Body one.", "2A. Second. Body two.",
        "3A. Third. Body three.", "4A. Fourth. Body four.",
        "5A. Fifth. Body five.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
    seg = segment(bs)
    assert seg.toc_found
    assert seg.missing == []
    assert seg.extra == []
    assert [entry["method"] for entry in seg.toc_entries] == [
        "label_typography",
    ] * 5
    assert [entry["node"].label for entry in seg.toc_entries] == [
        "1A", "2A", "3A", "4A", "5A",
    ]


def test_repeated_order_rule_labels_link_by_unique_printed_heading():
    """CPC's contents list repeats rule labels under many Orders.  Every
    occurrence must link to its own rule; mapping all ``6`` entries to section
    6 would make the row-level completeness gate pass dishonestly.
    """
    bs = blocks(
        "CONTENTS",
        "ORDER I", "1. Joinder of parties.", "2. Separate trials.",
        "ORDER II", "1. Agent to accept service.", "2. Appearance date.",
        "It is hereby enacted as follows:",
        "ORDER I", "1. Joinder of parties.– Operative text one.",
        "2. Separate trials.– Operative text two.",
        "ORDER II", "1. Agent to accept service.– Operative text three.",
        "2. Appearance date.– Operative text four.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 6 else 2
    seg = segment(bs)
    assert seg.toc_found
    assert seg.missing == []
    assert [entry["method"] for entry in seg.toc_entries] == [
        "label_heading_exact",
    ] * 4
    linked = [entry["node"] for entry in seg.toc_entries]
    assert len({id(node) for node in linked}) == 4
    expected = ["Joinder of parties", "Separate trials",
                "Agent to accept service", "Appearance date"]
    assert all((node.heading or node.text).startswith(heading)
               for node, heading in zip(linked, expected))


def test_repeated_order_rule_with_omitted_toc_heading_links_by_bounded_order():
    bs = blocks(
        "CONTENTS",
        "ORDER I", "1. First alpha.", "2. Second alpha.", "3. Third alpha.",
        "ORDER II", "1. First beta.", "2. Omitted.", "3. Third beta.",
        "It is hereby enacted as follows:",
        "ORDER I", "1. First alpha.– Text.", "2. Second alpha.– Text.",
        "3. Third alpha.– Text.",
        "ORDER II", "1. First beta.– Text.",
        "2. Historical heading.– * * * *", "3. Third beta.– Text.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 8 else 2
    seg = segment(bs)
    assert seg.toc_found
    assert seg.missing == []
    assert seg.toc_entries[4]["label"] == "2"
    assert seg.toc_entries[4]["method"] == "label_order"
    assert seg.toc_entries[4]["node"].text.startswith("Historical heading")


def test_section_toc_entry_never_links_to_same_numbered_subsection():
    """A missing section 3 is not repaired by subsection (3) of section 1."""
    bs = blocks(
        "CONTENTS", "1. First.", "2. Second.", "3. Missing privilege.",
        "4. Fourth.",
        "It is hereby enacted as follows:",
        "1. First. (1) Opening text. (3) It commences at once.",
        "2. Second. Operative text.",
        "4. Fourth. Operative text.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 4 else 2
    seg = segment(bs)
    entry = next(item for item in seg.toc_entries if item["label"] == "3")
    assert entry["node"] is None
    assert seg.missing == ["3"]


def test_resolved_toc_entry_backfills_marginal_section_heading():
    bs = blocks(
        "CONTENTS", "1. Short title and commencement.", "2. Definitions.",
        "It is hereby enacted as follows:",
        "1. (1) This Act may be called the Example Act.",
        "2. In this Act, prescribed means prescribed by rules.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 2 else 2
    seg = segment(bs)
    sections = [node for node in seg.flatten() if node.kind == "section"]
    assert sections[0].heading == "Short title and commencement."
    assert sections[1].heading == "Definitions."


def test_repeated_schedule_label_links_with_following_marginal_heading():
    bs = blocks(
        "CONTENTS",
        "1. Main opening.", "2. Main definitions.", "3. Main duty.",
        "SCHEDULE REGULATIONS OF THE BOARD",
        "1. Powers and duties of the Chairman.",
        "2. Powers and duties of the Secretary.",
        "3. Powers and duties of the Controller of Examinations.",
        "It is hereby enacted as follows:",
        "1. Main opening. Operative text.",
        "2. Main definitions. Operative text.",
        "3. Main duty. Operative text.",
        "SCHEDULE REGULATIONS OF THE BOARD",
        "1. The Chairman shall exercise control over the office.",
        "2. The Secretary shall administer the office.",
        "3. The Controller shall control examinations.",
        "Powers and duties of the Controller of Examinations.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 7 else (2 if index <= 11 else 3)
        block["x0"], block["x1"] = 108.0, 516.0
        block["y0"], block["y1"] = float(index * 20), float(index * 20 + 18)
    bs[-2]["y0"], bs[-2]["y1"] = 100.0, 130.0
    bs[-1]["x0"], bs[-1]["x1"] = 523.0, 591.0
    bs[-1]["y0"], bs[-1]["y1"] = 100.0, 135.0
    seg = segment(bs)
    schedule_three = seg.toc_entries[-1]
    assert schedule_three["node"] is not None
    assert schedule_three["node"].kind == "clause"
    assert schedule_three["node"].heading == (
        "Powers and duties of the Controller of Examinations."
    )
    assert schedule_three["method"] == "label_heading_exact"


def test_compound_schedule_toc_rows_link_to_their_subsections():
    bs = blocks(
        "CONTENTS", "1. Main opening.", "4. Main constitution.",
        "SCHEDULE REGULATIONS OF THE BOARD",
        "1. Chair duty.",
        "4(1). Constitution of the Academic Committee.",
        "4(2). Term of office of members of the Academic Committee.",
        "4(3). Quorum for the meeting.",
        "It is hereby enacted as follows:",
        "1. Main opening. Operative text.",
        "4. Main constitution. (1) Main member text. (2) Main term text. (3) Main quorum text.",
        "SCHEDULE REGULATIONS OF THE BOARD",
        "1. Chair duty. Schedule text.",
        "4. (1) The Academic Committee shall consist of members. Constitution of the Academic Committee.",
        "(2) The members shall hold office for two years. Term of office of members of the Academic Committee.",
        "(3) The quorum shall be one third. Quorum for the meeting.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 7 else (2 if index <= 10 else 3)
    seg = segment(bs)
    compounds = [entry for entry in seg.toc_entries if "(" in entry["label"]]
    assert [entry["label"] for entry in compounds] == ["4(1)", "4(2)", "4(3)"]
    assert all(entry["node"] is not None for entry in compounds)
    assert all(entry["node"].kind == "subsection" for entry in compounds)
    assert all(entry["node"].first_page == 3 for entry in compounds)


def test_repeated_section_label_does_not_reuse_unrelated_schedule_clause():
    """One schedule clause 11 may satisfy its own contents row, but cannot
    also conceal a missing section 11 in the principal Act.
    """
    bs = blocks(
        "CONTENTS", "1. Prior.", "2. Meetings of the Authority.",
        "3. Following.", "ORDER I", "2. Amendment of section 24.",
        "It is hereby enacted as follows:",
        "1. Prior. Text.", "3. Following. Text.",
        "ORDER I", "2. Amendment of section 24. Schedule text.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
    seg = segment(bs)
    twos = [item for item in seg.toc_entries if item["label"] == "2"]
    assert twos[0]["node"] is None
    assert twos[1]["node"] is not None
    assert twos[1]["node"].kind == "clause"
    assert seg.missing == ["2"]


def test_numbered_toc_schedule_rows_link_to_distinct_schedule_containers():
    bs = blocks(
        "CONTENTS", "1. First rule.", "2. Second rule.",
        "3. Schedule-I (Categories of waste).",
        "4. Schedule-II (Container label).",
        "It is hereby enacted as follows:",
        "1. First rule. Operative text.",
        "2. Second rule. Operative text.",
        "SCHEDULE I (see rule 1) CATEGORIES OF WASTE",
        # The prior schedule's last bullet has no terminal punctuation, but a
        # separately printed TOC identity still proves the new-page heading.
        "1. Pathological waste",
        "SCHEDULE II", "LABEL FOR WASTE CONTAINERS",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 4 else (2 if index <= 9 else 3)
    seg = segment(bs)
    schedule_entries = [
        entry for entry in seg.toc_entries if entry["kind"] == "schedule"
    ]
    assert [entry["method"] for entry in schedule_entries] == [
        "schedule_identity", "schedule_identity",
    ]
    assert [entry["node"].label for entry in schedule_entries] == [
        "SCHEDULE I", "SCHEDULE II",
    ]
    assert len({id(entry["node"]) for entry in schedule_entries}) == 2


def test_unnumbered_schedule_links_by_exact_rule_reference():
    """A numbered TOC row is not the schedule's legal label. Where neither
    side prints an ordinal, the same explicit rule reference plus uniqueness
    proves the link; a generic Schedule heading alone does not.
    """
    bs = blocks(
        "CONTENTS",
        "1. First rule.", "2. Second rule.", "3. Third rule.",
        "4. SCHEDULE- Under Rule -3—PART-I.", "5. PART-II",
        "It is hereby enacted as follows:",
        "1. First rule. Operative text.",
        "2. Second rule. Operative text.",
        "3. Third rule. Operative text.",
        "Schedule\n(Under Rule 3)", "PART-I", "First table text.",
        "PART-II", "Second table text.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else (2 if index <= 12 else 3)
    seg = segment(bs)
    schedule_entry = next(
        entry for entry in seg.toc_entries if entry["kind"] == "schedule"
    )
    part_two = next(
        entry for entry in seg.toc_entries if entry["kind"] == "part"
    )
    assert schedule_entry["method"] == "schedule_rule_reference"
    assert schedule_entry["node"].kind == "schedule"
    assert part_two["method"] == "part_identity"
    assert part_two["node"].kind == "part"
    assert part_two["node"].parent is schedule_entry["node"]
    assert seg.missing == []


def test_standalone_schedule_after_notification_body_opens_without_toc():
    """An embedded notification span need not repeat the package contents.

    Punjab's minimum-wage package prints the second notification's sections
    2--7, its departmental signature, and then an uppercase ``SCHEDULE`` whose
    first industry item shares the same extracted block.  The explicit display
    heading is source evidence; its numbered wage-table rows are clauses of the
    schedule, not hundreds of competing sections of the notification.
    """
    seg = segment(blocks(
        "2. Definitions apply to this notification.",
        "3. Minimum wages shall be paid.",
        "4. Existing favourable terms continue.",
        "5. The earlier notification is superseded.",
        "6. This notification applies to the listed industries.",
        "7. This notification comes into force on 1 July 2013.",
        "SECRETARY\nGOVERNMENT OF THE PUNJAB",
        "SCHEDULE\n\n1. Applicable to workers employed in manufacturing of "
        "Body Building Auto Vehicles Industry.",
        "1. Assistant Manager\n2. Accountant\n3. Foreman",
        "2. Applicable to workers employed in the Bicycle Industry.",
    ), detect_contents=False)
    top_sections = [node.label for node in seg.root.children
                    if node.kind == "section"]
    schedules = [node for node in seg.root.children
                 if node.kind == "schedule"]
    assert top_sections == ["2", "3", "4", "5", "6", "7"]
    assert len(schedules) == 1
    assert schedules[0].label == "SCHEDULE"
    schedule_rows = schedules[0].children
    assert schedule_rows
    assert all(node.kind == "clause" for node in schedule_rows)
    assert [node.label for node in schedule_rows] == ["1", "1", "2", "3", "2"]


def test_source_review_can_force_a_distant_package_contents_row():
    """A package TOC row may belong to an Act embedded many pages later."""
    bs = blocks(
        "1. Short title. 2. Definitions. 3. Levy. 4. Registration.",
        "It is hereby enacted as follows:",
        "1. Short title. This Act may be called the Tobacco Act.",
        "2. Definitions. In this Act, tobacco means tobacco leaf.",
        "3. Levy. A duty shall be levied.",
        "4. Registration. Every unit shall register.",
    )
    bs[0]["page_no"] = 1
    for block in bs[1:]:
        block["page_no"] = 14
    ordinary = segment(bs)
    forced = segment(bs, force_opening_contents=True)
    assert not ordinary.toc_found
    assert forced.toc_found
    assert forced.missing == []
    assert [node.label for node in forced.root.children
            if node.kind == "section"] == ["1", "2", "3", "4"]


def test_unlisted_schedule_without_signature_can_return_to_main_rules():
    """A schedule inside a long rules compendium is not necessarily the tail."""
    seg = segment(blocks(
        "Rule 2. Opening rule.", "Rule 3. Next rule.", "Rule 4. Next rule.",
        "Rule 5. Next rule.", "Rule 6. Next rule.", "Rule 7. Rule before schedule.",
        "SCHEDULE I\n1. First scheduled form.",
        "2. Second scheduled form.",
        "CHAPTER 45\nWARDER ESTABLISHMENT",
        "Rule 8. Main rules resume after the schedule.",
    ), detect_contents=False)
    schedules = [node for node in seg.flatten() if node.kind == "schedule"]
    assert len(schedules) == 1
    assert all(node.kind == "clause" for node in schedules[0].children)
    resumed = [node for node in seg.flatten()
               if node.kind == "section" and node.label == "8"]
    assert len(resumed) == 1
    assert resumed[0].parent is not schedules[0]


def test_rule_resumption_baseline_comes_from_source_not_parser_state():
    """An earlier false auxiliary state must not poison a later resumption.

    Punjab Prisons Rules contains editorial material that can keep the parser
    inside an auxiliary container even while the source continues printing
    explicit ``Rule N`` blocks.  When a later genuine schedule ends, its next
    Rule must be compared with the source sequence before that schedule, not a
    counter that stopped changing when the earlier container opened.
    """
    seg = segment(blocks(
        "Rule 63. Earlier enacted rule.",
        "Rule 64. Last rule reliably classified before editorial material.",
        "SCHEDULE\n1. Editorial material begins.",
        "Rule 1105. Source still prints an explicit rule prefix.",
        "Rule 1106. The rule immediately before the inserted schedule.",
        "SCHEDULE I\n1. First scheduled form.",
        "2. Second scheduled form.",
        "Rule 1107. Main rules resume after the inserted schedule.",
    ), detect_contents=False)
    resumed = [node for node in seg.flatten()
               if node.kind == "section" and node.label == "1107"]
    assert len(resumed) == 1, "; ".join(
        f"{node.kind}:{node.label}@{node.parent.kind if node.parent else '-'}"
        for node in seg.flatten()
    )
    assert resumed[0].parent.kind != "schedule"


def test_short_colon_heading_introduces_the_following_rule():
    """A display heading ending in a colon is not unfinished legal prose.

    Punjab Prisons Rules prints hundreds of marginal/display headings followed
    by ``Rule N``.  The line-wrapped cross-reference guard must still catch
    prose ending ``mentioned in column No. 2 of / Rule 21``, but it must not
    absorb an enacted rule into a short heading such as this one.
    """
    seg = segment(blocks(
        "CHAPTER-28\nDiscipline and daily routine:",
        "Discipline and movements of prisoners:",
        "Rule 657. Prisoners shall remain under discipline and control.",
    ), detect_contents=False)
    rules = [node for node in seg.flatten()
             if node.kind == "section" and node.label == "657"]
    assert len(rules) == 1
    assert rules[0].text.startswith("Prisoners shall remain")


def test_trailing_display_heading_in_prior_rule_introduces_next_rule():
    """A PDF block can end the prior rule and append the next marginal title."""
    seg = segment(blocks(
        "Rule 663. Prisoners shall obey officers and visitors.\n"
        "Distribution into work parties:",
        "Rule 664. (i) After breakfast, prisoners shall form work parties.",
    ), detect_contents=False)
    rules = [node for node in seg.root.children if node.kind == "section"]
    assert [node.label for node in rules] == ["663", "664"]


def test_monotonic_rule_prefix_outvotes_unpunctuated_marginal_heading():
    """A printed consecutive Rule is stronger than unfinished punctuation.

    Punjab Prisons Rules frequently ends one extracted block with a marginal
    heading that has no colon or full stop. Punctuation alone calls that block
    unfinished and absorbs the next enacted Rule. The explicit 77 -> 78 source
    sequence proves the boundary without guessing from heading prose.
    """
    seg = segment(blocks(
        "Rule77. The clothing shall be washed and safely stored.",
        "Disposal of cash property of the prisoners",
        "Rule 78. The cash property shall be paid on release.",
    ), detect_contents=False)
    rules = [node for node in seg.root.children if node.kind == "section"]
    assert [node.label for node in rules] == ["77", "78"]
    assert "cash property" in rules[-1].text.lower()


def test_explicit_rule_occurrence_beats_bare_repeated_numeric_row():
    """Without a TOC, keep the source-labelled Rule rather than a bare row."""
    seg = segment(blocks(
        "678. A bare numbered table or list row.",
        "Rule 677. Prisoners may take exercise on holidays.",
        "Games",
        "Rule 678. Prisoners may play indoor and outdoor games.",
    ), detect_contents=False)
    citable = [node for node in seg.root.children
               if node.kind == "section" and node.label == "678"]
    demoted = [node for node in seg.root.children
               if node.kind == "clause" and node.label == "678"]
    assert len(citable) == 1
    assert "prisoners may play" in citable[0].text.lower()
    assert len(demoted) == 1
    assert "bare numbered" in (demoted[0].heading or "").lower()


def test_toc_proves_inline_unpunctuated_section_but_bare_table_row_fails():
    bs = blocks(
        "CONTENTS",
        "1. First.", "2. Second.", "3. Efficiency and Discipline.",
        "4. Fourth.", "5. Fifth.",
        "It is hereby enacted as follows:",
        "1. First. Text.",
        "2. Second. Text.\n\n"
        "3  Efficiency and Discipline: The authority may impose penalties.",
        "4. Fourth. Text.", "5. Fifth. Text.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
    seg = segment(bs)
    section = next(
        node for node in seg.root.children
        if node.kind == "section" and node.label == "3"
    )
    assert section.heading == "Efficiency and Discipline."
    assert "may impose penalties" in section.text
    assert seg.missing == []

    # Same typography without ordered TOC/heading corroboration is merely a
    # table row and must not be promoted to a section.
    no_toc = segment(blocks("1. First. Text.", "13  Unrelated table value"))
    assert [node.label for node in no_toc.root.children
            if node.kind == "section"] == ["1"]


def test_line_wrapped_rule_cross_reference_does_not_steal_toc_entry():
    bs = blocks(
        "CONTENTS",
        "1. Short title.", "2. Definitions.", "3. Powers.",
        "4. Procedure.", "5. Appeal.", "21. Appellate authority.",
        "It is hereby enacted as follows:",
        "1. Short title. Text.",
        "2. Definitions. (a) Appellate Authority means the authority in",
        "Rule 21.\n(b) Other definition means prescribed.",
        "3. Powers. Text.", "4. Procedure. Text.", "5. Appeal. Text.",
        "21. Appellate authority. A person may appeal.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 6 else 2
    seg = segment(bs)
    twenty_ones = [
        node for node in seg.root.children
        if node.kind == "section" and node.label == "21"
    ]
    assert len(twenty_ones) == 1
    assert "person may appeal" in twenty_ones[0].text.lower()
    definitions = next(
        node for node in seg.root.children
        if node.kind == "section" and node.label == "2"
    )
    definition_text = " ".join(
        [definitions.text] + [child.text for child in definitions.children]
    )
    assert "Rule 21" in definition_text


def test_toc_and_marginal_heading_promote_parenthesized_top_level_label():
    """The Refugees Act prints section 4 as ``(4)`` between sections 3 and 5.
    A matching detached marginal heading plus printed TOC order proves that it
    is the next section, not subsection (4) of section 3.
    """
    bs = blocks(
        "CONTENTS",
        "1. First.", "2. Second.", "3. Third.", "4. Registration of claims.",
        "5. Powers.",
        "It is hereby enacted as follows:",
        "1. First. Enacted text.", "2. Second. Enacted text.",
        "3. Third. Enacted text.",
        "Registration of claims.", "(4) (i) A refugee may submit a claim.",
        "5. Powers. The officer shall exercise the prescribed powers.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
    seg = segment(bs)
    assert seg.toc_found
    assert seg.missing == []
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        "1", "2", "3", "4", "5",
    ]


def test_internal_section_before_fused_amendment_marker_is_subdivided():
    pieces = subdivide(
        "(3) Existing subsection text.\n"
        "7. 1[(1) The Relief Commissioner may delegate his powers]."
    )
    assert pieces[-1].lstrip().startswith("7.")


def test_internal_hyphenated_section_after_amendment_marker_is_subdivided():
    text = (
        "1[19-A. Sumptuary allowance. Existing enacted text.]\n"
        "3[19-B. Equipment allowance.– New enacted text.]"
    )
    pieces = subdivide(text)
    assert len(pieces) == 2
    assert classify(pieces[1])[:2] == ("section", "19-B")


def test_quoted_section_after_amendment_marker_is_classified():
    result = classify(
        '1[“6-A. Fund.– (1) There shall be established a fund.'
    )
    assert result is not None
    assert result[:2] == ("section", "6-A")


def test_new_section_after_prior_numbered_sentence_is_not_a_dotted_label():
    pieces = subdivide(
        "(2) The public servants provision refers to section 21 of the Code, "
        "1860.\n\n8.\n(1) An order is subject to revision."
    )
    assert any(piece.lstrip().startswith("8.") for piece in pieces)


def test_year_order_citation_on_wrapped_line_is_not_a_division():
    """A cited Order's year is prose, not a new structural container.

    PyMuPDF can place the cited title at the start of a new extracted line even
    though it remains inside a definition.  The inner-division splitter must
    preserve that definition as one unit.
    """
    text = (
        "(g) Facilities means hospitals seized under the United Nations "
        "(Security Council) Act 1948 read with the United Nations Security "
        "Council (Freezing and Seizure)\n"
        "Order 2019, published in the Gazette of Pakistan on 4 March 2019."
    )
    assert subdivide(text) == [text]


def test_bracketed_deleted_section_word_form_is_classified():
    text = "1[Deleted.]\n1[Section 10.\nPrimary Education Surcharge —Deleted\n]"
    pieces = subdivide(text)
    result = _classify_body(pieces[-1], {"10": "Primary Education Surcharge Deleted"})
    assert result is not None
    assert result[:2] == ("section", "10")


def test_bracketed_inserted_hyphenated_section_is_classified():
    result = _classify_body(
        "7[3-A]. Notices.- For the removal of doubts, notice shall be given.",
        {"3-A": "Notices."},
    )
    assert result is not None
    assert result[:2] == ("section", "3-A")


def test_amending_act_section_with_marginal_heading_is_not_a_footnote():
    """An amending Act's operative sections read exactly like amendment notes.

    In the West Pakistan Hill Tract Improvement Act every amending section says
    "In section N of the said Act ... shall be deemed to be substituted" -- the
    punctuated-amendment pattern's own shape. Demoting one to apparatus leaves
    the marginal heading printed beside it owning no provision, and the writer
    then strands its characters as 'unassigned' (C4/C5). Where the walk has
    already matched that marginal heading to a printed contents entry and proved
    it prints in its own column, that evidence outranks the text shape.
    """
    bs = blocks(
        "CONTENTS",
        "1. Short title and commencement.",
        "2. Definitions.",
        "3. Constitution of the Trust.",
        "4. Amendment of section 15.",
        "5. Amendment of section 17.",
        "It is hereby enacted as follows:",
        "1. (1) This Act may be called the Example Amendment Act.",
        "2. In this Act, prescribed means prescribed by rules.",
        "3. The Trust shall be constituted as provided in this Act.",
        "Amendment of section 15.",
        "4.\nIn section 15 of the said Act, for the word and figures \"and 24\" "
        "the figures, word and letter \"24 and 24-A\" preceded by a comma, "
        "shall be deemed to be substituted.",
        "Amendment of section 17.",
        "5.\nIn sub-section (3) of section 17 of the said Act, after the "
        "figures \"24\" the words shall be deemed to be inserted.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 5 else 2
        block["x0"], block["x1"] = 86.0, 494.0
        block["y0"], block["y1"] = float(index * 40), float(index * 40 + 30)
    # Both marginal headings print in the narrow right-hand column, each
    # vertically aligned with the section it heads.
    for marginal, body in ((10, 11), (12, 13)):
        bs[marginal]["x0"], bs[marginal]["x1"] = 501.0, 564.0
        bs[marginal]["y0"] = bs[body]["y0"]
        bs[marginal]["y1"] = bs[body]["y1"]

    seg = segment(bs)
    assert seg.toc_found, "fixture must print a contents list"
    roles = {bid: role for bid, (role, _node) in seg.block_roles.items()}
    assert roles[11] != "footnote", "the operative section became apparatus"

    # Every block whose role must own a provision has one. That is what keeps
    # the marginal heading's characters reachable.
    stranded = [bid for bid, (role, node) in seg.block_roles.items()
                if node is None
                and role in ("body", "heading", "schedule_row", "preamble")]
    assert stranded == [], stranded

    labels = [node.label for node in seg.flatten() if node.kind == "section"]
    assert "4" in labels, labels


def test_numeric_table_does_not_hang_the_footnote_marker_test():
    r"""A contribution table must not take exponential time to reject.

    Document 3912, the Punjab Contributory Provident Fund Rules, carries an
    808-character table of 132 numeric lines. The footnote-marker test used one
    pattern whose leading ``\s*`` and repeated ``\n\s*`` could both claim the
    same newline, so proving the table is NOT a run of markers meant trying
    every way to divide that whitespace. It had not finished after five minutes,
    which made the document impossible to re-segment at all.

    The answer is False -- four-digit rates are not footnote markers -- and the
    check must reach it immediately. The bound is deliberately loose: the point
    is minutes versus milliseconds, not a benchmark.
    """
    import time

    from nizam.corpus.segment import _footnote_markers_only

    rows = []
    for n in range(1, 34):
        rows += [f"{n} ", "", f"{440 + n * 20}  ", f"{640 + n * 20}  ",
                 f"{1020 + n * 10}  ", f"{16 + n % 8} ", "", "20  "]
    table = "\n".join(rows)
    assert sum(1 for line in table.split("\n")
               if line.strip() and len(line.strip()) > 3) >= 30

    started = time.perf_counter()
    result = _footnote_markers_only(table)
    elapsed = time.perf_counter() - started

    assert result is False
    assert elapsed < 1.0, f"took {elapsed:.1f}s -- the pattern is backtracking"


def test_footnote_marker_block_is_still_recognised():
    """The replacement keeps the behaviour the single pattern was written for."""
    from nizam.corpus.segment import _footnote_markers_only

    assert _footnote_markers_only("1.\n2.\n3.") is True
    assert _footnote_markers_only("1\n \n2\n \n3\n") is True
    assert _footnote_markers_only("12:\n13:") is True
    # One line is not a run of markers, and a four-digit number is not one.
    assert _footnote_markers_only("1.") is False
    assert _footnote_markers_only("1.\n1020") is False
    assert _footnote_markers_only("1.\nIn section 15 of the said Act") is False


def test_incomplete_contents_does_not_strip_a_plausible_rule_number():
    """Absence from the contents proves fusion only when the number is implausible.

    The Sindh mining rules print a contents list of 1,2,4,5,6,7,44,45 ... 72 --
    nothing at all between 7 and 44. Rules 21 and 22 are therefore missing from
    it, and reading that absence as superscript fusion stripped them to 1 and 2.
    Rule 22, "Records, and Reporting by Licensee", stopped being citable even
    though page 22 prints it with an ordinary bold heading.

    A number the document's own contents shows to be in range is a provision
    number. A number far outside that range still is not.
    """
    sparse = {label: f"heading {label}" for label in
              ["1", "2", "4", "5", "6", "7"] + [str(n) for n in range(44, 73)]}

    # In range (the contents itself reaches 72) and simply not listed.
    assert _repair_label("21", sparse) == "21"
    assert _repair_label("22", sparse) == "22"
    # Still listed, still untouched.
    assert _repair_label("44", sparse) == "44"


def test_superscript_fusion_is_still_undone_when_the_number_is_implausible():
    """The repair this guard narrows must keep working.

    PyMuPDF glues a footnote marker to the number that follows, so section 366
    carrying footnote 1 arrives as "1366". No statute numbering to 500 has a
    section 1366, and the contents says so.
    """
    dense = {str(n): f"heading {n}" for n in range(1, 501)}
    assert _repair_label("1366", dense) == "366"
    assert _repair_label("1500", dense) == "500"
    # A label the contents does list is never stripped.
    assert _repair_label("366", dense) == "366"


def test_repair_label_without_a_contents_list_changes_nothing():
    assert _repair_label("21", {}) == "21"
    assert _repair_label("1366", {}) == "1366"


def test_marginal_heading_fused_ahead_of_its_section_still_opens_it():
    r"""A heading glued in front of its own section used to delete the section.

    PyMuPDF emits "Repeal.\n27.\n2The Balochistan Education Foundation
    Ordinance, 1994 ... is hereby repealed." as one block, so section 27 was
    appended to section 26 and left the corpus.

    The rule is anchored to the START of a block on purpose. Tried as a general
    internal cut it also fired inside footnote runs, which carry the same
    number-dot-superscript shape, and shredded them into fabricated sections --
    costing one document twenty-one of its twenty-seven.
    """
    pieces = subdivide("Repeal.\n27.\n2The Balochistan Education Foundation "
                       "Ordinance, 1994 (IV of 1994), is hereby repealed.")
    assert len(pieces) == 2, pieces
    opened = classify(pieces[1])
    assert opened is not None and opened[:2] == ("section", "27")

    # A footnote run offers the same shape and must stay whole.
    assert len(subdivide("1Subs. by Act No. XX of 1972, ss. 2 and 3. \n"
                         "2Subs. by A. O., 1937.")) == 1


def test_a_detached_heading_never_loses_its_provision():
    """A heading owning nothing is refused by the writer, so it must own something.

    291 heading blocks across 71 documents were latent C5 failures: their body
    never became a provision, legal_write refused to store a heading without
    one, and their characters fell out of the ledger the moment the document was
    replayed. The words are printed on the page and belong to the provision they
    head, so a detached heading takes the node of the next block that has one.
    """
    bs = blocks(
        "CONTENTS", "1. Short title.", "2. Definitions.",
        "It is hereby enacted as follows:",
        "1. Short title. This Act may be called the Example Act.",
        "Definitions.",
        "2. In this Act, prescribed means prescribed by rules.",
    )
    for index, block in enumerate(bs):
        block["page_no"] = 1 if index <= 2 else 2
    seg = segment(bs)
    stranded = [bid for bid, (role, node) in seg.block_roles.items()
                if node is None
                and role in ("body", "heading", "schedule_row", "preamble")]
    assert stranded == [], stranded
