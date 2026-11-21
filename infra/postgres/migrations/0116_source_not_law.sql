-- A landed file that is not law: a draft published for consultation, a regulator's circular, a press release
-- (DECISION-LOG D-113, 21 Nov 2026).
--
-- The September source drops (FBR, SECP) filed drafts beside the notifications that enacted them. A draft prints
-- "The following draft of the X Regulations ... proposed to be made ... objections or suggestions ... within fourteen
-- days". Its title rarely says so, so title filters cannot catch it before landing; its own first page does, and a
-- sweep of the 251 laws landed that day found 21: 19 drafts, one SECP circular, one press release.
--
-- None is law, so none may be released. A hold (an extraction_verification review row) would be untruthful -- these
-- are not waiting for repair -- and leaves them counted as held. source_non_authoritative_copy (0065) cannot carry
-- them either: it names an authoritative counterpart, and for most drafts the corpus holds none.
--
-- So the fact is recorded as itself: an append-only row per landed observation, with the kind, the verbatim printed
-- words that make it not law and their source block. The latest row per observation wins; a withdrawal is a row with
-- assertion 'withdrawn'. v_release_instrument leaves out every instrument whose observation carries a standing row.
-- Nothing is deleted: the file, its blocks and its tree stay as evidence.
--
-- REVERSAL: withdraw the rows (the instruments return to the release on the next read); dropping the table needs
-- 0070's view first.
-- Governing contract: docs/02 §8 (release gates), docs/03 §9 (append-only evidence), INV-5.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE source_not_law (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    document_id           bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    kind                  text NOT NULL CHECK (kind IN ('draft_for_consultation', 'regulator_circular',
                                                        'press_release')),
    assertion             text NOT NULL CHECK (assertion IN ('excluded', 'withdrawn')),
    quote                 text CHECK (assertion = 'withdrawn' OR btrim(coalesce(quote, '')) <> ''),
    source_block_id       bigint REFERENCES text_block(id) ON DELETE RESTRICT,
    source_page           integer,
    method                text NOT NULL CHECK (btrim(method) <> ''),
    evidence              jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    recorded_by           text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    CHECK (assertion = 'withdrawn' OR source_block_id IS NOT NULL)
);
CREATE INDEX source_not_law_observation ON source_not_law(source_observation_id, recorded_at DESC, id DESC);

CREATE VIEW v_source_not_law_current AS
SELECT DISTINCT ON (source_observation_id) *
  FROM source_not_law
 ORDER BY source_observation_id, recorded_at DESC, id DESC;

-- 0070's definition, with one condition added: no standing not-law row on the instrument's observation.
CREATE OR REPLACE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND q.overall_outcome='passed'
   AND EXISTS (
       SELECT 1 FROM segmentation_run r
        WHERE r.instrument_id=i.id AND r.outcome='segmented')
   AND NOT EXISTS (
       SELECT 1 FROM v_toc_gap_pending t WHERE t.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_structural_adjudication_pending s
        WHERE s.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_boundary_adjudication_pending b
        WHERE b.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_source_not_law_current n
        WHERE n.source_observation_id=i.source_observation_id AND n.assertion='excluded');

COMMENT ON TABLE source_not_law IS
  'Append-only: a landed observation that is not law (a draft for consultation, a regulator circular, a press '
  'release), with the printed words that show it and their block. The latest row per observation stands; '
  'v_release_instrument leaves out instruments of observations whose standing row is excluded. Migration 0116, D-113.';

COMMIT;
