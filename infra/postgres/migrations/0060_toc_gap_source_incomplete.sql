-- A contents gap closed by a recorded source incompleteness, not by a claim
-- about the Act.
--
-- Migration 0054 records that a LANDED file is a partial copy of its statute.
-- It says nothing to the release gate: `v_toc_gap_pending` reads only
-- `toc_gap_adjudication`, so a contents row whose section the copy does not
-- print stays pending, and the instrument stays unreleased, however well the
-- incompleteness is evidenced. None of the four existing resolutions can close
-- it truthfully:
--
--   absent_in_source   asserts the SOURCE omits the section -- for a short
--                      copy that is a false statement about the Act, which is
--                      exactly the warning 0054 was written to carry;
--   found_elsewhere    the section is not elsewhere in this instrument;
--   other_instrument   it is not another instrument's either;
--   parser_defect      classifies work and closes nothing, by design (0042).
--
-- The case that forced the decision: document 510, the Sind Loans for
-- Agricultural Purposes Act, 1974 (observation 3151). Its printed contents
-- lists "4. Pass Book." between sections 3 and 5; the body on page 3 prints
-- section 3 and then directly section 5, and no page prints section 4, a stub,
-- an omission mark or a footnote. The Act's own s.2(g) defines "pass-book" and
-- s.6 requires entries "in the pass-book of the borrower", so the section
-- exists and this copy does not carry it. No complete copy is in the corpus.
-- The owner decided (decision-review-2026-10-06-b.json, document 510, q1,
-- card 7e28d495...): "release-with-gap" -- release the sections the copy
-- prints, and record the missing one as source incompleteness, shown as not
-- available in this copy rather than as repealed or absent.
--
-- So the vocabulary gains `source_incomplete`, and it is the narrowest thing
-- that says that:
--
--   * it names the 0054 record it rests on (`evidence.source_incompleteness_id`)
--     and is admitted only while that record is the LATEST one for the
--     instrument's own observation, about the same document, and still says
--     `no_complete_copy_acquired`. Where a complete copy IS held, the truncated
--     tree is retired by tools/apply_source_incompleteness.py and its gaps
--     never reach the gate -- releasing it with a gap would publish the
--     shorter of two copies;
--   * it carries the same page-review evidence 0050 requires of
--     `absent_in_source`: a human reading with its render, or an assistant
--     reading that also names the render hashes and says in words what the
--     pages show. A recorded incompleteness is evidence about the FILE; the
--     reading is what ties a particular contents row to it;
--   * it binds an exact printed contents entry. The legacy run-only arm of
--     0043 has no entry behind it and is not admitted.
--
-- Nothing is fabricated: no provision is created for the missing section, and
-- the contents row keeps provision_id NULL. The decision is append-only and
-- supersedable exactly like the other four, and the release view needs no
-- change -- v_toc_gap_pending already keeps only undecided and parser_defect
-- rows. Which gaps were released this way is a view of its own, below, so that
-- L6 can render "not available in this copy" from records rather than infer it.
--
-- Governing contract: docs/02 §5 and §8 (the contents list is source evidence,
-- never operative text; no missing section is fabricated to close a metric).

BEGIN;

ALTER TABLE toc_gap_adjudication
    DROP CONSTRAINT toc_gap_adjudication_resolution_check;

ALTER TABLE toc_gap_adjudication
    ADD CONSTRAINT toc_gap_adjudication_resolution_check CHECK (resolution IN (
        'absent_in_source', 'found_elsewhere', 'parser_defect',
        'other_instrument',
        -- The contents promises a unit this landed copy does not print, and a
        -- standing source_incompleteness record (0054) says no complete copy
        -- has been obtained.
        'source_incomplete'));

ALTER TABLE toc_gap_adjudication
    ADD CONSTRAINT toc_gap_adjudication_source_incomplete_evidence CHECK (
        resolution <> 'source_incomplete'
        OR (toc_entry_id IS NOT NULL
            AND evidence ? 'source_incompleteness_id'
            AND (evidence ->> 'source_incompleteness_id') ~ '^[0-9]+$'
            AND ((evidence @> '{"human_page_review":true}'::jsonb
                  AND evidence ? 'render_artifact')
                 OR (evidence @> '{"assistant_page_review":true}'::jsonb
                     AND evidence ? 'render_artifact'
                     AND evidence ? 'render_sha256'
                     AND evidence ? 'observed'))));

COMMENT ON CONSTRAINT toc_gap_adjudication_source_incomplete_evidence
    ON toc_gap_adjudication IS
  'source_incomplete names its source_incompleteness record, binds an exact '
  'contents entry, and carries a page reading (human with render, or assistant '
  'with render, render hashes and words), as 0050 requires of absent_in_source.';

-- The record must still be the standing truth about THIS instrument's file.
-- A separate function and trigger, so 0043's check_toc_gap_adjudication() --
-- which every resolution passes through -- is not redefined here.
CREATE FUNCTION check_toc_gap_source_incomplete() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    named      bigint;
    rec        source_incompleteness%ROWTYPE;
    latest     bigint;
    built_from bigint;
BEGIN
    -- BEFORE triggers run ahead of CHECK constraints. A missing or malformed
    -- id is left for toc_gap_adjudication_source_incomplete_evidence to
    -- refuse by name rather than failing here on a cast.
    IF coalesce((NEW.evidence ->> 'source_incompleteness_id') ~ '^[0-9]+$',
                false) IS NOT TRUE THEN
        RETURN NEW;
    END IF;
    named := (NEW.evidence ->> 'source_incompleteness_id')::bigint;

    SELECT * INTO rec FROM source_incompleteness WHERE id = named;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'source_incompleteness % does not exist', named;
    END IF;

    SELECT i.source_observation_id INTO built_from
      FROM instrument i WHERE i.id = NEW.instrument_id;
    IF rec.source_observation_id IS DISTINCT FROM built_from THEN
        RAISE EXCEPTION
            'source_incompleteness % is about observation %, but instrument % '
            'was built from observation %',
            named, rec.source_observation_id, NEW.instrument_id, built_from;
    END IF;
    IF rec.document_id IS DISTINCT FROM NEW.document_id THEN
        RAISE EXCEPTION
            'source_incompleteness % is about document %, not document %',
            named, rec.document_id, NEW.document_id;
    END IF;

    SELECT l.id INTO latest
      FROM v_source_incompleteness_latest l
     WHERE l.source_observation_id = rec.source_observation_id;
    IF latest IS DISTINCT FROM rec.id THEN
        RAISE EXCEPTION
            'source_incompleteness % is not the latest record for observation % '
            '(latest is %)', named, rec.source_observation_id, latest;
    END IF;

    IF rec.resolution <> 'no_complete_copy_acquired' THEN
        RAISE EXCEPTION
            'source_incompleteness % says a complete copy is held (document %); '
            'retire this tree with tools/apply_source_incompleteness.py rather '
            'than releasing it with a gap', named, rec.complete_document_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER toc_gap_adjudication_source_incomplete_guard
    BEFORE INSERT ON toc_gap_adjudication
    FOR EACH ROW WHEN (NEW.resolution = 'source_incomplete')
    EXECUTE FUNCTION check_toc_gap_source_incomplete();

-- Contents rows released as "not available in this copy": the standing
-- source_incomplete decision on a live canonical instrument, with the source
-- record it rests on. Read-only; the release gate does not consult it.
CREATE VIEW v_toc_gap_source_incomplete AS
SELECT a.id                       AS adjudication_id,
       a.instrument_id,
       a.document_id,
       a.toc_entry_id,
       a.printed_label,
       e.printed_heading,
       e.source_page              AS contents_page,
       a.source_page              AS reviewed_page,
       s.id                       AS source_incompleteness_id,
       s.source_observation_id,
       s.body_stops_at,
       s.last_attempt_at,
       -- false once a later 0054 record for the observation supersedes the
       -- one this decision named: re-read and re-record against the new one.
       (l.id = s.id)              AS source_record_current,
       a.decided_by,
       a.decided_at
  FROM v_toc_gap_adjudication_latest a
  JOIN instrument i ON i.id = a.instrument_id
                   AND i.is_active AND i.duplicate_of IS NULL
  JOIN instrument_toc_entry e ON e.id = a.toc_entry_id
                             AND e.provision_id IS NULL
  JOIN source_incompleteness s
    ON s.id = CASE WHEN a.resolution = 'source_incomplete'
                   THEN (a.evidence ->> 'source_incompleteness_id')::bigint END
  LEFT JOIN v_source_incompleteness_latest l
    ON l.source_observation_id = s.source_observation_id
 WHERE a.resolution = 'source_incomplete';

COMMENT ON VIEW v_toc_gap_source_incomplete IS
  'Printed contents entries of live canonical instruments released without a '
  'provision because the landed copy does not print them (0054 record named). '
  'Render as "not available in this copy" -- never as repealed or absent.';

COMMIT;
