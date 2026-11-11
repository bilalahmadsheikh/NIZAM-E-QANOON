"""Keep the exact reviewed NEPRA notification, without admitting other SROs."""
from nizam.corpus import segment as S

INTRO = ('S.R.O. 631 /2022 In exercise of the powers conferred by section 47 read with '
         'proviso to sub-section (2) of section 50 of the Regulation of Generation, '
         'Transmission and Distribution of Electric Power Act, 1997 (Act No. XL of '
         '1997) and all other enabling provisions thereof, the National Electric '
         'Power Regulatory Authority is pleased to make the following regulations: -')


def parse(intro=INTRO, bid=2673355, page=2):
    blocks = [dict(id=bid, page_no=page, text=intro, y0=170, page_height=842),
              dict(id=2673356, page_no=2, text='1. Short title and commencement. - (1) These regulations shall be called the National Electric Power Regulatory Authority (Uniform System of Accounts) Regulations, 2022.', y0=250, page_height=842),
              dict(id=2673357, page_no=2, text='(2) They shall commence on the day notified.', y0=300, page_height=842)]
    return S.segment(blocks, detect_contents=False, profile='unreleased-v4',
                     structural_overrides={'source_body_start_block': bid})


def test_exact_notification_is_preserved_before_regulation_one():
    seg = parse()
    assert [n.kind for n in seg.root.children] == ['preamble', 'section']
    assert seg.root.children[0].text == INTRO
    assert seg.root.children[0].first_block == 2673355
    assert [n.label for n in seg.root.children[1].children] == ['1', '2']


def test_notification_exception_refuses_other_block_page_or_words():
    for bid, page, text in [(2673354, 2, INTRO), (2673355, 3, INTRO),
                            (2673355, 2, INTRO.replace('section 47', 'section 48')),
                            (2673355, 2, INTRO.replace('631', '632'))]:
        assert not S._is_source_preamble_intro_block(dict(id=bid, page_no=page, text=text))
        assert not any(n.kind == 'preamble' for n in parse(text, bid, page).root.children)


def test_whitespace_reflow_does_not_change_notification_words():
    assert parse(INTRO.replace(' ', '\n')).root.children[0].text == INTRO
