"""Write the owner's policy cards for the recrawl queue (21 Oct 2026). Only decisions that are the owner's."""
import json
O = "/mnt/e/Nizam_e_Qanoon/.artifacts/decision-review/cards-recrawl/batch-recrawl.json"
OTHER = {"value": "other", "label": "Something else (write it in the notes)", "effect": "The lead follows your note."}
cards = [{
  "document_id": 0, "title": "Corpus-wide policies for the 21 Oct recrawl queue", "needs_owner": True, "reason": "",
  "kind": "other",
  "summary": "The recrawl released 3,037 new laws (4,744 -> 7,781). 830 stay held. These six choices decide how the rest are handled; everything else the lead settles itself.",
  "context": "Already settled without you: 2,342 repeated-number units closed by the rule tools; 689 badly OCR'd scans re-read (666 now pass); duplicates excluded (0 found). The lead will also settle the 'inverted', 'nesting', 'compendium' and 'probably-correct' numbering cases and the 341 contents rows that only need linking.",
  "questions": [
    {"id": "q1",
     "question": "67 scanned laws (2,257 pages, mostly 1855-1961 colonial and West Pakistan texts) have machine-OCR text too unreliable to release (average confidence 0.68, as low as 0.29). How should they be handled?",
     "evidence": "Example: doc 5679, Sind Live-Stock Improvement Act 1933 -- the page is clearly legible to a person, but tesseract scored 0.29. Doc 9266, Repealing and Amending Ordinance 1961, scored 0.39.",
     "pages": [{"page_no": 1, "render": "claude/renders/doc5679-p1.png", "sha256": "c974d0f5c2223b5ff25aaa0e404305d4caa2f11a89324b3aecffea5afeaff11e", "caption": "doc 5679 p1: Sind Act XXII of 1933 (OCR confidence 0.29)"},
               {"page_no": 2, "render": "claude/renders/doc9266-p2.png", "sha256": "1675a13cae36430738f6e56fe506f0815956ccf7ca11ba97236882f75e530f23", "caption": "doc 9266 p2: Repealing and Amending Ordinance 1961 (0.39)"}],
     "options": [
       {"value": "review-pack", "label": "Better OCR, then I review the pages", "effect": "The lead runs the stronger OCR (Surya) on them in the background and sends you OCR review packs (page image beside text, accept/correct, export JSON) in batches; released after your review."},
       {"value": "hold", "label": "Keep them held", "effect": "They stay unreleased and listed as 'scan too poor to release' until a better copy is found."},
       {"value": "release-flagged", "label": "Release the machine text, flagged", "effect": "Released now with a visible 'unreviewed machine OCR -- may contain reading errors' flag. Fast, but errors reach users."},
       OTHER], "recommended": "review-pack"},
    {"id": "q2",
     "question": "673 repeated-number cases in 313 laws are 'unclear': the same section number is printed twice and the corpus cannot tell which one is the law. How should they be settled?",
     "evidence": "Rule tools already closed every case the corpus can prove (2,342 units). What is left needs someone to look at the printed page.",
     "pages": [],
     "options": [
       {"value": "lead-reads", "label": "The lead reads each page and decides", "effect": "The lead renders each page, decides from the print (keep both / second is text of the first / renumber nothing), records the reading with the page image, and releases. Slower (days), no input from you."},
       {"value": "keep-parser", "label": "Accept the parser's choice, flagged", "effect": "The first occurrence stays citable, the second becomes non-citable text, and the law is released with a flag. Fast, but a wrong choice can hide a section from citation."},
       OTHER], "recommended": "lead-reads"},
    {"id": "q3",
     "question": "1,388 contents entries promise a section that is not found in the law's body (in 140 laws, mostly old scans). How should they be settled?",
     "evidence": "These need the page: either the section really is missing from this copy, or it is printed but the scan/parse lost it.",
     "pages": [],
     "options": [
       {"value": "lead-reads", "label": "The lead reads the pages and records each", "effect": "Each promised section is checked on the page: found (linked), genuinely absent from this copy (recorded as a source gap), or a parse fault (fixed and rebuilt). Released as each law clears."},
       {"value": "release-with-gaps", "label": "Release now with the gaps flagged", "effect": "Released immediately with 'contents lists sections not found in this copy' shown to readers; the lead fixes them later."},
       OTHER], "recommended": "lead-reads"},
    {"id": "q4",
     "question": "The Sindh portal (sindhlaws.gov.pk) has refused this machine's connections since about 1 a.m. on 21 Oct (likely an IP block after the crawl). 163 Sindh Acts are still to download. What should the lead do?",
     "evidence": "Both WSL and Windows get 'unable to connect' within ~3 seconds; Punjab, KP, Balochistan and federal sites answer normally. The download step is resumable.",
     "pages": [],
     "options": [
       {"value": "you-run", "label": "I will run the download from my network", "effect": "The lead gives you one command (tools/recrawl/run_land.sh sindh) to run on a network that can reach the portal; everything else is automatic."},
       {"value": "retry", "label": "Keep retrying from here", "effect": "The lead retries every few hours and lands them when the block lifts."},
       OTHER], "recommended": "retry"},
    {"id": "q5",
     "question": "Which further sources should the corpus cover? (Pick the broadest you want; write extras in the notes.)",
     "evidence": "Not yet crawled: FBR SROs (fbr.gov.pk, tax notifications, thousands), CDA/ICT regulations (21), Azad Jammu & Kashmir laws (law.gok.pk, ~600), Gilgit-Baltistan Acts (28 + older, poor site).",
     "pages": [],
     "options": [
       {"value": "pakistan-only", "label": "Pakistan only: add FBR SROs and ICT/CDA", "effect": "The lead crawls FBR SROs and CDA regulations next; AJK and GB stay out."},
       {"value": "all", "label": "Everything: also AJK and Gilgit-Baltistan", "effect": "The lead also crawls law.gok.pk (AJK) and the GB Assembly, each as its own jurisdiction."},
       {"value": "none", "label": "Nothing more for now", "effect": "The corpus stays at the five portals plus the Ministry of Law archive."},
       OTHER], "recommended": "pakistan-only"},
    {"id": "q6",
     "question": "680 federal Ordinances were added from the Ministry of Law archive. Many lapsed after 120 days or were replaced by Acts. How should their status be shown?",
     "evidence": "Today every Ordinance shows status 'unknown'. An Ordinance's lapse is a legal fact the text alone does not prove (some were extended, re-promulgated or enacted).",
     "pages": [],
     "options": [
       {"value": "mark-replaced", "label": "Mark 'replaced' only where an Act of the same name follows", "effect": "Where the corpus holds a later Act with the same title, the Ordinance is linked to it and shown as replaced; all others stay 'unknown'."},
       {"value": "leave", "label": "Leave every Ordinance as 'unknown'", "effect": "No status is inferred."},
       OTHER], "recommended": "mark-replaced"}]
}]
json.dump(cards, open(O, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", O)
