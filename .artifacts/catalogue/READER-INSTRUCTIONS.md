# Catalogue reader instructions (Step 1: diagnose only)

You are reading source pages of Pakistani statutes to diagnose why an instrument
is withheld from release. **You change nothing.** No database writes, no edits to
repository files, no git. The only files you create are your result files.

## Environment

- Windows host. Repo root: `E:\Nizam_e_Qanoon`.
- **Page images:** open with the Read tool. Shard paths are repo-relative with
  forward slashes (e.g. `.artifacts/catalogue/pages/doc169-p3-3.png`); read them as
  `E:\Nizam_e_Qanoon\.artifacts\catalogue\pages\doc169-p3-3.png`.
  Audit images are given as `/mnt/e/nizam-data/s7-audit/X.png`; read them as
  `E:\nizam-data\s7-audit\X.png`.
- **Read-only database lookups** (use the Bash tool, exactly this form, single quotes):
  ```
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh subtree <candidate_id>'
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh page <document_id> <page>'
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh tree <document_id> <from_page> <to_page>'
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh grep <document_id> "<regex>"'
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh entry <toc_entry_id>'
  ```
  `subtree` shows every node and block of text under a demoted S7 unit. `page` shows
  the extracted blocks on a page (exact text, x/y position, which provision owns it).
  `tree` shows the provision tree for a page range. `entry` shows a contents entry
  with its neighbours and what each is linked to.
- If you need to see a page that was not rendered, render it into your own folder:
  `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .render_page.sh <document_id> <page>'`
  It prints a repo-relative path such as `.artifacts/catalogue/pages/doc4441-p140-140.png`;
  open it as `E:\Nizam_e_Qanoon\.artifacts\catalogue\pages\doc4441-p140-140.png`.

## What a shard contains

`instruments[]`, each with `document_id`, `instrument_id`, `title`, `body_starts_page`,
and `defects[]`. Each defect is one of:

- **`contents_gap`**: the printed contents promises `label` / `printed_heading`, but no
  provision is linked to it. `contents_page` is where the entry is printed.
  `body_hit_page` / `body_hit_text` is where the label seems to be printed in the body
  (text search; may be wrong or absent). `pages` / `renders` are the pages to read.
- **`s7_unit`**: two units carried the same label. The segmenter kept one (`kept_page`,
  `kept_text`) and demoted the other to a non-citable node (`demoted_page`,
  `demoted_text`); `demoted_subtree_chars` is how much text sits under the demoted node.
  If `already_read` is true, a source reading was already recorded (`prior_resolution`,
  `prior_observation`): do NOT reread it, just classify it from that observation.
- **`quality_gate`**: the document failed a quality check; report what it is.

## For every defect, decide

1. **What the page actually prints.** Read the images. Quote the exact printed words.
2. **stage**: where the problem was caused. One of:
   - `source` (the PDF itself misprints, repeats a number, is truncated, blank, duplicated),
   - `extraction` (the text layer differs from the page: OCR misread, superscript flattened, stray glyph),
   - `segmentation` (text is right but it was split or nested wrongly),
   - `adjudication` (an earlier decision was wrong),
   - `none` (nothing is wrong: e.g. the demoted unit is correctly apparatus).
3. **class** (pick the closest; use `other` and explain if nothing fits):
   - Apparatus, correctly not a section: `contents_entry`, `circulation_list`, `table_row`,
     `form_field`, `footnote`, `marginal_note_fragment`, `quoted_amendment_text`,
     `running_header_or_masthead`, `duplicate_scan`, `blank_page_marker`
   - Law hidden or misplaced: `inversion_real_section_demoted`, `footnote_or_heading_absorbs_law`,
     `nested_list_at_root`, `subsection_printed_as_number`, `section_nested_as_clause`,
     `wrapped_heading_crossref`, `quoted_substitution_is_section_body`,
     `per_part_numbering_restart`, `two_instruments_one_document`, `compendium_mixed_content`
   - Numbering: `source_misnumbering_duplicate`, `contents_misprint`, `ocr_digit_misread`,
     `superscript_marker_fused`, `stray_glyph`, `missing_period_or_comma_in_number`,
     `amendment_bracket_prefix`
   - Contents gaps: `printed_but_missed`, `printed_under_other_label`,
     `omitted_or_repealed_marker`, `not_printed_in_body`, `truncated_or_missing_pages`,
     `contents_row_is_not_a_section`, `heading_only_no_number`
4. **fix**: one of `accept_non_citable`, `restore_citable`, `reparent`, `split_instrument`,
   `reject_candidate`, `curation_patch`, `disposition_omitted`, `disposition_repealed`,
   `found_elsewhere`, `absent_in_source`, `parser_rule`, `reacquire_source`, `needs_second_read`.
5. **fix_detail**: whatever the fixer will need, e.g.
   `{"patch_page": 11, "patch_before": "26. An employee appvinled", "patch_after": "28. An employee appvinled"}`,
   `{"found_label": "462N", "found_page": 161}`, `{"belongs_under": "section 389"}`,
   `{"parser_rule": "section nested as clause by indentation"}`,
   `{"truncation_evidence": "PDF ends at page 7 mid-sentence; footer says Page 7 of 12"}`.
6. **confidence**: `high`, `medium` or `low`.

## Traps (each of these has already caused a wrong reading)

1. **Never choose `accept_non_citable` without checking the subtree** when
   `demoted_subtree_chars` >= 120: run `.cq.sh subtree <candidate_id>`. A footnote or
   table-row node often has the next section's operative text under it (Penal Code
   section 158's tail sat under a footnote). If law is under it, the fix is `reparent`.
2. **The kept unit may itself be junk** (a contents entry, masthead, letterhead, the
   title block). If the real section was demoted, that is an inversion: `restore_citable`.
3. **A matching first sentence is not a duplicate.** Compare the whole text before
   calling anything a duplicate scan.
4. **Quoted amendment text** ("the following shall be substituted:-" then a quoted
   section) is not a section of the amending law. But if the quoted text is the whole
   substance of the amending section, accepting it creates a stub citation: `reparent`.
5. **Curation patches restore what the page prints**, or what the document's OWN printed
   contents corroborates. `patch_before` and `patch_after` must be exact substrings of
   the extracted text (check with `.cq.sh page`). Never infer a number from outside
   knowledge or from what the law "should" say.
6. **Superscripts**: a footnote marker before a number is often flattened
   (`¹1.` becomes `11.`, `⁴*[294B.` becomes `4*[294B.`). Look at the image.
7. **Absent sections**: read the pages on both sides of where the section should be.
   Check footers ("Page 7 of 12") and whether text stops mid-sentence, to tell a
   truncated PDF (`reacquire_source`) from a section genuinely not printed.
8. **An indented section** under a centred cross-heading can be nested as a clause of
   the previous section (Penal Code 390 under 389): `parser_rule`.
9. **When unsure, say so:** `fix = needs_second_read`, `confidence = low`. A wrong
   confident answer is worse than an honest unsure one.

## Output

Write ONE JSON file per document, as soon as you finish that document, with the Write
tool, to:

`E:\Nizam_e_Qanoon\.artifacts\catalogue\results\<shard name>\doc<document_id>.json`

Content: a JSON list with one object per defect:

```json
[
  {
    "defect_key": "536712",
    "kind": "contents_gap",
    "document_id": 4441,
    "instrument_id": "11a7e03a-...",
    "label": "390",
    "pages_read": [{"page": 139, "file": ".artifacts/catalogue/pages/doc4441-p139-139.png"}],
    "stage": "segmentation",
    "class": "section_nested_as_clause",
    "fix": "parser_rule",
    "observed": "Page 139 prints the cross-heading 'Of Robbery and Dacoity' and, indented, '390. Robbery. In all robbery there is either theft or extortion.' The tree holds it as clause 390 under section 389.",
    "fix_detail": {"parser_rule": "section nested as clause by indentation", "belongs_under": "root, as section 390"},
    "releases_if_fixed": true,
    "confidence": "high",
    "notes": ""
  }
]
```

`defect_key` is the `toc_entry_id` for a contents gap, the `candidate_id` for an S7
unit, and `"quality"` for a quality gate. `observed` must quote what the page prints
(at least 60 characters). Avoid backslashes in text. Write every defect of the
document, including `already_read` ones.

When the whole shard is done, reply with a short summary: documents done, defects by
fix type, and any document you could not finish and why.

## Resuming a shard

Readers were stopped part-way through several shards. **Before reading a
document, check whether `results/<shard>/doc<document_id>.json` already exists
and contains a row for every defect of that document. If it does, skip it.** If
it exists but is missing defects, read the missing ones and rewrite the file
with all rows.

`defect_key` must be copied from the shard (`toc_entry_id` or `candidate_id`).
Never take it from a render filename such as `doc2308-e477830-label20-p9.png`:
those ids come from an older inventory and the rollup rejects them.

## Patterns already confirmed across shards

Recognise these quickly, but still read the page -- each has exceptions.

a. **A four-digit year read as a label.** A wrapped title or citation puts
   `1972.` at the start of a line and the parser makes a contents entry or a
   section numbered 1972. Not law: `reject_candidate` for a phantom entry,
   `parser_rule` when it swallowed real sections.
b. **The contents region overruns the body.** Body blocks tagged
   `role=contents` with no owner; sometimes the body is then built from the
   page's footnote numbers. `parser_rule`.
c. **A section number printed bare, in parentheses, or with no period**
   (`8 (1) Government may`, `(3) Subject to`, `4 \n1) Appointment`).
   `curation_patch` when the contents corroborates the number.
d. **Contents renumber lettered insertions** (body `4-A`..`4-E`, contents
   `5`..`9`). `found_elsewhere` to the lettered section.
e. **A superscript footnote marker fused to the number**: printed `¹1.` extracts
   as `11.`, `¹6.` as `16.`. `curation_patch`, corroborated by the contents and
   usually by the footnote text itself.
f. **Numbering restarts** under a lettered/Roman part heading or in an appended
   Schedule of Statutes, while the contents continues or restarts differently.
   `found_elsewhere` into the schedule, or `parser_rule` for part headings.
g. **A number set tight against its text** (`20.The Protection Committee may`,
   `14.Information acquired`). No opener accepts it. `parser_rule`.
h. **Annotated editions**: numbered case-law footnotes (`12. Hakim-ud-Din v.
   Government of West Pakistan, PLD 1960 Lah. 709`) kept as sections while the
   real rules with those numbers are demoted. `restore_citable`.
i. **Stacked amendment brackets** (`5[4[19. Lepers from Acceding States`). The
   opener allows one marker-plus-bracket, not two. `parser_rule`.

## A curation patch may never supply legal text

A patch corrects the parser's INPUT -- a number, a period, a bracket, a line
join. It restores what the page prints at the point the parser reads. It must
never add words of law, and `patch_after` should almost never be more than a
few characters longer than `patch_before`.

If a page appears to print text that the database does not hold, do NOT
transcribe it. Prove it first:

```
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh grep <doc> "<a distinctive phrase>"'
```

and compare the page's stored characters with the PDF's own text layer before
claiming loss. One row in this catalogue claimed a whole section was missing and
proposed to type 624 characters of law into the parser input; the page's stored
text in fact matched pdftotext to within two characters. Real extraction loss is
reported as `stage: extraction` with the evidence, and it is fixed by
re-extracting that page, never by transcription.

## More patterns confirmed since (j onwards)

j. **The section number set in its own column.** The commonest defect in the
   corpus: the number is one block (`"15"`, `"22."`) and the heading and text are
   others, so no opener sees them together. 14,943 blocks in 991 documents are a
   bare number. Diagnose as `parser_rule`, quoting the block ids.
k. **A number set tight against its heading** (`20.The Protection Committee`,
   `3.The privilege etc`, `14.Information acquired`). `parser_rule`.
l. **A marker-and-bracket at a BLOCK START** (`128[6-A. Furnishing`,
   `13. 7[Lecturer`). The inner splitter accepts these mid-block; the block-start
   classifier does not. `parser_rule`.
m. **A comma where the period should be** (`26A, Punishment`, `30, (1)`,
   `22, Deposits`). `curation_patch`, corroborated by the contents.
n. **The source printing two different provisions under one number** (documents
   4537, 4549, 4568, 4571, 3939, 3949, 3509). Neither side is apparatus, so
   `accept_non_citable` would lose law and `restore_citable` would lose the
   other. Record `parser_rule` and say plainly that the corpus has no way to
   cite both yet — do not pretend a decision settles it.
o. **A date or a quantity read as a label** — `24.02.2014`, `1.000 Million`,
   `7.5%`, tariff code `9903.0010`. `reject_candidate` or `accept_non_citable`.
p. **A contents row carrying several labels in one line** (`18. | 18-A | 18-B`)
   or fusing one entry's heading with the next entry's number. `parser_rule`.
q. **A roster of people or an endorsement list** numbered 1, 2, 3 (addressees,
   committee members). Apparatus: `accept_non_citable`, or `reject_candidate`
   when it produced a contents row.
r. **The contents and the body numbered differently** — an offset of one or two,
   or a contents that renumbers an appended Schedule of Statutes. Match by
   HEADING, not by number, and say what the offset is. `found_elsewhere`.

## Patterns confirmed on 17 Sep (s onwards)

s. **The number stranded at the END of the previous block.** The column-layout
   defect (j) has a second shape: PyMuPDF appends the left-hand number cell to
   the paragraph block ABOVE, so the block holding section 11's text ends with a
   line that is only `12.`, and the block where section 12's text starts opens
   with `(1)`. Look at the TAIL of the preceding block before concluding a
   number is missing. Confirmed in documents 3751 (block 466094) and 3276
   (block 342219); `pdftotext -layout` prints the number in its right place in
   both. 2,047 blocks in 333 documents end this way, and in 13 documents the
   stranded number is the very label a pending gap names — 98 gaps, 78 of them
   in document 4498. `parser_rule`, and quote both block ids.
t. **A footnote-marker LIST before the amendment bracket.** The opener strips one
   plain digit (`1[3. Appointment`, `2[116. Power`) but not a list, and not a
   marker with a letter suffix: `1a,25[3A.`, `14a,129[19C.`, `44a,94,130[25D.`,
   `7,31[82.`, `5a[193A.`, `9,81[194A.`, `16a[203A.`, `24[(21A.`, `7, 8112.`,
   `1, 2115.`. Document 4451 loses thirteen sections to it and document 4501
   four. Always name the sibling on the same page that DID resolve — it is what
   proves the discriminator. `parser_rule`.
u. **A label inside the bracket with no period** — `4[5 –Delegation of powers.-`,
   `10[83C Cargo Tracking System`, `2[193 Appeals to Collector`, `1[27 A].(1)`,
   `1[11].`, `4[7-A (1)`. `parser_rule`, or `curation_patch` when the label is
   unambiguous and the contents corroborates it.
v. **Footnote lines read as sections.** A consolidation that prints its footnotes
   as numbered lines at the foot of each page (`1. Subs. by the Central Laws...`,
   `107. Substituted for the words "and" by F.A.,2014`) gives the opener numbers
   that run to 107, 129, 130. When such a node carries a subtree it has swallowed
   operative text, so `accept_non_citable` is wrong — use `reject_candidate` and
   say how many characters must be placed. Documents 4451 and 4453.
w. **A specification or schedule table whose rows became the top-level units.**
   Then every collision in the document is against a table row, and BOTH sides of
   some collisions are table rows. Say so: rejecting the candidate is right, but
   it does not put the document right on its own, because the kept side is a
   table row too. Document 4460 (pages 10 to 12) and document 3730.
x. **One amending Act carrying a schedule of per-instrument amendment blocks,**
   each restarting at 1. Document 4089 is forty-six defects of this one shape.
   `reparent` for the S7 units, `parser_rule` for the contents rows, and check
   the reading order — the item is often extracted BEFORE the heading it belongs
   to.
y. **The contents running several numbers ahead of, or behind, the body.** (r)
   again, but check how far it runs: document 4460's contents is FOUR behind
   throughout, and document 3277's is one ahead from section 33 because the
   printed contents repeats a chapter heading and invents an entry. In 3277 the
   matcher paired them positionally and three ACTIVE provisions now carry the
   wrong heading — when you find an offset, say whether provisions were
   mis-headed by it, because that is wider than the gap you were asked about.
z. **A collision whose kept and demoted sides open on the SAME block.** The block cannot tell
   you which unit is which. Read the two provisions (`segmentation_structural_candidate.
   candidate_provision_id` is the demoted unit, `canonical_provision_id` the kept one): their
   own text and child counts. In documents 3401 and 3823 the block looked like a harmless
   double reading, but the demoted provision was the real definitions section with its
   children and the kept one was section 1's commencement sub-section mislabelled 2. Calling
   such a pair a duplicate and accepting it would have retyped the definitions section as a clause
   under the root while a commencement clause kept the section's number.
aa. **Before `accept_non_citable`, read the demoted node's DESCENDANTS' text, not just its first
   block and not just their node kinds.** A footnote, a fee cell, a tariff code, a form field or
   a programme-list row can open a node that swallows the operative text printed after it.
   Found on 17 Sep by querying every accepted row: document 3901's footnote held definitions (6)
   to (10); 4397's fee cell held sub-rules (2) to (6); 4467's corrigendum footnote held
   definitions; 4502's tariff code held amending instructions and its rate cell held paragraphs
   (b) to (e); 4591's form field held '(II) Proper arrangements shall be made...'; and 4077's
   rows were written from one generic reading when the demoted units were the examination
   regulations themselves. The query is in `.q_acc4.sql`: any descendant whose text matches
   `shall|means|may not|is hereby|are hereby` is a stop sign. **Ask the same question of the
   node's OWN blocks past the first**, not only of its descendants: the first block is the
   opener -- the label, heading, fee cell or footnote line that wrongly opened the unit -- and
   everything after it is text the unit absorbed. A node with no children at all can still hold
   several blocks of law. Found on 18 Sep by the reader working shard defects-36: document
   4497's candidate 344983a9 reports zero stop-word descendants while the block it owns, 890143,
   carries rule 6's proviso and its sub-rule (2). Run over every accept on record, that widening
   questions **83 of 8,779**, holding 99 operative blocks -- the worst being document 3213's
   label 5 with 2,947 characters, and document 4421's label 145, "Whoever commits any of the
   offences specified in Part-I of the Fourth Schedule shall be punishable with...".
   `tools/audit/accepted-demotions-own-blocks-carry-law.sql` re-derives the queue. When it
   fires, use
   `reject_candidate` (or `restore_citable` if the demoted node is itself the provision) and say
   where the swallowed text must go. Note what accept does mechanically: it retypes the demoted
   'section' as a clause under the SAME parent, keeping its subtree -- so nothing is deleted, but
   swallowed law is left addressed under the wrong node, and a citation rendered from that record
   names the wrong provision.

bb. **A footnote quoting an old section is sometimes the thing to KEEP and sometimes the thing
   to demote -- only the live text settles which.** Consolidations footnote every amendment by
   quoting the text they replaced, and that quotation matches the operative stop-words, so both
   sides of such a collision look like law. The two cases are mirror images and the difference
   is which side the CURRENT text falls on.
   * Income Tax Ordinance, 2001, section 133 (document 4489, page 289 against page 291). The
     unit holding the number is block 864220, a footnote: "1Section 133 substituted by the
     Finance Act, 2005. The original section 133 read as follows: 133. Reference to High
     Court.- (1) Where the Appellate Tribunal has made an order on an appeal under section132,
     the taxpayer or Commissioner may, by application ... require the Appellate Tribunal to
     refer any question of law ... to the High Court." The operative section -- "Within sixty
     days ... the aggrieved person or the Commissioner may file a reference ... before the High
     Court" -- is demoted beneath it. A citation of section 133 renders repealed procedure as
     current law: ninety days to the Tribunal instead of sixty days to the High Court.
     `restore_citable`.
   * Customs Act, section 179 (document 4451, page 215 against page 227). Same shape, opposite
     polarity. The unit holding the number, block 815670, is the LIVE section: "15[179. Power of
     adjudication.- (1) ... confiscation of goods or recovery of duty and other taxes not
     levied, short levied or erroneously refunded, imposition of penalty or any other
     contravention under this Act". The demoted unit, block 815790, opens "1c. 179. Powers of
     adjudication.- (1) ... confiscation of goods or imposition of penalty under this Act" --
     the marker `1c.` is a footnote number and what follows is the superseded text quoted in
     that footnote. Here the accept is CORRECT.
   Read the two texts against each other before deciding. They differ exactly where the
   amendment did -- in 179 the live text adds recovery of duty and any other contravention --
   and that difference, not which block looks more like a footnote, is what tells you which side
   is current. Neither a "Section N substituted by" preamble nor a fused footnote marker is
   proof on its own: the marker sits in front of the live section in 179 and in front of the
   repealed quotation in 133.
