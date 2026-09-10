-- A fail-closed boundary between the evidentiary corpus and production reads.
--
-- Active documents are retained even when a verifier asks for review: hiding
-- them would destroy the review trail. Release consumers, however, must never
-- infer that document.is_active means "quality approved". These views make the
-- narrower, independently verified set explicit and reusable.
BEGIN;

CREATE OR REPLACE VIEW v_release_document AS
SELECT d.*
  FROM v_document d
  JOIN v_document_quality_status q ON q.document_id=d.document_id
 WHERE q.overall_outcome='passed';

CREATE OR REPLACE VIEW v_release_page AS
SELECT p.*
  FROM page p
  JOIN v_document_quality_status q ON q.document_id=p.document_id
 WHERE q.overall_outcome='passed';

CREATE OR REPLACE VIEW v_release_text_block AS
SELECT b.*
  FROM text_block b
  JOIN v_document_quality_status q ON q.document_id=b.document_id
 WHERE q.overall_outcome='passed';

COMMENT ON VIEW v_release_document IS
  'Active extraction revisions whose newest required independent evidence all passes.';
COMMENT ON VIEW v_release_page IS
  'Pages of quality-passed active extraction revisions; production-safe read boundary.';
COMMENT ON VIEW v_release_text_block IS
  'Blocks of quality-passed active extraction revisions; production-safe read boundary.';

COMMIT;
