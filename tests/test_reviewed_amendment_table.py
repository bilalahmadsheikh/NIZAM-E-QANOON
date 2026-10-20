"""4089's official 45-page source, reviewed 19/20 Oct 2026.

The fixture preserves all 530 immutable blocks. Expected structures come from
source-image review, not an old parser tree. Quoted inserted provisions are
kept as text of the amending instruction, never as current-Act provisions.
"""
import copy
import json
import pathlib

import pytest

from nizam.corpus.segment import _reviewed_unit_moves, assign_paths, segment
from nizam.workers.segment import reviewed_structural_overrides
from tools.record_curation_patch import owner_cited_block_problem

FIXTURE=json.loads((pathlib.Path(__file__).parent/'fixtures/doc4089-source-reviewed.json').read_text())


def source_parse(readings=None):
    readings=FIXTURE['readings'] if readings is None else readings
    patches=[dict(id=f'fixture-{i}',page_no=r['page_no'],match_text=r['match_text'],
                  before_text=r['before_text'],after_text=r['after_text'],
                  evidence={'structural_overrides':{k:v for k,v in r.items() if k.startswith('source_')}})
             for i,r in enumerate(readings)]
    return segment(FIXTURE['blocks'],profile='unreleased-v4',curation_patches=patches,
                   structural_overrides=reviewed_structural_overrides([],patches))


@pytest.fixture(scope='module')
def parsed():return source_parse()


def test_actual_4089_all_rows_amendments_and_children_have_source_parents(parsed):
    nodes=parsed.flatten()
    sched=next(n for n in nodes if n.kind=='schedule')
    rows=sched.children
    assert [n.label for n in rows]==[str(i) for i in range(1,31)]
    assert all(n.kind=='clause' for n in rows)
    assert len(nodes)==214
    for expected,row in zip(FIXTURE['expected_rows'],rows,strict=True):
        assert row.first_block==expected['row_block']
        assert row.text==expected['title']
        assert [n.label for n in row.children]==[a['label'] for a in expected['amendments']]
        assert all(n.kind=='subsection' for n in row.children)
        for a,expected_a,child_labels in zip(row.children,expected['amendments'],expected['children'],strict=True):
            assert a.first_block==expected_a['source_block_id']
            assert [c.label for c in a.children]==child_labels
            assert all(c.kind=='clause' and not c.children for c in a.children)
            assert 'In ' in a.text and f"section {expected_a['section']}" in a.text


def test_actual_4089_top_sections_preserve_printed_and_cited_identity(parsed):
    got={p:n for n,p in assign_paths(parsed,'sindh.act.y2025_V_o4499')}
    one=got['sindh.act.y2025_V_o4499.s_1__pi']
    two=got['sindh.act.y2025_V_o4499.s_2__pii']
    assert one.first_block==579203 and two.first_block==579207
    assert [c.label for c in one.children]==['1','2']
    assert 'come into force at once' in one.children[1].text
    assert 'column 2 of the schedule' in two.text
    assert [e['node'].label for e in parsed.toc_entries[2:]]==[str(i) for i in range(1,31)]
    assert not parsed.missing and not parsed.structural_reviews_refused
    assert not parsed.repeated_label_decisions


def test_actual_4089_source_exceptions_not_normalized(parsed):
    sched=next(n for n in parsed.flatten() if n.kind=='schedule')
    row=lambda i:sched.children[i-1]
    assert row(7).children[0].label=='3'  # actual print, not guessed amendment1
    assert [c.label for c in row(20).children[0].children]==['i','c']
    assert [c.label for c in row(28).children[1].children]==['a','ii']
    assert '“(oo)' in row(4).children[0].children[1].text
    assert 'Pakistan Engineering Council (PEC)' in row(3).children[1].children[0].text
    assert '(e)' in row(18).children[1].children[0].text
    assert '“(2)' in row(23).children[1].children[1].text
    last=row(30).children[1].children[0]
    assert last.first_page==44 and last.last_page==45 and 579701 in last.blocks
    assert 'Medical Professional' in last.text and '(d)' in last.text
    # The malformed row2 quotation introduction must not promote quoted (1).
    assert '“(1)' in row(2).children[1].children[0].text
    assert '(d)' in row(2).children[1].children[0].text


def test_actual_4089_raw_evidence_and_every_block_preserved(parsed):
    original=copy.deepcopy(FIXTURE['blocks'])
    assert len(parsed.block_roles)==530
    assert not any(role=='unassigned' for role,node in parsed.block_roles.values())
    assert FIXTURE['blocks']==original
    assert not any('THE SINDH UNIVERSITIES AND INSTITUTES LAWS' in n.text for n in parsed.flatten())
    # Both portions of this physical block retain provenance on different rows.
    row_nodes=[n for n in parsed.flatten() if 579252 in n.blocks]
    assert any(n.label=='ii' and 'resign' in n.text for n in row_nodes)
    assert any(n.label=='3' and 'N.E.D.' in n.text for n in row_nodes)


def test_reviewed_cell_moves_are_identity_preserving_and_inert_without_data():
    a=({'id':1,'page_no':1},'Amendment first cell')
    b=({'id':2,'page_no':1},'The printed law title')
    c=({'id':3,'page_no':1},'Instruction next cell')
    spec=dict(source_block_id=1,source_prefix=a[1],before_block_id=3,before_prefix=c[1])
    assert _reviewed_unit_moves([a,b,c],[])==[a,b,c]
    got=_reviewed_unit_moves([a,b,c],[spec])
    assert got==[b,a,c] and got[1] is a and got[1][0] is a[0]
    for changed in [dict(spec,source_prefix='Missing source print'),dict(spec,before_block_id=1,before_prefix=a[1])]:
        with pytest.raises(ValueError):_reviewed_unit_moves([a,b,c],[changed])
    with pytest.raises(ValueError):_reviewed_unit_moves([a,a,b,c],[spec])
    with pytest.raises(ValueError):_reviewed_unit_moves([a,b,c],[spec,spec])
    cross=({'id':3,'page_no':2},c[1])
    with pytest.raises(ValueError):_reviewed_unit_moves([a,b,cross],[spec])


def test_reviewed_cell_move_rejects_malformed_or_foreign_key_shape():
    with pytest.raises(ValueError):reviewed_structural_overrides([],[{'evidence':{'structural_overrides':{'source_unit_moves':[{'source_block_id':1}]}}}])


def test_mapped_schedule_rows_fail_closed_when_target_is_not_present():
    readings=copy.deepcopy(FIXTURE['readings'])
    readings[0]['source_contents_schedule_rows']['row_labels']['2']='999'
    with pytest.raises(ValueError,match='names 0 schedule entries'):source_parse(readings)
    readings[0]['source_contents_schedule_rows']['row_labels']['2']='2'
    with pytest.raises(ValueError):source_parse(readings)


def test_roman_owner_citation_requires_exact_source_start():
    entry=dict(kind='section',printed_label='ii',source_block_id=2)
    assert owner_cited_block_problem(entry,{2:'(ii) The laws specified in column2'}) is None
    assert owner_cited_block_problem(entry,{2:'Reference to (ii) is not an opener'}) is not None


def test_ordinary_roman_items_are_not_promoted_without_exact_owner_data():
    texts=['1. Powers. The Authority may do the following:-',
           '(i) inspect the premises;', '(ii) require production of records.']
    blocks=[dict(id=i,text=t,page_no=1,y0=100+i*60,page_height=842,x0=72,x1=500)
            for i,t in enumerate(texts,1)]
    parsed=segment(blocks,profile='unreleased-v4')
    root_sections=[n for n in parsed.flatten() if n.kind=='section']
    assert len(root_sections)==1 and root_sections[0].label=='1'
    assert [n.label for n in root_sections[0].children]==['i','ii']
    assert all(n.kind=='clause' for n in root_sections[0].children)
