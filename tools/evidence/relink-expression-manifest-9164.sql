-- Doc 9164 (The North-West Border Military Police Act, 1904): point the active
-- expression manifest at the live instrument.
--
-- What happened. The manifest 4dabfd19 was written on 30 Oct 2026 14:28 for
-- instrument 70917c82. At 18:36 the same day that instrument was retired and
-- two minutes later the document was re-segmented through the single-expression
-- path (instrument 6b1e29bd; that path sets no supersedes link and writes no
-- manifest), so the active manifest kept naming a retired tree. The tree is the
-- same expression: same observation (12424), ordinal 0, the same 227-block
-- span 2385094..2385320.
--
-- What this does. Append-only, as legal_write.save_many and
-- tools/publish_held_expression.py do it: retire the old manifest, insert a
-- superseding one whose materialized_instrument_id is the live instrument, copy
-- its spans. Nothing is deleted. The new manifest's evidence is the old
-- evidence plus a `relink` entry stating exactly this, and no printed text,
-- identity or span is asserted that the old manifest did not already carry.
--
-- Guard: every precondition is checked and the script aborts otherwise.

BEGIN;

DO $$
DECLARE
    old_m   constant uuid := '4dabfd19-4a3c-432f-8865-dd570bd19823';
    old_i   constant uuid := '70917c82-9a9f-4ac9-a9ac-68990605d770';
    live_i  constant uuid := '6b1e29bd-79eb-4c96-85da-9d0f329cac92';
    m       instrument_expression_manifest%ROWTYPE;
    li      instrument%ROWTYPE;
    new_m   uuid;
BEGIN
    SELECT * INTO m FROM instrument_expression_manifest WHERE id = old_m FOR UPDATE;
    IF NOT FOUND OR NOT m.is_active OR m.materialized_instrument_id IS DISTINCT FROM old_i THEN
        RAISE EXCEPTION 'manifest % is not the active manifest of retired instrument %', old_m, old_i;
    END IF;
    IF m.historical_validity IS NOT NULL THEN
        RAISE EXCEPTION 'a historical expression is not relinked by this script';
    END IF;
    SELECT * INTO li FROM instrument WHERE id = live_i;
    IF NOT FOUND OR NOT li.is_active
       OR li.created_at < (SELECT retired_at FROM instrument WHERE id = old_i)
       OR li.document_id <> m.document_id
       OR li.source_observation_id <> m.source_observation_id
       OR li.expression_ordinal <> m.expression_ordinal
       OR li.source_start_block_id <> m.start_block_id
       OR li.source_end_block_id <> m.end_block_id THEN
        RAISE EXCEPTION 'live instrument % is not the same expression as manifest %', live_i, old_m;
    END IF;
    IF EXISTS (SELECT 1 FROM instrument_expression_manifest
                WHERE materialized_instrument_id = live_i AND is_active) THEN
        RAISE EXCEPTION 'live instrument already has an active manifest';
    END IF;

    UPDATE instrument_expression_manifest SET is_active = false, retired_at = now() WHERE id = old_m;

    INSERT INTO instrument_expression_manifest
        (source_observation_id, document_id, expression_ordinal, expression_role,
         start_block_id, end_block_id, detected_title, detected_kind, detected_year,
         detected_number, review_basis, method, evidence, materialized_instrument_id,
         supersedes_manifest_id, historical_validity, current_source_observation_id,
         current_expression_ordinal)
    VALUES
        (m.source_observation_id, m.document_id, m.expression_ordinal, m.expression_role,
         m.start_block_id, m.end_block_id, m.detected_title, m.detected_kind, m.detected_year,
         m.detected_number, m.review_basis, m.method,
         m.evidence || jsonb_build_object('relink', jsonb_build_object(
             'relinked_on', '2026-11-11',
             'from_instrument_id', old_i,
             'to_instrument_id', live_i,
             'reason', 'the document was re-segmented through the single-expression path after the first instrument was retired, and that path writes no manifest; the expression, observation and block span are unchanged',
             'script', 'tools/evidence/relink-expression-manifest-9164.sql')),
         live_i, old_m, m.historical_validity, m.current_source_observation_id,
         m.current_expression_ordinal)
    RETURNING id INTO new_m;

    INSERT INTO instrument_expression_span (manifest_id, span_ordinal, start_block_id, end_block_id)
    SELECT new_m, span_ordinal, start_block_id, end_block_id
      FROM instrument_expression_span WHERE manifest_id = old_m;

    IF (SELECT count(*) FROM instrument_expression_span WHERE manifest_id = new_m)
       <> (SELECT count(*) FROM instrument_expression_span WHERE manifest_id = old_m) THEN
        RAISE EXCEPTION 'span copy is incomplete';
    END IF;
    IF EXISTS (SELECT 1 FROM instrument_expression_manifest x JOIN instrument i ON i.id = x.materialized_instrument_id
                WHERE x.is_active AND NOT i.is_active) THEN
        RAISE EXCEPTION 'an active manifest still names a retired instrument';
    END IF;
END $$;

COMMIT;
