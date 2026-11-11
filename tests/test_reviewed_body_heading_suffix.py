"""Doc7968 Rule15: a reviewed plural heading must leave no suffix in law."""
import pytest

from nizam.corpus import segment as S

HEAD = 'Evaluation Process of Zone Applications'
BODY = 'The evaluation process shall be as under:'
DECISION = dict(export='reviewed.json', document_id=7968, question_id='q4')


def block(i, text, page=2):
    return dict(id=i, text=text, page_no=page, x0=72, x1=480,
                y0=100, page_height=842)


def source():
    return [block(1, 'CONTENTS\n1. Short title\n2. Definitions\n15. Evaluation Process of Zone Application', 1),
            block(2, '1. Short title. These Rules may be called Test Rules.'),
            block(3, '2. Definitions. In these Rules words have their meanings.'),
            block(1989855, '15. ' + HEAD + '\n' + BODY)]


def item(**kw):
    spec = dict(label='15', source_block_id=1989855, heading=HEAD,
                use='heading', owner_decision=DECISION)
    spec.update(kw)
    return spec


def rule15(blocks=None, specs=None):
    overrides = {} if specs is None else dict(source_printed_headings=specs)
    return next(n for n in S.segment(blocks or source(), profile='unreleased-v5',
                                    structural_overrides=overrides).flatten()
                if n.kind == 'section' and n.label == '15')


def test_reviewed_same_block_body_heading_supplies_the_complete_printed_word():
    node = rule15(specs=[item()])
    assert node.heading == HEAD
    assert node.text == BODY


def test_without_reviewed_heading_ordinary_contents_split_is_unchanged():
    assert rule15().text == 's ' + BODY


def test_margin_heading_use_does_not_change_body_split():
    assert rule15(specs=[item(use='marginal_note')]).text == 's ' + BODY


def test_elsewhere_in_source_block_does_not_authorize_prefix_removal():
    blocks = source()
    blocks[-1]['text'] = '15. Evaluation Process of Zone Application\n' + BODY + ' ' + HEAD
    assert rule15(blocks, [item()]).text == BODY + ' ' + HEAD


@pytest.mark.parametrize('change', [dict(source_block_id=999), dict(label='16'),
                                    dict(heading='Evaluation Process of Zone Applications EXTRA'),
                                    dict(owner_decision=None)])
def test_bad_source_heading_evidence_fails_closed(change):
    with pytest.raises(ValueError, match='source printed heading'):
        rule15(specs=[item(**change)])


def test_existing_full_word_heading_line_route_still_runs_once():
    blocks = source()
    blocks[0]['text'] = 'CONTENTS\n1. Short title\n2. Definitions\n15. Evaluation procedure'
    overrides = dict(source_printed_headings=[item()],
                     source_heading_lines=[{k:v for k,v in item().items() if k != 'use'}])
    seg = S.segment(blocks, profile='unreleased-v5', structural_overrides=overrides)
    node = next(n for n in seg.flatten() if n.kind == 'section' and n.label == '15')
    assert node.heading == HEAD and node.text == BODY
