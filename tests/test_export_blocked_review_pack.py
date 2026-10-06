from tools.export_blocked_review_pack import _toc_body_pages


def test_bracketed_toc_case_gets_body_pages_and_limit_is_explicit():
    pages, search = _toc_body_pages({
        "contents_page": 1, "page_before": 4, "page_after": 8,
        "body_starts_page": 3,
    }, page_count=10, max_pages=2)
    assert pages == [4, 5]
    assert search["coverage_limited"]
    assert not search["inverted"]


def test_inverted_bracket_never_silently_swaps_to_wrong_page():
    pages, search = _toc_body_pages({
        "contents_page": 1, "page_before": 16, "page_after": 3,
        "body_starts_page": 2,
    }, page_count=20, max_pages=2)
    assert pages == [16, 17]
    assert search["inverted"]
    assert search["coverage_limited"]


def test_no_bracket_starts_after_contents_page():
    pages, search = _toc_body_pages({
        "contents_page": 2, "page_before": None, "page_after": None,
        "body_starts_page": None,
    }, page_count=8, max_pages=2)
    assert pages == [3, 4]
    assert search["coverage_limited"]
