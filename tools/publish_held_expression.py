"""Write the legal tree of ONE held expression of a compilation, leaving every other expression untouched.

Why this exists (docs/EXPRESSION-SOURCE-VARIANTS.md, 'Replay is deliberately fail-closed'): `legal_write.save_many()`
replaces EVERY expression of a source observation and so refuses an observation that carries a standing
source-variant disposition. Document 9361 does: e3-e9 are resolved as print variants of released instruments, e1 and
e2 are released, and e0 (the Karachi Development Authority Order, 1957) was held. This writer appends the tree of
the named expression only:

  * the other expressions' instrument ids, provisions, versions, manifests (and their variant dispositions) are not
    written, retired or re-created; every release fingerprint is compared before and after, inside the transaction;
  * the held expression's old instrument and manifest are RETIRED and superseded (append-only), its manifest evidence
    (including `source_access_release`) is carried forward unchanged and a `held_expression_release` record is added;
  * the observation's block-assignment set is superseded by a copy in which only the expression's own blocks change;
  * a `segmented` run is recorded and the release gate is checked in the same transaction, so the writer either
    leaves the expression released or leaves no trace.

Default is a rehearsal that rolls back. `--apply` needs `--owner-decision` (the owner's words, >= 80 characters) and
refuses unless the rehearsal conditions hold. It writes no dates: versions open at the observation's `as_at`, exactly
like every other released expression, and the instrument status stays 'unknown'.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nizam.storage import legal_write
from nizam.storage.db import connect
from tools import materialize_multi_instrument as m
from tools.second_parser_release import RELEASE_FINGERPRINT_SQL

ROOT = Path(__file__).resolve().parents[1]
METHOD = "nizam.held_expression_release/1"


class _Shared:
    """Lets legal_write.record_run() write inside our transaction."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        return False


def _others(cur, obs: int, ordinal: int) -> dict:
    cur.execute("""SELECT expression_ordinal, id::text, is_active, coalesce(duplicate_of::text,'-')
                     FROM instrument WHERE source_observation_id=%s ORDER BY expression_ordinal, created_at, id""",
                (obs,))
    instruments = [r for r in cur.fetchall() if r[0] != ordinal]
    cur.execute("""SELECT expression_ordinal, id::text, is_active, md5(evidence::text), materialized_instrument_id::text
                     FROM instrument_expression_manifest WHERE source_observation_id=%s ORDER BY expression_ordinal, created_at, id""",
                (obs,))
    manifests = [r for r in cur.fetchall() if r[0] != ordinal]
    return {"instruments": instruments, "manifests": manifests}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--document", type=int, required=True)
    ap.add_argument("--observation", type=int, required=True)
    ap.add_argument("--ordinal", type=int, required=True)
    ap.add_argument("--plan", required=True, help="reviewed multi-expression plan (tools/evidence/multi-instrument-plans)")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--owner-decision", default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.apply and (not args.owner_decision or len(args.owner_decision.strip()) < 80):
        ap.error("--apply needs --owner-decision with the owner's words (>= 80 characters)")
    DOC, OBS, ORD = args.document, args.observation, args.ordinal
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8-sig"))
    insts, segs, mans, blocks = m.prepare_from_plan(DOC, plan, OBS, profile=args.profile, allow_empty=True)
    inst = next(i for i in insts if i.expression_ordinal == ORD)
    seg = next(s for i, s in zip(insts, segs) if i.expression_ordinal == ORD)
    if not inst.provisions:
        raise SystemExit(f"expression {ORD} segments to no provisions; nothing to write")
    if inst.structural_decisions:
        print(f"note: expression {ORD} proposes {len(inst.structural_decisions)} S7 decisions; they are written pending")

    old_lw_connect = legal_write.connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur.execute("SELECT id FROM source_observation WHERE id=%s FOR UPDATE", (OBS,))
        if cur.fetchone() is None:
            raise SystemExit("unknown observation")
        cur.execute("""SELECT id, expression_ordinal FROM instrument
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""", (OBS,))
        active = {r[1]: r[0] for r in cur.fetchall()}
        if ORD not in active:
            raise SystemExit(f"expression {ORD} has no active instrument")
        old_id = active[ORD]
        cur.execute("SELECT count(*) FROM provision WHERE instrument_id=%s AND is_active", (old_id,))
        if cur.fetchone()[0]:
            raise SystemExit(f"expression {ORD} already has active provisions; refusing (this writer only releases a held, empty expression)")
        cur.execute("SELECT 1 FROM v_release_instrument WHERE id=%s", (old_id,))
        if cur.fetchone():
            raise SystemExit(f"expression {ORD} is already released")
        cur.execute("""SELECT id, expression_role, start_block_id, end_block_id, detected_title, detected_kind, detected_year,
                              detected_number, review_basis, method, evidence, historical_validity,
                              current_source_observation_id, current_expression_ordinal
                         FROM instrument_expression_manifest
                        WHERE source_observation_id=%s AND expression_ordinal=%s AND is_active FOR UPDATE""", (OBS, ORD))
        old_manifest = cur.fetchone()
        if old_manifest is None:
            raise SystemExit("no active manifest for the expression")
        if old_manifest[11] is not None:
            raise SystemExit("the expression carries a historical window; this writer does not handle it")
        cur.execute("""SELECT span_ordinal, start_block_id, end_block_id FROM instrument_expression_span
                        WHERE manifest_id=%s ORDER BY span_ordinal""", (old_manifest[0],))
        spans = cur.fetchall()
        cur.execute("""SELECT id FROM block_assignment_set WHERE source_observation_id=%s AND is_active FOR UPDATE""", (OBS,))
        old_set = cur.fetchone()[0]

        cur.execute("SELECT id::text FROM v_release_instrument")
        released_before = {r[0] for r in cur.fetchall()}
        cur.execute(RELEASE_FINGERPRINT_SQL)
        fingerprints_before = dict(cur.fetchall())
        others_before = _others(cur, OBS, ORD)
        own_blocks = {b[0] for b in inst.block_roles}
        cur.execute("""SELECT block_id, provision_id::text, role::text, chars FROM provision_block
                        WHERE assignment_set_id=%s ORDER BY block_id""", (old_set,))
        outside_before = [r for r in cur.fetchall() if r[0] not in own_blocks]

        # 1. retire the held expression's instrument, manifest and the observation's assignment set (append-only)
        cur.execute("UPDATE instrument SET is_active=false, retired_at=now() WHERE id=%s", (old_id,))
        cur.execute("""UPDATE instrument_expression_manifest SET is_active=false, retired_at=now() WHERE id=%s""",
                    (old_manifest[0],))
        cur.execute("UPDATE block_assignment_set SET is_active=false, retired_at=now() WHERE id=%s", (old_set,))
        cur.execute("""INSERT INTO block_assignment_set (document_id, source_observation_id, instrument_id, segmenter, supersedes_set_id)
                       VALUES (%s,%s,NULL,%s,%s) RETURNING id""", (DOC, OBS, METHOD, old_set))
        new_set = cur.fetchone()[0]

        # 2. the new instrument and its tree (as legal_write.save_many writes one expression)
        cur.execute("""
            INSERT INTO instrument
                (jurisdiction,kind,number,year,short_title,long_title,preamble,source_sha256,document_id,source_url,
                 extraction_conf,status,source_observation_id,supersedes_instrument_id,expression_ordinal,
                 source_start_block_id,source_end_block_id,expression_role)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'unknown',%s,%s,%s,%s,%s,%s) RETURNING id""",
            (inst.jurisdiction, inst.kind, inst.number, inst.year, inst.short_title, inst.long_title, inst.preamble,
             inst.sha256, inst.document_id, inst.source_url, inst.confidence, inst.source_observation_id, old_id,
             inst.expression_ordinal, inst.source_start_block_id, inst.source_end_block_id, inst.expression_role))
        new_id = cur.fetchone()[0]
        cur.execute("INSERT INTO instrument_source (instrument_id,source_observation_id,role) VALUES (%s,%s,'primary')", (new_id, OBS))
        ids: dict = {}
        for row in inst.provisions:
            parent_id = ids.get(row["parent_key"]) if row["parent_key"] is not None else None
            cur.execute("""INSERT INTO provision (instrument_id,parent_id,path,kind,label,heading,marginal_note,ordinal,
                                                  first_page,last_page,first_block)
                           VALUES (%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (new_id, parent_id, row["path"], row["kind"], row["label"], row["heading"], row.get("marginal_note"),
                         row["ordinal"], row["first_page"], row["last_page"], row["first_block"]))
            ids[row["key"]] = cur.fetchone()[0]
            if row["text"] or row.get("operation") != "original":
                legal_write.insert_version(cur, inst, ids[row["key"]], row)
        cur.execute("""WITH RECURSIVE ancestry AS (
                            SELECT p.id provision_id,p.id ancestor_id,p.path ancestor_path,0::smallint distance
                              FROM provision p WHERE p.instrument_id=%s
                            UNION ALL
                            SELECT a.provision_id,parent.id,parent.path,(a.distance+1)::smallint
                              FROM ancestry a JOIN provision child ON child.id=a.ancestor_id
                              JOIN provision parent ON parent.id=child.parent_id)
                        INSERT INTO provision_ancestor (ancestor_path,provision_id,distance)
                        SELECT ancestor_path,provision_id,distance FROM ancestry""", (new_id,))
        for entry in inst.toc_entries:
            key = entry.get("provision_key")
            pid = ids.get(key) if key is not None else None
            cur.execute("""INSERT INTO instrument_toc_entry (instrument_id,ordinal,printed_label,printed_heading,entry_kind,
                               source_block_id,source_char_offset,source_page,provision_id,match_method)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (new_id, entry["ordinal"], entry["label"], entry["heading"], entry["kind"], entry.get("source_block_id"),
                         entry.get("source_char_offset"), entry.get("source_page"), pid,
                         entry["method"] if pid is not None else "unmatched"))
        for d in inst.structural_decisions:
            pk = d.get("parent_key")
            cur.execute("""INSERT INTO segmentation_structural_candidate
                (instrument_id,source_observation_id,document_id,candidate_provision_id,canonical_provision_id,parent_provision_id,
                 decision_kind,original_kind,printed_label,source_block_id,source_page,canonical_source_block_id,canonical_source_page,
                 proposed_resolution,segmenter,evidence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (new_id, OBS, DOC, ids[d["candidate_key"]], ids[d["canonical_key"]], ids.get(pk) if pk is not None else None,
                         d["decision_kind"], d["original_kind"], d["printed_label"], d["source_block_id"], d["source_page"],
                         d["canonical_source_block_id"], d["canonical_source_page"], d["proposed_resolution"], METHOD,
                         json.dumps(d["evidence"], ensure_ascii=False)))

        # 3. manifest: carried forward unchanged, plus the release record
        evidence = dict(old_manifest[10] or {})
        evidence["source_body_review_state"] = "qualified-by-owner-page-reading" if args.apply else "rehearsal"
        evidence["held_expression_release"] = {
            "method": METHOD,
            "owner_decision": (args.owner_decision or "").strip(),
            "validity": "versions open at the observation's as_at; no historical window; instrument status unknown",
            "disclosure": ("The Order as made, from a compilation print; later amendments (P.O. 4 of 1958, Chapter VII notification, "
                           "1961 retrospective corrections) are not applied and their texts are not in the corpus. The source-access "
                           "notice recorded on this manifest stays in force."),
            "retired_instrument_id": str(old_id),
        }
        cur.execute("""INSERT INTO instrument_expression_manifest
            (source_observation_id,document_id,expression_ordinal,expression_role,start_block_id,end_block_id,detected_title,
             detected_kind,detected_year,detected_number,review_basis,method,evidence,materialized_instrument_id,
             supersedes_manifest_id,historical_validity,current_source_observation_id,current_expression_ordinal)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,NULL,%s,%s) RETURNING id""",
                    (OBS, DOC, ORD, old_manifest[1], old_manifest[2], old_manifest[3], old_manifest[4], old_manifest[5],
                     old_manifest[6], old_manifest[7], old_manifest[8], old_manifest[9], json.dumps(evidence, ensure_ascii=False),
                     new_id, old_manifest[0], old_manifest[12], old_manifest[13]))
        new_manifest = cur.fetchone()[0]
        for span_ordinal, a, b in spans:
            cur.execute("""INSERT INTO instrument_expression_span (manifest_id,span_ordinal,start_block_id,end_block_id)
                           VALUES (%s,%s,%s,%s)""", (new_manifest, span_ordinal, a, b))

        # 4. block ledger: every other block carries over unchanged; this expression's blocks take the new roles
        ledger = {}
        for block_id, role, node_key, chars in inst.block_roles:
            pid = ids.get(node_key) if node_key is not None else None
            if pid is None and role in ("body", "heading", "schedule_row", "preamble"):
                role = "unassigned"
            if pid is not None and role in ("contents", "preface", "running_header", "unstructured", "unassigned"):
                pid = None
            ledger[block_id] = (role, pid, chars)
        cur.execute("""INSERT INTO provision_block (assignment_set_id,block_id,document_id,provision_id,role,chars)
                       SELECT %s,block_id,document_id,provision_id,role,chars FROM provision_block
                        WHERE assignment_set_id=%s AND NOT (block_id = ANY(%s))""", (new_set, old_set, list(own_blocks)))
        cur.execute("SELECT block_id, role::text, chars FROM provision_block WHERE assignment_set_id=%s AND block_id=ANY(%s)", (old_set, list(own_blocks)))
        old_own = {r[0]: r for r in cur.fetchall()}
        missing = own_blocks - set(old_own)
        if missing:
            raise SystemExit(f"expression blocks absent from the old assignment set: {sorted(missing)[:5]}")
        for block_id in sorted(own_blocks):
            role, pid, chars = ledger[block_id]
            cur.execute("""INSERT INTO provision_block (assignment_set_id,block_id,document_id,provision_id,role,chars)
                           VALUES (%s,%s,%s,%s,%s,%s)""", (new_set, block_id, DOC, pid, role, chars))

        # 5. run record, release gate, and every invariant that must not move
        legal_write.connect = lambda: _Shared(conn)
        try:
            legal_write.record_run(DOC, OBS, new_id, METHOD, "segmented", provisions=len(inst.provisions),
                                   sections=sum(p["kind"] == "section" for p in inst.provisions),
                                   max_depth=max((p["path"].count(".") for p in inst.provisions), default=0),
                                   body_starts_page=seg.body_starts_page, toc_found=seg.toc_found, toc_entries=len(seg.toc_entries),
                                   toc_matched=seg.matched if seg.toc else 0, toc_missing=len(seg.missing) if seg.toc else 0,
                                   toc_extra=len(seg.extra) if seg.toc else 0,
                                   detail=dict(expression_ordinal=ORD, profile=seg.profile, held_expression_release=True,
                                               owner_decision=(args.owner_decision or "").strip()))
        finally:
            legal_write.connect = old_lw_connect
        failure = legal_write._release_gate_failure(cur, new_id, DOC)
        problems = []
        if failure:
            problems.append(f"release gate: {failure}")
        cur.execute("SELECT id::text FROM v_release_instrument")
        released_after = {r[0] for r in cur.fetchall()}
        if released_after - released_before != {str(new_id)} or released_before - released_after:
            problems.append("the released set changed by more than the new expression")
        cur.execute(RELEASE_FINGERPRINT_SQL)
        fingerprints_after = dict(cur.fetchall())
        for iid, fp in fingerprints_before.items():
            if fingerprints_after.get(iid) != fp:
                problems.append(f"release fingerprint changed for {iid}")
        if _others(cur, OBS, ORD) != others_before:
            problems.append("another expression's instrument or manifest changed")
        cur.execute("""SELECT block_id, provision_id::text, role::text, chars FROM provision_block
                        WHERE assignment_set_id=%s ORDER BY block_id""", (new_set,))
        outside_after = [r for r in cur.fetchall() if r[0] not in own_blocks]
        if outside_after != outside_before:
            problems.append("block assignments outside the expression changed")
        cur.execute("""SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id
                        WHERE i.source_observation_id=%s AND i.is_active AND i.expression_ordinal<>%s AND p.is_active
                          AND i.id::text <> ALL(%s)""",
                    (OBS, ORD, list(released_before)))
        unexpected = cur.fetchone()[0]
        if unexpected:
            problems.append(f"{unexpected} active provisions appeared in unreleased sibling expressions")
        report = {"applied": bool(args.apply and not problems), "document": DOC, "observation": OBS, "ordinal": ORD,
                  "old_instrument": str(old_id), "new_instrument": str(new_id), "provisions": len(inst.provisions),
                  "s7_pending": len(inst.structural_decisions), "released_before": len(released_before),
                  "released_after": len(released_after), "problems": problems}
        print(json.dumps(report, indent=2))
        if problems or not args.apply:
            conn.rollback()
            return 1 if problems else 0
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
