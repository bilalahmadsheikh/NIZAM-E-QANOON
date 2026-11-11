"""Reviewed atomic amendments cannot consume the next amending opener."""
from copy import deepcopy
import pytest
from nizam.corpus import segment as S

def b(i,text,page=1):
    return dict(id=i,text=text,page_no=page,y0=100,page_height=900)

def test_next_reviewed_opener_immediately_after_atomic_quote_is_not_swallowed():
    texts=[
        '(2) in section 3, the following new clause shall be inserted, namely :— '
        '“(dd) Income Tax Panels;”; (b) after “Commissioners’, insert “Panels’’;',
        '(3) in section 4, the following new sub-sections shall be inserted, namely :— '
        '“(1A) The Commissioner may appint Panels. (1B) The Board may make rules.’’;',
        '(4) in section 5, the following new clause shall be inserted, namely :— “(cc) The Commissioner may direct',
        'that the Income Tax Officer shall exercise the powers.”;',
    ]
    t=S._K4_QSE_TEXTS.set(frozenset(texts[1:3]));seen=set()
    s=S._K4_QSE_SEEN.set(seen)
    try:
        spans=S._quoted_insertion_spans(texts,[1,1,1,2])
        assert spans=={3:3}
        assert seen=={x.strip()[:60]for x in texts[1:3]}
    finally:
        S._K4_QSE_TEXTS.reset(t);S._K4_QSE_SEEN.reset(s)

@pytest.mark.parametrize('text,kind,label',[
    ('Provided that the taxpayer shall retain the receipt.','proviso','Provided'),
    ('Explanation.—The allowance includes a payment in kind.','explanation','Explanation'),
    ('(2) The receipt shall be retained.','subsection','2'),
])
def test_exact_text_unit_can_continue_an_explicit_open_parent(text,kind,label):
    blocks=[b(1,'6. Amendments.—The following amendments shall be made.'),
            b(2,'(1) in the First Schedule, replace the rates as follows:—'),b(3,text,2)]
    before=deepcopy(blocks)
    over={'source_text_units':[dict(source_block_id=3,kind=kind,label=label)],
          'source_continuation_parent_blocks':[dict(source_block_id=3,parent_block_id=2)]}
    seg=S.segment(blocks,detect_contents=False,profile='unreleased-v5',structural_overrides=over)
    host=next(x for x in seg.flatten()if x.kind=='subsection'and x.label=='1')
    assert text in host.text and 3 in host.blocks
    assert not any(x.first_block==3 for x in seg.flatten())
    assert blocks==before
    wrong=deepcopy(over);wrong['source_text_units'][0]['label']='wrong'
    with pytest.raises(ValueError):
        S.segment(blocks,detect_contents=False,profile='unreleased-v5',structural_overrides=wrong)

@pytest.mark.parametrize('bid,page,text',[
    (2450882,49,'AN ORDINANCE to provide for the establishment of the National Tariff Commission'),
    (2451243,75,'A REGULATION to determine the last preceding census in respect of the Federally Administered Tribal Areas.'),
])
def test_exact_printed_purpose_survives_in_preamble(bid,page,text):
    blocks=[b(bid,text,page),b(bid+1,'WHEREAS it is expedient to make provision for the purpose aforesaid;',page),
            b(bid+2,'1. This instrument shall come into force at once.',page)]
    seg=S.segment(blocks,detect_contents=False,profile='unreleased-v5')
    assert seg.root.children[0].kind=='preamble'
    assert seg.root.children[0].text.startswith(text)
    for changed in [b(bid+100,text,page),b(bid,text,page+1),b(bid,text+' altered',page)]:
        assert not S._is_source_preamble_intro_block(changed)
