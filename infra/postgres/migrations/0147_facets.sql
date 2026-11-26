-- 0147  Facets, first slice: a versioned vocabulary and subject_matter (DECISION-LOG D-163; docs/03b §2.1, §6.1,
--       §8). jurisdiction and instrument_type are columns already (instrument.jurisdiction, .kind) and life_stage is
--       read as at a date through operative_provision (status, currency): they are not copied here, where they would
--       go stale. subject_matter is new information: assigned by rule where the short title decides (§8: "rule where
--       the short title decides; classifier otherwise"), every value tied to the vocabulary version that produced it.
--
--  * taxonomy_version: the permitted vocabulary per facet and version (§8), with its rationale.
--  * instrument_facet: DERIVED (nizam.workers.facets), one row per instrument, facet and value (§6.1).
--  * judgment_subject: DERIVED, a judgment's subjects read from the laws it cites (proposed here, D-163: docs/03b
--    defines no judgment facet): the subjects of the resolved statute citations, weighted by role, a subject kept
--    when it carries at least a third of the weight. It lets precedent be filtered by area ("family law").

BEGIN;

CREATE TABLE IF NOT EXISTS taxonomy_version (
  facet        text NOT NULL,
  version      integer NOT NULL CHECK (version > 0),
  vocabulary   jsonb NOT NULL,                -- the permitted values at this version
  released_on  date NOT NULL,
  rationale    text NOT NULL,
  PRIMARY KEY (facet, version)
);

CREATE TABLE IF NOT EXISTS instrument_facet (
  instrument_id uuid NOT NULL REFERENCES instrument (id) ON DELETE CASCADE,
  facet         text NOT NULL,
  value         text NOT NULL,
  taxonomy_ver  integer NOT NULL,
  method        text NOT NULL CHECK (method IN ('title_rule', 'classifier', 'human')),
  evidence      text,                          -- the words that decided it (a title rule's match)
  builder       text NOT NULL,
  PRIMARY KEY (instrument_id, facet, value),
  FOREIGN KEY (facet, taxonomy_ver) REFERENCES taxonomy_version (facet, version)
);
CREATE INDEX IF NOT EXISTS ix_instrument_facet_value ON instrument_facet (facet, value);

CREATE TABLE IF NOT EXISTS judgment_subject (
  judgment_id   uuid NOT NULL,
  decided_on    date NOT NULL,
  value         text NOT NULL,
  share         real NOT NULL CHECK (share > 0 AND share <= 1),
  taxonomy_ver  integer NOT NULL,
  builder       text NOT NULL,
  facet         text NOT NULL DEFAULT 'subject_matter' CHECK (facet = 'subject_matter'),
  PRIMARY KEY (judgment_id, value),
  FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
  FOREIGN KEY (facet, taxonomy_ver) REFERENCES taxonomy_version (facet, version)
);
CREATE INDEX IF NOT EXISTS ix_judgment_subject_value ON judgment_subject (value);

COMMENT ON TABLE instrument_facet IS
  'Instrument facets (D-163; docs/03b §6.1): subject_matter by title rule, each value with its vocabulary version. '
  'Derived by nizam.workers.facets; audit A37.';
COMMENT ON TABLE judgment_subject IS
  'A judgment''s subject areas read from the laws it cites (D-163): share of the role-weighted resolved statute '
  'citations; kept when >= 1/3. Derived by nizam.workers.facets; audit A37.';

COMMIT;
