"""A contents-cited chapter must open before its reviewed partial section."""
from copy import deepcopy
import pytest
from nizam.corpus.segment import segment

def b(i,t,p=1):return dict(id=i,text=t,page_no=p,x0=60,x1=500,y0=100,page_height=1008)
TAIL='respect of whose default the guarantee is given, is called the principal debtor.'
DOC=[b(1,'CONTENTS\n117. Buyer rights.\n118. Warranty.\n119. Acceptance.\n120. Refusal.\n121. Price.\n122. Auction.\n123. Biddings.\nCHAPTER VIII.—OF INDEMNITY AND GUARANTEE.\n124. Indemnity.\n125. Indemnity holder.\n126. Guarantee.\n127. Consideration.'),
     b(2,'CHAPTER VII.\nSALE OF GOODS.',2),b(3,'117. Buyer rights. The buyer may recover damages.',2),
     b(4,TAIL,3),b(5,'127. Consideration. Anything done for the principal debtor is consideration.',3)]
CITE=dict(export='decision-review.json',document_id=9889,question_id='q4')
PARTIAL=dict(kind='section',printed_label=None,cited_label='126',source_block_id=4,source_prefix=TAIL,
             owner_decision=CITE,missing_before=[str(i)for i in range(118,126)],source_incompleteness_id=120)
DIV=dict(first_block_id=4,kind='chapter',label='VIII',heading='OF INDEMNITY AND GUARANTEE.',contents_block_ids=[1],owner_decision=dict(CITE,question_id='q5'))

def run(div=None):
    over=dict(source_body_start_block=2,source_owner_cited_labels=[PARTIAL])
    if div is not None:over['source_contents_named_divisions']=[div]
    return segment(deepcopy(DOC),profile='unreleased-v5',structural_overrides=over)

def test_partial_opener_uses_its_reviewed_contents_chapter_before_early_return():
    seg=run(DIV);secs=[n for n in seg.flatten()if n.kind=='section']
    assert [(n.label,n.parent.label)for n in secs]==[('117','VII'),('126','VIII'),('127','VIII')]
    assert secs[1].text==TAIL and secs[1].owner_cited and secs[1].printed_label_marker is None
    assert set(seg.missing)==set(str(i)for i in range(118,126))

def test_no_reviewed_division_keeps_existing_owner_cited_behavior():
    assert next(n for n in run().flatten()if n.label=='126').parent.label=='VII'

def test_wrong_contents_caption_fails_closed():
    with pytest.raises(ValueError,match='lacks exact source evidence'):
        run(dict(DIV,label='IX'))
