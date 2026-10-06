\set ON_ERROR_STOP on

BEGIN;

-- The first anchors were honest but not unique: page 2 of document 793 also
-- contains the same marginal heading on its amending section, and document
-- 1729's rule 12(2) repeats the words "seniority of Inspectors". Retire only
-- those refused records and replace them with source-exact unique anchors.
UPDATE segmentation_curation_patch
   SET retired_at=now()
 WHERE id IN ('eef4fb7f-c348-4e43-a97f-3cd99432af20',
              '86f9384e-0497-4ee2-b27f-bc357b24dedf')
   AND retired_at IS NULL;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,evidence,
     review_state,created_by)
VALUES
(3649,2,'(10) No member shall be liable',
$before$Amendment 
of 
section 51 of Sind 
Ordinance 
XII 
of 
1979. 
 
 $before$,' ',
 jsonb_build_object('reviewer_type','assistant','document_id',793,
   'source_block_id',35875,'purpose','remove fused marginal heading only',
   'supersedes_refused_patch','eef4fb7f-c348-4e43-a97f-3cd99432af20',
   'render_artifact','.artifacts/releases-six/source-pages/doc793-2.png',
   'render_sha256','452ac4b4e5d1e54d0c510f2837a1b33b1b328e54baf9c8e29e656be716bb6b96'),
 'source_verified','codex.release-six/1'),
(2168,4,'Seniority of Inspectors.- (1)', '(12)', '12.',
 jsonb_build_object('reviewer_type','assistant','document_id',1729,
   'source_block_id',112462,'purpose','top-level rule typography',
   'supersedes_refused_patch','86f9384e-0497-4ee2-b27f-bc357b24dedf',
   'render_artifact','.artifacts/releases-six/source-pages/doc1729-p4.png',
   'render_sha256','5b7628055b153db73c052692b20e165cf34e32508db56aa9082621a55ef6dc04'),
 'source_verified','codex.release-six/1')
ON CONFLICT DO NOTHING;

COMMIT;
