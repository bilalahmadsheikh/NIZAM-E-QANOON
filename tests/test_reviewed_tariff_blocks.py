"""Source-bound tariff rows: scope, cell coverage, numbering and raw immutability."""
import copy,hashlib
import pytest
from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides

OWNER={'export':'.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json','document_id':9851,'question_id':'q2'}
def event(n,kind,label,parent,text,named=False,targets=None):
    return dict(ref=f'p1e{n}',kind=kind,label=label,parent_ref=parent,source_text=text,named=named,targets=targets or [])
def fixture():
    ev=[event(0,'schedule','FIRST',None,'THE FIRST SCHEDULE.\nIMPORT TARIFF.'),
        event(1,'part','SECTION I. GOODS.','p1e0','SECTION I. GOODS.'),
        event(2,'clause','8(1)','p1e1','8(1) | PRINTED GOODS— | | | | |'),
        event(3,'clause','a','p1e2','(a) | First kind | Revenue | Rs. 3 each. | .. | .. | ..'),
        event(4,'clause','b','p1e2','(b) | Second kind | Revenue | Rs. 6 each. | .. | .. | ..'),
        event(5,'shared','','p1e2','or 37½ per cent. ad valorem, whichever is higher.',targets=['p1e3','p1e4']),
        event(6,'clause','c','p1e2','(c) | Other kind | Revenue | 50 per cent. ad valorem | .. | .. | ..'),
        event(7,'clause','ACTUAL PRINTED NAME','p1e1','[illegible] | ACTUAL PRINTED NAME | Revenue | 25 per cent. ad valorem | .. | .. | ..',True)]
    text='\n'.join(e['source_text']for e in ev)
    blocks=[dict(id=1,page_no=1,text='1. The duties specified in the Schedule shall be levied.',y0=100,page_height=900),
            dict(id=2,page_no=1,text=text,y0=200,page_height=900)]
    spec=dict(source_block_id=2,text_sha256=hashlib.sha256(S._norm(text).encode()).hexdigest(),events=ev,owner_decision=OWNER)
    return blocks,spec
def parse(bs,sp):return S.segment(bs,detect_contents=False,profile='unreleased-v5',structural_overrides={'source_reviewed_table_blocks':[sp]})
def test_compound_rows_named_gaps_shared_cell_scope_and_immutable_raw():
    bs,sp=fixture();before=copy.deepcopy(bs);seg=parse(bs,sp)
    schedule=next(n for n in seg.root.children if n.kind=='schedule')
    group=schedule.children[0];row=group.children[0]
    assert group.group_caption and row.label=='8(1)'
    a,b,c=row.children
    assert a.text.endswith('or 37½ per cent. ad valorem, whichever is higher.')
    assert b.text.endswith('or 37½ per cent. ad valorem, whichever is higher.')
    assert '37½'not in c.text and '50 per cent.'in c.text
    named=group.children[1];assert named.named_row and named.label=='ACTUAL PRINTED NAME'and '[illegible]'in named.text
    assert [n.label for n in seg.root.children if n.kind=='section']==['1']
    assert bs==before
    assert len(S.assign_paths(seg,'test'))==len(set(p for _,p in S.assign_paths(seg,'test')))

@pytest.mark.parametrize('mutation',['hash','coverage','serial','parent','duplicate','shared_parent','foreign_block','named_rate_word','caption_fragment','false_schedule_label'])
def test_incomplete_or_wrong_source_plan_refused(mutation):
    bs,sp=fixture()
    if mutation=='hash':sp['text_sha256']='0'*64
    if mutation=='coverage':sp['events'][3]['source_text']+=' Invented rate.'
    if mutation=='serial':sp['events'][2]['label']='8(2)'
    if mutation=='parent':sp['events'][3]['parent_ref']='p1e99'
    if mutation=='duplicate':sp['events'][4]['label']='a'
    if mutation=='shared_parent':sp['events'][5]['parent_ref']='p1e1'
    if mutation=='foreign_block':sp['source_block_id']=987654
    if mutation=='named_rate_word':sp['events'][7]['label']='Revenue'
    if mutation=='caption_fragment':sp['events'][1]['label']='GOODS'
    if mutation=='false_schedule_label':sp['events'][0]['label']='IMPORT'
    with pytest.raises(ValueError):parse(bs,sp)

def test_merged_conflicting_table_spec_refused():
    _,sp=fixture();changed=copy.deepcopy(sp);changed['text_sha256']='0'*64
    def p(x):return dict(evidence=dict(structural_overrides={'source_reviewed_table_blocks':[x]}))
    with pytest.raises(ValueError):reviewed_structural_overrides([], [p(sp),p(changed)])

def test_tariff_clipped_long_title_requires_exact_identity_and_text():
    title='[illegible] Act to consolidate the law relating to customs duties.'
    b=dict(id=2673045,page_no=1,text=title,y0=100,page_height=900)
    assert S._is_source_preamble_intro_block(b)
    for key,val in [('id',2673044),('page_no',2),('text',title.replace('[illegible]','An'))]:
        other=dict(b);other[key]=val;assert not S._is_source_preamble_intro_block(other)
    seg=S.segment([b,dict(id=2673046,page_no=1,text='WHEREAS it is expedient to consolidate the law; It is hereby enacted as follows:—',y0=120,page_height=900),dict(id=2673047,page_no=1,text='1. This Act may be called the Indian Tariff Act, 1934.',y0=150,page_height=900)],detect_contents=False,profile='unreleased-v5',structural_overrides={'source_body_start_block':2673045})
    pre=next(n for n in seg.root.children if n.kind=='preamble');assert pre.text.startswith(title+' WHEREAS')


def test_shipping_long_title_requires_exact_identity_and_text():
    title='An Act to consolidate certain enactments relating to Merchant Shipping.'
    b=dict(id=2472596,page_no=7,text=title,y0=100,page_height=900)
    assert S._is_source_preamble_intro_block(b)
    for key,val in [('id',2472595),('page_no',6),('text',title.replace('certain ',''))]:
        other=dict(b);other[key]=val;assert not S._is_source_preamble_intro_block(other)
    seg=S.segment([b,dict(id=2472597,page_no=7,text='WHEREAS it is expedient to consolidate certain enactments relating to merchant Shipping; It is hereby enacted as follows:—',y0=120,page_height=900),dict(id=2472599,page_no=7,text='1. (1) This Act may be called the Indian Merchant Shipping Act, 1923.',y0=150,page_height=900)],detect_contents=False,profile='unreleased-v5',structural_overrides={'source_body_start_block':2472596})
    pre=next(n for n in seg.root.children if n.kind=='preamble');assert pre.text.startswith(title+' WHEREAS')


def shipping_schedule_fixture(caption='SCHEDULE V.',label='V'):
    ev=[event(0,'schedule',label,None,caption+'\n(See section 296.)\nENACTMENTS REPEALED.'),
        event(1,'clause','The Devolution Act, 1920.','p1e0','1920 | XXXVIII | The Devolution Act, 1920. | So much of the First Schedule as relates to the Indian Merchant Shipping Act, 1880.',True)]
    text='\n'.join(e['source_text']for e in ev)
    blocks=[dict(id=1,page_no=55,text=text,y0=100,page_height=900)]
    spec=dict(source_block_id=1,text_sha256=hashlib.sha256(S._norm(text).encode()).hexdigest(),events=ev,owner_decision=OWNER)
    return blocks,spec


def test_reviewed_schedule_caption_after_keyword_preserves_repeal_row():
    bs,sp=shipping_schedule_fixture();before=copy.deepcopy(bs);seg=parse(bs,sp)
    schedule=next(n for n in seg.root.children if n.kind=='schedule')
    assert schedule.label=='V' and schedule.heading.startswith('SCHEDULE V.')
    assert schedule.children[0].named_row and schedule.children[0].label=='The Devolution Act, 1920.'
    assert schedule.children[0].text==sp['events'][1]['source_text']
    assert bs==before


@pytest.mark.parametrize('caption,label',[
    ('SCHEDULE IV.','V'),('THE SCHEDULE V.','V'),('INTRODUCTION SCHEDULE V.','V'),
    ('SCHEDULE VI.','V'),('SCHEDULE V','V'),('SCHEDULE V.','IV'),
])
def test_reviewed_schedule_caption_wrong_label_or_prefix_refused(caption,label):
    with pytest.raises(ValueError,match='caption is not printed'):
        parse(*shipping_schedule_fixture(caption,label))
