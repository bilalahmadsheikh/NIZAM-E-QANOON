\set ON_ERROR_STOP on

BEGIN;

-- Removing only the marginal heading left the opening curly quotation mark in
-- front of the substituted labels.  Section 14 was still recognisable, but
-- subsection (10) remained continuation text. Replace the two active patches
-- with source-exact versions that also remove that typographic quote.
UPDATE segmentation_curation_patch
   SET retired_at=now()
 WHERE id IN ('09e9cc8c-bb07-4709-9e69-eca687d72940',
              'e314f477-144c-4952-a744-433db4aabe6d')
   AND retired_at IS NULL;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,evidence,
     review_state,created_by)
VALUES
(3649,1,'A council other than taluka council',
$before$Substitution 
of 
section 14 of Sind 
Ordinance 
XII 
of 
1979. 
 
 “$before$,' ',
 jsonb_build_object('reviewer_type','assistant','document_id',793,
   'source_block_id',35865,'purpose','remove fused marginal heading and opening typographic quote only',
   'supersedes_patch','09e9cc8c-bb07-4709-9e69-eca687d72940',
   'render_artifact','.artifacts/releases-six/source-pages/doc793-1.png'),
 'source_verified','codex.release-six/1'),
(3649,2,'(10) No member shall be liable',
$before$Amendment 
of 
section 51 of Sind 
Ordinance 
XII 
of 
1979. 
 
 “$before$,' ',
 jsonb_build_object('reviewer_type','assistant','document_id',793,
   'source_block_id',35875,'purpose','remove fused marginal heading and opening typographic quote only',
   'supersedes_patch','e314f477-144c-4952-a744-433db4aabe6d',
   'render_artifact','.artifacts/releases-six/source-pages/doc793-2.png',
   'render_sha256','452ac4b4e5d1e54d0c510f2837a1b33b1b328e54baf9c8e29e656be716bb6b96'),
 'source_verified','codex.release-six/1')
ON CONFLICT DO NOTHING;

COMMIT;
