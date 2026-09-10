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
    assert not seg.toc_found
    assert seg.body_starts_page == 1
    assert [n.label for n in seg.root.children if n.kind == "section"][:20] == [
        str(n) for n in range(1, 21)]


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
    assert seg.toc_found
    assert seg.body_starts_page == 1
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        str(n) for n in range(1, 9)]
    assert seg.repeated_labels_demoted == 0


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
