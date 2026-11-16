-- The 'empowers' edge (docs/03b §1.1): a subordinate instrument linked to the law, and the section, it was made under;
-- and a later instrument's 'in supersession of' clause recorded as supersession.
--
-- docs/03b: "empowers -- A section authorises rules, regulations or an SRO to be made under it ... The highest-value
-- edge. The Act says 'as prescribed'; the prescription lives in delegated legislation." Measured 16 Nov 2026: 1,278 of
-- 2,600 released rules, regulations, orders and notifications print their enacting formula -- 'In exercise of the
-- powers conferred by section 25 of the Balochistan Civil Servants Act, 1974 ...' -- and 19 print 'in supersession
-- of the ... Rules, 1974'. tools/record_delegation.py reads both from the instrument's own text.
--
-- delegation_record (append-only, source-keyed like 0066/0067/0070 so a replay does not orphan it): the delegated
-- expression, the enabling expression, the enabling section as printed ('25'; every section the formula names is in
-- evidence), the clause verbatim and its source block. A row is written only when the named law and year resolve to
-- exactly one released instrument (same jurisdiction first, else the federation). v_delegation_current resolves the
-- current instruments and the enabling section's provision; legal_edge gains an 'empowers' edge from that provision
-- (or the instrument, when the section does not resolve) to the delegated instrument.
--
-- instrument_supersession (0067) gains basis 'supersession_clause': the LATER instrument's own text supersedes the
-- earlier one ('in supersession of the West Pakistan Factories Rules, 1962'); 'in partial supersession' is never
-- recorded. v_instrument_currency reports it as 'superseded_by_later_instrument' (not_current from the superseding
-- instrument's enactment or year) -- the same treatment 0088 gives an Ordinance replaced by an Act.
--
-- REVERSAL: drop v_delegation_current, delegation_record and their functions; restore 0079's legal_edge, 0067's basis
-- check and 0088's v_instrument_currency.
-- Governing contract: docs/03b §1.1 (empowers), §2 (superseded_by); docs/03 §9; migrations 0067, 0079, 0088.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE delegation_record (
    id                            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    delegated_observation_id      bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    delegated_expression_ordinal  smallint NOT NULL CHECK (delegated_expression_ordinal >= 0),
    enabling_observation_id       bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    enabling_expression_ordinal   smallint NOT NULL CHECK (enabling_expression_ordinal >= 0),
    enabling_section_label        text CHECK (enabling_section_label IS NULL OR btrim(enabling_section_label) <> ''),
    clause_text                   text NOT NULL CHECK (btrim(clause_text) <> ''),
    source_block_id               bigint NOT NULL CHECK (source_block_id > 0),
    assertion                     text NOT NULL CHECK (assertion IN ('recorded', 'withdrawn')),
    method                        text NOT NULL CHECK (btrim(method) <> ''),
    evidence                      jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                         AND btrim(evidence->>'reviewer_type') <> '', false)),
    recorded_by                   text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    CHECK ((delegated_observation_id, delegated_expression_ordinal)
           <> (enabling_observation_id, enabling_expression_ordinal))
);

CREATE INDEX delegation_record_key
    ON delegation_record (delegated_observation_id, delegated_expression_ordinal, enabling_observation_id,
                          enabling_expression_ordinal, recorded_at DESC, id DESC);

CREATE FUNCTION check_delegation_record() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'delegation_record is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.delegated_observation_id AND outcome = 'landed')
       OR NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.enabling_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'both observations must have landed';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM text_block t JOIN document d ON d.id = t.document_id
                     JOIN source_observation o ON o.sha256 = d.sha256
                    WHERE t.id = NEW.source_block_id AND o.id = NEW.delegated_observation_id) THEN
        RAISE EXCEPTION 'block % is not a block of observation %', NEW.source_block_id, NEW.delegated_observation_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER delegation_record_guard
BEFORE INSERT OR UPDATE OR DELETE ON delegation_record
FOR EACH ROW EXECUTE FUNCTION check_delegation_record();

CREATE TRIGGER delegation_record_no_truncate
BEFORE TRUNCATE ON delegation_record
FOR EACH STATEMENT EXECUTE FUNCTION check_delegation_record();

CREATE VIEW v_delegation_current AS
WITH latest AS (
    SELECT DISTINCT ON (delegated_observation_id, delegated_expression_ordinal, enabling_observation_id,
                        enabling_expression_ordinal) *
      FROM delegation_record
     ORDER BY delegated_observation_id, delegated_expression_ordinal, enabling_observation_id,
              enabling_expression_ordinal, recorded_at DESC, id DESC)
SELECT l.*, d.id AS delegated_instrument_id, e.id AS enabling_instrument_id, sec.id AS enabling_provision_id
  FROM latest l
  JOIN instrument d ON d.source_observation_id = l.delegated_observation_id
                   AND d.expression_ordinal = l.delegated_expression_ordinal AND d.is_active AND d.duplicate_of IS NULL
  JOIN instrument e ON e.source_observation_id = l.enabling_observation_id
                   AND e.expression_ordinal = l.enabling_expression_ordinal AND e.is_active AND e.duplicate_of IS NULL
  LEFT JOIN LATERAL (
       SELECT p.id FROM provision p
        WHERE l.enabling_section_label IS NOT NULL AND p.instrument_id = e.id AND p.is_active
          AND p.label = l.enabling_section_label AND p.kind::text IN ('section', 'article')
        ORDER BY nlevel(p.path), p.ordinal LIMIT 1) sec ON true
 WHERE l.assertion = 'recorded';

COMMENT ON TABLE delegation_record IS
  'Append-only: a subordinate instrument and the law (and section) its printed enacting formula says it was made '
  'under (docs/03b empowers). Migration 0089.';

ALTER TABLE instrument_supersession DROP CONSTRAINT IF EXISTS instrument_supersession_basis_check;
DO $$
DECLARE c record;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint WHERE conrelid = 'instrument_supersession'::regclass AND contype = 'c'
              AND pg_get_constraintdef(oid) ~ 'same_title_successor_act' LOOP
        EXECUTE format('ALTER TABLE instrument_supersession DROP CONSTRAINT %I', c.conname);
    END LOOP;
END $$;
ALTER TABLE instrument_supersession ADD CONSTRAINT instrument_supersession_basis
    CHECK (basis IN ('act_text_names_ordinance', 'same_title_successor_act', 'supersession_clause'));

CREATE OR REPLACE VIEW legal_edge AS
SELECT 'amends'::edge_kind                                    AS kind,
       NULL::uuid                                             AS src_provision,
       a.amending_instrument_id                               AS src_instrument,
       a.target_provision_id                                  AS dst_provision,
       CASE WHEN a.target_provision_id IS NULL THEN a.amended_instrument_id END AS dst_instrument,
       NULL::uuid                                             AS dst_judgment,
       NULL::uuid                                             AS dst_schedule,
       CASE WHEN a.effective_from IS NOT NULL THEN daterange(a.effective_from, NULL, '[)')
            ELSE '(,)'::daterange END                          AS validity,
       a.footnote_text                                        AS raw_text,
       1.0::real                                              AS confidence,
       'grammar'::text                                        AS method,
       NULL::text                                             AS verified_by,
       'amendment_reference'::text                            AS source_relation,
       a.id                                                   AS source_id
  FROM v_amendment_reference_current a
 WHERE a.amending_instrument_id IS NOT NULL
UNION ALL
SELECT 'repeals'::edge_kind,
       src.id,
       CASE WHEN src.id IS NULL THEN r.repealing_instrument_id END,
       NULL::uuid,
       r.repealed_instrument_id,
       NULL::uuid,
       NULL::uuid,
       CASE WHEN r.repealed_on IS NOT NULL THEN daterange(r.repealed_on, NULL, '[)') ELSE '(,)'::daterange END,
       r.clause_text,
       1.0::real,
       'grammar'::text,
       NULL::text,
       'statutory_repeal'::text,
       r.id
  FROM v_statutory_repeal_current r
  LEFT JOIN LATERAL (
       SELECT p.id
         FROM provision p
        WHERE r.repealing_relative_path IS NOT NULL
          AND p.instrument_id = r.repealing_instrument_id AND p.is_active
          AND nlevel(p.path) > nlevel(r.repealing_relative_path::ltree)
          AND subpath(p.path, nlevel(p.path) - nlevel(r.repealing_relative_path::ltree)) = r.repealing_relative_path::ltree
        LIMIT 1) src ON true
 WHERE r.repealing_instrument_id IS NOT NULL AND r.repealed_instrument_id IS NOT NULL
UNION ALL
-- 0089: the enabling section (or law) empowers the delegated instrument
SELECT 'empowers'::edge_kind,
       d.enabling_provision_id,
       CASE WHEN d.enabling_provision_id IS NULL THEN d.enabling_instrument_id END,
       NULL::uuid,
       d.delegated_instrument_id,
       NULL::uuid,
       NULL::uuid,
       '(,)'::daterange,
       d.clause_text,
       1.0::real,
       'grammar'::text,
       NULL::text,
       'delegation_record'::text,
       d.id
  FROM v_delegation_current d;

CREATE OR REPLACE VIEW v_instrument_currency AS
SELECT i.id AS instrument_id,
       c.currency,
       c.reason,
       c.not_current_from
  FROM v_release_instrument i
  LEFT JOIN v_instrument_metadata_current st ON st.instrument_id = i.id AND st.field = 'status'
  LEFT JOIN instrument rep ON rep.id = i.repealed_by_id
  LEFT JOIN LATERAL (SELECT s.superseding_instrument_id, s.basis FROM v_instrument_supersession_current s
                      WHERE s.superseded_instrument_id = i.id ORDER BY s.recorded_at, s.id LIMIT 1) sup ON true
  LEFT JOIN instrument succ ON succ.id = sup.superseding_instrument_id
  LEFT JOIN source_observation o ON o.id = i.source_observation_id
  CROSS JOIN LATERAL (SELECT
      CASE WHEN i.status = 'repealed' THEN 'not_current'
           WHEN i.status = 'lapsed' THEN 'not_current'
           WHEN i.repealed_by_id IS NOT NULL THEN 'not_current'
           WHEN sup.superseding_instrument_id IS NOT NULL THEN 'not_current'
           WHEN st.basis = 'portal_repeal_note' THEN 'not_current'
           WHEN cardinality(territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                             i.source_url)) = 0 THEN 'historical'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN 'historical'
           WHEN i.status = 'in_force' THEN 'current'
           ELSE 'current_unverified' END AS currency,
      CASE WHEN i.status = 'repealed' THEN 'repealed'
           WHEN i.status = 'lapsed' THEN 'ordinance_lapsed'
           WHEN i.repealed_by_id IS NOT NULL THEN 'repealed_date_not_established'
           WHEN sup.basis = 'supersession_clause' THEN 'superseded_by_later_instrument'
           WHEN sup.superseding_instrument_id IS NOT NULL THEN 'replaced_by_later_act'
           WHEN st.basis = 'portal_repeal_note' THEN 'official_portal_marks_repealed'
           WHEN cardinality(territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                             i.source_url)) = 0 THEN 'law_of_a_place_outside_pakistan'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN 'pre_1947_text_not_in_official_consolidation'
           WHEN i.status = 'in_force' THEN st.basis
           ELSE coalesce(st.basis, 'not_assessed') END AS reason,
      CASE WHEN i.status = 'repealed' THEN i.repealed_on
           WHEN i.status = 'lapsed' THEN ordinance_latest_lapse(i.jurisdiction::text, i.enacted_on, i.year)
           WHEN i.repealed_by_id IS NOT NULL
                THEN coalesce(rep.commenced_on, rep.enacted_on, make_date(rep.year, 1, 1))
           WHEN sup.superseding_instrument_id IS NOT NULL
                THEN coalesce(succ.enacted_on, make_date(succ.year, 1, 1))
           WHEN st.basis = 'portal_repeal_note' THEN coalesce(o.fetched_at::date, current_date)
           WHEN cardinality(territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                             i.source_url)) = 0 THEN DATE '1947-08-15'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN DATE '1947-08-15'
           END AS not_current_from) c;

COMMIT;
