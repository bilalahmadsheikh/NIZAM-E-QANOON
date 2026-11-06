"""replay_with_toc.py DOC READINGS.json "APPROVAL" : replay a RELEASED document whose corrected tree has contents gaps
the reader has already settled, recording those decisions in the replay's own transaction (30 Oct 2026, doc 9168).

Why: a released tree is replaced only if the new tree passes the release gate inside the replacement transaction
(legal_write.save). A correction that turns wrongly-built contents rows back into gaps -- the sections the copy does
not print -- can never pass, because a gap decision keys on a toc_entry_id that exists only once the new tree is
written. This runs the ordinary worker (python -m nizam.workers.segment --document DOC --redo --include-review
--approve-release-change APPROVAL) with one change: just before the gate is checked, the readings are applied to the
new tree's pending gaps on the same cursor, exactly as tools/adjudicate_toc_from_source.py would record them (same
evidence shape, decided_by, renders verified). The gate then judges the final state; if it still fails, everything
rolls back, the decisions included.

READINGS: [{"printed_label": "29", "heading_prefix": "Further matters", "resolution": "source_incomplete",
"source_incompleteness_id": 71, "source_page": 5, "observed": "...", "renders": [{"path", "sha256"}]},
{"printed_label": "10", "heading_prefix": "CHAPTER", "resolution": "found_elsewhere", "found_label": "10",
"found_kind": "section", ...}]. Each reading must match exactly one pending gap of the new tree."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
from nizam.workers import segment as worker

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
DECIDED_BY = "claude.toc-source-review/2"
doc, readings, approval = int(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), sys.argv[3]
for r in readings:
    for x in r["renders"]:
        assert hashlib.sha256((ROOT / x["path"]).read_bytes()).hexdigest() == x["sha256"], ("render changed", x["path"])

_orig = legal_write._release_gate_failure
applied = []


def _gate(cur, instrument_id, document_id):
    if document_id == doc and not applied:
        cur.execute("""SELECT toc_entry_id, printed_label, coalesce(printed_heading,''), entry_kind
                         FROM v_toc_gap_pending WHERE instrument_id=%s AND toc_entry_id IS NOT NULL""", (instrument_id,))
        gaps = cur.fetchall()
        for r in readings:
            hits = [g for g in gaps if g[1] == r["printed_label"] and g[2].startswith(r.get("heading_prefix", ""))]
            if len(hits) != 1:
                raise ValueError(f"reading {r['printed_label']!r}/{r.get('heading_prefix')!r} matches {len(hits)} gaps")
            entry, label, heading, kind = hits[0]
            ev = {"assistant_page_review": True, "human_page_review": False, "reviewer_type": "assistant",
                  "render_artifact": [x["path"] for x in r["renders"]],
                  "render_sha256": [x["sha256"] for x in r["renders"]],
                  "observed": r["observed"], "printed_heading": heading, "entry_kind": kind,
                  "toc_entry_id_at_review": entry, "tool": "tools/recrawl/replay_with_toc.py"}
            if r["resolution"] == "source_incomplete":
                cur.execute("""SELECT id, source_observation_id, resolution FROM v_source_incompleteness_latest
                                WHERE id=%s AND document_id=%s""", (r["source_incompleteness_id"], doc))
                si = cur.fetchone()
                assert si and si[2] == "no_complete_copy_acquired", ("source_incompleteness", r)
                ev.update({"source_incompleteness_id": si[0], "source_observation_id": si[1],
                           "source_incompleteness_resolution": si[2],
                           "not_absent_in_source": "the Act has this unit; the landed copy does not print it "
                                                   "(migration 0054 record named above)"})
            elif r["resolution"] == "found_elsewhere":
                cur.execute("""SELECT id::text, kind::text, label, path::text, first_block, first_page FROM provision
                                WHERE instrument_id=%s AND is_active AND kind=%s AND label=%s""",
                            (instrument_id, r["found_kind"], r["found_label"]))
                f = cur.fetchall()
                assert len(f) == 1, ("found provision", r, len(f))
                pid, fk, fl, fp, fb, fpg = f[0]
                ev.update({"found_provision_id": pid, "found_kind": fk, "found_label": fl, "found_path": fp,
                           "found_first_block": fb, "body_first_page": fpg})
            else:
                raise ValueError(r["resolution"])
            cur.execute("""INSERT INTO toc_gap_adjudication
                             (instrument_id, document_id, toc_entry_id, printed_label, resolution, source_page,
                              evidence, rationale, decided_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (instrument_id, doc, entry, label, r["resolution"], r["source_page"],
                         json.dumps(ev, ensure_ascii=False), r["observed"], DECIDED_BY))
            applied.append((label, r["resolution"]))
        print("decisions in the replay transaction:", applied)
    return _orig(cur, instrument_id, document_id)


legal_write._release_gate_failure = _gate
sys.argv = ["segment", "--document", str(doc), "--redo", "--include-review", "--approve-release-change", approval]
sys.exit(worker.main())
