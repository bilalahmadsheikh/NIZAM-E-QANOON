"""Exact source-bound Oudh title and Chapter IV caption support."""
import pytest
from nizam.corpus import segment as S

TITLE='An Act to consolidate and amend the Law relating to Rent in Oudh.'
RECITAL='WHEREAS it is expedient to consolidate and amend the law relating to rent in Oudh and to other matters connected therewith; It is hereby enacted as follows:—'

def block(i,p,text):return dict(id=i,page_no=p,text=text,y0=100,page_height=948)

def test_oudh_intro_preserves_long_title_and_chapter():
    seg=S.segment([block(1854328,7,TITLE),block(1854330,7,RECITAL),block(1854333,7,'CHAPTER I.\nPRELIMINARY.'),block(1854334,7,'1. This Act may be cited as “The Oudh Rent Act,” and shall extend only to Oudh.')],detect_contents=False,profile='unreleased-v5',structural_overrides={'source_body_start_block':1854328})
    p=next(x for x in seg.root.children if x.kind=='preamble')
    assert p.text==TITLE+' '+RECITAL
    c=next(x for x in seg.root.children if x.kind=='chapter')
    assert c.label=='I' and c.heading=='PRELIMINARY.' and c.children[0].label=='1'

def test_oudh_intro_requires_exact_source_identity_and_text():
    for b in [block(1854327,7,TITLE),block(1854328,8,TITLE),block(1854328,7,TITLE+' Extra.')]:
        assert not S._is_source_preamble_intro_block(b)
    assert S._is_source_preamble_intro_block(block(1854328,7,TITLE.replace(' ','\n')))

def source_parts():
    return [block(1854613,18,'CHAPTER IV.\nENHANCEMENT AND FIXING RATES OF RENT.'),block(1854614,18,'A.—Tenants with Right of Occupancy.'),block(1854615,18,'32. No tenant having a right of occupancy shall be liable to enhancement.'),block(1854644,19,'B.—Tenants not having Right of Occupancy.'),block(1854645,19,'35. The Court shall in no case enquire into the propriety of the rate.')]

def parse_parts(bs):
    return S.segment(bs,detect_contents=False,profile='unreleased-v5',structural_overrides={'source_body_start_block':1854613,'source_lettered_part_blocks':[1854614,1854644],'source_chapter_over_part':True})

def test_oudh_lettered_groups_belong_to_chapter_and_own_sections():
    seg=parse_parts(source_parts());chapter=next(x for x in seg.root.children if x.kind=='chapter')
    assert [(x.label,x.heading,[c.label for c in x.children])for x in chapter.children]==[('A','Tenants with Right of Occupancy.',['32']),('B','Tenants not having Right of Occupancy.',['35'])]

@pytest.mark.parametrize('mutation',['block','page','text'])
def test_oudh_group_wrong_source_fails_closed(mutation):
    bs=source_parts()
    if mutation=='block':bs[1]['id']=1854612
    if mutation=='page':bs[1]['page_no']=19
    if mutation=='text':bs[1]['text']+=' Extra.'
    with pytest.raises(ValueError):parse_parts(bs)
