"""ajk_note_patch.py OUT_DIR -- the AJK revised-volume notes footnote_zone.py could not take (15 Nov 2026), page-read.

Each page below was read from its block dump (rules, sizes, owners) and, where it was unclear, its render: every block
listed is wholly a note -- amendment notes and the superseded text the revised volumes reproduce in them -- and is set
aside (rule reviewed_apparatus_block); each CUT names a block that fuses the law's last line with the note printed
under it, and the cut removes the block's text from the note's marker to its end (the law before it is kept as
printed). The notes are not smaller than the law, open with markers footnote_zone's MARKER does not read ('1Between',
'2Sub-section'), or continue a note from the page before under a rule near the page's top.
Writes OUT_DIR/patch-<doc>n.json (one entry per page, plus one per cut) with renders; read-only on the database."""
import hashlib, json, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon"); REL = ".artifacts/release-work-2026-09-24/claude/renders"
R = lambda a, b: list(range(a, b + 1))  # noqa: E731
ASIDE = {
    10063: {1: [2748707], 2: [2748712], 3: [2748722], 4: R(2748731, 2748742), 8: R(2748799, 2748802)},
    10285: {9: [2763392]},
    10313: {1: [2765157, 2765158] + R(2765160, 2765166)},
    10482: {7: R(2777290, 2777293), 8: [2777312], 11: [2777342]},
    10499: {5: [2778217]},
    10524: {7: R(2780118, 2780121)},
    10624: {1: [2790527], 2: [2790543], 3: [2790549, 2790550]},
    10668: {8: [2794093]},
    10685: {3: R(2795014, 2795033), 4: R(2795036, 2795046), 5: R(2795050, 2795055)},
    10861: {6: [2807741], 7: [2807751]},
    10870: {4: [2808678], 9: [2808732], 12: R(2808749, 2808752), 19: R(2808803, 2808814), 20: R(2808820, 2808826),
            22: [2808844, 2808845]},
    10912: {3: [2811286, 2811287], 4: R(2811289, 2811308), 11: R(2811474, 2811478)},
    10977: {2: [2818369], 3: R(2818378, 2818384), 4: [2818399, 2818400], 6: [2818442], 8: [2818472]},
    11153: {6: [b for b in R(2834983, 2835015) if b not in (2834990, 2834996, 2835001)], 9: [2835063, 2835064],
            10: [b for b in R(2835071, 2835114) if b != 2835081], 11: R(2835124, 2835136)},
    11167: {5: R(2836400, 2836427)},
    11227: {3: R(2840218, 2840229), 4: R(2840231, 2840244), 5: R(2840246, 2840256), 6: R(2840260, 2840268),
            7: R(2840274, 2840280)},
    11324: {7: [2846525]},
    9994: {1: [2743708], 2: [2743720, 2743721, 2743722], 3: [2743730], 4: [2743737]},
}
# (doc, page, block, the note's opening words): the cut runs from those words to the block's end
CUTS = [(10482, 4, 2777257, "Sub-section (2) of Section 9 omitted"), (10499, 6, 2778226, "1Between the words"),
        (10524, 8, 2780130, "1 Between the words"), (10861, 5, 2807732, "In subsection (3) of Sec.5"),
        (10870, 10, 2808736, "1 Between the words"), (10870, 12, 2808748, "1Sub-section (1) subs."),
        (10870, 13, 2808758, "1Clause (c) of sub-section (2)"), (10977, 8, 2818471, "For the words “more than once”"),
        (10977, 10, 2818504, "For the words “every months”"), (11025, 1, 2825563, "1Section 2 subs. by the Excise"),
        (11153, 6, 2834982, "11 Omitted by The Azad"), (11153, 15, 2835214, "1Sec.28")]


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    docs = sorted(set(ASIDE) | {c[0] for c in CUTS})
    with connect() as conn, conn.cursor() as cur:
        for d in docs:
            cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (d,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s", (d,))
            blocks = {bid: (p, t or "") for bid, p, t in cur.fetchall()}
            entries = []

            def render(p):
                f = f"{REL}/doc{d}-p{p}.png"
                if not (ROOT / f).exists():
                    pdf[p - 1].get_pixmap(dpi=80).save(ROOT / f)
                return f
            for p, ids in sorted(ASIDE.get(d, {}).items()):
                assert all(blocks[b][0] == p for b in ids), (d, p)
                first = " ".join(blocks[ids[0]][1].split())
                entries.append({"document_id": d, "page_no": p, "source_apparatus_blocks": ids,
                                "defect": "page notes (amendment notes and the superseded text a revised volume "
                                          "reproduces in them) were read into the law as provision text",
                                "fixes": "rule reviewed_apparatus_block: the note blocks are set aside; no law text changes",
                                "observed": f"Page {p} prints, under its note rule, {len(ids)} note block(s), the first "
                                            f"{first[:140]!r}",
                                "render": render(p)})
            for dd, p, bid, words in CUTS:
                if dd != d:
                    continue
                text = blocks[bid][1]
                at = text.find(words)
                assert at > 0 and blocks[bid][0] == p, (d, bid, words)
                # start the cut at the marker line before the words when the marker stands alone ('1\nFor the ...')
                head = text[:at]
                m = head.rstrip(" ").rsplit("\n", 2)
                if len(m) == 3 and m[1].strip().isdigit() and len(m[1].strip()) <= 2 and not m[2].strip():
                    at = len(m[0]) + 1
                before = text[at:].rstrip()
                assert text.count(before) == 1, (d, bid)
                loc = next(ln.strip() for ln in before.split("\n") if len(ln.strip()) >= 12)
                entries.append({"document_id": d, "page_no": p, "match_text": loc, "before_text": before,
                                "after_text": " ",
                                "defect": "the block fuses the law's last line with the page note printed under it; "
                                          "the note was read as law",
                                "fixes": "parser-input correction: the note is cut from the block, from its marker to "
                                         "the block's end; the law before it is kept as printed",
                                "observed": f"Page {p} prints the law ending "
                                            f"{' '.join(text[:at].split())[-80:]!r}, then the note rule and the note "
                                            f"{' '.join(before.split())[:120]!r}",
                                "render": render(p)})
            for e in entries:
                e["render_sha256"] = hashlib.sha256((ROOT / e["render"]).read_bytes()).hexdigest()
            (out / f"patch-{d}n.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
            print(d, len(entries), "entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
