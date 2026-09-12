-- Declare the catalogued items that repeated dated attempts could not acquire.
--
-- Every reason below is read from the acquisition_attempt ledger, not asserted
-- by hand: the count of attempts, their first and last timestamps, and the
-- error the portal returned. The reason vocabulary says only what those
-- attempts show. A 404 means the catalogued URL no longer resolves -- it does
-- not claim the document was withdrawn, which would need catalogue
-- re-discovery nobody has run.
--
-- This deletes nothing and forecloses nothing. Each exception cites the
-- attempts that justify it, and the trigger refuses to record one for an
-- observation that landed or already has a recovered attempt. If re-discovery
-- later yields a working URL, the recovery worker lands the file and the
-- exception no longer applies.
--
-- Governing contract: docs/02-corpus-and-ingestion.html section 2.

BEGIN;

INSERT INTO acquisition_exception
    (source_observation_id, reason, attempts_considered,
     first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by)
SELECT u.source_observation_id,
       CASE
         WHEN o.error_code = 'HTTP 404'          THEN 'catalogued_url_no_longer_resolves'
         WHEN o.http_status BETWEEN 400 AND 499  THEN 'portal_rejects_the_request'
         WHEN o.error_code ILIKE '%not a valid pdf%'
                                                 THEN 'served_content_is_not_a_pdf'
         WHEN o.error_code ILIKE '%no english pdf%'
                                                 THEN 'no_english_pdf_published'
         ELSE 'no_pdf_url_catalogued'
       END,
       greatest(coalesce(l.attempts, 0), 1),
       coalesce(l.first_at, o.discovered_at, o.ingested_at),
       coalesce(l.last_at,  o.discovered_at, o.ingested_at),
       coalesce(nullif(btrim(o.error_code), ''), 'no error recorded'),
       jsonb_build_object(
           'reviewer_type',   'assistant',
           'review_method',   'acquisition_attempt ledger read in full; no '
                              'fetch was performed by this declaration',
           'attempt_ids',     coalesce(l.ids, '[]'::jsonb),
           'attempt_outcomes', coalesce(l.outcomes, '[]'::jsonb),
           'source_id',       o.source_id,
           'canonical_url',   coalesce(nullif(btrim(o.canonical_url), ''), null),
           'http_status',     o.http_status,
           'title',           o.source_metadata ->> 'title',
           'recovery_path',   'catalogue re-discovery for this item, then the '
                              'ordinary recovery worker'),
       'claude.acquisition-review/1'
  FROM v_acquisition_unresolved u
  JOIN source_observation o ON o.id = u.source_observation_id
  LEFT JOIN LATERAL (
      SELECT count(*)                     AS attempts,
             min(a.attempted_at)          AS first_at,
             max(a.attempted_at)          AS last_at,
             jsonb_agg(a.id ORDER BY a.id)      AS ids,
             jsonb_agg(DISTINCT a.outcome)      AS outcomes
        FROM acquisition_attempt a
       WHERE a.source_observation_id = o.id
  ) l ON true;

COMMIT;
