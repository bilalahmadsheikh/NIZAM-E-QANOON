-- Document 220 official PDF: page 1 is a contents list; enacted title and
-- preamble start on page 2 at source block 9061. This identity curation patch
-- records the reviewed boundary without altering immutable extracted text.
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id=1521 AND sha256=
       '251cc3123b49a795d148d3e3ae5ef764dbf1558c4fa8f5fb0426ad736dbb2497')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=9061
                    AND document_id=220 AND page_no=2
                    AND text LIKE 'THE WEST PAKISTAN AGRICULTURAL%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=9067
                    AND document_id=220 AND page_no=2
                    AND btrim(text,E' \n\r\t')='Preamble.' AND x0 > 500)
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=9068
                    AND document_id=220 AND page_no=2
                    AND text LIKE E' \nWHEREAS, it is expedient%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=9071
                    AND document_id=220 AND page_no=2
                    AND text LIKE '%1[(2)  It shall extend%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=9075
                    AND document_id=220 AND page_no=2
                    AND encode(digest(btrim(regexp_replace(
                        text,'[[:space:]]+',' ','g')),'sha256'),'hex')=
                        'ca36fa965e4d00770091392b78d99c2565179c67eb8256b9a9975d3b2babbd39')
  THEN RAISE EXCEPTION 'doc 220 source no longer matches reviewed page';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (1521,2,'WHEREAS, it is expedient to provide facilities',
     'WHEREAS, it is expedient to provide facilities',
     'WHEREAS, it is expedient to provide facilities',
     jsonb_build_object(
       'document_id',220,'source_block_id',9068,
       'identity_text_patch',true,
       'defect','enacted title and preamble incorrectly included in contents',
       'structural_overrides',jsonb_build_object('source_body_start_block',9061),
       'source_sha256','251cc3123b49a795d148d3e3ae5ef764dbf1558c4fa8f5fb0426ad736dbb2497',
       'source_page_image','.artifacts/released-source-audit-2026-09-24/page-doc220-2.png',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
