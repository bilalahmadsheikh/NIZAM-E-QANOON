-- Doc 2658, builder BZ 14 Oct 2026 (CLAUDE-CLAIMS). Precedent: retire-589-order-dependent-patches-2026-09-28.sql.
-- Two identity readings of agent JA (claude/agJA/patch-2658.json) carry structural keys on Appendix cell blocks
-- 229908 (p7) and 229922 (p8) with the locators 'and 15 years service' / '10 years experience or'. The row readings
-- recorded with them (500a1274, 98fc3b4e) merge each row's cells into the row block in column order, so after them the
-- two locators matched two blocks and the replay failed closed before writing. They are retired (not deleted) and the
-- same readings re-recorded with locators that keep the cell block's printed line break
-- (claude/agBZ/patch-2658-relocated.json); the readings themselves are unchanged.
BEGIN;
UPDATE segmentation_curation_patch SET retired_at = now()
 WHERE retired_at IS NULL
   AND id IN ('6acbae06-7748-41b6-aa47-188691631285', 'fe485a84-4939-4780-905a-0df57f6e6d00');
SELECT id, page_no, match_text, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE id IN ('6acbae06-7748-41b6-aa47-188691631285', 'fe485a84-4939-4780-905a-0df57f6e6d00');
COMMIT;
