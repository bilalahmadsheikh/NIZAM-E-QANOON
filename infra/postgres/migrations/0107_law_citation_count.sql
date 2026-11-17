-- How often each released law is relied on by the rest of the corpus (18 Nov 2026, DECISION-LOG D-075).
--
-- The library lists laws by jurisdiction, kind and topic. Alphabetical order put the Pakistan Penal Code among
-- hundreds of minor Acts. Nizam holds no usage data, and invents none; what it does hold is the law itself, and the
-- laws other laws cite are the ones practice turns on. tools/measure_law_citations.py reads every released law's
-- text once, finds citations by title ('the Code of Criminal Procedure, 1898', 'the Pakistan Penal Code (XLV of
-- 1860)'), resolves each to the cited law, and records here how many OTHER laws cite it -- plus the recorded
-- amends / repeals / empowers edges into it (legal_edge). A derived measure, replaced whole on each run.
--
-- Keyed by (document_id, expression_ordinal): stable across replays, which regenerate instrument ids.
-- REVERSAL: DROP TABLE law_citation_count.
-- Governing contract: docs/07 (catalogue endpoint); migration 0079/0089 (legal_edge).

CREATE TABLE IF NOT EXISTS law_citation_count (
    document_id         bigint   NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    expression_ordinal  smallint NOT NULL,
    cited_by_laws       integer  NOT NULL CHECK (cited_by_laws >= 0),
    citations           integer  NOT NULL CHECK (citations >= 0),
    edges_in            integer  NOT NULL CHECK (edges_in >= 0),
    measured_at         timestamptz NOT NULL DEFAULT now(),
    method              text     NOT NULL,
    PRIMARY KEY (document_id, expression_ordinal)
);

COMMENT ON TABLE law_citation_count IS
  'Derived: how many other released laws cite this law by title (cited_by_laws), the citation count, and recorded '
  'legal_edge links into it. Written whole by tools/measure_law_citations.py; a ranking signal, never law (D-075).';

-- Headings and marginal notes are what a reader searches when they look for a law by its subject ('robbery',
-- 'bail', 'rent'): a small, precise surface (131,745 served units carry one). Full-text retrieval over provision
-- text is L3's BM25 index, not this.
CREATE INDEX IF NOT EXISTS provision_heading_fts ON provision
  USING gin (to_tsvector('english', coalesce(heading, '') || ' ' || coalesce(marginal_note, '')))
  WHERE is_active AND (heading IS NOT NULL OR marginal_note IS NOT NULL);
