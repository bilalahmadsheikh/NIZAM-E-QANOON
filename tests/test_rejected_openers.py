"""Four printed openers the classifier used to refuse (doc 02 §5.1, §8).

Every block quoted here is a whole source block from `v_release_text_block`,
copied verbatim into `fixtures/rejected-openers.json`; nothing is transcribed
and no fixture holds a complete Act. Each shape is a section that IS printed in
the PDF's text layer and that no citation could reach, because `classify()`
refused its opener -- so the node was never built, and the contents row that
promised it became a gap, or vanished from the promises altogether.

The shapes, by their names in the reader-instruction catalogue:

    (c)  a section number printed bare, before its first subsection
    (t)  a footnote-marker LIST before the amendment bracket
    (u)  a label inside the bracket with no period
    (j)  the section number set in its own column

Each test asserts the rule, not today's corpus count, and each carries the
counter-examples the rule has to keep refusing -- because two of these four are
one character away from a cross-reference, a table cell or a definition clause.
"""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nizam.corpus.segment import (_classify_body, _detached_heading,
                                  _section_numbers, classify, parse_contents,
                                  segment, subdivide)

FIXTURE = Path(__file__).parent / 'fixtures' / 'rejected-openers.json'


def blocks():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def block(block_id):
    return next(b for b in blocks() if b['id'] == block_id)


def text(block_id):
    return block(block_id)['text']


# ------------------------------------------------------- (c) the bare number
#
# The Punjab Urban Immovable Property Tax Rules 1958 print rule 1 on page 3 as
#
#     1
#     (1)
#     these rules may be called the West Pakistan urban Immovable Property
#     Tax Rules, 1958.
#
# while rules 3 to 30 all carry their period.

@pytest.mark.parametrize('block_id,label', [
    (252235, '1'),      # 2803 p3  rule 1, the document whose contents this cost
    (19724, '8'),       # 510  p4  "8 / (1) / Government may by notification"
    (65428, '70-B'),    # 1244 p5  a lettered label in the same shape
    (47117, '6-D'),     # 998  p4  two spaces instead of a newline
    (923578, '337H'),   # 4501 p239
])
def test_a_bare_number_before_its_first_subsection_opens_a_section(block_id, label):
    source = block(block_id)
    original = deepcopy(source)
    found = classify(source['text'])
    assert found is not None and found[0] == 'section'
    assert found[1].replace(' ', '') == label
    # The subsection marker is part of the provision's text, not consumed by
    # the label: INV-4 needs the citable unit to hold everything printed under
    # it, and "(1)" is the first thing printed under it.
    assert found[2].lstrip().startswith('(1)')
    assert source == original          # the source block is never mutated


@pytest.mark.parametrize('block_id', [
    201887,   # 2452 p21 "3 (1) There shall be a Dean for each Faculty" --
              # paragraph 3(1) of an appended Statute, ONE space, and the form
              # measured unsafe when this rule was first tried.
    537239,   # 3974 p14 "5 / (1) / 5 / (1) / (a) / 5 / (2) / ..." -- a grid of
              # provision cross-references, not a provision.
])
def test_a_one_space_paragraph_and_a_reference_grid_stay_refused(block_id):
    assert classify(text(block_id)) is None


@pytest.mark.parametrize('probe', [
    '1 (1) This Act may be called the Sindh Act, 2013.',      # one space
    '1  (2) It shall come into force at once.',               # not the FIRST
    '1  (1) 5 (1) (a) 5 (2)',                                 # no prose after
    '1  (1)',                                                 # nothing at all
    'under rule 1  (1) of these rules the fee is payable.',   # mid-sentence
])
def test_the_bare_number_rule_refuses_its_near_neighbours(probe):
    found = classify(probe)
    assert found is None or found[0] != 'section'


def test_the_number_is_not_cut_away_from_its_first_subsection():
    # `subdivide` runs BEFORE `classify`, and it used to cut this block into
    # "1" and "(1) these rules ...". The first piece is a bare number no rule
    # accepts, so the opener was lost even though the grammar could read it.
    pieces = subdivide(text(252235))
    assert len(pieces) == 1
    assert classify(pieces[0])[:2] == ('section', '1')


def test_a_later_subsection_is_still_an_internal_cut():
    # Only subsection (1) is joined back, and only when nothing but the label
    # precedes it. A block holding a provision and then its (2) still splits.
    pieces = subdivide('4. Duties of assessing authority.- An authority shall act.\n'
                       '(2) It shall keep a register.')
    assert len(pieces) == 2
    assert classify(pieces[0])[:2] == ('section', '4')
    assert classify(pieces[1])[:2] == ('subsection', '2')


def test_a_section_ending_in_a_number_is_not_joined_to_the_next_clause():
    # The guard the file has carried since the "5.A." repair: a section ending
    # "5." followed by clause "A." must not become label "5.A".
    pieces = subdivide('The fee is payable under section 5.\nA. The Collector may act.')
    labels = [c[:2] for p in pieces for c in [classify(p)] if c]
    assert ('section', '5.A') not in labels


def test_the_contents_boundary_is_recoverable_once_rule_one_is_read():
    # The payoff, and the reason this shape mattered more than its 43 blocks.
    # `parse_contents` chooses a boundary where the leading integer FALLS, and
    # with rule 1 unreadable the numbering ran 1..25 across the contents page
    # and then resumed at 3 in the body -- it never fell, so there was no
    # candidate boundary at all and the document was recorded as printing no
    # contents. All 25 printed rows were then built as sections.
    rows = [{'id': 1, 'page_no': 1, 'y0': 90.0, 'text': 'CONTENTS \n'}]
    headings = ['Notification', 'Assessing Authority', 'Powers of subordinate officials',
                'Duties of Assessing Authority', 'Preparation of draft valuation list']
    for i, heading in enumerate(headings, start=1):
        rows.append({'id': 10 + i, 'page_no': 1, 'y0': 100.0 + 10 * i,
                     'text': f'{i}. \n{heading} \n'})
    rows.append(deepcopy(block(252235)))          # the bare-number rule 1
    for i, heading in enumerate(headings[1:], start=2):
        rows.append({'id': 100 + i, 'page_no': 3, 'y0': 200.0 + 10 * i,
                     'text': f'{i}. \n{heading}.- The authority shall act. \n'})
    toc, boundary, found = parse_contents(rows)
    assert found
    assert boundary == len(headings) + 1          # the body opens at rule 1
    assert set(toc) == {str(i) for i in range(1, len(headings) + 1)}
    result = segment(rows)
    assert result.toc_found
    # the contents rows are promises now, not twenty-five rival sections
    assert [e['label'] for e in result.toc_entries] == list(toc)
    assert result.repeated_labels_demoted == 0


# ------------------------- (t) a footnote-marker LIST before the bracket
#
# A consolidated edition footnotes a provision once per amendment and prints
# every marker it has collected. The opener stripped ONE plain digit before the
# bracket, so a list of markers, or a marker with a letter suffix, hid the
# section behind it. Document 4451 (the Customs Act, 1969) lost thirteen
# sections this way; the siblings on the same pages that DID resolve --
# 27[185A., 54[187A., 81[194B. -- differ only in carrying a single plain marker.

@pytest.mark.parametrize('block_id,label,heading_opens', [
    (813924, '19C', 'Minimal duties not to be demanded'),
    (813930, '21A', 'Power to defer collection of customs-duty'),   # 24[(21A.
    (813996, '25D', 'Review of the value determined'),
    (814307, '82', 'Procedure in case of goods not cleared'),
    (815828, '193A', 'Procedure in appeal'),
    (815840, '194', 'Appellate Tribunal'),
    (815854, '194A', 'Appeals to the Appellate Tribunal'),
    (816183, '203A', 'Power to authorize expenditure'),
])
def test_a_marker_list_before_the_bracket_does_not_hide_the_label(
        block_id, label, heading_opens):
    found = classify(text(block_id))
    assert found is not None and found[0] == 'section'
    assert found[1].replace(' ', '') == label
    assert found[2].lstrip().startswith(heading_opens)


def test_a_marker_list_mid_block_is_exposed_to_the_classifier():
    # Document 4451 prints section 3A eight lines into block 813831, after
    # clause (g) of section 3 and a blank line, so the inner splitter has to
    # find it: the block-start classifier never sees it otherwise.
    source = block(813831)
    original = deepcopy(source)
    pieces = subdivide(source['text'])
    assert ''.join(pieces).lstrip() == source['text'].lstrip()   # nothing dropped
    found = [c for p in pieces for c in [classify(p)]
             if c and c[0] == 'section' and c[1] == '3A']
    assert len(found) == 1
    assert source == original


@pytest.mark.parametrize('probe,label', [
    ('1[3. Appointment of officers of Customs.- The Board may appoint', '3'),
    ('1[ 2[67. Compensation for the death of a passenger.--(1) Where', '67'),
    ('506[33A***]. The rest follows.', '33A'),
])
def test_the_marker_shapes_that_already_worked_still_work(probe, label):
    found = classify(probe)
    assert found is not None and found[0] == 'section'
    assert found[1].replace(' ', '') == label


# A parenthesised label is the counter-example the widened prefix created:
# admitting "(" after the bracket to reach `24[(21A.` also reaches a definition
# clause whose own label is bracketed. No provision's text opens with ")".

@pytest.mark.parametrize('block_id', [
    600082,   # 4149 p14 `1[(23A.) "Service Delivery Centre" means ...`
              # -- definition clause (23A) of the definitions section
    817160,   # 4453 p9  `1[16-A.) "marketable security" means ...` -- printed
              # between definitions (d) and (17) of the Stamp Act's section 2
    56711,    # 1150 p4  `1898.)` -- the tail of a wrapped citation
])
def test_a_parenthesised_label_is_not_a_section(block_id):
    found = classify(text(block_id))
    assert found is None or found[0] not in ('section', 'article')


# ------------------------ (u) a label inside the bracket with no period
#
# `periodless` has always required the document's own contents to promise the
# label AND to predict the words that follow it. What it could not do was look
# past an amendment bracket, so three of document 4451's thirteen were refused
# before that corroboration was ever consulted.

CUSTOMS_TOC = {
    '83C': 'Cargo Tracking System and e-Bilty Mechanism',
    '193': 'Appeals to Collector (Appeals).',
    '5': 'Delegation of powers.',
}


@pytest.mark.parametrize('block_id,label', [
    (814359, '83C'),   # 10[83C  Cargo Tracking System and e-Bilty mechanism.-
    (815824, '193'),   # 2[193 Appeals to Collector (Appeals).-
])
def test_a_periodless_label_behind_a_bracket_is_read_when_the_contents_agrees(
        block_id, label):
    found = _classify_body(text(block_id), CUSTOMS_TOC, set())
    assert found is not None and found[:2] == ('section', label)


def test_a_substituted_heading_may_be_printed_inside_its_quotation():
    # Document 4451 page 35 prints section 5 as `4[5` then, on the next line,
    # `“Delegation of powers.- ...` -- the quote belongs to the amendment that
    # substituted the section, and it must not defeat the corroboration.
    printed = '4[5 \n“Delegation of powers.- 5,24(1) The Board may, by notification'
    found = _classify_body(printed, CUSTOMS_TOC, set())
    assert found is not None and found[:2] == ('section', '5')
    assert found[2].lstrip().startswith('“Delegation')   # nothing dropped


@pytest.mark.parametrize('block_id', [814359, 815824])
def test_a_periodless_label_is_refused_when_the_contents_does_not_promise_it(block_id):
    assert _classify_body(text(block_id), {}, set()) is None
    assert _classify_body(text(block_id),
                          {'83C': 'Something else entirely',
                           '193': 'A different heading altogether'},
                          set()) is None


# ----------------------------- (j) the number set in its own column
#
# The Sindh Mental Health Act, 2013 prints its contents in two columns, and the
# extractor strands four rows: the number is one block and its heading is the
# next. Both `parse_contents.score` and `_toc_source_entries` require a
# non-empty heading, so such a row was dropped from the promises AND from the
# stored evidence -- the printed row left the database and no gap recorded it.

@pytest.mark.parametrize('number_id,heading_id,heading_opens', [
    (251349, 251350, 'Admission for treatment'),
    (251366, 251367, 'Discharge of a detained person'),
    (251397, 251398, 'Informed consent for research'),
])
def test_a_number_alone_in_its_block_takes_the_next_block_s_heading(
        number_id, heading_id, heading_opens):
    rows = [block(number_id), block(heading_id)]
    assert _detached_heading(rows, 0).startswith(heading_opens)
    carried = [row for row in _section_numbers(rows) if row[3]]
    assert len(carried) == 1
    assert carried[0][2] == text(number_id).strip().rstrip('.')
    assert carried[0][3].startswith(heading_opens)


def test_a_detached_heading_is_refused_across_a_page_break():
    number, heading = block(251349), deepcopy(block(251350))
    heading['page_no'] = number['page_no'] + 1
    assert _detached_heading([number, heading], 0) == ''


def test_a_detached_heading_is_refused_when_the_next_block_opens_a_provision():
    # Block 251404 holds `55.` alone, but the block after it is CHAPTER-XI.
    # A structural heading is not this row's heading, and guessing would give
    # section 55 the name of the chapter that follows it.
    assert _detached_heading([block(251404), block(251405)], 0) == ''


# The extractor does not always emit the number before its heading --
# reader-instruction pattern (x), "check the reading order: the item is often
# extracted BEFORE the heading it belongs to". On such a page the block AFTER
# the number is the NEXT row's heading, and taking it names a live provision
# wrongly, which is worse than the gap it replaced.

def test_an_inverted_page_takes_the_heading_printed_above_the_number():
    # Sindh Local Government Act, document 4369, page 7:
    #     705072   110.   Approval of Budgets.
    #     705073   Accounts.
    #     705074   111.
    #     705075   Composition of Provincial Finance Commission.
    # "Accounts." is 111's heading; the block below it belongs to 112.
    rows = [block(i) for i in (705072, 705073, 705074, 705075)]
    assert _detached_heading(rows, 2) == 'Accounts.'


def test_the_ordinary_order_on_the_same_page_still_reads_downwards():
    #     705103   126.  Legal Adviser
    #     705104   127.
    #     705105   Training And Training Institutions
    # The block above carries its own number, so it is not this row's heading.
    rows = [block(i) for i in (705103, 705104, 705105)]
    assert _detached_heading(rows, 1) == 'Training And Training Institutions'


def test_a_stranded_run_does_not_shift_every_heading_onto_its_predecessor():
    # Two stranded rows in a row: 11's heading must not become 12's. The block
    # above 12 is 11's own heading, and the block two above is label-only,
    # which is what rules the upward borrow out.
    rows = [{'id': 1, 'page_no': 1, 'y0': 100.0, 'text': '11. \n'},
            {'id': 2, 'page_no': 1, 'y0': 110.0, 'text': 'Admission for treatment. \n'},
            {'id': 3, 'page_no': 1, 'y0': 120.0, 'text': '12. \n'},
            {'id': 4, 'page_no': 1, 'y0': 130.0, 'text': 'Admission in cases of urgency. \n'}]
    assert _detached_heading(rows, 0) == 'Admission for treatment.'
    assert _detached_heading(rows, 2) == 'Admission in cases of urgency.'


def test_a_lowercase_continuation_above_is_not_read_as_a_heading():
    # Document 2800 page 2 has the tail of the previous entry above `23.`
    # ("a patient for discharge."). It is prose, not a heading, so the row
    # still takes the heading printed below it.
    rows = [block(i) for i in (251365, 251366, 251367)]
    assert _detached_heading(rows, 1).startswith('Discharge of a detained person')


@pytest.mark.parametrize('own_text', [
    'FACILITY \n47. \n',            # 2800 p3: the label is not alone in the block
    '11. Admission for treatment. \n',   # nothing is detached here
    '11 \n',                        # no printed period: a page number looks like this
])
def test_a_detached_heading_needs_the_label_alone_in_its_own_block(own_text):
    rows = [{'id': 1, 'page_no': 1, 'y0': 100.0, 'text': own_text},
            {'id': 2, 'page_no': 1, 'y0': 110.0, 'text': 'Admission for treatment. \n'}]
    assert _detached_heading(rows, 0) == ''


def test_a_detached_heading_is_refused_when_the_next_block_is_apparatus():
    rows = [{'id': 1, 'page_no': 2, 'y0': 700.0, 'text': '9. \n'},
            {'id': 2, 'page_no': 2, 'y0': 710.0,
             'text': '1. Subs. by the Central Laws (Statute Reform) Ordinance, 1960.\n'
                     '2. The word "Province" omitted by W.P. Laws (Adaptation) Order.\n'
                     '3. Ins. ibid.\n'}]
    assert _detached_heading(rows, 0) == ''


def test_a_detached_heading_is_bounded_in_length():
    rows = [{'id': 1, 'page_no': 1, 'y0': 100.0, 'text': '11. \n'},
            {'id': 2, 'page_no': 1, 'y0': 110.0, 'text': 'A' + ' word' * 60}]
    assert _detached_heading(rows, 0) == ''


def test_a_stranded_contents_row_becomes_a_promise_and_a_heading():
    rows = [{'id': 1, 'page_no': 1, 'y0': 60.0, 'text': ' \nC O N T E N T S \n'}]
    printed = [('1', 'Short title, extent and commencement.'),
               ('2', 'Definitions.'),
               ('3', 'Sindh Mental Health Authority.'),
               ('4', 'Constitution of Board of Visitors.')]
    for ordinal, (label, heading) in enumerate(printed):
        if label == '3':                       # stranded, as page 1 strands 11.
            rows.append({'id': 20 + ordinal, 'page_no': 1, 'y0': 100.0 + ordinal,
                         'text': f'{label}. \n'})
            rows.append({'id': 40 + ordinal, 'page_no': 1, 'y0': 100.5 + ordinal,
                         'text': f'{heading} \n'})
        else:
            rows.append({'id': 20 + ordinal, 'page_no': 1, 'y0': 100.0 + ordinal,
                         'text': f'{label}. \n{heading} \n'})
    for label, heading in printed:
        rows.append({'id': 200 + int(label), 'page_no': 2, 'y0': 100.0 + int(label),
                     'text': f'{label}. {heading}- The Authority shall act. \n'})
    toc, _, found = parse_contents(rows)
    assert found
    assert toc['3'].startswith('Sindh Mental Health Authority')
    result = segment(rows)
    stored = {e['label']: e for e in result.toc_entries}
    assert '3' in stored and stored['3']['node'] is not None
    # the row keeps the exact block the number was printed in, not the heading's
    assert stored['3']['source_block_id'] == 22
