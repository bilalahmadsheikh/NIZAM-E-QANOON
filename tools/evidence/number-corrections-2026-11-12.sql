-- Instrument numbers: two reviewed adjustments to tools/record_instrument_numbers.py --correct-stored (12 Nov 2026).
-- Run AFTER the recorder's --apply. Each insert is guarded, so the file can be re-run safely.
--
-- 1707  The Service Tribunals Act, 1973. The segmenter stored 'LXXI' -- the number of the Civil Servants Act, 1973,
--       which section 2 cites ('Civil Servants Act, 1973 (LXXI of 1973)'). Page 2 prints the Act's own heading
--       '1ACT NO. LXX OF 1973' (block 110086); the recorder's title region stops before page 2 (a long contents page),
--       so it is recorded here, with the same basis the recorder uses.
-- 9520  'The Sind Rent Restriction (Amendment) Act, 1948'. The recorder read 'ACT NO. XXV OF 1948' in the title region,
--       but that heading opens 'An Act further to amend the Indian Patents and Designs (Extension of Time) Act, 1942'
--       -- a different Act printed in the same Gazette span (the expression starts in the tail of yet another Act).
--       The correction is withdrawn; the instrument's boundary is a separate defect.
BEGIN;

INSERT INTO instrument_metadata_assertion
    (source_observation_id, expression_ordinal, field, value, assertion, basis, source_block_id, source_page, quote,
     method, evidence, recorded_by)
SELECT 437, 0, 'number', 'LXX', 'asserted', 'printed_number_corrects_stored', 110086, 2, '1ACT NO. LXX OF 1973',
       'nizam.printed_instrument_number/1',
       jsonb_build_object('reviewer_type', 'claude', 'stored_by_segmenter', 'LXXI',
                          'note', 'stored LXXI is the Civil Servants Act cited in s.2; the Act prints LXX on page 2'),
       'claude'
 WHERE NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.source_observation_id = 437 AND c.expression_ordinal = 0 AND c.field = 'number');

INSERT INTO instrument_metadata_assertion
    (source_observation_id, expression_ordinal, field, value, assertion, basis, method, evidence, recorded_by)
SELECT 11891, 0, 'number', NULL, 'withdrawn', 'printed_number_belongs_to_another_act',
       'nizam.printed_instrument_number/1',
       jsonb_build_object('reviewer_type', 'claude',
                          'note', 'ACT NO. XXV OF 1948 heads the Indian Patents and Designs (Extension of Time) '
                                  'Amendment Act, 1948, printed inside this expression''s span; not this Act''s number'),
       'claude'
 WHERE EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                WHERE c.source_observation_id = 11891 AND c.expression_ordinal = 0 AND c.field = 'number');

COMMIT;
