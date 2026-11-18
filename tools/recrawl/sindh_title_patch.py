"""sindh_title_patch.py OUT_DIR [DOC,DOC,...] -- readings that take the Sindh Code's running TITLE line out of released provisions.

Companion to sindh_head_patch.py (15 Nov 2026), which set aside the running CITATION line ('SINDH ACT NO. XII OF 1994')
at the head of each page. Under it the Sindh Code prints the law's title ('THE SINDH CULTURAL HERITAGE (PERSERVATION)
ACT, 1994'); where the text layer gave that title a block of its own, or set it at the head of the law block below,
it was read into the provision's text (doc 1336, D-083). Measured 18 Nov 2026 across the released Sindh documents.

A block is touched only when ALL hold:
  * it is among its page's first three blocks, starts in the top 15% of the page, on a page after the document's first;
  * its first non-blank lines are all capitals (4+ capital letters, no lower case, two words or more), and each such
    line, folded, is part of the law's RECORDED title (display, short or catalogue title);
  * the same first line opens a top block on at least two pages of the document (it repeats: a running head);
  * it is assigned, as body text, to an active provision of a released instrument.
A block that is all title lines is set aside (rule reviewed_apparatus_block); otherwise the title lines are cut and the
law after them kept (parser-input correction). One reading per page, a 60-dpi render, a unique locator. Read-only on
the database; writes OUT_DIR/patch-<doc>t.json and prints totals."""
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect  # noqa: E402

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
REL = ".artifacts/release-work-2026-09-24/claude/renders/sindh-title"
DOCS = """SELECT DISTINCT r.document_id FROM v_release_instrument r WHERE r.jurisdiction='sindh' ORDER BY 1"""
BLOCKS = """
SELECT t.page_no, t.id, coalesce(t.text,''), t.y0, pg.height
  FROM text_block t JOIN page pg ON pg.document_id=t.document_id AND pg.page_no=t.page_no
 WHERE t.document_id=%s ORDER BY t.page_no, t.reading_order"""
# every block that is body text of an active provision of a released Sindh instrument -- read once (a per-block test
# through the release view took ~8 s a document)
IN_LAW = """
SELECT pb.block_id FROM provision_block pb
  JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
  JOIN provision p ON p.id=pb.provision_id AND p.is_active
  JOIN (SELECT id FROM v_release_instrument WHERE jurisdiction='sindh') r ON r.id=p.instrument_id
 WHERE pb.role='body'"""


CITE = re.compile(r"^SIND[H]? (ACT|ORDINANCE)( NO)? *[IVXLC0-9]+ OF [0-9]{4}$")


def fold(s: str) -> str:
    # capitals and digits only; the article 'THE' dropped (printed titles carry it, recorded titles mostly do not)
    return " ".join(w for w in re.sub(r"[^A-Z0-9]+", " ", (s or "").upper()).split() if w != "THE")


def tfold(s: str) -> str:
    """fold() for comparing a printed line with a recorded title: the province's name dropped too (doc 3749 prints
    'THE SINDH WILDLIFE PROTECTION, ...'; its recorded title is 'Wildlife Protection, ...')."""
    return " ".join(w for w in fold(s).split() if w not in ("SINDH", "SIND"))


def caps_line(line: str) -> bool:
    return bool(line.strip()) and not re.search(r"[a-z]", line) and len(re.findall(r"[A-Z]", line)) >= 4


def title_lines(text: str, title: str) -> int:
    """How many leading non-blank lines of `text` are capitals that are part of the folded `title`; 0 when none."""
    k, titled = 0, 0
    for line in [ln for ln in text.split("\n") if ln.strip()]:
        if titled == 0 and re.fullmatch(r"\s*\d{1,4}\s*", line):
            k += 1                                  # the page's folio above the title (doc 3749: '5' / title)
        elif caps_line(line) and len(tfold(line).split()) >= 2 and f" {tfold(line)} " in f" {title} ":
            k += 1
            titled += 1
        elif titled and CITE.match(fold(line)):
            # the citation printed under the title is the head too (19 Nov 2026, doc 3243 p5: '5 / title / SINDH ACT
            # NO. XXXIX OF 2023'). Stopping at the title cut two lines and left the citation in the block, and the
            # leftover line broke the chapter that followed.
            k += 1
        else:
            break
    return k if titled else 0


def plan(cur, d, totals, used, in_law_ids, pages=None, boundary=False):
    """pages: only these pages (None: all). boundary: a set-aside head also keeps ending the sentence before it (rule
    reviewed_head_boundary, D-089) -- for the pages where the batch proof showed the head was load-bearing."""
    cur.execute(BLOCKS, (d,))
    by_page = collections.defaultdict(list)
    for p, bid, text, y0, h in cur.fetchall():
        by_page[p].append((bid, text, float(y0 or 0), float(h or 1), bid in in_law_ids))
    if not by_page:
        return []
    first = min(by_page)
    # the law's own title, as RECORDED: its display, short and catalogue titles. Capitals printed near the top of the
    # first pages are not enough -- doc 4698's 'TABLE-II' repeated there and is a schedule's heading, not the title
    cur.execute("""SELECT coalesce(i.display_title,''), coalesce(i.short_title,''),
                          coalesce(o.source_metadata->>'title','')
                     FROM instrument i JOIN source_observation o ON o.id=i.source_observation_id
                    WHERE i.document_id=%s AND i.is_active""", (d,))
    title = " | ".join(tfold(x) for row in cur.fetchall() for x in row if x)
    if not title:
        return []
    tops = {p: [(b, t, il) for b, t, y0, h, il in blocks[:4] if y0 < .15 * h] for p, blocks in by_page.items()}

    def lead(t):                                    # a block's first line that is not a bare folio
        return fold(next((ln for ln in t.split("\n") if ln.strip() and not re.fullmatch(r"\s*\d{1,4}\s*", ln)), ""))
    firsts = collections.Counter(lead(t) for p, bl in tops.items() if p != first for _b, t, _il in bl)
    # the earliest page a head line opens is the law's own heading, not a running head: never touched (as 15 Nov)
    earliest = {}
    for p in sorted(tops):
        for _b, t, _il in tops[p]:
            earliest.setdefault(lead(t), p)
    out = []
    for p in sorted(tops):
        if p == first or (pages is not None and p not in pages):
            continue
        aside, cut, words = [], None, []
        for bid, text, in_law in tops[p]:
            if not in_law:
                continue
            head1 = lead(text)
            if firsts[head1] < 2 or earliest.get(head1) == p:
                continue
            if CITE.match(fold(text)):              # the citation line alone, under or over the title (doc 3749)
                aside.append(bid)
                words.append(" ".join(text.split()))
                continue
            k = title_lines(text, title)
            if k == 0:
                continue
            if any(head1 and head1 in fold(prior) for prior in used.get(("page", d, p), [])):
                totals["skipped: page already patched"] += 1  # a reading already cuts this title here (doc 1336)
                continue
            lines = text.split("\n")
            seen, at = 0, 0                         # the end of the k-th non-blank line
            for i, ln in enumerate(lines):
                if ln.strip():
                    seen += 1
                if seen == k:
                    at = i + 1
                    break
            head = "\n".join(lines[:at]).strip()
            rest = "\n".join(lines[at:]).strip()
            words.append(" / ".join(x.strip() for x in head.split("\n") if x.strip()))
            if not rest:
                aside.append(bid)
            elif cut is None and text.count(head) == 1 and len(head) >= 12 \
                    and sum(t.count(head) for _b, t, *_ in by_page[p]) == 1:
                cut = (bid, head)
            else:
                totals["skipped: second fused block or head not unique"] += 1
        if not aside and cut is None:
            continue
        render = f"{REL}/doc{d}-p{p}.png"
        e = {"document_id": d, "page_no": p, "render": render,
             "defect": "the Sindh Code's running head (the law's title, and its citation, printed at the head of each "
                       "page) was read into a provision's text",
             "observed": f"Page {p} prints the running head {' / '.join(words)!r} at its head; the same lines head the "
                         f"document's other pages, and the title is the law's own recorded title"}
        if cut:
            # a head line unique on the page; else the whole head, which is checked unique above (doc 986's title
            # line also opens another block on its page, so the recorder refused it as matching 2 blocks)
            # Any line of the cut's own block anchors it (the recorder needs only that the locator finds the block and
            # the cut is once in it): head lines first, then the block's law lines, never one used before on the page.
            block_text = next(t for b, t, *_ in by_page[p] if b == cut[0])
            lines_in_block = [x.strip() for x in cut[1].split("\n")] + [x.strip() for x in block_text.split("\n")]
            loc = next((x for x in lines_in_block if len(x) >= 12 and (d, p, x) not in used
                        and sum(t.casefold().count(x.casefold()) for _b, t, *_ in by_page[p]) == 1),
                       None if (d, p, cut[1]) in used else cut[1])
            if loc is None or (d, p, loc) in used:
                totals["skipped: locator used"] += 1
                continue
            e.update(match_text=loc, before_text=cut[1], after_text=" ")
            totals["title lines cut"] += 1
        else:
            cands = sorted({ln.strip() for b, t, *_ in by_page[p] if b not in aside for ln in t.split("\n")
                            if len(ln.strip()) >= 12}, key=len, reverse=True)
            loc = next((ln for ln in cands if sum(t.count(ln) for _b, t, *_ in by_page[p]) == 1
                        and sum(ln.casefold() in t.casefold() for _b, t, *_ in by_page[p]) == 1
                        and (d, p, ln) not in used), None)
            if loc is None:
                totals["skipped: no locator"] += 1
                continue
            e.update(match_text=loc, before_text=loc, after_text=loc)
        if aside:
            e["source_apparatus_blocks"] = aside
            totals["blocks set aside"] += len(aside)
            if boundary:
                e["source_head_boundary_blocks"] = aside
                totals["heads kept as a sentence boundary"] += len(aside)
        e["fixes"] = ("; ".join(x for x in [
            "rule reviewed_apparatus_block: the running-head block(s) set aside" if aside else "",
            "rule reviewed_head_boundary: the set-aside head still ends the sentence before it, as printed"
            if aside and boundary else "",
            "parser-input correction: the running-title lines cut from the block, the law after them kept as printed"
            if cut else ""] if x))
        used[(d, p, e["match_text"])] = True
        out.append(e)
    return out


def main() -> int:
    out_dir = Path(sys.argv[1])
    only = {int(x) for x in sys.argv[2].split(",")} if len(sys.argv) > 2 else None   # optional DOC,DOC,...
    # optional PAGES.json {"doc": [page, ...]}: only those pages, each head kept as a sentence boundary (D-089)
    page_map = ({int(k): set(v) for k, v in json.loads(Path(sys.argv[3]).read_text()).items()}
                if len(sys.argv) > 3 else None)
    out_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    totals = collections.Counter()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET max_parallel_workers_per_gather = 0")
        cur.execute(DOCS)
        docs = [r[0] for r in cur.fetchall() if only is None or r[0] in only]
        cur.execute(IN_LAW)
        in_law_ids = {r[0] for r in cur.fetchall()}
        for d in docs:
            # the document's active readings: their locators (page-scoped) and what each page's readings already cut
            # Locators: every reading ever recorded on the page, retired or not -- the evidence is append-only and the
            # recorder refuses an identical patch even when the earlier one was withdrawn (19 Nov 2026). What a page
            # already cuts: the active readings only.
            cur.execute("""SELECT DISTINCT c.page_no, c.match_text, c.before_text, c.retired_at IS NULL
                             FROM segmentation_curation_patch c
                             JOIN source_observation o ON o.id=c.source_observation_id
                             JOIN document x ON x.sha256=o.sha256 WHERE x.id=%s""", (d,))
            used = {}
            for page, match, before, active in cur.fetchall():
                used[(d, page, match)] = True
                if active:
                    used.setdefault(("page", d, page), []).append(before or "")
            out = plan(cur, d, totals, used, in_law_ids,
                       pages=page_map.get(d, set()) if page_map is not None else None,
                       boundary=page_map is not None)
            if not out:
                continue
            cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (d,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            for e in out:
                path = ROOT / e["render"]
                if not path.exists():
                    pdf[e["page_no"] - 1].get_pixmap(dpi=60).save(path)
                e["render_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            (out_dir / f"patch-{d}t.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            totals["documents"] += 1
            totals["pages"] += len(out)
    print(json.dumps(dict(totals)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
