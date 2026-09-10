-- Source-backed transcription evidence for four damaged embedded-font blocks.
-- This appends an assertion; it does not alter the PDF or an extraction row.
INSERT INTO extraction_assertion
    (sha256,page_no,kind,evidence,detail,asserted_by)
SELECT
    '13a00bb0010cb59519afba064ab7face9daa6209b1d870b84d145152ab6a3108',
    5,
    'source_content_confirmed',
    'Direct 600-DPI review of the official English gazette page, cross-checked '
    'against the Government of Sindh official Urdu publication, confirms the '
    'four schedule examples represented by damaged custom-font Unicode blocks.',
    jsonb_build_object(
        'method','two-official-render-cross-check',
        'source_page_render_dpi',600,
        'source_page_crop','100,225,470,405',
        'corroborating_url','https://www.sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-19-000056-U.pdf',
        'corroborating_sha256','252d0b14425f8fe47bbe57f0066a4f99a2f8680e51520b1ac9e8004a4e3e4ae6',
        'corroborating_object_key','evidence/pk-sindh/252d0b14425f8fe47bbe57f0066a4f99a2f8680e51520b1ac9e8004a4e3e4ae6',
        'replacement_manifest','tools/evidence/document-567-page-5-replacements.json',
        'blocks',jsonb_build_array(14,15,19,21)
    ),
    'codex-source-cross-review'
WHERE NOT EXISTS (
    SELECT 1 FROM extraction_assertion
     WHERE sha256='13a00bb0010cb59519afba064ab7face9daa6209b1d870b84d145152ab6a3108'
       AND page_no=5 AND kind='source_content_confirmed' AND is_active
       AND detail->>'replacement_manifest'=
           'tools/evidence/document-567-page-5-replacements.json'
);
