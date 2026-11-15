"""sindh_head_patch.py OUT_DIR -- page-read patches setting aside the Sindh Code's running head read into released provisions.

The Sindh Code prints the law's citation ('SINDH ACT NO. VI OF 1994', 'SIND ORDINANCE NO. XVI OF 2001') at the head of
every page. Measured 15 Nov 2026: 203 such blocks inside released provisions of 189 Sindh documents. A block is set
aside only when ALL hold:
  * it is its page's FIRST block and its whole text (blanks and stops folded) is that citation;
  * it starts in the top 15% of the page;
  * the same citation is the first block of at least one other page of the document (it repeats: a running head);
  * it is NOT the document's earliest such page -- the earliest is the law's own number line above its title;
  * it is assigned to an active provision of a released instrument.
One entry per page (rule reviewed_apparatus_block), with a 60-dpi render and a fresh identity locator; pages with no
locator are skipped and counted. Read-only on the database; writes OUT_DIR/patch-<doc>r.json."""
import collections, hashlib, json, re, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon"); REL = ".artifacts/release-work-2026-09-24/claude/renders/sindh-head"
FIND = r"""
WITH fb AS (
  SELECT DISTINCT ON (t.document_id, t.page_no) t.id, t.document_id, t.page_no, t.text, t.y0, pg.height,
         upper(btrim(regexp_replace(t.text, '[\s.]+', ' ', 'g'))) AS norm
    FROM text_block t JOIN page pg ON pg.document_id=t.document_id AND pg.page_no=t.page_no
    JOIN (SELECT DISTINCT document_id FROM v_release_instrument WHERE jurisdiction='sindh') r ON r.document_id=t.document_id
   ORDER BY t.document_id, t.page_no, t.reading_order),
heads AS (SELECT * FROM fb WHERE norm ~ '^SIND[H]? (ACT|ORDINANCE)( NO)? *[IVXLC0-9]+ OF [0-9]{4}$' AND y0 < 0.15*height)
SELECT h.document_id, h.page_no, h.id, btrim(h.text) FROM heads h
 WHERE (SELECT count(*) FROM heads g WHERE g.document_id=h.document_id AND g.norm=h.norm) > 1
   AND h.page_no > (SELECT min(g.page_no) FROM heads g WHERE g.document_id=h.document_id AND g.norm=h.norm)
   AND EXISTS (SELECT 1 FROM provision_block pb JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
                 JOIN provision p ON p.id=pb.provision_id AND p.is_active
                 JOIN v_release_instrument r ON r.id=p.instrument_id WHERE pb.block_id=h.id)
 ORDER BY 1, 2"""


CITE = re.compile(r"^SIND[H]? (ACT|ORDINANCE)( NO)? *[IVXLC0-9]+ OF [0-9]{4}$")
FUSED_DOCS = r"""
SELECT DISTINCT t.document_id FROM text_block t JOIN page pg ON pg.document_id=t.document_id AND pg.page_no=t.page_no
  JOIN (SELECT DISTINCT document_id FROM v_release_instrument WHERE jurisdiction='sindh') r ON r.document_id=t.document_id
 WHERE t.y0 < 0.15*pg.height AND t.text ~* '^\s*SIND[H]?\s+(ACT|ORDINANCE)(\s+NO\.?)?\s*[IVXLC0-9]+\s+OF\s+[0-9]{4}\.?\s*\n'
 ORDER BY 1"""


def norm_line(s: str) -> str:
    return re.sub(r"[\s.]+", " ", s or "").strip().upper()


def fused_entries(cur, d, by_page, used, pdf, totals) -> list:
    """The running head fused at the top of a law block on a LATER page: the citation line and the title lines after it
    that the document's own first heading prints (all capitals, each line inside that heading). Whole-head blocks are
    set aside; otherwise the head lines are cut and the law after them kept. A title line that sits in the next block
    of its own (the title wrapped) is set aside with it. Only blocks inside a released provision."""
    firsts = {p: blocks[0] for p, blocks in by_page.items() if blocks}
    heads = {p: (bid, text) for p, (bid, text) in firsts.items()
             if CITE.match(norm_line(text.split("\n", 1)[0]))}
    if len(heads) < 2:
        return []
    earliest = min(heads)
    first_head = norm_line(heads[earliest][1]) + " " + norm_line(
        by_page[earliest][1][1] if len(by_page[earliest]) > 1 else "")
    out = []
    for p in sorted(heads):
        if p == earliest:
            continue
        bid, text = heads[p]
        if CITE.match(norm_line(text)):
            continue                                    # whole-block heads are the main pass's
        cur.execute("""SELECT EXISTS (SELECT 1 FROM provision_block pb JOIN block_assignment_set s ON s.id=pb.assignment_set_id
                         AND s.is_active JOIN provision p ON p.id=pb.provision_id AND p.is_active
                         JOIN v_release_instrument r ON r.id=p.instrument_id WHERE pb.block_id=%s)""", (bid,))
        if not cur.fetchone()[0]:
            continue
        lines = text.split("\n")
        k = 1
        while k < len(lines) and (not lines[k].strip() or (
                not re.search(r"[a-z]", lines[k]) and len(re.findall(r"[A-Z]", lines[k])) >= 4
                and norm_line(lines[k]) in first_head)):     # a title line, never a table's '1 / 2' (doc 2260 p17)
            k += 1
        while k > 1 and not lines[k - 1].strip():
            k -= 1
        head = "\n".join(lines[:k]).strip()
        rest = "\n".join(lines[k:]).strip()
        blocks = by_page[p]
        render = f"{REL}/doc{d}-p{p}.png"
        if not (ROOT / render).exists():
            pdf[p - 1].get_pixmap(dpi=60).save(ROOT / render)
        e = {"document_id": d, "page_no": p, "render": render,
             "render_sha256": hashlib.sha256((ROOT / render).read_bytes()).hexdigest(),
             "defect": "the Sindh Code's running head (the law's citation and title at the head of every page) was "
                       "read into a provision's text, in the same block as the law below it",
             "observed": f"Page {p} prints the running head {' / '.join(ln.strip() for ln in head.split(chr(10)) if ln.strip())!r} "
                         f"at its head; the same head opens the document's other pages"}
        nxt = blocks[1] if len(blocks) > 1 else None
        aside = []
        if nxt and nxt[1].strip() and not re.search(r"[a-z]", nxt[1]) and norm_line(nxt[1]) in first_head \
                and len(norm_line(nxt[1])) >= 6 and not rest:
            aside.append(nxt[0])                       # the title wrapped into a block of its own
        if not rest:
            aside.insert(0, bid)
            lines_all = sorted({ln.strip() for b, t in blocks if b not in aside for ln in t.split("\n")
                                if len(ln.strip()) >= 12}, key=len, reverse=True)
            loc = next((ln for ln in lines_all if sum(ln.casefold() in t.casefold() for _, t in blocks) == 1
                        and sum(t.count(ln) for _, t in blocks) == 1 and ln not in used), None)
            if loc is None:
                totals["skipped: no locator"] += 1
                continue
            used.add(loc)
            e.update(source_apparatus_blocks=aside, match_text=loc, before_text=loc, after_text=loc,
                     fixes="rule reviewed_apparatus_block: the running-head block(s) are set aside; no law text changes")
        else:
            if text.count(head) != 1 or len(head) < 12:
                totals["skipped: head not unique"] += 1
                continue
            loc = next((ln.strip() for ln in head.split("\n") if len(ln.strip()) >= 12), head)
            e.update(match_text=loc, before_text=head, after_text=" ",
                     fixes="parser-input correction: the running-head lines are cut from the block; the law after "
                           "them is kept as printed")
        totals["fused"] += 1
        out.append(e)
    return out


def main() -> int:
    out_dir = Path(sys.argv[1]); out_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET max_parallel_workers_per_gather = 0")
        cur.execute(FIND)
        hits = collections.defaultdict(list)
        for d, p, bid, text in cur.fetchall():
            hits[d].append((p, bid, text))
        totals = collections.Counter()
        for d, rows in hits.items():
            cur.execute("SELECT page_no, id, text FROM text_block WHERE document_id=%s ORDER BY reading_order", (d,))
            by_page = collections.defaultdict(list)
            for p, bid, text in cur.fetchall():
                by_page[p].append((bid, text or ""))
            cur.execute("""SELECT DISTINCT c.match_text FROM segmentation_curation_patch c JOIN source_observation o
                             ON o.id=c.source_observation_id JOIN document x ON x.sha256=o.sha256 WHERE x.id=%s""", (d,))
            used = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (d,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            out = []
            for p, bid, head in rows:
                blocks = by_page[p]
                lines = sorted({ln.strip() for b, t in blocks if b != bid for ln in t.split("\n") if len(ln.strip()) >= 12},
                               key=len, reverse=True)
                loc = next((ln for ln in lines if sum(ln.casefold() in t.casefold() for _, t in blocks) == 1
                            and sum(t.count(ln) for _, t in blocks) == 1 and ln not in used), None)
                if loc is None:
                    totals["skipped: no locator"] += 1
                    continue
                used.add(loc)
                render = f"{REL}/doc{d}-p{p}.png"
                if not (ROOT / render).exists():
                    pdf[p - 1].get_pixmap(dpi=60).save(ROOT / render)
                out.append({"document_id": d, "page_no": p, "source_apparatus_blocks": [bid],
                            "defect": "the Sindh Code's running head (the law's citation printed at the head of every "
                                      "page) was read into a provision's text",
                            "fixes": "rule reviewed_apparatus_block: the running-head block is set aside; no law text changes",
                            "observed": (f"Page {p} prints the running head '{' '.join(head.split())}' alone at its "
                                         f"head (block {bid}, the page's first block); the same line heads the "
                                         f"document's other pages"),
                            "render": render,
                            "render_sha256": hashlib.sha256((ROOT / render).read_bytes()).hexdigest(),
                            "match_text": loc, "before_text": loc, "after_text": loc})
            out += fused_entries(cur, d, by_page, used, pdf, totals)
            if out:
                (out_dir / f"patch-{d}r.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                totals["documents"] += 1
                totals["pages"] += len(out)
        # documents whose only running heads are fused into a law block
        cur.execute(FUSED_DOCS)
        for (d,) in cur.fetchall():
            if d in hits:
                continue
            cur.execute("SELECT page_no, id, text FROM text_block WHERE document_id=%s ORDER BY reading_order", (d,))
            by_page = collections.defaultdict(list)
            for p, bid, text in cur.fetchall():
                by_page[p].append((bid, text or ""))
            cur.execute("""SELECT DISTINCT c.match_text FROM segmentation_curation_patch c JOIN source_observation o
                             ON o.id=c.source_observation_id JOIN document x ON x.sha256=o.sha256 WHERE x.id=%s""", (d,))
            used = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (d,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            out = fused_entries(cur, d, by_page, used, pdf, totals)
            if out:
                (out_dir / f"patch-{d}r.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                totals["documents"] += 1
                totals["pages"] += len(out)
    print(json.dumps(dict(totals)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
