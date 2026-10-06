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
                 "unnumbered_root_provision"):
        assert rule not in S.SEGMENTATION_PROFILES["unreleased-v3"]
        assert rule in S.SEGMENTATION_PROFILES["unreleased-v4"]
