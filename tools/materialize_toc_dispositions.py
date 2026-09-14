"""Append exact-tree revisions containing only source-reviewed omitted sections.

Re-running the evolving general segmenter would rewrite unrelated structures in
large compilations.  This overlay instead copies the active legal tree and its
block ledger exactly, adds only reviewed operation='omitted' nodes, and carries
each existing S7 candidate/adjudication with explicit provenance.  No corpus
row is deleted; the ordinary writer retires the predecessor atomically.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict

from nizam.shared.corpus_types import SegmentedInstrument
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import only_one_run


SEGMENTER = "nizam.toc_disposition_overlay/1"


def slug(value: str) -> str:
    return (re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "x")[:40]


def load_plan(observation_id: int) -> tuple[SegmentedInstrument, dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id::text,document_id,source_sha256,jurisdiction::text,kind::text,
                   number,year,short_title,long_title,preamble,source_url,
                   extraction_conf,expression_ordinal,source_start_block_id,
                   source_end_block_id,expression_role
              FROM instrument
             WHERE source_observation_id=%s AND is_active
               AND duplicate_of IS NULL
        """, (observation_id,))
        instrument_rows = cur.fetchall()
        if len(instrument_rows) != 1:
            raise ValueError(
                f"observation {observation_id}: expected one active canonical "
                f"expression, found {len(instrument_rows)}"
            )
        (instrument_id,document_id,sha256,jurisdiction,kind,number,year,
         short_title,long_title,preamble,source_url,confidence,
         expression_ordinal,start_block,end_block,expression_role) = instrument_rows[0]

        cur.execute("SELECT count(*) FROM toc_gap_adjudication WHERE instrument_id=%s",
                    (instrument_id,))
        if cur.fetchone()[0]:
            raise ValueError("exact overlay refuses instruments with TOC adjudications")

        cur.execute("""
            SELECT id,source_observation_id,expression_ordinal,toc_entry_ordinal,
                   printed_label,printed_heading,disposition,source_block_id,
                   source_page,amending_instrument_id::text,
                   amending_instrument_citation,evidence,reviewed_by,reviewed_at
              FROM v_toc_disposition_assertion_latest
             WHERE source_observation_id=%s AND expression_ordinal=%s
               AND NOT EXISTS (
                   SELECT 1
                     FROM provision_version pv
                     JOIN provision p ON p.id=pv.provision_id AND p.is_active
                     JOIN instrument materialised
                       ON materialised.id=p.instrument_id
                      AND materialised.is_active
                      AND materialised.duplicate_of IS NULL
                    WHERE pv.source_toc_disposition_assertion_id=
                          v_toc_disposition_assertion_latest.id
               )
             ORDER BY toc_entry_ordinal,id
        """, (observation_id, expression_ordinal))
        assertion_keys = ("id","source_observation_id","expression_ordinal",
                          "toc_entry_ordinal","printed_label","printed_heading",
                          "disposition","source_block_id","source_page",
                          "amending_instrument_id","amending_instrument_citation",
                          "evidence","reviewed_by","reviewed_at")
        assertions = [dict(zip(assertion_keys, row)) for row in cur.fetchall()]
        if not assertions:
            raise ValueError(f"observation {observation_id}: no disposition assertions")

        cur.execute("""
            SELECT p.id::text,p.parent_id::text,p.path::text,p.kind::text,p.label,
                   p.heading,p.marginal_note,p.ordinal,p.first_page,p.last_page,
                   p.first_block,pv.text_en,pv.operation::text,pv.amended_by_id::text,
                   pv.amendment_note,pv.source_toc_disposition_assertion_id
              FROM provision p
              LEFT JOIN provision_version pv ON pv.provision_id=p.id
             WHERE p.instrument_id=%s AND p.is_active
             ORDER BY p.ordinal
        """, (instrument_id,))
        node_rows = cur.fetchall()
        nodes: dict[str, dict] = {}
        for row in node_rows:
            (node_id,parent_id,path,node_kind,label,heading,marginal_note,ordinal,
             first_page,last_page,first_block,text,operation,amended_by_id,
             amendment_note,assertion_id) = row
            if node_id in nodes:
                raise ValueError(
                    f"instrument {instrument_id}: provision {node_id} has "
                    "more than one version; exact overlay cannot choose one"
                )
            nodes[node_id] = {
                "id": node_id, "parent": parent_id, "path": path,
                "kind": node_kind, "label": label, "heading": heading,
                "marginal_note": marginal_note, "old_ordinal": ordinal,
                "first_page": first_page, "last_page": last_page,
                "first_block": first_block, "text": text,
                "operation": operation or "original",
                "amended_by_id": amended_by_id,
                "amendment_note": amendment_note,
                "toc_disposition_assertion_id": assertion_id,
            }

        cur.execute("""
            SELECT id,ordinal,printed_label,printed_heading,entry_kind,
                   source_block_id,source_page,provision_id::text,match_method
              FROM instrument_toc_entry WHERE instrument_id=%s ORDER BY ordinal,id
        """, (instrument_id,))
        toc = [{
            "id": row[0], "ordinal": row[1], "label": row[2], "heading": row[3],
            "kind": row[4], "source_block_id": row[5], "source_page": row[6],
            "node_id": row[7], "method": row[8],
        } for row in cur.fetchall()]
        dangling_toc = [entry["id"] for entry in toc
                        if entry["node_id"] is not None
                        and entry["node_id"] not in nodes]
        if dangling_toc:
            raise ValueError(
                f"instrument {instrument_id}: TOC rows reference provisions "
                f"outside the active tree: {dangling_toc[:5]}"
            )

        cur.execute("""
            SELECT pb.block_id,pb.role::text,pb.provision_id::text,pb.chars
              FROM provision_block pb
              JOIN block_assignment_set s ON s.id=pb.assignment_set_id
             WHERE s.source_observation_id=%s AND s.is_active
             ORDER BY pb.block_id
        """, (observation_id,))
        ledger_source = cur.fetchall()

        cur.execute("""
            SELECT c.id::text,c.candidate_provision_id::text,
                   c.canonical_provision_id::text,c.parent_provision_id::text,
                   c.decision_kind,c.original_kind::text,c.printed_label,
                   c.source_block_id,c.source_page,c.canonical_source_block_id,
                   c.canonical_source_page,c.proposed_resolution,c.evidence,
                   a.id::text,a.resolution,a.review_basis,a.rationale,a.evidence,
                   a.candidate_id::text
              FROM segmentation_structural_candidate c
              LEFT JOIN v_structural_adjudication_latest a ON a.candidate_id=c.id
             WHERE c.instrument_id=%s ORDER BY c.created_at,c.id
        """, (instrument_id,))
        candidate_rows = cur.fetchall()

        cur.execute("""
            SELECT body_starts_page,toc_found,toc_entries,toc_matched,
                   toc_missing,toc_extra,toc_agreement,detail
              FROM segmentation_run WHERE instrument_id=%s
             ORDER BY run_at DESC,id DESC LIMIT 1
        """, (instrument_id,))
        old_run = cur.fetchone()
        if old_run is None:
            raise ValueError(f"instrument {instrument_id}: no predecessor run")

    children: dict[str | None, list[str]] = defaultdict(list)
    for node in sorted(nodes.values(), key=lambda item: item["old_ordinal"]):
        children[node["parent"]].append(node["id"])
    used_paths = {node["path"] for node in nodes.values()}

    def section_neighbour(index: int, step: int):
        cursor = index + step
        while 0 <= cursor < len(toc):
            node_id = toc[cursor]["node_id"]
            if node_id is not None and nodes[node_id]["kind"] in {"section", "article"}:
                return cursor, nodes[node_id]
            cursor += step
        return None, None

    def structural_between(start: int | None, stop: int | None) -> bool:
        if start is None or stop is None:
            return False
        low, high = sorted((start, stop))
        return any(
            item["node_id"] is not None
            and nodes[item["node_id"]]["kind"] in {
                "part", "chapter", "division", "schedule", "appendix",
            }
            for item in toc[low + 1:high]
        )

    additions = []
    for assertion in assertions:
        matching = [
            (index, entry) for index, entry in enumerate(toc)
            if entry["source_block_id"] == assertion["source_block_id"]
            and entry["label"].replace(" ", "").casefold()
                == assertion["printed_label"].replace(" ", "").casefold()
        ]
        if len(matching) != 1:
            raise ValueError(
                f"assertion {assertion['id']} matches {len(matching)} current TOC rows"
            )
        index, entry = matching[0]
        if entry["node_id"] is not None:
            raise ValueError(f"assertion {assertion['id']} TOC row is already resolved")

        prior_index, prior = section_neighbour(index, -1)
        next_index, following = section_neighbour(index, 1)
        prior_parent = prior["parent"] if prior else None
        next_parent = following["parent"] if following else None
        if prior_parent == next_parent:
            parent = prior_parent
            parent_basis = "same_parent_neighbours"
        elif structural_between(prior_index, index) and following is not None:
            parent = next_parent
            parent_basis = "preceding_structural_boundary"
        elif structural_between(index, next_index) and prior is not None:
            parent = prior_parent
            parent_basis = "following_structural_boundary"
        elif following is None:
            parent = prior_parent
            parent_basis = "prior_neighbour"
        elif prior is None:
            parent = next_parent
            parent_basis = "following_neighbour"
        else:
            prior_distance = index - int(prior_index)
            next_distance = int(next_index) - index
            parent = prior_parent if prior_distance <= next_distance else next_parent
            parent_basis = "nearest_neighbour"

        local_id = f"disposition:{assertion['id']}"
        if parent is None:
            root_candidates = [node for node in nodes.values() if node["parent"] is None]
            if not root_candidates:
                raise ValueError("cannot derive instrument path prefix")
            parent_path = min(root_candidates, key=lambda n: n["old_ordinal"])[
                "path"].rsplit(".", 1)[0]
        else:
            parent_path = nodes[parent]["path"]
        base_path = f"{parent_path}.s_{slug(entry['label'])}"
        path = base_path
        suffix = 1
        while path in used_paths:
            path = f"{base_path}_disp_{assertion['id']}_{suffix}"
            suffix += 1
        used_paths.add(path)
        nodes[local_id] = {
            "id": local_id, "parent": parent, "path": path, "kind": "section",
            "label": entry["label"], "heading": None, "marginal_note": None,
            "old_ordinal": 10**9 + entry["ordinal"],
            "first_page": assertion["source_page"],
            "last_page": assertion["source_page"],
            "first_block": assertion["source_block_id"], "text": None,
            "operation": "omitted",
            "amended_by_id": assertion["amending_instrument_id"],
            "amendment_note": assertion["printed_heading"],
            "toc_disposition_assertion_id": assertion["id"],
        }
        siblings = children[parent]
        following_sibling = next((
            item["node_id"] for item in toc[index + 1:]
            if item["node_id"] is not None
            and nodes[item["node_id"]]["parent"] == parent
            and item["node_id"] in siblings
        ), None)
        if following_sibling is not None:
            siblings.insert(siblings.index(following_sibling), local_id)
        else:
            prior_sibling = next((
                item["node_id"] for item in reversed(toc[:index])
                if item["node_id"] is not None
                and nodes[item["node_id"]]["parent"] == parent
                and item["node_id"] in siblings
            ), None)
            if prior_sibling is None:
                siblings.append(local_id)
            else:
                siblings.insert(siblings.index(prior_sibling) + 1, local_id)
        entry["node_id"] = local_id
        entry["method"] = "source_verified_disposition"
        additions.append({
            "assertion_id": assertion["id"], "label": entry["label"],
            "parent": parent, "parent_basis": parent_basis, "path": path,
            "source_page": assertion["source_page"],
        })

    ordered_ids: list[str] = []
    def walk(parent: str | None):
        for node_id in children[parent]:
            ordered_ids.append(node_id)
            walk(node_id)
    walk(None)
    if len(ordered_ids) != len(nodes):
        raise ValueError("tree traversal did not retain every provision")
    keys = {node_id: key for key, node_id in enumerate(ordered_ids)}
    provisions = []
    for ordinal, node_id in enumerate(ordered_ids):
        node = nodes[node_id]
        provisions.append({
            "key": keys[node_id],
            "parent_key": keys.get(node["parent"]), "path": node["path"],
            "kind": node["kind"], "label": node["label"],
            "heading": node["heading"], "marginal_note": node["marginal_note"],
            "ordinal": ordinal, "first_page": node["first_page"],
            "last_page": node["last_page"], "first_block": node["first_block"],
            "text": node["text"], "operation": node["operation"],
            "amended_by_id": node["amended_by_id"],
            "amendment_note": node["amendment_note"],
            "toc_disposition_assertion_id": node["toc_disposition_assertion_id"],
        })
    dangling_blocks = [block_id for block_id, _role, provision_id, _chars
                       in ledger_source
                       if provision_id is not None and provision_id not in keys]
    if dangling_blocks:
        raise ValueError(
            f"instrument {instrument_id}: active ledger references provisions "
            f"outside the copied tree: {dangling_blocks[:5]}"
        )
    block_roles = [
        (block_id, role, keys.get(provision_id), chars)
        for block_id, role, provision_id, chars in ledger_source
    ]
    toc_rows = [{
        "ordinal": entry["ordinal"], "label": entry["label"],
        "heading": entry["heading"], "kind": entry["kind"],
        "source_block_id": entry["source_block_id"],
        "source_page": entry["source_page"],
        "provision_key": keys.get(entry["node_id"]), "method": entry["method"],
    } for entry in toc]

    structural = []
    for row in candidate_rows:
        (candidate_id,candidate_pid,canonical_pid,parent_pid,decision_kind,
         original_kind,printed_label,source_block_id,source_page,
         canonical_block,canonical_page,proposed,evidence,adj_id,resolution,
         review_basis,rationale,adj_evidence,adj_candidate_id) = row
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
        document_id=document_id,source_observation_id=observation_id,sha256=sha256,
        jurisdiction=jurisdiction,kind=kind,number=number,year=year,
        short_title=short_title,long_title=long_title,preamble=preamble,
        source_url=source_url,as_at=legal_write.observed_on(observation_id),
        confidence=confidence,provisions=provisions,toc_entries=toc_rows,
        block_roles=block_roles,structural_decisions=structural,
        expression_ordinal=expression_ordinal,source_start_block_id=start_block,
        source_end_block_id=end_block,expression_role=expression_role,
        copy_instrument_id=instrument_id,
    )
    unresolved_entries = [entry for entry in toc_rows
                          if entry["provision_key"] is None]
    unresolved_labels = {entry["label"] for entry in unresolved_entries}
    old_detail = dict(old_run[7] or {})
    old_missing = list(old_detail.get("missing") or [])
    resolved_labels = {addition["label"] for addition in additions}
    # Preserve predecessor run-only gaps, but remove a label only when this
    # overlay resolved every current TOC occurrence carrying that label.
    remaining_run_missing = [
        label for label in old_missing
        if label not in resolved_labels or label in unresolved_labels
    ]
    pending_after = len(unresolved_entries)
    plan = {
        "observation_id": observation_id, "document_id": document_id,
        "instrument_id": instrument_id, "provisions_before": len(node_rows),
        "provisions_after": len(provisions), "assertions": len(assertions),
        "toc_pending_after": pending_after,
        "structural_candidates": len(structural),
        "carried_adjudications": sum(
            "carried_adjudication" in item for item in structural),
        "ledger_rows": len(ledger_source), "toc_rows": len(toc_rows),
        "remaining_run_missing": remaining_run_missing,
        "additions": additions, "old_run": old_run,
    }
    return inst, plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", help="comma-separated bounded set")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--show-nontrivial", action="store_true",
                        help="print additions not bracketed by same-parent TOC rows")
    args = parser.parse_args()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT a.source_observation_id
              FROM v_toc_disposition_assertion_latest a
             WHERE NOT EXISTS (
                 SELECT 1
                   FROM provision_version pv
                   JOIN provision p ON p.id=pv.provision_id AND p.is_active
                   JOIN instrument i ON i.id=p.instrument_id
                                    AND i.is_active
                                    AND i.duplicate_of IS NULL
                  WHERE pv.source_toc_disposition_assertion_id=a.id
             )
             ORDER BY 1
        """)
        available = [row[0] for row in cur.fetchall()]
    selected = ({int(value) for value in args.observations.split(",") if value.strip()}
                if args.observations else set(available))
    targets = [value for value in available if value in selected]
    if selected - set(targets):
        raise SystemExit(f"unknown assertion observations: {sorted(selected-set(targets))}")

    plans = []
    skipped: list[tuple[int, str]] = []
    with only_one_run():
        for observation_id in targets:
            try:
                inst, plan = load_plan(observation_id)
            except ValueError as exc:
                # One observation that the exact overlay refuses -- most often
                # because its instrument already carries TOC adjudications --
                # used to abort the whole run, so a single unusable target
                # blocked every other assertion from being materialised. Record
                # it and carry on; the refusal is still visible in the summary.
                skipped.append((observation_id, str(exc)))
                continue
            plans.append(plan)
            if args.apply:
                new_id = legal_write.save(inst, SEGMENTER)
                (body_page,toc_found,old_toc_entries,old_toc_matched,
                 old_toc_missing,toc_extra,old_toc_agreement,
                 old_detail) = plan["old_run"]
                detail = dict(old_detail or {})
                detail["missing"] = plan["remaining_run_missing"]
                detail.update({
                    "exact_tree_overlay": True,
                    "toc_dispositions_materialised": plan["assertions"],
                    "predecessor_instrument_id": plan["instrument_id"],
                })
                sections = sum(row["kind"] == "section" for row in inst.provisions)
                max_depth = max((row["path"].count(".") for row in inst.provisions),
                                default=0)
                toc_total = len(inst.toc_entries)
                toc_missing = len(plan["remaining_run_missing"])
                resolved_run_missing = max(0, (old_toc_missing or 0)-toc_missing)
                toc_matched = min(
                    toc_total,
                    (old_toc_matched or 0) + resolved_run_missing,
                )
                legal_write.record_run(
                    inst.document_id,inst.source_observation_id,new_id,SEGMENTER,
                    "segmented",provisions=len(inst.provisions),sections=sections,
                    max_depth=max_depth,body_starts_page=body_page,
                    toc_found=toc_found,toc_entries=old_toc_entries or toc_total,
                    toc_matched=toc_matched,toc_missing=toc_missing,
                    toc_extra=toc_extra,
                    toc_agreement=(toc_matched/(old_toc_entries or toc_total)
                                   if (old_toc_entries or toc_total) else
                                   old_toc_agreement),detail=detail,
                )
                plan["new_instrument_id"] = new_id
            if args.compact:
                print(
                    f"obs={observation_id} doc={plan['document_id']} "
                    f"assertions={plan['assertions']} "
                    f"provisions={plan['provisions_before']}->{plan['provisions_after']} "
                    f"pending_after={plan['toc_pending_after']} "
                    f"S7={plan['structural_candidates']}/"
                    f"{plan['carried_adjudications']}decided"
                )
            if args.show_nontrivial:
                for addition in plan["additions"]:
                    if addition["parent_basis"] != "same_parent_neighbours":
                        print(json.dumps({
                            "observation_id": observation_id,
                            **addition,
                        }, ensure_ascii=False, default=str))
    if not args.compact:
        print(json.dumps(plans,ensure_ascii=False,indent=2,default=str))
    basis_counts: dict[str, int] = defaultdict(int)
    for plan in plans:
        for addition in plan["additions"]:
            basis_counts[addition["parent_basis"]] += 1
    print("parent bases: " + ", ".join(
        f"{key}={value}" for key, value in sorted(basis_counts.items())))
    print(
        "totals: "
        f"assertions={sum(p['assertions'] for p in plans)} "
        f"provisions={sum(p['provisions_before'] for p in plans)}->"
        f"{sum(p['provisions_after'] for p in plans)} "
        f"S7={sum(p['structural_candidates'] for p in plans)}/"
        f"{sum(p['carried_adjudications'] for p in plans)}decided"
    )
    for observation_id, reason in skipped:
        print(f"  skip observation {observation_id}: {reason}")
    print(f"{'applied' if args.apply else 'planned'} {len(plans)} exact-tree revisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
