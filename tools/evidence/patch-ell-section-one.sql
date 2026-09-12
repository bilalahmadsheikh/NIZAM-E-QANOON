-- Five Acts lost their section 1 to a single wrong glyph.
--
-- Their official PDFs print "l." where the digit 1 belongs -- a lowercase L in
-- the text layer. Extraction is faithful to the file; the file is wrong. With no
-- digit the grammar opens no section, so the short title, extent and
-- commencement of five statutes is absent from the corpus, and each document's
-- contents row for section 1 has nothing to link to.
--
-- Verified by reading the rendered source page for each:
--   doc  49 p2  "l.  (1) This Act may be called the West Pakistan Agricultural
--               Development Finance Corporation (Recovery of Arrears) Act, 1958"
--               with the marginal heading "Short title, extent and Commencement."
--   doc  88 p2  the Balochistan Juvenile Smoking Ordinance, marginal heading
--               "Short title and extent."; its section 2 "Definitions." parses
--               normally, so only the glyph differs.
--   doc 152 p2, doc 583 p3, doc 4199 p3  the same shape.
--
-- A curation patch is the right instrument: it corrects the PARSER INPUT and
-- never text_block, it is located by page plus a unique fragment so it survives
-- re-extraction, and it fails closed if that locator stops being unique.
-- review_state is 'source_verified', which migration 0025 defines as "directly
-- checked against the official PDF page; it does not imply human publication
-- approval" -- exactly what was done here.

BEGIN;

INSERT INTO segmentation_curation_patch
    (source_observation_id, page_no, match_text, before_text, after_text,
     evidence, review_state, created_by)
VALUES
 (1070, 2, 'This Act may be called the 2West Pakistan',
  E'l.\n(1)\n', E'1.\n(1)\n',
  jsonb_build_object(
    'defect', 'digit 1 present as lowercase L in the source text layer',
    'document_id', 49,
    'marginal_heading', 'Short title, extent and Commencement.',
    'render_artifact', '.artifacts/toc-gap-review/doc49-e270362-label1-p2.png',
    'reviewer_type', 'assistant', 'human_page_review', false),
  'source_verified', 'claude.glyph-review/1'),

 (1058, 2, 'This Ordinance may be called the 2[Balochistan]',
  E'l.\n(1)\n', E'1.\n(1)\n',
  jsonb_build_object(
    'defect', 'digit 1 present as lowercase L in the source text layer',
    'document_id', 88,
    'marginal_heading', 'Short title and extent.',
    'render_artifact', '.artifacts/toc-gap-review/doc88-e268105-label1-p2.png',
    'reviewer_type', 'assistant', 'human_page_review', false),
  'source_verified', 'claude.glyph-review/1'),

 (1113, 2, 'Firewood and Charcoal (Restriction) Act',
  E'l.\n(1)\n', E'1.\n(1)\n',
  jsonb_build_object(
    'defect', 'digit 1 present as lowercase L in the source text layer',
    'document_id', 152,
    'reviewer_type', 'assistant', 'human_page_review', false),
  'source_verified', 'claude.glyph-review/1'),

 (1123, 3, 'Redemption and Restitution of Mortgaged',
  E'l.\n(1)\n', E'1.\n(1)\n',
  jsonb_build_object(
    'defect', 'digit 1 present as lowercase L in the source text layer',
    'document_id', 583,
    'reviewer_type', 'assistant', 'human_page_review', false),
  'source_verified', 'claude.glyph-review/1'),

 (877, 3, 'Short title, extent and commencement',
  'l. Short title', '1. Short title',
  jsonb_build_object(
    'defect', 'digit 1 present as lowercase L in the source text layer',
    'document_id', 4199,
    'note', 'this one prints the heading inline rather than in the margin',
    'reviewer_type', 'assistant', 'human_page_review', false),
  'source_verified', 'claude.glyph-review/1');

COMMIT;
