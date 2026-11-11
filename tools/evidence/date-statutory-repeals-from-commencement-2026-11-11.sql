-- Date the undated statutory repeals (migration 0066) whose repealing Act now has an established commencement.
--
-- 0066 records repealed_on only where the repealing Act prints a date under its title AND says it 'shall come into
-- force at once'; 54 repeals were left undated (repealed_by_id set, status 'unknown'). Migration 0070 now records,
-- from each Act's own text, its printed enactment date and -- only where the whole Act is self-executing -- its
-- commencement (tools/record_commencement.py). For a repealing Act whose commenced_on stands:
--   basis 'commences_at_once_on_printed_enactment_date'  -- exactly 0066's rule, now satisfiable (12);
--   basis 'commences_on_printed_date'                    -- the Act prints its own commencement date; a repeal it
--                                                           enacts operates from that date (4).
-- A new statutory_repeal row is appended for the same key, copying the standing row and adding the date and its
-- basis (append-only, latest wins). tools/apply_statutory_repeals.py then sets status 'repealed' and repealed_on.
-- Re-running inserts nothing: only standing rows that are still undated are taken.

BEGIN;

WITH standing AS (
    SELECT DISTINCT ON (s.repealed_observation_id, s.repealed_expression_ordinal, s.repealing_observation_id,
                        s.repealing_expression_ordinal, s.repealing_relative_path) s.*
      FROM statutory_repeal s
     ORDER BY s.repealed_observation_id, s.repealed_expression_ordinal, s.repealing_observation_id,
              s.repealing_expression_ordinal, s.repealing_relative_path, s.recorded_at DESC, s.id DESC),
dated AS (
    SELECT st.*, c.value::date AS commenced, c.basis AS commencement_basis, c.quote AS commencement_quote,
           c.id AS commencement_assertion_id
      FROM standing st
      JOIN v_statutory_repeal_current cur ON cur.id = st.id
      JOIN v_instrument_metadata_current c ON c.instrument_id = cur.repealing_instrument_id
                                          AND c.field = 'commenced_on'
                                          AND c.basis IN ('commences_at_once_on_printed_enactment_date',
                                                          'commences_on_printed_date')
     WHERE st.assertion = 'repealed' AND st.repealed_on IS NULL)
INSERT INTO statutory_repeal
    (repealed_observation_id, repealed_expression_ordinal, repealing_observation_id, repealing_expression_ordinal,
     repealing_source_block_id, repealing_relative_path, clause_text, matched_title, matched_year, repealed_on,
     repealed_on_basis, assertion, method, evidence, recorded_by)
SELECT repealed_observation_id, repealed_expression_ordinal, repealing_observation_id, repealing_expression_ordinal,
       repealing_source_block_id, repealing_relative_path, clause_text, matched_title, matched_year, commenced,
       CASE commencement_basis
            WHEN 'commences_at_once_on_printed_enactment_date'
            THEN 'the repealing Act comes into force at once and its printed enactment date is ' || commenced
            ELSE 'the repealing Act prints its commencement date, ' || commenced END,
       'repealed', 'nizam.statutory_repeal_dated_by_commencement/1',
       evidence || jsonb_build_object('reviewer_type', 'tool',
                                      'dated_from_commencement_assertion', commencement_assertion_id,
                                      'commencement_quote', commencement_quote,
                                      'supersedes_undated_row', id),
       'claude'
  FROM dated;

COMMIT;
