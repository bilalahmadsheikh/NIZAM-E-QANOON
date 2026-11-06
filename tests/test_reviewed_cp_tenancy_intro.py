"""The source-read CP Tenancy long title survives before its recital."""
from nizam.corpus import segment as S

TITLE='An Act to consolidate and amend the Law relating to Agricultural Tenancies in the Central Provinces.'
RECITAL='WHEREAS it is expedient to consolidate and amend the law relating to agricultural tenancies in the Central Provinces; It is hereby enacted as follows:—'
def block(i,p,t):return dict(id=i,page_no=p,text=t,y0=100,page_height=948)

def test_full_source_preamble_and_first_chapter_survive():
 seg=S.segment([block(2579916,6,TITLE),block(2579917,6,RECITAL),block(2579919,6,'CHAPTER I.\nPRELIMINARY.'),block(2579920,6,'1. (1) This Act may be called the Central Provinces Tenancy Act, 1898.\n(2) It extends to all the territories for the time being administered by the Chief Commissioner of the Central Provinces; and'),block(2579921,6,'(3) It shall come into force at once.')],detect_contents=False,profile='unreleased-v5',structural_overrides={'source_body_start_block':2579916})
 p=next(x for x in seg.root.children if x.kind=='preamble')
 assert p.text==TITLE+' '+RECITAL
 c=next(x for x in seg.root.children if x.kind=='chapter')
 assert c.label=='I'and c.heading=='PRELIMINARY.'and c.children[0].label=='1'
 assert [x.label for x in c.children[0].children]==['1','2','3']

def test_title_support_cannot_be_reused_for_another_source():
 for b in [block(2579915,6,TITLE),block(2579916,7,TITLE),block(2579916,6,TITLE+' Extra.')]:assert not S._is_source_preamble_intro_block(b)
 assert S._is_source_preamble_intro_block(block(2579916,6,TITLE.replace(' ','\n')))
