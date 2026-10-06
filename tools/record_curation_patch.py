"""Record a source-verified parser-input correction read from the official page.

`segmentation_curation_patch` (migration 0025) corrects the text the parser
reads, never `text_block`: extracted evidence stays immutable, and a replay of
the one document applies the patch. This is the lane for a printed number the
text layer misread -- "2IF" for 21F, "5." for 55. -- where linking the contents
row to the misnumbered node would render a wrong section number (INV-1).

    python tools/record_curation_patch.py --readings FILE.json          dry run
    python tools/record_curation_patch.py --readings FILE.json --apply  record

A reading:

    {"document_id": 4225, "page_no": 47,
     "match_text": "Remissions.__ Notwithstanding anything",   # >= 12 chars, unique on the page
     "before_text": "2IF. Remissions", "after_text": "21F. Remissions",
     "extracted_number": "2IF", "printed_number": "21F",
     "observed": "Page 47 prints '21F. Remissions.__ ...'",
     "render": ".artifacts/.../page-47.png", "render_sha256": "..."}

The dry run applies the locator exactly as the segmenter will (page plus a
case-insensitive fragment matching one block, `before_text` occurring once in
it) and refuses anything ambiguous. After --apply, replay the document with
`python -m nizam.workers.segment --document N --redo` (dry-run it first).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import owner_decision_answer, unnumbered_opener_shape_ok

CREATED_BY = "claude.ocr-digit-review/3"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readings", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--created-by", default=CREATED_BY,
                    help="reviewer identifier stored with newly accepted readings")
    a = ap.parse_args()
    readings = json.loads(pathlib.Path(a.readings).read_text(encoding="utf-8"))
    if isinstance(readings, dict):
        readings = [readings]

    planned, refused = [], []
    with connect() as conn, conn.cursor() as cur:
        for r in readings:
            doc = r.get("document_id")
            where = f"doc {doc} p{r.get('page_no')} {r.get('before_text')!r}"
            observed = (r.get("observed") or "").strip()
            if len(observed) < 40:
                refused.append((where, "no observation: say what the page shows"))
                continue
            match, before, after = (r.get("match_text") or "", r.get("before_text") or "",
                                    r.get("after_text") or "")
            body_start = r.get("source_body_start_block")
            apparatus = r.get("source_apparatus_blocks")
            reparents = r.get("source_reparent_blocks")
            continuations = r.get("source_continuation_parent_blocks")
            unnumbered_openers = r.get("source_unnumbered_section_openers")
            unnumbered_parts = r.get("source_unnumbered_part_headings")
            schedule_rows = r.get("source_schedule_row_openers")
            form_group = r.get("source_schedule_form_group")
            if reparents is not None and not (
                    isinstance(reparents, list) and reparents
                    and all(isinstance(v, dict)
                            and type(v.get("source_block_id")) is int
                            and type(v.get("parent_block_id")) is int
                            and v.get("kind") in (
                                "clause", "subsection", "explanation", "proviso")
                            and (v["source_block_id"] != v["parent_block_id"]
                                 or (v.get("source_label") is not None
                                     and v.get("parent_label") is not None))
                            for v in reparents)):
                refused.append((where, "source_reparent_blocks must be a list of "
                                       "{source_block_id, parent_block_id, kind "
                                       "clause|subsection|explanation|proviso} objects"))
                continue
            if continuations is not None and not (
                    isinstance(continuations, list) and continuations
                    and all(isinstance(v, dict)
                            and set(v) == {"source_block_id", "parent_block_id"}
                            and type(v["source_block_id"]) is int
                            and type(v["parent_block_id"]) is int
                            and v["source_block_id"] != v["parent_block_id"]
                            for v in continuations)
                    and len({v["source_block_id"] for v in continuations})
                    == len(continuations)):
                refused.append((where, "source_continuation_parent_blocks must "
                                       "name distinct source and parent block ids"))
                continue
            if unnumbered_openers is not None and not (
                    isinstance(unnumbered_openers, list) and unnumbered_openers
                    and all(unnumbered_opener_shape_ok(v) for v in unnumbered_openers)
                    and len({v["source_block_id"] for v in unnumbered_openers})
                    == len(unnumbered_openers)):
                refused.append((where, "source_unnumbered_section_openers must "
                                       "name distinct blocks and source-backed labels/headings"))
                continue
            # An opener that numbers an unnumbered paragraph cites the owner's
            # decision; the export must hold that answer (profile rule
            # `unnumbered_root_provision`).
            try:
                for v in unnumbered_openers or []:
                    if "owner_decision" in v:
                        owner_decision_answer(v["owner_decision"], doc)
            except ValueError as error:
                refused.append((where, str(error)))
                continue
            if unnumbered_parts is not None and not (
                    isinstance(unnumbered_parts, list) and unnumbered_parts
                    and all(isinstance(v, dict)
                            and set(v) == {"source_block_id", "heading"}
                            and type(v["source_block_id"]) is int
                            and isinstance(v["heading"], str) and v["heading"].strip()
                            for v in unnumbered_parts)
                    and len({v["source_block_id"] for v in unnumbered_parts})
                    == len(unnumbered_parts)):
                refused.append((where, "source_unnumbered_part_headings must "
                                       "name distinct source blocks and printed headings"))
                continue
            if schedule_rows is not None and not (
                    isinstance(schedule_rows, list) and schedule_rows
                    and all(isinstance(v, dict)
                            and set(v) == {"source_block_id", "schedule_block_id",
                                           "label", "source_text"}
                            and type(v["source_block_id"]) is int
                            and type(v["schedule_block_id"]) is int
                            and v["source_block_id"] > 0
                            and v["schedule_block_id"] > 0
                            and v["source_block_id"] != v["schedule_block_id"]
                            and isinstance(v["label"], str) and v["label"].strip()
                            and isinstance(v["source_text"], str)
                            and v["source_text"].strip()
                            for v in schedule_rows)
                    and len({v["source_block_id"] for v in schedule_rows})
                    == len(schedule_rows)):
                refused.append((where, "source_schedule_row_openers must name "
                                       "distinct grid blocks, their schedule and printed labels"))
                continue
            if apparatus is not None and not (
                    isinstance(apparatus, list) and apparatus
                    and all(type(v) is int and v > 0 for v in apparatus)
                    and len(set(apparatus)) == len(apparatus)):
                refused.append((where, "source_apparatus_blocks must be a "
                                       "non-empty list of unique block ids"))
                continue
            if form_group is not None and not (
                    isinstance(form_group, dict)
                    and set(form_group) == {
                        "schedule_block_id", "schedule_label",
                        "first_form_block_id", "first_form_label",
                        "second_form_block_id", "second_form_label"}
                    and all(type(form_group[key]) is int and form_group[key] > 0
                            for key in ("schedule_block_id",
                                        "first_form_block_id",
                                        "second_form_block_id"))
                    and len({form_group["schedule_block_id"],
                             form_group["first_form_block_id"],
                             form_group["second_form_block_id"]}) == 3
                    and all(isinstance(form_group[key], str)
                            and form_group[key].strip()
                            for key in ("schedule_label", "first_form_label",
                                        "second_form_label"))):
                refused.append((where, "source_schedule_form_group must name "
                                       "three distinct source blocks and labels"))
                continue
            # An identity patch (before == after) changes no text; it exists only
            # to carry a reviewed body boundary, as Codex's doc 157 record does,
            # or page-read apparatus blocks where no S7 collision exists to
            # carry them (owner's authorisation, 26 Sep 2026).
            identity = before == after
            if len(match) < 12 or not before or not after or (
                    identity and not isinstance(body_start, int)
                    and apparatus is None and reparents is None
                    and continuations is None
                    and unnumbered_openers is None
                    and unnumbered_parts is None
                    and schedule_rows is None
                    and form_group is None):
                refused.append((where, "match_text >= 12 chars and a real "
                                       "before/after change (or an identity "
                                       "patch carrying source_body_start_block "
                                       "or source_apparatus_blocks) are required"))
                continue
            render = pathlib.Path(r.get("render") or "")
            if not render.is_file():
                refused.append((where, f"render not on disk: {render}"))
                continue
            digest = hashlib.sha256(render.read_bytes()).hexdigest()
            if r.get("render_sha256") and r["render_sha256"] != digest:
                refused.append((where, "render_sha256 does not match the file"))
                continue
            additional_render = r.get("additional_render")
            additional_digest = None
            if additional_render:
                additional_path = pathlib.Path(additional_render)
                if not additional_path.is_file():
                    refused.append((where, f"additional render not on disk: "
                                           f"{additional_path}"))
                    continue
                additional_digest = hashlib.sha256(
                    additional_path.read_bytes()).hexdigest()
                if r.get("additional_render_sha256") != additional_digest:
                    refused.append((where, "additional_render_sha256 does "
                                           "not match the file"))
                    continue
            cur.execute("""SELECT source_observation_id FROM instrument
                            WHERE document_id=%s AND is_active AND duplicate_of IS NULL""",
                        (doc,))
            observations = sorted({row[0] for row in cur.fetchall()})
            # Two catalogue observations can carry one document's blocks (doc
            # 4501). A patch is keyed on the observation, so a reading that
            # says so is recorded once per observation; otherwise refuse.
            if not observations or (len(observations) > 1
                                    and not r.get("all_observations")):
                refused.append((where, f"{len(observations)} active observations"
                                       " (set all_observations to patch each)"))
                continue
            page = int(r["page_no"])
            blocks = [b for b in legal_write.blocks_for(doc)
                      if b.get("page_no") == page
                      and match.casefold() in b["text"].casefold()]
            if len(blocks) != 1:
                refused.append((where, f"locator matched {len(blocks)} blocks"))
                continue
            block = blocks[0]
            if block["text"].count(before) != 1:
                refused.append((where, "before_text is not exactly once in the block"))
                continue
            cur.execute("""SELECT 1 FROM segmentation_curation_patch
                            WHERE source_observation_id=ANY(%s) AND page_no=%s
                              AND match_text=%s AND before_text=%s""",
                        (observations, page, match, before))
            if cur.fetchone():
                refused.append((where, "an identical patch is already recorded"))
                continue
            evidence = {
                "defect": r.get("defect") or "printed number misread in the source text layer",
                "observed": observed, "document_id": doc,
                "render_artifact": str(render).replace("\\", "/"),
                "render_sha256": digest, "source_block_id": block["id"],
                "extracted_number": r.get("extracted_number"),
                "printed_number": r.get("printed_number"),
                "reviewer_type": "assistant", "assistant_page_review": True,
                "human_page_review": False,
                "tool": "tools/record_curation_patch.py",
            }
            if additional_render:
                evidence["additional_render_artifact"] = str(
                    additional_render).replace("\\", "/")
                evidence["additional_render_sha256"] = additional_digest
            if r.get("fixes"):
                evidence["fixes"] = r["fixes"]
            if isinstance(body_start, int):
                if body_start not in {b["id"] for b in legal_write.blocks_for(doc)}:
                    refused.append((where, "source_body_start_block is not a "
                                           "block of this document"))
                    continue
                evidence["structural_overrides"] = {"source_body_start_block": body_start}
                evidence["identity_text_patch"] = identity
            if apparatus is not None:
                # Every named block must be printed on the page the patch
                # anchors to and read there: one page, one reading.
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                stray = sorted(set(apparatus) - on_page)
                if stray:
                    refused.append((where, "source_apparatus_blocks not on page "
                                           f"{page}: {stray}"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_apparatus_blocks"] = apparatus
                evidence["identity_text_patch"] = identity
            if reparents is not None:
                # An exact source-block reparent where no S7 case exists; the
                # worker already honours it from a verified patch, and the
                # segmenter fails closed if an address is absent or ambiguous.
                document_blocks = {b["id"] for b in legal_write.blocks_for(doc)}
                stray = sorted({v[k] for v in reparents
                                for k in ("source_block_id", "parent_block_id")}
                               - document_blocks)
                if stray:
                    refused.append((where, f"source_reparent_blocks outside this "
                                           f"document: {stray}"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_reparent_blocks"] = reparents
                evidence["identity_text_patch"] = identity
            if continuations is not None:
                document_blocks = {b["id"] for b in legal_write.blocks_for(doc)}
                page_blocks = {b["id"] for b in legal_write.blocks_for(doc)
                               if b.get("page_no") == page}
                sources = {v["source_block_id"] for v in continuations}
                parents = {v["parent_block_id"] for v in continuations}
                if sources - page_blocks or parents - document_blocks:
                    refused.append((where, "source continuation or parent "
                                           "block is outside the reviewed page/document"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_continuation_parent_blocks"] = continuations
                evidence["identity_text_patch"] = identity
            if unnumbered_openers is not None:
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                if {v["source_block_id"] for v in unnumbered_openers} - on_page:
                    refused.append((where, "unnumbered section opener is outside "
                                           "the reviewed page"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_unnumbered_section_openers"] = unnumbered_openers
                evidence["identity_text_patch"] = identity
            if unnumbered_parts is not None:
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                if {v["source_block_id"] for v in unnumbered_parts} - on_page:
                    refused.append((where, "unnumbered part heading is outside "
                                           "the reviewed page"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_unnumbered_part_headings"] = unnumbered_parts
                evidence["identity_text_patch"] = identity
            if schedule_rows is not None:
                on_page = {b["id"]: b for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                if (any(v["source_block_id"] not in on_page
                        or v["schedule_block_id"] not in on_page
                        or " ".join(on_page[v["source_block_id"]]["text"].split())
                           != " ".join(v["source_text"].split())
                        for v in schedule_rows)):
                    refused.append((where, "source schedule row or schedule "
                                           "is outside the reviewed page or text changed"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_schedule_row_openers"] = schedule_rows
                evidence["identity_text_patch"] = identity
            if form_group is not None:
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                named = {form_group[key] for key in (
                    "schedule_block_id", "first_form_block_id",
                    "second_form_block_id")}
                if named - on_page:
                    refused.append((where, "source_schedule_form_group has "
                                           f"blocks outside page {page}: "
                                           f"{sorted(named - on_page)}"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_schedule_form_group"] = form_group
                evidence["identity_text_patch"] = identity
            planned.append({"where": where, "obs": observations, "page": page,
                            "match": match, "before": before, "after": after,
                            "evidence": evidence,
                            "preview": block["text"].replace(before, after, 1)[:140]})

        print(f"readings          : {len(readings)}")
        print(f"  will record     : {len(planned)}")
        print(f"  refused         : {len(refused)}")
        for where, why in refused:
            print(f"    {where}: {why}")
        for p in planned:
            print(f"    {p['where']} -> {p['after']!r}\n        block now reads: "
                  f"{' '.join(p['preview'].split())}")
        if not a.apply:
            print("\ndry run -- pass --apply to record these patches")
            return 0 if not refused else 1
        written = 0
        for p in planned:
            for observation in p["obs"]:
                cur.execute("""
                    INSERT INTO segmentation_curation_patch
                        (source_observation_id, page_no, match_text, before_text,
                         after_text, evidence, review_state, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,'source_verified',%s)
                """, (observation, p["page"], p["match"], p["before"], p["after"],
                      json.dumps(p["evidence"], ensure_ascii=False), a.created_by))
                written += 1
        conn.commit()
        print(f"\nrecorded {written} source-verified patch(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
