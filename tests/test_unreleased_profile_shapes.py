"""Smaller `unreleased-v1` rules: each fires only under the profile.

docs/SEGMENTATION-PROFILES.md. Each case is a printed shape read from a
blocked document's page; the default parser keeps its behaviour for all of
them (released trees are never re-parsed under a profile).
"""
from __future__ import annotations

import contextlib

from nizam.corpus import segment as S


@contextlib.contextmanager
def profile(name: str):
    token = S._ACTIVE_PROFILE_RULES.set(S.SEGMENTATION_PROFILES[name])
    try:
        yield
    finally:
        S._ACTIVE_PROFILE_RULES.reset(token)


def test_first_statutes_heading_opens_a_schedule_only_under_the_profile():
    # doc 2922 p27: "THE FIRST STATUTES" then "(see section 34)"
    assert S.classify("THE FIRST STATUTES") is None
    with profile("unreleased-v1"):
        assert S.classify("THE FIRST STATUTES")[:2] == ("schedule", "THE FIRST STATUTES")
        assert S.classify("FIRST STATUTES (See Section 20)")[0] == "schedule"
        # prose about the statutes is not a heading
        assert S.classify("The First Statutes shall be deemed to have been made") is None


def test_lowercase_explanation_word_is_prose_under_the_profile():
    # doc 1021 s.2(b): "... the following / explanation shall be inserted, namely:"
    line = "explanation shall be inserted, namely:"
    assert S.classify(line)[0] == "explanation"
    with profile("unreleased-v1"):
        assert S.classify(line) is None
        assert S.classify("Explanation.- For the purposes of this section")[0] == "explanation"


def test_heading_guess_does_not_end_at_an_abbreviation_or_enact():
    # doc 1021 s.2 "In the 8[..] Ordinance No. V of 1982, ..."; doc 1065 s.2
    toc = "Amendment of section 4 of Ordinance No. V of 1982"
    rest = "In the 8[Khyber Pakhtunkhwa] Ordinance No. V of 1982, in sub-section (1)"
    assert S._split_heading(rest, toc)[0] == "In the 8[Khyber Pakhtunkhwa] Ordinance No"
    with profile("unreleased-v1"):
        assert S._split_heading(rest, toc) == (None, rest)
        enacting = "The Gift Tax Act, 1963 (XIV of 1963), is hereby repealed. Repeal of Act XIV of 1963."
        assert S._split_heading(enacting, "Repeal of Act XIV of 1963") == (
            "Repeal of Act XIV of 1963",
            "The Gift Tax Act, 1963 (XIV of 1963), is hereby repealed.")


def test_margin_heading_blocks_need_the_margin_and_the_contents():
    # doc 2386 p15: the next statute's margin heading printed beside the
    # continuation of statute 2(3)
    line = "x" * 70
    body = [
        {"id": 1, "page_no": 15, "text": line, "x0": 72.0, "x1": 460.0},
        {"id": 2, "page_no": 15, "text": line, "x0": 72.0, "x1": 461.0},
        {"id": 3, "page_no": 15, "text": "Functions of the Board of Faculty.",
         "x0": 470.0, "x1": 560.0},
        {"id": 4, "page_no": 15, "text": "one-half of the total number of members.",
         "x0": 72.0, "x1": 300.0},
        # in the margin but naming nothing the contents lists
        {"id": 5, "page_no": 15, "text": "Some other words.", "x0": 470.0, "x1": 560.0},
        # the contents heading, but in the text column
        {"id": 6, "page_no": 15, "text": "Selection Board.", "x0": 72.0, "x1": 200.0},
    ]
    headings = ["Functions of the Board of Faculty.", "Selection Board."]
    assert S._margin_heading_blocks(body, headings) == {3}
    assert "margin_heading_blocks" in S.SEGMENTATION_PROFILES["unreleased-v2"]
    assert "margin_heading_blocks" not in S.SEGMENTATION_PROFILES["unreleased-v1"]
    assert S.SEGMENTATION_PROFILES["unreleased-v1"] < S.SEGMENTATION_PROFILES["unreleased-v2"]


def test_false_contents_rows():
    # docs 264, 2027 (contents-page footnotes), 2215 and 1142 (title lines)
    for heading in ("Subs Vide the Khyber Pakhtunkhwa Act.IV of 2011.",
                    "*Rep. by the Repealing Act 1938 (I of 1938), s. 2 and Schedule.",
                    "No. XXIII of 1918", "(W. P. Ord. No. XXXII of 1960)"):
        assert S._false_contents_row({"heading": heading}), heading
    # a real repealed or omitted entry, and ordinary headings, stay rows
    for heading in ("Rep. by the Repealing Act, 1938.", "[Omitted]", "*[Omitted]",
                    "Short title and commencement.", "Amendment of Act No. V of 1982."):
        assert not S._false_contents_row({"heading": heading}), heading


def test_download_stamp_and_page_numbers_are_furniture():
    body = [{"id": 1, "page_no": 3, "text": "12. 6[Omitted]"},
            {"id": 2, "page_no": 3, "text": "____________ \n"},
            {"id": 3, "page_no": 3, "text": "Date: 05-08-2024 \n"},
            {"id": 4, "page_no": 3, "text": "See Date: 05-08-2024 for the notice"}]
    assert S._download_stamp_blocks(body) == {2, 3}
    assert "download_stamp_furniture" in S.SEGMENTATION_PROFILES["unreleased-v2"]
    assert "page_number_furniture" in S.SEGMENTATION_PROFILES["unreleased-v2"]


def test_lowercase_heading_split_only_under_v2():
    # doc 2622 p4 and doc 3635 p8
    block = ("8. Bar of jurisdiction. No court shall grant any injunction under this "
             "Ordinance. \n \n9. indemnity. No suit or other legal proceeding shall lie.")
    assert [p[:2] for p in S.subdivide(block)] == ["8."]
    with profile("unreleased-v2"):
        assert [p[:2] for p in S.subdivide(block)] == ["8.", "9."]
        tail = ("show cause against the enhancement of the penalty. \n \n11. \n \n"
                "repeal.— the efficiency and discipline rules in force here before")
        assert any(p.startswith("11.") for p in S.subdivide(tail))
        # a wrapped sentence that happens to start a line with a number stays
        wrapped = "the amount specified in section\n9. and the fine shall be paid"
        assert len(S.subdivide(wrapped)) == 1


def test_fuzzy_printed_heading_only_under_v2():
    # doc 3635 p3 "3. Ground of penalty.-- Any one ..." / contents "Grounds of penalty."
    rest = "Ground of penalty.-- Any one or more penalties may be imposed"
    with profile("unreleased-v1"):
        assert S._split_heading(rest, "Grounds of penalty.")[1].startswith("Ground of")
    with profile("unreleased-v2"):
        assert S._split_heading(rest, "Grounds of penalty.") == (
            "Ground of penalty", "Any one or more penalties may be imposed")


def test_quoted_appendix_letter_only_under_v2():
    # doc 2019 p14 "APPENDIX ―A‖" (printer's quotes decoded as U+2015/U+2016)
    assert S.classify(" APPENDIX ―A‖ ")[:2] == ("appendix", "APPENDIX")
    with profile("unreleased-v2"):
        assert S.classify(" APPENDIX ―A‖ ")[:2] == ("appendix", "APPENDIX A")
        assert S.classify("ANNEXURE ‘B’ (See rule 4)")[:2] == ("annexure", "ANNEXURE B")


def _cell(block_id, text, y0, x0, x1, page=14):
    return {"id": block_id, "page_no": page, "text": text, "y0": y0, "x0": x0, "x1": x1}


def test_row_aligned_cell_moves_beside_its_row():
    # doc 2019 p14: "Upto 5%" is printed level with row 3 but emitted before it
    long_line = "x" * 70
    blocks = [
        _cell(1, long_line, 88, 180, 470), _cell(2, long_line, 167, 180, 470),
        _cell(3, "2. Sanction and acceptance of Tenders for works by contract.", 357, 78, 363),
        _cell(4, "Upto Rs. 25.0 lacs", 357, 371, 470),
        _cell(5, "Upto 5%", 388, 371, 481),
        _cell(6, "3. Sanction of amount in excess of the sanctioned estimates.", 388, 78, 363),
        _cell(7, long_line, 682, 88, 481),
    ]
    assert [b["id"] for b in S._align_row_cells(blocks)] == [1, 2, 3, 4, 6, 5, 7]


def test_margin_heading_level_with_an_opener_is_not_a_cell():
    # doc 2846 p11: "Group incentive" sits level with "11. (1) In every ..."; a
    # lone opener that spans the column is not a table row
    blocks = [
        _cell(1, "x" * 70, 56, 76, 519, page=11),
        _cell(2, "Group incentive", 635, 458, 544, page=11),
        _cell(3, "11. (1) In every industrial and commercial establishment " + "x" * 30,
              635, 76, 435, page=11),
    ]
    assert S._align_row_cells(blocks) == blocks


def test_column_number_cells():
    row = [_cell(1, "(1) ", 313, 75, 94), _cell(2, "(2) ", 313, 229, 248),
           _cell(3, "(3) ", 313, 411, 430)]
    assert S._column_number_cells(row) == {1, 2, 3}
    # sub-sections on their own lines are not a column-index row
    stacked = [_cell(1, "(1) ", 313, 75, 94), _cell(2, "(2) ", 360, 75, 94)]
    assert S._column_number_cells(stacked) == set()
    # nor is a row that does not count 1, 2, 3 from the left
    assert S._column_number_cells([_cell(1, "(2)", 313, 75, 94),
                                   _cell(2, "(1)", 313, 229, 248)]) == set()


def test_designation_cell_accepts_the_plural():
    # doc 1521 p7 prints "Members" beside rows 2, 6 and 7
    assert S._DESIGNATION_CELL.fullmatch("Members")
    assert S._DESIGNATION_CELL.fullmatch("Chairperson")


def test_decoded_quote_opener_splits_only_under_v2():
    # doc 2019 s.2: "(b) ―Board‖ means ..." inside (a)'s block
    block = ("(a) ―Authority‖ means the Karachi Development Authority; \n \n"
             "(b) ―Board‖ means the Karachi Water and Sewerage Board")
    assert len(S.subdivide(block)) == 1
    with profile("unreleased-v2"):
        assert [p[:3] for p in S.subdivide(block)] == ["(a)", "(b)"]


def test_tight_first_subsection_only_under_v2():
    # doc 1521 p12 "10.(1) Health workers shall ..."
    block = "10.(1) Health workers shall encourage, support and protect breast-feeding."
    assert len(S.subdivide(block)) == 1
    with profile("unreleased-v2"):
        assert [p.strip()[:3] for p in S.subdivide(block)] == ["10.", "(1)"]


def test_wrapped_bracket_reference_only_under_v3():
    # doc 1521 s.17(1); doc 2983 "set out in sub-paragraph / (3) shall participate"
    block = ("17. (1) Any manufacturer who contravenes sub-sections (1) to (7) of section 7, "
             "sub-section \n(1) of section 8, shall be punishable")
    with profile("unreleased-v2"):
        assert any(p.startswith("(1) of section 8") for p in S.subdivide(block))
    with profile("unreleased-v3"):
        assert not any(p.startswith("(1) of section 8") for p in S.subdivide(block))
        # a real opener after a reference word still starts: it is capitalised
        opener = "as provided in sub-section \n(2) The Board shall meet."
        assert any(p.startswith("(2) The Board") for p in S.subdivide(opener))
    assert "wrapped_bracket_reference" not in S.SEGMENTATION_PROFILES["unreleased-v2"]
    assert S.SEGMENTATION_PROFILES["unreleased-v2"] < S.SEGMENTATION_PROFILES["unreleased-v3"]


def test_promised_only_after_restart():
    # doc 2983: sections 1-12, then the Scheme's paragraphs 1-16
    entries = ([{"label": str(n)} for n in range(1, 13)]
               + [{"label": str(n)} for n in range(1, 17)])
    assert S._promised_only_after_restart(entries, "13")
    assert not S._promised_only_after_restart(entries, "12")
    assert not S._promised_only_after_restart(
        [{"label": str(n)} for n in range(1, 17)], "13")


def _block(block_id, text, page, y0, x0=72.0, x1=470.0):
    return {"id": block_id, "text": text, "page_no": page, "y0": y0,
            "x0": x0, "x1": x1, "page_height": 792}


def test_enacting_formula_and_sequential_chapter_open_divisions_under_v2():
    # doc 2019 pp2-4: "CHAPTER - I" after "... enacted as follows :-", and
    # "CHAPTER-III" after s.4(5) printed without its full stop
    blocks = [
        _block(1, "WHEREAS it is expedient to provide for the establishment of a Board;", 1, 100),
        _block(2, "It is hereby enacted as follows :—", 1, 140),
        _block(3, "CHAPTER – I", 1, 170, 226, 308),
        _block(4, "PRELIMNARY", 1, 188, 223, 311),
        _block(5, "1. Short title. This Act may be called the Water Board Act, 1996.", 1, 220),
        _block(6, "CHAPTER—II", 2, 88, 227, 307),
        _block(7, "CONSTITUTION OF THE BOARD", 2, 103, 63, 361),
        _block(8, "2. Board. (1) There shall be a Board. (2) The Secretary shall perform "
                  "such functions as may be assigned by the Board", 2, 133),
        _block(9, "CHAPTER—III", 2, 300, 225, 308),
        _block(10, "APPOINTMENT OF THE MANAGING DIRECTOR", 2, 320, 79, 455),
        _block(11, "3. Managing Director. The Managing Director shall be appointed by "
                   "Government.", 2, 350),
    ]
    def chapters(seg):
        return [n.label for n in seg.flatten() if n.kind == "chapter"]
    assert chapters(S.segment(blocks, profile="default")) == ["II"]
    assert chapters(S.segment(blocks, profile="unreleased-v2")) == ["I", "II", "III"]


def test_shorter_printed_name_closed_by_a_dash():
    # doc 2954 s.1 "Short title.___(1) This Act may be called ..."
    with profile("unreleased-v1"):
        assert S._split_heading("Short title.___(1) This Act may be called the Act",
                                "Short title, commencement") == (
            "Short title", "(1) This Act may be called the Act")
