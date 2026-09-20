"""Amendment brackets must not erase source-printed schedule identity.

Doc 02 section 5.1, doc 03 section 2A. Never create containers from prose
references or loosen the existing punctuation/continuation guards.
"""
from copy import deepcopy
import json
from pathlib import Path

from nizam.corpus.segment import _consecutive_roman_parts, classify, segment


def test_numbered_amendment_markers_preserve_printed_schedule_labels():
    for text,label in [('1[FOURTH SCHEDULE','FOURTH SCHEDULE'),
                       ('1[FIFTH SCHEDULE [See section 234]','FIFTH SCHEDULE'),
                       ('192[THE SCHEDULE IV','THE SCHEDULE IV'),
                       ('1[ 2[SECOND SCHEDULE','SECOND SCHEDULE'),
                       ('1[FIRST S C H E D U L E','FIRST S C H E D U L E')]:
        kind,actual,_ = classify(text)
        assert kind=='schedule' and actual==label


def test_prose_and_historical_notes_do_not_open_amended_schedules():
    for text in ['1. The Fourth Schedule was substituted by Act 2017.',
                 'The requirements in 1[FOURTH SCHEDULE] apply.',
                 '1[FOURTH SCHEDULE to this Act, for which the following rules apply.']:
        result=segment([dict(id=1,page_no=1,text=text,y0=100)])
        assert not any(n.kind=='schedule' for n in result.flatten())


def test_prefixed_reference_continuing_a_sentence_does_not_latch_a_container():
    blocks=[dict(id=1,page_no=1,text='1. A company shall make the return in',y0=100),
            dict(id=2,page_no=1,text='1[FOURTH SCHEDULE], which applies to listed companies.',y0=120),
            dict(id=3,page_no=1,text='2. An officer shall deliver the return.',y0=150)]
    result=segment(blocks)
    assert not any(n.kind=='schedule' for n in result.flatten())
    assert len([n for n in result.flatten() if n.kind=='section'])==2
    assert set(result.block_roles)=={1,2,3}


def test_distinct_amended_schedules_own_their_parts_not_the_preceding_form():
    blocks=[dict(id=1,page_no=1,text='FORM A. STATEMENT',y0=100),
            dict(id=2,page_no=1,text='This statement is complete.',y0=130),
            dict(id=3,page_no=2,text='1[FOURTH SCHEDULE',y0=40),
            dict(id=4,page_no=2,text='PART I—GENERAL',y0=100),
            dict(id=5,page_no=2,text='1. A listed company shall disclose its accounts.',y0=140),
            dict(id=6,page_no=3,text='1[FIFTH SCHEDULE [See section 234]',y0=40),
            dict(id=7,page_no=3,text='PART I—GENERAL',y0=100),
            dict(id=8,page_no=3,text='1. An unlisted company shall disclose its accounts.',y0=140)]
    result=segment(blocks)
    parts=[n for n in result.flatten() if n.kind=='part']
    assert [n.parent.kind for n in parts]==['schedule','schedule']
    assert [n.parent.label for n in parts]==['FOURTH SCHEDULE','FIFTH SCHEDULE']
    assert all(n.parent.parent is result.root for n in parts)
    assert set(result.block_roles)=={b['id'] for b in blocks}


def test_actual_companies_fourth_and_fifth_schedules_keep_distinct_part_scopes():
    blocks=json.loads((Path(__file__).parent/'fixtures'/'amended-schedules-4495.json').read_text())
    original=deepcopy(blocks)
    result=segment(blocks)
    schedules=[n for n in result.flatten() if n.kind=='schedule']
    assert [(n.label,n.first_block,n.first_page) for n in schedules]==[
        ('FOURTH SCHEDULE',884056,350),('FIFTH SCHEDULE',884231,359)]
    parts=[n for n in result.flatten() if n.kind=='part']
    assert len(parts)==2
    assert [n.parent for n in parts]==schedules
    assert all(n.parent.parent is result.root for n in parts)
    assert set(result.block_roles)=={b['id'] for b in blocks}
    assert blocks==original


def test_descriptive_statement_forms_do_not_steal_schedule_part_identity():
    blocks=[dict(id=1,page_no=1,text='SECOND SCHEDULE',y0=40),
            dict(id=2,page_no=1,text='PART II. FORM OF STATEMENT for a public company.',y0=100),
            dict(id=3,page_no=1,text='FORM OF STATEMENT AND PARTICULARS.',y0=150),
            dict(id=4,page_no=1,text='1. Name of the company __________________.',y0=200),
            dict(id=5,page_no=2,text='PART III. FORM OF STATEMENT for a private company.',y0=100),
            dict(id=6,page_no=2,text='FORM OF STATEMENT AND THE PARTICULARS.',y0=150),
            dict(id=7,page_no=2,text='1. Name of the company __________________.',y0=200)]
    result=segment(blocks)
    schedule=next(n for n in result.flatten() if n.kind=='schedule')
    parts=[n for n in result.flatten() if n.kind=='part']
    forms=[n for n in result.flatten() if n.kind=='form']
    assert [n.parent for n in parts]==[schedule,schedule]
    assert [n.parent for n in forms]==parts
    assert all(form.children and form.children[0].label=='1' for form in forms)
    assert set(result.block_roles)=={b['id'] for b in blocks}


def test_named_forms_keep_their_own_part_scope_and_statement_forms_need_a_schedule():
    for source in [
        ['FORM OF STATEMENT AND PARTICULARS.','PART I. GENERAL'],
        ['SECOND SCHEDULE','FORM A. RETURN','PART I. GENERAL'],
    ]:
        result=segment([dict(id=n,page_no=1,text=t,y0=80+n*40) for n,t in enumerate(source)])
        part=next(n for n in result.flatten() if n.kind=='part')
        assert part.parent.kind=='form'


def test_statement_form_internal_part_restart_stays_in_the_form():
    result=segment([dict(id=n,page_no=1,text=t,y0=60+n*40) for n,t in enumerate([
        'SECOND SCHEDULE','PART II. FORM OF STATEMENT for a public company.',
        'FORM OF STATEMENT AND PARTICULARS.','PART I. INTERNAL DETAILS',
        '1. Name of the applicant __________________.'
    ])])
    parts=[n for n in result.flatten() if n.kind=='part']
    assert parts[0].parent.kind=='schedule'
    assert parts[1].parent.kind=='form' and parts[1].parent.parent is parts[0]


def test_statement_heading_alone_does_not_assert_a_schedule_part_scope():
    result=segment([dict(id=n,page_no=1,text=t,y0=60+n*40) for n,t in enumerate([
        'SECOND SCHEDULE','PART II. REPORTS',
        'FORM OF STATEMENT AND PARTICULARS.','PART III. DETAILS'
    ])])
    form=next(n for n in result.flatten() if n.kind=='form')
    assert form.parent.kind!='part'
    assert not _consecutive_roman_parts('IIII','V')
    assert not _consecutive_roman_parts('2','3')
    assert _consecutive_roman_parts('II','III')
    assert _consecutive_roman_parts('IX','X')


def test_actual_second_schedule_parts_and_statement_forms_keep_the_printed_hierarchy():
    blocks=json.loads((Path(__file__).parent/'fixtures'/'schedule-statement-4495.json').read_text())
    original=deepcopy(blocks)
    result=segment(blocks)
    schedule=next(n for n in result.flatten() if n.kind=='schedule' and n.first_block==883652)
    parts=[n for n in result.flatten() if n.kind=='part']
    assert [(n.label,n.first_block) for n in parts]==[('I',883653),('II',883822),('III',883924)]
    assert all(n.parent is schedule for n in parts)
    forms=[n for n in result.flatten() if n.kind=='form']
    assert [(n.first_block,n.parent.first_block) for n in forms]==[(883825,883822),(883927,883924)]
    assert set(result.block_roles)=={b['id'] for b in blocks}
    assert blocks==original
