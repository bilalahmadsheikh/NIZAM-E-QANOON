-- Acquisition exceptions: the 26 Acts the Gilgit-Baltistan Assembly lists (lead, 14 Nov 2026).
--
-- GB was taken into scope on 14 Nov 2026 (docs/02 §2.2). tools/acquire/record_gb_assembly_acts.py catalogued each Act
-- listed at https://gbassembly.gbit.gov.pk/pages/acts as a failed source_observation (pk-gb, recrawl-2026-11-14/4), and
-- nizam.workers.recover_acquisition retried each. Every attempt that reached the server returned HTTP 404 for the
-- PDF the listing links (one first attempt was a network error, retried to a 404). Probed the same day, outside the
-- ledger: the same paths space-encoded, colon-encoded and under /storage/ also 404; gilgitbaltistan.gov.pk refuses
-- connections; gba.gov.pk presents a certificate that fails verification. No other official copy was found.
--
-- Reason 'catalogued_url_no_longer_resolves' (0048): the request completed and the document was not there. It does not
-- claim the Acts were withdrawn. A later fetch that succeeds lands the file through the ordinary recovery worker and
-- supersedes the exception. Append-only; idempotent (an observation already excepted is skipped).

BEGIN;

INSERT INTO acquisition_exception (source_observation_id, reason, attempts_considered, first_attempt_at,
                                   last_attempt_at, observed_error, evidence, asserted_by)
SELECT o.id, 'catalogued_url_no_longer_resolves', count(a.id), min(a.attempted_at), max(a.attempted_at),
       'HTTP 404 on the PDF the GB Assembly acts listing links',
       jsonb_build_object(
         'title', o.source_metadata->>'title', 'number', o.source_metadata->>'number',
         'source_id', o.source_id, 'canonical_url', o.canonical_url, 'http_status', 404,
         'attempt_ids', jsonb_agg(a.id ORDER BY a.id),
         'attempt_outcomes', jsonb_agg(DISTINCT a.outcome),
         'site_probe_2026_11_14', 'listing page 200; linked PDFs 404 as linked, %20-encoded, %3A-encoded and under '
                                  '/storage/; gilgitbaltistan.gov.pk connect timeout; gba.gov.pk certificate verification fails',
         'recovery_path', 'catalogue re-discovery for this item, then the ordinary recovery worker',
         'review_method', 'acquisition_attempt ledger read in full; no fetch was performed by this declaration',
         'reviewer_type', 'assistant'),
       'lead/claude-2026-11-14'
  FROM source_observation o
  JOIN acquisition_attempt a ON a.source_observation_id = o.id
 WHERE o.source_id = 'pk-gb' AND o.scraper_version = 'recrawl-2026-11-14/4' AND o.outcome <> 'landed'
   AND NOT EXISTS (SELECT 1 FROM v_acquisition_exception_latest e WHERE e.source_observation_id = o.id)
 GROUP BY o.id
HAVING bool_or(a.http_status = 404) AND NOT bool_or(a.outcome = 'recovered')
   AND (array_agg(a.http_status ORDER BY a.id DESC))[1] = 404;

SELECT count(*) AS gb_excepted FROM v_acquisition_exception_latest e JOIN source_observation o ON o.id = e.source_observation_id
 WHERE o.source_id = 'pk-gb';
SELECT count(*) AS unresolved FROM v_acquisition_unresolved;

COMMIT;
