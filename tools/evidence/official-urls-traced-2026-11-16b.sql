-- Official URLs for the last 10 released laws with none (lead, 16 Nov 2026; follows
-- official-urls-traced-2026-11-16.sql). Same rule: only a NULL canonical_url is filled, and only with a URL proven to
-- serve THIS file -- 4 by a live fetch whose sha256 equals the held blob, 6 Sindh laws by the August 2026 scrape
-- manifest, which recorded the pdf_url it downloaded these exact bytes (same sha256) from. Idempotent.

BEGIN;

UPDATE source_observation SET canonical_url = 'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-16-000015.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-16-000015.pdf", "detail_url": null, "method": "the August 2026 scrape manifest (sindh_code/manifest.csv) records this pdf_url with this sha256; the portal re-generates PDFs per download (PDFsharp) and answered 503 on 2026-11-16", "sha256": "e675080196bbc2aa40279c30b9befbcfcf81f0550bed7045d18edcc79b08dfb6", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'e675080196bbc2aa40279c30b9befbcfcf81f0550bed7045d18edcc79b08dfb6'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 762 AND is_active);
UPDATE source_observation SET canonical_url = 'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000838.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000838.pdf", "detail_url": null, "method": "the August 2026 scrape manifest (sindh_code/manifest.csv) records this pdf_url with this sha256; the portal re-generates PDFs per download (PDFsharp) and answered 503 on 2026-11-16", "sha256": "c2607eca8efc143b6cbad966846dfc21d034e7d709ae22350be4e15ac470d0ad", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'c2607eca8efc143b6cbad966846dfc21d034e7d709ae22350be4e15ac470d0ad'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 805 AND is_active);
UPDATE source_observation SET canonical_url = 'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-16-000185.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-16-000185.pdf", "detail_url": null, "method": "the August 2026 scrape manifest (sindh_code/manifest.csv) records this pdf_url with this sha256; the portal re-generates PDFs per download (PDFsharp) and answered 503 on 2026-11-16", "sha256": "deb97a5a66ec4898c12cfd6996b419b62c000f118d3011d465ae5cc2adbed647", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'deb97a5a66ec4898c12cfd6996b419b62c000f118d3011d465ae5cc2adbed647'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 1047 AND is_active);
UPDATE source_observation SET canonical_url = 'http://balochistancode.gob.pk/lawdir/c08cbfe6-15cf-419f-9849-b47ac660231d.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "http://balochistancode.gob.pk/lawdir/c08cbfe6-15cf-419f-9849-b47ac660231d.pdf", "detail_url": "http://balochistancode.gob.pk/Document.aspx?wise=opendoc&docid=1916&docc=1807", "method": "listing/manifest pdf_url fetched 2026-11-16, sha256 equal to the held blob", "sha256": "2bc2395d737c890ed027c817ac57805c88904b07c4fc4e37d493d7fedc8d7b3e", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '2bc2395d737c890ed027c817ac57805c88904b07c4fc4e37d493d7fedc8d7b3e'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 1477 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administrator36daa6c68c69913952887282f5f65820.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administrator36daa6c68c69913952887282f5f65820.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Npa5toaw%3D%3D-sg-jjjjjjjjjjjjj", "method": "Pakistan Code ''Latest Ordinances'' page (KmTY5e.php) link fetched 2026-11-16, sha256 equal to the held blob", "sha256": "b01ea4a00e2495d4862f2676351a10cdec03aeed3eb20ec4cecd71566c3d2ade", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'b01ea4a00e2495d4862f2676351a10cdec03aeed3eb20ec4cecd71566c3d2ade'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 2772 AND is_active);
UPDATE source_observation SET canonical_url = 'https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-financial-accounting-rules-1966-pdf.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://punjabcode.punjab.gov.pk/uploads/articles/provincial-employees-social-security-financial-accounting-rules-1966-pdf.pdf", "detail_url": "https://punjabcode.punjab.gov.pk/en/show_article/V29SZFZjU2Y-", "method": "listing/manifest pdf_url fetched 2026-11-16, sha256 equal to the held blob", "sha256": "c9b0402cf1f0dc79e664eb53674fd732e0272cfcba4edaeb5c5e2a80f6345a8c", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = 'c9b0402cf1f0dc79e664eb53674fd732e0272cfcba4edaeb5c5e2a80f6345a8c'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3711 AND is_active);
UPDATE source_observation SET canonical_url = 'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000637.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000637.pdf", "detail_url": null, "method": "the August 2026 scrape manifest (sindh_code/manifest.csv) records this pdf_url with this sha256; the portal re-generates PDFs per download (PDFsharp) and answered 503 on 2026-11-16", "sha256": "8b28ffb27fd893943b1a36ec2ecaab03b9e42bf650fa92e062e54d2eb95f6689", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '8b28ffb27fd893943b1a36ec2ecaab03b9e42bf650fa92e062e54d2eb95f6689'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 3859 AND is_active);
UPDATE source_observation SET canonical_url = 'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-23-000102.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-23-000102.pdf", "detail_url": null, "method": "the August 2026 scrape manifest (sindh_code/manifest.csv) records this pdf_url with this sha256; the portal re-generates PDFs per download (PDFsharp) and answered 503 on 2026-11-16", "sha256": "9aa68c8e4ff735e2f8a23ff269ad879da3e2e2789cea2ab6c1f805104c0fdf4a", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '9aa68c8e4ff735e2f8a23ff269ad879da3e2e2789cea2ab6c1f805104c0fdf4a'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4375 AND is_active);
UPDATE source_observation SET canonical_url = 'https://pakistancode.gov.pk/pdffiles/administratora0d32004cee3136e0d57987714fe6c7b.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://pakistancode.gov.pk/pdffiles/administratora0d32004cee3136e0d57987714fe6c7b.pdf", "detail_url": "https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Npa5tnbw%3D%3D-sg-jjjjjjjjjjjjj", "method": "Pakistan Code ''Latest Ordinances'' page (KmTY5e.php) link fetched 2026-11-16, sha256 equal to the held blob", "sha256": "0a8b926e1c6417563ab2afd0c5dc360edec2a4081a8b52be6e7b491ed4033efa", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '0a8b926e1c6417563ab2afd0c5dc360edec2a4081a8b52be6e7b491ed4033efa'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4510 AND is_active);
UPDATE source_observation SET canonical_url = 'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-21-000029.pdf',
       source_metadata = source_metadata || jsonb_build_object('canonical_url_traced', '{"url": "https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-21-000029.pdf", "detail_url": null, "method": "the August 2026 scrape manifest (sindh_code/manifest.csv) records this pdf_url with this sha256; the portal re-generates PDFs per download (PDFsharp) and answered 503 on 2026-11-16", "sha256": "39f57db13ce26a74cb8370e18124e268156ec9570bcb2a047547d1e06d0a1c95", "traced_by": "claude 2026-11-16"}'::jsonb)
 WHERE canonical_url IS NULL AND sha256 = '39f57db13ce26a74cb8370e18124e268156ec9570bcb2a047547d1e06d0a1c95'
   AND id IN (SELECT source_observation_id FROM instrument WHERE document_id = 4568 AND is_active);

UPDATE instrument i SET source_url = o.canonical_url
  FROM source_observation o
 WHERE o.id = i.source_observation_id AND i.is_active AND i.source_url IS NULL AND o.canonical_url IS NOT NULL
   AND o.source_metadata ? 'canonical_url_traced';

SELECT count(*) AS released_without_source_url FROM v_release_instrument WHERE source_url IS NULL;

COMMIT;
