"""D-091: an approved release change cannot carry in a rebuild the drift review found worse than the release."""
import pytest

from nizam.storage import legal_write


def test_the_review_lists_the_laws_whose_release_is_right():
    verdicts = legal_write._drift_verdicts()
    assert {1101, 1977, 2904, 2491, 4347, 5494, 6576, 6784, 8173, 8213, 9310, 9659} <= set(verdicts)
    # closed laws rebuild identically and are not guarded
    assert not {2772, 4702, 8743, 9868} & set(verdicts)


def test_a_reviewed_law_refuses_an_approved_change():
    with pytest.raises(ValueError, match="drift review"):
        legal_write._refuse_reviewed_drift(2904)


def test_any_other_law_is_untouched():
    legal_write._refuse_reviewed_drift(1245)
    legal_write._refuse_reviewed_drift(4702)
