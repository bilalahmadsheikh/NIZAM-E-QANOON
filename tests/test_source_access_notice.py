"""An archival availability note cannot masquerade as a legal-text release."""
import pytest
from tools.source_access_notice import METHOD, plain_source_access, source_access_html


def notice():
    return dict(schema=METHOD, access_kind='original-facsimile-only', legal_text_released=False,
                operative_eligibility=False, body_transcription_qualified=False,
                validity_dates='unresolved', source_scope='Order ends within shared page56.',
                missing_evidence=['P.O.4of1958 effective date', '<script>alert(1)</script>'])


def test_notice_is_explicit_and_escapes_source_metadata():
    n = notice()
    rendered = source_access_html(n)
    assert 'Legal-text release remains held' in rendered
    assert 'raw OCR transcription has not been qualified' in rendered
    assert '<script>' not in rendered and '&lt;script&gt;' in rendered
    assert 'shared page56' in plain_source_access(n)


@pytest.mark.parametrize('key,value', [('legal_text_released', True),
    ('operative_eligibility', True), ('body_transcription_qualified', True),
    ('validity_dates', '1957-12-13'), ('missing_evidence', []), ('source_scope', '')])
def test_no_notice_can_imply_a_qualified_legal_body_or_hide_uncertainty(key, value):
    n = notice(); n[key] = value
    with pytest.raises(ValueError):
        source_access_html(n)
