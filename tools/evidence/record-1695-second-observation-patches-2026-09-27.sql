-- Doc 1695 is carried by two catalogue observations over the same document
-- blocks: 2372 (canonical) and 2781 (duplicate_of the canonical instrument).
-- tools/record_curation_patch.py records a reading on the canonical
-- observation only, and a pinned replay of 2781 without the readings builds a
-- different tree (doc 876). The readings are block-anchored on document 1695 and
-- apply to both observations unchanged; this copies each of the 10 rows just
-- recorded on 2372 to 2781, append-only, and says so in the evidence.
BEGIN;
DO $$
BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id=2372 AND retired_at IS NULL
         AND review_state='source_verified'
         AND evidence->>'document_id'='1695') <> 10
     OR EXISTS (SELECT 1 FROM segmentation_curation_patch
                 WHERE source_observation_id=2781 AND retired_at IS NULL) THEN
    RAISE EXCEPTION 'doc 1695 patches not in the expected state';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
  (source_observation_id, operation, page_no, match_text, before_text, after_text,
   evidence, review_state, created_by)
SELECT 2781, operation, page_no, match_text, before_text, after_text,
       evidence || jsonb_build_object('copied_from_observation', 2372,
                                      'copied_from_patch', id::text,
                                      'same_document_blocks', true),
       review_state, created_by
  FROM segmentation_curation_patch
 WHERE source_observation_id=2372 AND retired_at IS NULL
   AND review_state='source_verified' AND evidence->>'document_id'='1695';
COMMIT;
