"""The actual doc9615 long title must survive before its separate recital."""
from nizam.corpus import segment as S

TITLE = ('AN ORDER to provide for the constitution of basic democratic '
         'institutions throughout Pakistan, and to consolidate and amend '
         'certain laws relating to local government.')
RECITAL = ('WHEREAS it is expedient to provide for the constitution of basic '
           'democratic institutions throughout Pakistan, and to consolidate '
           'and amend certain laws relating to local government;')

def source(title=TITLE, bid=2571378, page=5):
    return [dict(id=bid, page_no=page, text=title, y0=100, page_height=936),
            dict(id=2571383, page_no=page, text=RECITAL, y0=220, page_height=936),
            dict(id=2571386, page_no=page, text='1. Short title, extent and commencement.—(1) This Order may be called the Basic Democracies Order, 1959.', y0=400, page_height=936)]

def parse(blocks):
    return S.segment(blocks, detect_contents=False, profile='unreleased-v4',
                     structural_overrides={'source_body_start_block': blocks[0]['id']})

def test_exact_reviewed_order_intro_precedes_recital_in_preamble():
    seg=parse(source());p=next(n for n in seg.root.children if n.kind=='preamble')
    assert p.text == TITLE+' '+RECITAL
    assert p.first_block==2571378 and p.first_page==5
    assert len([n for n in seg.root.children if n.kind=='preamble'])==1

def test_source_intro_requires_exact_id_page_and_text():
    for blocks in [source(bid=2571379),source(page=6),source(title=TITLE+' Extra.')]:
        assert not S._is_source_preamble_intro_block(blocks[0])
        p=next(n for n in parse(blocks).root.children if n.kind=='preamble')
        assert TITLE not in p.text

def test_reviewed_intro_allows_whitespace_only_changes():
    seg=parse(source(title=TITLE.replace(' ', '\n')))
    p=next(n for n in seg.root.children if n.kind=='preamble')
    assert p.text==TITLE+' '+RECITAL
