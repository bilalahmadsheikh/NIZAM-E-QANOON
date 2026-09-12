"""Materialize source-reviewed internal instruments without copying source text.

This tool is deliberately bounded to documents whose boundary sequences were
reviewed against their immutable text blocks.  Default mode is a read-only
build/report.  ``--apply`` replaces one single-tree interpretation atomically
with disjoint expression trees plus one complete document block ledger.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter

from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import SEGMENTER, build, infer_kind

METHOD = "nizam.multi_expression_materializer/1"

# These have an independently citable outer instrument followed by appendices.
PRIMARY_DOCUMENTS = {1106, 3389, 3553, 3696, 3912, 4434, 4452}
# These are editorial compilations, not themselves legal instruments.
COMPILATION_DOCUMENTS = {3423, 3949, 4440, 4497}
REVIEWED_DOCUMENTS = PRIMARY_DOCUMENTS | COMPILATION_DOCUMENTS
REJECTED_EDITORIAL_BOUNDARIES = {893415}
# The package contents is outside each legal expression span.  If the parser
# tries to discover a second contents list inside these spans, the opening run
# of enacted sections is itself mistaken for contents and discarded.  This is
# a source-reviewed property of the package, not a general parser heuristic.
NO_LOCAL_CONTENTS_DOCUMENTS = {4440}
# The Finance Act's contents embeds the new Tobacco Act's own section list, and
# the Act itself is inserted before the Finance Act resumes its appendices.
# Both legal expressions therefore own disjoint immutable spans.  These exact
# endpoints partition all 633 blocks and were checked against rendered pages
# 1, 14, 17 and 18; no text is copied or discarded.
REVIEWED_EXPRESSION_SPANS = {
    4452: {
        0: [(816322, 816330), (816332, 816490), (816545, 816954)],
        1: [(816331, 816331), (816491, 816544)],
    },
}
FORCED_EXPRESSION_CONTENTS = {(4452, 1)}
SOURCE_REVIEW_DETAILS = {
    4452: {
        "reviewed_pages": [1, 14, 17, 18],
        "reviewed_on": "2026-09-12",
        "source_facts": [
            "page_1_nests_the_tobacco_act_contents_under_finance_act_section_15",
            "page_14_prints_finance_act_section_15_then_tobacco_act_section_1",
            "page_17_ends_the_tobacco_act_at_section_9",
            "page_18_resumes_finance_act_appendix_I_with_section_3_cross_reference",
        ],
    },
}


def _title_tokens(value: str) -> set[str]:
    stop = {"the","of","and","act","ordinance","rule","rules","regulation",
            "regulations","order","notification"}
    return {token.casefold() for token in re.findall(r"[A-Za-z]{3,}",value or "")
            if token.casefold() not in stop}


def _clean_title(value: str) -> str:
    value = re.sub(r"^\s*\d+(?:\.\d+)+\s+", "", value or "")
    value = re.sub(r"\b\d+\*(?=(?:Act|Ordinance|Rules?|Regulations?|Order)\b)","",value,
                   flags=re.I)
    return re.sub(r"\s+"," ",value).strip(" \"'‘’")


def _expanded_start(blocks: list[dict], start: int, title: str) -> int:
    """Include a nearby printed title split from its formula anchor."""
    wanted = _title_tokens(title)
    if not wanted:
        return start
    best = start
    wanted_year = re.search(r"\b(?:18|19|20)\d{2}\b",title or "")
    for index in range(start-1,max(-1,start-8),-1):
        text = blocks[index]["text"] or ""
        if blocks[index]["id"] in REJECTED_EDITORIAL_BOUNDARIES:
            continue
        letters = [char for char in text if char.isalpha()]
        uppercase = (sum(char.isupper() for char in letters) / len(letters)
                     if letters else 0.0)
        have = _title_tokens(text)
        overlap = len(wanted & have) / len(wanted)
        title_like = uppercase >= 0.52 or (len(text) <= 180 and overlap >= 0.75)
        if (len(text) > 240 or not title_like
                or re.search(r"\b(?:in exercise|whereas|subject to)\b",text,re.I)):
            continue
        printed_year = re.search(r"\b(?:18|19|20)\d{2}\b",text)
        if (wanted_year and printed_year
                and wanted_year.group(0) != printed_year.group(0)):
            continue
        if (re.search(r"\b(?:act|ordinance|rules?|regulations?|order)\b",text,re.I)
                and overlap >= 0.55):
            best = index
            break
    return best


def _source_title(blocks: list[dict], start: int, detected: str) -> str:
    printed = re.sub(r"\s+"," ",blocks[start]["text"] or "").strip()
    printed = re.sub(r"^\d+(?=[A-Za-z])","",printed).strip()
    letters = [char for char in printed if char.isalpha()]
    uppercase = (sum(char.isupper() for char in letters) / len(letters)
                 if letters else 0.0)
    printed_tokens = _title_tokens(printed)
    detected_tokens = _title_tokens(detected)
    if (len(printed) <= 240 and uppercase >= 0.52
            and re.search(r"\b(?:act|ordinance|rules?|regulations?|order)\b",printed,re.I)
            and re.search(r"\b(?:18|19|20)\d{2}\b",printed)
            and len(printed_tokens & detected_tokens)
                / max(len(detected_tokens),1) >= 0.55
            and (len(printed_tokens) >= 0.7 * len(detected_tokens)
                 or "constitution" not in detected_tokens
                 or "constitution" in printed_tokens)):
        return printed
    return detected


def _same_nearby_expression(left: dict,right: dict) -> bool:
    if right["start"]-left["start"] > 2:
        return False
    if infer_kind(left["title"]) != infer_kind(right["title"]):
        return False
    left_year = re.findall(r"\b(?:18|19|20)\d{2}\b",left["title"])
    right_year = re.findall(r"\b(?:18|19|20)\d{2}\b",right["title"])
    if left_year and right_year and left_year[-1] != right_year[-1]:
        return False
    a,b = _title_tokens(left["title"]),_title_tokens(right["title"])
    return bool(a and b and len(a & b)/min(len(a),len(b)) >= 0.75)


def _next_estacode_item(blocks: list[dict],start: int,ceiling: int) -> int | None:
    for index in range(start+1,ceiling+1):
        raw = blocks[index]["text"] or ""
        if re.match(r"^\s*\d{1,2}\.\d{1,2}\s+",raw):
            return index
    return None


def _load(document_id: int,observation_id: int | None = None) -> tuple[dict, list[dict]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.id::text,i.source_observation_id,i.document_id,i.source_sha256,
                   i.jurisdiction::text,i.kind::text,i.number,i.year,i.short_title,
                   i.source_url,o.source_id,
                   coalesce(o.source_metadata->>'year',o.source_metadata->>'year_or_dept')
              FROM instrument i
              JOIN source_observation o ON o.id=i.source_observation_id
             WHERE i.document_id=%s AND i.is_active
               AND (%s::bigint IS NULL AND i.duplicate_of IS NULL
                    OR i.source_observation_id=%s)
             ORDER BY (i.expression_role='primary') DESC,i.expression_ordinal
        """, (document_id,observation_id,observation_id))
        rows = cur.fetchall()
        if not rows:
            raise ValueError(
                f"document {document_id} has no active canonical expression")
        names = ("instrument_id","source_observation_id","document_id","sha256",
                 "jurisdiction","kind","number","year","short_title","source_url",
                 "source_id","meta_year")
        outer = dict(zip(names,rows[0]))
        cur.execute("""SELECT count(*) FROM instrument_expression_manifest
                        WHERE source_observation_id=%s AND is_active""",
                    (outer["source_observation_id"],))
        already_materialized = cur.fetchone()[0] > 0
        if already_materialized:
            cur.execute("""
                SELECT coalesce(c.id::text,m.evidence->>'candidate_id'),
                       m.start_block_id,b.page_no,m.detected_title,
                       m.detected_kind::text,m.detected_year,m.detected_number,
                       coalesce(c.confidence,1.0),m.method,
                       jsonb_build_object(
                         'manifest_id',m.id,
                         'manifest_evidence',m.evidence,
                         'candidate_evidence',c.evidence)
                  FROM instrument_expression_manifest m
                  JOIN text_block b ON b.id=m.start_block_id
                  LEFT JOIN segmentation_boundary_candidate c
                    ON c.id=(m.evidence->>'candidate_id')::uuid
                 WHERE m.source_observation_id=%s AND m.is_active
                   AND m.expression_role='embedded'
                 ORDER BY m.expression_ordinal
            """, (outer["source_observation_id"],))
        else:
            cur.execute("""
            SELECT c.id::text,c.start_block_id,c.source_page,c.detected_title,
                   c.detected_kind,c.detected_year,c.detected_number,c.confidence,
                   c.method,c.evidence
              FROM v_boundary_adjudication_pending c
             WHERE c.instrument_id=%s
             ORDER BY (SELECT reading_order FROM text_block WHERE id=c.start_block_id),c.id
            """, (outer["instrument_id"],))
            if cur.rowcount == 0 and document_id == 4497:
                # A byte-identical official observation gets the same reviewed
                # expression manifest, then exact tree fingerprints decide its
                # duplicate representation.  Provenance is not collapsed.
                cur.execute("""
                    SELECT c.id::text,c.start_block_id,c.source_page,c.detected_title,
                           c.detected_kind,c.detected_year,c.detected_number,c.confidence,
                           c.method,c.evidence
                      FROM instrument_expression_manifest m
                      JOIN segmentation_boundary_candidate c
                        ON c.id=(m.evidence->>'candidate_id')::uuid
                     WHERE m.document_id=%s AND m.is_active
                     ORDER BY m.expression_ordinal
                """, (document_id,))
        boundary_names = ("candidate_id","start_block_id","source_page","title","kind",
                          "year","number","confidence","detector","evidence")
        boundaries = [dict(zip(boundary_names,row)) for row in cur.fetchall()]
        return outer,boundaries


def prepare(document_id: int,observation_id: int | None = None) -> tuple[list, list, list, list]:
    if document_id not in REVIEWED_DOCUMENTS:
        raise ValueError(f"document {document_id} is not in the source-reviewed allow-list")
    outer,boundaries = _load(document_id,observation_id)
    if not boundaries:
        raise ValueError(f"document {document_id} has no pending source boundary evidence")
    blocks = legal_write.blocks_for(document_id)
    position = {block["id"]: index for index,block in enumerate(blocks)}
    if any(boundary["start_block_id"] not in position for boundary in boundaries):
        raise ValueError("a boundary does not belong to the active document")
    # Collapse multiple detector records anchored to the same immutable block.
    unique: list[dict] = []
    seen: set[int] = set()
    for boundary in boundaries:
        if boundary["start_block_id"] in REJECTED_EDITORIAL_BOUNDARIES:
            continue
        if boundary["start_block_id"] not in seen:
            unique.append(boundary)
            seen.add(boundary["start_block_id"])
    boundaries = unique

    specifications: list[dict] = []
    if document_id in PRIMARY_DOCUMENTS:
        specifications.append({
            "title": outer["short_title"], "year": outer["year"],
            "kind": outer["kind"], "number": outer["number"],
            "start": 0, "role": "primary", "candidate": None,
        })
    for boundary in boundaries:
        start = _expanded_start(blocks,position[boundary["start_block_id"]],
                                boundary["title"])
        specifications.append({
            "title": _clean_title(_source_title(blocks,start,boundary["title"])),
            "year": boundary["year"],
            "kind": infer_kind(boundary["title"]), "number": boundary["number"],
            "start": start,
            "role": "embedded",
            "candidate": boundary,
        })
    specifications.sort(key=lambda value: value["start"])
    collapsed: list[dict] = []
    for spec in specifications:
        if collapsed and collapsed[-1]["start"] == spec["start"]:
            old = collapsed[-1]
            old_confidence = (old["candidate"] or {}).get("confidence",1.0)
            new_confidence = (spec["candidate"] or {}).get("confidence",1.0)
            old_tokens,new_tokens = _title_tokens(old["title"]),_title_tokens(spec["title"])
            prefer_new_title = (
                len(new_tokens) > len(old_tokens)
                or (len(new_tokens) == len(old_tokens)
                    and re.match(r"^\d",old["title"])
                    and not re.match(r"^\d",spec["title"])))
            if prefer_new_title:
                old["title"] = spec["title"]
                old["candidate"] = spec["candidate"]
                old["year"] = spec["year"]
                old["kind"] = spec["kind"]
                old["number"] = spec["number"]
            elif new_confidence > old_confidence:
                old["candidate"] = spec["candidate"]
            continue
        exact_nearby_title = bool(
            collapsed
            and spec["start"]-collapsed[-1]["start"] <= 2
            and re.sub(r"[^a-z0-9]+","",spec["title"].casefold())
                == re.sub(r"[^a-z0-9]+","",collapsed[-1]["title"].casefold()))
        if collapsed and (exact_nearby_title
                          or _same_nearby_expression(collapsed[-1],spec)):
            old = collapsed[-1]
            # Keep the earliest printed-title anchor and the more complete
            # source title.  Both candidate ids remain in the immutable queue;
            # the manifest materialises their one shared legal expression.
            if len(_title_tokens(spec["title"])) > len(_title_tokens(old["title"])):
                old["title"] = spec["title"]
                old["candidate"] = spec["candidate"]
            continue
        collapsed.append(spec)
    specifications = collapsed

    as_at = legal_write.observed_on(outer["source_observation_id"])
    patches = legal_write.segmentation_patches_for(outer["source_observation_id"])
    insts = []
    segs = []
    manifests = []
    for ordinal,spec in enumerate(specifications):
        end = (specifications[ordinal + 1]["start"] - 1
               if ordinal + 1 < len(specifications) else len(blocks) - 1)
        if document_id == 4497:
            next_item = _next_estacode_item(blocks,spec["start"],end)
            if next_item is not None:
                end = next_item-1
            # The official contents puts item 2.14 (Postal Group) at printed
            # page 68 / PDF page 75, but its heading is absent from extraction.
            # The preceding Police Rules schedule ends at block 886063; source
            # blocks 886064 onward are editorial apparatus for later items.
            if spec["title"].startswith("Police Service of Pakistan"):
                end = min(end,position[886063])
        reviewed_spans = REVIEWED_EXPRESSION_SPANS.get(document_id, {}).get(ordinal)
        span_ranges = ([(position[first], position[last])
                        for first,last in reviewed_spans]
                       if reviewed_spans else [(spec["start"], end)])
        span = [block for first,last in span_ranges
                for block in blocks[first:last + 1]]
        if not span:
            raise ValueError(f"empty source span for expression {ordinal}")
        inst,seg = build(
            document_id,outer["sha256"],outer["source_observation_id"],
            outer["source_id"],spec["title"],
            str(spec["year"] or outer["meta_year"] or ""),outer["source_url"],
            span,as_at,patches,expression_ordinal=ordinal,
            expression_role=spec["role"],
            detect_contents=document_id not in NO_LOCAL_CONTENTS_DOCUMENTS,
            force_opening_contents=(document_id, ordinal)
                in FORCED_EXPRESSION_CONTENTS)
        if not inst.provisions:
            raise ValueError(
                f"expression {ordinal} ({spec['title']!r}, blocks "
                f"{span[0]['id']}..{span[-1]['id']}, pages "
                f"{span[0]['page_no']}..{span[-1]['page_no']}) produced no provisions")
        insts.append(inst)
        segs.append(seg)
        candidate = spec["candidate"]
        evidence = {
            "source_review": "independent legal formula and self-naming section/rule reset",
            "candidate_id": candidate["candidate_id"] if candidate else None,
            "candidate_method": candidate["detector"] if candidate else None,
            "candidate_evidence": candidate["evidence"] if candidate else None,
            "span_block_count": len(span),
            "span_first_page": span[0]["page_no"],
            "span_last_page": span[-1]["page_no"],
            "source_spans": [
                {
                    "start_block_id": blocks[first]["id"],
                    "end_block_id": blocks[last]["id"],
                    "first_page": blocks[first]["page_no"],
                    "last_page": blocks[last]["page_no"],
                }
                for first,last in span_ranges if first <= last
            ],
        }
        evidence.update(SOURCE_REVIEW_DETAILS.get(document_id, {}))
        manifests.append({
            "expression_ordinal": ordinal,
            "expression_role": spec["role"],
            "start_block_id": span[0]["id"],
            "end_block_id": span[-1]["id"],
            "detected_title": spec["title"],
            "detected_kind": inst.kind,
            "detected_year": inst.year,
            "detected_number": inst.number,
            "review_basis": "source_verified",
            "method": METHOD,
            "evidence": evidence,
            "spans": [
                {
                    "start_block_id": blocks[first]["id"],
                    "end_block_id": blocks[last]["id"],
                }
                for first,last in span_ranges if first <= last
            ],
        })
    return insts,segs,manifests,blocks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document",type=int,action="append",required=True)
    parser.add_argument("--observation",type=int,
                        help="materialize one provenance observation of a shared blob")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--summary-only",action="store_true")
    args = parser.parse_args()
    report = []
    for document_id in args.document:
        started = time.time()
        insts,segs,manifests,blocks = prepare(document_id,args.observation)
        item = {
            "document_id": document_id,
            "source_observation_id": insts[0].source_observation_id,
            "expressions": [{
                "ordinal": inst.expression_ordinal,
                "role": inst.expression_role,
                "title": inst.short_title,
                "kind": inst.kind,
                "year": inst.year,
                "first_block": inst.source_start_block_id,
                "last_block": inst.source_end_block_id,
                "first_page": min(row["first_page"] for row in inst.provisions
                                  if row["first_page"] is not None),
                "last_page": max(row["last_page"] for row in inst.provisions
                                 if row["last_page"] is not None),
                "provisions": len(inst.provisions),
                "provision_kinds": dict(sorted(Counter(
                    row["kind"] for row in inst.provisions
                ).items())),
                "top_level_citable_labels": [
                    row["label"] for row in inst.provisions
                    if row["parent_key"] is None
                    and row["kind"] in {"section", "article"}
                ],
                "s7_candidates": len(inst.structural_decisions),
                "toc_found": seg.toc_found,
                "toc_missing": len(seg.missing) if seg.toc else 0,
                "toc_missing_labels": seg.missing if seg.toc else [],
                "toc_unmatched_entries": [
                    {
                        "ordinal": entry["ordinal"],
                        "label": entry["label"],
                        "heading": entry["heading"],
                        "kind": entry["kind"],
                        "source_page": entry.get("source_page"),
                    }
                    for entry in seg.toc_entries if entry.get("node") is None
                ],
                "unassigned_blocks": sum(1 for row in inst.block_roles
                                         if row[1] == "unassigned"),
            } for inst,seg in zip(insts,segs)],
            "document_blocks": len(blocks),
            "expression_blocks": sum(len(inst.block_roles) for inst in insts),
            "apparatus_blocks": len(blocks)-sum(len(inst.block_roles) for inst in insts),
            "applied": args.apply,
        }
        if args.apply:
            ids = legal_write.save_many(insts,blocks,manifests,METHOD)
            for inst,seg,instrument_id in zip(insts,segs,ids):
                legal_write.record_run(
                    document_id,inst.source_observation_id,instrument_id,METHOD,"segmented",
                    provisions=len(inst.provisions),
                    sections=sum(1 for row in inst.provisions if row["kind"] == "section"),
                    max_depth=max((row["path"].count(".") for row in inst.provisions),default=0),
                    body_starts_page=seg.body_starts_page,toc_found=seg.toc_found,
                    toc_entries=len(seg.toc_entries) or None,
                    toc_matched=seg.matched if seg.toc else None,
                    toc_missing=len(seg.missing) if seg.toc else None,
                    toc_extra=len(seg.extra) if seg.toc else None,
                    toc_agreement=round(seg.agreement,4) if seg.toc else None,
                    detail={"missing":seg.missing[:60],"extra":seg.extra[:60],
                            "blocks_total":len(inst.block_roles),
                            "repeated_labels_demoted":seg.repeated_labels_demoted,
                            "schedule_sections_retyped":seg.schedule_sections_retyped,
                            "detached_heading_bodies_merged":seg.detached_heading_bodies_merged,
                            "curation_patches_applied":seg.curation_patches_applied,
                            "multi_expression":True,
                            "expression_ordinal":inst.expression_ordinal},
                    duration_ms=int((time.time()-started)*1000))
            item["instrument_ids"] = ids
        report.append(item)
    if args.summary_only:
        report = [{
            "document_id":item["document_id"],
            "source_observation_id":item["source_observation_id"],
            "expressions":len(item["expressions"]),
            "provisions":sum(value["provisions"] for value in item["expressions"]),
            "s7_candidates":sum(value["s7_candidates"] for value in item["expressions"]),
            "document_blocks":item["document_blocks"],
            "expression_blocks":item["expression_blocks"],
            "apparatus_blocks":item["apparatus_blocks"],
            "applied":item["applied"],
        } for item in report]
    print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
