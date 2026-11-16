-- The Azad Jammu and Kashmir Rent Restriction Act, 1986 (doc 10394, obs 14327) s.26, page-read 16 Nov 2026 while
-- authoring golden set 2: "Repeal.- The Azad Jammu and Kashmir Rent Restriction Act, 1952 (Council Order No. 659/52
-- a define Azad Jammu and Kashmir Rent Restriction Ordinance, 1986 (Ordinance XXIX of 1986) are hereby repealed."
-- Its s.1 prints "It shall come into force at once"; it is dated 1986-03-05.
--
-- record_statutory_repeals.py missed it: the clause names "Azad Jammu and Kashmir Rent Restriction Act, 1952" while
-- both held texts of that law are titled "The Azad Kashmir Rent Restriction Act, 1952" (docs 10096 and 11195, the
-- same law released twice), so no exact title matched. The owner presumption (16 Nov) then made the 1952 Act
-- current. Both texts are recorded here, from the one clause, by a reviewer who read the clause and both titles.
INSERT INTO statutory_repeal
    (repealed_observation_id, repealed_expression_ordinal, repealing_observation_id, repealing_expression_ordinal,
     repealing_source_block_id, repealing_relative_path, clause_text, matched_title, matched_year, repealed_on,
     repealed_on_basis, assertion, method, evidence, recorded_by)
SELECT o.obs, 0, 14327, 0, 2770772, 's_26',
       'Repeal.- The Azad Jammu and Kashmir Rent Restriction Act, 1952 (Council Order No. 659/52 a define Azad Jammu '
       'and Kashmir Rent Restriction Ordinance, 1986 (Ordinance XXIX of 1986) are hereby repealed.',
       'The Azad Jammu and Kashmir Rent Restriction Act, 1952', 1952, DATE '1986-03-05',
       'the repealing Act comes into force at once and its printed enactment date is 1986-03-05',
       'repealed', 'nizam.statutory_repeal_page_read/1',
       jsonb_build_object('reviewer_type', 'lead', 'read', 'doc 10394 s.1 and s.26; titles of docs 10096 and 11195',
                          'why_missed', 'title printed as "Azad Jammu and Kashmir", held as "Azad Kashmir"',
                          'repealed_document', o.doc),
       'tools/evidence/ajk-rent-1952-repealed-by-1986-2026-11-16.sql'
  FROM (VALUES (14178, 10096), (14297, 11195)) o(obs, doc)
 WHERE NOT EXISTS (SELECT 1 FROM statutory_repeal r WHERE r.repealed_observation_id = o.obs
                      AND r.repealing_observation_id = 14327 AND r.repealing_relative_path = 's_26');
