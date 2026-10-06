"""Source-backed parser regressions from documents 118 and 956 official PDFs."""

from nizam.corpus.segment import segment
from nizam.corpus.segment import _is_enactment_history_footnote, classify


def _source_blocks():
    rows = [
        (3421, 2, 72, "1.\nShort title, extent and commencement.– (1) This Act may be called the\nPunjab Acquisition of Land (Housing) (Repeal) Act, 1985.\n"),
        (3424, 2, 72, "2.\nRepeal of Act VIII of 1973.– The Punjab Acquisition of Land (Housing) Act,\n1973 (VIII of 1973) is hereby repealed.\n"),
        (3425, 2, 72, "3.\nContinuation of acquisition proceedings and assessment etc. of\ncompensation.– Where in a case proceedings have commenced under the Punjab\nAcquisition of Land (Housing) Act 1973 or under its provisions as incorporated or\nreferred to in any other law, rule or instrument, for the time being in force, the same\nshall continue and shall be completed under the provisions of the said Act and the\nrules made thereunder:\n"),
        (3426, 2, 72, "Provided that where in a case an award has not been made under section 7\nof the said Act at the time of commencement of this Act, the compensation in such a\ncase shall be assessed, awarded and paid under the provisions of the Land\nAcquisition Act, 1894 (I of 1894):\n"),
        (3427, 2, 72, "Provided further that in a case in which an award has been made before the\ncommencement of this Act under the Punjab Acquisition of Land (Housing) Act, 1973\nbut the payment of compensation or a part thereof is to be made through bonds,\ndebentures or annuities, the said compensation shall become due for immediate\npayment in cash on the commencement of this Act unless the owner whose land has\nbeen acquired chooses to adjust the same towards the cost of any developed site\nwhich may have been given to him as part of compensation\n"),
        (3431, 3, 72, "3[Provided further that for the purpose of operation of this section the following\nprovisions of the Punjab Acquisition of Land (Housing) Act, 1973 shall be read as\nmentioned hereunder:–\n"),
        (3432, 3, 108, "1.\nIn the Preamble the words “urban and rural areas of” shall be deemed\nto have been deleted.\n"),
        (3433, 3, 108, "2.\nIn section 2, sub-section (1)–\n"),
        (3434, 3, 144, "(i)\nclause (a) shall be read as:–\n"),
        (3442, 3, 144, "(v)\nclauses (h) and (i) shall be deemed to have been omitted.\n"),
        (3443, 3, 108, "3.\nIn section 6, sub-section (1) the words “Government intends” shall be\nread as:-\n"),
    ]
    geometry = {
        3421: (284.796, 523.267, 314.688),
        3424: (363.996, 523.393, 393.888),
        3425: (403.596, 523.526, 488.688),
        3426: (492.540, 523.385, 549.888),
        3427: (553.740, 523.408, 652.488),
        3431: (70.980, 522.998, 114.528),
        3432: (118.380, 523.023, 148.128),
        3433: (151.980, 298.152, 167.928),
        3434: (171.636, 330.792, 188.352),
        3442: (454.380, 485.952, 470.328),
        3443: (474.180, 523.163, 503.928),
    }
    return [{"id": id_, "page_no": page, "text": text, "x0": x0,
             "x1": geometry[id_][1], "y0": geometry[id_][0],
             "y1": geometry[id_][2], "page_height": 841.920}
            for id_, page, x0, text in rows]


def test_doc118_section_two_and_third_proviso_item_two_keep_distinct_identities():
    seg = segment(_source_blocks())
    nodes = seg.flatten()
    section2 = next(n for n in nodes if n.first_block == 3424)
    section3 = next(n for n in nodes if n.first_block == 3425)
    third_proviso = next(n for n in nodes if n.first_block == 3431)
    item1 = next(n for n in nodes if n.first_block == 3432)
    item2 = next(n for n in nodes if n.first_block == 3433)
    romanette = next(n for n in nodes if n.first_block == 3434)
    final_romanette = next(n for n in nodes if n.first_block == 3442)
    item3 = next(n for n in nodes if n.first_block == 3443)
    assert (section2.kind, section2.label, section2.parent) == ("section", "2", seg.root)
    assert (third_proviso.kind, third_proviso.parent) == ("proviso", section3)
    assert (item2.kind, item2.label, item2.parent) == (
        "clause", "2", third_proviso), [
            (n.kind, n.label, n.first_block,
             n.parent.first_block if n.parent else None) for n in nodes]
    assert (item1.kind, item1.label, item1.parent) == ("clause", "1", third_proviso)
    assert (item3.kind, item3.label, item3.parent) == ("clause", "3", third_proviso)
    assert (romanette.kind, romanette.label, romanette.parent) == ("clause", "i", item2)
    assert (final_romanette.kind, final_romanette.label, final_romanette.parent) == (
        "clause", "v", item2)
    assert "In section 2, sub-section (1)" in item2.text
    assert 3424 in section2.blocks and 3433 in item2.blocks
    assert section2 is not item2


def test_doc956_amendment_marker_is_not_a_section_or_continuation():
    """Document 956 official page 3: superscript 10 opens section 3's proviso."""
    source = ("            10[Provided that no proceeding shall be taken under this section against \n"
              "any person in respect of any disobedience to the prohibition contained in sub-\n"
              "section (2) of that section, save with the sanction of the authority competent to \n"
              "issue \nthe \nrequisite \npassport \nor \npass \nas \nthe \ncase \nmay \nbe]. \n \n")
    decision = classify(source)
    assert decision is not None
    assert decision[:2] == ("proviso", "Provided")
    assert "no proceeding shall be taken" in decision[2]


def test_doc956_closed_proviso_does_not_absorb_following_section_paragraph():
    """Official PDF p.3 prints Section 3 prose after the closed 10[proviso]."""
    rows = [
        (45047, 313.718, "3. Whoever disobeys, or attempts to disobey, "
         "or abets another person shall be punishable with fine not "
         "exceeding five hundred rupees:"),
        (45048, 394.766, "10[Provided that no proceeding shall be taken "
         "under this section without sanction]."),
        (45049, 479.818, "The provisions of sections 64, 67, 68, 69 and 70 "
         "of the Pakistan Penal Code shall apply to all fines imposed "
         "under this section."),
    ]
    blocks = [{"id": block_id, "page_no": 3, "x0": 100.820,
               "x1": 499.900, "y0": y0, "y1": y0 + 50,
               "page_height": 842.0, "text": text}
              for block_id, y0, text in rows]
    seg = segment(blocks)
    section = next(node for node in seg.flatten() if node.first_block == 45047)
    proviso = next(node for node in seg.flatten() if node.first_block == 45048)
    assert proviso.parent is section
    assert "no proceeding shall be taken" in proviso.text
    assert "The provisions of sections" not in proviso.text
    assert "The provisions of sections" in section.text
    assert seg.block_roles[45049][1] is section


def test_doc118_enactment_history_below_rule_is_not_proviso_text():
    source = ("1This Act was passed by the Punjab Assembly on 10th November, 1985; assented to by the Governor of the Punjab on 13th\n"
              "November, 1985; and, was published in the Punjab Gazette (Extraordinary), dated 13th November, 1985, Pages 5381-A to\n"
              "5381-C.\n")
    blocks = _source_blocks()
    blocks.insert(5, {"id": 3429, "page_no": 2, "text": source,
                      "x0": 72.000, "y0": 682.415, "x1": 523.557,
                      "y1": 712.405, "page_height": 841.920})
    seg = segment(blocks)
    assert seg.block_roles[3429][0] == "footnote"
    assert all("This Act was passed by" not in node.text for node in seg.flatten())


def test_amending_section_and_other_brackets_are_not_provisos():
    assert classify("4. In section 15 of the said Act, the words shall be substituted.")[:2] == (
        "section", "4")
    assert classify("10[In section 2, words shall be omitted.]") is None


def test_enactment_history_note_requires_provenance_and_bottom_position():
    source = ("1This Act was passed by the Punjab Assembly; assented to by the "
              "Governor; published in the Punjab Gazette.")
    assert not _is_enactment_history_footnote(
        source, {"y0": 100, "page_height": 842})
    assert not _is_enactment_history_footnote(
        "1This Act was passed by the Assembly.",
        {"y0": 700, "page_height": 842})


def test_doc247_released_source_prints_bracketed_proviso_under_subsection_three():
    """Official PDF p.3 shows superscript 3, then an indented proviso."""
    rows = [
        (10530, 2, 530.664, 528.700, 562.572,
         "3.\n(1)\nThere shall be a Balochistan Public Service \nCommission. \n"),
        (10539, 3, 167.864, 528.700, 215.572,
         "(3)\nThe Chairman1 and other members of the \nCommission shall be appointed by the 2[Governor in \nconsultation with the Chief Minister.] \n"),
        (10540, 3, 221.364, 528.800, 269.072,
         "3[Provided that no person below the age of 55 \nyears shall be appointed as Chairman or Member of the \nCommission.]\n"),
        (10541, 3, 274.964, 528.800, 322.672,
         "(4)\nNo proceeding or act of the Commission shall be \ninvalid merely on the ground of existence of any vacancy in or \nany defect in the Constitution of the Commission.\n"),
    ]
    blocks = [{"id": bid, "page_no": page, "x0": 217.0, "y0": y0,
               "x1": x1, "y1": y1, "page_height": 842.0, "text": source}
              for bid, page, y0, x1, y1, source in rows]
    seg = segment(blocks)
    nodes = seg.flatten()
    subsection3 = next(node for node in nodes if node.first_block == 10539)
    proviso = next(node for node in nodes if node.first_block == 10540)
    subsection4 = next(node for node in nodes if node.first_block == 10541)
    assert (proviso.kind, proviso.parent) == ("proviso", subsection3)
    assert 10540 in proviso.blocks
    assert "no person below the age of 55" in proviso.text
    assert subsection4.parent is subsection3.parent


def test_doc120_released_source_prints_bracketed_proviso_under_section_three_one():
    """Official PDF p.2: footnote marker 3 precedes an operative proviso."""
    rows = [
        (3499, 462.964,
         "Effect of Repeal. 3. (1) Notwithstanding anything contained in any "
         "existing law, the provisions of this Act shall take effect."),
        (3500, 611.664,
         "3[Provided that a case tried by a Deputy Commissioner, or any "
         "other court or authority, in its original jurisdiction under the "
         "laws listed in the Schedule of the Act shall not be affected, "
         "the trial thereof shall continue as before.]"),
        (3501, 681.064,
         "(2) This repeal shall not, unless a contrary intention appears."),
    ]
    blocks = [{"id": bid, "page_no": 2, "x0": 412.0,
               "x1": 1000.0, "y0": y0, "y1": y0 + 45.0,
               "page_height": 1600.0, "text": source}
              for bid, y0, source in rows]
    seg = segment(blocks)
    nodes = seg.flatten()
    proviso = next(node for node in nodes if node.first_block == 3500)
    assert proviso.kind == "proviso"
    assert proviso.parent is not None
    assert proviso.parent.kind == "subsection"
    assert proviso.parent.label == "1"
    assert "trial thereof shall continue" in proviso.text
    assert seg.block_roles[3500][0] == "body"
