"""Propose printed numbers for pending S7 units from the section sequence (read-only).

    python tools/recrawl/seqfix.py OUT.json [DOC ...]
For each pending structural candidate in a held instrument: the kept (K) and demoted (D) units are placed among the
instrument's active units of the same kind and parent, in source order (page, reading order of first block). A unit
whose numeric label breaks the run while its neighbours leave exactly one number free (prev p, next p+2) is proposed
as p+1, and flagged 'gap' when a pending contents row promises p+1. Proposals are hypotheses for a page read, never
decisions: the sheet shows the printed number, and only a page-read reading is recorded."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

SQL_PEND = """
SELECT c.id::text, c.document_id, c.instrument_id, c.printed_label, c.candidate_provision_id, c.canonical_provision_id
  FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id = p.id
 WHERE NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id = c.instrument_id)"""
SQL_UNITS = """
SELECT pr.id, pr.label, pr.kind::text, pr.parent_id, coalesce(t.page_no, pr.first_page), coalesce(t.reading_order, 0), t.id,
       left(coalesce(t.text, ''), 80)
  FROM provision pr LEFT JOIN text_block t ON t.id = pr.first_block
 WHERE pr.instrument_id = %s AND pr.is_active AND pr.kind::text IN ('section','article','rule','regulation')"""
CONF = {"3": "85", "8": "306", "5": "36", "6": "58", "1": "74", "7": "14", "4": "17", "0": "896", "9": "04", "2": "7"}
num = lambda s: int(s) if s and re.fullmatch(r"\d{1,4}", s.strip()) else None
docs = set(map(int, sys.argv[2:]))
out = []
with connect() as conn, conn.cursor() as cur:
    cur.execute(SQL_PEND)
    pend = [r for r in cur.fetchall() if not docs or r[1] in docs]
    cache, gaps = {}, {}
    for cid, doc, inst, lab, dpid, kpid in pend:
        if inst not in cache:
            cur.execute(SQL_UNITS, (inst,))
            cache[inst] = cur.fetchall()
            cur.execute("SELECT printed_label FROM v_toc_gap_pending WHERE instrument_id=%s", (inst,))
            gaps[inst] = {r[0] for r in cur.fetchall()}
        units = cache[inst]
        byid = {u[0]: u for u in units}
        for role, pid in (("D", dpid), ("K", kpid)):
            u = byid.get(pid)
            if not u or num(u[1]) is None:
                continue
            same = sorted([x for x in units if x[2] == u[2] and x[3] == u[3]], key=lambda x: (x[4], x[5]))
            i = same.index(u)
            prev = next((num(x[1]) for x in reversed(same[:i]) if num(x[1]) is not None and x[0] not in (dpid, kpid)), None)
            nxt = next((num(x[1]) for x in same[i + 1:] if num(x[1]) is not None and x[0] not in (dpid, kpid)), None)
            if prev is None or nxt is None or prev < num(u[1]) < nxt:
                continue
            used = {x[1] for x in same}
            if nxt - prev == 2:
                cands = {str(prev + 1)}
            else:   # one-digit OCR confusions of the read label that fit strictly between the neighbours
                lab0 = u[1].strip()
                cands = {lab0[:k] + c + lab0[k + 1:] for k, ch in enumerate(lab0) for c in CONF.get(ch, "")}
                cands = {v for v in cands if not v.startswith("0") and prev < int(v) < nxt}
            cands = {v for v in cands if v not in used}
            if len(cands) != 1:
                continue
            want = cands.pop()
            out.append({"cid": cid, "doc": doc, "label": lab, "role": role, "block": u[6], "page": u[4],
                        "proposed": want, "gap": want in gaps[inst], "text": u[7]})
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "proposals;", sum(x["gap"] for x in out), "confirmed by a pending contents row;",
      len({x["doc"] for x in out}), "documents")
