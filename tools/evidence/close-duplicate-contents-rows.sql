-- Contents gaps that are a SECOND COPY of a promise already resolved.
--
-- `_toc_source_entries` sometimes takes a body section opener for a contents
-- row. The instrument then carries the same promise twice: once from the
-- contents page, linked to its provision, and once from the body, unlinked and
-- reported as a gap. Document 2225 shows it plainly -- the contents page gives
-- "1 Short title and extent" linked to section 1, and page 2's body opener
-- "Short title and extent. ___ (1) This Act may be called ..." becomes a second
-- entry that resolves to nothing.
--
-- No section is missing in these. The promised provision is present and citable
-- at the number the source prints, which is what `found_elsewhere` records, and
-- the provision named is the one the LINKED twin already points at.
--
-- WHY THE LABEL ALONE IS NOT ENOUGH, and this is most of the work. Matching on
-- the citation label only, 96 gaps in 29 documents look like duplicates. They
-- are not: the headings disagree completely. Document 1839's "gap" for section
-- 3 is "The Registrar, Lahore High Court Lahore." -- a distribution list on a
-- notification's last page, parsed as a contents row and carrying a coincidental
-- number. Document 876's is "Finance and Planning Committee." against a linked
-- "Visitation.". Recording those as found_elsewhere would assert that a postal
-- address is section 3.
--
-- So the heading must agree too, as an exact match or a prefix either way --
-- the body row carries the heading plus its operative text, the contents row
-- carries the heading alone. That takes 96 to 15.
--
-- And one of those 15 is still wrong: document 2852's twin heading is "****", a
-- starred omission whose normalised form is empty, and `d.hk LIKE '' || '%'`
-- matches everything. An empty twin heading is excluded below, which is the
-- difference between 15 and 14.
--
-- The underlying parser defect -- body openers becoming contents rows -- is NOT
-- repaired here. These rows will return on a replay until it is.

BEGIN;

WITH dup AS (
  SELECT g.toc_entry_id, g.instrument_id, g.document_id, g.printed_label,
         g.source_page,
         regexp_replace(lower(g.printed_label), '[^a-z0-9]', '', 'g') AS lk,
         regexp_replace(lower(coalesce(g.printed_heading, '')),
                        '[^a-z0-9]', '', 'g') AS hk
    FROM v_toc_gap_pending g
   WHERE g.toc_entry_id IS NOT NULL
), twin AS (
  SELECT DISTINCT ON (d.toc_entry_id)
         d.toc_entry_id, d.instrument_id, d.document_id, d.printed_label,
         d.source_page, e.id AS twin_entry_id, p.id AS provision_id, p.label,
         p.kind::text AS kind
    FROM dup d
    JOIN instrument_toc_entry e
      ON e.instrument_id = d.instrument_id
     AND e.id <> d.toc_entry_id
     AND e.provision_id IS NOT NULL
     AND regexp_replace(lower(e.printed_label), '[^a-z0-9]', '', 'g') = d.lk
     -- an empty twin heading would match every gap under the prefix test
     AND regexp_replace(lower(coalesce(e.printed_heading, '')),
                        '[^a-z0-9]', '', 'g') <> ''
     AND (regexp_replace(lower(coalesce(e.printed_heading, '')),
                         '[^a-z0-9]', '', 'g') = d.hk
          OR regexp_replace(lower(coalesce(e.printed_heading, '')),
                            '[^a-z0-9]', '', 'g') LIKE d.hk || '%'
          OR d.hk LIKE regexp_replace(lower(coalesce(e.printed_heading, '')),
                                      '[^a-z0-9]', '', 'g') || '%')
    JOIN provision p ON p.id = e.provision_id AND p.is_active
   WHERE d.hk <> '' AND length(d.hk) >= 10
   ORDER BY d.toc_entry_id, e.ordinal
)
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT t.instrument_id, t.document_id, t.toc_entry_id, t.printed_label,
       'found_elsewhere', t.source_page,
       jsonb_build_object(
         'found_provision_id', t.provision_id::text,
         'body_label', t.label,
         'body_kind', t.kind,
         'duplicate_of_toc_entry_id', t.twin_entry_id,
         'check', 'another contents entry of this instrument carries the same '
                  'citation label AND a matching heading, and is already linked '
                  'to a provision; this row is a second copy of that promise, '
                  'taken from the body opener rather than the contents page',
         'why_label_alone_is_insufficient',
             'matching on the label only gives 96 rows whose headings disagree '
             'entirely -- document 1839 entry 3 is "The Registrar, Lahore High '
             'Court Lahore.", a distribution list; recording those would assert '
             'that a postal address is a section',
         'tool', 'tools/evidence/close-duplicate-contents-rows.sql',
         'upstream_defect', '_toc_source_entries takes a body section opener '
                            'for a contents row; not repaired here, so these '
                            'rows return on a replay',
         'reviewer_type', 'assistant',
         'human_page_review', false)::jsonb,
       'This contents row is a second copy of a promise the instrument already '
       'resolves. Another entry with the same citation label and a matching '
       'heading is linked to ' || t.kind || ' ' || t.label || ', so the section '
       'is present and citable at the number the source prints. Nothing is '
       'absent and nothing is fabricated: what is wrong is that the body''s own '
       'section opener was collected as a contents entry. Supersede this if a '
       'reading disagrees.',
       'claude.duplicate-contents-row/1'
  FROM twin t;

COMMIT;
