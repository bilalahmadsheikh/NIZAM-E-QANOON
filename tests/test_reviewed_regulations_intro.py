"""Doc5814's exact reviewed notification formula remains replayable prose."""
from nizam.corpus import segment as S

FORMULA = ('No.—In exercise of the powers conferred by Section 18 of the '
           'Khyber Pakhtunkhwa Establishment of Information Technology Board Act, '
           '2011, the Khyber Pakhtunkhwa Information Technology Board is hereby, '
           'pleased to make the following Regulations, namely:')
TITLE = ('THE KHYBER PAKHTUNKHWA INFORMATION TECHNOLOGY BOARD SERVICE '
         'REGULATIONS, 2018(as amended up to date)')

def source(text=FORMULA, bid=1403354, page=1):
    return [dict(id=bid,page_no=page,text=text,y0=100,page_height=842),
            dict(id=1403355,page_no=1,text=TITLE,y0=200,page_height=842),
            dict(id=1403358,page_no=1,text='1. Short title.—(1) These Regulations shall be called the Khyber Pakhtunkhwa Information Technology Board Service Regulations, 2018.',y0=400,page_height=842)]

def parse(blocks):
    return S.segment(blocks,detect_contents=False,profile='unreleased-v4',
                     structural_overrides={'source_body_start_block':blocks[0]['id']})

def test_exact_notification_formula_is_preserved():
    p=next(n for n in parse(source()).root.children if n.kind=='preamble')
    assert FORMULA in p.text and p.first_block==1403354

def test_notification_exception_requires_exact_id_page_and_text():
    for b in [source(bid=1403353),source(page=2),source(text=FORMULA+' Extra.')]:
        assert not S._is_source_preamble_intro_block(b[0])
        assert not any(n.kind=='preamble' for n in parse(b).root.children)

def test_reviewed_notification_whitespace_is_harmless():
    p=next(n for n in parse(source(text=FORMULA.replace(' ','\n'))).root.children if n.kind=='preamble')
    assert FORMULA in p.text
