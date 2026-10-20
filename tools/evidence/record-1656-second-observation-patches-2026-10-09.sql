-- Doc 1656 (Sind Regulation VIII of 1827) is carried by two catalogue observations over the same document
-- blocks: 3028 (canonical) and 3248 (duplicate_of the canonical instrument; same SHA-256 073647ad...).
-- tools/record_curation_patch.py records a reading on the canonical observation only, and a pinned replay of
-- 3248 without the readings builds a different tree (doc 876). The readings (claude/agCO/patch-1656.json, owner
-- decision 2026-10-08 export -h q1 'keep-both') are block-anchored on document 1656 and apply to both observations
-- unchanged; this copies each of the 7 rows just recorded on 3028 to 3248, append-only, and says so in the
-- evidence. Pattern: tools/evidence/record-1695-second-observation-patches-2026-09-27.sql. Builder BZ, 9 Oct 2026.
BEGIN;
DO $$
BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id=3028 AND retired_at IS NULL
         AND review_state='source_verified'
         AND evidence->>'document_id'='1656') <> 7
     OR EXISTS (SELECT 1 FROM segmentation_curation_patch
                 WHERE source_observation_id=3248 AND retired_at IS NULL) THEN
    RAISE EXCEPTION 'doc 1656 patches not in the expected state';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
  (source_observation_id, operation, page_no, match_text, before_text, after_text,
   evidence, review_state, created_by)
SELECT 3248, operation, page_no, match_text, before_text, after_text,
       evidence || jsonb_build_object('copied_from_observation', 3028,
                                      'copied_from_patch', id::text,
                                      'same_document_blocks', true),
       review_state, created_by
  FROM segmentation_curation_patch
 WHERE source_observation_id=3028 AND retired_at IS NULL
   AND review_state='source_verified' AND evidence->>'document_id'='1656';
COMMIT;
