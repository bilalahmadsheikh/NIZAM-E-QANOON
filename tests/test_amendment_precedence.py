"""Where a provincial code prints a rule twice, the later print is the law.

A provincial code reprints a rule under one number: the text as first made, a
preamble naming the amendment, then the text that replaced it. Both prints are
siblings bearing that number, so the repeated-label rule has to choose, and
until this rule existed it chose the FIRST -- the text the page itself says was
substituted.

Punjab Prisons Rules (document 4474) page 44, verbatim:

    Fixing of date of execution.
    Rule105. In the event of the final orders of Government to carry out
    executions, the Superintendent shall appoint a day for execution not more
    than a week later than the date on which such orders actually reach him...
    Punjab Amendment:  For rule   105, the following shall be substituted:-
    Execution of Condemned Prisoners.
    Rule 105. (i) On receipt of the final orders of the Government to carry out
    the execution, the Superintendent Jail, shall request the Trial Court
    concerned to fix a date for the execution of the sentence of death...

and page 60:

    Action in case of difference of opinion.
    Rule144. If the District Magistrate dissents from the Superintendent's
    recommendations, the case shall be submitted through the Inspector-General
    to Government for orders.
    Punjab Amendment:
    Action in case of difference of opinion.
    Rule144. Omitted by Punjab Notification No. SO (Prs.j 18-1/2002, dated
    12.1.2002.

Rule 144 is the reason this is an INV-5 defect and not a tidiness one: the
corpus made citable a rule the Punjab government omitted by notification in
2002. No `as_of` and no `operative_provision` can be right about a date when
the tree kept the superseded print.

Segmentation is pure, so every case below is the source text, cut down to the
blocks that carry the device, with no database.
"""
from __future__ import annotations

from nizam.corpus.segment import segment


def blocks(*texts: str, page: int = 1) -> list[dict]:
    """Blocks as the extractor hands them over: id, text, page, geometry."""
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0, "x0": 55.0, "x1": 520.0}
            for i, t in enumerate(texts)]


def paged(*pairs: tuple[int, str]) -> list[dict]:
    """Blocks spanning pages: (page_no, text) in reading order."""
    return [{"id": i, "text": t, "page_no": pg, "y0": 100.0 + i * 20,
             "page_height": 792.0, "x0": 55.0, "x1": 520.0}
            for i, (pg, t) in enumerate(pairs)]


def sections(seg) -> dict:
    """Citable nodes by label, anywhere in the tree."""
    found = {}
    def walk(node):
        for child in node.children:
            if child.kind in ("section", "article"):
                found.setdefault(str(child.label).replace(" ", ""), child)
            walk(child)
    walk(seg.root)
    return found


# ------------------------------------------------- the device, as printed
def test_substituted_rule_is_citable_and_not_the_text_it_replaced():
    """Punjab Prisons Rules page 44, rule 105."""
    seg = segment(blocks(
        "Fixing of date of execution. \n",
        "Rule105. In the event of the final orders of \nGovernment to carry out "
        "executions, the Superintendent shall \nappoint a day for execution not "
        "more than a week later than \nthe date on which such orders actually "
        "reach him. \nPunjab Amendment:  For rule   105, the following shall be \n"
        "substituted:- \nExecution of Condemned Prisoners. \n",
        "Rule 105. (i) On receipt of the final orders of the \nGovernment to carry "
        "out the execution, the Superintendent \nJail, shall request the Trial "
        "Court concerned to fix a date for \nthe execution of the sentence of "
        "death, in accordance with \nparagraph 39 of Chapter 24-B of the High "
        "Court Rules. \n",
    ))
    rule_105 = sections(seg)["105"]
    assert rule_105.first_block == 2, (
        "the citable rule 105 must be the print BELOW the amendment preamble; "
        f"got block {rule_105.first_block}")
    assert "Trial Court" in "".join(rule_105.text_parts) + str(
        [c.text for c in rule_105.children])


def test_omission_record_supersedes_the_rule_it_omits():
    """Punjab Prisons Rules page 60, rule 144 -- omitted by notification, 2002.

    The preamble names no rule here; the marginal heading is reprinted instead.
    """
    seg = segment(blocks(
        "Action in case of difference of opinion. \n",
        "Rule144. If the District Magistrate dissents from the \n"
        "Superintendent's recommendations, the case shall be \nsubmitted through "
        "the Inspector-General to Government for \norders. \n"
        "Punjab Amendment: \nAction in case of difference of opinion. \n",
        "Rule144. Omitted by Punjab Notification No. SO (Prs.j \n"
        "18-1/2002, dated 12.1.2002. \n",
    ))
    assert sections(seg)["144"].first_block == 2, (
        "rule 144 was omitted in 2002; the omission record is the current law "
        "and the repealed text must not be what a citation renders")


def test_preamble_may_sit_in_its_own_block_behind_a_marginal_heading():
    """Page 105, rule 255: preamble, then a new marginal heading, then the rule.

    This is the widest confirmed gap between preamble and reprint, and the
    reason the search window is three blocks rather than one.
    """
    seg = segment(blocks(
        "Furniture. \n",
        "Rule255. (i) Rooms shall be supplied with following \narticles:- \n"
        "One cot, one chair, one teapoy, one lantern if there \nis no electric "
        "light, one shelf, and necessary washing appliances. \n",
        "Punjab Amendment:    The    existing   rule    255,    shall   be) \n"
        "substituted as under:- \n",
        "“More Furniture” \n",
        "Rule255. (i) Rooms shall be supplied with following \narticles:— \n"
        "One cot woven with niwar, one chair, one tea-pot, and table lamp, \n"
        "one shelf, one ash tray, one wooden rack and necessary appliances. \n",
    ))
    assert sections(seg)["255"].first_block == 4


def test_the_device_works_across_a_page_break():
    """Page 108-109, rule 260: the original ends one page, the amendment opens
    the next. The two prints must still be read as one collision."""
    seg = segment(paged(
        (108, "Diet. \n"),
        (108, "Rule260. (i) Superior diet shall be provided according to \nthe "
              "following scale; provided that the Inspector General may, \nwith "
              "the approval of the Government, modify or alter the scale. \n"),
        (109, "Punjab Amendment: Better Diet. \n"),
        (109, "Rule260. Against the below noted items the quantity \nbe "
              "substituted as follows: wheat atta, dal, meat, milk and sugar \n"
              "at the revised scale set out in the table below. \n"),
    ))
    assert sections(seg)["260"].first_block == 3


# ------------------------------------- the device is not Punjab's alone
def test_sindh_and_baluchistan_wordings_move_the_citation_too():
    """Measured over the corpus, the preamble is written with four different
    qualifiers -- Punjab (37 lines), Sindh (4), Sind (3) and Baluchistan (2) --
    and document 3267 prints three of them against one Act. A pattern that
    named only Punjab would leave the same INV-5 defect standing in the other
    provinces' codes, so the qualifier is not enumerated.
    """
    for qualifier in ("Sindh Amendment", "Sind Amendment",
                      "Baluchistan Amendment", "N.-W.F.P. Amendment"):
        seg = segment(blocks(
            "Register of prisoners. \n",
            "Rule12. The officer shall keep the register in the form \n"
            "prescribed by the Inspector-General from time to time, and shall \n"
            "enter in it the particulars of every prisoner admitted. \n"
            f"{qualifier}:  For rule 12, the following shall be \n"
            "substituted:- \nRegister of prisoners. \n",
            "Rule 12. The officer shall keep the register in the revised form \n"
            "prescribed by the Government under this rule, and shall enter in \n"
            "it the particulars of every prisoner admitted or released. \n",
        ))
        assert sections(seg)["12"].first_block == 2, qualifier


def test_a_flattened_footnote_marker_before_the_qualifier_is_tolerated():
    """PyMuPDF glues a superscript to the word after it: "56Punjab Amendment:"."""
    seg = segment(blocks(
        "Locking of the gate. \n",
        "Rule 9. The gate shall be locked at sunset and the key shall be \n"
        "kept in the office of the Officer In-charge until the following \n"
        "morning. \n"
        "56Punjab Amendment: For rule 9, the following shall be \n"
        "substituted:- \nLocking of the gate. \n",
        "Rule 9. The gate shall be locked at sunset and the key kept by the \n"
        "Officer In-charge in person until sunrise on the following day. \n",
    ))
    assert sections(seg)["9"].first_block == 2


# ------------------------------------------------------------- the guards
def test_a_preamble_naming_another_rule_moves_nothing():
    """Page 187 prints "Punjab  Amendment:   108In rule  518(i)  the  scale  of
    ..." beside sibling labels 2 and 8. That preamble is evidence about rule
    518 and must not decide a collision it has nothing to do with."""
    seg = segment(blocks(
        "Rule 7. The scale of rations shall be as set out in the schedule. \n"
        "Punjab Amendment: In rule 518(i) the scale of diet for labouring \n"
        "prisoners shall be substituted as under:- \n",
        "Rule 7. A wholly different provision that merely repeats the number \n"
        "seven because the compiler restarted the appendix numbering here. \n",
    ))
    assert sections(seg)["7"].first_block == 0


def test_an_insertion_preamble_moves_nothing():
    """"After rule 545-A, the following rule 545-B shall be inserted:-" adds a
    new rule; it is not evidence that an earlier print was replaced."""
    seg = segment(blocks(
        "Rule 4. Visitors shall be admitted between nine and eleven o'clock. \n"
        "Punjab Amendment: After rule 3, the following rule 4 shall be \n"
        "inserted:- \n",
        "Rule 4. A second print of this number that the preamble does not \n"
        "claim to substitute for anything at all. \n",
    ))
    assert sections(seg)["4"].first_block == 0


def test_an_amendment_note_list_item_does_not_steal_a_rule_number():
    """West Pakistan Opium Rules (document 3267). Page 2 prints rule 2
    (definitions); page 3 prints "Punjab Amendment: Cl. (f) has been subs. By
    Notification No. 64/75/43/Ex-II-(P) ... as under :", the replacement clause,
    and then "2. Throughout the rule for the words ..." -- item 2 of the
    notification's own instructions, not a reprint of rule 2. Moving the
    citation onto it would replace a definitions rule with a drafting
    instruction, so the reprint must identify itself as that unit.
    """
    seg = paged(
        (2, "2. \nUnless there is anything repugnant in the subject or "
            "context- \n"),
        (2, "(f) \n“Commissioner” means the Commissioner incharge of a "
            "revenue division. \n"),
        (3, "Punjab Amendment: \nCl. (f) has been subs. By Notification No. "
            "64/75/43/Ex-II-(P), published \nin Gazette of Punjab, "
            "Extraordinary, Part I, dated 4th March, 1977 as under : \n"),
        (3, "“(f) “Commissioner” means the Director-General Excise "
            "and Taxation, Punjab. \n"),
        (3, "2.  \nThroughout the rule for the words “Boards of Revenue” "
            "wherever \noccurring, the word “Commissioner” shall be "
            "substituted”. ] \n"),
    )
    found = sections(segment(seg))
    assert found["2"].first_block == 0, (
        "rule 2 must stay the definitions rule printed on page 2")


def test_a_document_with_no_amendment_preamble_is_untouched():
    """The rule scores -1 for every print in a group it does not apply to, so
    an ordinary repeated label still falls to the existing signals: first
    occurrence, source order."""
    seg = segment(blocks(
        "Rule 3. The first printing of this rule, which carries the law. \n",
        "Rule 3. A later table row that repeats the number and no more. \n",
    ))
    assert sections(seg)["3"].first_block == 0


def test_the_reason_is_recorded_on_the_decision():
    """A parser decision that moves a citation has to say why, or an S7
    reviewer sees only the result (doc 02 §8)."""
    seg = segment(blocks(
        "Fixing of date of execution. \n",
        "Rule105. In the event of the final orders of Government to carry \n"
        "out executions, the Superintendent shall appoint a day for \n"
        "execution not more than a week later than the date of the orders. \n"
        "Punjab Amendment:  For rule   105, the following shall be \n"
        "substituted:- \nExecution of Condemned Prisoners. \n",
        "Rule 105. (i) On receipt of the final orders of the Government to \n"
        "carry out the execution, the Superintendent Jail shall request the \n"
        "Trial Court concerned to fix a date for the execution. \n",
    ))
    decisions = [d for d in seg.repeated_label_decisions
                 if d["printed_label"].replace(" ", "") == "105"]
    assert len(decisions) == 1
    assert "Punjab Amendment" in (decisions[0]["amendment_preamble"] or "")
