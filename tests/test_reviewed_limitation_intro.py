"""Doc9765's reviewed long title survives before WHEREAS and Part I."""
from nizam.corpus import segment as S

TITLE = 'An Act for the Limitation of Suits, and for other purposes.'
RECITAL = ('WHEREAS it is expedient to amend the law relating to the limitation '
           'of suits, appeals and certain applications to Courts; And whereas '
           'it is also expedient to provide rules for acquiring by possession '
           'the ownership of easements and other property; It is hereby enacted as follows:—')

def source(title=TITLE, bid=2645990, page=3):
    return [dict(id=bid,page_no=page,text=title,y0=100,page_height=948),
            dict(id=2645991,page_no=page,text=RECITAL,y0=160,page_height=948),
            dict(id=2645993,page_no=page,text='PART I.\nPRELIMINARY.',y0=240,page_height=948),
            dict(id=2645994,page_no=page,text='1. This Act may be called “The Indian Limitation Act, 1877:”',y0=300,page_height=948)]

def parse(blocks):
    return S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                     structural_overrides={'source_body_start_block':blocks[0]['id']})

def test_exact_limitation_title_is_preserved_before_recital_and_part():
    seg=parse(source());p=next(n for n in seg.root.children if n.kind=='preamble')
    assert p.text==TITLE+' '+RECITAL and p.first_block==2645990
    part=next(n for n in seg.root.children if n.kind=='part')
    assert part.label=='I' and part.heading=='PRELIMINARY.'
    assert part.children[0].kind=='section' and part.children[0].label=='1'

def test_limitation_intro_requires_exact_block_page_and_reading():
    for b in [source(bid=2645989),source(page=4),source(title=TITLE+' Extra.')]:
        assert not S._is_source_preamble_intro_block(b[0])
        assert TITLE not in next(n for n in parse(b).root.children if n.kind=='preamble').text

def test_limitation_intro_whitespace_variation_preserves_source_words():
    p=next(n for n in parse(source(title=TITLE.replace(' ','\n'))).root.children if n.kind=='preamble')
    assert p.text==TITLE+' '+RECITAL
