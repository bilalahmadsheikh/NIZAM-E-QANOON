"""Source-bound preamble recovery must stay inert on unreviewed prose."""
from nizam.corpus.segment import _is_source_preamble_intro_block

INTRO = ('In exercise of the powers conferred by section 43 of the [illegible] '
         'Development Finance Corporation Act, 1952 (XVII of 1952), the [illegible] '
         'of Directors of the Agricultural Development Finance [illegible] with '
         'the previous sanction of the Central Government, hereby [illegible] '
         'the following amendments to the Agricultural Development [illegible] '
         'Corporation General Regulations, namely:—')


def test_only_exact_reviewed_intro_is_admitted():
    block = dict(id=2511403, page_no=56, text=INTRO)
    assert _is_source_preamble_intro_block(block)
    assert not _is_source_preamble_intro_block(dict(block, id=2511404))
    assert not _is_source_preamble_intro_block(dict(block, page_no=57))
    assert not _is_source_preamble_intro_block(dict(block, text=INTRO.replace('[illegible]', 'Board', 1)))
