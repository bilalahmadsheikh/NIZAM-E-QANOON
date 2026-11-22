"""D-115: a statutory notification that numbers no paragraph is one unit (profile notification-v1)."""
from nizam.corpus.segment import SEGMENTATION_PROFILES, assign_paths, segment


def _blocks(*texts, x0=72.0):
    return [{"id": n + 1, "text": t, "page_no": 1, "y0": 60.0 + 30 * n, "page_height": 842.0, "x0": x0, "x1": 520.0}
            for n, t in enumerate(texts)]


MAST = ("GOVERNMENT OF PAKISTAN \nSECURITIES AND EXCHANGE COMMISSION OF PAKISTAN \n",
        "  \nIslamabad, the 23rd June, 2022  \n  \nNOTIFICATION  \n")


def test_a_single_paragraph_notification_is_one_unit_and_its_file_number_stays_out():
    blocks = _blocks(*MAST,
                     "S.R.O.2393(I)/2025.- In exercise of the powers conferred under section 512 of the \n"
                     "Companies Act, 2017 (XIX of 2017), the Securities and Exchange Commission of Pakistan hereby \n"
                     "makes the following amendment to the Auditors (Reporting Obligations) Regulations, 2018, namely: - \n",
                     "In the aforesaid Regulations, in regulation 2, in sub-regulation (1), clause (viii) shall be \n"
                     "substituted, namely: - \n",
                     " \n \n[File No. CLD/CCD/PR(12)/2017] \n \n",
                     "(Afnan Khan)\nSecretary (Enforcement)\n")
    default = segment(blocks)
    assert default.root.children == []                           # the defect: nothing is a provision
    seg = segment(blocks, profile="notification-v1")
    [unit] = seg.root.children
    assert (unit.kind, unit.label) == ("notification", "Notification")
    assert unit.text.startswith("S.R.O.2393(I)/2025.- In exercise of the powers")
    assert unit.text.endswith("clause (viii) shall be substituted, namely: -")
    roles = {bid: r[0] for bid, r in seg.block_roles.items()}
    assert roles == {1: "preface", 2: "preface", 3: "body", 4: "body", 5: "preface", 6: "preface"}
    assert [p for _, p in assign_paths(seg, "fed.sro.y2025_o1")] == ["fed.sro.y2025_o1.notif_Notification"]
    assert {"resolution": "notification_unit"} in seg.structural_reviews_enacted


def test_items_hang_beneath_the_notification_in_order():
    blocks = _blocks(*MAST,
                     "S.R.O. 959 (I)/2022.- In exercise of the powers conferred under sub-section (1) of \n"
                     "section 169 of the Securities Act, 2015, the Commission hereby makes the following amendments, namely:-\n",
                     "  \n In the aforesaid Regulations, -  \n \n",
                     "(1)  \nin regulation 18, sub-regulation (5) shall be omitted;  \n \n",
                     "(2)  \nin Annexure III, in paragraph (2) after sub-paragraph (vi), the following new \n"
                     "sub-paragraph (vii) shall be inserted, namely:- \n")
    seg = segment(blocks, profile="notification-v1")
    [unit] = seg.root.children
    assert unit.kind == "notification" and unit.text.endswith("In the aforesaid Regulations, -")
    assert [(c.kind, c.label) for c in unit.children] == [("subsection", "1"), ("subsection", "2")]
    assert all(c.parent is unit for c in unit.children) and unit.depth == 3


def test_the_head_is_cut_out_of_a_masthead_block_and_a_glued_file_number_is_cut_off():
    blocks = _blocks("GOVERNMENT OF PAKISTAN\n",
                     "Islamabad, 7th December, 2018 \nNOTIFICATION \n \n \nS.R.O. 1480 (I)/2018.- In exercise of the "
                     "powers conferred by section 40B of the Securities and Exchange Commission of Pakistan Act, 1997, "
                     "the Commission is pleased to direct that the Registrar shall act, with effect from the date of "
                     "this notification. [No. SMD/CIW/CR/03/2012]\n")
    seg = segment(blocks, profile="notification-v1")
    [unit] = seg.root.children
    assert unit.text.startswith("S.R.O. 1480 (I)/2018.- In exercise")
    assert unit.text.endswith("with effect from the date of this notification.")


def test_a_gazette_text_layers_broken_head_still_opens_the_unit():
    blocks = _blocks("GOVERNMENT OF PAKISTAN\nREVENUE DIVISION\nFEDERAL BOARD OF REVENUE\n", "NOTIFICATION\n",
                     "s.R.o. ti, \n0/2026.- ln exercise of the powers conferred by section 219 of the customs Act, "
                     "1969 (IV of 1969), the Federal Board of Revenue is pleased to direct that the following further "
                     "amendments shall be made in the Customs Rules, 2001, namely:-\n")
    [unit] = segment(blocks, profile="notification-v1").root.children
    assert unit.kind == "notification" and unit.text.startswith("s.R.o. ti, 0/2026.- ln exercise")


def test_a_gazette_masthead_read_as_a_part_is_dissolved():
    blocks = _blocks("PART II \n", "Statutory Notification (S. R. O) \n", *MAST,
                     "S.R.O 9(I)/2007.--In exercise of the powers conferred by subsection (5) of section 234 of the "
                     "Companies Ordinance, 1984, the Commission is pleased to exempt the companies, namely:-\n",
                     "(a) \nthe first class of companies;\n", "(b) \nthe second class of companies.\n")
    default = segment(blocks)
    assert [c.kind for c in default.root.children] == ["part"]
    seg = segment(blocks, profile="notification-v1")
    assert [c.kind for c in seg.root.children] == ["notification"]
    assert seg.block_roles[1][0] == "preface"


def test_a_numbered_law_and_a_draft_are_left_alone():
    numbered = _blocks(*MAST, "S.R.O. 1(I)/2020.- In exercise of the powers conferred by section 1, the Commission "
                       "makes the following regulations, namely:-\n",
                       "1. Short title and commencement.- (1) These regulations may be called the Test "
                       "Regulations, 2020.\n", "2. Definitions.- In these regulations, unless there is anything repugnant.\n")
    assert ([c.kind for c in segment(numbered, profile="notification-v1").root.children]
            == [c.kind for c in segment(numbered).root.children])
    draft = _blocks(*MAST, "S.R.O.946(I) /2011.- The following draft of certain amendments in the Securities Rules, "
                    "2011, which are proposed to be made in exercise of powers conferred by section 33, is published.\n")
    assert segment(draft, profile="notification-v1").root.children == []


def test_the_profile_is_the_default_plus_the_two_rules():
    assert SEGMENTATION_PROFILES["notification-v1"] == {"gazette_masthead_part", "notification_unit"}
    assert not SEGMENTATION_PROFILES["default"] & {"gazette_masthead_part", "notification_unit"}
