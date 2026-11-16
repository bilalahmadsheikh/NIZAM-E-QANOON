-- nzq_amendment_marks (0097) counted brackets that are not amendment marks.
--
-- Read 16 Nov 2026 in the Anti-Rape (Investigation and Trial) Ordinance, 2020 (doc 5366), which was never amended:
-- its leaked Gazette running heads "DECEMBER 18,2020 [PART I" and "Rs. 20.00 [6538" were counted as 'N[' insertion
-- marks, and OCR's "I]TIIVERSITY" as a closing one, so 0098 held the whole Ordinance unknown before capture. A schedule
-- heading "[See section 2]" is not an amendment either.
--
-- Now:
--   * an opening mark is one or two digits immediately before '[' that are not the tail of a longer number, a year or
--     a decimal ('1[Interior Division]', '2[:]');
--   * a closing ']' counts only when no letter or digit follows it ('rupees.]', 'Division] may'), and only beyond the
--     plain brackets the same text opens ('[See section 2]' cancels itself);
--   * an omission mark is 'N* * *' with the same digit rule.
-- marks = greatest(opening marks, unmatched closings) + omissions. The snapshot is refreshed here.
--
-- REVERSAL: restore 0097's nzq_amendment_marks and refresh mv_provision_text_known_from.
-- Governing contract: INV-5; migrations 0097, 0098.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE OR REPLACE FUNCTION nzq_amendment_marks(t text) RETURNS integer
LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = public, pg_temp AS $$
    WITH c AS (
        SELECT (SELECT count(*) FROM regexp_matches(coalesce(t, ''), '(?<![0-9.,])[0-9]{1,2}\s*\[', 'g')) AS opens,
               (SELECT count(*) FROM regexp_matches(coalesce(t, ''), '\[', 'g'))                          AS all_opens,
               (SELECT count(*) FROM regexp_matches(coalesce(t, ''), '\](?![A-Za-z0-9])', 'g'))            AS closes,
               (SELECT count(*) FROM regexp_matches(coalesce(t, ''), '(?<![0-9.,])[0-9]{1,2}\s*\*\s*\*\s*\*', 'g'))
                                                                                                          AS omits)
    SELECT (greatest(opens, greatest(closes - (all_opens - opens), 0)) + omits)::int FROM c
$$;

DO $$
BEGIN
    IF nzq_amendment_marks('Punishment for marrying a child. ... fine of fifty thousand rupees.]') <> 1
       OR nzq_amendment_marks('Talaq. (1) Any man ... to the wife 2[:] that where') <> 1
       OR nzq_amendment_marks('The 1[Interior Division] may certify an observation home') <> 1
       OR nzq_amendment_marks('Interpretation clause In this Act___ 5* * * * * * *') <> 1
       OR nzq_amendment_marks('THE GAZETTE OF PAKISTAN, EXTRA., DECEMBER 18,2020 [PART I') <> 0
       OR nzq_amendment_marks('Price : Rs. 20.00 [6538(2') <> 0
       OR nzq_amendment_marks('STATIONERY AND FORMS, I]TIIVERSITY ROAD') <> 0
       OR nzq_amendment_marks('SCHEDULE [See section 2]') <> 0
       OR nzq_amendment_marks('Whoever commits theft shall be punished') <> 0 THEN
        RAISE EXCEPTION '0099: amendment markers misread';
    END IF;
END $$;

REFRESH MATERIALIZED VIEW mv_provision_text_known_from;

COMMIT;
