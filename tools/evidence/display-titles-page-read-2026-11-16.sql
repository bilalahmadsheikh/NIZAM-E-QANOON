-- Display titles read from the page for released Balochistan amendment notifications whose catalogue title is an
-- abbreviation ('Baln Educ Dept (Clg Branch)(Mens Section) ... S.Rules, 2020 (Amend 2024)') and whose text prints no
-- short-title clause (lead, 16 Nov 2026). Each name is the rules the notification itself says it amends ('... is
-- pleased to make the following amendments in the <Rules>'), quoted below, with the notification's year.
-- 7782 is NOT named here: its clause is too OCR-damaged ('Service Hikes, BOWS') to state the name. Append-only.

BEGIN;

WITH d(doc, name, quote) AS (VALUES
  (7585, 'The Balochistan Education Department (Collegiate Branch) (Men''s Section) (BPS-16 and above) Service Rules, 2020 — Amendment Notification, 2024',
         'following amendments in the Balochistan Education Department (Collegiate Branch) (Men’s Section) (BPS-16 and above) Service Rules, 2020'),
  (7654, 'The Balochistan Coastal Development and Fisheries Department (BPS-16 and above) Service Rules, 2016 — Amendment Notification, 2020',
         'following amendments in the Balochistan Coastal Development and Fisheries Department (BPS-16 and above) Service Rules, 2016'),
  (7643, 'The Balochistan Tehsildari Service Rules, 2015 — Amendment Notification, 2021',
         'following amendments in the Balochistan Tehsildari Service Rules, 2015'),
  (7696, 'The Balochistan Directorate of Agriculture-Crop Reporting Services (BPS-16 and above) Service Rules, 2017 — Amendment Notification, 2024',
         'following amendments in the Balochistan Directorate of Agriculture-Crop Reporting Services (BPS-16 and above) Service Rules, 2017'),
  (9688, 'The Balochistan Secretariat (Miscellaneous Posts) (BPS-16 and above) Service Rules, 2016 — Amendment Notification, 2024',
         'following amendments in the Balochistan Secretariat (Miscellaneous Posts) (BPS-16 and above) Service Rules, 2016'),
  (7632, 'The Balochistan Excise and Taxation Department (BPS-1 to 15) Service Rules, 2016 — Amendment Notification, 2019',
         'following amendments in the Balochistan Excise and Taxation Department (BPS-1 to 15) Service Rules, 20 16'),
  (7549, 'The Balochistan Civil Servants (Appointment, Promotion and Transfer) Rules, 2009 — Notification, 2021',
         'the Provincial Cabinet is pleased to authorize the Chief Minister Balochistan to make all service rules (except Recruitment Rules made under rule 3(2) of the Balochistan Civil Servants (Appointment, Promotion and Transfer) Rul')
)
INSERT INTO instrument_metadata_assertion
       (source_observation_id, expression_ordinal, field, value, assertion, basis, method, evidence, recorded_by)
SELECT i.source_observation_id, i.expression_ordinal, 'display_title', d.name, 'asserted', 'reviewed_corrected_name',
       'nizam.display_title_from_printed_text/1',
       jsonb_build_object('reviewer_type', 'claude', 'page_read', true, 'review_evidence', d.quote,
                          'corrected_from', i.short_title, 'reviewed_file',
                          'tools/evidence/display-titles-page-read-2026-11-16.sql'),
       'claude'
  FROM d JOIN v_release_instrument i ON i.document_id = d.doc
 WHERE NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.instrument_id = i.id AND c.field = 'display_title');

COMMIT;
