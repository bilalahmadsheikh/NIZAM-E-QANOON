"""8364's singular-power recital must preserve the top-level32rule series."""
from copy import deepcopy
import pytest
import nizam.corpus.segment as S

RECITAL=('In the exercise of the power conferred by the Indian Income Tax Act, Section 46, '
         'the Governor-General in Council is pleased to make the following rules for the '
         'guidance of officers connected with the enforcement of the Act.')

def block(i,text,page=13):
    return dict(id=i,text=text,page_no=page,y0=100,page_height=1008,x0=70,x1=500)

def run(recital):
    return S.segment([recital,block(2717794,'1. Section 2.—A person is defined to include a Hindu undivided family.'),
                      block(2717795,'2. Section 4.—All orders of exemption remain in force.')],
                     detect_contents=False,profile='unreleased-v5')

def test_exact_source_recital_opens_preamble_without_owning_numbered_rules():
    b=block(2717793,RECITAL);old=deepcopy(b);seg=run(b)
    assert [(n.kind,n.label)for n in seg.root.children]==[('preamble','Preamble'),('section','1'),('section','2')]
    assert seg.root.children[0].text==RECITAL
    assert b==old

@pytest.mark.parametrize('change',['id','page','word'])
def test_nearby_or_modified_source_does_not_gain_the_exception(change):
    b=block(2717793,RECITAL)
    if change=='id':b['id']+=100
    elif change=='page':b['page_no']+=1
    else:b['text']=RECITAL.replace('power conferred','powers conferred')
    assert not S._is_source_preamble_intro_block(b)
    assert not any(n.kind=='preamble'for n in run(b).flatten())

def test_income_tax_enacted_purpose_is_preserved_as_source_preamble():
    text=('An Act for the purpose of imposing duties on income arising from offices, property, '
          'professions and trades: It is hereby enacted as follows:—')
    seg=S.segment([block(2716562,text,2),block(2716564,'1. This Act may be called The Indian Income Tax Act.',2)],
                  detect_contents=False,profile='unreleased-v5')
    assert seg.root.children[0].kind=='preamble' and seg.root.children[0].text==text
    assert not S._is_source_preamble_intro_block(block(2716562,text.replace('imposing','collecting'),2))
