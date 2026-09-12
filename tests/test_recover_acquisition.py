from nizam.workers.recover_acquisition import safe_official_url, valid_pdf


def test_official_url_is_unicode_encoded_without_changing_host():
    value = safe_official_url(
        "https://kpcode.kp.gov.pk/uploads/NORTH–WEST ACT.pdf")
    assert value == "https://kpcode.kp.gov.pk/uploads/NORTH%E2%80%93WEST%20ACT.pdf"


def test_non_official_host_is_rejected():
    try:
        safe_official_url("https://example.com/not-authority.pdf")
    except ValueError as exc:
        assert "allow-listed" in str(exc)
    else:
        raise AssertionError("non-official host was accepted")


def test_balochistan_department_host_is_accepted():
    value = safe_official_url(
        "https://health.balochistan.gov.pk/wp-content/uploads/2025/03/2012.pdf"
    )
    assert value.startswith("https://health.balochistan.gov.pk/")


def test_html_error_body_is_not_a_pdf():
    ok, reason = valid_pdf(b"<html>not found</html>")
    assert not ok
    assert "%PDF-" in reason
