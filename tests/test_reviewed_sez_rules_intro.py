"""Doc7968's exact enabling formula is retained before Chapter I."""
import hashlib

from nizam.corpus import segment as S

FORMULA=('In exercise of powers conferred by Section 40 of the Special Economic Zones Act, 2012 the '
         'Board of Investment, in consultation with Special Economic Zones Authorities and with the '
         'Approval of Board of Approvals, hereby makes the following Rules:-')
DIGEST='e40c7fb143b2ec9bf4e6c1138fbaf7e93ffc90382d89fad906f97b5c27151b0e'


def block(i,text,page=5):
    return dict(id=i,page_no=page,text=text,y0=100,page_height=842)


def source(text=FORMULA,bid=1989746,page=5):
    return [block(bid,text,page),
            block(1989747,'CHAPTER I - PRELIMINARY'),
            block(1989748,'1. Short Title and Commencement'),
            block(1989749,'1. These Rules may be called the Special Economic Zones Rules, 2013.'),
            block(1989750,'2. They shall come into force at once.'),
            block(1989751,'2. Definitions'),
            block(1989752,'1. In these rules, unless there is anything repugnant to the subject or context:')]


def parse(blocks):
    # The printed inner 1./2. are reviewed subsection openers, not top-level
    # rule numbers. They are source-shaped fixture structure, independent
    # of the preamble change under test.
    openers=[dict(source_block_id=b,kind='subsection',label=l,source_prefix=t)
             for b,l,t in [(1989749,'1','1. These Rules'),(1989750,'2','2. They shall'),
                           (1989752,'1','1. In these rules')]]
    return S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                     structural_overrides=dict(source_body_start_block=blocks[0]['id'],
                                               source_printed_rule_openers=openers))


def test_exact_enabling_formula_precedes_chapter_and_rules():
    assert hashlib.sha256(FORMULA.encode()).hexdigest()==DIGEST
    seg=parse(source())
    preamble=next(n for n in seg.root.children if n.kind=='preamble')
    assert preamble.first_block==1989746 and preamble.text==FORMULA
    chapter=next(n for n in seg.root.children if n.kind=='chapter')
    assert chapter.label=='I' and chapter.heading=='PRELIMINARY'
    rules=[n for n in chapter.children if n.kind=='section']
    assert [n.label for n in rules]==['1','2']
    assert [n.label for n in rules[0].children]==['1','2']
    assert [n.label for n in rules[1].children]==['1']
    assert not any('Islamabad' in(n.text or'')or'_dd_'in(n.text or'')for n in seg.flatten())


def test_formula_exception_is_inert_for_wrong_block_page_or_reading():
    for blocks in [source(bid=1989745),source(page=6),source(text=FORMULA+' Extra.'),
                   source(text=FORMULA.replace('Section 40','Section 41'))]:
        assert not S._is_source_preamble_intro_block(blocks[0])
        assert not any(n.kind=='preamble'for n in parse(blocks).root.children)


def test_reviewed_formula_whitespace_variation_keeps_exact_words():
    seg=parse(source(text=FORMULA.replace(' ','\n')))
    preamble=next(n for n in seg.root.children if n.kind=='preamble')
    assert preamble.text==FORMULA
