"""`unreleased-v4` rules (migration 0059).

docs/SEGMENTATION-PROFILES.md. Doc 876 frozen in
tests/fixtures/unreleased-v4-876.json with its page-read overrides; plus the
shape of `paren_amendment_opener` (doc 1563 p4). What is asserted is what the
pages print (renders doc876-p1..p24.png, doc1563-p4.png).
"""
from __future__ import annotations

import contextlib
import json
import re
from functools import lru_cache
from pathlib import Path

from nizam.corpus import segment as S

FIXTURE = Path(__file__).parent / "fixtures" / "unreleased-v4-876.json"


@contextlib.contextmanager
def profile(name: str):
    token = S._ACTIVE_PROFILE_RULES.set(S.SEGMENTATION_PROFILES[name])
    try:
        yield
    finally:
        S._ACTIVE_PROFILE_RULES.reset(token)


@lru_cache(maxsize=None)
def _parse(profile_name: str):
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))["876"]
    return S.segment(case["blocks"], profile=profile_name,
                     structural_overrides=case["structural_overrides"])


def _links(seg):
    out = []
    for entry in seg.toc_entries:
        node = entry["node"]
        parent = node.parent.kind if node is not None and node.parent is not None else None
        out.append((entry["label"], (entry.get("heading") or "")[:20],
                    node.kind if node else None, parent))
    return out


def test_876_bare_number_contents_row_and_statute_links():
    seg = _parse("unreleased-v4")
    links = _links(seg)
    assert len(links) == 37 and all(node for _, _, node, _ in links)
    # the Act's s.11 is "Chancellor."; the statutes' 10 and 11 are schedule rows
    assert ("11", "Chancellor.", "section", "instrument") in links
    assert ("10", "Finance and Planning", "clause", "schedule") in links
    assert ("11", "Functions of the Fin", "clause", "schedule") in links
    chancellor = [n for n in seg.flatten() if n.kind == "section" and n.label == "11"][0]
    assert chancellor.heading.startswith("Chancellor")


def test_876_v3_parse_names_the_wrong_section_11():
    # the defect v4 exists for: under v3 the contents row "11 Chancellor." is
    # unread and the statutes' row 11 names the Act's s.11
    seg = _parse("unreleased-v3")
    act_11 = [n for n in seg.flatten() if n.kind == "section" and n.label == "11"][0]
    assert not act_11.heading.startswith("Chancellor")


def test_paren_amendment_opener_only_under_v4():
    block = ("licensed. Under this ordinance every such crusher shall be operated.\n"
             "4. 1(The authority having power to register a power crusher shall be the "
             "District Officer.)")
    with profile("unreleased-v3"):
        assert not any(p.lstrip().startswith("4.") for p in S.subdivide(block))
    with profile("unreleased-v4"):
        assert any(p.lstrip().startswith("4. 1(The authority") for p in S.subdivide(block))


def test_detached_heading_after_division_leaves_a_bare_row_unnamed():
    # doc 3350 p1: "CHAPTER IV" / "FUNCTIONS OF THE CORPORTION" / "10." --
    # section 10 prints no heading, in the contents or in the text (p6)
    blocks = [{"id": i, "page_no": 1, "text": t} for i, t in enumerate(
        ["9. Delegation of powers ", " CHAPTER IV ", " FUNCTIONS OF THE CORPORTION ",
         "10. ", "Page 1 of 9 "])]
    with profile("unreleased-v3"):
        assert S._detached_heading(blocks, 3) == "FUNCTIONS OF THE CORPORTION"
    with profile("unreleased-v4"):
        assert S._detached_heading(blocks, 3) == ""
    # a number stranded under an ordinary row keeps pattern (x)
    shifted = [{"id": i, "page_no": 7, "text": t} for i, t in enumerate(
        ["110. Approval of Budgets. ", "Accounts. ", "111. ", "Composition of Commission. "])]
    with profile("unreleased-v4"):
        assert S._detached_heading(shifted, 2) == "Accounts."


def test_long_romanettes_only_under_v4():
    # doc 1695 reg 8(2): (xxv), (xxx), (xxxv), (xli) among (i)-(xli)
    labels = ("xxv", "xxx", "xxxv", "xli", "xliv", "xlix")
    with profile("unreleased-v3"):
        for label in labels:
            assert S.classify(f"({label}) shall have full powers") is None
    with profile("unreleased-v4"):
        for label in labels:
            assert S.classify(f"({label}) shall have full powers") == (
                "clause", label, "shall have full powers")
        # the grammar before it is unchanged, and a word is not a numeral
        assert S.classify("(xxiv) shall have")[:2] == ("clause", "xxiv")
        assert S.classify("(xv) shall have")[:2] == ("clause", "xv")
        assert S.classify("(abc) shall have") is None
        assert S.classify("(lxx) shall have") is None


def test_dash_closed_heading_guess_only_without_contents_and_under_v4():
    # doc 1695 p2: no contents list; reg 6's name is closed by ".-"
    rest = ("Recruitment, tenure of office and terms and conditions of service.- "
            "Subject to the Provisions of this Regulation and any other Regulation")
    with profile("unreleased-v3"):
        assert S._split_heading(rest, None)[0] is None
    with profile("unreleased-v4"):
        assert S._split_heading(rest, None) == (
            "Recruitment, tenure of office and terms and conditions of service",
            "Subject to the Provisions of this Regulation and any other Regulation")
        # an enacting sentence closed the same way is not a name
        assert S._split_heading("The Board shall meet monthly.- Provided that", None)[0] != (
            "The Board shall meet monthly")


def test_1746_enacting_sentence_is_not_guessed_as_heading():
    # The official Act prints these as operative amendment instructions, not
    # section headings. Neither document has a contents list to supply one.
    examples = (
        "In the Cooperative Societies Act, 1925 (Act No. VII of 1925), hereinafter referred to",
        "In the said Act, after section 20, the following new sections shall be inserted: “20-A. Provision",
    )
    with profile("unreleased-v4"):
        for rest in examples:
            heading, text = S._split_heading(rest, None)
            assert heading is None
            assert text == rest


def test_1746_quote_led_inserted_items_keep_their_labels():
    with profile("unreleased-v4"):
        assert S.classify("“(5) Other than as set out in subsection (1)") == (
            "subsection", "5", "Other than as set out in subsection (1)")
        assert S.classify("“(v) information as prescribed about its members") == (
            "clause", "v", "information as prescribed about its members")
        parts = S.subdivide("(4) Existing text.\n“(5) Other than as set out")
        assert len(parts) == 2
        assert parts[1].lstrip().startswith("“(5)")
        assert S.classify("“(5) citation without a complete opener") is not None
        assert S.classify("“(5) 3 other things") is None


def test_1746_premature_closing_quote_does_not_end_inserted_sections():
    texts = [
        "5. In the said Act, the following new sections shall be inserted: “20-A. Provision",
        "(i) report when changes occur”.",
        "(ii) give notice",
        "(iii) comply",
        "20-B. Provision of information by the Registrar: condition of the society”.",
        "6. In the said Act, section 21 is amended",
    ]
    with profile("unreleased-v4"):
        assert S._quoted_insertion_spans(texts, [2, 2, 2, 2, 2, 3]) == {1: 4}


def test_2783_quoted_definitions_after_omission_remain_citable():
    # The official page 2 prints omitted definition (1) as stars, followed by
    # the separate definitions (2) "Collector" and (3) "defaulter".
    block = ('2. Definitions. In this Act, unless there is something repugnant—\n'
             '3\n* * * * * * *\n\n'
             '(2) “Collector” means the chief officer in charge of land revenue.\n\n'
             '(3) “defaulter” means a person from whom an arrear is due.')
    with profile("unreleased-v3"):
        assert len(S.subdivide(block)) == 1
    with profile("unreleased-v4"):
        parts = S.subdivide(block)
        assert len(parts) == 3
        assert [S.classify(part)[0:2] for part in parts[1:]] == [
            ("subsection", "2"), ("subsection", "3")]


def _forms_blocks():
    texts = [
        (1, "1. Short title.- These rules may be called the Housing Rules."),
        (2, "Form-B [Rule 21(1)(d)] "), (2, "TRANSFER DEED "),
        (2, "WHEREAS the Transferor is absolute owner with possession of land measuring "),
        (2, "NOW THEREFORE, this deed witnesses as follows: "),
        (3, "FORM C1 "), (3, "SCHEME PLAN SHOWING MORTAGAGE PLOTS "), (3, "Total Area "),
        (4, "FORM D [Rule 22(1)] "), (4, "SUBJECT: APPROVAL OF SCHEME "),
        (4, "This approval of the scheme is subject to the following conditions: "),
    ]
    return [{"id": i + 1, "page_no": page, "text": text, "y0": 100.0 + 20 * i,
             "page_height": 842.0, "x0": 72.0, "x1": 520.0}
            for i, (page, text) in enumerate(texts)]


def test_form_d_opens_and_a_deed_recital_is_not_the_preamble_only_under_v4():
    # doc 4318 pp29, 38-39
    def shape(seg):
        return [(n.kind, n.label) for n in seg.flatten()
                if n.kind in ("form", "preamble")]
    v3 = shape(S.segment(_forms_blocks(), profile="unreleased-v3"))
    v4 = shape(S.segment(_forms_blocks(), profile="unreleased-v4"))
    assert ("preamble", "Preamble") in v3 and ("form", "FORM D") not in v3
    assert ("preamble", "Preamble") not in v4 and ("form", "FORM D") in v4


def test_bracketed_repeal_stub_opens_mid_block_only_under_v4():
    # doc 3284 p4: s.7's repeal stub printed in the block that ends s.6
    block = ("(2) For the purposes of this section the executor or administrator of a "
             "deceased trustee shall be deemed to be a person acting in the "
             "administration of the trust. \n \n \n7. [Exercise by Governor General in "
             "Council of powers of Local Government.] Rep. by \nA.O., 1937. \n \n \n"
             "8. Bare trusteeship of Treasurer.—(1) Subject to the provisions of this Act")
    with profile("unreleased-v3"):
        assert not any(p.lstrip().startswith("7. [") for p in S.subdivide(block))
    with profile("unreleased-v4"):
        stub = [p for p in S.subdivide(block) if p.lstrip().startswith("7. [")]
        assert len(stub) == 1 and S.classify(stub[0])[:2] == ("section", "7")
        # a bracketed reference in running text is not a stub
        prose = "under section 6. \n7. [See the rules made under this Act] shall apply."
        assert not any(p.lstrip().startswith("7. [") for p in S.subdivide(prose))


def test_presidency_act_abbreviation_is_no_heading_end_only_under_v4():
    # doc 1918 p2: "3. [Repeal of Bom. Act III of 1879.] rep. by ..."
    rest = ("[Repeal of Bom. Act III of 1879.] rep. by the Sind Laws (Adaptation, Revision, "
            "Repeal and Declaration) Ordinance, 1955")
    toc = "Repeal of Bombay Act III of 1879."
    with profile("unreleased-v3"):
        assert S._split_heading(rest, toc)[0] == "[Repeal of Bom"
    with profile("unreleased-v4"):
        heading, text = S._split_heading(rest, toc)
        assert heading is None and text.startswith("[Repeal of Bom. Act III")


_S6 = [  # doc 1144 pp3-4, s.6 and the quoted new sections 8-11 (abridged)
    "6. In the said Ordinance, for sections 8 to 11, the following sections shall be substituted:-",
    "Declaration of urban areas.",
    "―8. (1) Government may, after inviting objections, declare any area to be an urban area.",
    "9. (1) Government may, by notification, declare any urban area as a town.",
    "10. Government may alter the limits of any town, municipality or city.",
    "11. (1) As soon as may be the following Councils shall be constituted in an urban area.‖",
    "7. In the said Ordinance, in section 12, sub-section (1), for the words ―joint sitting‖, "
    "the words ―sitting‖ shall be substituted.",
    "11. In the said Ordinance, Schedule I and Schedule IV shall be omitted.",
]


def test_quoted_insertion_spans_close_on_the_quote_and_refuse_a_lost_one():
    pages = [3, 3, 3, 3, 4, 4, 4, 5]
    assert S._quoted_insertion_spans(_S6, pages) == {1: 5}
    # a closing quote the text layer lost never swallows the next amending section
    lost = [t.replace("‖", "") for t in _S6]
    assert S._quoted_insertion_spans(lost, pages) == {}
    # nor the next amending clause: "(ii) for clause (12), ..." (doc 3442)
    clauses = ["(i) for Article 1, the following shall be substituted:-",
               "“1. ACKNOWLEDGMENT OR RECEIPT of money Twenty rupees",
               "(ii) in Article 2, for the word “Fifty”, the words “Two Hundred” shall be substituted;",
               "Five Thousand rupees”;"]
    assert S._quoted_insertion_spans(clauses, [2, 2, 2, 3]) == {}


def test_quoted_new_sections_stay_inside_the_amending_section_only_under_v4():
    blocks = [{"id": i + 1, "page_no": 3 + (i > 3), "text": t, "y0": 80.0 + 60 * (i % 4),
               "page_height": 842.0, "x0": 72.0, "x1": 450.0}
              for i, t in enumerate(["5. In the said Ordinance, section 5 shall be omitted."] + _S6)]

    def sections(profile_name):
        seg = S.segment(blocks, profile=profile_name)
        return [n.label for n in seg.flatten() if n.kind == "section"], seg

    v3, _ = sections("unreleased-v3")
    v4, seg4 = sections("unreleased-v4")
    assert v3.count("11") == 2 or "9" in v3
    assert v4 == ["5", "6", "7", "11"]
    six = [n for n in seg4.flatten() if n.kind == "section" and n.label == "6"][0]
    assert "11. (1) As soon as may be" in six.text


def test_contents_footnote_repeating_a_row_number_is_no_row_only_under_v4():
    # doc 1534 p1: rows 1-20, then footnotes "2. Omitted vide ..." and "3. ..."
    rows = ["1. Short title, extent and commencement.", "2. Definitions.",
            "3. Order for performance of patrol Duty and its cancellation.",
            "4. Appointment of the council and selection of patrol."]
    body = ["1. Short title, extent and commencement.- This Ordinance may be called the Patrol Ordinance.",
            "2. Definitions.- In this Ordinance, unless the context otherwise requires, the words mean.",
            "3. Order for performance of patrol Duty and its cancellation.- The Magistrate may order.",
            "4. Appointment of the council and selection of patrol.- The council shall be appointed."]
    texts = (["CONTENTS"] + rows
             + ["2. Omitted vide Khyber Pakhtunkhwa Ordinance No.I of 1975.",
                "3. Omitted vide Khyber Pakhtunkhwa Ordinance No. I of 1975."] + body)
    blocks = [{"id": i + 1, "page_no": 1 if i < 7 else 2, "text": t, "y0": 80.0 + 40 * (i % 7),
               "page_height": 842.0, "x0": 72.0, "x1": 500.0} for i, t in enumerate(texts)]

    def rows_of(profile_name):
        seg = S.segment(blocks, profile=profile_name)
        return [(e["label"], e.get("heading")) for e in seg.toc_entries]

    assert any((h or "").startswith("Omitted vide") for _, h in rows_of("unreleased-v3"))
    v4 = rows_of("unreleased-v4")
    assert not any((h or "").startswith("Omitted vide") for _, h in v4)
    assert [label for label, _ in v4] == ["1", "2", "3", "4"]


def test_contents_name_that_opens_the_sentence_keeps_the_sentence_only_under_v4():
    # doc 1534 p4: contents "6. Exemption."; body "6. Exemptions from patrol duty may be granted.-"
    rest = "Exemptions from patrol duty may be granted.-"
    with profile("unreleased-v3"):
        assert S._split_heading(rest, "Exemption.")[1] == "from patrol duty may be granted.-"
    with profile("unreleased-v4"):
        assert S._split_heading(rest, "Exemption.") == ("Exemption.", rest)
        # a name printed apart from its text is still split off
        heading, text = S._split_heading("Substitution. Any person liable to patrol duty", "Substitution.")
        assert text.startswith("Any person liable")


def test_subsection_opening_with_its_clause_is_cut_only_under_v4():
    # doc 1515 p3: reg 11(1)'s last clause, then "(2) (i) Where recruitment ..."
    block = ("(iii) experience, where prescribed, would include equivalent experience. \n \n"
             "(2) (i) Where recruitment is to he made on the basis of a written examination, "
             "age shall be reckoned as on the first January;")
    with profile("unreleased-v3"):
        assert not any(p.lstrip().startswith("(2)") for p in S.subdivide(block))
    with profile("unreleased-v4"):
        opened = [p for p in S.subdivide(block) if p.lstrip().startswith("(2)")]
        assert len(opened) == 1
        assert S.classify(opened[0])[:2] == ("subsection", "2")


def test_part_range_is_one_division_only_under_v4():
    # doc 904 pp2, 5: the stubs of repealed parts
    with profile("unreleased-v3"):
        assert S.classify(" PART I AND II ")[:2] == ("part", "I")
    with profile("unreleased-v4"):
        assert S.classify(" PART I AND II ")[:2] == ("part", "I AND II")
        kind, label, rest = S.classify("PART IV to XIV. [Criminal Jails; Superintendents ...]")
        assert (kind, label) == ("part", "IV TO XIV") and rest.lstrip().startswith("[Criminal")
        # an ordinary part is untouched
        assert S.classify("PART III CIVIL JAILS.")[:2] == ("part", "III")


def test_next_chapter_with_its_title_after_a_comma_only_under_v4():
    # doc 3672 pp4-5: s.2(y) ends "... by regulations," and p5 opens "CHAPTER II / THE INSTITUTE"
    texts = ["CHAPTER I \nPRELIMINARY", "1. Short title.- This Act may be called the Institute Act.",
             "2. Definitions.- In this Act,- (a) \"teachers\" include such other person as may be "
             "declared to be teachers by regulations,",
             " \nCHAPTER II \nTHE INSTITUTE \n",
             "3. Establishment.- The Institute shall consist of the following.",
             "4. Powers.- The Institute shall have the following powers."]
    blocks = [{"id": i + 1, "page_no": 1 + (i > 2), "text": t, "y0": 120.0 + 60 * (i % 3),
               "page_height": 842.0, "x0": 72.0, "x1": 450.0} for i, t in enumerate(texts)]

    def chapters(profile_name):
        seg = S.segment(blocks, profile=profile_name)
        return [(n.label, [c.label for c in n.children if c.kind == "section"])
                for n in seg.flatten() if n.kind == "chapter"]

    assert [label for label, _ in chapters("unreleased-v3")] == ["I"]
    assert chapters("unreleased-v4") == [("I", ["1", "2"]), ("II", ["3", "4"])]
    # the running prose of a cross-reference is no title
    blocks[3] = dict(blocks[3], text=" \nCHAPTER II of this Act shall apply to them \n")
    assert [label for label, _ in chapters("unreleased-v4")] == ["I"]


def test_lettered_part_opens_only_under_v4():
    # doc 1563 pp7-9: the Schedule's "PART A", "PART B", "PART D" ("PART C" reads as Roman 100)
    with profile("unreleased-v3"):
        assert S.classify("PART  A \n[See section 5 (2)] \n") is None
    with profile("unreleased-v4"):
        kind, label, rest = S.classify("PART  A \n[See section 5 (2)] \n")
        assert (kind, label) == ("part", "A") and rest.lstrip().startswith("[See section")
        assert S.classify("PART D ")[:2] == ("part", "D")
        assert S.classify("PART C [See section 5 (3)].")[:2] == ("part", "C")
        # a sentence about a part is not the part
        assert S.classify("PART A of the Schedule shall apply.") is None
        assert S.classify("Part A of the Schedule") is None


def test_hyphen_suffix_labels_open_only_under_v4():
    # doc 1794 p14 (s.21's inserted (1-A)..(1-E)); doc 3714 p3 (s.2's inserted (a-i), (a-ii))
    block = ("prefer an appeal to the 1[\"District Judge\"] \n1[“(1-A). On such appeal being preferred, the "
             "District Judge may hear it himself. \n(1-B). The District Judge may recall an appeal. \n")
    clauses = ("waters where fish after being caught is collected; \n \n2[(a-i) “adjacent province’s "
               "waters” means the maritime waters; \n \n   (a-ii)  “continental shelf” means the seabed; \n")
    with profile("unreleased-v3"):
        assert len(S.subdivide(block)) == 1 and len(S.subdivide(clauses)) == 1
        assert S.classify("(1-A). On such appeal") is None
    with profile("unreleased-v4"):
        pieces = S.subdivide(block)
        assert [S.classify(p)[:2] for p in pieces[1:]] == [("subsection", "1-A"), ("subsection", "1-B")]
        assert pieces[1].lstrip().startswith("1[“(1-A)")
        assert [S.classify(p)[:2] for p in S.subdivide(clauses)[1:]] == [("clause", "a-i"), ("clause", "a-ii")]
        # a reference running onto the next line is not a unit
        assert len(S.subdivide("as provided in sub-section \n(1-A) of this section.")) == 1


def test_percent_led_item_opens_only_under_v4():
    # doc 3794 p4: s.6's member list, item 10 "50% of the members of the board shall be women."
    block = (" \n8. \nA serving or retired social scientist. \n \n9. \nEminent scholar having uncontroversial "
             "status in the society. \n \n10. \n50% of the members of the board shall be women. \n")
    with profile("unreleased-v3"):
        assert not any(p.lstrip().startswith("10.") for p in S.subdivide(block))
    with profile("unreleased-v4"):
        item = [p for p in S.subdivide(block) if p.lstrip().startswith("10.")]
        assert len(item) == 1 and S.classify(item[0])[:2] == ("section", "10")
        # without item 9 before it in the block, a percentage row is not cut
        row = "Rate of tax \n10. \n50% of the value of the goods \n"
        assert not any(p.lstrip().startswith("10.") for p in S.subdivide(row))


def test_contents_banner_block_only_under_v4():
    # doc 2875 p1: "CONTENT / Preamble / Sections" in one block
    banner = " \nCONTENT \n \nPreamble \nSections \n"
    with profile("unreleased-v3"):
        assert not S._has_contents_marker(banner)
    with profile("unreleased-v4"):
        assert S._has_contents_marker(banner)
        assert S._has_contents_marker("CONTENTS")
        # a sentence about content, or a banner line beside operative text, is no marker
        assert not S._has_contents_marker("Content of the application \nSections")
        assert not S._has_contents_marker("CONTENT \nThis Act may be called the Act.")


def test_form_code_number_reference_and_rs_item_only_under_v4():
    # doc 3665: "FORM PCT-8 / See rule 12 and 17." after a form ending "Date:", and Form PCT-9's items
    with profile("unreleased-v3"):
        assert S.classify("FORM PCT-8 \n \nSee rule 12 and 17.")[:2] == ("form", "FORM PCT")
    with profile("unreleased-v4"):
        assert S.classify("FORM PCT-8 \n \nSee rule 12 and 17.")[:2] == ("form", "FORM PCT-8")
        assert S.classify("FORM PCT—13 \nSee Rule (16)")[:2] == ("form", "FORM PCT-13")
        assert S.classify("FORM PCT-I \nSurvey Register.")[:2] == ("form", "FORM PCT-I")
        assert S.classify("FORM A [See rule 3]")[:2] == ("form", "FORM A")
    items = "1. Current Tax for the year_____19......   Rs. \n2. Arrears          Rs. \n   ______ \n"
    tariff = "in excess of Rs.\n1000.\nTen rupees."
    with profile("unreleased-v3"):
        assert len(S.subdivide(items)) == 1
    with profile("unreleased-v4"):
        assert [p.lstrip()[:2] for p in S.subdivide(items)] == ["1.", "2."]
        assert len(S.subdivide(tariff)) == 1
    blocks = [{"id": i + 1, "page_no": 9 + i, "text": t, "y0": 80.0, "page_height": 842.0, "x0": 72.0, "x1": 450.0}
              for i, t in enumerate(["FORM PCT-7 \n(See Rule 5(3) \nI, do hereby declare that ... Place____ \nDate:",
                                     "FORM PCT-8 \n \nSee rule 12 and 17. \n \nLast date of payment____"])]

    def forms(profile_name):
        return [n.label for n in S.segment(blocks, profile=profile_name).flatten() if n.kind == "form"]

    assert forms("unreleased-v4") == ["FORM PCT-7", "FORM PCT-8"]


def test_bracketed_sub_rule_reference_opens_the_form_only_under_v4():
    # doc 2344 p8-9: Form III ends "Signature of Notary" (no stop); Form IV's reference is two units down
    texts = ["FORM III \n", "FORM OF NOTING FOR DISHONOUR. \n", "(See Sub-Rule (1) of RULE 12) \n",
             "Date of note. \n", "Notary’s charges. \n \n \nSignature of Notary \n",
             "FORM  IV \n", "FORM OF NOTING FOR DISHONOUR. \n", "(See Sub-Rule (1) of RULE 12) \n",
             "On the ______day of ______20____ the above bill was a the request of \n"]
    blocks = [{"id": i + 1, "page_no": 8 if i < 5 else 9, "text": t, "y0": 72.0 + 20 * (i % 5),
               "page_height": 842.0, "x0": 72.0, "x1": 450.0} for i, t in enumerate(texts)]

    def forms(profile_name):
        return [n.label for n in S.segment(blocks, profile=profile_name).flatten() if n.kind == "form"]

    assert forms("unreleased-v4") == ["FORM III", "FORM IV"]
    ref = S._BRACKETED_SUB_RULE_REFERENCE
    assert ref.match("(See Sub-Rule (1) of RULE 12)") and ref.match("(See SUB-RULE (1) OF RULE 12)")
    assert not ref.match("(See rule 12)") and not ref.match("see sub-rule (1) of rule 12")


def test_marked_first_subsection_and_marked_clause_only_under_v4():
    # doc 3144 s.18 "—(1) 1[Under the said Act]" and s.2 "(v) ...; or / 2[(l) “criminal offence” means ..."
    heading = ("18. \nNon-disclosure of confidential requests for assistance.—(1) 1[Under the said Act], a \n"
               "person who has knowledge of the,— \n")
    clauses = ("(v) \nthe freezing or seizure of proceeds or instrumentalities of crime or terrorist \nproperty; or \n \n"
               "2[(l) \n “criminal offence” means an offence punishable under the Pakistan Penal code \n")
    with profile("unreleased-v3"):
        assert len(S.subdivide(heading)) == 1
        assert len(S.subdivide(clauses)) == 1
    with profile("unreleased-v4"):
        assert [S.classify(p)[:2] for p in S.subdivide(heading)] == [("section", "18"), ("subsection", "1")]
        en = "3. \nRestrictions on alienations.– (1) 2[Save as hereinafter provided, no person \n"
        assert [S.classify(p)[:2] for p in S.subdivide(en)] == [("section", "3"), ("subsection", "1")]
        assert [S.classify(p)[:2] for p in S.subdivide(clauses)] == [("clause", "v"), ("clause", "l")]
        # a note marker in running text is no cut, nor a reference "sub-section / 1[(a)" mid-line
        assert len(S.subdivide("(a) the words 2[(b) the] shall be read; \n")) == 1


def test_quoted_schedule_heading_only_under_v4():
    # doc 2508 p6: the annexure's second schedule "“SCHEDULE -II" with "(See section 4)" in the next block
    with profile("unreleased-v3"):
        assert S.classify("“SCHEDULE -II \n") is None
    with profile("unreleased-v4"):
        assert S.classify("“SCHEDULE -II \n")[:2] == ("schedule", "SCHEDULE -II")
        assert S.classify("“SCHEDULE II \n(See section 4) \nS.No")[:2] == ("schedule", "SCHEDULE II")
        # a quoted schedule running into prose that names no section is no heading
        assert S.classify("“SCHEDULE II shall be omitted") is None


def test_joint_schedule_heading_only_under_v4():
    # doc 3132 p17: the repealed Third and Fourth Schedules printed under one heading
    stub = ("THE THIRD AND FOURTH SCHEDULES. [ENACTMENTS REPEALED. ENACTMENTS \nAMENDED.] Rep. by the Repealing "
            "and Amending Act, 1945 (VI of 1945),s.2  and First Schedule. \n")
    with profile("unreleased-v3"):
        assert S.classify(stub) is None
    with profile("unreleased-v4"):
        assert S.classify(stub)[:2] == ("schedule", "THIRD AND FOURTH SCHEDULES")
        # the words in running prose are no heading
        assert S.classify("the Second and Third Schedules shall be omitted") is None


def test_bracket_not_division_label_only_under_v4():
    # doc 3302 p12: "ANNEXURE / (See regulation 14 )"
    with profile("unreleased-v3"):
        assert S.classify("ANNEXURE \n(See regulation 14 ) \n")[:2] == ("annexure", "ANNEXURE (See")
    with profile("unreleased-v4"):
        kind, label, rest = S.classify("ANNEXURE \n(See regulation 14 ) \n")
        assert (kind, label) == ("annexure", "ANNEXURE") and rest.startswith("(See regulation 14")
    # an identity that is not a "(See ..." reference is untouched
    for text in ("ANNEXURE II \nForm", "ANNEXURE (A) \nForm", "APPENDIX B \n(rule 3)"):
        with profile("unreleased-v3"):
            before = S.classify(text)
        with profile("unreleased-v4"):
            assert S.classify(text) == before


def test_member_designation_row_shape():
    # doc 3836 s.6(1) row 7 "Chief Executive Officer of the Authority | Member/Cum- Secretary"
    assert "member_designation_row" in S.SEGMENTATION_PROFILES["unreleased-v4"]
    assert "member_designation_row" not in S.SEGMENTATION_PROFILES["unreleased-v3"]
    end = S._MEMBER_DESIGNATION_END
    for row in ("Chief Executive Officer of the Authority Member/Cum- Secretary",
                "Deputy Chairman, Planning Commission Vice- Chairperson",
                "Five members from private sector to be nominated by the Federal Government Member"):
        assert end.search(row)
    # a real section carries its heading dash, and ordinary text does not end in a designation
    assert re.search(r"[.:]\s*[-–—―]", "Chief Executive Officer.— The Federal Government shall appoint a Secretary")
    assert not end.search("The Board shall meet at least once in a quarter.")


def test_doc2299_definition_and_label_shapes_only_under_v4():
    # doc 2299: '(15) ... colony; / (16) "commencement" ...' with (15) opened in an earlier block
    cont = '(a) \nin any Act passed ... deemed to be one \ncolony; \n \n \n(16) "commencement" used with reference to \n'
    whole = '(1) "Act" means the Act; \n(2) "Board" means the Board; \n'
    with profile("unreleased-v3"):
        assert len(S.subdivide(cont)) == 1
        assert S.classify("2[(39-a) \"Khyber Pakhtunkhwa\" shall mean ...") is None
        assert len(S.subdivide("POWERS AND FUNCTIONARIES. \n19. \nwhere, by any 3[Provincial] Act \n")) == 1
    with profile("unreleased-v4"):
        assert len(S.subdivide("POWERS AND FUNCTIONARIES. \n19. \nwhere, by any 3[Provincial] Act \n")) == 2
        assert [p.lstrip()[:4] for p in S.subdivide(cont)] == ["(a) ", "(16)"]
        # a definitions list held whole in one text is left as it is (released docs 3486, 3665, 3794)
        assert len(S.subdivide(whole)) == 1
        assert S.classify("2[(39-a) \"Khyber Pakhtunkhwa\" shall mean ...")[:2] == ("subsection", "39-a")
        assert S.classify("6[(17a) 'Constitution means ...")[:2] == ("subsection", "17a")
        assert S.classify("19. \nwhere, by any 3[Provincial] Act, a power ...")[:2] == ("section", "19")
        assert S.classify('3"[28. The Provisions of this Act shall apply ...')[:2] == ("section", "28")
        assert [S.classify(p)[:2] for p in S.subdivide("7. \n5[(1)] Where this Act repeals \n")] == [
            ("section", "7"), ("subsection", "1")]


def test_letter_closing_finished_only_under_v4():
    # doc 1874: Form A ends "Yours faithfully" (no stop); "FORM 'B'" heads the next page
    with profile("unreleased-v3"):
        assert S._continues_previous("Signature of applicant \nYours faithfully")
    with profile("unreleased-v4"):
        assert not S._continues_previous("Signature of applicant \nYours faithfully")
        assert not S._continues_previous("Your obediently,")
        assert S._continues_previous("the Board may by notification in the")


def test_docs_3785_4263_shapes_only_under_v4():
    para = "12. \nNew section 24-A.– After section 24 of the said Act the following shall be inserted \n"
    note = "12 New section 24-A inserted by Ord. XX of 1960 \n"
    with profile("unreleased-v3"):
        assert S._FOOTNOTE.match(para)
        assert S.classify("1[11]. Meetings of the Authority.– (a) The Authority shall meet") is None
        assert S.classify('5[(ccc)  "Institution" means the Institution;]') is None
        assert not S._schedule_heading_with_reference("THE SCHEDULE \n", ["SCHEME \n[(See section 2(e)] \n"])
    with profile("unreleased-v4"):
        assert not S._FOOTNOTE.match(para)          # doc 3785: an enacting paragraph, no note
        assert S._FOOTNOTE.match(note)              # a real provenance note still is one
        assert S.classify("1[11]. Meetings of the Authority.– (a) The Authority shall meet")[:2] == ("section", "11")
        assert S.classify('5[(ccc)  "Institution" means the Institution;]')[:2] == ("clause", "ccc")
        assert S.classify("(abc) not a repeated letter") is None
        assert S._schedule_heading_with_reference("THE SCHEDULE \n", ["SCHEME \n[(See section 2(e)] \n"])
        assert not S._schedule_heading_with_reference("THE SCHEDULE \n", ["SCHEME \nthe following shall be substituted \n"])


def test_referenced_table_heading_shape():
    # doc 4276 p5: the substituted TABLE under s.7, with its section reference
    heading = S._REFERENCED_TABLE_HEADING
    assert heading.fullmatch(S._norm(" 1[TABLE [see section 7(1)] "))
    assert heading.fullmatch("TABLE (see rule 12)")
    assert not heading.fullmatch("TABLE OF CONTENTS")
    assert not heading.fullmatch("TABLE [see section 7(1)] 1. All persons engaged")
    assert "referenced_table_heading" in S.SEGMENTATION_PROFILES["unreleased-v4"]
    assert "referenced_table_heading" not in S.SEGMENTATION_PROFILES["unreleased-v3"]


def test_whole_schedule_quote_only_under_v4():
    # doc 4433 s.10(s): the substituted Second Schedule opens past the next
    # page's three running-head units and runs on for many pages; one of its
    # rows prints a lower-case instruction that is not an amending provision
    texts = (["(s) \nfor the existing Second Schedule, the following shall be substituted, namely: \n",
              "THE FINANCE ACT, 2025. \n", "(ACT NO. XVIII OF 2025) \n", "14 | P a g e \n",
              "“SECOND SCHEDULE \n[see sections 3(1) and (4)] \n"]
             + [f"{k}. Services of kind {k}. Five percent (5%) \n" for k in range(1, 30)]
             + ["(i) for Umrah services; and \n", "30. Other services. Two percent.”. \n",
                "11. Amendment of the Act No. XXV of 2022.---In the Cess Act, \n"])
    pages = [13, 14, 14, 14, 14] + [14 + k // 4 for k in range(1, 30)] + [22, 22, 22]
    with profile("unreleased-v3"):
        assert S._quoted_insertion_spans(texts, pages) == {}
    with profile("unreleased-v4"):
        assert S._quoted_insertion_spans(texts, pages) == {1: len(texts) - 2}


def test_amendment_items_owner_only_under_v4():
    # doc 715 s.2: "shall stand amended as under:-" owns its numbered items
    # the shape of doc 715 pp1-4: margin headings in their own right-hand blocks
    rows = [  # (page, y, x0, x1, text)
        (1, 80, 72, 520, "CONTENTS"), (1, 120, 72, 520, "1. Short title and commencement."),
        (1, 160, 72, 520, "2. Revival and amendments of the Authority Act."), (1, 200, 72, 520, "3. Saving."),
        (2, 35, 72, 525, "SINDH ACT NO. VIII OF 2009 THE AUTHORITY (REVIVAL AND AMENDING) ACT, 2009"),
        (2, 194, 72, 421, "WHEREAS it is expedient to revive and amend the Authority Act, 1994, in the manner "
                          "hereinafter appearing; It is hereby enacted as follows:-"),
        (2, 194, 428, 491, "Preamble."),
        (2, 312, 72, 421, "1. (1) This Act may be called the Revival and Amending Act, 2009."),
        (2, 312, 428, 511, "Short title and commence- ment."),
        (2, 415, 72, 421, "2. The Authority Act, 1994, shall stand revived and on such revival, shall "
                          "stand amended as under:-"),
        (2, 415, 428, 523, "Revival and amendments of the Authority Act."),
        (2, 488, 90, 421, "1. Through out the Act, for the words “Division”, the words "
                          "“District” shall be substituted."),
        (3, 165, 90, 421, "2. In section 2, clause (o) shall be omitted. \n3. In section 3, in sub-section "
                          "(3), the words “or such place” shall be omitted. \n4. In section 6, for the "
                          "word “Non-official”, the word “The” shall be substituted."),
        (4, 76, 72, 421, "3. All orders made, proceedings taken and acts done by the Authority shall be "
                         "deemed to have been validly made."),
        (4, 91, 428, 474, "Saving.")]
    blocks = [{"id": i + 1, "page_no": pg, "text": t + " \n", "y0": float(y), "page_height": 842.0,
               "x0": float(x0), "x1": float(x1)} for i, (pg, y, x0, x1, t) in enumerate(rows)]

    # the margin heading "Saving." emitted after its section block, and before it
    swapped = blocks[:-2] + [blocks[-1], blocks[-2]]
    for case in (blocks, swapped):
        parsed = S.segment(case, profile="unreleased-v4").flatten()
        sections = [(n.label, n.heading) for n in parsed if n.kind == "section"]
        assert [label for label, _ in sections] == ["1", "2", "3"]
        assert sections[2][1].startswith("Saving")
        s2 = next(n for n in parsed if n.kind == "section" and n.label == "2")
        assert [(c.kind, c.label) for c in s2.children] == [("clause", str(k)) for k in range(1, 5)]
    assert "amendment_items_owner" in S.SEGMENTATION_PROFILES["unreleased-v4"]
    assert "amendment_items_owner" not in S.SEGMENTATION_PROFILES["unreleased-v3"]


def test_parenthesised_letter_label_and_clause_then_romanette_only_under_v4():
    # doc 4453 Schedule I: inserted articles "1[6(A)." / "6(B)"; Art.33 "(a)" then "(i) when ..."
    block = ("of the loan amount. \n1[6(A). \nAllotment order or transfer of allotment order \n"
             "6(B) \nTransfer of Allotment Orders before lease. \n")
    gift = "GIFT-instrument of, not being a SETTLEMENT. \n(a) \n(i) when executed in favour of legal heirs; \n"
    with profile("unreleased-v3"):
        assert S.classify("1[6(A). \nAllotment order") is None
        assert not any(p.lstrip().startswith("6(B)") for p in S.subdivide(block))
        assert not any(p.lstrip().startswith("(a)") for p in S.subdivide(gift))
    with profile("unreleased-v4"):
        assert S.classify("1[6(A). \nAllotment order")[:2] == ("section", "6(A)")
        assert S.classify("6(B) \nTransfer of Allotment Orders")[:2] == ("section", "6(B)")
        assert S.classify("2(a) the Board") is None or S.classify("2(a) the Board")[1] != "2(a)"
        assert any(p.lstrip().startswith("6(B)") for p in S.subdivide(block))
        assert any(p.lstrip().startswith("(a)") for p in S.subdivide(gift))


def test_suffixed_decimal_label_and_rule_range_only_under_v4():
    # doc 2418: "11-A.2." / "11-A-9." are whole rule numbers; "Rules 9.12 to 9.27 ..." is a reference
    block = "11-A.6. \nRules 9.12 to 9.27 of the Punjab Distillery Rules shall apply. \n"
    with profile("unreleased-v3"):
        assert S.classify("11-A.2. In these rules")[1] == "11-A"
        assert any(p.lstrip().startswith("Rules 9.12") for p in S.subdivide(block))
    with profile("unreleased-v4"):
        assert S.classify("11-A.2. In these rules")[:2] == ("section", "11-A.2")
        assert S.classify("11-A-9. Immediately on arrival")[:2] == ("section", "11-A-9")
        assert S.classify("7.2.A Every person who imports")[:2] == ("section", "7.2.A")
        assert not any(p.lstrip().startswith("Rules 9.12") for p in S.subdivide(block))
        assert any(p.lstrip().startswith("Rule 9.") for p in S.subdivide("text. \nRule 9. Every licensee shall"))


def test_sequential_part_heading_only_under_v4():
    # doc 4433 p38: "Part-B" in mixed case; its title ends at the blank line
    with profile("unreleased-v3"):
        assert S.classify("Part-B \nOther Commercial Properties") is None
    with profile("unreleased-v4"):
        assert S.classify("Part-B \nOther Commercial Properties")[:2] == ("part", "B")
        assert S.classify("Part of the land shall be")  is None or S.classify("Part of the land shall be")[0] != "part"
    rows = [  # (page, y, text)
        (1, 80, "APPENDIX I [see section 3]"), (1, 120, "PART-A RESIDENTIAL BUILDINGS"),
        (1, 160, "1. Up to 4.9 Marlas. 2000/- 1800/-"), (1, 200, "2. Exceeding 4.9 Marlas. 3000/- 2500/-"),
        (1, 240, "Part-B \nOther Commercial Properties \n \nTax for properties used as shops shall be assessed "
                 "with the following formula:"),
        (1, 300, "(a) the formula for tax calculation shall be-")]
    blocks = [{"id": i + 1, "page_no": pg, "text": t + " \n", "y0": float(y), "page_height": 842.0,
               "x0": 72.0, "x1": 520.0} for i, (pg, y, t) in enumerate(rows)]
    parts = [(n.label, n.heading, n.text) for n in S.segment(blocks, profile="unreleased-v4").flatten()
             if n.kind == "part"]
    assert [p[0] for p in parts] == ["A", "B"]
    assert parts[1][1] == "Other Commercial Properties"
    assert parts[1][2].startswith("Tax for properties")


def test_hyphen_letter_division_label_only_under_v4():
    # doc 4330: "CHAPTER VII-A" / "FORM II-A" alone on their lines
    with profile("unreleased-v3"):
        assert S.classify("CHAPTER VII-A \nSPECIAL PRECAUTIONS")[1] != "VII-A"
    with profile("unreleased-v4"):
        assert S.classify("CHAPTER VII-A \nSPECIAL PRECAUTIONS")[:2] == ("chapter", "VII-A")
        assert S.classify("FORM II-A \n[See Regulation 3(4)]")[:2] == ("form", "FORM II-A")


def test_lettered_paragraph_sequence_only_under_v4():
    # doc 4330 reg 53(2): "(2)-A. Proper ..." then "B." ... in sequence
    rows = ["53. (1) No person shall be employed in any mine unless there are two shafts.",
            "21[(2)-A. Proper arrangements shall be made for persons to descend.",
            "B. Where the slope of a seam is more than one vertical, roads shall be provided.",
            "C. All platforms shall be securely fenced.",
            "(3) Such shafts shall be not less than 45 feet distant."]
    blocks = [{"id": i + 1, "page_no": 1, "text": t + " \n", "y0": 80.0 + 40 * i, "page_height": 842.0,
               "x0": 72.0, "x1": 520.0} for i, t in enumerate(rows)]

    def paragraphs(name):
        return [n.label for n in S.segment(blocks, profile=name).flatten() if n.kind == "clause"]
    assert paragraphs("unreleased-v4") == ["A", "B", "C"]
    assert paragraphs("unreleased-v3") != ["A", "B", "C"]
    lone = [{"id": 1, "page_no": 1, "text": "B. This is not in a lettered run. \n", "y0": 80.0,
             "page_height": 842.0, "x0": 72.0, "x1": 520.0}]
    assert not [n for n in S.segment(lone, profile="unreleased-v4").flatten() if n.label == "B"]


def test_quoted_schedule_word_owner_only_under_v4():
    # doc 3056 s.2(viii): only the heading word is quoted; the articles follow unquoted
    rows = ["1. (1) This Ordinance may be called the Stamp (Sindh Amendment) Ordinance, 2002.",
            "2. In the Stamp Act, 1899, in its application to the Province of Sindh-",
            "(i) in section 23-A for the word \"Article 5\" the word \"Article 3\" shall be substituted;",
            "(viii) for the existing Schedule 1, the following shall be substituted- \n\"SCHEDULE\"",
            "1. Acknowledgement of a debt written or signed by a debtor. One rupee.",
            "2. Affidavit, including an affirmation. Twenty rupees.",
            "3. Agreement or Memorandum of an Agreement. One hundred rupees."]
    blocks = [{"id": i + 1, "page_no": 1 + i // 4, "text": t + " \n", "y0": 80.0 + 60 * (i % 4),
               "page_height": 842.0, "x0": 72.0, "x1": 520.0} for i, t in enumerate(rows)]

    def sections(name):
        return [n.label for n in S.segment(blocks, profile=name).flatten() if n.kind == "section"]
    assert sections("unreleased-v4") == ["1", "2"]
    viii = next(n for n in S.segment(blocks, profile="unreleased-v4").flatten() if n.label == "viii")
    assert [c.label for c in viii.children] == ["1", "2", "3"]
    assert sections("unreleased-v3") != ["1", "2"]


def test_form_reference_sequence_and_colon_heading_only_under_v4():
    # doc 4317: "(rule 24)" after the form's title; "Form C1" continuing Form C; "32. Name: Text"
    with profile("unreleased-v3"):
        assert S._split_heading("Fee for revised plan and service designs: A sponsor shall deposit the fee.", None)[0] is None
    with profile("unreleased-v4"):
        assert S._split_heading("Fee for revised plan and service designs: A sponsor shall deposit the fee.",
                                None)[0] == "Fee for revised plan and service designs"
        assert S._split_heading("The Authority shall: A sponsor", None)[0] != "The Authority shall"
    blocks = [{"text": t} for t in ["Form-C \n", "witness Address Address \n", "Form C1 \n", "Form C2 \nSCHEDULE OF PROPERTY \n",
                                    "Form-E \n"]]
    assert S._sequential_form_labels(blocks) == frozenset({("C", "1"), ("C", "2")})


def test_schedule_word_rows_own_items_only_under_v4():
    # doc 3056: each substituted article owns its own (a)/(b) items
    rows = ["1. (1) This Ordinance may be called the Stamp (Sindh Amendment) Ordinance, 2002.",
            "2. In the Stamp Act, 1899, in its application to the Province of Sindh-",
            "(viii) for the existing Schedule 1, the following shall be substituted- \n\"SCHEDULE\"",
            "1. Acknowledgement of a debt written or signed by a debtor-",
            "(a) where the amount does not exceed five hundred rupees. One rupee.",
            "(b) where the amount exceeds five hundred rupees. Two rupees.",
            "2. Affidavit, including an affirmation. Twenty rupees."]
    blocks = [{"id": i + 1, "page_no": 1, "text": t + " \n", "y0": 80.0 + 40 * i, "page_height": 842.0,
               "x0": 72.0, "x1": 520.0} for i, t in enumerate(rows)]

    def article_one(name):
        viii = next(n for n in S.segment(blocks, profile=name).flatten() if n.label == "viii")
        first = next((c for c in viii.children if c.label == "1"), None)
        return [c.label for c in first.children] if first else None
    assert article_one("unreleased-v4") == ["a", "b"]


def test_first_part_and_sequential_schedule_only_under_v4():
    # doc 4353: "PART-A" after an item ending ";"; "Schedule-III" first on its page after a lower-case cell
    rows = [(1, "1. Short title. This Act may be called the Universities Act, 2022."),
            (2, "SCHEDULE-II"), (2, "1. Criteria for appointment of the Vice Chancellor as set out in Part-E;"),
            (2, "PART-A"), (2, "1. Essential Qualification and Experience;"),
            (2, "PART-B"), (2, "2. Desirable Experience in research and teaching;"),
            (2, "(a) teaching at the university level and national research awards"),
            (3, "Schedule-III"), (3, "Establishment of New Public Universities"),
            (3, "1. The Government may establish a university by notification.")]
    blocks = [{"id": i + 1, "page_no": pg, "text": t + " \n", "y0": 80.0 + 40 * i, "page_height": 842.0,
               "x0": 72.0, "x1": 520.0} for i, (pg, t) in enumerate(rows)]

    def divisions(name):
        return [(n.kind, n.label) for n in S.segment(blocks, profile=name).flatten()
                if n.kind in ("schedule", "part")]
    v4 = divisions("unreleased-v4")
    assert ("part", "A") in v4 and ("part", "B") in v4
    assert [d for d in v4 if d[0] == "schedule"][-1][1].endswith("III")


def test_doc3108_form_and_rule_shapes_only_under_v4():
    with profile("unreleased-v3"):
        assert S.classify("FORM L-37-A \nForm of Bankers Guarantee")[1] != "FORM L-37-A"
    with profile("unreleased-v4"):
        assert S.classify("FORM L-37-A \nForm of Bankers Guarantee")[:2] == ("form", "FORM L-37-A")
        assert S._split_heading("(1) (a). In this rule, the following terms", None)[0] is None
        assert S._split_heading("Not reproduced being un-necessary.", None)[0] is None
        quoted = [{"text": t} for t in ["FORM 'A' \n", "District \n", "FORM “B” \n"]]
        assert ("B", "") in S._sequential_form_labels(quoted)
    rows = [(1, "7.1 In exercise of the powers conferred, the Commissioner makes these rules."),
            (1, "7.2 Any person importing country spirit shall obtain a pass."),
            (2, "FORM A"), (2, "Authorization for the export-in-bond by sea of the following items"),
            (3, "7.3 Any person importing foreign liquor must obtain a transport pass.")]
    blocks = [{"id": i + 1, "page_no": pg, "text": t + " \n", "y0": 80.0 + 40 * i, "page_height": 842.0,
               "x0": 72.0, "x1": 520.0} for i, (pg, t) in enumerate(rows)]
    sections = [n.label for n in S.segment(blocks, profile="unreleased-v4").flatten() if n.kind == "section"]
    assert "7.3" in sections


def test_enactment_chapter_reference_only_under_v4():
    # doc 2221: a First Schedule row group headed by another enactment's chapter
    rows = ["1. Short title. This Ordinance may be called the Goondas Ordinance, 1959.",
            "FIRST SCHEDULE \n[See Section 21-A]", "Name and other details of enactment",
            "Chapter VIII, Pakistan Penal Code.", "1. Section 143. Two years.",
            "Chapter X, Pakistan Penal Code.", "2. Section 172. One year."]
    blocks = [{"id": i + 1, "page_no": 1 + (i > 0), "text": t + " \n", "y0": 80.0 + 40 * i,
               "page_height": 842.0, "x0": 72.0, "x1": 520.0} for i, t in enumerate(rows)]
    chapters = [n for n in S.segment(blocks, profile="unreleased-v4").flatten() if n.kind == "chapter"]
    assert chapters == []
    with profile("unreleased-v4"):
        assert S._split_heading("Maintenance of the farm: - The owner shall keep the animals.",
                                None)[0] == "Maintenance of the farm"


def test_in_respect_of_not_opener_only_under_v4():
    # doc 4276 s.6(d): a quoted fee entry whose rows read "(a) in respect of ..."
    texts = ["(d) for the entries at serial No. 10, the following shall be substituted, namely: \n",
             "“10. Registration fee under rule 42 and 48--- \n",
             "(a) in respect of Motor Cycles or a Trailer; 100 \n",
             "(b) in respect of an invalid carriage; 10 \n",
             "(f) in respect of temporary registration of any vehicle. 200.” \n"]
    pages = [4] * 5
    with profile("unreleased-v3"):
        assert S._quoted_insertion_spans(texts, pages) == {}
    with profile("unreleased-v4"):
        assert S._quoted_insertion_spans(texts, pages) == {1: 4}
        assert S._AMENDING_OPENER_NOT_RESPECT.match("(ii) in Article 2, for the words")


def test_page_first_running_header_only_under_v4():
    # doc 4453: the page number first, then the title ending in the bracketed Act number
    head = "6 | P a g e \nTHE STAMP ACT, 1899 (ACT II OF 1899) \n"
    with profile("unreleased-v3"):
        assert not S._is_running_header(head)
    with profile("unreleased-v4"):
        assert S._is_running_header(head)
        assert not S._is_running_header("6. The Stamp Act shall apply (ACT II OF 1899)")


def test_no_cut_after_number_abbreviation_only_under_v4():
    # doc 4453 s.29(a): "No.    2. (Administration Bond)" is a list of articles, not a unit
    text = "(a) in the case of any instrument described in any of the following articles, namely:-- No. \n2. Administration Bond, No. 6 Agreement"
    with profile("unreleased-v4"):
        assert not any(u.lstrip().startswith("2.") for u in S.subdivide(text))
    with profile("unreleased-v3"):
        assert any(u.lstrip().startswith("2.") for u in S.subdivide(text))


def test_serial_abbreviation_ends_no_guessed_heading_only_under_v4():
    # doc 3442 s.4: "... for entries at Sr. No.1, 4 and 5, the following shall respectively be substituted"
    body = ("In the Sindh Finance Act, 1964, in the Seventh Schedule, for entries at Sr. No.1, 4 and 5, the "
            "following shall respectively be substituted: -")
    toc = "Amendment of Seventh Schedule of Sindh Act XXIV of 1964."
    with profile("unreleased-v3"):
        assert (S._split_heading(body, toc)[0] or "").endswith("Sr")
    with profile("unreleased-v4"):
        assert not (S._split_heading(body, toc)[0] or "").endswith("Sr")


def test_first_printed_chapter_two_opens_only_under_v4():
    # doc 3002 p4: no Chapter I is printed; "CHAPTER II / THE UNIVERSITY" follows "... of the University;"
    texts = ["1. Short title.- This Ordinance may be called the University Ordinance.",
             "2. Definitions.- In this Ordinance,- (i) \"University\" means the University;",
             " \nCHAPTER II \nTHE UNIVERSITY \n",
             "3. Establishment.- There shall be established a University.",
             " \nCHAPTER III \nOFFICERS \n",
             "4. Officers.- The following shall be the officers."]
    blocks = [{"id": i + 1, "page_no": 1 + i // 3, "text": t, "y0": 120.0 + 60 * (i % 3),
               "page_height": 842.0, "x0": 72.0, "x1": 450.0} for i, t in enumerate(texts)]

    def chapters(profile_name):
        seg = S.segment(blocks, profile=profile_name)
        return [(n.label, [c.label for c in n.children if c.kind == "section"])
                for n in seg.flatten() if n.kind == "chapter"]

    assert chapters("unreleased-v4") == [("II", ["3"]), ("III", ["4"])]
    assert [label for label, _ in chapters("unreleased-v3")] != ["II", "III"]


def test_form_word_not_letter_only_under_v4():
    # doc 2344: "FORM OF NOTING FOR DISHONOUR." under Form III
    with profile("unreleased-v3"):
        assert S.classify("FORM OF NOTING FOR DISHONOUR.")[:2] == ("form", "FORM OF")
    with profile("unreleased-v4"):
        assert S.classify("FORM OF NOTING FOR DISHONOUR.") is None
        assert S.classify("FORM 'C' [See Rule 3 (6)]")[:2] == ("form", "FORM C")


def test_regulation_then_decimal_child_only_under_v4():
    # Document 3069 p4/block 301252 prints the bare regulation 5 above 5.1.
    source = "5. \n5.1 There shall be constituted a Fund."
    with profile("unreleased-v3"):
        assert len(S.subdivide_spans(source)) == 1
    with profile("unreleased-v4"):
        assert S.subdivide_spans(source) == [
            (0, "5. \n"), (4, "5.1 There shall be constituted a Fund.")]
        # A decimal reference within a sentence must not open a new unit.
        assert len(S.subdivide_spans("5. The rule refers to 5.1 in the Schedule.")) == 1


def test_reviewed_body_start_does_not_turn_body_sentence_into_contents(monkeypatch):
    # Document 3069: the automatic contents detector reads beyond the reviewed
    # first body block, importing sub-regulation 1.1's operative sentence as a
    # heading. The reviewed boundary must also trim that spurious heading.
    texts = ["CONTENTS", "1. ****", "2. Definitions.",
             "1. These Regulations may be called the Example Regulations.",
             "1.1 These Regulations shall come into effect with immediate effect.",
             "2. Definitions. In these Regulations, Fund means the Fund."]
    blocks = [
        {"id": i, "text": value, "page_no": 1 if i < 4 else 2,
         "y0": i * 40.0, "page_height": 800.0, "x0": 70.0, "x1": 500.0}
        for i, value in enumerate(texts, 1)
    ]
    monkeypatch.setattr(S, "parse_contents", lambda _blocks: (
        {"1": "****", "2": "Definitions.",
         "1.1": "These Regulations shall come into effect with immediate effect."},
        len(blocks), True))
    parsed = S.segment(blocks, profile="unreleased-v4",
                       structural_overrides={"source_body_start_block": 4})
    child = next(n for n in parsed.flatten() if n.label == "1.1")
    assert child.text.startswith("These Regulations shall come into effect")
    assert child.heading != child.text


def test_page_top_form_before_schedule_is_not_previous_signature_text():
    # Document 3069 pp13-14: FORM “A” starts the new page above SECOND
    # SCHEDULE, immediately after the First Schedule's unpunctuated signature.
    texts = ["1. Preliminary. These Regulations apply.",
             "2. Scope. Employees may subscribe.",
             "FIRST SCHEDULE", "APPLICATION FOR ENROLMENT",
             "Secretary of the Fund", "FORM “A”", "SECOND SCHEDULE",
             "FORM OF NOMINATION", "I hereby nominate a family member."]
    blocks = [
        {"id": i, "text": value, "page_no": 1 if i <= 5 else 2,
         "y0": (i % 6) * 50.0, "page_height": 800.0,
         "x0": 70.0, "x1": 500.0}
        for i, value in enumerate(texts, 1)
    ]
    parsed = S.segment(blocks, profile="unreleased-v4")
    form = next(n for n in parsed.flatten() if n.kind == "form" and n.label == "FORM A")
    assert form.first_block == 6
    preceding = next(n for n in parsed.flatten() if 5 in n.blocks)
    assert 6 not in preceding.blocks
    assert "FORM “A”" not in preceding.text


def test_source_reviewed_schedule_groups_both_nomination_forms():
    # Document 3069 pp14-15 prints Form A above SECOND SCHEDULE and Form B
    # above a repeated (misspelled) SECOND SCHUDULE heading. Both are variants
    # of the Second Schedule, not content of the First Schedule.
    root = S.Node("instrument", "")
    first_schedule = S.Node("schedule", "FIRST SCHEDULE", first_block=10,
                            blocks=[10, 11], text_parts=["Enrollment form"],
                            parent=root, depth=1, first_page=13, last_page=13)
    form_a = S.Node("form", "FORM A", first_block=12, blocks=[12],
                    parent=root, depth=1, first_page=14, last_page=14)
    second_schedule = S.Node("schedule", "SECOND SCHEDULE", first_block=13,
                             blocks=[13, 14], text_parts=["Nomination for family"],
                             parent=root, depth=1, first_page=14, last_page=14)
    form_b = S.Node("form", "FORM B", first_block=15, blocks=[15, 16],
                    text_parts=["SECOND SCHUDULE", "Nomination without family"],
                    parent=root, depth=1, first_page=14, last_page=15)
    child = S.Node("clause", "1", first_block=17, blocks=[17],
                   text_parts=["Signature"], parent=second_schedule, depth=2)
    second_schedule.children = [child]
    root.children = [first_schedule, form_a, second_schedule, form_b]
    roles = {13: ("heading", second_schedule),
             14: ("body", second_schedule), 15: ("heading", form_b)}
    spec = {"schedule_block_id": 13, "schedule_label": "SECOND SCHEDULE",
            "first_form_block_id": 12, "first_form_label": "FORM A",
            "second_form_block_id": 15, "second_form_label": "FORM B"}
    enacted = S._apply_source_schedule_form_group(root, spec, roles)
    assert enacted["resolution"] == "source_schedule_form_group"
    assert root.children == [first_schedule, second_schedule]
    assert second_schedule.children == [form_a, form_b]
    assert form_a.text == "Nomination for family"
    assert form_a.blocks == [12, 14]
    assert form_a.children == [child] and child.parent is form_a
    assert roles[13][1] is second_schedule and roles[14][1] is form_a
    assert form_b.parent is second_schedule
    assert first_schedule.text == "Enrollment form"
    try:
        S._apply_source_schedule_form_group(root, spec, roles)
    except ValueError:
        pass
    else:
        raise AssertionError("reusing a reviewed grouping must fail closed")


def test_duplicate_witness_fields_stay_form_text_not_two_citations():
    # Document 3069 pp14-15: the two columns each print "1. Signature:";
    # they are blank witness fields, not two clauses labelled 1.
    texts = ["1. Rule. The form follows.", "FORM B", "SECOND SCHUDULE",
             "FORM OF NOMINATION",
             "1. Signature: ___________  \n \n \n1. Signature: ____________ \n"]
    blocks = [
        {"id": i, "text": value, "page_no": 1 if i == 1 else 2,
         "y0": i * 55.0, "page_height": 800.0, "x0": 70.0, "x1": 500.0}
        for i, value in enumerate(texts, 1)
    ]
    parsed = S.segment(blocks, profile="unreleased-v4")
    form = next(n for n in parsed.flatten() if n.kind == "form" and n.label == "FORM B")
    assert not form.children
    assert form.text.count("1. Signature:") == 2
    assert parsed.block_roles[5][1] is form


def _laid_block(i, text, page, x0, x1, y0):
    return {"id": i, "text": text, "page_no": page, "x0": x0, "x1": x1, "y0": y0, "page_height": 842.0}


def test_left_column_margin_heading_only_under_v4():
    # Document 4399 prints no contents and sets each section in three columns:
    # margin heading | number | text. Shape (A): a heading block level with a
    # bare number block; (B): heading lines before "N." inside one block.
    blocks = [
        _laid_block(1, "Short Title and \nCommencement. \n", 1, 73.0, 162.0, 415.0),
        _laid_block(2, "1. \n", 1, 218.0, 230.0, 415.0),
        _laid_block(3, "This Act may be called the Sales Tax (Amendment) Act, 2019. \n", 1, 270.0, 520.0, 415.0),
        _laid_block(4, "Amendment in Section \n1, Act VI of 2015. \n2. \n \nIn the said Act, in section 1, the "
                       "words “except its Tribal Areas” shall be omitted. \n", 1, 77.0, 520.0, 470.0),
        _laid_block(5, "Amendment in Section \n3, Act VI of 2015. \n3. \n \nIn the said Act, in section 3, for "
                       "the word “plan”, the word “place” shall be substituted. \n", 1, 77.0, 520.0, 560.0),
    ]
    v3 = [n for n in S.segment(blocks, profile="unreleased-v3").flatten() if n.kind == "section"]
    assert "Amendment in Section 1" in v3[0].text
    v4 = [n for n in S.segment(blocks, profile="unreleased-v4").flatten() if n.kind == "section"]
    assert [(n.label, n.heading) for n in v4] == [
        ("1", "Short Title and Commencement."),
        ("2", "Amendment in Section 1, Act VI of 2015."),
        ("3", "Amendment in Section 3, Act VI of 2015.")]
    assert not any("Amendment in Section" in n.text for n in v4)


def test_whole_section_quote_only_under_v4():
    # Document 4399's s.3 substitutes the Act's whole s.2 -- 186 definitions
    # over 38 pages -- in one quotation; it is held as s.3's text.
    blocks = [
        _laid_block(1, "1. Short title. This Act may be called the Sales Tax (Amendment) Act, 2019. \n",
                    1, 70.0, 520.0, 100.0),
        _laid_block(2, "2. In the said Act, for Section 2, the following shall be substituted, namely: - \n",
                    1, 70.0, 520.0, 140.0),
        _laid_block(3, "“2. Definitions.-- In this Act, unless there is anything repugnant in the subject "
                       "or context,- \n", 1, 90.0, 520.0, 180.0)]
    for k in range(1, 91):
        blocks.append(_laid_block(3 + k, f"({k}) “term{k}” means the {k}th defined thing; \n",
                                  1 + k // 20, 90.0, 520.0, 200.0 + (k % 20) * 30))
    blocks.append(_laid_block(94, "(91) all other expressions shall have the meaning assigned to them under "
                                  "this section.” \n", 6, 90.0, 520.0, 700.0))
    blocks.append(_laid_block(95, "3. In the said Act, in section 3, for the word “plan”, the word “place” "
                                  "shall be substituted. \n", 6, 70.0, 520.0, 760.0))
    v3 = {n.label: n for n in S.segment(blocks, profile="unreleased-v3").flatten() if n.kind == "section"}
    assert len(v3["2"].children) == 91
    v4 = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten() if n.kind == "section"}
    assert sorted(v4) == ["1", "2", "3"]
    assert not v4["2"].children
    assert "(91) all other expressions" in v4["2"].text
    assert v4["3"].text.startswith("In the said Act, in section 3")


def test_numbered_marked_first_subsection_only_under_v4():
    # Document 1295 p3: "4. / (1) / 6[The Provincial Government] ..." -- no
    # heading dash, so (1) stayed in the section's text while (2) opened.
    blocks = [
        _laid_block(1, "1. Short title. This Act may be called the Smoke Act. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. \n(1) \n6[The Provincial Government] may extend this Act to any area. \n"
                       "(2) Any inhabitant may object in writing. \n", 1, 72.0, 480.0, 80.0)]
    v3 = {(n.kind, n.label): n for n in S.segment(blocks, profile="unreleased-v3").flatten()}
    assert v3[("section", "2")].text.startswith("(1)")
    v4 = {(n.kind, n.label): n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert v4[("section", "2")].text == ""
    assert v4[("subsection", "1")].text.startswith("6[The Provincial Government]")


def test_quoted_first_definition_only_under_v4():
    # Document 1295 s.3: 'In this Act-- / (1) / "furnace" means ...'.
    blocks = [
        _laid_block(1, "1. Short title. This Act may be called the Smoke Act. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "3. In this Act-- \n \n(1) \n“furnace” means any furnace used for engines; \n"
                       "(2) \n“Inspector” means a Chief Inspector; \n", 1, 72.0, 480.0, 80.0)]
    v3 = {n.label: n for n in S.segment(blocks, profile="unreleased-v3").flatten()}
    assert "(1)" in v3["3"].text
    v4 = {(n.kind, n.label): n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert v4[("section", "3")].text == "In this Act--"
    assert v4[("subsection", "1")].text.startswith("“furnace” means")


def test_marked_suffixed_definition_only_under_v4():
    # Document 1295 p3 prints the inserted definition '2[(1A)] "Flue" ...'.
    blocks = [
        _laid_block(1, "1. Short title. This Act may be called the Smoke Act. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "3. In this Act,- \n(1) “furnace” means any furnace used for engines; \n"
                       "2[(1A)] “Flue” means any flue joined to a furnace;] \n"
                       "(2) “Inspector” means a Chief Inspector; \n", 1, 72.0, 480.0, 80.0)]
    v3 = [n.label for n in S.segment(blocks, profile="unreleased-v3").flatten()]
    assert "1A" not in v3
    v4 = [n.label for n in S.segment(blocks, profile="unreleased-v4").flatten()]
    assert "1A" in v4


def test_bare_trailing_label_cut_only_under_v4():
    # Document 2452's contents prints "20. Regulations. / 21." -- row 21 has
    # no name, and its bare label had joined row 20's heading.
    blocks = [
        _laid_block(1, "CONTENTS \n1. Short title. \n2. Definitions. \n3. Regulations. \n4. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. This Act may be called the Smoke Act. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(3, "2. Definitions. In this Act words have their meanings. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(4, "3. The Board may make regulations. \n", 2, 72.0, 480.0, 160.0),
        _laid_block(5, "4. The Board may make rules. \n", 2, 72.0, 480.0, 200.0)]
    v3 = {n.label: n for n in S.segment(blocks, profile="unreleased-v3").flatten()}
    assert v3["3"].heading == "Regulations. 4."
    v4 = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert v4["3"].heading == "Regulations."


def test_apparatus_over_margin_heading_only_under_v4():
    # Document 2452: a margin-note block a reviewed reading sets aside as
    # apparatus stayed a margin heading and was hung on the page's first unit.
    tail = " and the words run on to fill a long printed line of the page"
    blocks = [
        _laid_block(1, "CONTENTS \n1. Short title. \n2. Definitions. \n3. Board of Governors. \n",
                    1, 72.0, 400.0, 40.0),
        _laid_block(2, "1. This Act may be called the Smoke Act" + tail + ". \n", 2, 72.0, 400.0, 100.0),
        _laid_block(3, "2. In this Act the Board means the Board of Governors" + tail + ". \n",
                    2, 72.0, 400.0, 160.0),
        _laid_block(4, "Board of Governors. \n", 2, 430.0, 520.0, 100.0),
        _laid_block(5, "3. The Board shall consist of five members" + tail + ". \n", 2, 72.0, 400.0, 300.0)]
    overrides = {"source_apparatus_blocks": [4]}
    v3 = S.segment(blocks, profile="unreleased-v3", structural_overrides=overrides)
    assert v3.block_roles[4][0] == "heading"
    v4 = S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
    assert v4.block_roles[4][0] != "heading"


def test_dotted_omission_stub_cut_only_under_v4():
    # Document 3805 p3 prints s.3 as the stub '5[3. .........]' on the line
    # after s.2(d)'s stub, in the same block.
    blocks = [
        _laid_block(1, "1. Short title. This Act may be called the Finance Act. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. In this Act,- \n(c) “tax” means the tax; \n4[(d) .. .. ..] \n5[3. \n.........] \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, "4. The tax shall be levied on every fare. \n", 1, 72.0, 480.0, 120.0)]
    v3 = [(n.kind, n.label) for n in S.segment(blocks, profile="unreleased-v3").flatten()]
    assert ("section", "3") not in v3
    v4 = [(n.kind, n.label) for n in S.segment(blocks, profile="unreleased-v4").flatten()]
    assert ("section", "3") in v4


def test_ordinal_schedule_reference_only_under_v4():
    # Document 3805 p9: "SECOND SCHEDULE" / "(See Section 4)" after the First
    # Schedule's last cell, which has no stop.
    blocks = [
        _laid_block(1, "1. Short title. This Act may be called the Finance Act. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. The tax shall be levied at the rates in the Schedules. \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "FIRST SCHEDULE \n(See section 2) \n", 2, 72.0, 480.0, 40.0),
        _laid_block(4, "1. On each ticket 1 1/2 percent of such total \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "SECOND SCHEDULE \n", 3, 72.0, 480.0, 40.0),
        _laid_block(6, "(See Section 4) \n", 3, 72.0, 480.0, 80.0),
        _laid_block(7, "1. On each licence Rupees one thousand \n", 3, 72.0, 480.0, 120.0)]
    v3 = [n.label for n in S.segment(blocks, profile="unreleased-v3").flatten() if n.kind == "schedule"]
    assert v3 == ["FIRST SCHEDULE"]
    v4 = [n.label for n in S.segment(blocks, profile="unreleased-v4").flatten() if n.kind == "schedule"]
    assert v4 == ["FIRST SCHEDULE", "SECOND SCHEDULE"]


def test_enacting_formula_not_member_list_only_under_v4():
    # Document 4296's Preamble (f) ends "It is hereby enacted as follows:-";
    # that introduces the Act, not a numbered list owned by (f).
    node = S.Node(kind="clause", label="f",
                  text_parts=["to provide for matters connected therewith; It is hereby enacted as follows:-"])
    for name, expected in (("unreleased-v3", True), ("unreleased-v4", False)):
        token = S._ACTIVE_PROFILE_RULES.set(S.SEGMENTATION_PROFILES[name])
        try:
            assert S._introduces_member_list(node) is expected
        finally:
            S._ACTIVE_PROFILE_RULES.reset(token)


def test_dotted_contents_row_cut_only_under_v4():
    # Document 4296's contents prints row 26 as "26." and a spaced dotted line;
    # it had joined row 25's heading.
    blocks = [
        _laid_block(1, "CONTENTS \n1. Short title. \n2. Pre-operational steps. \n3. . . . . . \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. This Act may be called the Bank Act. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(3, "2. Pre-operational steps. The Bank shall take steps. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(4, "3. The Bank shall keep accounts. \n", 2, 72.0, 480.0, 160.0)]
    v3 = {n.label: n for n in S.segment(blocks, profile="unreleased-v3").flatten()}
    assert v3["2"].heading != "Pre-operational steps."
    v4 = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert v4["2"].heading == "Pre-operational steps."


def test_reparent_parent_section_label_picks_one_of_several_same_block_parents():
    # Document 4296 block 666480 opens 17(1), 18(1) and 19(1); s.19's (o)
    # belongs under 19(1) and only the section label tells the three apart.
    root = S.Node(kind="instrument", label="")
    parents = {}
    for number in ("17", "18", "19"):
        section = S.Node(kind="section", label=number, first_block=666480, parent=root)
        root.children.append(section)
        sub = S.Node(kind="subsection", label="1", first_block=666480, parent=section)
        section.children.append(sub)
        parents[number] = sub
    item = S.Node(kind="clause", label="o", first_block=666490, parent=root.children[-1])
    root.children[-1].children.append(item)
    spec = {"source_block_id": 666490, "parent_block_id": 666480, "kind": "clause",
            "source_label": "o", "parent_label": "1", "parent_kind": "subsection"}
    try:
        S._apply_source_reparents(root, [dict(spec)], [], {})
    except ValueError:
        pass
    else:
        raise AssertionError("three same-block parents must fail closed")
    S._apply_source_reparents(root, [dict(spec, parent_section_label="19")], [], {})
    assert item.parent is parents["19"]


def test_serial_header_rows_and_last_promised_section_only_under_v4():
    # Document 3142: rule 11 ends with an 'S.NO. ...' column header and its rows
    # '01', '02' are table rows (serial_column_header_owner); rule 12 is printed
    # after the Schedule and resumes the body (last_promised_section_after_schedule).
    contents = "CONTENTS \n1. Short title. \n2. Ground for penalty. \n3. Appointment of Authority. \nSCHEDULE \n4. Repeal. \n"
    blocks = [
        _laid_block(1, contents, 1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. These rules may be called the Staff Rules. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(3, "2. Ground for penalty: Where an employee is inefficient he may be penalised. \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(4, "3. Appointment of Authority. The authorities are as follows: \n"
                       "S.NO. POWER IN RESPECT OF AUTHORISED OFFICER AUTHORITY. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(5, "01. Officer in BPS-17 Managing Director Chairman \n", 2, 72.0, 480.0, 160.0),
        _laid_block(6, "02. Officer in BPS-16 Deputy Director Managing Director \n", 2, 72.0, 480.0, 200.0),
        _laid_block(7, "SCHEDULE \n(See rule 3) \n", 3, 72.0, 480.0, 40.0),
        _laid_block(8, "01. Chairman. Chairman for Review \n", 3, 72.0, 480.0, 80.0),
        _laid_block(9, "4. Repeal. The Staff Rules, 1973 are repealed. \n", 3, 72.0, 480.0, 120.0)]
    v3 = [(n.kind, n.label) for n in S.segment(blocks, profile="unreleased-v3").flatten()]
    assert ("section", "01") in v3 and ("clause", "4") in v3
    v4 = [(n.kind, n.label) for n in S.segment(blocks, profile="unreleased-v4").flatten()]
    assert ("section", "01") not in v4 and ("clause", "01") in v4
    assert v4[-1] == ("section", "4")


def test_colon_closed_contents_heading_only_under_v4():
    # Document 3142 rule 3 prints "Ground for penalty: Where a SASO employee,
    # in the opinion of the authority:"; the heading ends at the first colon.
    flat = "Ground for penalty: Where a SASO employee, in the opinion of the authority:"
    cut = len("Ground for penalty:")
    without = S.SEGMENTATION_PROFILES["unreleased-v4"] - {"colon_closed_contents_heading"}
    token = S._ACTIVE_PROFILE_RULES.set(without)
    try:
        extended = S._printed_heading_extent(flat, cut)
    finally:
        S._ACTIVE_PROFILE_RULES.reset(token)
    token = S._ACTIVE_PROFILE_RULES.set(S.SEGMENTATION_PROFILES["unreleased-v4"])
    try:
        assert S._printed_heading_extent(flat, cut) is None
    finally:
        S._ACTIVE_PROFILE_RULES.reset(token)
    assert extended is not None


def test_contents_row_decimal_cut_only_under_v4():
    # Document 3103 prints decimal paragraphs mid-block ("2.1 Provincial
    # Committee: ..."); its contents prints each as a one-line row.
    blocks = [
        _laid_block(1, "CONTENTS \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. BACKGROUND \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "2. COMMITTEES \n", 1, 72.0, 480.0, 120.0),
        _laid_block(4, "2.1 Provincial Committee \n", 1, 72.0, 480.0, 160.0),
        _laid_block(5, "2.2 District Committee \n", 1, 72.0, 480.0, 200.0),
        _laid_block(6, "1. BACKGROUND Stray dogs pose problems. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(7, "2. COMMITTEES \n2.1 Provincial Committee: The committee shall consist of members. \n"
                       "2.2 District Committee: The committee shall be notified. \n", 2, 72.0, 480.0, 80.0)]
    v3 = {n.label: n for n in S.segment(blocks, profile="unreleased-v3").flatten()}
    assert "2.1 Provincial" in v3["2"].text
    v4 = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert v4["2"].text == ""
    assert v4["2.1"].heading == "Provincial Committee"


def test_titled_appended_form_and_definition_lead_only_under_v4():
    # Document 3064: the Order's form is headed by an upper-case title with no
    # FORM label (titled_appended_form), and "2. In this Order:-" is the
    # definitions' lead-in, not a heading (definition_lead_not_heading).
    blocks = [
        _laid_block(1, "1. (1) This order may be called the Meat Order. \n(2) It shall come into force at once. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. In this Order:- \n(i) “Inspector” means an officer; \n(ii) “Meat” means cooked meat. \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, "3. A Licence shall be issued in the form appended to this Order. \n", 1, 72.0, 480.0, 120.0),
        _laid_block(4, "LICENCE UNDER THE MEAT ORDER, 1978 \n1. The licensee shall keep a register. \n",
                    2, 72.0, 480.0, 40.0),
        _laid_block(5, "2. The licensee shall display prices. \n", 2, 72.0, 480.0, 80.0)]
    v3 = S.segment(blocks, profile="unreleased-v3").flatten()
    assert not any(n.kind == "form" for n in v3)
    assert next(n for n in v3 if n.kind == "section" and n.label == "2").heading == "In this Order"
    v4 = S.segment(blocks, profile="unreleased-v4").flatten()
    form = next(n for n in v4 if n.kind == "form")
    assert form.label == "LICENCE UNDER THE MEAT ORDER, 1978"
    assert [c.label for c in form.children] == ["1", "2"]
    assert next(n for n in v4 if n.kind == "section" and n.label == "2").heading is None


def test_schedule_amendment_item_helper():
    # Document 2739's amending Schedule items "N. / In section X, ... shall be
    # substituted." continue the schedule's numbering and are law.
    schedule = S.Node(kind="schedule", label="SCHEDULE")
    schedule.children.append(S.Node(kind="clause", label="1", parent=schedule))
    item = "2. \nIn section 4, for the words “Director” the words “Authority” shall be substituted. \n"
    assert S._schedule_amendment_item(schedule, item)
    assert not S._schedule_amendment_item(schedule, item.replace("2.", "5.", 1))
    quoted_only = "2. \nIn section 4, “the words shall be substituted” are printed. \n"
    assert not S._schedule_amendment_item(schedule, quoted_only)


def test_quoted_part_span_only_under_v4():
    # Document 2621 substitutes a quoted Schedule Part over several pages; its
    # items stayed clauses and sections of the amending Act.
    blocks = [
        _laid_block(1, "1. Short title. This Act may be called the Amendment Act. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. In the said Ordinance, in Schedule II, for Part 1, the following shall be substituted:— \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, "“PART—I \n“FUNCTIONS TO BE PERFORMED BY THE CORPORATION. \n", 1, 72.0, 480.0, 120.0),
        _laid_block(4, "1. Water supply. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(5, "2. Drainage. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(6, "3. Street lighting. \n", 3, 72.0, 480.0, 40.0),
        _laid_block(7, "4. Parks and gardens.” \n", 4, 72.0, 480.0, 40.0),
        _laid_block(8, "3. In the said Ordinance, in Schedule V, the word “and” shall be omitted. \n",
                    4, 72.0, 480.0, 80.0)]
    v3 = [(n.kind, n.label) for n in S.segment(blocks, profile="unreleased-v3").flatten()]
    assert ("section", "4") in v3
    v4 = [(n.kind, n.label) for n in S.segment(blocks, profile="unreleased-v4").flatten()]
    assert v4 == [("section", "1"), ("section", "2"), ("section", "3")]


def test_body_start_without_contents_only_under_v4():
    # Document 4639, a Gazette copy, prints Act XL of 1975 before Act XLI and
    # no contents list; a reviewed body start at Act XLI's title makes Act XL
    # preface.
    blocks = [
        _laid_block(1, "ACT No. XL OF 1975 \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. This Act may be called the Explosive Substances (Amendment) Act, 1975. \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, "2. In section 3, for the words “ten years” the words “life” shall be substituted. \n",
                    1, 72.0, 480.0, 120.0),
        _laid_block(4, "ACT No. XLI of 1975 \n", 2, 72.0, 480.0, 40.0),
        _laid_block(5, "1. Short title. This Act may be called the Baluchistan Constabulary Act, 1975. \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(6, "2. Definitions. In this Act words have their meanings. \n", 2, 72.0, 480.0, 120.0)]
    overrides = {"source_body_start_block": 4}
    v3 = S.segment(blocks, profile="unreleased-v3", structural_overrides=overrides)
    assert "Explosive" in next(n for n in v3.flatten() if n.label == "1").text
    v4 = S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
    assert [(n.kind, n.label) for n in v4.flatten()] == [("section", "1"), ("section", "2")]
    assert "Constabulary" in v4.flatten()[0].text
    assert all(v4.block_roles[i][0] == "preface" for i in (1, 2, 3))


def test_number_abbreviation_line_end_only_where_the_no_line_is_item_n_minus_1():
    # Document 3803 Appendix 1.2: "2. National Identity Card No. / 3. District."
    text = "1. Name of the licensee. \n2. National Identity Card No. \n3. District. \n"
    with profile("unreleased-v4"):
        assert any(u.lstrip().startswith("3.") for u in S.subdivide(text))
    without = S.SEGMENTATION_PROFILES["unreleased-v4"] - {"number_abbreviation_line_end"}
    token = S._ACTIVE_PROFILE_RULES.set(without)
    try:
        assert not any(u.lstrip().startswith("3.") for u in S.subdivide(text))
    finally:
        S._ACTIVE_PROFILE_RULES.reset(token)


def test_reparent_ordinal_picks_one_of_two_same_block_same_label_nodes():
    # Document 4447 block 810168 holds s.73(1)'s two provisos; the second
    # proviso's items belong under it, and only the order tells them apart.
    root = S.Node(kind="instrument", label="")
    sub = S.Node(kind="subsection", label="1", first_block=810160, parent=root)
    root.children.append(sub)
    first = S.Node(kind="proviso", label="Provided", first_block=810168, parent=sub)
    second = S.Node(kind="proviso", label="Provided", first_block=810168, parent=sub)
    item = S.Node(kind="clause", label="a", first_block=810169, parent=sub)
    sub.children.extend([first, second, item])
    spec = {"source_block_id": 810169, "parent_block_id": 810168, "kind": "clause",
            "source_label": "a", "parent_label": "Provided"}
    try:
        S._apply_source_reparents(root, [dict(spec)], [], {})
    except ValueError:
        pass
    else:
        raise AssertionError("two same-block parents must fail closed")
    S._apply_source_reparents(root, [dict(spec, parent_ordinal=2)], [], {})
    assert item.parent is second


def _tail_blocks(with_schedule: bool = True):
    # Document 128 (Balochistan Land Laws (Amendment) Act, 2009) p5: after the
    # amending Schedule's last item the Act prints, at full width, with no
    # number and no contents row, "Repeal: ... are hereby repealed."
    head = [
        _laid_block(1, "1. Short title. This Act may be called the Land Laws (Amendment) Act, 2009. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Amendment of certain laws. The laws specified in the Schedule are amended "
                       "to the extent specified in it. \n", 1, 72.0, 480.0, 80.0)]
    schedule = [
        _laid_block(3, "SCHEDULE \n", 2, 72.0, 480.0, 40.0),
        _laid_block(4, "1. In section 3, clause (h) shall be deleted. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "2. In section 161, for the words “Revenue Tribunal” the word “Commissioner” "
                       "shall be substituted. \n", 2, 72.0, 480.0, 120.0)]
    tail = [_laid_block(6, "Repeal: The Land Laws (Amendment) Ordinance, 2001 is hereby repealed. \n",
                        2, 72.0, 480.0, 160.0)]
    return head + (schedule if with_schedule else []) + tail


def _tail_opener(**changes):
    opener = {"source_block_id": 6, "label": "Repeal", "heading": "Repeal",
              "source_prefix": "Repeal:", "after_section_label": "__AFTER_SCHEDULE__"}
    return {"source_unnumbered_section_openers": [dict(opener, **changes)]}


def test_unnumbered_tail_provision_only_under_v4():
    blocks = _tail_blocks()
    # Without the reviewed opener the Repeal is read into the Schedule's last item.
    plain = S.segment(blocks, profile="unreleased-v4").flatten()
    assert plain[-1].kind == "clause" and plain[-1].text.endswith("hereby repealed.")
    seg = S.segment(blocks, profile="unreleased-v4", structural_overrides=_tail_opener())
    nodes = seg.flatten()
    assert [(n.kind, n.label, n.parent.kind) for n in nodes] == [
        ("section", "1", "instrument"), ("section", "2", "instrument"),
        ("schedule", "SCHEDULE", "instrument"), ("clause", "1", "schedule"),
        ("clause", "2", "schedule"), ("section", "Repeal", "instrument")]
    repeal = nodes[-1]
    assert repeal.heading == "Repeal" and repeal.first_block == 6
    assert repeal.text == "The Land Laws (Amendment) Ordinance, 2001 is hereby repealed."
    assert nodes[-2].text.endswith("shall be substituted.")
    assert seg.block_roles[6][0] == "body"
    # The sentinel is unknown to v3's opener, which fails closed.
    try:
        S.segment(blocks, profile="unreleased-v3", structural_overrides=_tail_opener())
    except ValueError as error:
        assert "source unnumbered section 6" in str(error)
    else:
        raise AssertionError("v3 must refuse an __AFTER_SCHEDULE__ opener")


def test_unnumbered_tail_provision_refuses_without_matching_evidence():
    refused = [
        (_tail_blocks(), _tail_opener(label="3")),                 # a number is never invented
        (_tail_blocks(), _tail_opener(label="Repeals")),           # not the printed lead word
        (_tail_blocks(), _tail_opener(heading="Saving")),          # heading is not the printed one
        (_tail_blocks(), _tail_opener(source_prefix="Repealed:")),  # prefix is not in the source
        (_tail_blocks(with_schedule=False), _tail_opener()),       # no Schedule is open
    ]
    for blocks, overrides in refused:
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert "source unnumbered tail provision 6" in str(error)
        else:
            raise AssertionError(f"accepted {overrides}")


def test_unnumbered_provision_marker():
    from nizam.shared.corpus_types import is_unnumbered_provision
    assert is_unnumbered_provision("section", "Repeal")
    for kind, label in (("section", "302"), ("section", "4A"), ("section", "۱۲"),
                        ("section", "٣"), ("section", "IV"), ("section", "x"),
                        ("subsection", "1"), ("clause", "a"), ("proviso", "Provided"),
                        ("preamble", "Preamble"), ("schedule", "SCHEDULE")):
        assert not is_unnumbered_provision(kind, label), (kind, label)


def _notification_blocks():
    # Document 268 p1 and p6 (expression 1, the 2003 notification): the only
    # operative text is the unnumbered clause under the caption AMENDMENTS,
    # then the appended SCHEDULE.
    return [
        _laid_block(1, "NOTIFICATION \nNo. SOR-III-1-10/95.- In exercise of the power conferred upon him, "
                       "the Governor is pleased to direct that in the Service Rules, 1996 the following \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "amendments shall be made:- \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "AMENDMENTS \n", 1, 72.0, 480.0, 120.0),
        _laid_block(4, "  \n \nFor the existing Schedule the Schedules appended here to shall be substituted \n",
                    1, 72.0, 480.0, 160.0),
        _laid_block(5, "SCHEDULE \n", 2, 72.0, 480.0, 40.0),
        _laid_block(6, "Name of the Post Appointing authority Method of Recruitment \n", 2, 72.0, 480.0, 80.0)]


def _root_opener(source_block_id=3, **changes):
    opener = {"source_block_id": source_block_id, "label": "AMENDMENTS", "heading": "AMENDMENTS",
              "source_prefix": "AMENDMENTS", "after_section_label": "__ROOT__"}
    return {"source_unnumbered_section_openers": [dict(opener, **changes)]}


def test_unnumbered_root_provision_word_label_and_appended_schedule():
    blocks = _notification_blocks()
    # Without the reviewed opener nothing opens: the clause is preface.
    assert S.segment(blocks, profile="unreleased-v4").flatten() == []
    seg = S.segment(blocks, profile="unreleased-v4", structural_overrides=_root_opener())
    nodes = seg.flatten()
    assert [(n.kind, n.label, n.parent.kind) for n in nodes] == [
        ("section", "AMENDMENTS", "instrument"), ("schedule", "SCHEDULE", "instrument")]
    assert nodes[0].heading == "AMENDMENTS"
    assert nodes[0].text == "For the existing Schedule the Schedules appended here to shall be substituted"
    assert nodes[1].text.startswith("Name of the Post")
    assert [seg.block_roles[i][0] for i in (1, 2, 3, 4)] == ["preface", "preface", "body", "body"]
    try:
        S.segment(blocks, profile="unreleased-v3", structural_overrides=_root_opener())
    except ValueError as error:
        assert "source unnumbered section 3" in str(error)
    else:
        raise AssertionError("v3 must refuse a word-label __ROOT__ opener")


def test_unnumbered_root_provision_refuses_without_matching_evidence():
    blocks = _notification_blocks()
    refused = [
        _root_opener(label="Amendment"),             # not the printed caption
        _root_opener(heading="Substitution"),        # heading is not the printed one
        _root_opener(source_prefix="AMENDMENT:"),    # prefix is not in the source
        _root_opener(source_block_id=4, label="For", heading="For", source_prefix="For"),
    ]
    for overrides in refused[:3]:
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert "source unnumbered root provision 3" in str(error)
        else:
            raise AssertionError(f"accepted {overrides}")
    # "For" is a printed lead word, but a unit (AMENDMENTS) must not already be open.
    both = {"source_unnumbered_section_openers": (
        _root_opener()["source_unnumbered_section_openers"]
        + refused[3]["source_unnumbered_section_openers"])}
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides=both)
    except ValueError as error:
        assert "source unnumbered root provision 4" in str(error)
    else:
        raise AssertionError("a root opener after an open unit was accepted")


def _order_blocks():
    # Document 268 p3 (expression 2, the 1998 Order): para 1 printed with no
    # number, para 2 printed "2." in the same block.
    return [
        _laid_block(1, "Government of the Punjab \nExcise & Taxation Department \nDated Lahore, The 30 th Dec, 1998 \n",
                    1, 300.0, 480.0, 40.0),
        _laid_block(2, "ORDER \n \n \n \nNo.SOAI(E&T)3-10/93. The Government of the Punjab is pleased to upgrade "
                       "the existing \nfive(05) posts of Accountants (BS-16) to BS-17 with immediate effect. \n \n2. \n"
                       "He is further pleased to re-designate these posts as Assistant Director with immediate "
                       "effect. \n", 1, 72.0, 480.0, 80.0)]


DECISION = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-06-b.json",
            "document_id": 268, "question_id": "q1"}


def _para_opener(**changes):
    opener = {"source_block_id": 2, "label": "1", "heading": "",
              "source_prefix": "ORDER No.SOAI(E&T)3-10/93.", "after_section_label": "__ROOT__",
              "owner_decision": DECISION}
    return {"source_unnumbered_section_openers": [{k: v for k, v in dict(opener, **changes).items()
                                                   if v is not None}]}


def test_unnumbered_root_provision_owner_numbered_paragraph():
    blocks = _order_blocks()
    assert [n.label for n in S.segment(blocks, profile="unreleased-v4").flatten()] == ["2"]
    nodes = S.segment(blocks, profile="unreleased-v4", structural_overrides=_para_opener()).flatten()
    assert [(n.kind, n.label, n.heading, n.parent.kind) for n in nodes] == [
        ("section", "1", None, "instrument"), ("section", "2", None, "instrument")]
    assert nodes[0].text == ("The Government of the Punjab is pleased to upgrade the existing five(05) "
                             "posts of Accountants (BS-16) to BS-17 with immediate effect.")
    assert nodes[1].text.startswith("He is further pleased")
    # A number needs the owner's decision: without the citation the old
    # __ROOT__ opener asks for contents evidence and refuses.
    for overrides, message in (
            (_para_opener(owner_decision=None), "source unnumbered section 2"),
            (_para_opener(owner_decision={"export": "x.json", "document_id": 268}),
             "source unnumbered root provision 2"),
            (_para_opener(label="2"), "source unnumbered root provision 2"),
            (_para_opener(heading="ORDER"), "source unnumbered root provision 2")):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert message in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")


def test_owner_decision_citation_is_checked_against_the_export(tmp_path):
    from nizam.workers.segment import owner_decision_answer, unnumbered_opener_shape_ok
    opener = _para_opener()["source_unnumbered_section_openers"][0]
    assert unnumbered_opener_shape_ok(opener)
    assert not unnumbered_opener_shape_ok({k: v for k, v in opener.items() if k != "owner_decision"})
    assert unnumbered_opener_shape_ok(_tail_opener()["source_unnumbered_section_openers"][0])
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [
        {"document_id": 268, "question_id": "q1", "choice": "other", "note": "para 1 / para 2"}]}),
        encoding="utf-8")
    citation = {"export": str(export), "document_id": 268, "question_id": "q1"}
    assert owner_decision_answer(citation, 268)["choice"] == "other"
    for bad, document_id in ((dict(citation, question_id="q2"), 268), (citation, 128),
                             (dict(citation, export=str(tmp_path / "missing.json")), 268),
                             ({"export": str(export), "document_id": 268}, 268)):
        try:
            owner_decision_answer(bad, document_id)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted {bad}")


def _v4_without(monkeypatch, *rules):
    # unreleased-v4 with only the named rules switched off: the test shows
    # what each rule itself changes, not what all of v4 changes over v3.
    name = "unreleased-v4-without-" + "-".join(rules)
    monkeypatch.setitem(S.SEGMENTATION_PROFILES, name, S.SEGMENTATION_PROFILES["unreleased-v4"] - set(rules))
    return name


def _nest(seg):
    return [(n.kind, n.label, n.parent.kind, n.parent.label) for n in seg.flatten()]


def _cpc_act():
    return [_laid_block(1, "1. Short title. This Act may be called the Code of Civil Procedure, 1908. \n",
                        1, 72.0, 480.0, 40.0),
            _laid_block(2, "2. Definitions. In this Act words have the meanings given to them. \n",
                        1, 72.0, 480.0, 80.0)]


def test_starred_letter_stub_cut_only_under_v4(monkeypatch):
    # Document 4490 s.104(1) p83 prints the omitted clauses (b)-(e) each on
    # its own line, the label then the stars; they stayed inside (a).
    blocks = _cpc_act() + [_laid_block(
        3, "3. Orders from which appeal lies.– An appeal shall lie from the following orders:- \n"
           "3[(a) \n* * * \n(b) \n* * * \n(c) \n* * *] \n(f) an order under rule 2 of Order XXXIX; \n",
        1, 72.0, 480.0, 120.0)]
    off = [n.label for n in S.segment(blocks, profile=_v4_without(monkeypatch, "starred_letter_stub_cut")).flatten()]
    assert off == ["1", "2", "3", "f"]
    nodes = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert [n for n in nodes] == ["1", "2", "3", "b", "c", "f"]
    assert nodes["b"].parent is nodes["3"] and nodes["b"].text == "* * *"
    assert nodes["3"].text.endswith("3[(a) * * *")


def _cpc_contents_status_row():
    # Document 4490: contents row 25 prints only "Omitted"; Order XLI rule 25
    # prints "... has omitted to frame ... any issue".
    return [
        _laid_block(1, "CONTENTS \n1. Short title. \n2. Omitted \n3. Courts to try all civil suits. \n"
                       "THE FIRST SCHEDULE \nORDER I \n1. Who may be joined as plaintiffs. \n"
                       "2. Power of Court to order separate trials. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. This Act may be called the Code of Civil Procedure, 1908. \n",
                    2, 72.0, 480.0, 40.0),
        _laid_block(3, "2. Presidency Small Cause Courts.– * * * \n", 2, 72.0, 480.0, 80.0),
        _laid_block(4, "3. Courts to try all civil suits.– The Courts shall have jurisdiction to try all suits. \n",
                    2, 72.0, 480.0, 120.0),
        _laid_block(5, "THE FIRST SCHEDULE \n", 3, 72.0, 480.0, 40.0),
        _laid_block(6, "ORDER I \nPARTIES OF SUITS \n", 3, 72.0, 480.0, 80.0),
        _laid_block(7, "1. Who may be joined as plaintiffs.– All persons may be joined in one suit as plaintiffs. \n",
                    3, 72.0, 480.0, 120.0),
        _laid_block(8, "2. Power of Court to order separate trials.– Where the Court has omitted to frame any "
                       "issue, the Court may order separate trials. \n", 3, 72.0, 480.0, 160.0)]


def test_status_row_order_only_under_v4(monkeypatch):
    blocks = _cpc_contents_status_row()

    def row_two(seg):
        entry = [e for e in seg.toc_entries if e["label"] == "2"][0]
        return entry["heading"], entry["node"].kind, entry["node"].parent.kind

    off = S.segment(blocks, profile=_v4_without(monkeypatch, "status_row_order_only"))
    assert row_two(off) == ("Omitted", "clause", "order")      # the word matched inside rule 2
    assert row_two(S.segment(blocks, profile="unreleased-v4")) == ("Omitted", "section", "instrument")


def _first_schedule(*rule_blocks):
    return _cpc_act() + [_laid_block(3, "THE FIRST SCHEDULE \n", 2, 72.0, 480.0, 40.0)] + list(rule_blocks)


def test_order_rule_owns_subrules_only_under_v4(monkeypatch):
    # Document 4490 First Schedule: sub-rules (2) of rules 1 and 2 of Order I
    # unwound past their rules and became the Order's children.
    blocks = _first_schedule(
        _laid_block(4, "ORDER I \nPARTIES OF SUITS \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "1. Who may be joined as plaintiffs.– (1) All persons may be joined in one suit as "
                       "plaintiffs. \n(2) Any other person may be joined as a plaintiff. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(6, "2. Power of Court to order separate trials.– (1) Where it appears to the Court that any "
                       "joinder may embarrass the trial, the Court may order separate trials. \n(2) The Court may "
                       "make such other order as may be expedient. \n", 2, 72.0, 480.0, 200.0))
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "order_rule_owns_subrules")))
    assert ("subsection", "2", "order", "ORDER I") in off
    on = _nest(S.segment(blocks, profile="unreleased-v4"))
    assert on[-4:] == [("clause", "1", "order", "ORDER I"), ("subsection", "2", "clause", "1"),
                       ("clause", "2", "order", "ORDER I"), ("subsection", "2", "clause", "2")]


def test_marked_order_heading_only_under_v4(monkeypatch):
    # Document 4490 prints inserted Orders behind their note marker: "2[ORDER IV-A".
    blocks = _first_schedule(
        _laid_block(4, "ORDER IV \nINSTITUTION OF SUITS \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "1. Suit to be commenced by plaint.– Every suit shall be instituted by presenting a "
                       "plaint. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(6, "2[ORDER IV-A \nCONSOLIDATION OF SUITS \n", 3, 72.0, 480.0, 40.0),
        _laid_block(7, "1. Consolidation of suits.– Where two or more suits are pending in the same Court, the "
                       "Court may order their consolidation. \n", 3, 72.0, 480.0, 80.0))
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "marked_order_heading")))
    assert off[-2:] == [("clause", "1", "order", "ORDER IV"), ("clause", "1", "order", "ORDER IV")]
    on = S.segment(blocks, profile="unreleased-v4")
    assert _nest(on)[-2:] == [("order", "ORDER IV-A", "schedule", "FIRST SCHEDULE"),
                              ("clause", "1", "order", "ORDER IV-A")]
    assert [n.heading for n in on.flatten() if n.kind == "order"] == ["INSTITUTION OF SUITS",
                                                                      "CONSOLIDATION OF SUITS"]


def test_amendment_word_heading_not_note_only_under_v4(monkeypatch):
    # Document 4490 Order V rule 20 p111: the heading "Substituted service."
    # read as a note ("N Substituted ...") and the rule vanished.
    blocks = _first_schedule(
        _laid_block(4, "ORDER V \nISSUE AND SERVICE OF SUMMONS \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "19. Examination of serving officer.– Where a summons is returned the Court shall examine "
                       "the serving officer. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(6, "20. \nSubstituted service.– 1[(1) Where the Court is satisfied that the defendant is "
                       "keeping out of the way, the Court shall order the summons to be served by affixing a "
                       "copy. \n", 2, 72.0, 480.0, 200.0))
    off = [n.label for n in S.segment(blocks, profile=_v4_without(
        monkeypatch, "amendment_word_heading_not_note")).flatten()]
    assert "20" not in off
    on = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert on["20"].text.startswith("Substituted service.")
    # a note is still a note
    with profile("unreleased-v4"):
        assert S._FOOTNOTE.match("20 Substituted by the Code of Civil Procedure (Amendment) Act, 1976.")


def test_ordinal_schedule_closes_part_only_under_v4(monkeypatch):
    # Document 4490: THE FIRST SCHEDULE after s.159 of Part XI was nested under Part XI.
    blocks = _cpc_act() + [
        _laid_block(3, "PART XI \nMISCELLANEOUS \n", 2, 72.0, 480.0, 40.0),
        _laid_block(4, "158. Reference to Code of Civil Procedure.– In every enactment a reference shall be read "
                       "as a reference to this Code. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "THE FIRST SCHEDULE \n", 3, 72.0, 480.0, 40.0),
        _laid_block(6, "ORDER I \nPARTIES OF SUITS \n", 3, 72.0, 480.0, 80.0),
        _laid_block(7, "1. Who may be joined as plaintiffs.– All persons may be joined in one suit as "
                       "plaintiffs. \n", 3, 72.0, 480.0, 120.0)]
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "ordinal_schedule_closes_part")))
    assert ("schedule", "FIRST SCHEDULE", "part", "XI") in off
    on = _nest(S.segment(blocks, profile="unreleased-v4"))
    assert ("schedule", "FIRST SCHEDULE", "instrument", "") in on


def _appendix(*form_blocks):
    return _cpc_act() + [_laid_block(3, "APPENDIX A \nPLEADINGS \n", 2, 72.0, 480.0, 40.0)] + list(form_blocks)


def test_appendix_numbered_form_only_under_v4(monkeypatch):
    # Document 4490 Appendices A-H: each form's number stands alone on its
    # line ("No. / 1.", "No.  2."), its title in the next block.
    blocks = _appendix(
        _laid_block(4, "No. \n1. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "MONEY LENT \n1. On the 1st day of January the plaintiff lent the defendant rupees one "
                       "hundred. \n2. The defendant has not paid the same. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(6, "No.  2. \n", 3, 72.0, 480.0, 40.0),
        _laid_block(7, "MONEY LENT ON A BOND \n1. On the 1st day of January the defendant executed a bond. \n"
                       "2. The defendant has not paid the same. \n", 3, 72.0, 480.0, 80.0))
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "appendix_numbered_form")))
    assert [k for k, *_ in off].count("form") == 0
    on = S.segment(blocks, profile="unreleased-v4")
    assert _nest(on)[2:] == [
        ("appendix", "APPENDIX A", "instrument", ""),
        ("form", "No. 1", "appendix", "APPENDIX A"), ("clause", "1", "form", "No. 1"), ("clause", "2", "form", "No. 1"),
        ("form", "No. 2", "appendix", "APPENDIX A"), ("clause", "1", "form", "No. 2"), ("clause", "2", "form", "No. 2")]
    forms = [n for n in on.flatten() if n.kind == "form"]
    # J5: the number keeps no heading; the title in the next block is the form's text
    assert [(n.heading, n.text) for n in forms] == [(None, "MONEY LENT"), (None, "MONEY LENT ON A BOND")]
    with profile("unreleased-v4"):
        for printed, label in (("4[No.  15-A. \n", "No. 15-A"), ("FORM No. 7B. \n", "FORM No. 7B"),
                               ("No.  1[9]. \n", "No. 9"), ("1[No. 1A. * *] \n", "No. 1A")):
            seg = S.segment(_appendix(_laid_block(4, printed, 2, 72.0, 480.0, 80.0),
                                      _laid_block(5, "PLAINT \n1. The plaintiff claims. \n", 2, 72.0, 480.0, 120.0)),
                            profile="unreleased-v4")
            assert [n.label for n in seg.flatten() if n.kind == "form"] == [label], printed


def test_form_schedule_caption_only_under_v4(monkeypatch):
    # Document 4490: a decree form's own caption "SCHEDULE." had opened a schedule division.
    blocks = _appendix(
        _laid_block(4, "No. 1. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "DECREE FOR POSSESSION \n1. It is ordered that the defendant do put the plaintiff in "
                       "possession of the property in the schedule. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(6, "SCHEDULE. \n", 2, 72.0, 480.0, 200.0),
        _laid_block(7, "A house in Lahore bounded on the north by a road. \n", 2, 72.0, 480.0, 240.0))
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "form_schedule_caption")))
    assert ("schedule", "SCHEDULE", "instrument", "") in off
    on = S.segment(blocks, profile="unreleased-v4")
    assert not [n for n in on.flatten() if n.kind == "schedule"]
    assert [n for n in on.flatten() if n.kind == "clause"][0].text.endswith(
        "in the schedule. SCHEDULE. A house in Lahore bounded on the north by a road.")


def test_appendix_form_paragraphs_only_under_v4(monkeypatch):
    # Document 4490 Appendices: a form's numbered paragraph owns its items.
    blocks = _appendix(
        _laid_block(4, "No. 1. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "GOODS SOLD \n1. The plaintiff claims: \n(1) delivery of the said goods; \n"
                       "(2) damages for their detention. \n2. The defendant has not paid. \n", 2, 72.0, 480.0, 120.0))
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "appendix_form_paragraphs")))
    assert ("subsection", "1", "form", "No. 1") in off
    on = _nest(S.segment(blocks, profile="unreleased-v4"))
    assert on[-4:] == [("clause", "1", "form", "No. 1"), ("subsection", "1", "clause", "1"),
                       ("subsection", "2", "clause", "1"), ("clause", "2", "form", "No. 1")]


def test_connective_not_clause_label_only_under_v4(monkeypatch):
    # Document 4490 App A(4) form No. 13 p288: "7. (or) The plaintiff has been guilty of delay;".
    blocks = _appendix(
        _laid_block(4, "No. 1. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "DEFENCES \n6. The plaintiff's claim is barred. \n7. (or) The plaintiff has been guilty of "
                       "delay; \n8. The defendant tendered the sum. \n", 2, 72.0, 480.0, 120.0))
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "connective_not_clause_label")))
    assert ("clause", "or", "clause", "7") in off
    on = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert "or" not in on
    assert on["7"].text == "(or) The plaintiff has been guilty of delay;"


DECISION_C = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-06-c.json",
              "document_id": 691, "question_id": "q2"}
_COLUMN_HEADS = "Name of the Post Appointing Authority Method of Recruitment Minimum qualification \n"


def _recruitment_rules():
    # Document 691 pp8-9: the 1997 notification makes the Rules, then prints
    # the recruitment table with no heading; rows 1-35 under their serials.
    return [
        _laid_block(1, "NOTIFICATION \nNo. SOR-III.1-26/87. In exercise of the powers conferred by section 23 "
                       "of the Punjab Civil Servants Act, 1974, the Governor of the Punjab is pleased to make the "
                       "following rules, namely:- \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, _COLUMN_HEADS, 2, 72.0, 480.0, 40.0),
        _laid_block(3, "1. Director (BS-19) Secretary By promotion from among the Deputy Directors. \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(4, "2. Deputy Director (BS-18) Secretary By promotion from among the Assistant "
                       "Directors. \n", 2, 72.0, 480.0, 120.0)]


def _schedule_opener(**changes):
    item = {"source_block_id": 2, "label": "SCHEDULE", "source_text": _COLUMN_HEADS,
            "owner_decision": DECISION_C}
    return {"source_unlabelled_schedule_openers": [dict(item, **changes)]}


def test_unlabelled_schedule_opener_only_under_v4(monkeypatch):
    blocks = _recruitment_rules()
    # Without the owner's reading the rows open as sections 1 and 2 ...
    plain = [(n.kind, n.label) for n in S.segment(blocks, profile="unreleased-v4").flatten()]
    assert plain == [("section", "1"), ("section", "2")]
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "unlabelled_schedule_opener"),
                    structural_overrides=_schedule_opener())
    assert [(n.kind, n.label) for n in off.flatten()] == plain
    # ... with it the column heads open the Schedule and the rows are its rows.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_schedule_opener())
    assert _nest(on) == [("schedule", "SCHEDULE", "instrument", ""), ("clause", "1", "schedule", "SCHEDULE"),
                         ("clause", "2", "schedule", "SCHEDULE")]
    assert on.flatten()[0].text == _COLUMN_HEADS.strip()
    assert on.block_roles[1][0] == "preface"


def test_unlabelled_schedule_opener_refuses_without_exact_evidence():
    blocks = _recruitment_rules()
    for overrides in (_schedule_opener(source_text="Name of the Post"),       # not the block's text
                      _schedule_opener(label="SCHEDULE I"),                    # a label the owner did not give
                      _schedule_opener(owner_decision={"export": "x.json"}),   # no decision cited
                      _schedule_opener(source_block_id=3)):                    # a row, not the heads
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert "source unlabelled schedule" in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")


def test_quoted_table_row_text_only_under_v4(monkeypatch):
    # Document 691 pp1-4: an amending paragraph quotes table rows whose cells
    # print their own enumerators "(i) By promotion ... (ii) If none ...".
    blocks = [
        _laid_block(1, "1. Short title. These rules may be called the Service (Amendment) Rules, 2011. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Amendment. In the said Rules, in the Schedule, for the existing entries the following "
                       "shall be substituted:- \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "1-A Deputy Director Journal. (i) By promotion from among the Assistant Directors. \n"
                       "(ii) If none is available, by initial recruitment. \n", 1, 72.0, 480.0, 120.0),
        _laid_block(4, "3. Commencement. These rules shall come into force at once. \n", 1, 72.0, 480.0, 200.0)]
    overrides = {"source_quoted_table_row_blocks": [3]}
    off = _nest(S.segment(blocks, profile=_v4_without(monkeypatch, "quoted_table_row_text"),
                          structural_overrides=overrides))
    assert ("clause", "ii", "section", "2") in off
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
    assert [(n.kind, n.label) for n in on.flatten()] == [("section", "1"), ("section", "2"), ("section", "3")]
    assert on.flatten()[1].text.endswith("(ii) If none is available, by initial recruitment.")


def _range_act():
    # Document 1003 p1 (contents) and p4 (body): one repealed stub for ss.8-10.
    return [
        _laid_block(1, "CONTENTS \n1. Short title. \n2. Definitions. \n"
                       "7. Punishment of Revenue-officers no bar to civil remedies. \n8-10. (Repealed.) \n"
                       "11. Suits not to be entertained unless plaintiff has exhausted right of appeal. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. This Act may be called the Sind Revenue Jurisdiction Act, 1876. \n",
                    2, 72.0, 480.0, 20.0),
        _laid_block(3, "2. Definitions. In this Act words have their meanings. \n", 2, 72.0, 480.0, 30.0),
        _laid_block(4, "7. Nothing in this Act shall bar a civil remedy against a Revenue-officer for punishment "
                       "or prosecution. \n8. \nto 10. [Suits against Revenue-officers. Appeals from their "
                       "proceedings. Power for Local Government to call for records.] Rep. by the Bombay Revenue "
                       "Jurisdiction Act, 1880 (XV of 1880). \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "11. No Civil Court shall entertain any suit unless the plaintiff has exhausted his right "
                       "of appeal. \n", 2, 72.0, 480.0, 200.0)]


def test_range_repeal_stub_only_under_v4(monkeypatch):
    blocks = _range_act()
    off = {n.label: n for n in S.segment(blocks, profile=_v4_without(monkeypatch, "range_repeal_stub")).flatten()}
    assert off["8"].heading == "to 10. [Suits against Revenue-officers"
    on = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert "8" not in on and on["8 to 10"].kind == "section" and on["8 to 10"].heading is None
    assert on["8 to 10"].text.startswith("[Suits against Revenue-officers. Appeals from their proceedings.")
    assert on["8 to 10"].text.endswith("Rep. by the Bombay Revenue Jurisdiction Act, 1880 (XV of 1880).")


def test_range_contents_row_only_under_v4(monkeypatch):
    blocks = _range_act()
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "range_contents_row"))
    assert [e["label"] for e in off.toc_entries] == ["1", "2", "7", "11"]
    assert off.toc_entries[2]["heading"].endswith("8-10. (Repealed.)")
    on = S.segment(blocks, profile="unreleased-v4")
    assert [(e["label"], e["heading"]) for e in on.toc_entries][2:4] == [
        ("7", "Punishment of Revenue-officers no bar to civil remedies."), ("8-10", "(Repealed.)")]
    # the row is linked by a page-read found_elsewhere reading, not by the parser
    assert on.toc_entries[3]["node"] is None


def _margin_act():
    # Document 1003 p1 (contents) and p4 (body, margin column block 4).
    return [
        _laid_block(1, "CONTENTS \n1. Short title. \n2. Definitions. \n"
                       "7. Punishment or prosecution of Revenue-officer no bar to civil remedies. \n"
                       "12. Power of Provincial Government to refer questions for decision of High Court. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. This Act may be called the Sind Revenue Jurisdiction Act, 1876. \n",
                    2, 72.0, 480.0, 10.0),
        _laid_block(3, "2. Definitions. In this Act words have their meanings. \n", 2, 72.0, 480.0, 20.0),
        _laid_block(4, "Punishment of prosecution of Revenue officers no bar to civil remedies. \nPower of "
                       "Government to refer question as for decision of High Court. \n", 2, 72.0, 480.0, 30.0),
        _laid_block(5, "7. Nothing in this Act shall bar a civil remedy against a Revenue-officer. \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(6, "12. The Provincial Government may refer any question for the decision of the High "
                       "Court. \n", 2, 72.0, 480.0, 120.0)]


DECISION_1003 = dict(DECISION_C, document_id=1003)


def _printed(label, use, heading, block=4):
    return {"label": label, "source_block_id": block, "use": use, "heading": heading,
            "owner_decision": DECISION_1003}


def _margin_overrides(*items):
    return {"source_apparatus_blocks": [4], "source_printed_headings": list(items) or [
        _printed("7", "heading", "Punishment of prosecution of Revenue officers no bar to civil remedies."),
        _printed("12", "marginal_note", "Power of Government to refer question as for decision of High Court.")]}


def test_printed_heading_override_reviewed_in_any_profile(monkeypatch):
    # Rule `printed_heading_reviewed_default` (agent JE, doc 4441 s.390; 13 Oct): a reviewed source_printed_headings
    # entry is honoured whether or not the profile carries printed_heading_override; without the key nothing changes.
    blocks = _margin_act()
    off_profile = _v4_without(monkeypatch, "printed_heading_override")
    plain = {n.label: n for n in S.segment(blocks, profile=off_profile,
                                           structural_overrides={"source_apparatus_blocks": [4]}).flatten()}
    assert plain["7"].heading == "Punishment or prosecution of Revenue-officer no bar to civil remedies."
    assert plain["12"].marginal_note is None
    off = {n.label: n for n in S.segment(blocks, profile=off_profile,
                                         structural_overrides=_margin_overrides()).flatten()}
    assert off["7"].heading == "Punishment of prosecution of Revenue officers no bar to civil remedies."
    assert off["12"].marginal_note == "Power of Government to refer question as for decision of High Court."
    seg = S.segment(blocks, profile="unreleased-v4", structural_overrides=_margin_overrides())
    on = {n.label: n for n in seg.flatten()}
    # q2 'printed': s.7 takes the printed margin wording ...
    assert on["7"].heading == "Punishment of prosecution of Revenue officers no bar to civil remedies."
    # ... q1 'contents': s.12 keeps the contents heading, the margin note is kept beside it
    assert on["12"].heading == "Power of Provincial Government to refer questions for decision of High Court."
    assert on["12"].marginal_note == "Power of Government to refer question as for decision of High Court."
    assert [r["printed_label"] for r in seg.structural_reviews_enacted
            if r.get("resolution") == "source_printed_heading"] == ["7", "12"]


def test_printed_heading_override_refuses_without_exact_evidence():
    blocks = _margin_act()
    for item in (_printed("7", "heading", "Punishment of Revenue officers."),         # not printed there
                 _printed("9", "heading", "Power of Government to refer question"),  # no such section
                 _printed("7", "title", "Power of Government to refer question"),    # not a known use
                 dict(_printed("7", "heading", "Power of Government to refer question"), owner_decision=None)):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=_margin_overrides(item))
        except ValueError as error:
            assert "source printed heading" in str(error), (item, error)
        else:
            raise AssertionError(f"accepted {item}")


def test_unclosed_paren_heading_guess_only_under_v4(monkeypatch):
    # Document 1003 p3: beside "5." only the second line of a repeal note run
    # across ss.4-6 is printed; the guess named s.5 "(Act".
    blocks = [
        _laid_block(1, "CONTENTS \n1. Short title. \n4. (Repealed). \n5. (Repealed). \n6. Reference to "
                       "Commissioner. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title. This Act may be called the Sind Revenue Jurisdiction Act, 1876. \n",
                    2, 72.0, 480.0, 40.0),
        _laid_block(3, "4. Repealed by the West Pakistan Land Revenue Act, 1967. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(4, "5. (Act. (XVII of 1967), Schedule, Part-2. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(5, "6. The Collector may refer any question to the Commissioner. \n", 2, 72.0, 480.0, 160.0)]
    off = {n.label: n for n in S.segment(blocks, profile=_v4_without(
        monkeypatch, "unclosed_paren_heading_guess")).flatten()}
    assert off["5"].heading == "(Act"
    on = {n.label: n for n in S.segment(blocks, profile="unreleased-v4").flatten()}
    assert on["5"].heading == "(Repealed)."
    assert on["5"].text == "(Act. (XVII of 1967), Schedule, Part-2."


DECISION_999 = dict(DECISION_C, document_id=999, question_id="q1")


def _hackney_act():
    # Document 999 pp1-2: the contents numbers the preamble as row 1; the body
    # prints "2. 1[Repealed]" with its paragraph, then a second "2. In this Act".
    return [
        _laid_block(1, "CONTENTS \n1. Preamble. \n2. Short title. \n3. Interpretation clause. \n"
                       "4. Application of Act to municipalities. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "WHEREAS it is expedient to provide for the regulation and control of hackney carriages; "
                       "It is hereby enacted as follows: \n", 2, 72.0, 480.0, 40.0),
        _laid_block(3, "1. Short title. \nThis Act may be called the Hackney-Carriage Act, 1879: \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(4, "2. \n1[Repealed] \n", 2, 72.0, 480.0, 120.0),
        _laid_block(5, "Nothing herein contained shall affect any power conferred by any law relating to "
                       "municipalities, or any rule made in exercise of any such power. \n", 2, 72.0, 480.0, 160.0),
        _laid_block(6, "2. Interpretation clause. \nIn this Act \"hackney-carriage\" means any wheeled vehicle drawn "
                       "by animals and used for the conveyance of passengers. \n", 2, 72.0, 480.0, 200.0),
        _laid_block(7, "3. Application of Act to municipalities. \nThe Provincial Government may apply this Act to "
                       "any municipality. \n", 2, 72.0, 480.0, 260.0)]


def _order_suffix(**changes):
    item = {"kind": "section", "label": "2", "source_block_ids": [4, 6], "owner_decision": DECISION_999}
    return {"source_order_suffix_labels": [dict(item, **changes)]}


def test_order_suffix_label_keeps_both_prints_citable(monkeypatch):
    from nizam.shared.corpus_types import order_suffix, print_occurrence
    blocks = _hackney_act()
    # Without the rule (or the owner's reading) the repealed print is demoted.
    # Agent DE (owner 12 Oct, docs 3500, 4225): the rule is data-gated -- a reviewed source_order_suffix_labels spec
    # is honoured in any profile, so 'off' means no reading (with or without the profile rule).
    for profile_name, overrides in ((_v4_without(monkeypatch, "order_suffix_label"), None),
                                    ("unreleased-v4", None)):
        off = S.segment(blocks, profile=profile_name, structural_overrides=overrides)
        assert [(n.kind, n.label) for n in off.flatten() if n.kind in ("section", "clause")] == [
            ("section", "1"), ("clause", "2"), ("section", "2"), ("section", "3")]
        assert [d["printed_label"] for d in off.repeated_label_decisions] == ["2"]
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_order_suffix())
    sections = [n for n in on.flatten() if n.kind == "section"]
    assert [(n.label, n.print_occurrence) for n in sections] == [
        ("1", None), ("2", 1), ("2", 2), ("3", None)]
    assert on.repeated_label_decisions == []
    assert sections[1].text.startswith("1[Repealed] Nothing herein contained")
    # the contents row "3. Interpretation clause." names the second print
    links = {e["label"]: e["node"] for e in on.toc_entries}
    assert links["3"] is sections[2] and links["2"] is sections[0] and links["4"] is sections[3]
    # the label stays as printed; the path keys the second print by print order
    paths = {id(node): path for node, path in S.assign_paths(on, "kp.act.y1879_XIV")}
    assert [paths[id(n)] for n in sections] == ["kp.act.y1879_XIV.s_1", "kp.act.y1879_XIV.s_2",
                                                 "kp.act.y1879_XIV.s_2__o2", "kp.act.y1879_XIV.s_3"]
    assert [order_suffix(paths[id(n)]) for n in sections] == ["", "", "(second)", ""]
    assert print_occurrence("kp.act.y1879_XIV.s_2__o3") == 3 and order_suffix("x.s_2__o3") == "(third)"
    assert print_occurrence("kp.act.y1879_XIV.s_2_n4_1") == 1


def test_order_suffix_label_refuses_without_exact_evidence():
    blocks = _hackney_act()
    for overrides in (_order_suffix(source_block_ids=[6, 4]),         # not print order
                      _order_suffix(source_block_ids=[4, 7]),         # not the prints of one label
                      _order_suffix(label="3", source_block_ids=[4, 6]),
                      _order_suffix(owner_decision={"export": "x.json"})):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert "source order suffix" in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")


DECISION_1034 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-07-e.json",
                     document_id=1034, question_id="q2")


def _board_section():
    # Document 1034 s.5 (owner decision 2026-10-07 q2 'keep-both'): the section
    # prints sub-section (2) twice -- the members, then "(2) The Director
    # General shall also act as Secretary of the Board."
    return [
        _laid_block(1, "1. Short title. This Ordinance may be called the Health Authority Ordinance, 2013. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "5. Constitution of the Board. (1) The general directions shall vest in a Board. \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, "(2) The Board shall consist of the following members. \n", 1, 72.0, 480.0, 120.0),
        _laid_block(4, "(3) The Chairperson shall preside over the meetings. \n", 1, 72.0, 480.0, 160.0),
        _laid_block(5, "(2) The Director General shall also act as Secretary of the Board. \n",
                    1, 72.0, 480.0, 200.0),
        _laid_block(6, "(4) The Board shall meet once a month. \n", 1, 72.0, 480.0, 240.0)]


def _subsection_suffix(**changes):
    item = {"kind": "subsection", "label": "2", "source_block_ids": [3, 5], "owner_decision": DECISION_1034}
    return {"source_order_suffix_labels": [dict(item, **changes)]}


def test_order_suffix_label_keeps_both_subsection_prints_citable(monkeypatch):
    from nizam.shared.corpus_types import order_suffix
    blocks = _board_section()

    def subsections(seg):
        paths = {id(node): path for node, path in S.assign_paths(seg, "sd.ord.y2013")}
        return [(n.label, n.print_occurrence, paths[id(n)].rsplit(".", 2)[-2:]) for n in seg.flatten()
                if n.kind == "subsection"]
    # Without a spec (or without the rule) the second (2) is keyed by its
    # position among the children, and nothing renders it as the second print.
    # Agent DE (owner 12 Oct, docs 3500, 4225): the rule is data-gated -- a reviewed source_order_suffix_labels spec
    # is honoured in any profile, so 'off' means no reading (with or without the profile rule).
    for profile_name, overrides in ((_v4_without(monkeypatch, "order_suffix_label"), None),
                                    ("unreleased-v4", None)):
        off = subsections(S.segment(blocks, profile=profile_name, structural_overrides=overrides))
        assert [row[1] for row in off] == [None] * 5
        assert off[3][2] == ["s_5", "ss_2_n3_1"]
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_subsection_suffix())
    rows = subsections(on)
    assert rows == [("1", None, ["s_5", "ss_1"]), ("2", 1, ["s_5", "ss_2"]), ("3", None, ["s_5", "ss_3"]),
                    ("2", 2, ["s_5", "ss_2__o2"]), ("4", None, ["s_5", "ss_4"])]
    assert on.repeated_label_decisions == []
    assert [order_suffix("sd.ord.y2013." + ".".join(r[2])) for r in rows] == ["", "", "", "(second)", ""]
    second = [n for n in on.flatten() if n.kind == "subsection"][3]
    assert second.text == "The Director General shall also act as Secretary of the Board."


def test_order_suffix_label_subsection_refuses_without_exact_evidence():
    blocks = _board_section()
    for overrides in (_subsection_suffix(source_block_ids=[5, 3]),             # not print order
                      _subsection_suffix(source_block_ids=[3, 4]),             # not the prints of one label
                      _subsection_suffix(label="3", source_block_ids=[3, 5]),
                      _subsection_suffix(owner_decision={"export": "x.json"})):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert "source order suffix" in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")


def test_quoted_letter_annexure_title_only_under_v4(monkeypatch):
    # Document 1415 p9: 'ANNEXURE "A" / FORM OF NOMINATION / (See sub-clause (1) of clause 10)' follows the
    # Schedule's last row 'Twenty thousand' (no stop) and names a clause, so it read as a cross-reference and
    # ran into the Schedule.
    blocks = [
        _laid_block(1, "1. Short title. These regulations may be called the Poultry Vaccine Centre Regulations, "
                       "1998. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Insurance. The sum assured shall be as specified in the Schedule. \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "SCHEDULE \n(See clause 7) \n", 2, 72.0, 480.0, 40.0),
        _laid_block(4, "Basic Scale-16 and above Fifty thousand \nBasic Scale-01 to 05 Twenty thousand \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(5, "ANNEXURE \"A\" \nFORM OF NOMINATION \n(See sub-clause (1) of clause 10) \n"
                       "I hereby nominate the person named below to receive the sum assured. \n", 3, 72.0, 480.0, 40.0)]
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "quoted_letter_annexure_title"))
    assert [(n.kind, n.label) for n in off.flatten()][-1] == ("schedule", "SCHEDULE")
    assert "ANNEXURE \"A\"" in off.flatten()[-1].text
    on = S.segment(blocks, profile="unreleased-v4")
    assert [(n.kind, n.label) for n in on.flatten()][-2:] == [("schedule", "SCHEDULE"), ("annexure", "ANNEXURE A")]
    assert on.flatten()[-2].text.endswith("Twenty thousand")
    assert on.flatten()[-1].text.startswith("FORM OF NOMINATION")


DECISION_1440 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-f.json",
                     document_id=1440, question_id="q1")


def test_notification_preamble_row_only_under_v4(monkeypatch):
    # Document 1440 p2 (owner decision 2026-10-08 export -f q1 'body'): contents row 1 prints only
    # 'Notification'; the body prints the notification's enacting paragraph unnumbered before rule 1.
    blocks = [
        _laid_block(1, "CONTENTS \n1. Notification \n2. Rule 1 \n3. Rule 2 \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "NOTIFICATION \n", 2, 72.0, 480.0, 40.0),
        _laid_block(3, "No. SO (Tax) 6 (1) /75, dated 7th August, 1978: In exercise of the powers conferred by "
                       "Section 8 of the Punjab Finance Act, 1977, the Governor of the Punjab is pleased to make the "
                       "following Rules, namely; \n", 2, 72.0, 480.0, 80.0),
        _laid_block(4, "1. Short title. These rules may be called the Punjab Professions and Trades Tax Rules, 1977. \n",
                    2, 72.0, 480.0, 140.0),
        _laid_block(5, "2. Commencement. These rules shall come into force at once. \n", 2, 72.0, 480.0, 180.0)]
    links = {"source_body_start_block": 2, "source_contents_row_links": [
        {"ordinal": ordinal, "printed_label": printed, "unit_label": unit, "owner_decision": DECISION_1440}
        for ordinal, printed, unit in ((0, "1", None), (1, "2", "1"), (2, "3", "2"))]}

    def kinds(seg):
        return [(n.kind, n.label) for n in seg.flatten()]
    # Without the rule (or without a reviewed link naming the 'Notification' row) the paragraph is preface ...
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "notification_preamble_row"), structural_overrides=links)
    assert kinds(off) == [("section", "1"), ("section", "2")] and off.block_roles[3][0] == "preface"
    unlinked = S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_body_start_block": 2})
    assert ("preamble", "Preamble") not in kinds(unlinked)
    # ... with it the notification's enacting paragraph is the instrument's preamble.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=links)
    assert kinds(on) == [("preamble", "Preamble"), ("section", "1"), ("section", "2")]
    assert on.flatten()[0].text.startswith("No. SO (Tax) 6 (1) /75") and on.block_roles[3][0] == "preamble"
    assert [(e["label"], e["node"].label if e.get("node") else None) for e in on.toc_entries] == [
        ("1", None), ("2", "1"), ("3", "2")]


DECISION_1431 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-f.json",
                     document_id=1431, question_id="q2")


def _stamp_schedule_act():
    # Document 1431 pp2-37 (owner decision 2026-10-08 export -f q2 's2-text'):
    # s.2 substitutes Schedule-I of the Stamp Act, which follows UNQUOTED;
    # 'Exemptions' heads three pages; a duty cell is emitted before the
    # article it is printed level with; s.3 of the Act follows the Schedule.
    def cell(i, text, page, y0, x0=72.0, x1=480.0):
        return _laid_block(i, text, page, x0, x1, y0)
    return [
        cell(1, "1. Short title. This Act may be called the Balochistan Finance Act, 1994. \n", 1, 80.0),
        cell(2, "2. Substitution of Schedule-I. For Schedule-I of the Stamp Act, 1899, the following shall be "
                "substituted:- (See Schedule on next page) \n", 1, 120.0),
        cell(3, "SCHEDULE \n", 2, 40.0),
        cell(4, "Stamp Duty on instruments (See Section 3) \n", 2, 60.0),
        cell(5, "Description of Instrument Proper Stamp Duty \n", 2, 80.0),
        cell(6, "1. ACKNOWLEDGEMENT of a debt exceeding twenty rupees. \n", 2, 120.0),
        cell(7, "Forty paisa. \n", 2, 160.0, 380.0, 480.0),
        cell(8, "2. ADMINISTRATION BOND given under section 6. \n", 2, 160.5),
        cell(9, "Exemptions \n", 3, 40.0, 250.0, 330.0),
        cell(10, "3. AFFIDAVIT for the purpose of any court. \n", 3, 80.0),
        cell(11, "Ten rupees. \n", 3, 80.0, 380.0, 480.0),
        cell(12, "Exemptions \n", 4, 40.0, 250.0, 330.0),
        cell(13, "4. AGREEMENT relating to deposit of title deeds. \n", 4, 80.0),
        cell(14, "Exemptions \n", 5, 40.0, 250.0, 330.0),
        cell(15, "Agreements made by members of the Armed Forces. \n", 5, 80.0),
        cell(16, "3. Levy of tax. The tax shall be levied at the rates in the Schedule. \n", 5, 200.0)]


def _stamp_overrides(span=None, cells=None, headers=(9, 12, 14)):
    span = dict({"owner_block_id": 2, "schedule_block_id": 3, "source_text": "SCHEDULE", "resume_block_id": 16,
                 "owner_decision": DECISION_1431}, **(span or {}))
    return {"source_substituted_schedule_items": [span],
            "source_not_running_header_blocks": list(headers),
            "source_level_cell_blocks": cells if cells is not None else [{"cell_block_id": 7, "row_block_id": 8}]}


def _stamp_tree(seg):
    return [(path.split(".", 3)[3], node.text) for node, path in S.assign_paths(seg, "bl.act.y1994")]


def test_substituted_schedule_items_only_under_v4(monkeypatch):
    blocks = _stamp_schedule_act()
    # Without the owner's reading the unquoted Schedule opens a root SCHEDULE
    # whose rows are not s.2's, and the Act's own s.3 becomes a third row 3 ...
    plain = _stamp_tree(S.segment(blocks, profile="unreleased-v4"))
    assert [p for p, _ in plain] == ["s_1", "s_2", "sch_SCHEDULE", "sch_SCHEDULE.cl_1", "sch_SCHEDULE.cl_2",
                                     "sch_SCHEDULE.cl_3", "sch_SCHEDULE.cl_4", "sch_SCHEDULE.cl_3_n4_1"]
    off = _stamp_tree(S.segment(blocks, profile=_v4_without(monkeypatch, "substituted_schedule_items"),
                                structural_overrides=_stamp_overrides()))
    assert off[2][0] == "sch_SCHEDULE" and off[-1][0] == "sch_SCHEDULE.cl_3_n4_1"
    # ... with it the articles are items of s.2, its heading and column heads are s.2's text, and the walk
    # resumes at the root with the Act's s.3.
    on = _stamp_tree(S.segment(blocks, profile="unreleased-v4", structural_overrides=_stamp_overrides()))
    assert [p for p, _ in on] == ["s_1", "s_2", "s_2.cl_1", "s_2.cl_2", "s_2.cl_3", "s_2.cl_4", "s_3"]
    assert on[1][1].endswith("(See Schedule on next page) SCHEDULE Stamp Duty on instruments (See Section 3) "
                             "Description of Instrument Proper Stamp Duty")
    assert on[-1][1] == "The tax shall be levied at the rates in the Schedule."


def test_not_running_header_blocks_honoured_in_every_profile(monkeypatch):
    # Stage 3 (agent DB, owner 11 Oct 2026): the reviewed key is data and is honoured in every profile, not only
    # under unreleased-v4 (doc 3255's '15%' rate cells are default-profile); without a reading it is inert.
    blocks = _stamp_schedule_act()
    # 'Exemptions' at the top of three pages is a running heading by repetition: set aside everywhere ...
    off = S.segment(blocks, profile="unreleased-v4", structural_overrides=_stamp_overrides(headers=()))
    assert [off.block_roles[i][0] for i in (9, 12, 14)] == ["running_header"] * 3
    assert "Exemptions" not in " ".join(t for _, t in _stamp_tree(off))
    # ... the reviewed blocks are read as the printed sub-headings they are; an unnamed print stays aside --
    # under v4 and equally in a profile without the rule's name.
    for profile in ("unreleased-v4", _v4_without(monkeypatch, "not_running_header_blocks")):
        on = S.segment(blocks, profile=profile, structural_overrides=_stamp_overrides(headers=(9, 14)))
        assert [on.block_roles[i][0] for i in (9, 12, 14)] == ["body", "running_header", "body"]
        assert dict(_stamp_tree(on))["s_2.cl_4"] == ("AGREEMENT relating to deposit of title deeds. Exemptions "
                                                     "Agreements made by members of the Armed Forces.")


def test_level_cell_blocks_only_under_v4(monkeypatch):
    blocks = _stamp_schedule_act()
    # The duty cell emitted before art.2 joins art.1 ...
    off = dict(_stamp_tree(S.segment(blocks, profile=_v4_without(monkeypatch, "level_cell_blocks"),
                                     structural_overrides=_stamp_overrides())))
    assert off["s_2.cl_1"].endswith("Forty paisa.") and "Forty paisa." not in off["s_2.cl_2"]
    # ... the reviewed pair puts it after the row it is printed level with; no word changes.
    on = dict(_stamp_tree(S.segment(blocks, profile="unreleased-v4", structural_overrides=_stamp_overrides())))
    assert on["s_2.cl_1"] == "ACKNOWLEDGEMENT of a debt exceeding twenty rupees."
    assert on["s_2.cl_2"].startswith("ADMINISTRATION BOND given under section 6. Forty paisa.")


def test_doc1431_rules_refuse_without_exact_evidence():
    blocks = _stamp_schedule_act()
    for overrides, message in (
            (_stamp_overrides(span={"source_text": "SCHEDULE I"}), "source substituted schedule 3"),
            (_stamp_overrides(span={"owner_block_id": 1}), "source substituted schedule 3"),
            (_stamp_overrides(span={"owner_decision": {"export": "x.json"}}), "source substituted schedule 3"),
            (_stamp_overrides(cells=[{"cell_block_id": 7, "row_block_id": 6}]), "source level cell"),   # not level
            (_stamp_overrides(cells=[{"cell_block_id": 11, "row_block_id": 8}]), "source level cell"),  # other page
            (_stamp_overrides(cells=[{"cell_block_id": 8, "row_block_id": 7}]), "source level cell"),   # left of row
            (_stamp_overrides(cells=[{"cell_block_id": 7, "row_block_id": 8},
                                     {"cell_block_id": 7, "row_block_id": 8}]), "source level cell")):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert message in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")
    two = _stamp_overrides()
    two["source_substituted_schedule_items"] = two["source_substituted_schedule_items"] * 2
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides=two)
    except ValueError as error:
        assert "more than one source substituted schedule span" in str(error)
    else:
        raise AssertionError("accepted two spans")


DECISION_1225 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-f.json",
                     document_id=1225, question_id="q1")
_QUOTED_29 = ("\"29 - In the absence of an agreement to the contrary, the expense of providing the stamp shall be "
              "borne by the transferee.\"; and")


def _finance_act_2006():
    # Document 1225 (owner decision 2026-10-08 export -f q1 'contents'): the
    # contents numbers the quoted Stamp Act s.29 that body s.2(ii) substitutes
    # as row 3, so from body s.3 on the contents runs one ahead.
    return [
        _laid_block(1, "CONTENTS \n1. Short title and commencement. \n2. Amendment of Act II of 1899. \n"
                       "3. Duties payable by whom. \n4. Amendment of Sindh Act X of 1985. \n5. Repeal. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. Short title and commencement. This Act may be called the Sindh Finance Act, 2006. \n",
                    2, 72.0, 480.0, 40.0),
        _laid_block(3, "2. Amendment of Act II of 1899. In the Stamp Act, 1899, (i) in section 28, the word shall be "
                       "omitted; and (ii) for section 29, the following shall be substituted:- \n" + _QUOTED_29 + " \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(4, "3. Amendment of Sindh Act X of 1985. In the said Act, the entry shall be omitted. \n",
                    2, 72.0, 480.0, 160.0),
        _laid_block(5, "4. Repeal. The Sindh Finance Ordinance, 2005 is hereby repealed. \n", 2, 72.0, 480.0, 200.0)]


def _owner_cited(*changes, drop=None):
    specs = [{"kind": "section", "printed_label": None, "cited_label": "3", "source_block_id": 3,
              "source_prefix": "\"29 - In the absence of an agreement", "owner_decision": DECISION_1225},
             {"kind": "section", "printed_label": "3", "cited_label": "4", "source_block_id": 4,
              "owner_decision": DECISION_1225},
             {"kind": "section", "printed_label": "4", "cited_label": "5", "source_block_id": 5,
              "owner_decision": DECISION_1225}]
    for index, change in changes:
        specs[index] = dict(specs[index], **change)
    if drop is not None:
        specs.pop(drop)
    return {"source_owner_cited_labels": specs}


def test_owner_cited_label_honoured_with_the_reading_in_any_profile(monkeypatch):
    from nizam.shared.corpus_types import printed_label, printed_note
    blocks = _finance_act_2006()

    def cited(seg):
        return ([(path.rsplit(".", 1)[-1], n.label, n.heading) for n, path in S.assign_paths(seg, "sd.act.y2006")],
                [(e["label"], e["node"].label if e.get("node") else None) for e in seg.toc_entries])
    # Without the owner's reading the body numbering stands and row 3 is unlinked ...
    plain = cited(S.segment(blocks, profile="unreleased-v4"))
    assert [p for p, _, _ in plain[0]] == ["s_1", "s_2", "s_3", "s_4"]
    assert plain[1] == [("1", "1"), ("2", "2"), ("3", None), ("4", "3"), ("5", "4")]
    # Agent DC round 2 (owner 12 Oct, doc 2756): the reviewed reading is honoured in ANY profile -- the rule is gated
    # by the recorded, owner-cited reading itself, so the profile switch no longer matters once it exists.
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "owner_cited_label"), structural_overrides=_owner_cited())
    assert cited(off) == cited(S.segment(blocks, profile="unreleased-v4", structural_overrides=_owner_cited()))
    assert cited(S.segment(blocks, profile=_v4_without(monkeypatch, "owner_cited_label"))) == plain
    # ... with it the quotation is cited s.3 and the printed 3 and 4 are cited 4 and 5;
    # the print stays on the path and no number is written into the text.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_owner_cited())
    paths, links = cited(on)
    assert [(p, label) for p, label, _ in paths] == [("s_1", "1"), ("s_2", "2"), ("s_3__pnone", "3"),
                                                    ("s_4__p3", "4"), ("s_5__p4", "5")]
    assert links == [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5")]
    assert on.repeated_label_decisions == []
    sections = [n for n in on.flatten() if n.kind == "section"]
    assert sections[2].text == _QUOTED_29 and sections[2].first_block == 3
    assert sections[1].text.endswith("the following shall be substituted:-")
    assert sections[3].text == "In the said Act, the entry shall be omitted."
    full = [path for _, path in S.assign_paths(on, "sd.act.y2006")]
    assert [printed_label(p) for p in full] == [None, None, "", "3", "4"]
    assert [printed_note(p) for p in full] == ["", "", "(no number printed)", "(printed 3)", "(printed 4)"]
    assert printed_label("x.s_2__o2") is None and printed_note("x.sch_SCHEDULE.cl_Naib_Qasid__nr") == ""


def test_owner_cited_label_refuses_without_exact_evidence():
    blocks = _finance_act_2006()
    for overrides, message in (
            (_owner_cited((1, {"cited_label": "5"}), (2, {"cited_label": "6"})), "out of sequence"),
            (_owner_cited((1, {"source_block_id": 5})), "printed again at block 4"),        # printed 3 left beside cited 3
            (_owner_cited((2, {"source_block_id": 4})), "not reached"),                     # 4 not printed there
            (_owner_cited((0, {"source_prefix": "No such printed words here"})), "prefix not found once"),
            (_owner_cited((2, {"printed_label": "none"})), "malformed"),
            (_owner_cited((1, {"owner_decision": {"export": "x.json"}})), "malformed"),
            (_owner_cited((1, {"cited_label": "3"})), "malformed"),                         # cited == printed
            (_owner_cited(drop=0), "out of sequence")):                                     # cited 4 after 2
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert message in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")


DECISION_I = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-10-i.json",
                  document_id=1, question_id="q1")


def _keys_heads(seg):
    return [(p.split(".", 1)[1], n.heading, n.text) for n, p in S.assign_paths(seg, "x")]


def test_unlabelled_schedule_before_row_only_under_v4(monkeypatch):
    # Document 2211 p2 (owner decision 2026-10-10 export -i q1 'release-as-is'): the schedule's heading is lost;
    # the reviewed opener names the block of its first numbered item '4. Municipal Committee Street Rules, 1962.'
    blocks = [
        _laid_block(1, "1. Short title. These rules may be called the Training Rules, 1996. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Examination. The examination shall be held as specified in the Schedule. \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, "4. Municipal Committee Street Rules, 1962. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(4, "5. Municipal Committee Building Rules, 1963. \n", 2, 72.0, 480.0, 60.0)]
    opener = {"source_unlabelled_schedule_openers": [{"source_block_id": 3, "label": "SCHEDULE",
                                                      "source_text": "4. Municipal Committee Street Rules, 1962.",
                                                      "owner_decision": DECISION_I}]}
    try:
        S.segment(blocks, profile=_v4_without(monkeypatch, "unlabelled_schedule_before_row"),
                  structural_overrides=opener)
    except ValueError as error:
        assert "source unlabelled schedule 3" in str(error)
    else:
        raise AssertionError("an opener on a numbered item was accepted without the rule")
    on = _keys_heads(S.segment(blocks, profile="unreleased-v4", structural_overrides=opener))
    assert [(p, t) for p, _, t in on[2:]] == [("sch_SCHEDULE", ""),
                                              ("sch_SCHEDULE.cl_4", "Municipal Committee Street Rules, 1962."),
                                              ("sch_SCHEDULE.cl_5", "Municipal Committee Building Rules, 1963.")]


def test_owner_cited_label_sequence_passes_lettered_insertions():
    # Document 2055 (owner decision 2026-10-10 export -i q1 'contents': 'the sequence 10, 11, 12, 12-A, 13'):
    # printed 14 and 15 are cited 11 and 12, and the inserted 12-A stands between cited 12 and printed 13.
    blocks = [
        _laid_block(1, "10. Quorum. Five members shall form a quorum. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "14. Meetings. The Committee shall meet monthly. \n", 1, 72.0, 480.0, 60.0),
        _laid_block(3, "15. Minutes. Minutes shall be kept. \n", 1, 72.0, 480.0, 80.0),
        _laid_block(4, "12-A. Records. Records shall be kept. \n", 1, 72.0, 480.0, 100.0),
        _laid_block(5, "13. Repeal. The old rules are repealed. \n", 1, 72.0, 480.0, 120.0)]
    entries = [{"kind": "section", "printed_label": "14", "cited_label": "11", "source_block_id": 2,
                "owner_decision": DECISION_I},
               {"kind": "section", "printed_label": "15", "cited_label": "12", "source_block_id": 3,
                "owner_decision": DECISION_I}]
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_owner_cited_labels": entries})
    assert [p for p, _, _ in _keys_heads(on)] == ["s_10", "s_11__p14", "s_12__p15", "s_12_A", "s_13"]
    # a neighbour that is not a lettered insertion of the number still breaks the sequence
    wrong = blocks[:3] + [_laid_block(4, "14-A. Records. Records shall be kept. \n", 1, 72.0, 480.0, 100.0)] + blocks[4:]
    try:
        S.segment(wrong, profile="unreleased-v4", structural_overrides={"source_owner_cited_labels": entries})
    except ValueError as error:
        assert "out of sequence" in str(error)
    else:
        raise AssertionError("an out-of-sequence neighbour was accepted")


def test_stray_number_continuation_only_under_v4(monkeypatch):
    # Document 2055 p4 (owner decision 2026-10-10 export -i q2 'first-only'): '14. A copy of the minutes ...' is
    # printed after rule 13(2); the contents ends at 13 -- the paragraph is rule 13's continuing text.
    blocks = [
        _laid_block(1, "CONTENTS \n", 1, 72.0, 480.0, 20.0), _laid_block(2, "1. Short title. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(3, "2. Meetings. \n", 1, 72.0, 480.0, 50.0),
        _laid_block(4, "1. Short title. These rules may be called the Committee Rules, 1990. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(5, "2. Meetings. (1) The Committee shall meet monthly. \n", 2, 72.0, 480.0, 60.0),
        _laid_block(6, "(2) The Chairman shall preside. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(7, "3. A copy of the minutes shall be sent to the Government. \n", 2, 72.0, 480.0, 100.0)]
    cont = {"source_continuation_parent_blocks": [{"source_block_id": 7, "parent_block_id": 5}]}
    try:
        S.segment(blocks, profile=_v4_without(monkeypatch, "stray_number_continuation"), structural_overrides=cont)
    except ValueError as error:
        assert "source continuation override not reached: [7]" in str(error)
    else:
        raise AssertionError("an uncontented number continued its rule without the rule")
    on = _keys_heads(S.segment(blocks, profile="unreleased-v4", structural_overrides=cont))
    assert [p for p, _, _ in on] == ["s_1", "s_2", "s_2.ss_1", "s_2.ss_2"]
    assert on[1][2] == "3. A copy of the minutes shall be sent to the Government."


def test_bracketed_omit_section_stub_only_under_v4(monkeypatch):
    # Document 2186 p11: '7[Omit section 26.].' after s.25 ran on in s.25(2)'s text.
    blocks = [
        _laid_block(1, "25. Fees. (1) A fee shall be paid. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "(2) The fee shall be credited to the fund. \n", 1, 72.0, 480.0, 60.0),
        _laid_block(3, "7[Omit section 26.]. \n", 1, 72.0, 480.0, 80.0),
        _laid_block(4, "27. Repeal. The old Act is repealed. \n", 1, 72.0, 480.0, 100.0)]
    off = _keys_heads(S.segment(blocks, profile=_v4_without(monkeypatch, "bracketed_omit_section_stub")))
    assert "s_26" not in [p for p, _, _ in off] and off[2][2].endswith("7[Omit section 26.].")
    on = dict((p, (h, t)) for p, h, t in _keys_heads(S.segment(blocks, profile="unreleased-v4")))
    assert on["s_26"] == (None, "7[Omit section 26.].") and on["s_25.ss_2"][1] == "The fee shall be credited to the fund."


def test_contents_split_division_name_only_under_v4(monkeypatch):
    # Document 2009 pp6, 8, 9, 11: 'PART-VIII / ACTION AGAINST CANDIDATE SON' then a block 'GROUNDS OF CHEATING,
    # ETC.' -- the second line stayed the Part's text; its contents row names the whole.
    monkeypatch.setattr(S, "parse_contents", lambda _blocks: (
        {"1": "PART-I GENERAL", "2": "PART-II ACTION AGAINST CANDIDATES ON GROUNDS OF CHEATING, ETC."}, 1, True))
    blocks = [
        _laid_block(1, " \n1. \nPART-I GENERAL \n2. \nPART-II ACTION AGAINST CANDIDATES ON GROUNDS OF CHEATING, ETC. \n",
                    1, 72.0, 480.0, 30.0),
        _laid_block(6, "PART-I \nGENERAL \n", 2, 72.0, 480.0, 20.0),
        _laid_block(7, "1. These regulations may be called the Examination Regulations, 1990. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(10, "PART-II \nACTION AGAINST CANDIDATES ON \n", 3, 72.0, 480.0, 80.0),
        _laid_block(11, "GROUNDS OF CHEATING, ETC. \n", 3, 72.0, 480.0, 90.0),
        _laid_block(12, "2. A candidate found cheating shall be disqualified. \n", 3, 72.0, 480.0, 120.0)]
    start = {"source_body_start_block": 6}
    part = lambda seg: next((n.heading, n.text) for n in seg.flatten() if n.kind == "part" and n.label == "II")  # noqa: E731
    assert part(S.segment(blocks, profile=_v4_without(monkeypatch, "contents_split_division_name"),
                          structural_overrides=start)) == ("ACTION AGAINST CANDIDATES ON", "GROUNDS OF CHEATING, ETC.")
    assert part(S.segment(blocks, profile="unreleased-v4", structural_overrides=start)) == (
        "ACTION AGAINST CANDIDATES ON GROUNDS OF CHEATING, ETC.", "")


def test_terse_sentence_not_heading_only_under_v4(monkeypatch):
    # Document 2009 reg.57 (p10): '57. The allocation of posts to Committees for interview will be made by the
    # Chairman.' -- a whole enacted sentence -- was taken as the regulation's heading.
    blocks = [
        _laid_block(1, "56. Interviews. Interviews shall be held at Lahore. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "57. The allocation of posts to Committees for interview will be made by the Chairman. \n",
                    1, 72.0, 480.0, 60.0),
        _laid_block(3, "58. Results. Results shall be announced. \n", 1, 72.0, 480.0, 80.0)]
    off = dict((p, (h, t)) for p, h, t in _keys_heads(S.segment(blocks, profile=_v4_without(
        monkeypatch, "terse_sentence_not_heading"))))
    assert off["s_57"][0].startswith("The allocation of posts") and off["s_57"][1] == ""
    on = dict((p, (h, t)) for p, h, t in _keys_heads(S.segment(blocks, profile="unreleased-v4")))
    assert on["s_57"] == (None, "The allocation of posts to Committees for interview will be made by the Chairman.")
    assert on["s_56"][0] == "Interviews"


def test_blank_rule_heading_none_only_under_v4(monkeypatch):
    # Document 1970 contents row 5 prints '5.' and only an underscore rule '________'; rule 5 prints no heading,
    # and the contents linker copied the rule line onto it.
    rows = ["1. Short title. \n", "2. Definitions. \n", "3. Board. \n", "4. Meetings. \n", "5. ________ \n",
            "6. Repeal. \n"]
    body = ["1. Short title. These rules may be called the Library Rules, 1991. \n",
            "2. Definitions. In these rules the Board means the Board of Governors. \n",
            "3. Board. The Board shall consist of seven members. \n",
            "4. Meetings. The Board shall meet twice a year. \n",
            "5. The Secretary shall keep the minutes of every meeting. \n",
            "6. Repeal. The Library Rules, 1980 are hereby repealed. \n"]
    blocks = ([_laid_block(1, "CONTENTS \n", 1, 72.0, 480.0, 20.0)]
              + [_laid_block(10 + i, row, 1, 72.0, 480.0, 40.0 + 10 * i) for i, row in enumerate(rows)]
              + [_laid_block(20 + i, text, 2, 72.0, 480.0, 40.0 + 20 * i) for i, text in enumerate(body)])
    heading5 = lambda seg: next(n.heading for n in seg.flatten() if n.label == "5")  # noqa: E731
    # Since 16 Oct agent JD's rule 8 `wordless_contents_heading` (a contents heading with no letter or digit heads
    # nothing; doc 4149's ']') also covers this underscore row, so both rules are switched off to see the print.
    assert heading5(S.segment(blocks, profile=_v4_without(monkeypatch, "blank_rule_heading_none",
                                                          "wordless_contents_heading"))) == "________"
    on = S.segment(blocks, profile="unreleased-v4")
    assert heading5(on) is None and [e["node"].label for e in on.toc_entries] == ["1", "2", "3", "4", "5", "6"]


def test_root_provision_member_list_only_under_v4(monkeypatch):
    # Document 1970 pp5-6 (owner decision 2026-10-08 export -h q1 'split'): each notification prints a caption
    # 'NOTIFICATION', one paragraph and a numbered list of members; the members read as sections beside it.
    blocks = [
        _laid_block(1, "NOTIFICATION \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "The Governor of the Punjab is pleased to constitute the following Board of Governors, "
                       "namely:- \n", 1, 72.0, 480.0, 60.0),
        _laid_block(3, "1. Chief Secretary, Punjab Lahore Chairman \n", 1, 72.0, 480.0, 100.0),
        _laid_block(4, "2. Secretary Education Member \n", 1, 72.0, 480.0, 120.0),
        _laid_block(5, "3. Director Libraries Member \n", 1, 72.0, 480.0, 140.0)]
    opener = {"source_unnumbered_section_openers": [{"source_block_id": 1, "label": "NOTIFICATION",
                                                     "heading": "NOTIFICATION", "source_prefix": "NOTIFICATION",
                                                     "after_section_label": "__ROOT__"}]}
    keys = lambda seg: [(p.split(".", 1)[1], n.heading) for n, p in S.assign_paths(seg, "x")]  # noqa: E731
    off = keys(S.segment(blocks, profile=_v4_without(monkeypatch, "root_provision_member_list"),
                         structural_overrides=opener))
    assert [p for p, _ in off] == ["s_NOTIFICATION", "s_1", "s_2", "s_3"]
    on = keys(S.segment(blocks, profile="unreleased-v4", structural_overrides=opener))
    assert on == [("s_NOTIFICATION", "NOTIFICATION"), ("s_NOTIFICATION.cl_1", None), ("s_NOTIFICATION.cl_2", None),
                  ("s_NOTIFICATION.cl_3", None)]
    # inert without a reviewed word-labelled root provision
    assert [p for p, _ in keys(S.segment(blocks[2:], profile="unreleased-v4"))] == ["s_1", "s_2", "s_3"]


def test_numeric_quote_definition_cut_only_under_v4(monkeypatch):
    # Document 1970 p2 r.2: '(4) "Board" means the Board of the Children Library Complex, Lahore' (no closing stop)
    # and on the next line '(5) \n"Complex" means ...' -- (5) stayed text of (4). The narrow form only: after an
    # unterminated line (the broad form also cut definitions after ';' in released documents).
    blocks = [
        _laid_block(1, "1. Short title. These rules may be called the Library Rules, 1991. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Definitions. In these rules, unless the context otherwise requires,- \n(1) \"Act\" means the "
                       "Library Act; \n(4) \"Board\" means the Board of the Children Library Complex, Lahore \n(5) \n"
                       "\"Complex\" means the Children Library Complex, Lahore; \n(6) \n\"Director\" means the Director "
                       "of the Complex; \n", 1, 72.0, 480.0, 80.0)]
    labels = lambda seg: [n.label for n in seg.flatten() if n.kind == "subsection"]  # noqa: E731
    assert labels(S.segment(blocks, profile=_v4_without(monkeypatch, "numeric_quote_definition_cut"))) == ["4"]
    on = S.segment(blocks, profile="unreleased-v4")
    assert labels(on) == ["4", "5"]                      # (6) follows a ';' line: the narrow form leaves it
    assert next(n.text for n in on.flatten() if n.label == "5").startswith("\"Complex\" means")


def test_apparatus_over_left_margin_heading_only_under_v4(monkeypatch):
    # Document 1839 pp2-21: a row's other cell blocks are set aside as apparatus by page readings, but the
    # left-column margin-heading pairing ran over the body before the apparatus was removed, so the set-aside cell
    # became the row's heading. The fixture is doc 4399's shape (A) with the margin block read as apparatus.
    blocks = [
        _laid_block(1, "Short Title and \nCommencement. \n", 1, 73.0, 162.0, 415.0),
        _laid_block(2, "1. \n", 1, 218.0, 230.0, 415.0),
        _laid_block(3, "This Act may be called the Sales Tax (Amendment) Act, 2019. \n", 1, 270.0, 520.0, 415.0)]
    aside = {"source_apparatus_blocks": [1]}
    heading = lambda seg: next(n.heading for n in seg.flatten() if n.label == "1")  # noqa: E731
    assert heading(S.segment(blocks, profile="unreleased-v4")) == "Short Title and Commencement."
    assert heading(S.segment(blocks, profile=_v4_without(monkeypatch, "apparatus_over_left_margin_heading"),
                             structural_overrides=aside)) == "Short Title and Commencement."
    assert heading(S.segment(blocks, profile="unreleased-v4", structural_overrides=aside)) is None


def _co_paths(seg):
    return [(path.split(".", 1)[1], n.heading, n.text) for n, path in S.assign_paths(seg, "x")]


def test_bracketed_repeal_stub_text_only_under_v4(monkeypatch):
    # Document 1656 s.6 (p3): with no contents, '6. [Wills and recognitions to be registered.] Rep. Act XII of
    # 1873.' -- a repeal stub -- was named whole as the section's heading and s.6 had no text.
    blocks = [
        _laid_block(1, "5. Registration of wills. Wills shall be registered in the court of the district. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "6. [Wills and recognitions to be registered.] Rep. Act XII of 1873. \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "7. Fees. A fee of one rupee shall be paid. \n", 1, 72.0, 480.0, 120.0)]
    off = dict((p, (h, t)) for p, h, t in _co_paths(S.segment(blocks, profile=_v4_without(
        monkeypatch, "bracketed_repeal_stub_text", "terse_sentence_not_heading"))))
    # (both off: this stub's '... to be registered' also trips terse_sentence_not_heading, which agrees)
    assert off["s_6"] == ("[Wills and recognitions to be registered.] Rep. Act XII of 1873", "")
    on = dict((p, (h, t)) for p, h, t in _co_paths(S.segment(blocks, profile="unreleased-v4")))
    assert on["s_6"] == (None, "[Wills and recognitions to be registered.] Rep. Act XII of 1873.")
    assert on["s_5"][0] == "Registration of wills"                            # ordinary headings unchanged


def test_numbered_starred_first_subsection_only_under_v4(monkeypatch):
    # Document 1692 s.10 (p7): '10. / (1)2[***] 3["**"] 4[10. The Chief Minister ...' -- (1) opens with omission
    # stars behind a note marker; it stayed in the section's text and named its heading.
    blocks = [
        _laid_block(1, "9. Leave. The Chief Minister shall be entitled to leave. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "10. \n(1)2[***] 3[\"**\"] 4[10. The Chief Minister shall be entitled to medical facilities. \n"
                       "(2) The members of his family shall be so entitled. \n", 1, 72.0, 480.0, 80.0)]
    off = [p for p, _, _ in _co_paths(S.segment(blocks, profile=_v4_without(monkeypatch,
                                                                            "numbered_starred_first_subsection")))]
    assert off == ["s_9", "s_10", "s_10.ss_2"]
    on = _co_paths(S.segment(blocks, profile="unreleased-v4"))
    assert [p for p, _, _ in on] == ["s_9", "s_10", "s_10.ss_1", "s_10.ss_2"]
    assert on[1][1] is None and on[2][2].startswith("2[***] 3[\"**\"] 4[10. The Chief Minister")


def test_parenthesised_lettered_division_and_order_suffix_across_divisions(monkeypatch):
    # Document 1827: '(A) DEFINITIONS.' ... '(I) EXEMPTIONS.' open lettered parts; the rules print '1.' under
    # (A) and again under (B) (owner decision 2026-10-08 export -h q1 'keep-both': one citation each, by order).
    blocks = [
        _laid_block(1, "(A) DEFINITIONS. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. In these rules, drug means any substance used in medicine. \n", 1, 72.0, 480.0, 60.0),
        _laid_block(3, "(B) MANUFACTURE. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(4, "1. No person shall manufacture a drug without a licence. \n", 2, 72.0, 480.0, 60.0),
        _laid_block(5, "2. A licence shall be granted by the Inspector. \n", 2, 72.0, 480.0, 80.0)]
    group = {"source_order_suffix_labels": [{"kind": "section", "label": "1", "source_block_ids": [2, 4],
                                             "owner_decision": dict(DECISION_C, document_id=1827, question_id="q1")}]}
    off = _co_paths(S.segment(blocks, profile=_v4_without(monkeypatch, "parenthesised_lettered_division"),
                              structural_overrides=group))
    assert off[0][0] == "s_1" and "(B) MANUFACTURE" in off[0][2]               # the heading ran on into rule 1
    plain = [p for p, _, _ in _co_paths(S.segment(blocks, profile="unreleased-v4"))]
    assert plain == ["pt_A", "pt_A.s_1", "pt_B", "pt_B.s_1", "pt_B.s_2"]
    on = _co_paths(S.segment(blocks, profile="unreleased-v4", structural_overrides=group))
    assert [p for p, _, _ in on] == ["pt_A", "pt_A.s_1", "pt_B", "pt_B.s_1__o2", "pt_B.s_2"]
    assert on[0][1] == "DEFINITIONS." and on[2][1] == "MANUFACTURE."
    reversed_group = {"source_order_suffix_labels": [dict(group["source_order_suffix_labels"][0],
                                                          source_block_ids=[4, 2])]}
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides=reversed_group)
    except ValueError as error:
        assert "source order suffix override not reached" in str(error)
    else:
        raise AssertionError("a group not in print order was accepted")


def test_stray_label_continuation_only_under_v4(monkeypatch):
    # Document 1946 p2 (owner decisions 2026-10-08 export -h q1, q2): after byelaw 3(2) the page prints
    # '3. Removal from service shall not ...' -- the closing paragraph of byelaw 3, its stray number kept.
    blocks = [
        _laid_block(1, "3. Penalties. (1) A servant may be removed from service. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "(2) A servant may be dismissed. \n", 1, 72.0, 480.0, 60.0),
        _laid_block(3, "3. Removal from service shall not, but dismissal shall, disqualify for future employment. \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(4, "4. Inquiry. An inquiry shall be held. \n", 1, 72.0, 480.0, 120.0)]
    cont = {"source_continuation_parent_blocks": [{"source_block_id": 3, "parent_block_id": 1}]}
    try:
        S.segment(blocks, profile=_v4_without(monkeypatch, "stray_label_continuation"), structural_overrides=cont)
    except ValueError as error:
        assert "source continuation 3 is not one unnumbered unit" in str(error)
    else:
        raise AssertionError("a labelled continuation was accepted without the rule")
    on = _co_paths(S.segment(blocks, profile="unreleased-v4", structural_overrides=cont))
    assert [p for p, _, _ in on] == ["s_3", "s_3.ss_1", "s_3.ss_2", "s_4"]
    assert on[0][2] == "3. Removal from service shall not, but dismissal shall, disqualify for future employment."
    wrong = {"source_continuation_parent_blocks": [{"source_block_id": 3, "parent_block_id": 4}]}
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides=wrong)
    except ValueError as error:
        assert "source continuation" in str(error)
    else:
        raise AssertionError("a continuation to a parent that is not open was accepted")


DECISION_1666 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-h.json",
                     document_id=1666, question_id="q1")


def test_owner_cited_label_bracketed_print_opens_its_unit():
    # Document 1666 p1 (owner decision 2026-10-08 export -h q1 'rule-3'): rule 3 prints its own number as '(3)'
    # and was read as sub-rule (3) of rule 2, with rule 3's (1), (2) after it.
    blocks = [
        _laid_block(1, "1. Short title and commencement:- These rules may be called the Bonded Labour System "
                       "(Abolition) Rules, 1995. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Definitions:- In these rules, the Act means the Bonded Labour System (Abolition) Act, 1992. \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, "(3) Authority to deal with cases of restoration of possession of property:- \n",
                    1, 72.0, 480.0, 120.0),
        _laid_block(4, "(1) The District Magistrate shall be the authority. \n", 1, 72.0, 480.0, 140.0),
        _laid_block(5, "(2) He shall decide the case within thirty days. \n", 1, 72.0, 480.0, 160.0),
        _laid_block(6, "4. Vigilance committees:- The committees shall meet monthly. \n", 1, 72.0, 480.0, 200.0)]
    keys = lambda seg: [p.split(".", 1)[1] for _, p in S.assign_paths(seg, "x")]  # noqa: E731
    assert keys(S.segment(blocks, profile="unreleased-v4"))[2:5] == ["s_2.ss_3", "s_2.ss_1", "s_2.ss_2"]
    entry = {"kind": "section", "printed_label": "3", "cited_label": "3", "source_block_id": 3,
             "printed_bracketed": True, "owner_decision": DECISION_1666}
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_owner_cited_labels": [entry]})
    # the number printed IS the cited number: no printed-number marker, path s_3
    assert keys(on) == ["s_1", "s_2", "s_3", "s_3.ss_1", "s_3.ss_2", "s_4"]
    s3 = next(n for n in on.flatten() if n.label == "3")
    assert s3.heading.startswith("Authority to deal with cases") and s3.text == ""
    for bad, message in ((dict(entry, cited_label="5"), "malformed"),                  # printed must equal cited
                         (dict(entry, printed_bracketed=False), "malformed"),
                         (dict(entry, source_block_id=4, printed_label="4", cited_label="4"),
                          "not reached")):                                        # block 4 prints '(1)', not '(4)'
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_owner_cited_labels": [bad]})
        except ValueError as error:
            assert message in str(error), (bad, error)
        else:
            raise AssertionError(f"accepted {bad}")


def test_dotted_form_code_only_under_v4(monkeypatch):
    # Document 1889 pp6-10: the forms print 'FORM H.T.I', 'FORM H.T.2', 'H.T. 3.' (no FORM word), 'FORM H.T.4'.
    blocks = [
        _laid_block(1, "1. Short title. These rules may be called the Punjab Hotel Tax Rules, 1992. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Forms. The forms in the Appendix shall be used. \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "FORM H.T.I \nApplication for registration of a hotel \n", 2, 72.0, 480.0, 40.0),
        _laid_block(4, "Name of the hotel ____________ Address ____________ \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "FORM H.T.2 \nRegister of hotels \n", 3, 72.0, 480.0, 40.0),
        _laid_block(6, "Serial No. Name Address \n", 3, 72.0, 480.0, 80.0),
        _laid_block(7, "H.T. 3. \n", 3, 72.0, 480.0, 140.0),
        _laid_block(8, "Notice of demand \n", 3, 72.0, 480.0, 150.0),
        _laid_block(9, "You are hereby required to pay the tax. DISTRICT------ \n", 3, 72.0, 480.0, 160.0),
        _laid_block(10, "FORM H.T.4 \nNOTICE OF ASSESSMENT \n", 4, 72.0, 480.0, 40.0)]
    forms = lambda seg: [n.label for n in seg.flatten() if n.kind == "form"]  # noqa: E731
    # Without the rule the first letter is the label: four forms all 'FORM H' and 'H.T. 3.' opens nothing ...
    assert forms(S.segment(blocks, profile=_v4_without(monkeypatch, "dotted_form_code"))) == ["FORM H", "FORM H"]
    # ... with it the whole dotted code is the label, and 'H.T. 3.' opens the next form, labelled as printed.
    assert forms(S.segment(blocks, profile="unreleased-v4")) == ["FORM H.T.I", "FORM H.T.2", "H.T.3", "FORM H.T.4"]


def test_reviewed_contents_alignment_index_row_never_heads_its_unit():
    # Documents 1889, 1635 (owner decision 2026-10-08 export -h q1 'body': 'Rules 1-11 exactly as printed, with no
    # invented headings'): a compiler's index row names a topic; linked as an index row it links its unit but its
    # words never become the unit's heading.
    blocks = [
        _laid_block(1, "CONTENTS \n1. Title of the rules \n2. Registration of hotels \n3. Tax on rooms let out \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "1. These rules may be called the Punjab Hotel Tax Rules, 1992. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(3, "2. Every hotel shall be registered with the Excise and Taxation Officer. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(4, "3. The tax shall be levied on every room let out. \n", 2, 72.0, 480.0, 120.0)]
    cite = dict(DECISION_1368, document_id=1889)
    links = [{"ordinal": o, "printed_label": str(o + 1), "unit_label": str(o + 1), "owner_decision": cite}
             for o in range(3)]

    def build(entries):
        seg = S.segment(blocks, profile="unreleased-v4", structural_overrides={
            "source_body_start_block": 2, "source_contents_row_links": entries})
        return ([(n.label, n.heading) for n in seg.flatten() if n.kind == "section"],
                [(e["label"], e["node"].label if e.get("node") else None) for e in seg.toc_entries])
    plain = build(links)
    assert plain[0] == [("1", "Title of the rules"), ("2", "Registration of hotels"), ("3", "Tax on rooms let out")]
    index = build([dict(link, index_row=True) for link in links[:2]] + links[2:])
    assert index[0] == [("1", None), ("2", None), ("3", "Tax on rooms let out")]   # rows 1-2 index rows only
    assert index[1] == plain[1] == [("1", "1"), ("2", "2"), ("3", "3")]


DECISION_1626 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-h.json",
                     document_id=1626, question_id="q3")


def _food_rule_4():
    # Document 1626 p2 (owner decision 2026-10-08 export -h q3 'keep-both'): rule 4 prints its repealed rules
    # lettered 'a)', 'b)', 'c)', 'd)', 'c)' -- closing parenthesis only, each letter alone on its line, all in one
    # text block.
    return [
        _laid_block(1, "3. Method of recruitment. Recruitment shall be made as specified in the Schedule. \n",
                    2, 72.0, 480.0, 40.0),
        _laid_block(2, "4. Repeal. The following rules are hereby repealed:- \na) \nthe Food Department Rules, 1974; \n"
                       "b) \nthe Food Department (Ministerial) Rules, 1976; \nc) \nthe Food Inspectors Rules, 1979; \n"
                       "d) \nthe Food Department (Executive) Rules, 1980; and \nc) \nthe Food Department Rules, 1983. \n",
                    2, 72.0, 480.0, 80.0)]


def _rule4_keys(seg):
    return [path.split(".", 3)[3] for _, path in S.assign_paths(seg, "pb.rules.y1993")]


def test_half_paren_clause_label_only_under_v4(monkeypatch):
    blocks = _food_rule_4()
    named = {"source_half_paren_clause_blocks": [2]}
    # Without the rule the 'x)' items are prose of rule 4 (the grammar reads only '(x)') ...
    off = _rule4_keys(S.segment(blocks, profile=_v4_without(monkeypatch, "half_paren_clause_label"),
                                structural_overrides=named))
    assert off == ["s_3", "s_4"]
    # ... with it the named block is cut before each 'x)' line and each opens clause x; nothing is added.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=named)
    assert _rule4_keys(on) == ["s_3", "s_4", "s_4.cl_a", "s_4.cl_b", "s_4.cl_c", "s_4.cl_d", "s_4.cl_c_n4_1"]
    rule4 = next(n for n in on.flatten() if n.label == "4")
    assert rule4.text == "The following rules are hereby repealed:-"
    assert [c.text for c in rule4.children][-1] == "the Food Department Rules, 1983."
    # fail-closed: a named block that opens no clause raises
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_half_paren_clause_blocks": [1]})
    except ValueError as error:
        assert "source half-paren clause blocks [1] opened no clause" in str(error)
    else:
        raise AssertionError("a named block that opens no clause was accepted")


def test_order_suffix_one_block_keeps_both_prints_in_one_block(monkeypatch):
    from nizam.shared.corpus_types import order_suffix
    blocks = _food_rule_4()
    overrides = {"source_half_paren_clause_blocks": [2], "source_order_suffix_labels": [
        {"kind": "clause", "label": "c", "source_block_ids": [2, 2], "owner_decision": DECISION_1626}]}
    # Both prints of 'c)' are in one block; without the rule the group naming it twice is refused ...
    try:
        S.segment(blocks, profile=_v4_without(monkeypatch, "order_suffix_one_block"), structural_overrides=overrides)
    except ValueError as error:
        assert "source order suffix 'c' lacks exact source evidence" in str(error)
    else:
        raise AssertionError("a repeated block id was accepted without the rule")
    # ... with it the second print is r.4(c) (second), keyed by print order.
    keys = _rule4_keys(S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides))
    assert keys[-1] == "s_4.cl_c__o2" and order_suffix(keys[-1]) == "(second)" and "s_4.cl_c" in keys


DECISION_1463 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-g.json",
                     document_id=1463, question_id="q1")


def test_owner_cited_opener_hangs_on_the_open_part():
    # Document 1463 p5 (owner decision 2026-10-08 export -g q1 'release-as-is'): the KP copy prints 'PART-HI'
    # and then s.11 with a corrupted number '2[1-(i) Notwithstanding ...'; the owner opened it as s.11 (from the
    # contents and margin). The opener hung the unit on the root, outside the open Part; it belongs to the Part.
    from nizam.shared.corpus_types import printed_note
    blocks = [
        _laid_block(1, "10. Valuation of other suits. Suits not otherwise provided for shall be valued as the court "
                       "directs. \n", 4, 72.0, 480.0, 40.0),
        _laid_block(2, "PART-HI \n", 5, 72.0, 480.0, 40.0),
        _laid_block(3, "2[1—(i) Notwithstanding anything contained in this Act, the court may revise the "
                       "valuation. \n", 5, 72.0, 480.0, 80.0),
        _laid_block(4, "12. Decision as to value. The decision of the court on the value shall be final. \n",
                    5, 72.0, 480.0, 140.0)]
    part = {"source_unnumbered_part_headings": [{"source_block_id": 2, "heading": "PART-HI"}]}
    plain = [p.split(".", 3)[3] for _, p in S.assign_paths(S.segment(blocks, profile="unreleased-v4",
                                                                     structural_overrides=part), "kp.act.y1887")]
    assert plain == ["s_10", "pt_PART_HI", "pt_PART_HI.s_12"]          # s.11's words are the Part's text
    opener = {"kind": "section", "printed_label": None, "cited_label": "11", "source_block_id": 3,
              "source_prefix": "2[1—(i) Notwithstanding", "owner_decision": DECISION_1463}
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=dict(part, source_owner_cited_labels=[opener]))
    paths = {node.label: path for node, path in S.assign_paths(on, "kp.act.y1887")}
    assert paths["11"].split(".", 3)[3] == "pt_PART_HI.s_11__pnone" and paths["12"].endswith("pt_PART_HI.s_12")
    s11 = next(n for n in on.flatten() if n.label == "11")
    assert s11.parent.kind == "part" and s11.text.startswith("2[1—(i) Notwithstanding")  # the corrupt print stays
    assert printed_note(paths["11"]) == "(no number printed)" and on.repeated_label_decisions == []


DECISION_1491 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-g.json",
                     document_id=1491, question_id="q1")
_INDEX_HEADS = "INDEX \nName of Post Appointing Authority Method of Recruitment \n"


def _corporation_rules():
    # Document 1491 pp14-22 (owner decision 2026-10-08 export -g q1 'appendix-rows-by-serial'): the Appendix is
    # printed under the caption 'INDEX'; its serials are printed with and without a stop; 'Note:-' closes it.
    return [
        _laid_block(1, "1. Short title. These rules may be called the Corporation Employees Service Rules, 1982. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. Appointment. Appointments shall be made as specified in the Appendix. \n",
                    1, 72.0, 480.0, 80.0),
        _laid_block(3, _INDEX_HEADS, 2, 72.0, 480.0, 40.0),
        _laid_block(4, "1 Directors Board By promotion from among the Managers. \n", 2, 72.0, 480.0, 80.0),
        _laid_block(5, "2. Managers Board By initial recruitment. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(6, "3 Assistants Director By initial recruitment \n", 2, 72.0, 480.0, 160.0),
        _laid_block(7, "Note:- \n", 2, 72.0, 480.0, 200.0),
        _laid_block(8, "(i) The posts may be filled on contract basis. \n", 2, 72.0, 480.0, 220.0),
        _laid_block(9, "(ii) Age relaxation as admissible under the rules. \n", 2, 72.0, 480.0, 240.0)]


def _appendix_overrides(label="APPENDIX"):
    return {"source_unlabelled_schedule_openers": [{"source_block_id": 3, "label": label, "source_text": _INDEX_HEADS,
                                                    "owner_decision": DECISION_1491}],
            "source_quoted_table_row_blocks": [4, 6]}


def _appendix_keys(seg):
    return [path.split(".", 3)[3] for _, path in S.assign_paths(seg, "pb.rules.y1982")]


def test_unlabelled_appendix_opener_only_under_v4(monkeypatch):
    blocks = _corporation_rules()
    # Without the rule an 'APPENDIX' label is refused (the opener admitted only 'SCHEDULE') ...
    try:
        S.segment(blocks, profile=_v4_without(monkeypatch, "unlabelled_appendix_opener"),
                  structural_overrides=_appendix_overrides())
    except ValueError as error:
        assert "source unlabelled schedule 3" in str(error)
    else:
        raise AssertionError("an APPENDIX label opened without the rule")
    # ... with it the reviewed opener opens kind appendix; 'SCHEDULE' still opens a schedule.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_appendix_overrides())
    appendix = on.flatten()[2]
    assert (appendix.kind, appendix.label, appendix.text) == ("appendix", "APPENDIX", _norm_text(_INDEX_HEADS))
    assert _appendix_keys(S.segment(blocks, profile="unreleased-v4",
                                    structural_overrides=_appendix_overrides("SCHEDULE")))[2] == "sch_SCHEDULE"
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides=_appendix_overrides("ANNEX"))
    except ValueError as error:
        assert "source unlabelled schedule 3" in str(error)
    else:
        raise AssertionError("accepted a label the owner did not give")


def _norm_text(value):
    return " ".join(value.split())


def test_bare_serial_row_only_under_v4(monkeypatch):
    blocks = _corporation_rules()
    # Without the rule the stop-less serials '1' and '3' open nothing: row 1 is the Appendix's text and
    # row 3 runs into row 2 ...
    off = _appendix_keys(S.segment(blocks, profile=_v4_without(monkeypatch, "bare_serial_row"),
                                   structural_overrides=_appendix_overrides()))
    assert [k for k in off if k.startswith("app_APPENDIX.cl_")] == ["app_APPENDIX.cl_2"]
    # ... with it each page-read row block opens its row under its printed serial, not normalised.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_appendix_overrides())
    rows = [n for n in on.flatten() if n.kind == "clause" and n.parent.kind == "appendix"]
    assert [(n.label, n.text) for n in rows] == [
        ("1", "Directors Board By promotion from among the Managers."),
        ("2", "Managers Board By initial recruitment."), ("3", "Assistants Director By initial recruitment")]
    # only inside a division opened by a reviewed unlabelled opener: without the opener nothing changes
    plain = S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_quoted_table_row_blocks": [4, 6]})
    labels = [(n.kind, n.label) for n in plain.flatten()]
    assert not any(kind == "appendix" for kind, _ in labels)
    assert ("clause", "1") not in labels and ("clause", "3") not in labels and ("section", "3") not in labels


def test_appendix_note_caption_only_under_v4(monkeypatch):
    blocks = _corporation_rules()
    # Without the rule the Note's items are clauses of the last row ...
    off = _appendix_keys(S.segment(blocks, profile=_v4_without(monkeypatch, "appendix_note_caption"),
                                   structural_overrides=_appendix_overrides()))
    assert off[-2:] == ["app_APPENDIX.cl_3.cl_i", "app_APPENDIX.cl_3.cl_ii"]
    # ... with it 'Note:-' opens the Appendix's Part 'Note' holding them.
    on = _appendix_keys(S.segment(blocks, profile="unreleased-v4", structural_overrides=_appendix_overrides()))
    assert on[-3:] == ["app_APPENDIX.pt_Note", "app_APPENDIX.pt_Note.cl_i", "app_APPENDIX.pt_Note.cl_ii"]
    # inside a schedule (not an appendix) the rule is inert
    sched = _appendix_keys(S.segment(blocks, profile="unreleased-v4",
                                     structural_overrides=_appendix_overrides("SCHEDULE")))
    assert sched[-2:] == ["sch_SCHEDULE.cl_3.cl_i", "sch_SCHEDULE.cl_3.cl_ii"]


DECISION_1457_Q3 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-08-g.json",
                        document_id=1457, question_id="q3")
DECISION_1457_Q4 = dict(DECISION_1457_Q3, question_id="q4")


def _speakers_act():
    # Document 1457 pp3-6 (owner decisions 8 Oct, q3 'open-at-p3', q4 'keep-both'): s.6 opens at p3's
    # '6["(1) The Speaker ...' (the 6 is a footnote marker) and the copy prints '6.' only on p4, before (2);
    # a later section prints its items (i), (ii) twice.
    return [
        _laid_block(1, "5. Salary. The Speaker shall receive a salary of five thousand rupees a month. \n",
                    3, 72.0, 480.0, 40.0),
        _laid_block(2, "6[\"(1) The Speaker or the Deputy Speaker shall be entitled to an official residence free of "
                       "rent. \n", 3, 72.0, 480.0, 80.0),
        _laid_block(3, "Explanation.- In this section official residence includes the furniture provided in it. \n",
                    4, 72.0, 480.0, 40.0),
        _laid_block(4, "1[6. 2[\"(2) Where the Speaker does not occupy an official residence, he shall be paid a house "
                       "rent allowance. \n", 4, 72.0, 480.0, 80.0),
        _laid_block(5, "7. Allowances. The Speaker shall receive the following allowances, namely:- \n",
                    5, 72.0, 480.0, 40.0),
        _laid_block(6, "(i) a sumptuary allowance; \n", 5, 72.0, 480.0, 80.0),
        _laid_block(7, "(ii) a conveyance allowance; \n", 5, 72.0, 480.0, 100.0),
        _laid_block(8, "(i) a telephone allowance; \n", 6, 72.0, 480.0, 40.0),
        _laid_block(9, "(ii) a medical allowance; and \n", 6, 72.0, 480.0, 60.0),
        _laid_block(10, "(iii) a travelling allowance. \n", 6, 72.0, 480.0, 80.0)]


_S6_OPENER = {"kind": "section", "printed_label": None, "cited_label": "6", "source_block_id": 2,
              "source_prefix": "6[\"(1) The Speaker or the Deputy Speaker", "owner_decision": DECISION_1457_Q3}
_S6_CONTINUES = {"kind": "section", "printed_label": "6", "cited_label": "6", "source_block_id": 4,
                 "continues_opened": True, "owner_decision": DECISION_1457_Q3}


def _speaker_keys(seg):
    return [path.split(".", 3)[3] for _, path in S.assign_paths(seg, "sd.act.y1975")]


def test_owner_cited_label_continuation_keeps_the_later_print_in_the_unit():
    blocks = _speakers_act()
    # As printed, s.6(1) and its Explanation sit under s.5 and s.6 opens at (2) ...
    plain = _speaker_keys(S.segment(blocks, profile="unreleased-v4"))
    assert plain[:4] == ["s_5", "s_5.ss_1", "s_5.ss_1.expl_Explanation", "s_6"]
    # ... the owner's opener opens s.6 at p3's printed words, which open s.6(1); the p4 print '1[6.' is the
    # continuing print of s.6 (its text), and '(2) Where ...' is read inside s.6.
    on = S.segment(blocks, profile="unreleased-v4",
                   structural_overrides={"source_owner_cited_labels": [_S6_OPENER, _S6_CONTINUES]})
    # Lead decision 8 Oct: the number IS printed (p4 '6.', the used continuation), so s.6 carries no
    # printed-number marker -- the stored label is the print. An opener with no continuation keeps
    # `__pnone` (doc 1225 s.3, below and in test_owner_cited_label_only_under_v4).
    assert _speaker_keys(on)[:5] == ["s_5", "s_6", "s_6.ss_1", "s_6.ss_1.expl_Explanation", "s_6.ss_2"]
    s6 = next(n for n in on.flatten() if n.kind == "section" and n.label == "6")
    assert s6.text == "1[6." and [c.label for c in s6.children] == ["1", "2"]
    from nizam.shared.corpus_types import printed_label, printed_note
    s6_path = next(path for node, path in S.assign_paths(on, "sd.act.y1975") if node is s6)
    assert printed_label(s6_path) is None and printed_note(s6_path) == ""
    # the same opener without the continuation's print having a number of this instrument: doc 1225's s.3
    cited = S.segment(_finance_act_2006(), profile="unreleased-v4", structural_overrides=_owner_cited())
    s3_path = next(path for node, path in S.assign_paths(cited, "sd.act.y2006") if node.label == "3")
    assert s3_path.endswith("s_3__pnone") and printed_note(s3_path) == "(no number printed)"
    assert s6.children[0].text.startswith("The Speaker or the Deputy Speaker shall be entitled")
    assert on.repeated_label_decisions == []
    for entries, message in (
            ([_S6_OPENER], "printed again at block 4 without a continuation entry"),
            ([_S6_OPENER, dict(_S6_CONTINUES, source_block_id=5)], "printed again at block 4"),
            ([_S6_CONTINUES], "has no open owner-cited unit"),
            ([_S6_OPENER, dict(_S6_CONTINUES, continues_opened=False)], "malformed")):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_owner_cited_labels": entries})
        except ValueError as error:
            assert message in str(error), (entries, error)
        else:
            raise AssertionError(f"accepted {entries}")


def test_order_suffix_label_keeps_both_clause_prints_citable(monkeypatch):
    from nizam.shared.corpus_types import order_suffix
    blocks = _speakers_act()
    groups = {"source_order_suffix_labels": [
        {"kind": "clause", "label": "i", "source_block_ids": [6, 8], "owner_decision": DECISION_1457_Q4},
        {"kind": "clause", "label": "ii", "source_block_ids": [7, 9], "owner_decision": DECISION_1457_Q4}]}
    clauses = lambda seg: [k for k in _speaker_keys(seg) if k.startswith("s_7.")]
    # Agent DE (owner 12 Oct, docs 3500, 4225): the rule is data-gated -- a reviewed source_order_suffix_labels spec
    # is honoured in any profile, so 'off' means no reading (with or without the profile rule).
    for profile_name, overrides in ((_v4_without(monkeypatch, "order_suffix_label"), None),
                                    ("unreleased-v4", None)):
        assert clauses(S.segment(blocks, profile=profile_name, structural_overrides=overrides)) == [
            "s_7.cl_i", "s_7.cl_ii", "s_7.cl_i_n2_1", "s_7.cl_ii_n3_1", "s_7.cl_iii"]
    on = clauses(S.segment(blocks, profile="unreleased-v4", structural_overrides=groups))
    assert on == ["s_7.cl_i", "s_7.cl_ii", "s_7.cl_i__o2", "s_7.cl_ii__o2", "s_7.cl_iii"]
    assert [order_suffix(k) for k in on] == ["", "", "(second)", "(second)", ""]
    for bad, message in ((dict(groups["source_order_suffix_labels"][0], source_block_ids=[8, 6]), "not reached"),
                         (dict(groups["source_order_suffix_labels"][0], owner_decision={"export": "x.json"}),
                          "lacks exact source evidence")):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_order_suffix_labels": [bad]})
        except ValueError as error:
            assert message in str(error), (bad, error)
        else:
            raise AssertionError(f"accepted {bad}")


DECISION_1106 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-07-e.json",
                     document_id=1106, question_id="q3")
_GROUP_ROW = "Asstt. Research Officer -do- M.Sc. Agri. By initial recruitment. \n"


def _floriculture_rules():
    # Document 1106 pp1-6 (owner decision 2026-10-07 q3 'rows-by-group'): no
    # contents; rules 1-3, then a Schedule whose wing title and group
    # captions are printed across the table, the serials restarting under
    # each, and one row printed with no serial (identified by its post).
    return [
        _laid_block(1, "1. These Rules may be called the Floriculture Services Rules, 1996. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "2. They shall come into force at once. \n", 1, 72.0, 480.0, 80.0),
        _laid_block(3, "3. The method of recruitment shall be as specified in the Schedule annexed. \n",
                    1, 72.0, 480.0, 120.0),
        _laid_block(4, "SCHEDULE \n", 2, 72.0, 480.0, 40.0),
        _laid_block(5, "Name of Post Appointing Authority Method of Recruitment \n", 2, 72.0, 480.0, 80.0),
        _laid_block(6, "GAZETTED STAFF OF FLORICULTURE WING \n", 2, 72.0, 480.0, 120.0),
        _laid_block(7, "GREEN BELT GROUP \n", 2, 72.0, 480.0, 160.0),
        _laid_block(8, "1. Horticulturist Secretary By promotion. \n", 2, 72.0, 480.0, 200.0),
        _laid_block(9, "2. Assistant Horticulturist Director By initial recruitment. \n", 2, 72.0, 480.0, 240.0),
        _laid_block(10, "TISSUCULTURE GROUP \n", 2, 72.0, 480.0, 280.0),
        _laid_block(11, "1. Field Assistant Director By initial recruitment. \n", 2, 72.0, 480.0, 320.0),
        _laid_block(12, _GROUP_ROW, 2, 72.0, 480.0, 360.0)]


def _group_captions(*changes):
    captions = [{"source_block_id": block, "caption": caption, "level": level, "owner_decision": DECISION_1106}
                for block, caption, level in ((6, "GAZETTED STAFF OF FLORICULTURE WING", 1),
                                              (7, "GREEN BELT GROUP", 2), (10, "TISSUCULTURE GROUP", 2))]
    for index, change in changes:
        captions[index] = dict(captions[index], **change)
    return {"source_schedule_group_captions": captions,
            "source_named_schedule_rows": [{"source_block_id": 12, "schedule_block_id": 4,
                                            "label": "Asstt. Research Officer", "source_text": _GROUP_ROW,
                                            "owner_decision": DECISION_1106}]}


def _keys(seg):
    return [path.split(".", 3)[3] for _, path in S.assign_paths(seg, "pb.rules.y1996")]


def test_schedule_group_caption_only_under_v4(monkeypatch):
    from nizam.shared.corpus_types import is_named_schedule_row, is_schedule_group_caption
    blocks = _floriculture_rules()
    wing = "sch_SCHEDULE.pt_GAZETTED_STAFF_OF_FLORICULTURE_WING__gc"
    # Without the captions the restarting serials are told apart only by
    # sibling position (cl_1_n2_1), which a re-segmentation can change ...
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "schedule_group_caption"),
                    structural_overrides=_group_captions())
    assert _keys(off)[4:] == ["sch_SCHEDULE.cl_1", "sch_SCHEDULE.cl_2", "sch_SCHEDULE.cl_1_n2_1",
                              "sch_SCHEDULE.cl_Asstt_Research_Officer__nr"]
    # ... with them each row sits under its printed caption with its own serial,
    # and the post-name row under the caption open where it is printed.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_group_captions())
    keys = _keys(on)
    assert keys == ["s_1", "s_2", "s_3", "sch_SCHEDULE", wing,
                    f"{wing}.pt_GREEN_BELT_GROUP__gc", f"{wing}.pt_GREEN_BELT_GROUP__gc.cl_1",
                    f"{wing}.pt_GREEN_BELT_GROUP__gc.cl_2", f"{wing}.pt_TISSUCULTURE_GROUP__gc",
                    f"{wing}.pt_TISSUCULTURE_GROUP__gc.cl_1",
                    f"{wing}.pt_TISSUCULTURE_GROUP__gc.cl_Asstt_Research_Officer__nr"]
    captions = [n for n in on.flatten() if n.kind == "part"]
    assert [(n.label, n.heading, n.parent.label) for n in captions] == [
        ("GAZETTED STAFF OF FLORICULTURE WING", "GAZETTED STAFF OF FLORICULTURE WING", "SCHEDULE"),
        ("GREEN BELT GROUP", "GREEN BELT GROUP", "GAZETTED STAFF OF FLORICULTURE WING"),
        ("TISSUCULTURE GROUP", "TISSUCULTURE GROUP", "GAZETTED STAFF OF FLORICULTURE WING")]
    # a renderer reads the markers from the stored path: the caption is cited as printed
    assert [is_schedule_group_caption(k) for k in keys] == [False] * 4 + [True, True, False, False, True,
                                                                        False, False]
    assert is_named_schedule_row(keys[-1]) and not is_schedule_group_caption(keys[-1])
    for path in ("x.pt_I", "x.sch_SCHEDULE.pt_GREEN__gc.cl_1", "x.cl_A__gc", "", None):
        assert not is_schedule_group_caption(path), path


def test_schedule_group_caption_refuses_without_exact_evidence():
    blocks = _floriculture_rules()
    for overrides in (_group_captions((1, {"caption": "GREEN BELT"})),               # not the printed caption
                      _group_captions((0, {"level": 2})),                             # level 2 with no wing open
                      _group_captions((2, {"caption": "GREEN BELT GROUP"})),          # a caption twice under one wing
                      _group_captions((1, {"owner_decision": {"export": "x.json"}})),
                      _group_captions((0, {"source_block_id": 3, "caption": "3. The method of recruitment shall "
                                           "be as specified in the Schedule annexed."}))):  # outside a schedule
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert "source schedule group caption" in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides=_group_captions((2, {"source_block_id": 99})))
    except ValueError as error:
        # since agent K4's rule R (group 20) the cut finds no print in block 99 before the walk can miss it
        assert ("source schedule group caption not reached: [99]" in str(error)
                or "source schedule group caption 99 'TISSUCULTURE GROUP' is not printed once in its block" in str(error))
    else:
        raise AssertionError("accepted an unreached caption")


def test_uncontented_subpart_scan_schedule_bound_only_under_v4(monkeypatch):
    # Document 1106 p1: with no contents, the Schedule's row '2.' counted as a
    # second rule 2 and buried 'They shall come into force at once.' in 1(2).
    blocks = _floriculture_rules()
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "uncontented_subpart_scan_schedule_bound"),
                    structural_overrides=_group_captions())
    assert _keys(off)[:3] == ["s_1", "s_1.ss_2", "s_3"]
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_group_captions())
    assert _keys(on)[:3] == ["s_1", "s_2", "s_3"]


def test_contents_opener_later_units_only_under_v4(monkeypatch):
    # Document 1337 p2 (owner decision 2026-10-07 q1 'contents-number'): rule 1
    # prints no number -- 'Short title and commencement.- (1) These rules ...
    # (2) They shall ...' -- and the contents numbers it 1. The block is cut
    # into units first; its later unit '(1) These rules' re-entered the
    # contents-evidenced opener and raised.
    monkeypatch.setattr(S, "parse_contents", lambda _blocks: (
        {"1": "Short title and commencement", "2": "Definitions"}, 3, True))
    texts = ["CONTENTS", "1. Short title and commencement", "2. Definitions",
             "THE SINDH HOSPITAL WASTE MANAGEMENT RULES, 2014",
             "Short title and commencement.- (1) These rules may be called the Sindh Hospital Waste Management "
             "Rules, 2014.\n(2) They shall come into force at once.",
             "2. Definitions. In these rules, unless the context otherwise requires, words have their ordinary "
             "meaning."]
    blocks = [{"id": i, "page_no": 1 if i <= 3 else 2, "text": value, "y0": i * 50.0, "x0": 70.0, "x1": 500.0,
               "page_height": 800.0} for i, value in enumerate(texts, 1)]
    overrides = {"source_body_start_block": 4, "source_unnumbered_section_openers": [{
        "source_block_id": 5, "label": "1", "heading": "Short title and commencement",
        "source_prefix": "Short title and commencement.-", "after_section_label": "__ROOT__"}]}
    try:
        S.segment(blocks, profile=_v4_without(monkeypatch, "contents_opener_later_units"),
                  structural_overrides=overrides)
    except ValueError as error:
        assert "source unnumbered section 5" in str(error)
    else:
        raise AssertionError("the later unit no longer re-enters the opener without the rule")
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
    assert [(n.kind, n.label, n.parent.label) for n in on.flatten()] == [
        ("section", "1", ""), ("subsection", "1", "1"), ("subsection", "2", "1"), ("section", "2", "")]
    assert on.flatten()[0].heading == "Short title and commencement"
    assert on.flatten()[1].text.startswith("These rules may be called")
    assert [(e["label"], e["node"].label) for e in on.toc_entries] == [("1", "1"), ("2", "2")]


DECISION_1368 = dict(DECISION_C, export=".artifacts/decision-review/exports/decision-review-2026-10-07-e.json",
                     document_id=1368, question_id="q1")


def _finance_ordinance():
    # Document 1368 pp1-2: the contents numbers 'Preamble.' as row 1, so rows
    # 2-5 name ss.1-4 -- but it prints the two schedule amendments in the other
    # order (row 3 is body s.3, row 4 is body s.2).
    return [
        _laid_block(1, "CONTENTS \n1. Preamble. \n2. Short title and commencement. \n3. Amendment of the schedule "
                       "to Ordinance IX of 1980. \n4. Amendment of the schedule to Act XXXII of 1958. \n5. Repeal. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "WHEREAS it is expedient to amend certain laws for the purposes hereinafter appearing; "
                       "It is hereby ordained as follows:- \n", 2, 72.0, 480.0, 40.0),
        _laid_block(3, "1. Short title and commencement. This Ordinance may be called the Finance Ordinance, 1983. \n",
                    2, 72.0, 480.0, 80.0),
        _laid_block(4, "2. Amendment of the schedule to Act XXXII of 1958. In the said Act, in the schedule, the "
                       "entry shall be omitted. \n", 2, 72.0, 480.0, 120.0),
        _laid_block(5, "3. Amendment of the schedule to Ordinance IX of 1980. In the said Ordinance, in the "
                       "schedule, the entry shall be added. \n", 2, 72.0, 480.0, 160.0),
        _laid_block(6, "4. Repeal. The Finance Ordinance, 1982 is hereby repealed. \n", 2, 72.0, 480.0, 200.0)]


def _row_links(*changes):
    links = [{"ordinal": ordinal, "printed_label": printed, "unit_label": unit, "owner_decision": DECISION_1368}
             for ordinal, printed, unit in ((0, "1", None), (1, "2", "1"), (2, "3", "3"), (3, "4", "2"),
                                            (4, "5", "4"))]
    for index, change in changes:
        links[index] = dict(links[index], **change)
    return {"source_contents_row_links": links}


def test_reviewed_contents_alignment_only_under_v4(monkeypatch):
    blocks = _finance_ordinance()

    def links(seg):
        return [(e["label"], e["node"].label if e.get("node") else None) for e in seg.toc_entries]
    # Without the owner's reading the rows link by number -- row 3 to s.3 is
    # right by accident, row 4 'Act XXXII' to s.4 'Repeal' is wrong ...
    plain = links(S.segment(blocks, profile="unreleased-v4"))
    assert plain == [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", None)]
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "reviewed_contents_alignment"),
                    structural_overrides=_row_links())
    assert links(off) == plain
    # ... with it each row links to the section it names, row 1 to nothing.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_row_links())
    assert links(on) == [("1", None), ("2", "1"), ("3", "3"), ("4", "2"), ("5", "4")]
    assert [n.label for n in on.flatten() if n.kind == "section"] == ["1", "2", "3", "4"]


def test_reviewed_contents_alignment_refuses_without_exact_evidence():
    blocks = _finance_ordinance()
    for overrides, message in (
            (_row_links((2, {"printed_label": "9"})), "reviewed contents row link"),       # not the printed row
            (_row_links((4, {"ordinal": 7})), "reviewed contents row link"),               # no such row
            (_row_links((3, {"unit_label": "3"})), "name one unit twice"),
            (_row_links((2, {"owner_decision": {"export": "x.json"}})), "reviewed contents row link"),
            (_row_links((4, {"unit_label": "9"})), "reviewed contents row link 4 not linked")):
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert message in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")


DECISION_1121 = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-07-e.json",
                 "document_id": 1121, "question_id": "q2"}
_POST_HEADS = ("Name of the Deptt Functional Unit Name of the Post with Grade Appointing Authority "
               "Method of Recruitment \n")
_POST_ROW_1 = ("Food Department Office of Cane Commissioner Punjab Cane Commissioner (BS-19) Chief Minister "
               "1. By promotion from amongst Additional Cane Commissioners. 2. If none is available, by "
               "initial recruitment. \n")
_POST_ROW_2 = ("Food Department Office of Cane Commissioner Punjab Assistant Cane Commissioner (Audit & "
               "Accounts / Admin) (BS-17) Cane Commissioner (i) By initial recruitment. (ii) By transfer. "
               "a) Graduate. \n")


def _post_table():
    # Document 1121 pp2-4: a titled recruitment table with no SCHEDULE heading
    # and no serial column; each row is identified only by its post, and the
    # cells print their own '1.', '(i)', 'a)' lists.
    return [
        _laid_block(1, "THE FOOD DEPARTMENT, OFFICE OF THE CANE COMMISSIONER PUNJAB RECRUITMENT RULES, 2009. \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, _POST_HEADS, 1, 72.0, 480.0, 80.0),
        _laid_block(3, _POST_ROW_1, 1, 72.0, 480.0, 120.0),
        _laid_block(4, _POST_ROW_2, 1, 72.0, 480.0, 200.0)]


_POST_LABELS = ("Cane Commissioner (BS-19)", "Assistant Cane Commissioner (Audit & Accounts / Admin) (BS-17)")


def _named_rows(*changes):
    opener = {"source_block_id": 2, "label": "SCHEDULE", "source_text": _POST_HEADS,
              "owner_decision": DECISION_1121}
    rows = [{"source_block_id": block, "schedule_block_id": 2, "label": label, "source_text": text,
             "owner_decision": DECISION_1121}
            for block, label, text in ((3, _POST_LABELS[0], _POST_ROW_1), (4, _POST_LABELS[1], _POST_ROW_2))]
    for index, change in enumerate(changes):
        rows[index] = dict(rows[index], **change)
    return {"source_unlabelled_schedule_openers": [opener], "source_named_schedule_rows": rows}


def test_named_schedule_row_only_under_v4(monkeypatch):
    from nizam.shared.corpus_types import is_named_schedule_row, is_unnumbered_provision
    blocks = _post_table()
    opener_only = {"source_unlabelled_schedule_openers": _named_rows()["source_unlabelled_schedule_openers"]}
    # Without the owner's reading the cells' own enumerators open clauses '2'
    # and 'ii' under the schedule and the posts are lost in their text ...
    plain = _nest(S.segment(blocks, profile="unreleased-v4", structural_overrides=opener_only))
    assert ("clause", "2", "schedule", "SCHEDULE") in plain and ("clause", "ii", "clause", "2") in plain
    off = S.segment(blocks, profile=_v4_without(monkeypatch, "named_schedule_row"),
                    structural_overrides=_named_rows())
    assert _nest(off) == plain
    # ... with it each row is a Schedule row labelled by its printed post name.
    on = S.segment(blocks, profile="unreleased-v4", structural_overrides=_named_rows())
    assert _nest(on) == [("schedule", "SCHEDULE", "instrument", ""),
                         ("clause", _POST_LABELS[0], "schedule", "SCHEDULE"),
                         ("clause", _POST_LABELS[1], "schedule", "SCHEDULE")]
    rows = on.flatten()[1:]
    # the whole row line, post cell and in-cell lists included, is the text
    assert [n.text for n in rows] == [_POST_ROW_1.strip(), _POST_ROW_2.strip()]
    assert [n.blocks for n in rows] == [[3], [4]]
    assert on.block_roles[3][0] == on.block_roles[4][0] == "schedule_row"
    assert on.repeated_label_decisions == []
    # the path keys the row by its full label slug (no 40-character cut) and the marker
    paths = [path for _, path in S.assign_paths(on, "pb.rules.y2009")]
    assert paths == ["pb.rules.y2009.sch_SCHEDULE",
                     "pb.rules.y2009.sch_SCHEDULE.cl_Cane_Commissioner_BS_19__nr",
                     "pb.rules.y2009.sch_SCHEDULE.cl_Assistant_Cane_Commissioner_Audit_Accounts_Admin_BS_17__nr"]
    # a renderer reads the marker from the stored path, never the label's shape
    assert [is_named_schedule_row(p) for p in paths] == [False, True, True]
    assert not any(is_unnumbered_provision(n.kind, n.label) for n in rows)
    for path in ("pb.rules.y2009.sch_SCHEDULE.cl_2", "x.s_2__o2", "x.cl_nr", "x.s_Repeal__nr", "", None):
        assert not is_named_schedule_row(path), path


def test_named_schedule_row_refuses_without_exact_evidence():
    blocks = _post_table()
    for overrides in (_named_rows({"source_text": "Food Department"}),             # not the block's text
                      _named_rows({"label": "Cane Commissioner (BS-20)"}),        # not printed in the row
                      _named_rows({"label": "Cane Commissioner"}),                # printed twice in the row
                      _named_rows({"label": "1."}),                               # a printed enumerator
                      _named_rows({"label": "19"}),                               # a bare number
                      _named_rows({"schedule_block_id": 1}),                    # not the open schedule
                      _named_rows({"owner_decision": {"export": "x.json"}}),      # no decision cited
                      _named_rows({"source_block_id": 1})):                       # before the schedule
        try:
            S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
        except ValueError as error:
            assert "source named schedule row" in str(error), (overrides, error)
        else:
            raise AssertionError(f"accepted {overrides}")
    # two rows printing one post: the second may not take a sibling's label
    twice = blocks[:3] + [dict(blocks[3], text=_POST_ROW_1)]
    try:
        S.segment(twice, profile="unreleased-v4", structural_overrides=_named_rows(
            {}, {"label": _POST_LABELS[0], "source_text": _POST_ROW_1}))
    except ValueError as error:
        assert "source named schedule row 4" in str(error)
    else:
        raise AssertionError("accepted a repeated sibling label")
    # an entry the walk never reaches is refused, not dropped
    try:
        S.segment(blocks, profile="unreleased-v4", structural_overrides=_named_rows({"source_block_id": 99}))
    except ValueError as error:
        assert "source named schedule row override not reached: [99]" in str(error)
    else:
        raise AssertionError("accepted an unreached named row")


def _ck_paths(seg):
    return [(path.split(".", 1)[1], n.heading, n.text) for n, path in S.assign_paths(seg, "x")]


def test_decimal_paragraph_cut_only_under_v4(monkeypatch):
    # Document 1973 pp2-7 numbers its paragraphs 3.1-3.19; 3.3 follows a line ending '/', 3.6 one ending ','.
    # With no blank line before them and no repeat elsewhere, the paragraphs ran into the one before.
    blocks = [_laid_block(1, "3.1 Under section 3 the Collector may grant licences. \n", 1, 72.0, 480.0, 40.0),
              _laid_block(2, "3.2 Under section 5 the Government directs three classes of officers. \n"
                             "3.3 The persons mentioned below are invested with powers of an Excise Officer, sections "
                             "23 and 30 of the Act/ \n3.4 Under section 11 the persons mentioned below are invested "
                             "with powers. \n", 1, 72.0, 480.0, 60.0),
              _laid_block(3, "3.5 Under section 13 every Collector may delegate powers, \n3.6 Under section 14 an "
                             "appeal shall lie. \n3.7 Under section 15 the Collector may revise any order. \n",
                          1, 72.0, 480.0, 100.0)]
    labels = lambda seg: [n.label for n in seg.flatten() if n.kind == "section"]  # noqa: E731
    assert labels(S.segment(blocks, profile=_v4_without(monkeypatch, "decimal_paragraph_cut"))) == ["3.1", "3.2", "3.5"]
    on = S.segment(blocks, profile="unreleased-v4")
    assert labels(on) == ["3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7"]
    assert next(n.text for n in on.flatten() if n.label == "3.3").endswith("sections 23 and 30 of the Act/")
    # inert below five consecutive labels of one series
    assert labels(S.segment(blocks[:2], profile="unreleased-v4")) == ["3.1", "3.2"]


_CK_ITEM_LIST = [
    _laid_block(1, "3.8 Under section 30 the Government invests all officers, \n3.9 A Under section 13(b) the Government "
                   "delegates his powers under the following rules, namely: - \n1 \nThe Punjab Intoxicants Licence "
                   "Orders. \n2 \nThe Punjab Liquor Licence Rules. \n3. The Punjab Tari Rules. \n4. The Punjab Brewery "
                   "Rules. \n", 1, 72.0, 480.0, 40.0),
    _laid_block(2, "3.10 Under section 13 every Collector may delegate powers. \n3.11 Under section 14 an appeal shall "
                   "lie. \n3.12 Under section 58 it is directed that the appeal be filed. \n", 1, 72.0, 480.0, 80.0)]


def test_spaced_letter_decimal_label_only_under_v4(monkeypatch):
    # Document 1973 p4: '3.9 A Under section 13(b) ...' is paragraph '3.9 A' (3.13-A cites it 'order 3.9-A').
    off = dict((p, t) for p, _, t in _ck_paths(S.segment(_CK_ITEM_LIST, profile=_v4_without(
        monkeypatch, "spaced_letter_decimal_label"))))
    assert off["s_3_9"].startswith("A Under section 13(b)")
    on = dict((p, t) for p, _, t in _ck_paths(S.segment(_CK_ITEM_LIST, profile="unreleased-v4")))
    assert "s_3_9" not in on and on["s_3_9_A"].startswith("Under section 13(b)")


def test_decimal_paragraph_item_list_only_under_v4(monkeypatch):
    # Document 1973 3.9 A and 3.13-A: '... namely: -' and then items '1 / The Punjab Intoxicants ...' with or
    # without a stop -- the paragraph's items, not sections 3 and 4.
    off = [p for p, _, _ in _ck_paths(S.segment(_CK_ITEM_LIST, profile=_v4_without(
        monkeypatch, "decimal_paragraph_item_list")))]
    assert "s_3" in off and "s_4" in off
    on = _ck_paths(S.segment(_CK_ITEM_LIST, profile="unreleased-v4"))
    assert [p for p, _, _ in on] == ["s_3_8", "s_3_9_A", "s_3_9_A.cl_1", "s_3_9_A.cl_2", "s_3_9_A.cl_3",
                                     "s_3_9_A.cl_4", "s_3_10", "s_3_11", "s_3_12"]
    assert dict((p, t) for p, _, t in on)["s_3_9_A.cl_1"] == "The Punjab Intoxicants Licence Orders."


def test_lettered_power_group_only_under_v4(monkeypatch):
    # Document 1973 3.5 (p3): '... declared to be as follows: -' then 'A / Powers of an Excise Officer of the 3rd
    # class.' with its (1), (2), then 'B / ...' with its own (1), (2): the groups had no unit and their items
    # collided as siblings.
    blocks = [
        _laid_block(1, "3.4 Under section 11 the persons mentioned below are invested with powers. \n",
                    1, 72.0, 480.0, 30.0),
        _laid_block(2, "3.5 Under section 10(b) the Powers of Excise Officers of the classes specified below are "
                       "declared to be as follows: - \n", 1, 72.0, 480.0, 40.0),
        _laid_block(3, "A \nPowers of an Excise Officer of the 3rd class. \n(1) \nPower under section 47 to seize any "
                       "person. \n(2) \nPower under section 47 to detain intoxicants. \nB \nPowers of an Excise Officer "
                       "of the 2nd class. \n(1) \nAll the powers of an Excise Officer of the 3rd class. \n(2) \nPower "
                       "under section 49 to search. \n", 1, 72.0, 480.0, 60.0),
        _laid_block(4, "3.6 Under section 14 an appeal shall lie. \n3.7 Under section 15 the Collector may revise. \n"
                       "3.8 Under section 30 the Government invests all officers. \n", 1, 72.0, 480.0, 100.0)]
    off = [p for p, _, _ in _ck_paths(S.segment(blocks, profile=_v4_without(monkeypatch, "lettered_power_group")))]
    assert "s_3_5.ss_1_n2_1" in off and not any(".cl_" in p for p in off)
    on = _ck_paths(S.segment(blocks, profile="unreleased-v4"))
    assert [p for p, _, _ in on if p.startswith("s_3_5.")] == [
        "s_3_5.cl_A", "s_3_5.cl_A.ss_1", "s_3_5.cl_A.ss_2", "s_3_5.cl_B", "s_3_5.cl_B.ss_1", "s_3_5.cl_B.ss_2"]
    assert dict((p, t) for p, _, t in on)["s_3_5.cl_B"] == "Powers of an Excise Officer of the 2nd class."


def test_bare_number_paragraph_only_under_v4(monkeypatch):
    # Document 1973 NWFP Orders (p8, owner q2 'body'): '4 / (a) Under section 11 ...', '5 / Under section 10 (b)
    # ...', '6', '7' -- no stop after the number; they ran into the last unit of the paragraph before.
    blocks = [
        _laid_block(1, "3.18 Not reproduced being unnecessary. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(2, "(1) \nThis notification may be cited as the North West Frontier Province Excise Powers "
                       "Orders. \n", 1, 72.0, 480.0, 60.0),
        _laid_block(3, "4 \n(a) \nUnder section 11 of the Punjab Excise Act all Excise Inspectors are invested with "
                       "powers. \n5 \nUnder section 10 (b) of the Punjab Excise Act the powers are declared. \n6 \n"
                       "Under section 14 an appeal shall lie. \n7 \nUnder section 58 the appeal shall be filed. \n",
                    1, 72.0, 480.0, 80.0)]
    off = [p for p, _, _ in _ck_paths(S.segment(blocks, profile=_v4_without(monkeypatch, "bare_number_paragraph")))]
    assert off == ["s_3_18", "s_3_18.ss_1", "s_3_18.ss_1.cl_a"]
    on = _ck_paths(S.segment(blocks, profile="unreleased-v4"))
    assert [p for p, _, _ in on] == ["s_3_18", "s_3_18.ss_1", "s_4", "s_4.cl_a", "s_5", "s_6", "s_7"]
    assert dict((p, t) for p, _, t in on)["s_5"].startswith("Under section 10 (b)")
    # inert below four consecutive bare numbers
    short = [_laid_block(3, "4 \n(a) \nUnder section 11 the Inspectors are invested. \n5 \nUnder section 10 the "
                            "powers are declared. \n", 1, 72.0, 480.0, 80.0)]
    assert "s_4" not in [p for p, _, _ in _ck_paths(S.segment(blocks[:2] + short, profile="unreleased-v4"))]


def test_dashed_stub_clause_cut_only_under_v4(monkeypatch):
    # Document 1973 3.4 (p3): '(a)------- / (b)------- / (c)-------' -- clauses printed as label and rule.
    blocks = [
        _laid_block(1, "3.4 Under section 11 the persons mentioned below are invested with powers: \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(2, "(a)------------------- \n(b)--------------- \n(c)--------------- \n(d) \nAll Excise "
                       "Inspectors employed in the Province. \n", 1, 72.0, 480.0, 60.0)]
    off = _ck_paths(S.segment(blocks, profile=_v4_without(monkeypatch, "dashed_stub_clause_cut")))
    assert [p for p, _, _ in off] == ["s_3_4", "s_3_4.cl_a", "s_3_4.cl_d"]
    on = _ck_paths(S.segment(blocks, profile="unreleased-v4"))
    assert [(p, t) for p, _, t in on][1:4] == [("s_3_4.cl_a", "-------------------"),
                                               ("s_3_4.cl_b", "---------------"), ("s_3_4.cl_c", "---------------")]


def test_decimal_name_contents_row_only_under_v4(monkeypatch):
    # Document 1973 p1: the contents print '3. / 3.3', '4. / 3.4' -- a row whose name is a paragraph number; the
    # rows ran together into row 2.
    blocks = [
        _laid_block(1, "CONTENTS \n", 1, 72.0, 480.0, 20.0),
        _laid_block(2, " \n1. \nIntroduction \n2. \nClasses of Excise Officers \n3. \n3.3 \n4. \n3.4 \n5. \n3.5 \n",
                    1, 72.0, 480.0, 40.0),
        _laid_block(3, "TEXT \n", 2, 72.0, 480.0, 20.0),
        _laid_block(4, "3.1 Introduction. The Punjab Government are pleased to make these orders. \n3.2 Classes of "
                       "Excise Officers. There shall be three classes. \n", 2, 72.0, 480.0, 40.0),
        _laid_block(5, "3.3 Under section 11 the persons below are invested with powers. \n3.4 Under section 12 the "
                       "persons below are invested. \n3.5 Under section 13 every Collector may delegate. \n",
                    2, 72.0, 480.0, 80.0)]
    off = _ck_paths(S.segment(blocks, profile=_v4_without(monkeypatch, "decimal_name_contents_row")))
    assert dict((p, t) for p, _, t in off)["s_2"].startswith("Classes of Excise Officers 3. 3.3")
    on = dict((p, t) for p, _, t in _ck_paths(S.segment(blocks, profile="unreleased-v4")))
    assert (on["s_2"], on["s_3"], on["s_4"]) == ("Classes of Excise Officers", "3.3", "3.4")
    # a rate table's '10. / 11', '11. / 10' (two rows, released doc 4433 p38) is not a run of three: no cut
    rate = [_laid_block(1, "1. Rates. The rates are as follows: \n10. \n11 \n11. \n10 \n9. \n", 1, 72.0, 480.0, 40.0)]
    assert _ck_paths(S.segment(rate, profile="unreleased-v4")) == [
        ("s_1", "Rates", "The rates are as follows: 10. 11 11. 10 9.")]


def test_explanation_of_heading_only_under_v4(monkeypatch):
    # Document 2146 E1 rr.21-34 (pp11-13): '21. Explanation of Estimates of Revenue. While explaining ...' -- the
    # rule's heading, not an Explanation; an Explanation is never followed directly by 'of'.
    blocks = [
        _laid_block(1, "20. Budget. The budget shall be prepared annually. \n", 1, 72.0, 480.0, 30.0),
        _laid_block(2, "21. Explanation of Estimates of Revenue. While explaining the estimates the variations shall "
                       "be shown. \n", 1, 72.0, 480.0, 40.0),
        _laid_block(3, "22. Explanation of the Statement of Demand for Grants. The statement shall be explained. \n"
                       "Explanation.- A grant includes a supplementary grant. \n", 1, 72.0, 480.0, 60.0)]
    off = dict((p, (h, t)) for p, h, t in _ck_paths(S.segment(blocks, profile=_v4_without(
        monkeypatch, "explanation_of_heading"))))
    assert off["s_21"] == (None, "") and off["s_21.expl_Explanation"][1].startswith("of Estimates of Revenue.")
    on = _ck_paths(S.segment(blocks, profile="unreleased-v4"))
    assert [(p, h) for p, h, _ in on] == [
        ("s_20", "Budget"), ("s_21", "Explanation of Estimates of Revenue"),
        ("s_22", "Explanation of the Statement of Demand for Grants"), ("s_22.expl_Explanation", None)]
    assert dict((p, t) for p, _, t in on)["s_21"] == "While explaining the estimates the variations shall be shown."


def test_v4_extends_v3():
    assert S.SEGMENTATION_PROFILES["unreleased-v3"] < S.SEGMENTATION_PROFILES["unreleased-v4"]
    for rule in ("level_margin_heading_text", "contents_bare_number_rows",
                 "paren_amendment_opener", "detached_heading_after_division",
                 "long_romanettes", "dash_closed_heading_guess",
                 "bracketed_rule_reference_division", "preamble_not_in_auxiliary",
                 "bracketed_repeal_stub_cut", "presidency_act_abbreviation",
                 "quoted_insertion_span", "repeated_label_note_rows",
                 "heading_prefix_of_sentence", "subsection_then_clause_cut",
                 "part_range_label", "sequential_chapter_title", "lettered_part_label",
                 "hyphen_suffix_labels", "percent_led_item", "contents_banner_block",
                 "form_code_number", "unbracketed_division_reference", "rs_line_item",
                 "form_word_not_letter", "bracketed_sub_rule_reference",
                 "marked_first_subsection", "marked_clause_cut",
                 "quoted_schedule_heading", "serial_abbreviation", "joint_schedule_heading",
                 "bracket_not_division_label", "member_designation_row",
                 "quoted_definition_cut", "lowercase_suffix_subsection", "lowercase_section_start",
                 "quote_before_bracket", "closed_marked_first_subsection", "letter_closing_finished",
                 "new_section_paragraph_not_note", "bracketed_section_number",
                 "schedule_title_reference_unit", "repeated_letter_clause",
                 "regulation_then_decimal_child", "kept_contents_stop_at_body_start",
                 "standalone_form_before_schedule",
                 "duplicate_witness_fields_as_form_text", "referenced_table_heading",
                 "no_cut_after_number_abbreviation", "page_first_running_header",
                 "whole_schedule_quote", "amendment_items_owner", "in_respect_of_not_opener",
                 "parenthesised_letter_label", "clause_then_romanette_cut",
                 "suffixed_decimal_label", "rule_range_not_opener", "sequential_part_heading",
                 "hyphen_letter_division_label", "lettered_paragraph_sequence",
                 "quoted_schedule_word_owner",
                 "sequential_form_label", "colon_closed_heading_guess",
                 "schedule_word_rows_own_items", "first_lettered_part_in_schedule",
                 "sequential_schedule_heading", "quoted_sequential_form_label",
                 "decimal_rule_resumes", "appended_form_at_page_top", "letter_number_form_code",
                 "label_only_heading_none", "not_reproduced_text",
                 "enactment_chapter_reference", "repeated_label_section_note_rows",
                 "left_column_margin_heading", "whole_section_quote",
                 "numbered_marked_first_subsection", "quoted_first_definition",
                 "marked_suffixed_definition", "bare_trailing_label_cut",
                 "apparatus_over_margin_heading", "dotted_omission_stub_cut",
                 "ordinal_schedule_reference", "enacting_formula_not_member_list",
                 "dotted_contents_row_cut", "last_promised_section_after_schedule",
                 "serial_column_header_owner", "colon_closed_contents_heading",
                 "contents_row_decimal_cut", "titled_appended_form",
                 "definition_lead_not_heading", "schedule_amendment_item",
                 "schedule_item_rows_in_order", "quoted_part_span",
                 "body_start_without_contents", "ordinal_quoted_schedule_word",
                 "repeated_decimal_label_cut", "dotted_other_heading",
                 "indented_list_item_continues", "schedule_title_first_statutes",
                 "statute_rows_margin_evidence", "bare_number_schedule_name_row",
                 "side_noted_definition_cut", "numbered_schedule_form", "misprinted_chapter_word",
                 "misprinted_form_word", "quoted_hyphen_form_label",
                 "appendix_number_label", "lowercase_hyphen_label_cut", "ditto_item_cut",
                 "dotted_nameless_contents_row", "number_abbreviation_line_end",
                 "definition_lead_not_name",
                 "contents_leader_page_strip",
                 "omission_stub_closes_table",
                 "fbr_definition_label",
                 "label_then_marked_text_cut",
                 "marked_proviso_cut",
                 "bare_marker_label",
                 "multi_letter_subsection",
                 "marked_chapter_heading",
                 "marked_lettered_omission_stub",
                 "bare_bracket_clause_cut",
                 "inserted_three_letter_clause",
                 "closed_marked_clause_cut",
                 "four_letter_section_suffix",
                 "bare_omission_stub",
                 "e_prefix_section_start",
                 "high_ordinal_schedule",
                 "column_head_line_cut",
                 "schedule_tables_annexes_parts",
                 "roman_stub_item_cut",
                 "stub_row_cut",
                 "schedule_table_rows_own_items",
                 "capital_letter_item",
                 "figure_led_item",
                 "four_digit_marker_label_cut",
                 "range_stub_row",
                 "marked_quoted_label",
                 "stacked_marker_row",
                 "schedule_division_heading_lines",
                 "unnumbered_tail_provision",
                 "unnumbered_root_provision",
                 "starred_letter_stub_cut",
                 "status_row_order_only",
                 "order_rule_owns_subrules",
                 "marked_order_heading",
                 "amendment_word_heading_not_note",
                 "ordinal_schedule_closes_part",
                 "appendix_numbered_form",
                 "form_schedule_caption",
                 "appendix_form_paragraphs",
                 "connective_not_clause_label",
                 "unlabelled_schedule_opener",
                 "quoted_table_row_text",
                 "range_repeal_stub",
                 "range_contents_row",
                 "printed_heading_override",
                 "unclosed_paren_heading_guess",
                 "order_suffix_label",
                 "named_schedule_row",
                 "contents_opener_later_units",
                 "reviewed_contents_alignment",
                 "schedule_group_caption",
                 "uncontented_subpart_scan_schedule_bound",
                 "owner_cited_label",
                 "substituted_schedule_items",
                 "not_running_header_blocks",
                 "level_cell_blocks",
                 "quoted_letter_annexure_title",
                 "notification_preamble_row",
                 "unlabelled_appendix_opener",
                 "bare_serial_row",
                 "appendix_note_caption",
                 "half_paren_clause_label",
                 "order_suffix_one_block",
                 "dotted_form_code",
                 "bracketed_repeal_stub_text",
                 "numbered_starred_first_subsection",
                 "parenthesised_lettered_division",
                 "stray_label_continuation",
                 "blank_rule_heading_none",
                 "root_provision_member_list",
                 "numeric_quote_definition_cut",
                 "apparatus_over_left_margin_heading",
                 "unlabelled_schedule_before_row",
                 "stray_number_continuation",
                 "bracketed_omit_section_stub",
                 "contents_split_division_name",
                 "terse_sentence_not_heading",
                 "decimal_paragraph_cut",
                 "spaced_letter_decimal_label",
                 "decimal_name_contents_row",
                 "decimal_paragraph_item_list",
                 "lettered_power_group",
                 "bare_number_paragraph",
                 "dashed_stub_clause_cut",
                 "explanation_of_heading"):
        assert rule not in S.SEGMENTATION_PROFILES["unreleased-v3"]
        assert rule in S.SEGMENTATION_PROFILES["unreleased-v4"]


def test_order_suffix_label_honoured_with_a_reading_in_any_profile(monkeypatch):
    # agent DE (owner 12 Oct): a released default-profile observation cannot be pinned, so the reviewed spec gates it
    from nizam.shared.corpus_types import order_suffix
    blocks = _hackney_act()
    without_rule = S.segment(blocks, profile=_v4_without(monkeypatch, "order_suffix_label"),
                             structural_overrides=_order_suffix())
    default = S.segment(blocks, structural_overrides=_order_suffix())
    for seg in (without_rule, default):
        sections = [n for n in seg.flatten() if n.kind == "section"]
        paths = {id(node): path for node, path in S.assign_paths(seg, "kp.act.y1879_XIV")}
        assert [order_suffix(paths[id(n)]) for n in sections] == ["", "", "(second)", ""]
        assert seg.repeated_label_decisions == []
