"""A source-bound common form tail can escape one OCR block's last subpart."""
import copy

import pytest

from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides
from tools import record_curation_patch as recorder

PREFIX='I/We hereby declare that the above statements'
TAIL=PREFIX+' and attached documents are true and correct.'


def fixture():
    def b(i,text):return dict(id=i,page_no=1,text=text,y0=100+i*10,page_height=900)
    blocks=[b(1,'1. The application is in the Annex.'),b(2,'ANNEX 3\nApplication form'),
            b(3,'PART FOUR\n4.1 Land requirement\n4.10 Wastes and their disposals\n'+TAIL),
            b(4,'I/We fully understand that admission is liable to cancellation.')]
    outer=dict(source_division_openers=[dict(source_block_id=2,kind='annexure',label='ANNEX 3')],
               source_printed_rule_openers=[dict(source_block_id=3,kind='part',label='IV',
                                                source_prefix='PART FOUR\n')])
    # The explicit part opener uses a literal Roman caption in this fixture;
    # source-specific group captions in7968 behave identically as containers.
    blocks[2]['text']=blocks[2]['text'].replace('PART FOUR','PART IV')
    outer['source_printed_rule_openers'][0]['source_prefix']='PART IV\n4.1'
    entries=[dict(source_block_id=3,parent_block_id=2,source_prefix=PREFIX),
             dict(source_block_id=4,parent_block_id=2)]
    return blocks,outer,entries


def parse(blocks,outer,entries):
    return S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                     structural_overrides=dict(outer,source_continuation_parent_blocks=entries))


def test_prefix_tail_and_next_legacy_block_belong_to_whole_application():
    blocks,outer,entries=fixture();before=copy.deepcopy(blocks)
    seg=parse(blocks,outer,entries)
    annex=next(n for n in seg.flatten()if n.kind=='annexure')
    part=next(n for n in seg.flatten()if n.kind=='part')
    assert TAIL in annex.text and 'I/We fully understand' in annex.text
    part_content=(part.heading or'')+' '+part.text
    assert TAIL not in part_content and 'Land requirement' in part_content
    assert sum(TAIL in(n.text or'')for n in seg.flatten())==1
    assert blocks==before


def test_no_prefix_entry_keeps_previous_container_behavior():
    blocks,outer,_=fixture();seg=S.segment(blocks,detect_contents=False,profile='unreleased-v5',structural_overrides=outer)
    part=next(n for n in seg.flatten()if n.kind=='part')
    assert TAIL in (part.heading or'')+' '+part.text


@pytest.mark.parametrize('change',['missing','duplicate','foreign','classified','closed_parent','self_parent','short','extra_key'])
def test_prefix_continuation_fails_closed(change):
    blocks,outer,entries=fixture()
    if change=='missing':entries[0]['source_prefix']='No such source prefix appears'
    if change=='duplicate':blocks[2]['text']+='\n'+TAIL
    if change=='foreign':entries[0]['source_block_id']=99
    if change=='classified':
        entries[0]['source_prefix']='5. A new numbered rule'
        blocks[2]['text']=blocks[2]['text'].replace(TAIL,'5. A new numbered rule is not an unnumbered declaration.')
    if change=='closed_parent':entries[0]['parent_block_id']=4
    if change=='self_parent':entries[0]['parent_block_id']=3
    if change=='short':entries[0]['source_prefix']='I/We'
    if change=='extra_key':entries[0]['unexpected']=True
    with pytest.raises(ValueError):parse(blocks,outer,entries)


def test_worker_and_recorder_share_exact_continuation_shape():
    _,_,entries=fixture()
    assert recorder.continuation_parent_shape_ok is S.continuation_parent_shape_ok
    patch=lambda es:dict(evidence=dict(structural_overrides={'source_continuation_parent_blocks':es}))
    assert reviewed_structural_overrides([],[patch(entries)])['source_continuation_parent_blocks']==entries
    changed=copy.deepcopy(entries);changed[0]['source_prefix']='Different source declaration'
    with pytest.raises(ValueError,match='conflicting'):
        reviewed_structural_overrides([],[patch(entries),patch(changed)])
    for item in [dict(entries[0],source_prefix='tiny'),dict(entries[0],parent_block_id=3),
                 dict(entries[0],source_prefix=None),dict(entries[0],unexpected=True)]:
        assert not S.continuation_parent_shape_ok(item)
        with pytest.raises(ValueError):reviewed_structural_overrides([],[patch([item])])


def same_block_fixture():
    blocks=[dict(id=10,page_no=1,text='8. The applicant shall file the form.',y0=100,page_height=900),
            dict(id=11,page_no=1,text='(1) Information required.\n(a) First alternative.\n'+TAIL,y0=150,page_height=900)]
    entry=dict(source_block_id=11,parent_block_id=11,source_prefix=PREFIX,
               parent_kind='subsection',parent_label='1')
    return blocks,entry


def test_exact_parent_selector_disambiguates_ancestor_and_child_in_same_block():
    blocks,entry=same_block_fixture();before=copy.deepcopy(blocks)
    seg=S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                  structural_overrides={'source_continuation_parent_blocks':[entry]})
    sub=next(n for n in seg.flatten()if n.kind=='subsection')
    clause=next(n for n in seg.flatten()if n.kind=='clause')
    assert TAIL in sub.text and TAIL not in clause.text and blocks==before


@pytest.mark.parametrize('change',[
    dict(parent_label='2'),dict(parent_kind='section'),dict(parent_kind='item'),
    dict(parent_label=''),dict(parent_kind=None),
])
def test_parent_selector_fails_closed_when_no_exact_open_ancestor(change):
    blocks,entry=same_block_fixture();entry.update(change)
    with pytest.raises(ValueError):
        S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                  structural_overrides={'source_continuation_parent_blocks':[entry]})


def test_selector_pair_requires_prefix_and_both_selector_fields():
    _,entry=same_block_fixture()
    for missing in ['source_prefix','parent_kind','parent_label']:
        bad=dict(entry);del bad[missing]
        assert not S.continuation_parent_shape_ok(bad)


def test_prefix_without_selector_rejects_ambiguous_shared_block_ancestors():
    blocks,outer,entries=fixture()
    # A subsection and its clause share first_block12; both are open when
    # a separate source block13 prints the common unnumbered tail.
    blocks=[dict(id=10,page_no=1,text='8. Form rule.',y0=100,page_height=900),
            dict(id=12,page_no=1,text='(1) Information.\n(a) First alternative.',y0=150,page_height=900),
            dict(id=13,page_no=1,text=TAIL,y0=200,page_height=900)]
    with pytest.raises(ValueError,match='requires one open parent'):
        S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                  structural_overrides={'source_continuation_parent_blocks':[
                      dict(source_block_id=13,parent_block_id=12,source_prefix=PREFIX)]})
