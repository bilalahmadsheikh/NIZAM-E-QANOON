-- Doc 1666 (Bonded Labour System Rules 1995) is carried by two catalogue observations over the same document
-- blocks: 2484 (canonical) and 2550 (duplicate_of the canonical instrument; same SHA-256 bd9d48d8...).
-- tools/record_curation_patch.py records a reading on the canonical observation only, and a pinned replay of
-- 2550 without the readings builds a different tree (doc 876). The readings (claude/agCN/patch-1666.json, owner
-- decision 2026-10-08 export -h q1 'rule-3') are block-anchored on document 1666 and apply to both observations
-- unchanged; this copies each of the 3 rows just recorded on 2484 to 2550, append-only, and says so in the
-- evidence. Pattern: tools/evidence/record-1695-second-observation-patches-2026-09-27.sql. Builder BZ, 9 Oct 2026.
BEGIN;
DO $$
BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id=2484 AND retired_at IS NULL
         AND review_state='source_verified'
         AND evidence->>'document_id'='1666') <> 3
     OR EXISTS (SELECT 1 FROM segmentation_curation_patch
                 WHERE source_observation_id=2550 AND retired_at IS NULL) THEN
    RAISE EXCEPTION 'doc 1666 patches not in the expected state';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
  (source_observation_id, operation, page_no, match_text, before_text, after_text,
   evidence, review_state, created_by)
SELECT 2550, operation, page_no, match_text, before_text, after_text,
       evidence || jsonb_build_object('copied_from_observation', 2484,
                                      'copied_from_patch', id::text,
                                      'same_document_blocks', true),
       review_state, created_by
  FROM segmentation_curation_patch
 WHERE source_observation_id=2484 AND retired_at IS NULL
   AND review_state='source_verified' AND evidence->>'document_id'='1666';
COMMIT;
