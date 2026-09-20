"""Append exact-tree revisions for unambiguous TOC typography variants.

The printed contents and body sometimes spell one citation differently:
``01`` versus ``1``, or ``53-A`` versus ``53A``/``53 A``.  The current parser
reconciles those forms, but replaying a years-old tree with today's complete
parser can also change unrelated structure.  This worker therefore copies the
active tree, text, block ledger, and S7 evidence exactly and changes only TOC
links whose typography-normalized key identifies one unresolved entry and one
otherwise-unlinked section/article.

No corpus row is deleted.  ``legal_write.save`` atomically retires the prior
revision and records the new append-only expression.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter

from nizam.corpus.segment import _citation_label_key, _heading_supports
from nizam.shared.corpus_types import SegmentedInstrument
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import only_one_run


SEGMENTER = "nizam.toc_typography_overlay/1"

# Set from --exact-label; the default keeps the original typography-only rule.
EXACT_LABELS = False


def _is_supported_variant(printed: str, body: str, exact: bool = False) -> bool:
    """Accept only measured zero-padding and suffix dash/space typography.

    ``exact`` additionally accepts a contents label that is already identical to
    the body label. The segmenter normally links those itself, so one left
    pending means the link was lost rather than never possible -- 111 such rows
    sit in 24 documents. It is gated because "identical" is not by itself a
    reason to link: the ambiguity guards in the caller, which require exactly
    one pending entry and exactly one unlinked section for the key, are what
    make it safe, and they apply unchanged.
    """
    if printed.casefold() == body.casefold():
        return exact
    if printed.isdigit() and body.isdigit():
        return (len(printed) > 1 and printed.startswith("0")
                and int(printed) == int(body))
    suffix = re.compile(r"^\d+[\s\-\u2013\u2014]*[A-Za-z]+$")
    return bool(suffix.fullmatch(printed) and suffix.fullmatch(body)
                and _citation_label_key(printed) == _citation_label_key(body))


def load_plan(
    instrument_id: str,
    retract_entry_ids: set[int] | None = None,
) -> tuple[SegmentedInstrument, dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id::text,document_id,source_observation_id,source_sha256,
                   jurisdiction::text,kind::text,number,year,short_title,
                   long_title,preamble,source_url,extraction_conf,
                   expression_ordinal,source_start_block_id,source_end_block_id,
                   expression_role
              FROM instrument
             WHERE id=%s AND is_active AND duplicate_of IS NULL
        """, (instrument_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"instrument {instrument_id}: not active/canonical")
        (old_id,document_id,observation_id,sha256,jurisdiction,kind,number,year,
         short_title,long_title,preamble,source_url,confidence,
         expression_ordinal,start_block,end_block,expression_role) = row

        cur.execute("""
            SELECT count(*) FROM instrument
             WHERE source_observation_id=%s AND is_active
               AND duplicate_of IS NULL
        """, (observation_id,))
        expressions = cur.fetchone()[0]
        if expressions != 1:
            raise ValueError(
                f"observation {observation_id}: {expressions} active canonical "
                "expressions; exact relinker requires one"
            )
        cur.execute(
            "SELECT count(*) FROM toc_gap_adjudication WHERE instrument_id=%s",
            (old_id,),
        )
        if cur.fetchone()[0]:
            raise ValueError("exact relinker refuses instruments with TOC adjudications")

        cur.execute("""
            SELECT p.id::text,p.parent_id::text,p.path::text,p.kind::text,
                   p.label,p.heading,p.marginal_note,p.ordinal,p.first_page,
                   p.last_page,p.first_block,pv.text_en,pv.operation::text,
                   pv.amended_by_id::text,pv.amendment_note,
                   pv.source_toc_disposition_assertion_id
              FROM provision p
              LEFT JOIN provision_version pv ON pv.provision_id=p.id
             WHERE p.instrument_id=%s AND p.is_active
             ORDER BY p.ordinal
        """, (old_id,))
        nodes: dict[str, dict] = {}
        for node_row in cur.fetchall():
            (node_id,parent_id,path,node_kind,label,heading,marginal_note,ordinal,
             first_page,last_page,first_block,text,operation,amended_by_id,
             amendment_note,assertion_id) = node_row
            if node_id in nodes:
                raise ValueError(f"provision {node_id}: multiple active versions")
            nodes[node_id] = {
                "parent": parent_id, "path": path, "kind": node_kind,
                "label": label, "heading": heading,
                "marginal_note": marginal_note, "ordinal": ordinal,
                "first_page": first_page, "last_page": last_page,
                "first_block": first_block, "text": text,
                "operation": operation or "original",
                "amended_by_id": amended_by_id,
                "amendment_note": amendment_note,
                "toc_disposition_assertion_id": assertion_id,
            }

        cur.execute("""
            SELECT id,ordinal,printed_label,printed_heading,entry_kind,
                   source_block_id,source_char_offset,source_page,
                   provision_id::text,match_method
              FROM instrument_toc_entry
             WHERE instrument_id=%s ORDER BY ordinal,id
        """, (old_id,))
        toc = [{
            "id": r[0], "ordinal": r[1], "label": r[2], "heading": r[3],
            "kind": r[4], "source_block_id": r[5],
            "source_char_offset": r[6], "source_page": r[7],
            "node_id": r[8], "method": r[9],
        } for r in cur.fetchall()]
        toc_ids = {entry["id"] for entry in toc}
        cur.execute("""
            SELECT toc_entry_id FROM v_toc_gap_pending
             WHERE instrument_id=%s ORDER BY toc_entry_id
        """, (old_id,))
        pending_ids = {r[0] for r in cur.fetchall()}
        if not pending_ids and not retract_entry_ids:
            raise ValueError(f"instrument {old_id}: no pending TOC entries")
        if not pending_ids <= toc_ids:
            raise ValueError("pending view contains a TOC row outside this instrument")

        cur.execute("""
            SELECT pb.block_id,pb.role::text,pb.provision_id::text,pb.chars
              FROM provision_block pb
              JOIN block_assignment_set s ON s.id=pb.assignment_set_id
             WHERE s.source_observation_id=%s AND s.is_active
             ORDER BY pb.block_id
        """, (observation_id,))
        ledger = cur.fetchall()

        cur.execute("""
            SELECT c.candidate_provision_id::text,
                   c.canonical_provision_id::text,c.parent_provision_id::text,
                   c.decision_kind,c.original_kind::text,c.printed_label,
                   c.source_block_id,c.source_page,c.canonical_source_block_id,
                   c.canonical_source_page,c.proposed_resolution,c.evidence,
                   a.id::text,a.resolution,a.review_basis,a.rationale,a.evidence,
                   a.candidate_id::text
              FROM segmentation_structural_candidate c
              LEFT JOIN v_structural_adjudication_latest a ON a.candidate_id=c.id
             WHERE c.instrument_id=%s ORDER BY c.created_at,c.id
        """, (old_id,))
        candidate_rows = cur.fetchall()

        cur.execute("""
            SELECT body_starts_page,toc_found,toc_entries,toc_matched,
                   toc_missing,toc_extra,toc_agreement,detail
              FROM segmentation_run WHERE instrument_id=%s
             ORDER BY run_at DESC,id DESC LIMIT 1
        """, (old_id,))
        old_run = cur.fetchone()
        if old_run is None:
            raise ValueError(f"instrument {old_id}: no segmentation run")

    links = []
    if retract_entry_ids:
        found = {entry["id"] for entry in toc if entry["id"] in retract_entry_ids}
        if found != retract_entry_ids:
            raise ValueError(
                f"instrument {old_id}: requested TOC rows are not all active here: "
                f"{sorted(retract_entry_ids - found)}"
            )
        for entry in toc:
            if entry["id"] not in retract_entry_ids:
                continue
            if entry["node_id"] is None or entry["method"] not in {
                    "label_typography_overlay", "label_exact_overlay"}:
                raise ValueError(
                    f"TOC row {entry['id']}: not an active overlay link"
                )
            node_id = entry["node_id"]
            links.append({
                "toc_entry_id": entry["id"],
                "printed_label": entry["label"],
                "body_label": nodes[node_id]["label"],
                "provision_id": node_id,
                "source_page": entry["source_page"],
                "first_page": nodes[node_id]["first_page"],
                "prior_method": entry["method"],
            })
            entry["node_id"] = None
            entry["method"] = None
    else:
        by_key: dict[str, list[str]] = {}
        for node_id, node in nodes.items():
            if node["kind"] in {"section", "article"}:
                by_key.setdefault(_citation_label_key(node["label"]), []).append(node_id)
        pending_by_key = Counter(
            _citation_label_key(entry["label"])
            for entry in toc if entry["id"] in pending_ids
        )
        already_linked = {entry["node_id"] for entry in toc
                          if entry["node_id"] is not None}
        for entry in toc:
            if entry["id"] not in pending_ids:
                continue
            key = _citation_label_key(entry["label"])
            candidates = by_key.get(key, [])
            if pending_by_key[key] != 1 or len(candidates) != 1:
                continue
            node_id = candidates[0]
            body_label = nodes[node_id]["label"]
            if node_id in already_linked or not _is_supported_variant(
                    entry["label"], body_label, exact=EXACT_LABELS):
                continue
            # A unique number is not a unique legal provision. Schedules,
            # tables, forms and annexes routinely restart at 1. Document 2491
            # is the concrete counterexample: its only unlinked 9--12 are posts
            # in a schedule, not the Ordinance sections promised by its TOC.
            expected_heading = entry["heading"]
            heading_evidence = (
                nodes[node_id]["heading"],
                nodes[node_id]["marginal_note"],
                nodes[node_id]["text"],
            )
            if (not expected_heading
                    or not any(_heading_supports(value, expected_heading)
                               for value in heading_evidence if value)):
                continue
            # Contents and body run in the same order. Do not jump from the Act
            # to an identically numbered provision in a later schedule.
            before = max((nodes[e["node_id"]]["first_page"] for e in toc
                          if e["ordinal"] < entry["ordinal"] and e["node_id"]
                          and nodes.get(e["node_id"], {}).get("first_page")),
                         default=None)
            after = min((nodes[e["node_id"]]["first_page"] for e in toc
                         if e["ordinal"] > entry["ordinal"] and e["node_id"]
                         and nodes.get(e["node_id"], {}).get("first_page")),
                        default=None)
            page = nodes[node_id]["first_page"]
            if page is not None:
                if before is not None and page < before:
                    continue
                if after is not None and page > after:
                    continue
            entry["node_id"] = node_id
            entry["method"] = ("label_exact_overlay"
                               if entry["label"].casefold() == body_label.casefold()
                               else "label_typography_overlay")
            already_linked.add(node_id)
            links.append({
                "toc_entry_id": entry["id"], "printed_label": entry["label"],
                "body_label": body_label, "provision_id": node_id,
                "source_page": entry["source_page"],
                "first_page": nodes[node_id]["first_page"],
            })
    if not links:
        raise ValueError(f"instrument {old_id}: no unambiguous links")

    ordered_ids = [node_id for node_id, _node in sorted(
        nodes.items(), key=lambda item: item[1]["ordinal"])]
    keys = {node_id: key for key, node_id in enumerate(ordered_ids)}
    if any(node["parent"] is not None and node["parent"] not in keys
           for node in nodes.values()):
        raise ValueError("active tree has a parent outside itself")
    provisions = []
    for node_id in ordered_ids:
        node = nodes[node_id]
        provisions.append({
            "key": keys[node_id], "parent_key": keys.get(node["parent"]),
            "path": node["path"], "kind": node["kind"],
            "label": node["label"], "heading": node["heading"],
            "marginal_note": node["marginal_note"],
            "ordinal": node["ordinal"], "first_page": node["first_page"],
            "last_page": node["last_page"], "first_block": node["first_block"],
            "text": node["text"], "operation": node["operation"],
            "amended_by_id": node["amended_by_id"],
            "amendment_note": node["amendment_note"],
            "toc_disposition_assertion_id": node["toc_disposition_assertion_id"],
        })
    dangling = [block_id for block_id, _role, provision_id, _chars in ledger
                if provision_id is not None and provision_id not in keys]
    if dangling:
        raise ValueError(f"ledger references provisions outside tree: {dangling[:5]}")
    block_roles = [(bid, role, keys.get(pid), chars)
                   for bid, role, pid, chars in ledger]
    toc_rows = [{
        "ordinal": entry["ordinal"], "label": entry["label"],
        "heading": entry["heading"], "kind": entry["kind"],
        "source_block_id": entry["source_block_id"],
        "source_char_offset": entry["source_char_offset"],
        "source_page": entry["source_page"],
        "provision_key": keys.get(entry["node_id"]),
        "method": entry["method"],
    } for entry in toc]

    structural = []
    for r in candidate_rows:
        (candidate_pid,canonical_pid,parent_pid,decision_kind,original_kind,
         printed_label,source_block_id,source_page,canonical_block,
         canonical_page,proposed,evidence,adj_id,resolution,review_basis,
         rationale,adj_evidence,adj_candidate_id) = r
        if candidate_pid not in keys or canonical_pid not in keys:
            raise ValueError("S7 evidence references a provision outside tree")
        decision = {
            "candidate_key": keys[candidate_pid],
            "canonical_key": keys[canonical_pid],
            "parent_key": keys.get(parent_pid), "decision_kind": decision_kind,
            "original_kind": original_kind, "printed_label": printed_label,
            "source_block_id": source_block_id, "source_page": source_page,
            "canonical_source_block_id": canonical_block,
            "canonical_source_page": canonical_page,
            "proposed_resolution": proposed, "evidence": evidence,
        }
        if adj_id is not None:
            decision["carried_adjudication"] = {
                "id": adj_id, "candidate_id": adj_candidate_id,
                "resolution": resolution, "review_basis": review_basis,
                "rationale": rationale, "evidence": adj_evidence,
            }
        structural.append(decision)

    inst = SegmentedInstrument(
        document_id=document_id,source_observation_id=observation_id,
        sha256=sha256,jurisdiction=jurisdiction,kind=kind,number=number,year=year,
        short_title=short_title,long_title=long_title,preamble=preamble,
        source_url=source_url,as_at=legal_write.observed_on(observation_id),
        confidence=confidence,provisions=provisions,toc_entries=toc_rows,
        block_roles=block_roles,structural_decisions=structural,
        expression_ordinal=expression_ordinal,source_start_block_id=start_block,
        source_end_block_id=end_block,expression_role=expression_role,
        copy_instrument_id=old_id,
    )
    unresolved_after = sum(entry["provision_key"] is None for entry in toc_rows)
    return inst, {
        "instrument_id": old_id, "document_id": document_id,
        "observation_id": observation_id, "links": links,
        "provisions": len(provisions), "ledger_rows": len(ledger),
        "toc_rows": len(toc_rows), "pending_after": unresolved_after,
        "structural_candidates": len(structural),
        "carried_adjudications": sum(
            "carried_adjudication" in item for item in structural),
        "old_run": old_run,
        "retraction": bool(retract_entry_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", help="comma-separated bounded set")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--exact-label", action="store_true",
                        help="also link a contents row whose label is already "
                             "identical to an unlinked section's")
    parser.add_argument(
        "--retract-entry-ids",
        help="comma-separated active TOC row ids; append an exact-tree revision "
             "that removes only those disproved overlay links",
    )
    args = parser.parse_args()
    if args.exact_label and args.retract_entry_ids:
        parser.error("--exact-label and --retract-entry-ids are mutually exclusive")
    global EXACT_LABELS
    EXACT_LABELS = args.exact_label
    retract_ids = ({int(v) for v in args.retract_entry_ids.split(",") if v.strip()}
                   if args.retract_entry_ids else set())
    wanted = ({int(v) for v in args.documents.split(",") if v.strip()}
              if args.documents else None)
    with connect() as conn, conn.cursor() as cur:
        if retract_ids:
            cur.execute("""
                SELECT i.id::text,i.document_id,array_agg(e.id ORDER BY e.id)
                  FROM instrument_toc_entry e
                  JOIN instrument i ON i.id=e.instrument_id
                                   AND i.is_active AND i.duplicate_of IS NULL
                 WHERE e.id = ANY(%s)
                 GROUP BY i.id,i.document_id
                 ORDER BY i.document_id,i.id::text
            """, (list(retract_ids),))
            targets = [(iid, doc, set(ids)) for iid, doc, ids in cur.fetchall()
                       if wanted is None or doc in wanted]
        else:
            cur.execute("""
                SELECT DISTINCT i.id::text,i.document_id
                  FROM v_toc_gap_pending g
                  JOIN instrument i ON i.id=g.instrument_id
                                   AND i.is_active AND i.duplicate_of IS NULL
                 ORDER BY i.document_id,i.id::text
            """)
            targets = [(iid, doc, None) for iid, doc in cur.fetchall()
                       if wanted is None or doc in wanted]

    plans = []
    skipped = []
    with only_one_run():
        for instrument_id, document_id, ids_here in targets:
            try:
                inst, plan = load_plan(instrument_id, ids_here)
            except ValueError as exc:
                if "no unambiguous typography links" not in str(exc):
                    skipped.append((document_id, str(exc)))
                continue
            plans.append(plan)
            if args.apply:
                segmenter = ("nizam.toc_typography_overlay_retraction/1"
                             if plan["retraction"] else SEGMENTER)
                new_id = legal_write.save(inst, segmenter)
                (body_page,toc_found,toc_entries,toc_matched,toc_missing,
                 toc_extra,toc_agreement,old_detail) = plan["old_run"]
                detail = dict(old_detail or {})
                linked = len(plan["links"])
                total = toc_entries or plan["toc_rows"]
                if plan["retraction"]:
                    matched = max(0, (toc_matched or 0) - linked)
                    missing = (toc_missing or 0) + linked
                    detail.update({
                        "exact_tree_overlay": True,
                        "toc_typography_links_retracted": plan["links"],
                        "retraction_reason": (
                            "rendered source disproves linked provision identity"
                        ),
                        "predecessor_instrument_id": plan["instrument_id"],
                    })
                else:
                    resolved = {link["printed_label"] for link in plan["links"]}
                    detail["missing"] = [
                        label for label in detail.get("missing", [])
                        if label not in resolved
                    ]
                    matched = min(total, (toc_matched or 0) + linked)
                    missing = max(0, (toc_missing or 0) - linked)
                    detail.update({
                        "exact_tree_overlay": True,
                        "toc_typography_links": plan["links"],
                        "predecessor_instrument_id": plan["instrument_id"],
                    })
                legal_write.record_run(
                    inst.document_id,inst.source_observation_id,new_id,segmenter,
                    "segmented",provisions=plan["provisions"],
                    sections=sum(r["kind"] == "section" for r in inst.provisions),
                    max_depth=max((r["path"].count(".") for r in inst.provisions),
                                  default=0),body_starts_page=body_page,
                    toc_found=toc_found,toc_entries=total,toc_matched=matched,
                    toc_missing=missing,
                    toc_extra=toc_extra,
                    toc_agreement=(matched/total if total else toc_agreement),
                    detail=detail,
                )
                plan["new_instrument_id"] = new_id
            print(
                f"doc={document_id} obs={plan['observation_id']} "
                f"links={len(plan['links'])} pending_after={plan['pending_after']} "
                f"tree={plan['provisions']} ledger={plan['ledger_rows']} "
                f"S7={plan['structural_candidates']}/"
                f"{plan['carried_adjudications']}decided"
            )
            for link in plan["links"]:
                print(f"  {link['printed_label']} -> {link['body_label']} "
                      f"(toc p{link['source_page']}, body p{link['first_page']})")
    print(f"{'applied' if args.apply else 'planned'} {len(plans)} exact-tree revisions, "
          f"{sum(len(p['links']) for p in plans)} links; skipped={len(skipped)}")
    for document_id, reason in skipped[:20]:
        print(f"  skip doc={document_id}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
