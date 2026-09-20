"""Read-only, repeatable-read evidence inventory; signals are NOT verdicts.

Writes review artifacts only. Does not adjudicate, replay, or change corpus rows.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import subprocess

from nizam.storage.db import connect


def key(value):
    # Preserve internal punctuation: 2.1 is not 21 and 2-A is not 2A.
    return re.sub(r"\s+", " ", (value or "").strip()).rstrip(".").casefold()


def write_inventory(out: Path, summary: dict, blocked: list[dict]) -> None:
    """Name every withheld expression; search signals are not source verdicts."""
    assert len(blocked)==summary['blocked']
    assert all(not i['released'] for i in blocked)
    def cell(value):
        return re.sub(r'\s+', ' ', str(value)).replace('|',r'\|')
    lines=['# Remaining withheld instruments', '',
        f"Measured {summary['measured_at']} against `{summary['database']}`.", '',
        f"{summary['released']:,}/{summary['canonical']:,} releasable; "
        f"{summary['blocked']:,} withheld; {summary['toc']:,} TOC gaps; {summary['s7']:,} S7 units.", '',
        'Each row is an active, canonical expression joined to an active document. '
        'This is a diagnostic worklist, not adjudication or proof that a section is absent.', '',
        '| Document | Instrument UUID | Title | TOC | S7 | Pending contents labels |',
        '|---:|---|---|---:|---:|---|']
    for i in sorted(blocked,key=lambda i:(-i['toc_count'],-i['s7_count'],i['document_id'],i['id'])):
        lines.append('| '+ ' | '.join(cell(v) for v in [i['document_id'],i['id'],
            i['short_title'],i['toc_count'],i['s7_count'],', '.join(i['labels'])])+' |')
    (out/'INVENTORY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument('--inventory-only',action='store_true',
                    help='Render the saved snapshot inventory without a database query')
    args = ap.parse_args()
    if args.inventory_only:
        write_inventory(args.out,json.loads((args.out/'summary.json').read_text()),
                        json.loads((args.out/'instruments.json').read_text()))
        print('Rendered saved withheld inventory; no database query.')
        return
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

        def query(sql, params=None):
            cur.execute(sql, params)
            names = [c.name for c in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

        measured = query("SELECT now() AS measured_at, current_database() AS database")[0]
        live = query("""
            SELECT i.id, i.document_id, i.source_observation_id, i.expression_ordinal,
                   i.short_title, i.kind::text, i.jurisdiction::text, i.source_url,
                   d.page_count, d.sha256, b.object_key, d.extractor,
                   bs.reading_order AS span_start, be.reading_order AS span_end,
                   EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id) AS released
            FROM instrument i JOIN document d ON d.id=i.document_id AND d.is_active
            JOIN blob b ON b.sha256=d.sha256
            LEFT JOIN text_block bs ON bs.id=i.source_start_block_id
            LEFT JOIN text_block be ON be.id=i.source_end_block_id
            WHERE i.is_active AND i.duplicate_of IS NULL
        """)
        blocked = [i for i in live if not i["released"]]
        ids = [i["id"] for i in blocked]
        docs = sorted({i["document_id"] for i in blocked})
        gaps = query("SELECT * FROM v_toc_gap_pending WHERE instrument_id=ANY(%s)", (ids,))
        s7 = query("""
            SELECT s.*, k.text AS kept_block_text, c.text AS candidate_block_text,
                   kp.kind::text AS kept_kind, cp.kind::text AS candidate_kind,
                   kp.label AS kept_label, cp.label AS candidate_label,
                   kp.path::text AS kept_path, cp.path::text AS candidate_path,
                   kv.text_en AS kept_provision_text, cv.text_en AS candidate_provision_text
            FROM v_structural_adjudication_pending s
            LEFT JOIN text_block k ON k.id=s.canonical_source_block_id
            LEFT JOIN text_block c ON c.id=s.source_block_id
            LEFT JOIN provision kp ON kp.id=s.canonical_provision_id AND kp.is_active
            LEFT JOIN provision cp ON cp.id=s.candidate_provision_id AND cp.is_active
            LEFT JOIN LATERAL (SELECT text_en FROM provision_version v WHERE v.provision_id=kp.id
                AND v.validity @> current_date
                ORDER BY created_at DESC,id DESC LIMIT 1) kv ON true
            LEFT JOIN LATERAL (SELECT text_en FROM provision_version v WHERE v.provision_id=cp.id
                AND v.validity @> current_date
                ORDER BY created_at DESC,id DESC LIMIT 1) cv ON true
            WHERE s.instrument_id=ANY(%s)
        """, (ids,))
        blocks = query("""
            SELECT b.*, p.width, p.height,
                   ARRAY(SELECT DISTINCT pb.role::text FROM provision_block pb
                     JOIN block_assignment_set a ON a.id=pb.assignment_set_id AND a.is_active
                     WHERE pb.block_id=b.id) AS roles
            FROM text_block b JOIN document d ON d.id=b.document_id AND d.is_active
            JOIN page p ON p.document_id=b.document_id AND p.page_no=b.page_no
            WHERE b.document_id=ANY(%s) ORDER BY b.document_id,b.reading_order,b.id
        """, (docs,))
        provisions = query("""
            SELECT p.id,p.instrument_id,p.label,p.heading,p.kind::text,p.path::text,
                   p.first_page,p.last_page,p.first_block,p.parent_id
            FROM provision p JOIN instrument i ON i.id=p.instrument_id
                 AND i.is_active AND i.duplicate_of IS NULL
            JOIN document d ON d.id=i.document_id AND d.is_active
            WHERE p.is_active AND p.instrument_id=ANY(%s)
        """, (ids,))
    bydoc = defaultdict(list)
    for b in blocks:
        bydoc[b["document_id"]].append(b)
    byinst = {i["id"]: i for i in blocked}
    provs = defaultdict(list)
    for p in provisions:
        provs[p["instrument_id"]].append(p)
    for g in gaps:
        inst = byinst[g["instrument_id"]]
        label = key(g["printed_label"])
        # Match line starts, including a fused amendment wrapper. This is a
        # search candidate only; the page and expression ownership decide it.
        pattern = re.compile(r"(?m)^\s*(?:\d{0,2}\[\s*)?" + re.escape(label)
                             + r"\s*(?:[.)\u2014]|\s*\(\d+\))", re.I)
        heading = re.sub(r"\W+", " ", g.get("printed_heading") or "").strip().casefold()
        matches = []
        for b in bydoc[g["document_id"]]:
            if "contents" in b["roles"]:
                continue
            txt = b["text"]
            hit_label = bool(pattern.search(txt))
            hit_heading = len(heading) >= 12 and heading in re.sub(r"\W+", " ", txt).casefold()
            if hit_label or hit_heading:
                inside = (inst["span_start"] is None or inst["span_start"] <= b["reading_order"])
                inside &= inst["span_end"] is None or b["reading_order"] <= inst["span_end"]
                matches.append({k: b[k] for k in ("id", "page_no", "reading_order", "text", "roles", "x0", "y0", "x1", "y1")}
                               | {"label_hit": hit_label, "heading_hit": hit_heading, "within_expression_span": inside})
        same = [p for p in provs[g["instrument_id"]] if key(p["label"]) == label]
        g["matching_provisions"] = same
        g["noncontents_candidates"] = matches
        if any(p["kind"] in ("section", "article") for p in same):
            sig = "label already citable; link/identity needs review"
        elif any(m["label_hit"] and m["within_expression_span"] for m in matches):
            sig = "line-start label outside assigned contents; inspect role/body"
        elif any(m["heading_hit"] and m["within_expression_span"] for m in matches):
            sig = "heading outside assigned contents; inspect numbering"
        elif matches:
            sig = "match only outside expression span; inspect ownership"
        else:
            sig = "no strict hit; source/typography/boundary unresolved"
        g["search_signal"] = sig
    for i in blocked:
        ig = [g for g in gaps if g["instrument_id"] == i["id"]]
        iss = [s for s in s7 if s["instrument_id"] == i["id"]]
        i["toc_count"] = len(ig)
        i["s7_count"] = len(iss)
        i["labels"] = [g["printed_label"] for g in ig]
        i["search_signals"] = dict(Counter(g["search_signal"] for g in ig))
        i["active_expressions_in_document"] = sum(j["document_id"] == i["document_id"] for j in live)
    summary = dict(measured, canonical=len(live), released=len(live)-len(blocked), blocked=len(blocked),
                   toc=len(gaps), s7=len(s7), documents=len(docs),
                   toc_signals=dict(Counter(g["search_signal"] for g in gaps)),
                   blockers=dict(Counter("both" if i["toc_count"] and i["s7_count"] else
                       "toc_only" if i["toc_count"] else "s7_only" if i["s7_count"] else "other" for i in blocked)),
                   one_gap_toc_only=sum(i["toc_count"] == 1 and i["s7_count"] == 0 for i in blocked),
                   one_s7_only=sum(i["s7_count"] == 1 and i["toc_count"] == 0 for i in blocked))
    summary["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in (("summary",summary),("instruments",blocked),("toc",gaps),("s7",s7),("blocks",blocks),("provisions",provisions)):
        (args.out / f"{name}.json").write_text(json.dumps(value,default=str,ensure_ascii=False,indent=2),encoding="utf-8")
    write_inventory(args.out,summary,blocked)
    print(json.dumps(summary,default=str,indent=2))
    print("Largest TOC backlogs:")
    for i in sorted(blocked,key=lambda i:-i["toc_count"])[:15]:
        print(i["document_id"], i["toc_count"], i["s7_count"], i["short_title"], i["search_signals"])
    print("Largest S7 backlogs:")
    for i in sorted(blocked,key=lambda i:-i["s7_count"])[:12]:
        print(i["document_id"], i["toc_count"], i["s7_count"], i["short_title"])


if __name__ == "__main__":
    main()
