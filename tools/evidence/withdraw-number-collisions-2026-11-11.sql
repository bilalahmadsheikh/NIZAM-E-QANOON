-- Withdraw six printed-number assertions (migration 0070) that collide with a DIFFERENT law of the same series.
--
-- tools/record_instrument_numbers.py recorded 510 numbers on 11 Nov 2026. v_instrument_duplicates then showed 23
-- groups involving one of them. Most are not errors: either two copies of one law (the number confirms the
-- duplicate) or two numbering series filed under one jurisdiction (West Pakistan Acts/Ordinances stored as 'fed';
-- post-1958 Post-Proclamation Ordinances). The six below are the same series, different laws, and the text alone does
-- not say which number is right -- so the recorded one is withdrawn and the instrument keeps no number.
--   7420 e0  Baluchistan (Administration of Evacuee Property) Regulation 1950 -- 'Regulation I of 1950' is also 8460's
--   8527 e0  Pakistan (Administration of Evacuee Property) Ordinance 1956     -- 'XVIII of 1956' is also 9094's
--   8680 e0, 8336 e0  two different President's Orders both read 'No. 2 of 1972'
--   9773 e1  Balochistan Speaker's and Deputy Speaker's (Salaries...) Act 1975 -- read the heading of e0 (Act II)
--   7580 e0  Letters Patent and CrPC (Suspension...) Ordinance 1977          -- 'XXI of 1977' is also 6462's
-- Second pass (same day, after the title region learned to skip contents pages):
--   4378 e1  KP Public Financial Management Act 2022 -- 'Act No. XXIX of 2022' is also e0's (KP Finance Act 2022)
-- Each row is inserted only while its number still stands, so the file can be re-run safely.

BEGIN;

INSERT INTO instrument_metadata_assertion
    (source_observation_id, expression_ordinal, field, value, assertion, basis, method, evidence, recorded_by)
SELECT k.obs, k.ord, 'number', NULL, 'withdrawn', 'collides_with_different_law_same_series',
       'nizam.printed_instrument_number/1',
       jsonb_build_object('reviewer_type', 'claude', 'collides_with_document', k.other,
                          'note', 'same jurisdiction, kind, number and year as a different law; not resolvable from text'),
       'claude'
  FROM (VALUES (11303, 0, 8460), (13026, 0, 9094), (11853, 0, 8336), (12995, 0, 8680),
               (10261, 1, 671), (12679, 0, 6462), (1898, 1, 4378)) AS k(obs, ord, other)
 WHERE EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                WHERE c.source_observation_id = k.obs AND c.expression_ordinal = k.ord AND c.field = 'number');

COMMIT;
