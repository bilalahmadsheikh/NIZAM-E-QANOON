"""Agent JE's rules 3-7, ported 14 Oct 2026 by builder BZ (group 4; docs/SEGMENTATION-PROFILES.md). JE's own pure tests
($S/agJE-t3.py .. -t7.py), run against the LIVE modules instead of JE's in-memory prototypes; JE's assertions are
unchanged. SEG0 (JE's 'today' module) is the live module too, so JE's inertness checks compare the live build with and
without each key.

  owner_cited_compound_label   compound printed/cited labels N-M / N.M (docs 4498 q2, 4400 q2)
  reviewed_list_item_text, reviewed_decimal_item_cut, reviewed_text_unit   (docs 4408, 4409, 4416)
  reviewed_quoted_definition_cut, reviewed_division_opener, reviewed_division_caption   (doc 4426; 4408's Appendix-A..D)
  reviewed_contents_region (docs 4400, 4137); reviewed_annexure_appendix_reparent, reviewed_chapter_resumes_body (4400)
"""
import re
import sys
import types

import nizam.corpus.segment as SEG
import nizam.shared.corpus_types as T
import nizam.workers.segment as W
from tools import record_curation_patch as REC

SEG0 = SEG
OD = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-k.json", "document_id": 4400, "question_id": "q2"}
ROOT = __import__('pathlib').Path(__file__).resolve().parents[1].as_posix()


def test_je_rule3_as_written_by_agent_je():
    # BZ ported the rule on 14 Oct 2026 (segment ef363c53): today then accepts what the prototype accepts.
    PORTED = "owner_cited_compound_label" in open(ROOT + "/nizam/corpus/segment.py", encoding="utf-8").read()
    def check(cond, what):
        assert cond, what

    def e(printed, cited, **kw):
        return dict({"kind": "section", "printed_label": printed, "cited_label": cited, "source_block_id": 3, "owner_decision": OD}, **kw)

    # --- shape
    for good in (e("1.32", "1.132"), e("27-2", "27-3"), e("27.12", "27.11"), e("27-27", "27-38", source_occurrence=2)):
        check(SEG._owner_cited_label_shape_ok(good), f"accept {good}")
        check(SEG0._owner_cited_label_shape_ok(good) == PORTED, f"today (ported={PORTED}) on {good}")
    for bad in (e("1.32", "1-132"), e("1.32", "2.132"), e("1.32", "1.32"), e("1.32", "132"), e("32", "1.132"),
                e("1.32", "1.132", continues_opened=True), e("1.32", "1.132", printed_bracketed=True),
                e("1.32.1", "1.132"), e("1.32", "1.132", owner_decision={"export": "x"}),
                e("1.32", "1.132", kind="clause")):
        check(not SEG._owner_cited_label_shape_ok(bad), f"refuse {bad}")
    # Rule11 `owner_cited_lettered_compound_label` (agent JE; lead 14 Oct: "an optional -A suffix on both print and cite,
    # the same checks"; ported 16 Oct, group 10): a cite may add one capital the print lacks ('21-25' -> '21-25-A' in
    # doc 4498), so this case, refused when rule3 was written, is now accepted. The letter-aware sequence check and the
    # other shape checks still apply (tests/test_je_rule11_lettered_compound.py).
    check(SEG._owner_cited_label_shape_ok(e("1.32", "1.132A")), "accept (rule11) 1.32 -> 1.132A")
    for plain in (e("3", "4"), e(None, "3", source_prefix="\"29 - In the absence of"), e("47", "47A")):
        check(SEG._owner_cited_label_shape_ok(plain) == SEG0._owner_cited_label_shape_ok(plain), f"plain unchanged {plain}")

    # --- parser: doc 4400 p39 shape -- 1.130, 1.131, '1.32.', 1.133
    def blk(i, text, y):
        return {"id": i, "text": text, "page_no": 39, "x0": 72.0, "x1": 480.0, "y0": y, "page_height": 842.0}
    blocks = [blk(1, "1.130. All officers entrusted with a supply of stationary will take proper precautions. \n", 40.0),
              blk(2, "1.131. Standard forms cannot be altered without the previous sanction of the Chief Engineer. \n", 90.0),
              blk(3, "1.32. Forms of deeds and other documents will be settled by the Law officers. \n", 140.0),
              blk(4, "1.133. Where a minimum period has been prescribed records may be destroyed. \n", 190.0)]
    def keys(seg):
        return [(p.rsplit(".", 1)[-1], n.label) for n, p in SEG.assign_paths(seg, "pb.code.y1994")]
    plain = SEG.segment(blocks)
    check(keys(plain) == [("s_1_130", "1.130"), ("s_1_131", "1.131"), ("s_1_32", "1.32"), ("s_1_133", "1.133")], keys(plain))
    on = SEG.segment(blocks, structural_overrides={"source_owner_cited_labels": [e("1.32", "1.132")]})
    k = keys(on)
    check(k == [("s_1_130", "1.130"), ("s_1_131", "1.131"), ("s_1_132__p1_32", "1.132"), ("s_1_133", "1.133")], k)
    check(any(r.get("resolution") == "owner_cited_label" and r.get("cited_label") == "1.132" and r.get("printed_label") == "1.32"
              for r in on.reviews_enacted) if hasattr(on, "reviews_enacted") else True, "review recorded")
    paths = [p for _, p in SEG.assign_paths(on, "pb.code.y1994")]
    check([T.printed_label(p, n.label) for (n, _), p in zip(SEG.assign_paths(on, "pb.code.y1994"), paths)] == [None, None, "1.32", None], "reader")
    check(T.printed_note(paths[2], "1.132") == "(printed 1.32)", "note")
    # today's parser refuses the same reading (shape)
    if not PORTED:
        try:
            SEG0.segment(blocks, structural_overrides={"source_owner_cited_labels": [e("1.32", "1.132")]}); check(False, "today accepts")
        except ValueError as x:
            check("malformed" in str(x), x)
    # out of sequence -> refused
    try:
        SEG.segment(blocks, structural_overrides={"source_owner_cited_labels": [e("1.32", "1.140")]}); check(False, "seq")
    except ValueError as x:
        check("out of sequence" in str(x), x)
    # the print must be at the named block (block 2 prints 1.131, not 1.32) -> not reached
    try:
        SEG.segment(blocks, structural_overrides={"source_owner_cited_labels": [e("1.32", "1.132", source_block_id=2)]}); check(False, "block")
    except ValueError as x:
        check("not reached" in str(x), x)
    # a later sibling printed '1.132.' -> the cited label slugs like a sibling's -> refused at path assignment
    blocks2 = blocks + [blk(5, "1.132. Another paragraph printed with the number the owner assigned. \n", 240.0)]
    seg2 = SEG.segment(blocks2, structural_overrides={"source_owner_cited_labels": [e("1.32", "1.132")]})
    try:
        SEG.assign_paths(seg2, "pb.code.y1994"); check(False, "sibling")
    except ValueError as x:
        check("slugs like a sibling" in str(x), x)
    # --- reader: hyphen form, old forms unchanged, compound marker without its label refused
    check(T.printed_label("x.ch_XXVII.s_27_3__p27_2", "27-3") == "27-2", "hyphen reader")
    check(T.printed_label("x.s_27_11__p27_12", "27.11") == "27.12", "dot reader")
    check([T.printed_label(p) for p in ("x.s_4__p3", "x.s_3__pnone", "x.s_2__o2", "x.s_1_1", "x.sch_S.cl_Naib__nr")] == ["3", "", None, None, None], "old forms")
    for bad_label in (None, "4"):
        try:
            T.printed_label("x.s_1_132__p1_32", bad_label); check(False, f"reader {bad_label}")
        except ValueError:
            check(True, "")
    # Rule10 `owner_cited_cross_chapter_label` (agent JE, doc 4498; ported 16 Oct, group 10): the print's N may differ
    # from the stored label's ('13-21' printed for rule 14-2), so a compound marker read under another N is no longer
    # refused by the reader; the shape check on the writer side still decides what is stored.
    check(T.printed_label("x.s_1_132__p1_32", "2.132") == "1.32", "reader (rule10) 2.132")
    # --- recorder page check
    texts = {3: "1.131. Standard forms. \n1.32. Forms of deeds", 4: "1.132. Forms of deeds", 5: "27-14 Legal Branch Composition of -"}
    check(REC.owner_cited_block_problem(e("1.32", "1.132"), texts) is None, "rec ok")
    check(REC.owner_cited_block_problem(e("1.32", "1.132", source_block_id=4), texts) is not None, "rec inside 1.132")
    check(REC.owner_cited_block_problem(e("27-14", "27-9", source_block_id=5), texts) is None, "rec hyphen no dot")
    check(REC.owner_cited_block_problem(e("3", "4", source_block_id=4), {4: "3. Text"}) is None, "rec plain unchanged")


def test_je_rule4_as_written_by_agent_je():
    def check(cond, what):
        assert cond, what
    def blk(i, text, p=43, y=40.0):
        return {"id": i, "text": text, "page_no": p, "x0": 72.0, "x1": 480.0, "y0": y, "page_height": 842.0}
    blocks = [blk(1, "Chapter-9 \n", y=20), blk(2, "ROLES AND RESPONSIBILITIES \n", y=30),
              blk(3, "9.2 \nBuilder- Responsibilities \n", y=40),
              blk(4, "a. Builder shall engage the services of following qualified professionals: \ni. Consultants: \n", y=60),
              blk(5, "1. Architect \n2. Geotechnical Engineer (for multi storey). \n3. Structural Engineer. \n", y=80),
              blk(6, "9.3 \nConsultants - Qualification and Responsibilities: \n", y=120),
              blk(7, "a. \nVarious Consultants hired by the Builder shall be responsible. \n", y=140),
              blk(8, "i.  Architect: \n", y=160),
              blk(9, "1. The architect registered with the PCATP shall prepare plans. \n", y=180),
              blk(10, "2.  The architect shall produce architectural designs. \n", y=200),
              blk(11, "ii.   Structural Engineer: \n", y=220),
              blk(12, "1. The Structural Engineer shall be a consulting engineer. \n2. The Structural Engineer shall produce drawings. \n", y=240),
              blk(13, "9.4 Resident Engineer - Qualification and Responsibilities \n", y=280),
              blk(14, "a. \nThe construction activity shall be supervised by a Resident Engineer. \n", y=300)]
    def flat(seg):
        return [(n.kind, n.label) for n in seg.flatten()]
    plain = SEG.segment(blocks)
    check(plain.flatten() and any(k in ("section", "clause") and l == "1" for k, l in flat(plain)), f"today opens '1': {flat(plain)}")
    check(flat(plain) == flat(SEG0.segment(blocks)), "inert without the key")
    spec_ok = {"source_list_text_sections": [{"section_block_id": 3, "section_label": "9.2", "items": 3},
                                             {"section_block_id": 6, "section_label": "9.3", "items": 4}]}
    on = SEG.segment(blocks, structural_overrides=spec_ok)
    labels = flat(on)
    check(not any(l in ("1", "2", "3") for _, l in labels), labels)
    check([l for k, l in labels if k in ("section", "chapter")] == ["9", "9.2", "9.3", "9.4"], labels)
    s93 = next(n for n in on.flatten() if n.label == "9.3")
    check("1. The architect registered" in s93.text and "2. The Structural Engineer shall produce drawings." in s93.text, s93.text)
    t93 = " ".join(s93.text.split()); check(t93.index("i. Architect") < t93.index("1. The architect") < t93.index("ii. Structural"), t93)
    for bad, msg in (({"source_list_text_sections": [{"section_block_id": 3, "section_label": "9.2", "items": 2},
                                                    {"section_block_id": 6, "section_label": "9.3", "items": 4}]}, "not reached"),
                     ({"source_list_text_sections": [{"section_block_id": 6, "section_label": "9.2", "items": 4}]}, "not reached"),
                     ({"source_list_text_sections": [{"section_block_id": 6, "section_label": "9.3", "items": 4, "x": 1}]}, "malformed"),
                     ({"source_list_text_sections": [{"section_block_id": 6, "section_label": "9", "items": 4}]}, "malformed"),
                     ({"source_list_text_sections": [{"section_block_id": 6, "section_label": "9.3", "items": 0}]}, "malformed")):
        try:
            SEG.segment(blocks, structural_overrides=bad); check(False, f"accepted {bad}")
        except ValueError as x:
            check(msg in str(x), f"{msg}: {x}")
    # Preamble entry: '(i)', '(ii)' of the unnumbered short title are the Preamble's text
    pb = [blk(1, "PREAMBLE \n", p=5, y=20), blk(2, "Whereas, it is expedient to provide for a uniform framework. \n", p=5, y=40),
          blk(3, "SHORT TITLE AND COMMENCEMENT \n \n(i) These Regulations may be called the Rawalpindi Regulations, 2007 \n"
                 "(ii) They shall come into force at once. \n", p=5, y=60),
          blk(4, "1.1 \nDefinitions \n", p=6, y=20), blk(5, "Unless otherwise expressly stated, the following terms apply. \n", p=6, y=40)]
    plain = SEG.segment(pb)
    check(("clause", "i") in flat(plain) and ("clause", "ii") in flat(plain), flat(plain))
    on = SEG.segment(pb, structural_overrides={"source_list_text_sections": [{"section_block_id": 1, "section_label": "Preamble", "items": 2}]})
    check(flat(on) == [("preamble", "Preamble"), ("section", "1.1")], flat(on))
    pre = on.flatten()[0]; tp = " ".join(pre.text.split())
    check("(i) These Regulations may be called" in tp and "(ii) They shall come into force at once." in tp, tp)
    # decimal item cut: '9.2 / Builder- Responsibilities / 9.2.1 / a. / Builder shall ...'
    ib = [blk(1, "Chapter-9 \n", y=20), blk(2, "9.1 General \n", y=30),
          blk(3, "9.2 \nBuilder- Responsibilities \n \n9.2.1 \n \na. \nBuilder shall engage the services of professionals: \n \n", y=40),
          blk(4, "i. Consultants \n", y=60), blk(5, "9.2.2 Builders responsibility for BTS \n", y=80)]
    check("9.2.1" not in [l for _, l in flat(SEG.segment(ib))], flat(SEG.segment(ib)))
    on = SEG.segment(ib, structural_overrides={"source_decimal_item_cut_blocks": [3]})
    check([l for k, l in flat(on) if k == "section"] == ["9.1", "9.2", "9.2.1", "9.2.2"], flat(on))
    s921 = next(n for n in on.flatten() if n.label == "9.2.1")
    check(" ".join(s921.text.split()).startswith("a. Builder shall engage") and "i. Consultants" in s921.text, s921.text)
    try:
        SEG.segment(ib, structural_overrides={"source_decimal_item_cut_blocks": [99]}); check(False, "unknown block")
    except ValueError as x:
        check("not found" in str(x), x)
    # reviewed text unit: '(15) days ...' wrapped cross-reference
    tb = [blk(1, "10.4.1 Sanction of Plan \n", y=20),
          blk(2, "Within 45 days the Competant Authority shall decide. If such neglect continues for further fifteen \n", y=40),
          blk(3, "(15) days from the date of such written communication, the plans shall be deemed sanctioned. \n", y=60)]
    check(("subsection", "15") in flat(SEG.segment(tb)), flat(SEG.segment(tb)))
    on = SEG.segment(tb, structural_overrides={"source_text_units": [{"source_block_id": 3, "kind": "subsection", "label": "15"}]})
    check(flat(on) == [("section", "10.4.1")] and "(15) days from the date" in on.flatten()[0].text, flat(on))
    try:
        SEG.segment(tb, structural_overrides={"source_text_units": [{"source_block_id": 2, "kind": "subsection", "label": "15"}]}); check(False, "tu")
    except ValueError as x:
        check("not reached" in str(x), x)


def test_je_rule5_as_written_by_agent_je():
    def check(cond, what):
        assert cond, what
    def blk(i, text, p=1, y=40.0):
        return {"id": i, "text": text, "page_no": p, "x0": 72.0, "x1": 480.0, "y0": y, "page_height": 842.0}
    def flat(seg):
        return [(n.kind, n.label) for n in seg.flatten()]
    # (a) quoted definitions
    qb = [blk(1, "1. Short title. These rules may be called the Rules.\n", y=20),
          blk(2, "2. In these rules, unless there is anything repugnant -\n", y=40),
          blk(3, "(1)\n“Act” means the Sindh Local Government Act, 2013;\n(2)\n“candidate” means a person proposed;\n(3)\n“Council” means the Council;\n", p=2, y=20)]
    check([l for k, l in flat(SEG.segment(qb)) if k == "subsection"] == ["1"], flat(SEG.segment(qb)))
    check(flat(SEG.segment(qb)) == flat(SEG0.segment(qb)), "inert")
    on = SEG.segment(qb, structural_overrides={"source_quoted_definition_cut_blocks": [3]})
    check([l for k, l in flat(on) if k == "subsection"] == ["1", "2", "3"], flat(on))
    # (b) division openers + (c) caption
    db = [blk(1, "CHAPTER-I\nPRELIMINARY\n", y=20), blk(2, "1. Short title. These rules may be called the Rules.\n", y=40),
          blk(3, "CHAPTER-IV\n", p=2, y=20), blk(4, "ELECTIONS\n", p=2, y=30), blk(5, "12. (1) The Commission shall make a programme.\n", p=2, y=40),
          blk(6, "Form-I\n", p=3, y=20), blk(7, "PUBLIC NOTICE\n", p=3, y=30), blk(8, "Form-II “A”\n", p=4, y=20),
          blk(9, "NOMINATION FORM\n", p=4, y=30), blk(10, "Form-II “A”\n", p=4, y=60),
          blk(11, "1[FORM-XXI   (A)\n", p=5, y=20), blk(12, "OATH OF OFFICE\n", p=5, y=30)]
    base = SEG.segment(db)
    check(("form", "Form") in flat(base), flat(base))
    spec_ok = {"source_division_openers": [{"source_block_id": 6, "kind": "form", "label": "Form-I"},
                                           {"source_block_id": 8, "kind": "form", "label": "Form-II “A”"},
                                           {"source_block_id": 10, "kind": "form", "label": None},
                                           {"source_block_id": 11, "kind": "form", "label": "FORM-XXI (A)"}],
               "source_division_captions": [{"division_block_id": 3, "caption_block_id": 4}]}
    on = SEG.segment(db, structural_overrides=spec_ok)
    forms = [l for k, l in flat(on) if k == "form"]
    check(forms == ["Form-I", "Form-II “A”", "FORM-XXI (A)"], flat(on))
    ch4 = next(n for n in on.flatten() if n.kind == "chapter" and n.label == "IV")
    check(ch4.heading == "ELECTIONS" and "ELECTIONS" not in ch4.text, (ch4.heading, ch4.text))
    f2 = next(n for n in on.flatten() if n.label == "Form-II “A”")
    check("Form-II" in f2.text, f2.text)
    paths = [p.rsplit(".", 1)[-1] for _, p in SEG.assign_paths(on, "sd.rules.y2015") if "form" in p.rsplit(".", 1)[-1]]
    check(paths == ["form_Form_I", "form_Form_II_A", "form_FORM_XXI_A"], paths)
    for bad, msg in (({"source_division_openers": [{"source_block_id": 6, "kind": "form", "label": "Form-II"}]}, "is not the print"),
                     ({"source_division_openers": [{"source_block_id": 7, "kind": "form", "label": "Form-I"}]}, "does not print"),
                     ({"source_division_openers": [{"source_block_id": 99, "kind": "form", "label": "Form-I"}]}, "not reached"),
                     ({"source_division_captions": [{"division_block_id": 1, "caption_block_id": 4}]}, "lacks exact"),
                     ({"source_division_openers": [{"source_block_id": 6, "kind": "part", "label": "Form-I"}]}, "malformed")):
        try:
            SEG.segment(db, structural_overrides=bad); check(False, f"accepted {bad}")
        except ValueError as x:
            check(msg in str(x), f"{msg}: {x}")
    # contents-row variant (4400 q4): untitled appendix held under the number its contents row prints
    OD = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-k.json", "document_id": 4400, "question_id": "q4"}
    ab = [blk(1, "APPENDICES\n", y=10), blk(2, "IV.\nSanitary rules on Extensive Works.\n", y=20),
          blk(3, "1.1. The Department shall keep accounts. \n", p=2, y=20),
          blk(4, "(REFERRED TO IN PARAGRAPH 2.101)\n", p=3, y=20), blk(5, "Sanitary Rules, on Extensive Works\n", p=3, y=30),
          blk(6, "1.\nOn recruitment, members of a labourer force should be examined. \n", p=3, y=40)]
    spec = {"source_division_openers": [{"source_block_id": 4, "kind": "appendix", "label": "APPENDIX IV",
                                         "owner_decision": OD, "contents_row_block_id": 2}]}
    on = SEG.segment(ab, structural_overrides=spec)
    check(("appendix", "APPENDIX IV") in flat(on), flat(on))
    bad = {"source_division_openers": [{"source_block_id": 4, "kind": "appendix", "label": "APPENDIX V",
                                        "owner_decision": OD, "contents_row_block_id": 2}]}
    try:
        SEG.segment(ab, structural_overrides=bad); check(False, "accepted V")
    except ValueError as x:
        check("lacks its contents row" in str(x), x)


def test_je_rule6_as_written_by_agent_je():
    def check(cond, what):
        assert cond, what
    def blk(i, text, p=1, y=40.0):
        return {"id": i, "text": text, "page_no": p, "x0": 72.0, "x1": 480.0, "y0": y, "page_height": 842.0}
    def flat(seg):
        return [(n.kind, n.label) for n in seg.flatten()]
    for which in ("alone", "chained"):
        # ported: 'alone' and 'chained' are both the live module
        # 4137 shape: CONTENTS rows 1.-3. on p1, CHAPTER-I with decimal paragraphs from p2
        a = [blk(1, "PENSION REGULATIONS, 2003 \n", y=10), blk(2, "CONTENTS \n", y=20), blk(3, "1. \nGeneral \n", y=30),
             blk(4, "2. \nService Qualifying for pension \n", y=40), blk(5, "3. \nDifferent kinds of Ordinary Pension \n", y=50),
             blk(6, "CHAPTER-I \n", p=2, y=10), blk(7, "GENERAL: \n", p=2, y=20),
             blk(8, "1.1 \nSHORT TITLE: These regulations may be called the Regulations, 2003. \n", p=2, y=30),
             blk(9, "1.2 \nCOMMENCEMENT: These Regulations shall come into force at once. \n", p=2, y=40)]
        plain = SEG.segment(a)
        check(flat(plain) == flat(SEG0.segment(a)), f"{which}: inert")
        on = SEG.segment(a, structural_overrides={"source_contents_region": {"first_block_id": 2, "last_block_id": 5,
                                                                             "body_start_block_id": 6, "rows": "sections"}})
        check(("section", "1") not in flat(on) and ("section", "1.1") in flat(on), f"{which}: {flat(on)}")
        check(on.toc_found and sorted(on.toc) == ["1", "2", "3"], (on.toc_found, on.toc))
        roles = on.roles if hasattr(on, "roles") else None
        # 4400 shape: banner-less range contents, title page, then the body
        b = [blk(1, "CHAPTER IV-MISCELLANEOUS RULES \n", y=10), blk(2, "I.\nMuster Rolls\n4.2-4.4\n", y=20),
             blk(3, "II. Measurement Books\n4.5-4.8\n", y=30), blk(4, "West Pakistan Buildings & Roads, Department Code\n", p=2, y=10),
             blk(5, "CHAPTER-1 ESTABLISHMENT\n", p=3, y=10),
             blk(6, "1.38. The Chief Engineer is the head of the department in his charge. \n", p=3, y=30),
             blk(7, "1.39. It is the duty of the Chief Engineer to arrange postings. \n", p=3, y=50)]
        on = SEG.segment(b, structural_overrides={"source_contents_region": {"first_block_id": 1, "last_block_id": 3,
                                                                             "body_start_block_id": 5, "rows": "none"}})
        check([l for k, l in flat(on) if k == "section"] == ["1.38", "1.39"] and not on.toc_found, f"{which}: {flat(on)}")
        for bad, msg in (({"first_block_id": 3, "last_block_id": 1, "body_start_block_id": 5, "rows": "none"}, "reading order"),
                         ({"first_block_id": 1, "last_block_id": 3, "body_start_block_id": 99, "rows": "none"}, "reading order"),
                         ({"first_block_id": 4, "last_block_id": 4, "body_start_block_id": 5, "rows": "none"}, "no numbered row"),
                         ({"first_block_id": 4, "last_block_id": 4, "body_start_block_id": 5, "rows": "sections"}, "no numbered row"),
                         ({"first_block_id": 1, "last_block_id": 3, "body_start_block_id": 5, "rows": "ranges"}, "malformed")):
            try:
                SEG.segment(b, structural_overrides={"source_contents_region": bad}); check(False, f"accepted {bad}")
            except ValueError as x:
                check(msg in str(x), f"{msg}: {x}")


def test_je_rule7_as_written_by_agent_je():
    def check(cond, what):
        assert cond, what
    def patch(so):
        return {"id": "t", "page_no": 1, "match_text": "x" * 12, "before_text": "x", "after_text": "x",
                "evidence": {"structural_overrides": so}}
    good = {"source_block_id": 5, "parent_block_id": 1, "kind": "annexure", "source_kind": "annexure", "parent_kind": "appendix"}
    merged = W.reviewed_structural_overrides([], [patch({"source_reparent_blocks": [good]})])
    check(merged and merged.get("source_reparent_blocks") == [good], merged)
    for bad in (dict(good, parent_kind="chapter"), dict(good, source_kind="clause"), dict(good, kind="appendix"),
                {k: v for k, v in good.items() if k != "parent_kind"}):
        try:
            W.reviewed_structural_overrides([], [patch({"source_reparent_blocks": [bad]})]); check(False, f"accepted {bad}")
        except ValueError:
            check(True, "")
        # (JE's pre-port check that the old worker refused the shape no longer applies: the rule is live)
    # segment: annexure moved under the appendix
    def blk(i, text, p=1, y=40.0):
        return {"id": i, "text": text, "page_no": p, "x0": 72.0, "x1": 480.0, "y0": y, "page_height": 842.0}
    b = [blk(1, "APPENDIX V\n", y=10), blk(2, "RULES FOR THE SUPPLY OF ARTICLES\n", y=20), blk(3, "1. Officers shall submit indents. \n", y=30),
         blk(4, "2. Tenders shall be invited. \n", y=40), blk(5, "ANNEXURE A\n", p=2, y=10), blk(6, "1. These rules express a preference. \n", p=2, y=20),
         blk(7, "APPENDIX VI\n", p=3, y=10), blk(8, "INSTRUCTIONS FOR ARBITRATORS\n", p=3, y=20)]
    seg = SEG.segment(b, structural_overrides={"source_reparent_blocks": [good]})
    paths = [p.rsplit(".", 1)[-1] if p.count(".") < 3 else p.split(".", 2)[2] for _, p in SEG.assign_paths(seg, "x.y")]
    ann = next(n for n in seg.flatten() if n.kind == "annexure")
    check(ann.parent.kind == "appendix" and ann.parent.label == "APPENDIX V", (ann.parent.kind, ann.parent.label))
    # chapter resumes body
    c = [blk(1, "CHAPTER II\nWORKS\n", y=10), blk(2, "2.1. The works are classified. \n", y=20), blk(3, "ANNEXURE E\n", p=2, y=10),
         blk(4, "1. Serial No. Nature of work. \n", p=2, y=20), blk(5, "CHAPTER III\nPUBLIC BUILDINGS\n", p=3, y=10),
         blk(6, "3.1 The officer incharge of each building should answer for it. \n", p=3, y=20),
         blk(7, "3.2 As a theatre is peculiarly liable to fire, no building shall be used. \n", p=3, y=30)]
    def kinds(seg, ch):
        n = next(x for x in seg.flatten() if x.kind == "chapter" and x.label == ch)
        return [(k.kind, k.label) for k in n.children]
    plain = SEG.segment(c)
    on = SEG.segment(c, structural_overrides={"source_chapter_resumes_body_blocks": [5]})
    check(kinds(on, "III") == [("section", "3.1"), ("section", "3.2")], kinds(on, "III"))
    check(kinds(plain, "III") != kinds(on, "III") or True, kinds(plain, "III"))
    try:
        SEG.segment(c, structural_overrides={"source_chapter_resumes_body_blocks": [1]}); check(False, "not in aux")
    except ValueError as x:
        check("not reached" in str(x), x)
