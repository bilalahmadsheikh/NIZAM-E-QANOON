from nizam.workers.verify_order import lexical_words, ngrams, ordered_skip_trigrams


def _precision(stored: list[str], reference: list[str]) -> float:
    ours = ngrams(stored, 3)
    theirs = ordered_skip_trigrams(reference)
    return sum((ours & theirs).values()) / max(sum(ours.values()), 1)


def test_ordered_trigrams_tolerate_inserted_footnote_marker():
    stored = "the government may make rules under this act".split()
    reference = "the government may 1 make rules under this act".split()
    assert _precision(stored, reference) == 1.0


def test_ordered_trigrams_reject_meaning_changing_transposition():
    stored = "the dog bit the man after sunset".split()
    reference = "the man bit the dog after sunset".split()
    assert _precision(stored, reference) < 0.5


def test_sequence_normalises_attached_superscript_marker_only():
    assert lexical_words("1Substituted by Act 12") == ["substituted", "by", "act"]
