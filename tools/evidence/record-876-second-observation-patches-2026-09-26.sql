-- Doc 876 (Al-Hamd Islamic University, Quetta Act 2005) is carried by two
-- catalogue observations, 1207 ("...Act 2005.doc") and 1208 ("...Act 2005"),
-- over the same document blocks. The four page-read curation patches were
-- recorded for 1207 only (tools/record_curation_patch.py found one
-- observation when it ran), so 1208's pinned replay built its tree without
-- them. The readings are block-anchored on document 876 and apply to both
-- observations unchanged; this copies each 1207 row to 1208, append-only,
-- and says so in the evidence.
BEGIN;
DO $$
BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id=1207 AND retired_at IS NULL
         AND review_state='source_verified'
         AND evidence->>'document_id'='876') <> 4
     OR EXISTS (SELECT 1 FROM segmentation_curation_patch
                 WHERE source_observation_id=1208 AND retired_at IS NULL) THEN
    RAISE EXCEPTION 'doc 876 patches not in the expected state';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
  (source_observation_id, operation, page_no, match_text, before_text, after_text,
   evidence, review_state, created_by)
SELECT 1208, operation, page_no, match_text, before_text, after_text,
       evidence || jsonb_build_object('copied_from_observation', 1207,
                                      'copied_from_patch', id::text,
                                      'same_document_blocks', true),
       review_state, created_by
  FROM segmentation_curation_patch
 WHERE source_observation_id=1207 AND retired_at IS NULL
   AND review_state='source_verified' AND evidence->>'document_id'='876';
COMMIT;
