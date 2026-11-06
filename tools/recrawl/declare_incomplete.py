"""declare_incomplete.py SPEC.json : write tools/evidence/declare-source-incompleteness-DOC.sql from a reviewed spec
(the pattern of declare-source-incompleteness-9662.sql) and print the psql command that applies it.

SPEC: {"document_id", "title", "body_stops_at", "promised_top", "observed", "missing": [{"what",
"last_printed_block_id", "resumes_block_id"}], "pages": [render page numbers read], "question_id": "q1",
"recovery_path"}. The observation, its URL and SHA-256 come from the database; the renders' SHA-256 from the files
(.artifacts/release-work-2026-09-24/claude/renders/docDOC-pN.png). Requires a recorded refetch attempt (the SQL
refuses without one) and the delegated answer (tools/recrawl/deleg_answer.py)."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
s = json.load(open(sys.argv[1], encoding="utf-8"))
d = int(s["document_id"])
with connect() as c, c.cursor() as cur:
    cur.execute("""SELECT o.id, coalesce(o.canonical_url, ''), o.sha256 FROM instrument i
                    JOIN source_observation o ON o.id = i.source_observation_id
                   WHERE i.document_id=%s AND i.is_active LIMIT 1""", (d,))
    obs, url, sha = cur.fetchone()
renders = [f".artifacts/release-work-2026-09-24/claude/renders/doc{d}-p{p}.png" for p in s["pages"]]
shas = [hashlib.sha256((ROOT / r).read_bytes()).hexdigest() for r in renders]
q = lambda x: "'" + str(x).replace("'", "''") + "'"   # noqa: E731
jarr = lambda xs: "jsonb_build_array(" + ", ".join(q(x) for x in xs) + ")"   # noqa: E731
missing = "jsonb_build_array(" + ", ".join(
    "jsonb_build_object('what', {}, 'last_printed_block_id', {}, 'resumes_block_id', {})".format(
        q(m["what"]), m.get("last_printed_block_id") or "NULL", m.get("resumes_block_id") or "NULL")
    for m in s["missing"]) + ")"
sql = f"""--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document {d}, {s['title']}.
-- Observation {obs}, {url}, SHA-256 {sha}.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document {d}, {s.get('question_id', 'q1')}
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation {obs} --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = {obs} AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation {obs} has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT {obs}, {d}, 'no_complete_copy_acquired', NULL,
       {q(s['body_stops_at'])},
       {q(s['promised_top'])},
       {q(s['observed'])},
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN {q('A dated refetch of the official URL returned the same PDF (SHA-256 ' + sha[:8] + '...); no complete copy was obtained.')}
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', {q(sha)},
         'render_artifact', {jarr(renders)},
         'render_sha256', {jarr(shas)},
         'missing', {missing},
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', {d}, 'question_id', {q(s.get('question_id', 'q1'))}, 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', {q(s['recovery_path'])}),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = {obs}
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = {obs});

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = {obs}) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation {obs}: run tools/record_source_refetch.py --observation {obs} --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = {obs};
"""
out = ROOT / f"tools/evidence/declare-source-incompleteness-{d}.sql"
out.write_text(sql, encoding="utf-8")
print(out)
