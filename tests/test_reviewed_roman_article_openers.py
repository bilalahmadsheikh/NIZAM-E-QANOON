"""Explicit source-bound ARTICLE I.–VII. captions in an incorporated schedule."""
import copy

import pytest

from nizam.corpus import segment as S


LABELS=['I','II','III','IV','V','VI','VII']


def fixture():
    def block(i,t):
        return dict(id=i,page_no=54,text=t,y0=100+i*10,page_height=900)
    blocks=[block(1,'296. The enactments specified in Schedule V are repealed.'),
            block(2,'SCHEDULE IV.\nDECLARATION.'),
            *[block(i+3,f'ARTICLE {label}.\nRetained source paragraph {label}.')
              for i,label in enumerate(LABELS)]]
    specs=[dict(source_block_id=i+3,kind='article',label=label,
                source_prefix=f'ARTICLE {label}.')for i,label in enumerate(LABELS)]
    outer=dict(source_division_openers=[dict(source_block_id=2,kind='schedule',label='SCHEDULE IV')])
    return blocks,specs,outer


def test_seven_reviewed_article_captions_remain_articles_of_the_schedule():
    blocks,specs,outer=fixture();before=copy.deepcopy(blocks)
    seg=S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                  structural_overrides=dict(outer,source_printed_rule_openers=specs))
    schedule=next(n for n in seg.flatten()if n.kind=='schedule')
    # Only matched explicit ARTICLE captions retain the source's article kind.
    assert [(n.kind,n.label)for n in schedule.children]==[('article',v)for v in LABELS]
    assert [n.text for n in schedule.children]==[f'Retained source paragraph {v}.'for v in LABELS]
    assert blocks==before


def test_plain_schedule_numerals_keep_ordinary_clause_typing_beside_reviewed_articles():
    blocks,specs,outer=fixture()
    blocks.append(dict(id=20,page_no=54,text='8. An ordinary numbered schedule row.',
                       y0=400,page_height=900))
    seg=S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                  structural_overrides=dict(outer,source_printed_rule_openers=specs))
    schedule=next(n for n in seg.flatten()if n.kind=='schedule')
    assert next(n for n in schedule.children if n.label=='8').kind=='clause'


def test_article_extension_is_inert_without_reviewed_openers():
    blocks,_,outer=fixture()
    seg=S.segment(blocks,detect_contents=False,profile='unreleased-v5',structural_overrides=outer)
    schedule=next(n for n in seg.flatten()if n.kind=='schedule')
    assert [n.label for n in schedule.children]!=LABELS
    assert not any(n.kind=='article'for n in schedule.children)


@pytest.mark.parametrize('change',[
    dict(label='II'),dict(label='VIII'),dict(source_prefix='ART I.'),
    dict(source_prefix='ARTICLE II.'),dict(source_prefix='ARTICLE I'),
    dict(source_prefix='ARTICLEI.'),dict(source_block_id=99),
])
def test_roman_article_opener_rejects_wrong_label_prefix_or_source(change):
    blocks,specs,outer=fixture();specs[0]=dict(specs[0],**change)
    with pytest.raises(ValueError):
        S.segment(blocks,detect_contents=False,profile='unreleased-v5',
                  structural_overrides=dict(outer,source_printed_rule_openers=specs))
