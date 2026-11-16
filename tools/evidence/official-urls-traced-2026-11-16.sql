-- Official URLs for released laws whose source observation never recorded one (lead, 16 Nov 2026).
--
-- 53 released laws had source_url NULL: their observations came from the original portal scrapes (archive_path only)
-- and every one has an apostrophe in its title (Employers', Women's, President's ...) -- the scrapers lost the URL
-- when they sanitised the file name. Each was matched by title and year to the 13 Nov 2026 portal listing
-- (E:/nizam-data/acquire/portal-diff-2026-11-13/*-listing.csv), its official PDF fetched (TLS verified, generic
-- client), and accepted ONLY where the portal's bytes hash to the SAME sha256 as the held blob: then the URL is
-- proven to be where this exact file is published. 43 proven here; 10 had no listing row and are left NULL.
--
-- Only a NULL canonical_url is filled; nothing recorded is overwritten. The proof is kept in
-- source_metadata.canonical_url_traced. The active instrument rows get the same source_url a replay would give
-- them (legal_write takes it from the observation's canonical_url). Idempotent.

BEGIN;

UPDATE source_observation SET canonical_url = 'https://kpcode.kp.gov.pk/uploads/1987_01_REG_THE_NEWSPAPER_EMPLOYEES_CONDITIONS_OF_SERVICE_ACT_APPLICATION_TO_PROVINCIALLY_ADMINISTERED_TRIBAL_AREAS_REGULATION_1987.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://kpcode.kp.gov.pk/uploads/1987_01_REG_THE_NEWSPAPER_EMPLOYEES_CONDITIONS_OF_SERVICE_ACT_APPLICATION_TO_PROVINCIALLY_ADMINISTERED_TRIBAL_AREAS_REGULATION_1987.pdf", "detail_url": "https://kpcode.kp.gov.pk/homepage/lawDetails/713", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "536e0a6510f25a999f2a4e101e6cb819bf378c43348b0e1be1b78d3c7cc5b8a2", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '536e0a6510f25a999f2a4e101e6cb819bf378c43348b0e1be1b78d3c7cc5b8a2'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 559 AND is_active);
UPDATE source_observation SET canonical_url = 'https://kpcode.kp.gov.pk/uploads/1948_23_THE_NORTH_WEST_FRONTIER_PROVINCE_ADOLESCENT_PRISONERS_RELEASE_ON_PROBATION_ACT_1948.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://kpcode.kp.gov.pk/uploads/1948_23_THE_NORTH_WEST_FRONTIER_PROVINCE_ADOLESCENT_PRISONERS_RELEASE_ON_PROBATION_ACT_1948.pdf", "detail_url": "https://kpcode.kp.gov.pk/homepage/lawDetails/746", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "8cd3a902bb8bc095edfb0dc2673e75f9fab0ec3e3d762c81915fc67b1116d190", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '8cd3a902bb8bc095edfb0dc2673e75f9fab0ec3e3d762c81915fc67b1116d190'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 1165 AND is_active);
UPDATE source_observation SET canonical_url = 'http://balochistancode.gob.pk/lawdir/d259b249-733e-44ac-bde6-0afeee962e94.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "http://balochistancode.gob.pk/lawdir/d259b249-733e-44ac-bde6-0afeee962e94.pdf", "detail_url": "http://balochistancode.gob.pk/Document.aspx?wise=opendoc&docid=1366&docc=1306", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "00674f441d2dddcc17ebebba8d5fc266dd23d53492f0ca6cae8e70788b5c6d68", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '00674f441d2dddcc17ebebba8d5fc266dd23d53492f0ca6cae8e70788b5c6d68'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 1518 AND is_active);
UPDATE source_observation SET canonical_url = 'https://kpcode.kp.gov.pk/uploads/1926_10_THE_GOOD_CONDUCT_PRISONERS_PROBATIONAL_RELEASE_ACT_1926.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://kpcode.kp.gov.pk/uploads/1926_10_THE_GOOD_CONDUCT_PRISONERS_PROBATIONAL_RELEASE_ACT_1926.pdf", "detail_url": "https://kpcode.kp.gov.pk/homepage/lawDetails/983", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "7d785d6c91392aa070777cd4317ba7d79e184b0b59df586fbe2b49aace8036e7", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '7d785d6c91392aa070777cd4317ba7d79e184b0b59df586fbe2b49aace8036e7'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 1710 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/administrator-generals-punjab-rules-1914-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/administrator-generals-punjab-rules-1914-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/BD0GN1NhWm0-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "38906caa2314250ae7b2821cf8b2e9a4be58a0c6fdcc79d5f0e415ffff2ac73e", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '38906caa2314250ae7b2821cf8b2e9a4be58a0c6fdcc79d5f0e415ffff2ac73e'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2193 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratorbe81002044f65895757da5cc51a85222.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratorbe81002044f65895757da5cc51a85222.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-b5%2Bd-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "36571dbc19c37221242b3863e784da3953e5cd97b30b9c80e0666f6f0b4a76a4", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '36571dbc19c37221242b3863e784da3953e5cd97b30b9c80e0666f6f0b4a76a4'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2233 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratorb5d621089cd3b9f89bd243da38df4ee3.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratorb5d621089cd3b9f89bd243da38df4ee3.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Npa5pq-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "32181e1c310720b6e9043b61392df959f8929b8016007cb19ff4361abf684e24", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '32181e1c310720b6e9043b61392df959f8929b8016007cb19ff4361abf684e24'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2271 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/pessi-employers-returns-and-records-regulation-1967-pdf1.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/pessi-employers-returns-and-records-regulation-1967-pdf1.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/UGhVYwQxBTM-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "188a83a892ff26d29999588f5aff5e9261de5b5ab536eda1871e293466f1b603", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '188a83a892ff26d29999588f5aff5e9261de5b5ab536eda1871e293466f1b603'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2284 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator5a78ff5559911f2b13d17d04c7d27043.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator5a78ff5559911f2b13d17d04c7d27043.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-cJed-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "2ac0569806969dfe6f03c661fcb1c0d0e459d8c734e1cde20b674b85552c9f7a", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '2ac0569806969dfe6f03c661fcb1c0d0e459d8c734e1cde20b674b85552c9f7a'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2397 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/punjab-enforcement-of-womens-property-rights-act-2021-pdf1.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/punjab-enforcement-of-womens-property-rights-act-2021-pdf1.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/UWECNAcyVWxXPg--", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "4ea741fb0377092275be3025241c2f4eca3bfbc38a870a6b29289c60b4fd1eda", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '4ea741fb0377092275be3025241c2f4eca3bfbc38a870a6b29289c60b4fd1eda'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2442 AND is_active);
UPDATE source_observation SET canonical_url = 'https://kpcode.kp.gov.pk/uploads/The_Khyber_Pakhtunkhwa_Water_Users_Associations_Ordinance%2C_1981.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://kpcode.kp.gov.pk/uploads/The_Khyber_Pakhtunkhwa_Water_Users_Associations_Ordinance%2C_1981.pdf", "detail_url": "https://kpcode.kp.gov.pk/homepage/lawDetails/346", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "282cbd5dcd580704ca0a44a2430e22e6ac2a66fb46914f67e4ddda89faee4302", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '282cbd5dcd580704ca0a44a2430e22e6ac2a66fb46914f67e4ddda89faee4302'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2477 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-contributions-regulations-1967-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-contributions-regulations-1967-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/Bz9WYFdiUGM-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "98672c349bfb3a1d21b901a672e1a6e44d5e184f0563a330a3bcf839ba5e39e9", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '98672c349bfb3a1d21b901a672e1a6e44d5e184f0563a330a3bcf839ba5e39e9'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2479 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratore7155559002a87ff8a13fd82aceedf05.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratore7155559002a87ff8a13fd82aceedf05.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Npa5Zr-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "06abae9a6580afd9a9b934ca77374b96a259657f050a269f60da4299c459338a", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '06abae9a6580afd9a9b934ca77374b96a259657f050a269f60da4299c459338a'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2579 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator8d873828abdc2f65c379bbcea11fff10.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator8d873828abdc2f65c379bbcea11fff10.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Fuapw%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "f7d7aa4c6ef623cd22e49158e97983fa3548a9d46d9432ec274b692bd9bfd41d", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'f7d7aa4c6ef623cd22e49158e97983fa3548a9d46d9432ec274b692bd9bfd41d'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2633 AND is_active);
UPDATE source_observation SET canonical_url = 'https://kpcode.kp.gov.pk/uploads/1999_07_THE_SHARI_NIZAM_E_ADL_ACT_1999.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://kpcode.kp.gov.pk/uploads/1999_07_THE_SHARI_NIZAM_E_ADL_ACT_1999.pdf", "detail_url": "https://kpcode.kp.gov.pk/homepage/lawDetails/1199", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "8786c2e788439e70c73f0b07c169a4d6f4774bf340c3f0fcdda779ed84a583bd", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '8786c2e788439e70c73f0b07c169a4d6f4774bf340c3f0fcdda779ed84a583bd'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2659 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator9052d5a368bd546d5a8dbe428bf6744c.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator9052d5a368bd546d5a8dbe428bf6744c.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-bZk%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "e4f1cf6047328fbc20d11c2023057bdbe328779269573f8ed9e63bd1c0995654", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'e4f1cf6047328fbc20d11c2023057bdbe328779269573f8ed9e63bd1c0995654'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2674 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator838fddea2bd84054cde358506b537096.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator838fddea2bd84054cde358506b537096.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-bJg%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "5ba3f262962aea1b000141b7b943fc52d8e6fdc0c84eb1483967cc405a7939f7", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '5ba3f262962aea1b000141b7b943fc52d8e6fdc0c84eb1483967cc405a7939f7'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2702 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator27e8ffee09259f1aeb1927fcc66b301c.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator27e8ffee09259f1aeb1927fcc66b301c.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-bpuUY2ls-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "28cdfdd507dc1b07c35a531b84d9ebececd7a1e59543082a7c14af305f446368", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '28cdfdd507dc1b07c35a531b84d9ebececd7a1e59543082a7c14af305f446368'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2764 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/pessi-medical-advisors-qualifications-rules-1966-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/pessi-medical-advisors-qualifications-rules-1966-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/UWkCNFZiV2A-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "4819b9c7286db72cf433c1236fefabc95cecee93c1ed756f26b2e858a0776a59", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '4819b9c7286db72cf433c1236fefabc95cecee93c1ed756f26b2e858a0776a59'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2928 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator0514adf6314402fef39409941c94e967.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator0514adf6314402fef39409941c94e967.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apmXZA%3D%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "82300f49ae47102d9b5fc43cc105c1a9696f8bc666a766208c4a0d79cbf74a3a", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '82300f49ae47102d9b5fc43cc105c1a9696f8bc666a766208c4a0d79cbf74a3a'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3011 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/punjab-revenue-department-commissioner-2019-office-ministerial-service-rules-2008-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/punjab-revenue-department-commissioner-2019-office-ministerial-service-rules-2008-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/VG1TbQEzW2g-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "ca1672a6e307704d3d20b7737578a0e7af7443cac46af8f8926c605d2a4b856b", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'ca1672a6e307704d3d20b7737578a0e7af7443cac46af8f8926c605d2a4b856b'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3178 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/board-of-governors-cadet-college-pasrur-district-sialkots-rules-2011-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/board-of-governors-cadet-college-pasrur-district-sialkots-rules-2011-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/UmsAPws.ATE-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "8d901a8c5229e5036cc3e1f5360645dd33c0b45faa8e94259af693e5602d8dfb", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '8d901a8c5229e5036cc3e1f5360645dd33c0b45faa8e94259af693e5602d8dfb'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3185 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator080fe2813f4e31fb566cb0385a414fe1.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator080fe2813f4e31fb566cb0385a414fe1.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2NpapZi-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "2fde3e0b805a25938ba9d1df533360d729b252d87250cc1eb34e8eb03ead148b", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '2fde3e0b805a25938ba9d1df533360d729b252d87250cc1eb34e8eb03ead148b'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3212 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/official-trustees-punjab-rules-1914-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/official-trustees-punjab-rules-1914-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/ADkFOgU0Wmk-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "263f9b7916c6d4fed4717d9d6f447c9b7c2cdd73e06aeeeeb5839882f0cc0aba", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '263f9b7916c6d4fed4717d9d6f447c9b7c2cdd73e06aeeeeb5839882f0cc0aba'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3297 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratorf2659375fe49533f79b277d9a770c645.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratorf2659375fe49533f79b277d9a770c645.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-cJo%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "fe990c0ed11c187ed9770a6a141bb19da055ee113765bbcf7f66ea897a77b068", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'fe990c0ed11c187ed9770a6a141bb19da055ee113765bbcf7f66ea897a77b068'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3313 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator5d3f29ab30222e9f556d9a02bf22d823.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator5d3f29ab30222e9f556d9a02bf22d823.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-b5uX-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "bf466a5790bfd9bedd078d6a8c9b6cb9bdddc319fe07e53956db734574804379", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'bf466a5790bfd9bedd078d6a8c9b6cb9bdddc319fe07e53956db734574804379'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3323 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator2572c4ac0ac32549a5562652ef9cf8a9.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator2572c4ac0ac32549a5562652ef9cf8a9.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apiW-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "cfa5248c9162320dbd691fa0fb66a7e117cf86e36b0eb2d1c184b9c47abf9ad0", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'cfa5248c9162320dbd691fa0fb66a7e117cf86e36b0eb2d1c184b9c47abf9ad0'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3343 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/punjab-employees-social-security-travelling-allowance-regulations-2004-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/punjab-employees-social-security-travelling-allowance-regulations-2004-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/Bz8GMAI3AjU-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "3ad77eac68291e735e4a16375def50cbd8a61e4677b4f4b764257cf5ade3407b", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '3ad77eac68291e735e4a16375def50cbd8a61e4677b4f4b764257cf5ade3407b'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3377 AND is_active);
UPDATE source_observation SET canonical_url = 'https://kpcode.kp.gov.pk/uploads/1975_03_THE_KHYBER_PAKHTUNKHWA_SPEAKER_AND_DEPUTY_SPEAKERS_SALARIES_ALLOWANCES_AND_PRIVILEGES_ACT_1975.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://kpcode.kp.gov.pk/uploads/1975_03_THE_KHYBER_PAKHTUNKHWA_SPEAKER_AND_DEPUTY_SPEAKERS_SALARIES_ALLOWANCES_AND_PRIVILEGES_ACT_1975.pdf", "detail_url": "https://kpcode.kp.gov.pk/homepage/lawDetails/470", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "abcb230e3afb57261d4f8ca12885662fb5a9965e07884f59baefa9b16e56bf81", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'abcb230e3afb57261d4f8ca12885662fb5a9965e07884f59baefa9b16e56bf81'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3418 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator484616c50fb23172262b08aa2c109772.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator484616c50fb23172262b08aa2c109772.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Npbps%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "4d66926aa01d10aca5529e8e36449e16c108a3d56de28a83557e31868de1d7e5", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '4d66926aa01d10aca5529e8e36449e16c108a3d56de28a83557e31868de1d7e5'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3473 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratora522f8db17a8fa28b29b5444ded32b3c.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratora522f8db17a8fa28b29b5444ded32b3c.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Npa5pjaw%3D%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "7c62b3e7afd82f5707e348d91b9b1927e1d096102b364a98c93bb15416c06cd1", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '7c62b3e7afd82f5707e348d91b9b1927e1d096102b364a98c93bb15416c06cd1'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3533 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-contributions-rules-1966-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-contributions-rules-1966-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/U2tSZFBlBTc-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "81c3368ac5574f4e432a5c396d1eeae74cb1caa16b5efa63c4e44dba6e0fc373", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '81c3368ac5574f4e432a5c396d1eeae74cb1caa16b5efa63c4e44dba6e0fc373'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3627 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/punjab-province-workers-children-education-cess-utilization-rules-1978-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/punjab-province-workers-children-education-cess-utilization-rules-1978-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/UGhTZgU1BTQ-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "b7957d7774685258d74b28f6d68667564cdca5888ad148759e90cf31abaa1455", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'b7957d7774685258d74b28f6d68667564cdca5888ad148759e90cf31abaa1455'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3758 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/32-punjab-hindu-womens-rights-to-agricultural-land-ordinance-1959-xi-of-1959-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/32-punjab-hindu-womens-rights-to-agricultural-land-ordinance-1959-xi-of-1959-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/VmNWZVZoUGE-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "a3ce18ee1d00e86980559612bef8b1ff7d263a0df94feedb3e2c8f8d23c25b6e", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'a3ce18ee1d00e86980559612bef8b1ff7d263a0df94feedb3e2c8f8d23c25b6e'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3815 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator3772954c177afad4f21b0257142ed337.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator3772954c177afad4f21b0257142ed337.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apiX-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "bf1dd2d67a89c47edada32464e857ba717ff60a511389f77e583503e42cefcfa", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'bf1dd2d67a89c47edada32464e857ba717ff60a511389f77e583503e42cefcfa'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3948 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratorc0a301ae45df31b6a4b3828a5cd57fde.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratorc0a301ae45df31b6a4b3828a5cd57fde.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-ap2U-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "16766c96c83df5b4c0d31a1e26adffc1629c285ad643fe1731d47cecbf8332b8", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '16766c96c83df5b4c0d31a1e26adffc1629c285ad643fe1731d47cecbf8332b8'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4007 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/17-punjab-agriculturists-loans-act-1958-xvii-of-1958-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/17-punjab-agriculturists-loans-act-1958-xvii-of-1958-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/ADVRYgU3ATc-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "11b08f93a4494d9a084b0eef52a18b035db266eb480a52843072e1c5f6c03b40", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '11b08f93a4494d9a084b0eef52a18b035db266eb480a52843072e1c5f6c03b40'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4054 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratorc7cdfe755077e6bc513ece84c7dec903.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratorc7cdfe755077e6bc513ece84c7dec903.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Npa5piaA%3D%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "df9504e4ab9f559869d0d5a584c2c196d3ef2763840481a21e2e0d36fd76ebbc", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'df9504e4ab9f559869d0d5a584c2c196d3ef2763840481a21e2e0d36fd76ebbc'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4241 AND is_active);
UPDATE source_observation SET canonical_url = 'https://kpcode.kp.gov.pk/uploads/The_Khyber_Pakhtunkhwa_Enforcement_of_Womens_Property_Rights_Act_2019.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://kpcode.kp.gov.pk/uploads/The_Khyber_Pakhtunkhwa_Enforcement_of_Womens_Property_Rights_Act_2019.pdf", "detail_url": "https://kpcode.kp.gov.pk/homepage/lawDetails/1420", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "5ff04daf60e1c973e752509fd281e6c89de9fabf711401021cd878d55ec8d448", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '5ff04daf60e1c973e752509fd281e6c89de9fabf711401021cd878d55ec8d448'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4256 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratorc66d03456235d55a9e107ca30fd6f14e.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratorc66d03456235d55a9e107ca30fd6f14e.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-cJ6W-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "82e3e305afba6253e9b42f83f40e6501f5ff2e166df947558a87ee61a7bf3ad8", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '82e3e305afba6253e9b42f83f40e6501f5ff2e166df947558a87ee61a7bf3ad8'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4302 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratorf3be1ec8d21dfebb9c5d1733f43cffe6.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratorf3be1ec8d21dfebb9c5d1733f43cffe6.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-bpuUY2Rt-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "f455a5a5e28b91e5748ae24b1e05bdc7a6cce07d706289f82626c91a6fa32259", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'f455a5a5e28b91e5748ae24b1e05bdc7a6cce07d706289f82626c91a6fa32259'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4348 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-institution-servants-medical-attendance-regulations-1967-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-institution-servants-medical-attendance-regulations-1967-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/VW1RZwo~BjI-", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "ad9c614a6e9e267c6d704fbe73707ab28b6b8a020bbb6d25d8dd484cfe615738", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'ad9c614a6e9e267c6d704fbe73707ab28b6b8a020bbb6d25d8dd484cfe615738'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4367 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator8b34b071116ce718a2770908b43282a9.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator8b34b071116ce718a2770908b43282a9.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Fuaps%3D-sg-jjjjjjjjjjjjj", "method": "listing title+year match, official PDF fetched 2026-11-16, sha256 equal to the held blob", "sha256": "360de0007cd3a94a153bbdc2dd2bcdc75c17e8373bbd3823c976fdef3cdf188f", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '360de0007cd3a94a153bbdc2dd2bcdc75c17e8373bbd3823c976fdef3cdf188f'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4597 AND is_active);

UPDATE instrument i SET source_url = o.canonical_url
  FROM source_observation o
 WHERE o.id = i.source_observation_id AND i.is_active AND i.source_url IS NULL AND o.canonical_url IS NOT NULL
   AND o.source_metadata ? 'canonical_url_traced';

SELECT count(*) AS released_without_source_url FROM v_release_instrument WHERE source_url IS NULL;

COMMIT;
