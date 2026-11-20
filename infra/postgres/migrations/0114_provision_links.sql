-- The links a provision's own words make (docs/03b §1.1): defines, notwithstanding, subject_to, refers_to
-- (20 Nov 2026, DECISION-LOG D-108).
--
-- docs/03b §10: "The contains, refers_to and defines edges -- extractable from the statute text we already have, and
-- they carry most of the retrieval-expansion value." docs/03b §1.1: notwithstanding and subject_to "point at the same
-- provision and mean opposite things", so the phrase is kept as the edge's kind, never flattened.
--
-- These are DERIVED index artefacts, like chunk (0108): computed from released provision versions by one named rule
-- (nizam.storage.linking via nizam.workers.links, `linker`), keyed by the version they were read from, and rebuilt
-- when the release changes -- not evidence. (The source-keyed, append-only pattern of 0079/0089 is for decisions read
-- from a page; a deterministic parse of today's released text is rebuilt instead, as chunks are.) A rule change is a
-- rebuild. Audit A23 asserts the tables are exactly the release under one linker, and that nothing they point at
-- has left it.
--
--   provision_reference   one printed naming of a unit or schedule: its phrase (the edge kind), the label as printed,
--                         the unit it resolves to in the same law, or in another law when the words name one and
--                         exactly one released law matches; unresolved rows are kept (dst NULL), so a gap is counted
--   provision_definition  one word a clause defines: its scope (the whole law; a Part or Chapter, for the units
--                         printed after the definition; or its own unit), whether its words are empty in its node,
--                         and the following siblings that carry a flattened definition's sub-items
--   provision_link_state  every released version the linker has read, with the rule that read it (A23's coverage)
--
-- legal_edge (0079, 0089) gains the four kinds. Operative status is NOT decided here: readers ask
-- operative_provision about the versions at their own as_of and territory (INV-5).
-- REVERSAL: restore 0089's legal_edge; DROP TABLE provision_reference, provision_definition, provision_link_state.
-- Governing contract: docs/03b §1.1, §6, §10; docs/04 §4 (graph expansion), §7 (assembly); migration 0108.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE provision_reference (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    src_version_id     uuid NOT NULL REFERENCES provision_version(id) ON DELETE CASCADE,
    src_provision_id   uuid NOT NULL REFERENCES provision(id) ON DELETE CASCADE,
    src_instrument_id  uuid NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
    kind               edge_kind NOT NULL CHECK (kind IN ('notwithstanding', 'subject_to', 'refers_to')),
    target             text NOT NULL CHECK (target IN ('unit', 'schedule')),
    label              text NOT NULL,          -- the unit label as printed, or the schedule's number ('' : "the Schedule")
    other_law          text,                   -- the other law as printed ('Pakistan Penal Code', 'the Act'); NULL: same law
    dst_unit_id        uuid REFERENCES provision(id) ON DELETE CASCADE,
    dst_instrument_id  uuid REFERENCES instrument(id) ON DELETE CASCADE,
    char_start         integer NOT NULL,
    char_end           integer NOT NULL,
    linker             text NOT NULL,
    CONSTRAINT ck_ref_span CHECK (char_start >= 0 AND char_end > char_start),
    CONSTRAINT ck_ref_dst CHECK (dst_unit_id IS NULL OR dst_instrument_id IS NOT NULL)
);
CREATE INDEX ix_reference_src ON provision_reference (src_provision_id);
CREATE INDEX ix_reference_dst ON provision_reference (dst_unit_id) WHERE dst_unit_id IS NOT NULL;
CREATE INDEX ix_reference_version ON provision_reference (src_version_id);

CREATE TABLE provision_definition (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id          uuid NOT NULL REFERENCES provision_version(id) ON DELETE CASCADE,
    provision_id        uuid NOT NULL REFERENCES provision(id) ON DELETE CASCADE,
    instrument_id       uuid NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
    unit_id             uuid NOT NULL REFERENCES provision(id) ON DELETE CASCADE,   -- the definition's own unit
    term                text NOT NULL CHECK (btrim(term) <> ''),
    term_key            text NOT NULL CHECK (btrim(term_key) <> ''),                -- case and spacing folded
    scope               text NOT NULL CHECK (scope IN ('law', 'division', 'unit')),
    scope_provision_id  uuid REFERENCES provision(id) ON DELETE CASCADE,             -- the Part, Chapter or unit
    after_ordinal       integer,                                                     -- division: units printed after
    empty               boolean NOT NULL,                                            -- 'means--' and nothing in-node
    continuation        uuid[] NOT NULL DEFAULT '{}',                                -- flattened sub-items (siblings)
    linker              text NOT NULL,
    CONSTRAINT ck_def_scope CHECK ((scope = 'law') = (scope_provision_id IS NULL))
);
CREATE INDEX ix_definition_law ON provision_definition (instrument_id, term_key);
CREATE INDEX ix_definition_version ON provision_definition (version_id);

CREATE TABLE provision_link_state (
    version_id  uuid PRIMARY KEY REFERENCES provision_version(id) ON DELETE CASCADE,
    linker      text NOT NULL,
    linked_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE provision_reference IS
  'Derived (D-108): a unit or schedule a released version names, with the phrase as its docs/03b kind. Rebuilt by '
  'nizam.workers.links; A23 asserts it is exactly the release. Never read as law: readers ask operative_provision.';
COMMENT ON TABLE provision_definition IS
  'Derived (D-108): a word a released version defines, with its scope. Rebuilt by nizam.workers.links (A23).';
COMMENT ON TABLE provision_link_state IS
  'Derived (D-108): every released version the linker has read, and the rule that read it (A23 coverage).';

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
  FROM v_delegation_current d
UNION ALL
-- 0114: a unit or schedule a provision names, resolved (unresolved rows are not edges)
SELECT r.kind,
       r.src_provision_id,
       NULL::uuid,
       r.dst_unit_id,
       NULL::uuid,
       NULL::uuid,
       NULL::uuid,
       '(,)'::daterange,
       NULL::text,
       1.0::real,
       'grammar'::text,
       NULL::text,
       'provision_reference'::text,
       r.id
  FROM provision_reference r
 WHERE r.dst_unit_id IS NOT NULL
UNION ALL
-- 0114: a clause defines a word for its scope (a Part, Chapter or unit; or the whole law)
SELECT 'defines'::edge_kind,
       d.provision_id,
       NULL::uuid,
       d.scope_provision_id,
       CASE WHEN d.scope_provision_id IS NULL THEN d.instrument_id END,
       NULL::uuid,
       NULL::uuid,
       '(,)'::daterange,
       d.term,
       1.0::real,
       'grammar'::text,
       NULL::text,
       'provision_definition'::text,
       d.id
  FROM provision_definition d;

COMMIT;
