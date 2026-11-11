"""Render an annotated facsimile's source-access notice, never a legal release badge."""
from __future__ import annotations

import html

METHOD = 'nizam.source_access_release/1'


def validate_source_access(notice: dict) -> None:
    if notice.get('schema') != METHOD:
        raise ValueError('Unknown source-access contract')
    if (notice.get('access_kind') != 'original-facsimile-only'
            or notice.get('legal_text_released') is not False
            or notice.get('operative_eligibility') is not False
            or notice.get('body_transcription_qualified') is not False
            or notice.get('validity_dates') != 'unresolved'):
        raise ValueError('Source availability cannot qualify legal text or invent validity')
    if not notice.get('missing_evidence') or not notice.get('source_scope'):
        raise ValueError('Missing source scope or unresolved-evidence notice')


def plain_source_access(notice: dict) -> str:
    validate_source_access(notice)
    missing = '\n'.join('- ' + str(x) for x in notice['missing_evidence'])
    return ('ORIGINAL SCAN AVAILABLE WITH UNRESOLVED-DATE NOTICE\n'
            'Legal-text release remains held. This source is not qualified for dated legal answers.\n'
            'The raw OCR transcription has not been qualified.\n'
            + notice['source_scope'] + '\nMissing or unresolved evidence:\n' + missing + '\n')


def source_access_html(notice: dict) -> str:
    validate_source_access(notice)
    missing = ''.join('<li>' + html.escape(str(x)) + '</li>' for x in notice['missing_evidence'])
    return ('<aside class="source-access-notice" role="note" '
            'style="border:2px solid #9a641a;background:#fff6df;color:#332713;'
            'padding:16px;margin:0 0 18px;border-radius:8px">'
            '<strong>Original scan available with unresolved-date notice</strong>'
            '<p>Legal-text release remains held. This source is not qualified for dated legal answers. '
            'The raw OCR transcription has not been qualified.</p><p>'
            + html.escape(notice['source_scope']) + '</p>'
            '<details><summary>Missing or unresolved historical evidence</summary><ul>'
            + missing + '</ul></details></aside>')
