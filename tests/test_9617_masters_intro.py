from nizam.corpus import segment as S

INTRO = ('S. R. O. 763 (K)/61.—In exercise of the powers conferred by section 21 of '
         'the Merchant Shipping Act, 1923 (XXI of 1923), the Central Government is '
         'pleased to make the following rules for the conduct of examinations and '
         'grant of certificates of competency as Masters and Mates:—')

def parse(text=INTRO,bid=2573347,page=3):
    return S.segment([dict(id=bid,page_no=page,text=text,y0=170,page_height=842),
        dict(id=2573350,page_no=3,text='1. Valid Certificates.—An officer must hold a valid certificate.',y0=250,page_height=842)],
        detect_contents=False,profile='unreleased-v5',structural_overrides={'source_body_start_block':bid})

def test_exact_source_enabling_paragraph_retained():
    seg=parse()
    assert seg.root.children[0].kind=='preamble'
    assert seg.root.children[0].text==INTRO
    assert seg.root.children[1].label=='1'

def test_other_source_identity_or_words_not_admitted():
    for bid,page,text in [(2573346,3,INTRO),(2573347,4,INTRO),(2573347,3,INTRO.replace('section 21','section 22')),(2573347,3,INTRO.replace('763','764'))]:
        assert not S._is_source_preamble_intro_block(dict(id=bid,page_no=page,text=text))
        assert not any(n.kind=='preamble' for n in parse(text,bid,page).root.children)

def test_whitespace_reflow_preserves_source_words():
    assert parse(INTRO.replace(' ', '\n')).root.children[0].text==INTRO
