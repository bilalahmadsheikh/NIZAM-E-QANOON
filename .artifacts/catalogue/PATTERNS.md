
## Pattern: a four-digit year read as a contents entry label

Found while reading shard defects-01 (documents 523 and 559). A wrapped title
block on the body's first page puts a year at the start of a line -- `An Act to
amend the Sind Wildlife Protection Ordinance,` / `1972.` -- and the contents
extractor opens a contents entry numbered 1972. The instrument's real contents
sit on an earlier page and are fully linked; the phantom entry can never link,
so the instrument is withheld forever.

Corpus-wide: **21 pending contents gaps across 19 instruments** carry a label
matching `^(18|19|20)[0-9][0-9]$`. Documents: 523, 559, 1051, 1079, 1142, 1319
(x2), 1368, 1577, 1806 (x2), 2009, 2370, 2373, 2475, 2658, 2856, 3184, 3190,
3812, 4409. Their headings are mastheads (`2[KHYBER PAKHTUNKHWA] ORDINANCE No.
VIII OF 1980`), assent lines, `CONTENTS`/`CONTAINTS` headers, or bracket
fragments -- none is a section heading.

Each still needs its page read before the rule is applied to it, but one parser
rule plus a replay clears all of them.

### The same year defect on the body side

Document 838 shows the twin of the contents-side defect: definition (m) ends
`...excluding urban area as defined in the Sind Local Government Ordinance,` /
`1979.` and the parser opened a **section 1979** at root from the wrapped year.
Sections 3 and 4 (printed `(3)` and `(4)`) then nested under it. So the rule
must cover both: a four-digit year at the start of a wrapped line is not a
section opener and not a contents entry.

## Pattern: the contents region overruns into the body

Three of the twenty-five documents in shard defects-01 fail the same way. The
parser's contents region does not stop at the end of the printed contents: it
keeps consuming blocks into the body until it meets something that looks like a
numbered sequence starting at 1.

- **362** (Defence Housing Authority Quetta Act 2015): the preamble, section 1,
  is tagged `role=contents` with no owner. The region closes at section 2, whose
  marginal note happens to sit in its own block. Section 1 is stranded.
- **904** (Civil Jails Act 1874): every block on page 2 is tagged contents. The
  parser made contents entries out of the body's sections 8 and 9, left sections
  9 and 10 with no provision at all, and then opened sections on the page's
  footnote numbers -- including a `section 154` from the page reference
  "pp. 111, 152 and 154".
- **983** (Municipal Taxation Act 1881): the region runs through the whole of
  page 3 and closes on the footnote block, so the tree's sections 1 to 10 ARE
  footnotes 1 to 10. Contents entries 1 to 6 are linked to them. A citation of
  section 3 returns footnote 3.

The common signature is queryable without reading a page: **an instrument with
`role=contents` blocks that carry no owner on a page at or after
`body_starts_page`**, or **a provision whose only text block is a footnote**.
Worth counting corpus-wide before the fix phase; one parser rule (close the
contents region at the first body unit; never open a section on a footnote
block) covers all three.

## Measured: two systemic defects, most of them inside RELEASED instruments

Both counted on the live corpus while the readers were running.

**1. Sections named after a year.** `provision.kind = 'section'` with a label
matching `^(18|19|20)[0-9][0-9]$`: **236 provisions in 218 documents**. 111 hold
no text at all; the rest hold a masthead (document 244's "section 1981" is
`1981. 2[KHYBER PAKHTUNKHWA] ORDINANCE NO.VI OF 1981. 30th June. 1981. AN
ORDINANCE`) or a bare date (document 284's "section 1898" is `1898.`).
**210 of them are in instruments that are already released** -- so the release
today contains 210 citable "sections" that are not sections.

**2. Operative text stranded in a contents region.** Blocks assigned to the
active assignment set with `provision_id IS NULL`, `role = 'contents'`, longer
than 200 characters and containing `shall` or `may`:
**1,985 blocks, 842,975 characters, across 322 instruments -- 247 of them
released.** A sample of ten: eight were operative law (`21. Retention of lien.-
A confirmed employee shall acquire lien against the post held by him...`,
`(1) Every hotel owner shall within 7 days of the close of each calendar month
furnish to the District Officer...`), two were genuine contents lists whose
headings happen to contain "may". So the signature over-counts by roughly a
fifth and still leaves most of a megabyte of law present in the corpus and
citable from nothing.

Query, for re-derivation:

```sql
SELECT count(*), count(DISTINCT bas.instrument_id), sum(length(tb.text))
  FROM provision_block pb
  JOIN block_assignment_set bas ON bas.id = pb.assignment_set_id AND bas.is_active
  JOIN instrument i ON i.id = bas.instrument_id AND i.is_active AND i.duplicate_of IS NULL
  JOIN text_block tb ON tb.id = pb.block_id
 WHERE pb.provision_id IS NULL AND pb.role = 'contents'
   AND length(tb.text) > 200 AND tb.text ~* '(^|[^a-z])(shall|may) ';
```

Neither defect blocks a release gate, which is why neither was visible in the
gate counts. Both bear directly on the standing rule that everything in the PDF
must be in the database and every law must be citable.

**The mechanism behind #2, and its size against the gap queue (18 Sep 2026).**
The contents role is not applied to the wrong kind of block at random: it is
applied correctly to the printed contents list and then *not switched off*. Where
the printed list ends is knowable -- it is the last page any `v_toc` entry was
read from -- and for **3,016 of 3,161 instruments the contents role outlasts it**,
by up to **14 pages**. Document 4498, the Punjab Police Promotion Rules 1934, is
the clearest case: its first provision does not begin until page 76, and page 30
is already operative law -- `1-16. Duties of Superintendent towards District
Magistrate.- The primary duty of the Superintendent of Police...` -- filed as
contents and attached to nothing. Document 2844, the Foodgrains (Licensing
Control) Order 1957, has its definitions, its licensing clauses and its penalties
in the same condition.

Ranked against the 928 still-open contents gaps, this is the larger of the two
levers by a factor of four: **143 gaps across 50 instruments (15.4%)** name a
label that opens one of these stranded blocks, against **36 gaps (3.9%)** for the
stranded-number shape above. Beyond the gap queue it strands **914,094 characters
across 437 documents** -- law that is in the database exactly as the PDF prints
it, and that no citation can reach, because provisions are the citable unit
(INV-4) and these characters belong to no provision.

Re-derive with `tools/audit/contents-region-overrun.sql`. Note that
`provision_block` is append-only and keeps retired assignment sets: every query
there joins `block_assignment_set` on `is_active`, and omitting that filter
multiplies every count by the number of times the document was re-segmented
(document 4498 reads 3x too high without it).

## Acquisition: eight "not a PDF" exceptions are valid PDFs behind an injected HTML prefix

The Punjab Code portal — and the Balochistan Code portal for at least one file —
prepends exactly **110 bytes** of HTML to every file it serves:

```
<head>
<meta name="google-site-verification" content="gaZIe_A75rY1YmkYEAcA7Zr7oUKSoNe7YdYntMBmkPY" />
</head>
```

The response is `HTTP 200`, `Content-Type: application/pdf`, and the body becomes
a real PDF at byte 110. Poppler, a browser and a fetching agent all parse it, so
it *looks* fine to a reader; the acquisition pipeline reads the first four bytes,
does not find `%PDF`, and correctly refuses it. That is why these were recorded
as `served_content_is_not_a_pdf` — the reason was right about the bytes and wrong
about the cause. They are not Word documents.

Verified byte-for-byte today on all eight: exceptions **10, 13, 17, 21, 30, 36,
38** (punjabcode.punjab.gov.pk) and **39** (balochistancode.gob.pk). After
stripping, each parses and carries its own title — `ELECTRICITY ACT, 1910`,
`THE NATURALIZATION ACT, 1926`, and for 39 an Author of `Law Department`, created
22 March 2021. Exception 10's file is a single page, and that page is the Act's
repeal notice (`Repealed by the Punjab Laws (Amendment) Act 2011 (VI of 2011),
w.e.f. 20.4.2011`) — that is genuinely what the portal publishes.

**This is a decision for the corpus owner, not a silent fix.** Stripping means
the stored blob is not byte-identical to the served response, so the observation
would have to record both sha256 values and the normalisation as declared
evidence. What is settled is the fact: eight declared exceptions are recoverable,
and 400 sampled landed blobs were checked — every one begins with `%PDF`, so
nothing already in the corpus carries this injection.

## One landed blob is truncated

Document 4608, the Sindh Local Government (Amendment) Act 2014, landed with
HTTP 200 and 98,171 bytes from sindhlaws.gov.pk, but the file has no `%%EOF`
marker and poppler cannot read its xref table. PyMuPDF recovers text with a
space between nearly every character, which is why the document's quality gate
reads `character_outcome = unverifiable` and `order_outcome = unverifiable`.

Every one of the **4,600** landed blobs was scanned for a missing end-of-file
marker. **This is the only one.** It needs refetching, re-extraction and a
replay; the acquisition check should also test for `%%EOF`, not only the leading
`%PDF` magic bytes.

## A plural disposition word the opener does not accept

The Succession Act 1925 prints its repealed section as `392. [Repeals.] Rep. by
the Repealing Act, 1927 (XII of 1927), s. 2 and Sch.` The segmenter has an inner
opener for exactly this shape -- a number, a period, a bracketed disposition word
-- but its word list is `Repeal(ed)?|Omitted|Deleted`, so the word boundary after
`Repeal` fails against the `s` of `Repeals`. The section never opens and stays
inside the preceding one.

Corpus-wide: **30 blocks in 27 documents** print a bracketed plural disposition
after a number (`18. [Repeals; who may be witnesses...`, `6. [Repeals.`,
`9. [Repeals.`), and **6 of those documents carry pending contents gaps**. One
word added to the list closes them.

## The biggest single lever: section numbers set in their own column

Many Pakistani Gazette instruments print the section number in one column and
the heading and text in another, so the extractor emits the number as a block of
its own:

```
block 703044  " | FUNCTIONS OF THE COUNCILS | | |40 |(1) |A Council shall, subject to rules..."
block 705221  "15"
block 262346  "... |22. |"      block 262347  "Other Auditors."
```

Every opener the segmenter has expects the number and the text it opens to be
adjacent in one block, so these sections are never created. Documents diagnosed
with this shape so far: 2800, 2860, 2862, 3014, 3665, 3979, 4004, 4026, 4364,
4369 -- and in document 2800 it is visible that only the sections whose number
happened to share a block with their text (13 to 16, 20, 22, 24) linked at all.

Measured corpus-wide: **14,943 blocks in 991 documents** consist of nothing but
a section number. Of those documents, **117 carry pending contents gaps, 396 of
them**, and **181 withheld instruments** sit in documents with this shape.

The rule must be written carefully -- a bare number is also a page number, a list
marker or a table cell -- so it should require the neighbouring block to open a
heading or operative text AND the number to continue the document's own
sequence. But no other single change reaches as many withheld instruments.

## The same lever, second shape: the number stranded at the END of the previous block

The column-layout lever above counts blocks that are *nothing but* a number.
PyMuPDF does not always isolate that cell: often it appends it to the paragraph
block above, so the number becomes the last line of the *previous* section's
text and no block begins with it.

```
doc 3751 p13  block 466094  "(6) A resonation recommending ... absent my deem fit.\n\n12.\n"
              block 466095  "(1) Three shall be a Registrar of the University ..."
doc 3276 p11  block 342219  "... conducive to the attainment of the objects of the Authority. 12."
              block 342221  "(1) All business of the Authority shall ..."
```

Both documents lose exactly one section this way, and in both the NEXT section
survives because its number happened to come out fused with its own text
(`13. (1) There shall be a measure of the University ...`). `pdftotext -layout`
on the landed blob prints the number in its proper place in both cases, so
nothing is missing from the PDF -- the digits are in `text_block`, in the wrong
block.

Measured corpus-wide: **2,047 blocks in 333 documents** end with a line that is
nothing but a section number. Those documents carry **193 pending contents gaps
across 56 documents**; and in **13 documents the stranded number is the very
label the gap names -- 36 pending gaps**, 3.9% of the 928 still open:

| document | instrument | gaps | labels |
|---|---|---|---|
| 4498 | Punjab Police Promotion Rules 1934 | 18 | 1,2,4,5,6,7 |
| 2852 | PESSI (Benefit) Regulations, 1967 | 5 | 1,3,4,5 |
| 3929 | Punjab Auqaf Organization (Appointment of Conditions of Service) Rules, 1994 | 2 | 25,30 |
| 4450 | Sindh Civil Servants Promotion (BPS-18 to BPS-21) Rules, 2022 | 2 | 1 |
| 3276 | Sind Katchi Abadis Ordinance, 1986 | 1 | 12 |
| 2374 | Auqaf Service Rules, 1994 | 1 | 30 |
| 3348 | Karachi Water & Sewerage Board Employees (Probation, Confirmation & Seniority) Rules, 1987 | 1 | 15 |
| 3512 | Sind Regional Plan Organization Employees (Travelling Allowance) Rules, 1989 | 1 | 5 |
| 4004 | Sindh Town Municipal Administration Rules of Business, 2002 | 1 | 12 |
| 3334 | Karachi Water and Sewerage Board Employees (Appointment, Promotion and Transfer) Rules, 1987 | 1 | 4 |
| 2784 | Sind Local, Taluka and Sub-Divisional Zakat and Ushr Committees (Constitution) Rules, 1979 | 1 | 14 |
| 2860 | Sindh Bank Act, 1995 | 1 | 22 |
| 3069 | Punjab Seed Corporation Contributory Provident Fund Regulations | 1 | 5 |

Document 4498 alone accounts for 18 of them. The same guard applies as above:
require the next block to open operative text and the number to continue the
instrument's own sequence, because a trailing number is also a page number.

Re-derive with `tools/audit/stranded-number-lever.sql`.

**Corrected, 18 Sep 2026.** This table first read 98 gaps, 10.6%, and 78 for
document 4498. That was a join artefact: sections 3 and 4 of the lever file
counted `count(*)` over a join of the gap queue against the stranded blocks, so
a gap whose label was stranded in four places was counted four times. The join
now counts `count(DISTINCT g.toc_entry_id)`. The shape is real and the documents
are the same thirteen; the size was overstated 2.7x. The agent cataloguing
document 4498 refused the number rather than the rule, and was right to.

**And the remaining 36 are an upper bound, not a verified set.** The signature
asks only that some block's last line be a bare number matching the gap's label,
and two of the rows -- document 4450's, both labelled "1" -- do not hold: every
block there whose last line is a bare number is either a rate-table cell
(`2. B: Very Good 80 to 90% 85.00% 7.650 5.`) or photocopy gutter noise
(`6;' "'f'~Ii!1i}?i'I';~~:~tlt~i:ik`). That document's real defect is the
contents-region overrun below -- 199 unowned `role=contents` blocks over pages
1 to 7, 19,963 characters, so its rules 1 to 10 are in the corpus and citable
from nothing, and what survives is labelled `1.70`, `1.4`, `50 I` and `75`.
Read the rows before quoting the total; the lever is a queue to review, not a
count of confirmed defects.

## A small one, precisely bounded: footnote markers fused to a section number

The opener strips ONE footnote marker fused to a section number but not a
comma-separated list of them. Document 4501 -- the Code of Criminal Procedure,
which this document holds twice -- shows both behaviours on the same two pages:

```
block 920463  "8114. Summons or warrant in case of person not so present..."   -> section 114 exists
block 920468  "2116. Power to dispense with personal attendance..."            -> section 116 exists
block 920461  "7, 8112. Order to be made. When a Magistrate acting under..."   -> section 112 MISSING
block 920467  "1, 2115. Copy of order under section 112 to accompany..."       -> section 115 MISSING
```

Measured corpus-wide the shape appears in **5 blocks in 2 documents** -- the
four CrPC openers above and one table row of figures in document 4473
(`10, 20, 40. 60, 80, 100. ...`), which is exactly the false positive the rule
must guard against. So: worth fixing, because it is cheap and it costs the Code
four sections; not worth planning around. Re-derive with
`tools/audit/fused-marker-lever.sql`.

The Code's fifth gap, section 417, is a different defect: block 921673 reads
`6[4l7. Appeal in case of acquittal.__` -- the digit 1 came out as a lowercase
L, the same misread as document 4387's `l9K` and document 3721's `l[25A`.

## Released law: a check the release gate does not make

Cataloguing withheld documents 3078, 3184, 3277 and 3330 turned up provisions that carry
another section's number or heading, because a printed contents that disagrees with the
body was matched to it by position. The release gate cannot see that shape: it checks
contents gaps and S7 collisions, and a mis-headed provision is neither. So the question
was whether it reached released law. It did, on a small scale, and two new audits find it.

**`tools/audit/label-disagrees-with-first-block.sql`** -- released sections whose own first
block opens with a different number and never prints their label. After removing the
confirmed noise (mid-block openers, a footnote marker fused in front of the right number,
zero-padded roster serials): **29 sections in 15 released instruments.**

**`tools/audit/released-phantom-sections.sql`** -- released sections that share their first
block with another released section although the block does not print their label:
**75 sections in 40 released instruments.** Many are first_block pointers at a shared
footnote block (the CPC's sections 37, 40, 43, 51, 53, 73, 97, 102, 126, 143 all point at
block 828092, `1S. 25 was amended by Adaptation Order, 1937...`) rather than wrong text.

Two cases read by hand:

- **Sindh Livestock Breeding Act -- confirmed defect in released law.** A root-level
  provision labelled `16` and headed `Monitoring of genetic merit.` sits between sections
  1 and 2 (path `sindh.act.y2017_XVI_o3678.s_16`). Its first block is 145612 -- section 1's
  own block, `1. (1) This Act may be called the Sindh Livestock Breeding Act, 2016. (2) It
  extends to the whole of Sindh. (3) It shall come into force at...` -- and it holds two
  children labelled 2 and 3 that are section 1's sub-sections. The real section 16 is
  separately in the tree under Chapter IV (`...ch_IV.s_16`, block 145671). A citation to
  "section 16(2)" would render "It extends to the whole of Sindh."
- **Elections Act, 2017, sections 130 and 131 -- not a tree defect.** Page 71 prints two
  sections numbered 130: block 714315 `1[130. Vacancy in electoral college not to
  invalidate election.—` (substituted by Act XLIV of 2023) and block 714316 `130. Drawing
  of lots.—`. The tree labels the second 131, which is what the Act's own contents prints
  (`131 Drawing of lots`). The consolidation misprints; the record is right. Worth a note
  on the provision, not a change.

So both listings need a reader, row by row, before anything is changed -- but they are the
first evidence that "released" and "correct" are not yet the same set, and both belong in
the release criteria once the rows are read.

## Released law was serving the wrong text for "section 2" -- 26 decisions superseded, and a queue of 171

**What was wrong.** `accept_non_citable` retypes the demoted "section" as a clause under the same
parent and leaves the kept unit holding the section number. Earlier bulk decisions verified that the
printed LABEL stayed reachable ("this demotion removes a duplicate rather than a citation ... 0 of
which leave their label uncitable") -- true, and not the question. In many released Acts the kept unit
was a fragment of section 1 and the demoted unit was the real section. A citation rendered from the
record (INV-1) named the right number and quoted the wrong provision.

**The commencement shape, read and superseded on 17 Sep.** Pakistan Code and KP Code PDFs print section
1's extent and commencement either as `(2) It extends to...` / `(3) It shall come into force...` or,
in several federal Acts, with bare numbers `2. It extends to the whole of Pakistan.` / `3. It shall come
into force at once.` The segmenter made those sentences sections 2 and 3, and the collision was decided
the wrong way round. I rendered and read the page for every one of the 28 accepted collisions whose kept
section 2 or 3 is such a sentence: 26 were inversions, recorded with `./nz s7-source` as
`source_verified` decisions that supersede the old ones (25 `restore_citable`, 1 `reparent` -- the IGCT
Act's `2. The Cabinet Committee may:` is section 4(2)); 2 were correct and left alone (a Balochistan
Mines amendment whose demoted unit is an addressee, and a footnote). Readings:
`.artifacts/s7-source/readings-released-commencement-inversions.json`; renders beside it.
Among them: the **Pakistan Nuclear Regulatory Authority Ordinance, 2001** (sections 2 and 3), the
**Torture and Custodial Death (Prevention and Punishment) Act, 2022** (sections 2 and 3), the
**Inter-Governmental Commercial Transactions Act, 2022**, the **Iqbal Academy Ordinance, 1962**, the
**West Pakistan Departmental Inquiries (Powers) Act, 1958** (section 2 is its operative power to summon
witnesses), the **KP Pre-emption Act, 1987** and the **West Pakistan Motor Vehicles Taxation Act, 1958**.
**Released instruments: 4,214 before, 4,192 after the commencement shape, 4,094 after the whole queue.**
Those 120 are withheld until their trees are rebuilt, which is the honest state: they were answering a
section number with the wrong text.

**The segmenter rule this needs:** a sentence opening `It extends`, `It shall extend`, `It shall come
into force` or `It applies` immediately after section 1's opener -- numbered `(2)`, `2.` or `2[(2)` --
is a sub-section of section 1, never section 2.

**The wider queue.** `tools/audit/released-accepts-that-fail-the-stub-guard.sql` lists released accepts
that today's non-overridable stub guard would refuse (demoted 500+ characters, kept under half):
**171 decisions in 111 released instruments** (after the 26 above were superseded). **All 171 have now
been read, page by page, from renders made for the purpose** (`.artifacts/s7-source/sg/`), and recorded:
**152 superseded** -- 81 restore_citable, 47 reject_candidate, 23 reparent, 1 split_instrument -- and **20 confirmed correct as recorded** (a footnote or an endorsement list
demoted with nothing operative beneath it), listed with their reasons in
`.artifacts/s7-source/stubguard-left-as-recorded.json`. The readings are in
`.artifacts/s7-source/readings-stubguard.json`; the queue as measured is
`.artifacts/s7-source/released-accepts-failing-stub-guard.psv`.

What they turned out to be, in the order they cost the corpus most:
- a **footnote** holding the section number while the real section sits demoted beneath it -- the
  **Prevention of Corruption Act, 1947**, whose section 5 `Criminal misconduct.⸺ (1) A public servant
  is said to...` (4,272 characters) was demoted under `The Act has been applied to whole of the
  Province of West Pa...`; the **Cotton Cess Act**, **Land Improvement Loans Act**, **Securities Act**,
  **Tolls (Army and Air Force) Act**, **Transfer of Property Act**, **Vaccination Act**, the **KP Sarhad
  Development Authority Act** (sections 3, 5, 6 and 7) and more;
- a **membership-table row** holding it -- the **Sindh Protection and Promotion of Breast-Feeding and
  Young Child Nutrition Act, 2023**, where sections 4, 5, 6, 8, 12, 13, 14, 15, 16, 17, 19, 20 and 22 --
  the Act's whole operative body, including its penalties -- sat demoted under rows of the Board's
  membership list, and the same shape in the 2013 Sindh Act, the **KP Hydel Development Fund Ordinance**,
  the **Pakistan Broadcasting Corporation Act** and the **NICVD Act**;
- a **footnote node that had swallowed the following page's law** -- definitions of the **Explosives
  Act**, the **Electoral Rolls Act**, the **West Pakistan Money-Lenders Ordinance**, the **Mehran** and
  **Sind Agriculture** University Acts, the **KP Text Book Board Ordinance** -- 30 decisions of this kind,
  recorded as `reject_candidate` with a note of where the swallowed text must go;
- an **OCR or opener misread of the number itself**: `11.`, `13.`, `23.`, `26.`, `31.`, `81.`, `243.`,
  `310.` read as `1`, `3`, `6`, `10`, `43` -- so a real section was demoted against a different one;
- a **schedule or rate table row** demoted where it should have been nested under its table --
  the **Punjab Control of Narcotic Substances Act 2025** punishment table, the **Sales Tax Act 1990**
  offences table, the **KP Finance Act 1990** tax table, the **Punjab Private Housing Schemes Rules**
  planning standards.

Related audits written the same day, each asserting a rule and reporting a number:
`accepted-demotions-with-operative-text.sql`, `accepted-demotions-hiding-unique-law.sql`,
`released-section-inversions.sql`, `commencement-subsections-numbered-as-sections.sql`,
`released-phantom-sections.sql`, `label-disagrees-with-first-block.sql`.

## Two parser rules landed, 18 Sep 2026, and what each is worth

Both were found by reading source, both are narrow, and both were measured
against the corpus with `tools/diff_segment_trees.py` before being kept. Neither
has reached the database: they change the segmenter, so they take effect on
replay.

**1. Section 1's extent and commencement sub-parts (`_SECTION_ONE_SUBPART`).**
The Pakistan Code and the KP Code print them with bare numbers, flush with the
body, so they collide with the real sections 2 and 3 -- the collision behind the
26 released instruments that were answering "section 2" with the extent sentence
(above). An earlier repair existed but required five typographic signals
including indentation, which this shape does not have. The new condition asks
instead for evidence that does not depend on typography: the sentence must be
closed and complete, the owner must be the section that names the instrument,
the number must continue section 1's own sub-part sequence, and the instrument
must independently print a different section under that number -- promised by
the contents, or printed again below. A second guard, `_SUBPART_FOREIGN_DUTY`,
refuses the demotion once some actor other than the instrument acquires a duty
in the same sentence: that is the stub guard's rule in the parser, never demote
a unit that carries law of its own. Tests: `tests/test_section_one_subparts.py`.

**2. The explanatory-note guard must read a heading, not the word "note"**
(`subdivide`). The guard refuses to cut where the text before the cut ends in
`Note.`, for `Note. 1. ...` explanatory notes. Written unanchored, it also
matched any sentence merely ENDING in the word "note". The Contract Act 1872
prints an illustration to section 132 ending "...is no answer to a suit by C
against A upon the note.", and section 133 follows it in the same block:
**the whole of section 133 was being swallowed into section 132.** Anchoring
"Note." to the head of its own line recovers it -- document 4337 goes from 196
sections and 576 provisions to 197 and 579, and its last unsatisfied contents
entry closes (`old_missing` 1 -> `new_missing` 0). The Punjab Prisons Rules'
genuine `Note. 1. ...` cases still suppress the cut. Tests:
`tests/test_note_guard.py`.

**3. Footnote provenance written out in words (`_FOOTNOTE`).** The vocabulary
recognised `The words ... rep. by ...` but not the same editorial frame written
out -- `The word "Local" omitted by the Punjab Act IV of 1944, s.10.` A footnote
run needs two recognised provenance lines to be read as apparatus, and these
runs scored one, so their markers were handed to the grammar as section numbers.
**642 blocks in 134 documents carry that note shape, and 110 blocks in 53
documents are currently attached as SECTIONS** -- footnote text standing as
citable law. The widening is held to the editorial frame and requires a named
instrument, and `_split_note_is_apparatus` still refuses any note carrying
unquoted operative modality, which is what an enacted "shall be omitted" has.

Measured over those 53 documents with `tools/diff_segment_trees.py`: **8 change,
losing 23 phantom sections and 12 S7 collisions.** Five (depth, label) pairs
disappear, and every one was read against source first:

| document | label | what the lost node actually was |
|---|---|---|
| 4434 Constitution | 5 | "It was inserted by the Legal Framework Order, 2002 (CEO No. 24 of 2002), published the Gazette of Pakistan (Extraordinary)..." |
| 4434 Constitution | 7 | "It was earlier inserted by the Constitution (Eighteenth Amendment) Act, 2010 ... Omitted by the Constitution (Nineteenth Amendment) Act, 2010" |
| 4490 Code of Civil Procedure | 13 | "The word in crotches was earlier substituted for the word 'Federal' by the Central Laws Adaption Order, 1961..." |
| 4490 Code of Civil Procedure | 19 | "It was earlier substituted Inserted by the Code of Civil Procedure (Amendment) Ordinance, 1970..." |
| 2366 West Pakistan Land Preservation Act | 5 | the whole block is `5. The word "Local" Omitted by Act No Iv of 1944. s . 8.` -- a phantom that had SWALLOWED the operative text following it |

The real Articles 5 and 7 of the Constitution survive at page 4 -- "Loyalty to
State and obedience to Constitution and law" and "Definition of the State" --
and the Code's real 13 and 19 survive. Document 2366's contents agreement is
unchanged at 0.5000 either way while its S7 collisions fall from 13 to 7: the
law the phantom had swallowed returns to the section that was printing it, and
no contents entry goes unsatisfied. Nothing is dropped from the database in any
of the five: the blocks keep their roles and become apparatus attached to the
provision they annotate, instead of standing as sections of their own.

## `first_block` is a block pointer, not a character offset

`subdivide()` cuts one extracted block into several printed sections, and every
piece inherits the containing block's id. So a block's opening line names only
the FIRST of the sections that start inside it, and any audit that reads a
section's `first_block` text to judge that section is reading a different
section's words whenever the block was cut.

Measured 18 Sep 2026: **7,113 blocks are the `first_block` of more than one
active section, covering 17,573 sections; 2,811 blocks and 7,903 sections inside
the release.**

```sql
SELECT count(*), sum(sections) FROM (
  SELECT first_block, count(*) AS sections
    FROM provision WHERE kind='section' AND is_active AND first_block IS NOT NULL
   GROUP BY first_block HAVING count(*) > 1) t;
```

This is the single largest source of false positives in
`label-disagrees-with-first-block.sql` and `released-phantom-sections.sql` --
of 26 rows read and found correct as released, 12 were exactly this shape (Canal
and Drainage 40-43, Insolvency 61/74/82-84, Married Women's Property 5-7,
Railways 12-13). Neither audit can be trusted on count until `first_block`
carries an offset as well as an id. Both remain useful as review queues.

**A related correction to two figures quoted here earlier.** The two audits were
quoted at 29 sections / 15 instruments and 75 / 40. They re-derive today as
**26 / 13** and **52 / 27**, and the reason is NOT the join fan-out that inflated
the stranded-number count. Audit 1 has no self-join; audit 2 already counted
`DISTINCT provision_id`. The released set itself shrank -- 4,192 instruments
after the 17 Sep supersessions, 4,094 by the time the rows were read, with 70 of
the 122 phantom rows moving into withheld instruments. Over all active
provisions the same rules return 37 / 22 and 122 / 60. The earlier figures were
right when written and stale when re-read: a count over the release is a moving
measurement, and quoting one without its date says less than it appears to.

## The fused-marker strip firing on a real digit

The inverse of pattern (e). The opener strips a leading digit as a footnote
marker, so a longer number's tail becomes the section label: `437.` reads as
section 37, `1499.` as 99, `1974.` as 74, `19.` as 9, `48.` as 8.

**58 released sections across 45 released instruments** carry their own text
preceded, inside their own block, by a longer number ending in their label. Two
sub-shapes, and only one of them is harmless:

- the longer number is a citation tail -- a Gazette page, an Act number, a date
  -- and the section then holds footnote text;
- the longer number is the real section number, and the section holds **another
  section's text while the donor section vanishes from the corpus.**

The second kind loses law, and two cases are confirmed against source:

| instrument | printed | in the corpus |
|---|---|---|
| Sale of Goods Act (document 3617) | s.48 "Part delivery.-- Where an unpaid seller has made part delivery..." | no section 48 exists; its text is a SECOND section 8 |
| KP New Irrigation Projects (Planned Development) Act 1953 (document 1847) | ss.12, 17, 18, 19 | absent; labels run 1-8, 10, 11, 13-16, 9, 20-35, and s.19's text is citable only as "section 9" |

Both are in the release. A citation to Sale of Goods s.48 resolves to nothing
today, and the law it names is in the database under a number that is not its
own -- the exact failure INV-4 exists to prevent.

The sting is that the audits' own noise filter, `printed NOT LIKE ('%' ||
label)`, makes the same assumption the segmenter does. That is right at a block
opening -- Canal and Drainage's `540.` really is marker 5 on section 40 -- and
wrong mid-block, where the longer number is often the real one. The filter is
anchored to the block opening, so it silently both over- and under-fires.

## Replay readiness, measured 18 Sep 2026 -- and the one document that blocks it

The parser is ahead of the corpus. The uncommitted segmenter work plus the three
rules landed today fix defects that are still present in the database, because
no replay has been run: document 3617's Sale of Goods section 48 exists in the
new tree and not in the corpus, and document 1847 recovers sections 12, 17 and
18 the same way. Every dry run quoted here measures a fix that exists but has
not landed.

**Is the parser itself safe?** `tools/diff_segment_trees.py` over 86 documents,
HEAD against the working tree: **0 sections lost, 5 gained** (document 3228
gains `6.A`; document 4407 gains 10, 27, 37 and 74). The parser changes bury
nothing.

**What would a replay do?** A dry run over a 399-document random sample
(`--redo --dry-run`, 407 document-instruments):

| | |
|---|---|
| sections | 9,279 -> 9,373 (**+94**) |
| S7 candidates | 328 -> 291 (**-37**) |
| documents | 26 gain, 34 lose, 347 unchanged |
| contents agreement | mean 0.9659, median 1.0000, 82.9% at or above 0.99 |

Net positive -- the Code of Civil Procedure alone gains 76 sections -- but the
aggregate hides the thing that matters. Of the 34 documents that lose sections,
the disappearing labels were read: **21 hold no text at all, 44 hold furniture**
(tariff rows `Fiber-optic based`, application-form fields `Marital status :`,
appendix table cells `Lahore Rs.97 or less Rs.3`), and **8 carry operative
language**. Of those eight, document 1886's label 2 is `They shall come into
force at once.` -- the extent/commencement rule above, firing correctly.

**The blocker was document 2754**, the Provincial Ombudsman (Employees) Service
Rules: **20 sections became 0.** All 329 blocks still carried a role, so nothing
left the database, but the new tree typed every rule as a `clause` -- exactly
the kind `accept_non_citable` uses to make a unit non-citable. The instrument
would have kept its text and lost every citable unit it has, including `No
person shall be appointed by initial appointment to a post unless he is a
citizen of...`.

The cause was not today's work: HEAD produces 0 sections for it too, so this is
a regression already committed, which a replay would simply have landed. A
Sindh Gazette notification promulgates its rules as an annexure to itself --
`ANNEXURE A PART-I / PRELIMINARY / 1. (1) These rules may be called the
Provincial Ombudsman (Employees) Service Rules, 1997` -- and the annexure
heading opens auxiliary mode, where a numbered opener is a schedule row. Both
existing exits from that mode need evidence this document lacks: one requires a
contents entry (its contents parse returns 0), the other a `schedule` node
carrying a printed "Rule N" prefix.

**Fixed 18 Sep**: a schedule row never names the instrument, so the naming
formula at label 1 is proof that the auxiliary was the instrument's own body,
and the body resumes there. Confirmed by removing `ANNEXURE A` from the block by
hand, which restores exactly the same 20 sections. The annexure heading is kept
in the tree -- nothing is deleted to buy the repair. Tests:
`tests/test_annexure_instrument_body.py`, including the negative control that an
annexure WITHOUT the naming formula keeps its rows as schedule rows.

Re-running the 34 losers afterwards: **2754 is 20 -> 20**, and four documents
gain besides -- document 1463's S7 candidates fall from 10 to 0, document 2366's
from 49 to 7, documents 2188 and 2930 from 1 to 0.

Three more to read against source before a replay: document 2362 label 56
(`Pension-- The service as Chairman or Member shall not qualify for pension`),
document 2366 label 13 (`It shall be lawful for the Deputy Commissioner...`),
and document 4088 labels 3 and 4 -- though 4088 simultaneously GAINS 13 to 19,
so that one is very likely a renumbering of mislabelled duplicates rather than
a loss.

So: the replay is a net gain and is safe for 4,690 instruments minus a named
handful. It should not be run until 2754 is fixed and those three are read.
Running it on the aggregate alone would strip an entire instrument of citable
law while reporting +94 sections.

**The three flagged for source reading are cleared (18 Sep).** Each disappearing
label was traced to where its TEXT goes in the new tree, which is the question
that matters -- a label moving is not a loss, a text becoming uncitable is:

- document 4088: the stored tree held several sections labelled `3` and `4`; the
  new tree gives them their printed numbers -- 13 `Retirement from service.]`,
  14 `Employment after retirement.`, 19 `Pension and gratuity.]`, 23 `Saving.`
  -- and satisfies every contents entry (`missing: []`). A repair, not a loss.
- document 2362: `Pension-- The service as Chairman or Member shall not qualify
  for pension` stays citable, as section 6. The stored label `56` was never
  plausible in an instrument of ten sections.
- document 2366: `It shall be lawful for the Deputy Commissioner...` stays
  citable as section 3. Twelve of its 24 contents entries go unsatisfied -- but
  its contents agreement measures 0.5000 both with and without the change, so
  the document is equally broken either way, while its S7 candidates fall from
  49 to 7.

So no disappearing label in the sampled 34 takes law out of reach. The replay's
remaining risk is numbering quality in already-broken documents, not loss.

## Audit state, 18 Sep 2026: 26 of 30 criteria pass, and why four are red

`tools/audit/criteria.sql` reports **A1-A9 pass, C1 and C5-C8 pass, Q1-Q3 pass,
S1-S6 and S8-S10 pass**, with four failing:

| criterion | value | what it is |
|---|---|---|
| C2 every blob is read | 4 | in flight |
| C3 no document silently unsegmented | 5 | in flight |
| C4 EVERY text block accounted for | 3,392 | in flight |
| S7 repeated-label demotions adjudicated | 1,103 pending in 312 observations | the real queue |

**C2, C3 and C4 are not a regression.** They are the nine Sindh documents landed
today, observations 9574-9582, recovered from the portal's Gazette store
(`TypeCode=Gazette`) which the catalogue never used -- four documents that were
declared permanently unavailable and five alternate official copies of documents
already held. A blob that has landed but has not yet been extracted is by
definition "unread" (C2); its observation has no segmentation run (C3); and once
extracted its blocks belong to no provision until it is segmented (C4). All
three return to zero when the landing finishes. The criteria are working
correctly: they are fail-closed and they are telling the truth about a pipeline
mid-run.

This is worth writing down because the temptation on seeing three green criteria
turn red is to assume the last change broke them. The check that settles it is
cheap: `source_observation` ids 9574-9582 are contiguous, dated today, and every
`canonical_url` is a `sindhlaws.gov.pk` PUB id from the recovery list.

S7 is the standing red, and the only one of the four that represents work rather
than motion.

## A noise filter that hid 163 released sections from review

Both released-law audits carried the same one-line excuse:

```sql
AND printed NOT LIKE ('%' || label)
```

where `printed` is the number at the BLOCK OPENING. The theory was a footnote
marker fused in front of the number -- `1273.` for section 273 -- and that shape
is real. The line was wrong anyway, in two directions at once.

It is **anchored at the block opening but applied to every section**, including
the many that open mid-block. 7,113 blocks are the `first_block` of more than one
active section, so the excuse routinely described a different section from the
row being judged: the Canal and Drainage Act's sections 40, 41 and 42 print
`540. 541. 542.` mid-block while the block opens at `36.`, so the excuse never
fired and they were flagged as defects. And **where it did fire it assumed the
longer number was marker+label**, when often the longer number is the real one
and the LABEL is the truncation -- `19.` read as section 9, `48.` as section 8,
`233.` as rule 3. It therefore excused exactly the rows where one section has
silently taken another's text, which are the rows that matter.

The correction takes the opener belonging to THIS section -- located by finding
the section's own text inside its block -- and excuses only when **both** tests
pass: the label continues the instrument's numbering, and the label is unique in
the instrument. Both are needed. A run of truncations defeats the first alone:
the Hyderabad Development Authority Act has four consecutive phantoms 5, 6, 7, 8
standing for 45, 46, 47, 48, so each "continues" its equally-wrong neighbour.
Uniqueness catches them, because a truncated label always collides with the real
section of that number while a genuine fused marker does not.

**Measured over the release, 63,225 sections, 18 Sep 2026** (the join takes
1h13m, which is why it is a separate file and not inlined):

| | sections |
|---|---|
| excused by the OLD filter | 163 |
| excused by the CORRECTED filter | 27 |
| newly excused | 27 |
| newly flagged | 163 |

**The two sets are completely disjoint.** Every row the old excuse hid, the
corrected test flags; every row the corrected test excuses, the old one was
flagging. Removing the broken line takes
`label-disagrees-with-first-block.sql` from 26 sections in 13 instruments to
**207 in 84** -- not a regression, a queue that was being suppressed.

The corrected test lives in `.artifacts/corrected-fused-marker-filter.sql`. The
general lesson is the one worth carrying: a filter whose job is to remove noise
can hide the signal, and it will do so silently, because nobody re-reads the
rows a filter excused. This one was verified by hand on eleven rows before being
trusted, and then measured over the whole release before being adopted.

## An image-only scan whose OCR mangles every rule number: document 4594

The Sindh Prisons and Corrections Services Rules 2019 is a scan with no text
layer, and its OCR reads rule numbers unreliably in a specific way: it truncates
them. `39` arrives as `3`, `233` as `3`, `303` as `3`. Every truncated number
then collides with a real early rule, and the collision is resolved by demoting
the later one -- so twenty-two real rules from pages 13 to 48 were accepted as
non-citable clauses, thirteen of them beneath rule 11's *"Duties and Functions of
the Committee"*, a unit of 153 characters.

The rules recovered, each under the number its page actually prints: 39 Provision
of funds · 63 Duty hours of Officer in charge · 68 Checking and counting
prisoners twice daily · 69 All business on prison premises · 77 Reports and
Statistics · 103 Deputy Superintendent to accompany officers · 133 Search of
Women Prisoners · 140 Women prisoners in advanced pregnancy · 153 Examination on
admission and release · 182 Convalescent and infirm parties · 194 Intimation of
serious illness · 202 Sanitary matters · 203 Origin of the first case · 210
Sudden or violent death or suicide · 223 Duty of sentry · 233 Gate sentry to
defend gate · 243 Recapture of a prisoner · 253 Punishment only by the Officer
In-charge · 273 Officers not to leave place of duty · 279 Prohibition against
sleeping on duty · 289 Permanent vacancy · 303 Seniority list.

Twenty are `reparent` rather than `restore_citable`, because restoring them under
the OCR's label would collide with a different real rule; two (140, 182) already
carried the right label, so there the KEPT unit was the impostor. Several rules
corroborate their own numbering internally -- rule 243 cites "rule 237", rule 305
cites "rule 297" -- which is the cheapest available proof when the printed digits
cannot be trusted.

The document now has zero accepts outstanding. It is the clearest demonstration
in the corpus that an OCR quality score says nothing about whether the STRUCTURE
survived: the characters were legible enough to pass, and the numbering was
destroyed.

## The cohort grows faster than it is cleared, and that is not failure

Measured across one reader's pass: instruments in the supersession cohort went
162 -> 171 while accepts standing went 700 -> 680 and accepts burying operative
text went 190 -> 174. The reader cleared 20 and the cohort gained 9 instruments
from other readers' supersessions in the same window.

This is structural, not drift. Superseding one wrong decision withholds that
instrument, and withholding it brings every remaining accept inside it into the
queue. So the visible total rises while real errors fall. Any report of progress
here has to quote both numbers or it misleads: today the buried-character total
went 264,861 -> 130,706, a little over half, while the instrument count climbed.

The operational consequence is the one worth keeping: **re-derive the queue at
the start and end of every pass.** Two readers working from a list built twenty
minutes earlier wrote decisions on the same two candidates; re-deriving caught
it, and the conclusions happened to agree, which will not always be true.

## Open for a boundary reader: document 3696 binds two regulation sets

Found while superseding an accept in the buried-law queue, and NOT settled by that
decision. Document 3696 appears to hold two separate sets of regulations in one
file, and the S7 collision on label 5 is a symptom rather than the defect.

- Page 14, block 448246: `CONFIRMATION / 5. Confirmation:- Confirmation of an
  employee shall be made in the order of seniority in a permanent post on of which
  no other employee holds any lien. / 6. Termination of lien:- ... / 7.` -- service
  regulations.
- Page 18, block 448256: the gazette running header `313 THE SINDH GOVT. GAZETTE
  EXT, SEPTEMBER 22, 1998 PART-I` and then `4. (1) There shall be a fund known as
  the Employee's Fund Pension Fund. (2) The Fund shall be utilized for grant of
  Pension; and gratuity under these regulations. / 5. Application or Pension Fund:
  (1) The Pension fund shall be administered by a Committee consisting of the
  following:-` -- Pension Fund regulations, numbering restarted.

Regulation 5 of the pension set was demoted behind regulation 5 of the service set.
I recorded `restore_citable` so the pension regulation is citable, which is the
minimum that preserves the law -- but if the two sets are separate instruments the
correct fix is `split_instrument` at the page-18 boundary, and then neither unit
needs to yield its number. One page cannot establish that: it needs the second
set's own enacting notification, which is not on page 18. Whoever takes
multi-instrument boundaries should read this document rather than trusting the
restore.

## Measured: a stop INSIDE a compound label

The 4234 case -- `59.F Establishment of sinking fund.` read as if the stop ended
the number, so section 59F was demoted behind the genuine section 59 -- is a
distinct shape from the fused-marker family in (t) and (l). There the marker sits
in FRONT of the label; here the stop sits INSIDE it.

Measured corpus-wide: **46 blocks in 26 documents** open with `NN.X`; **35 opened a
provision** and in **28 of those the parser kept only the bare number**. The
remaining 7 kept the compound label correctly -- documents 4235 (`51.O. Whistle-
blower disclosure`, `51.P`, `51.Q`) and 4495 (`282.D. Power to issue directions`) --
so this is an inconsistency in the opener, not a missing capability.

The 28 is an upper bound, and a rule written on the shape alone would be wrong.
Inspecting them: only about eight are section-level compound labels that continue
into a heading and operative text (4234 `59.F`, 3979 `72.B`, 4244 `19.A` and
`22.A`, 4369 `126.A`, 4400 `3.A`, 4498 `8.A`). The rest are abbreviations read as
labels (4137 `2.M.S.PESSI`, `3.S.M.O.(HQ.)`), schedule rows (3929 `2.A 4Computer
Programmer`, `6.B 7Proof Reader`) and scan noise (4450 `13.U V 11\13`). So the
guard must require a heading or operative text after the compound label, exactly as
the bare-number lever does.

Re-derive: blocks matching `^\s*\d{1,4}\.[A-Z]{1,2}[\s.]` in `text_block`, joined
to `provision.first_block`, comparing `provision.label` with the captured number.

## The 207-row queue, classified: 87 defects and 115 fused markers

Removing the broken excuse surfaced 207 sections in 84 released instruments, but
the listing mixed two populations and a reader had to separate them by eye. One
rule, verified against eleven rows read from the rendered page across six
documents, agrees with all eleven:

- the label is used TWICE in the instrument, **or** another released section
  already carries the PRINTED number → **defect**: the label is a truncation and
  this section has borrowed another's number (6 of 6 source-read);
- the label is unique, no section carries the printed number, and the printed
  token ends with the label → **a footnote marker fused in front**, correct as
  released (5 of 5 source-read).

Measured over the whole listing:

| classification | sections | instruments |
|---|---|---|
| defect: label is a truncation | **87** | 49 |
| correct: fused marker | 115 | 45 |
| read it | 2 | 2 |

So the old one-line excuse was built for a real shape -- document 2605 prints a
superscript 1 flattened onto `4.` with footnote *"This section has been amended
in its application to the Punjab by the Punjab Act No. I of 1938, s. 2"*, and
document 2362 runs a whole column of them, markers 2 through 8 down one page.
The shape was real; the test was wrong. **115 of the rows are that shape, and 87
are released sections whose citation resolves to another section's text.**

Document 3386 is the case that proves the uniqueness half is required. Page 18
prints sections 45 *Review*, 46, 47 *Dropping of proceedings*, 48 *Civil Court's
powers*; the tree holds them as `ch_IV.s_5`, `s_7`, `s_8`, and the instrument
ALREADY holds real sections 5, 7 and 8 in Chapter II on page 6, whose headings
the Chapter IV nodes have borrowed. A sequence test alone passes them, because
each continues its equally-wrong neighbour.

**The listing is a floor.** `printed` is read from the first block's opening, so
a section whose `first_block` points at its marginal note yields NULL and never
enters the listing. 3386's section 46 is missing for exactly that reason -- block
365984 opens `Dropping of proceedings.` -- while 45, 47 and 48 appear.

One triage column that did NOT work, recorded so it is not reused: whether a
footnote marker appears on the same page does not predict the fused-marker class.
Document 2362's markers 2 and 3 are real superscripts whose footnotes sit on a
later page, so the column reads 0 while the page reads *correct*. Label
uniqueness is the test that held.

## Acquisition closed: nine recovered, and a second document store nobody had used

The 21 unresolved Sindh exceptions all returned HTTP 404 on their catalogued
URLs, re-fetched and confirmed on 18 Sep 2026 -- 1,245 bytes of the portal's own
error page, not a PDF. Nine were recovered anyway, because
`sindhlaws.gov.pk/Search.aspx/LoadRegion` accepts `TypeCode=Gazette` as well as
`SindhCode`, and **the Gazette store is a second document store the catalogue
never queried.** Four of the nine recoveries came from it.

Landed through the project's own path
(`nizam.workers.recover_acquisition --alternate-for <obs> --url <candidate>`),
which hashes the body, checks `%PDF` magic bytes and the page tree, and inserts a
NEW landed observation carrying `source_metadata.alternate_of`. The nine original
observations were verified afterwards as untouched -- still `outcome=failed`,
`http_status=404`, sha256 and object_key NULL. Both facts are true and both are
kept: the catalogued URL is dead, and an alternate official copy exists.

**Four were genuinely new content**, none having had an observation, blob or
document before: the Provincial Motor Vehicles (Amendment) Acts of 2021 and 2020,
the Women Agricultural Workers' Act 2019, and the Physiotherapy Council Act 2022.
The last two have no text layer and went through OCR at 300 dpi -- confidence
0.930 and 0.892, **0 pages below the 0.70 review threshold**, so no declared
exception was needed. That is what moved Q1 from 107/109 to 109/109.

**Five were already held under other catalogue rows, and were confirmed by BYTE
IDENTITY rather than by title** -- the bytes fetched today hash to the same
SHA-256 as the existing document. This mattered concretely: the portal's row
label for the ISRA University Act 1997 says "ORDINANCE", and the document's own
page 1 says "THE ISRA UNIVERSITY ACT, 1997 SINDH ACT NO. V OF 1997". Identity
rested on the digest and the printed page, never on the portal's label.

**Final ledger over all 40 exceptions: 15 resolved_same_portal, 8
resolved_with_declared_normalisation, 15 confirmed_unavailable, 2
needs_second_look.**

Why the remaining Sindh exceptions cannot be recovered there, evidenced rather
than assumed: the Gazette store publishes Acts, Ordinances and Bills. A
Gazette-mode search for `RULES` returns two rows -- a corrigendum and a
partial-modification notification -- and `SERVICE RULES` returns none, so the
eight subordinate-rules exceptions cannot be found there by construction. For the
BISE Ordinance 1972 the store holds fourteen amending instruments and not the
principal.

**A gap worth naming on its own.** The sweep turned up a 99-page
`WEST PAKISTAN MOTOR VESICLES ORDINANCE 1965` (the portal's typo), No. XIX of
18 June 1965. The corpus holds **no copy of that principal Ordinance**, although
Sindh Acts amended it as recently as 2026. Whether it resolves exception 26 is
unsettled -- the catalogued row reads "AMENDMENT 1965" with no instrument number
-- but a corpus that holds the amendments and not the Act they amend is a defect
independent of how that exception is finally classified.

## Fourteen mine-safety regulations are not citable, in released instruments

The truncation shape at its worst. **COAL MINES REGULATIONS, 1926** (document
4330, released) holds **nine provisions labelled `1`**, at ordinals spread from
page 5 to page 33. Only the first is regulation 1. The others are regulations
**11, 21, 31, 61, 71, 91, 101, 121** -- every regulation whose printed number
ENDS in 1. **Metalliferous Mines Regulations, 1926** (document 4122, released) is
the same defect in the same 1926 series: seven provisions labelled `1`, being
regulations 11, 21, 31, 51, 61, 71.

Confirmed from rendered pages 24 apart: page 6 prints regulations 4 to 13 in
sequence, and regulation 11 -- *"If the operations in respect of which notice is
given under regulation 10 or 10-A are not commenced within twelve months..."* --
is stored as `1`; page 30 prints regulations 90 to 101, and both regulation 91
(haulage signal handle placement) and regulation 101 (*"Explosives shall be
issued only to competent persons appointed in writing by the manager"*) are
stored as `1`.

So a citation to "regulation 1" of the Coal Mines Regulations is ambiguous
between nine provisions, and fourteen mine-safety rules -- ventilation,
explosives, riding in shafts, blasting -- cannot be cited under their own
numbers. Both instruments are in the release today.

## A10's root cause is block ROLE, not the splitter

All 80 apparatus-linked contents entries across the 20 instruments are one
defect: **the page's footnote run carries `role = body`**, so nothing downstream
treats it as apparatus and the splitter carves sections out of it.

| document | block | numbered lines | shape |
|---|---|---|---|
| 4242 | 638220 | 11 | the whole run in one block |
| 1710 | 110322 | 10 | one block |
| 1856 | 127923 | 8 | one block |
| 2534 | 212644 | 4 | one block |
| 1918 | 134880-134890 | 1 each | one block per footnote line |

Document 4242 is the clearest: block 638220 holds
`1. Substituted vide the Khyber Pakhtunkhwa Act No. IV of 2011. 2. Substituted
vide ... 3. Replaced vide the Khyber Pakhtunkhwa Ordinance No. XXVII of 2002.`
as a single `role=body` block, so the Ordinance's "sections" 1 to 8 ARE footnotes
1 to 8, wearing headings the contents matcher supplied. Section 9, the first real
section after the run, is intact with its own block.

The two extraction shapes explain a split that was previously unaccounted for:
where the run is one block, the sections carved from its middle have NO block;
where the extractor emitted one block per line, each keeps one. Same defect, one
fix -- classify the run `role = footnote` and re-segment.

**A10 counts entries, not repairs.** An instrument can be wholly corrupted while
contributing few entries: 4242 shows 10 entries and 2534 shows 16, but in both
every early section is a footnote. The 80 is the size of the gate's complaint;
the repair is 20 documents re-segmented.

## Provisions whose text no active block backs: a property, not a defect

Flagged first as an anomaly in the A10 work, then measured and withdrawn as one.
`provision_block` is block-granular, so any provision the segmenter carves from
the MIDDLE of a block has no row in it at all. Over the release: **49,526
provisions in 3,114 instruments hold text that no active block backs, 8.29
million characters, of which 8,061 are sections in 1,293 instruments.**

That is how the model represents mid-block splitting. What remains true and is
worth stating as a standing property: for those provisions `text_normalised`
cannot be re-derived from the active assignment set, so "which block did this
text come from" is unanswerable at provision granularity. It is a real INV-3
replay limit, general to the corpus, and it should be recorded as a property
rather than chased as a defect queue.

## The decisive measurement: 87.5% of the release is built by a stale segmenter

Traced while confirming A10's root cause, and it reframes most of the defect
hunting in this file.

A reader deduced that A10's footnote runs were being claimed as detached
headings, which suppressed their footnote role and let the splitter carve
sections out of them. It asked for the deduction to be confirmed by
instrumentation before anything was changed. Instrumented, the answer was that
**the current parser already marks those blocks `footnote`**. Document 4242's
block 638220 comes back `role = footnote` today, and the tree the current parser
builds has section 2 *Definitions* holding *"In this Ordinance, unless the
context otherwise requires..."* and section 6 *Removal from office* holding
*"A member shall not be removed from office except in..."* -- real law, correct
headings.

Checked across the five worst A10 documents, every one produces **zero**
apparatus-opening sections under the current parser:

| document | stored segmenter | block role now | apparatus sections now |
|---|---|---|---|
| 1710 | segment/5 | footnote | 0 |
| 1856 | segment/8 | contents | 0 |
| 2534 | segment/8 | footnote | 0 |
| 1918 | segment/5 | contents | 0 |
| 4242 | segment/5 | footnote | 0 |

And all sixteen A10 instruments sit on `segment/5` (12), `/8` (3) or `/23` (1).
**Not one is on a current revision.** So A10's 80 failures are not a parser
defect at all: they are a stale corpus. No code change clears them; a replay
does.

Corpus-wide the same query gives the number that matters:

| | released instruments |
|---|---|
| built by an old revision (5, 8, 12, 16, 23, 25, 26, 27, 29) | **3,487** |
| built by a current-ish revision | 497 |

This also explains the heading coverage spread measured alongside it --
`segment/23` 35.6%, `segment/12` 47.4%, `segment/8` 48.8%, `segment/5` 78.9%
against `segment/59` 84.1% -- and why several class-A dedup groups have a
heading-less tree released while a heading-bearing tree of the same bytes sits
linked as a duplicate.

**The replay is therefore the single highest-value action available**, and it is
now evidenced rather than assumed:

- the parser buries nothing: `diff_segment_trees` over 86 documents, HEAD against
  the working tree, gives 0 sections lost and 5 gained;
- a 399-document dry run gives +94 sections, -37 S7 candidates, contents
  agreement median 1.0000;
- all 34 documents that lose sections were read: 21 empty, 44 furniture, 8
  carrying operative language, and every one of those eight traced to where its
  text goes -- no law leaves reach;
- the one document that lost every citable unit, 2754, was a regression already
  committed at HEAD and is fixed, with tests;
- A10's 80 failures vanish under the current parser, as above.

## The buried-law audit was counting the opener, and two questions were conflated

Found by a reader correcting its own handover: it had claimed all of document
4460's burying rows were already source-verified, then queried the whole document
rather than the top of a shared listing and found three still flagged at 471-485
characters each. Checking what those three actually bury turned the correction
into something more useful.

For each of them the **only** block matching the stop-words is the node's own
opening block -- a food-colour specification row reading *"3. Water insoluble
matter, per cent by mass, Max. 0.2"*. Nothing sits behind it. They match because
the sheet's requirement line says *"shall conform"*.

So the consolidated audit was counting the opener block in its subtree sum, while
the earlier own-blocks audit excluded it. Any table row whose own text happens to
contain "shall" reports as burying law even when the node holds nothing else --
a systematic inflator on exactly the numbered-table documents where the opener
flag already fails (4460, 4447, 3247, 3525).

The fix is two columns, not one narrower rule, because the two questions are
genuinely different and the reader was right to refuse to choose between them
silently:

| | rows | characters |
|---|---|---|
| law addressed under a non-citable node (opener included) | 315 | 109,331 |
| law sitting BEHIND an opener that should never have been a unit | **116** | **35,591** |

Both matter. For document 4489's section 133 the opening block IS the buried law
-- the live *Reference to High Court* text as amended -- so excluding it would
hide the worst case in the corpus. For a specification sheet the opening block is
a table row and there is nothing behind it at all.

The reader also declined to record decisions for those three, on the reasoning
that a source-verified confirmation stays in the queue exactly as the existing
`accept_non_citable` does, so it would have been three rows of audit trail for no
signal. That is the right test for whether a decision is worth writing.

## The replay, run 18 Sep 2026: staleness eliminated, and what it was worth

Every active instrument is now segmented by a current revision. **1,575 stale
instruments went to 0**; 4,675 are current. Run in bounded batches -- 16, then
304, 909, 915, 920, 664 -- **0 failures in any batch**, contents agreement median
1.0000 throughout with 91-96% of documents at or above 0.99.

What it was worth, every queue re-derived afterwards:

| queue | before | after | cut |
|---|---|---|---|
| A10 contents entries resolving to apparatus | 80 | **1** | 99% |
| accepts burying operative law | 315 | **135** | 57% |
| ...characters behind the opener | 35,591 | **15,556** | 56% |
| label-truncation defects | 87 | **35** | 60% |
| provisions in the corpus | 507,351 | **556,125** | +48,774 |

**48,774 provisions were recovered** -- law that was in the database and not
reachable as a citable unit, now addressed under its own number.

Two counts went UP, and they are the honest half of the result:

| | before | after |
|---|---|---|
| S7 pending units | 1,161 | 1,785 |
| pending contents gaps | 935 | 1,682 |

Re-segmenting surfaces collisions and gaps the stale trees were hiding. This is
the same shape as removing the broken noise filter, which took one audit from 26
rows to 207: the corpus has not got worse, it has stopped concealing what it does
not know. Both numbers are now measured against a current parser for the first
time.

**The ordering lesson, which cost most of a day to learn.** Reading a defect
queue before replaying is close to wasted effort when the corpus is stale,
because the parser has already fixed an unknown fraction of what the queue
contains -- here, 57% to 99% depending on the queue. The replay costs compute and
almost no tokens; reading costs tokens and no compute. Replay first, re-derive
every queue, and only then spend reading on what survives.

## The replay discards S7 adjudication, and that fixes the order of work

Measured 19 Sep 2026, directly, after replaying 63 documents to land a contents
fix: **all 838 `accept_non_citable` decisions in those documents were orphaned**,
and 142 of their collisions came back pending. A replay retires each candidate
and creates a fresh one, so an accepted decision does not carry across.

The same measurement over all 430 pre-replay corrective decisions:

| | rows |
|---|---|
| candidate retired by the replay | 242 |
| ...of which the SAME collision came back | **118 (49%)** |
| genuinely resolved by the parser having changed | 124 |
| candidate untouched | 188 |

And migration `0036_release_identity_and_resolution.sql` states the gate's half of
it in its own comment: only accepting the parser's non-citable classification
resolves a candidate as written; restore, reparent, split and reject are
*instructions to build a corrected revision*, so they stay blocking until a
replay supersedes the candidate with a tree in which it no longer exists.

Put together, these two facts fix the order of all remaining work:

1. **land every parser fix**
2. **replay once**
3. **then adjudicate**

Any other order pays for itself twice. A replay before adjudication is nearly
free; a replay after it destroys the adjudication for every document it touches,
and returns about half the corrective findings unresolved. Reading a queue on a
stale corpus is worse still, because the parser has already fixed an unknown
fraction of what the queue contains -- measured today at 57% to 99% by queue.

This was learned the expensive way. Today's sequence was: read for a day, replay
(orphaning 339 readings), fix the parser, replay again (orphaning 838 accepts),
fix the parser again. The recovery each time was mechanical -- re-attach by
`(document_id, source_block_id)`, which is stable across re-segmentation where
`candidate_id` is not -- but the reading itself had to be redone wherever the
evidence no longer described the current candidate.

**The re-attachment tool is the thing to keep.** Matching orphaned readings on
document plus source block, taking the latest decision per block, and carrying
the observation forward with an explicit re-attachment note recovered 85 + 25 +
157 = 267 decisions across three rounds without a single page being re-read. It
should run as a mandatory post-replay step, alongside
`resolve_exact_instrument_duplicates.py`, which the replay also leaves undone --
the fresh-insert path never sets `duplicate_of`, so 63 duplicate groups with 130
live instruments accumulated silently and carried 324 queue rows.

## Shared contents anchors: a real defect, but not the one I briefed

I asked for a fix to "505 pending gaps across 137 documents" caused by several
contents entries sharing one `source_block_id`. Two things came back, and both
corrected me.

**The population is much larger and none of it is gaps.** Measured over all
4,596 documents: **16,006 stored entries share a block id, across 682 documents
and 2,168 blocks** (13,907 entries / 685 documents when re-derived from the parse
rather than the stored rows -- the stored count is higher because older parses
contributed). Pending gaps whose entry shares a block: 382, in 132 documents.
Not 505 / 137.

**And the mechanism I described does not exist.** `toc_node(entry)` resolves a
printed row against the body by citation label, heading support and source
order. `source_block_id` enters resolution in exactly one place --
`disposition_by_key`, keyed on `(block, label)`, which was already
collision-free. So a shared block never caused a gap and re-anchoring cannot
close one. Document 1918 is the proof: of the eight entries on block 134870,
**six resolve**; the two that fail, fail on body evidence. Its real defect is a
boundary error -- printed contents is page 1 alone while `body_starts_page` is 3,
so page 2's operative text becomes five phantom contents rows.

What the shared anchor did destroy is evidence and printed order:

| | before | after |
|---|---|---|
| entries sharing a full anchor `(block, offset)` | -- | **0** |
| `toc_matched` | 78,423 | 78,423 (0 down, 0 up) |
| citable sections | 103,903 | 103,903 (0 lost, 0 gained) |
| entries removed / added | -- | 0 / 0 |
| documents whose printed order changed | -- | **1** |

That one document is the Customs Act 1969. Block 813341 prints
`12 Power to appoint or licence public ware-houses` then `12A. Power to appoint
or licence common warehouses` then `13`, `14`. `12A.` carries a period so the
dotted reader found it, `12`/`13`/`14` are two-column rows, and the stable sort
put every dotted hit before every two-column hit in the block. The ledger
therefore recorded **12A at ordinal 30 and 12 at ordinal 31** -- asserting the
Act prints 12A before 12. `ordinal` is the printed position by definition
(migration 0011) and the order-bounded match recovery reads adjacency out of it.

So: worth having, and not a recovery lever. Migration 0051 adds
`source_char_offset` with a partial unique index; offsets are NULL until an
instrument is re-parsed and are deliberately not backfilled, because an invented
offset would be evidence the parser never produced.

## A timed-out client does not cancel its query

Found while the migration would not apply. `pg_stat_activity` showed **PID 75
active for 2,221 minutes** -- a read-only `SELECT count(DISTINCT r.id) ... FROM
v_release_provision JOIN text_block ...` started at 00:46 the previous day. It
was my own corrected fused-marker measurement: the psql client hit a local
timeout, I moved on, and the server kept executing for 37 hours.

Queued behind it: three `ALTER TABLE instrument_toc_entry` backends (the same
migration, attempted by three agents), a `COPY instrument_toc_entry` from a
re-segmentation, a `LOCK TABLE public.schema_migration ...` from a snapshot, two
reviewer SELECTs, and a replay. An autovacuum on `public.instrument` had been
stuck on `BufferPin` for 1,287 minutes. Cancelling PID 75 cleared the entire
chain in under a second.

It also left the schema ahead of the ledger, which doc 09a s7 does not permit:
three `migrate.sh` runs raced, one completed the file, the others died on
"column already exists", and none reached its `INSERT INTO schema_migration`.
The repair was to make 0051 idempotent -- `ADD COLUMN IF NOT EXISTS`, the CHECK
guarded by a `DO` block, `CREATE UNIQUE INDEX IF NOT EXISTS`, `DROP VIEW IF
EXISTS` -- and re-run it, so the file records itself whatever partial state it
meets. Recorded sha and file sha now agree.

**Check `pg_stat_activity` after abandoning any query.** A long analytic SELECT
that nobody is waiting for still holds its locks.

## The disposition model cannot express "the entry moved"

Found while trying to unblock the last three documents that will not re-segment.

A TOC disposition assertion records that a printed contents entry is omitted or
repealed, and carries the rendered page and its SHA-256 as evidence. It anchors
on `(source_observation_id, expression_ordinal, toc_entry_ordinal)` plus
`reviewed_toc_entry_id`, and `check_toc_disposition_assertion()` enforces that
the row identifies a LIVE entry exactly -- id, ordinal, label, heading, source
block and page.

The 19 Sep replay changed how many entries some contents lists yield, because
phantom footnote rows were withdrawn and merged blocks were split per entry. So
ordinals shifted beneath assertions that were correct when written. **Nine are
stranded**, each still true on its face -- document 3581's says entry 15, label
"16", is repealed, and label 16 now sits at ordinal 16 with its printed heading
still exactly `1[Repealed].`

The repair looked identical to the S7 re-attachment that recovered 267 readings:
the evidence describes a printed page, the page has not changed, only our pointer
broke. It is not available. **A superseding assertion must carry the same
`toc_entry_ordinal` as the row it supersedes**, so supersession expresses "the
same entry, judged again" and cannot express "the same judgement, the entry
moved". The ordinal is part of the entry's identity in this model.

That is not an oversight to patch around, and the trigger refusing it is right:
silently dropping a repeal assertion would let repealed text become citable
again, which is why `segment()` also refuses to materialise a tree while an
unmatched assertion is outstanding. Three documents (3581, 4441, 4608) are held
by exactly that refusal.

**The question it raises is a schema question.** An anchor that survives a replay
would be printed label plus printed heading plus source page -- the three things
the reviewer actually looked at, and the three this repair matched on
successfully. The alternatives are to let the supersession rule admit a moved
ordinal when those three agree, or to have the materialiser re-derive the ordinal
at match time rather than storing it. All three are decisions for the owner of
migration 0043.

A tenth assertion is stranded differently: id 179, document 4441, label 376B, on
an observation with no active canonical expression at all. That is a dedup
artefact rather than ordinal drift, and it fails the first check before the
second is reached.

**The general lesson, third instance today.** An identifier that our own pipeline
regenerates cannot anchor evidence across a regeneration. `candidate_id` broke
that way and `(document_id, source_block_id)` fixed it; `reviewed_toc_entry_id`
and `toc_entry_ordinal` break the same way and have no fix available. Anchor on
what the SOURCE supplies -- a block id, a page, a printed label -- never on a row
id or an ordinal we assign.

## An "absent" gap in an OCR'd document is not evidence of absence

Raised by a reader working the `absent` gap class, which was measured by asking
whether a promised label or heading appears anywhere outside the contents list.
The reader tested each gap against the RAW PDF text rather than our block table
-- the right instinct, since the block table is our interpretation and the PDF is
the evidence -- and then found that document 4556's pages have no text layer at
all. They are OCR'd. A `pdftotext` search over such a page returns nothing
whatever the page prints, so "not found in the PDF text" cannot distinguish a
section that is absent from one the OCR did not read.

Measured across the whole pending queue: **10 of the 441 documents carrying gaps
are OCR-derived, holding 35 of the 1,414 gaps -- 2.5%.**

So the caveat is real and bounded. It does not undermine the `absent` class; it
qualifies thirty-five rows inside it, which must be settled from the page image
rather than from extracted text. Worth stating because the opposite mistake is
easy and expensive: recording a document as lacking a section it actually prints
would be a false statement about the Act, and 35 such statements would be 35 too
many.

The general form, which applies to every text-search verdict in this project:
**a search that cannot distinguish "not present" from "not readable" must not
return "not present".** Where the text layer is absent the evidence is the
render, and the check has to say so rather than reporting a clean negative.

## 140 live mis-citations the gap queue cannot see

The most serious defect found in this corpus, and it is invisible to every gate
we have.

**The count is being refined as this is written and should not be quoted from
here.** It read 140 provisions in 59 documents, then 113 in 39, then 101 in 30,
on the same database within an hour. A reader judging S7 in parallel saw two of
those figures and reasonably concluded "something republished under us" -- it had
not. `tools/census_heading_mislabel.py` was being tightened between the runs, to
strip the ~10% false positives where a marginal note shares its block with
operative text. The corpus did not move; the instrument did. Run the census for
the current number, and note the lesson for any figure taken while its detector
is under construction: **a measurement is only stable once the thing measuring it
is.**

RESOLVED, 20 Sep 2026 -- root cause found, repaired, replayed, measured.
**101 mis-labelled provisions in 30 documents became 3 in 2 documents.
Sections lost: 0.**

The cause was not an offset to be shifted. `_split_heading` was handed a
contents entry, saw that the body did not open with that name, and correctly
returned NO heading. The entry linker (`segment.py:5456`) then pasted the
contents heading onto the headingless node anyway. One function declined the
bad name and the next one applied it regardless.

Document 4499, the Industrial Relations Act 2008, is the clean specimen and
its page settles the direction. The body prints `34. Workers participation in
management`, `35. Joint management board`. Its own contents page omits
"Workers participation in management" entirely, so from that point its printed
labels run one behind the body: it calls Joint Management Board section 34.
The tree took the contents' word for it. Anyone citing s.34 got the
participation-in-management text under the joint-management-board name.
**Where a document's index and its enacted text disagree, the text governs** --
the contents list is an index, not the law, and our own parse had preferred the
index.

The repair is two narrowings, neither of which invents a heading: `_split_heading`
falls through to the body's own first-sentence name (its first branch only, which
requires enacted text after the name, so a bare schedule row still gets nothing),
and the linker refuses a contents heading when the provision's own text names
another section.

**Two residuals remain and are a different defect**: doc 1683 Finance Act 1978
s.4 and doc 4139 r.15 are each a SCHEDULE ROW segmented as a section, then
dressed in the real section's name. Fixing the heading there would paint over a
structural mis-parse.

### How the count moved, and why that is a lesson about instruments

**6,682 -> 1,514 -> 140 -> 113 -> 102 -> 101.** Each round looked finished
until the next one found a false-positive class, and each class removed honest
drafting rather than concealing a defect: operative text read as a name
(`3. In this Act unless there be something repugnant...`); a preposition opener,
which is how every Sindh and Punjab Finance Act prints its amending sections,
with the real name in the margin (27 rows); editorial apparatus that is A10's
defect counted twice; and one name written two ways -- front-truncation,
initialism, singular/plural -- which prefix comparison cannot see.

Two readers measured this corpus mid-refinement and got 140/59 and 113/39 an
hour apart on an unchanged database. The reasonable conclusion -- "something
republished under us" -- was wrong. `tools/census_heading_mislabel.py` was being
tightened between the runs. **A measurement is only stable once the thing
measuring it is**, and a figure taken while its detector is under construction
should be quoted with that fact attached or not quoted at all.

### Why there is no A11 gate yet

The criterion is written (`tools/audit/heading-not-the-provisions-own.sql`) and
deliberately NOT adopted at threshold 0. Three reasons, and the third is the
decisive one: **expressed as plain SQL where `criteria.sql` computes its values,
it reports 472 rows in 221 documents -- 4.7x the true 101** -- concentrated in
the CrPC (44), Customs Act (14), PAF Act (13), Army Act (11), Constitution (11)
and PPC (11), every one of them the "one name two ways" class, which needs
per-token fuzzy matching and initialism detection that SQL cannot express. An
A11 printing 472 would be a worse artefact than no A11 at all.

Adopted instead in the REPORTED form A5 already uses, value carried by the
census tool; promotable to threshold 0 once every reported row has been read
against its page and the two schedule-row documents are repaired. A non-zero
threshold was considered and refused: it would have to mean "this many citations
may name the wrong provision", and no number of those is correct.

What the class looked like before the repair. **Provisions carried a heading that
was not theirs** -- the section's own printed opener names one thing and the tree's
heading names another -- and all 140 are reachable from a printed contents
entry, so all 140 are live.

Verified independently against the page. Document 4499, the Industrial Relations
Act 2008, page 30 prints:

```
37. Penalty for obstructing inspector. Whoever willfully obstructs an inspector...
38. Penalty for contravening section 34 or section 35, etc.__ (1) Whoever contra...
```

The tree gives section **37** the heading `PENALTY FOR CONTRAVENING SECTION 34 OR
SECTION 35, ETC` -- section 38's name -- and gives 38 `WORKS COUNCIL`. Every
heading in that Act is shifted by one. Document 3508 prints `7. Institute open to
all classes, creeds, etc.` and the tree calls section 7 "Teaching and examination
at the Institute". Document 3387 prints `5. Offence of hoarding.` and the tree
calls section 5 "Power to auction seized Scheduled articles".

**Why no gate sees it.** A5 asks whether a promised contents entry resolved; it
did. A10 asks whether it resolved to law rather than apparatus; it did. The
contents-gap queue records entries with no provision; these have one. A dense
contents list running at a constant offset finds a same-numbered provision for
*every* entry, so it produces **no gaps at all** -- only wrong names. Of the
eleven worst documents, five have no pending gap whatever.

`tools/census_heading_mislabel.py` re-derives it (`./nz mislabelled-headings`).

**Two corrections the reader made to its own figures, both worth more than the
original.** A loose test first gave 6,682 provisions "carrying a heading not
their own" -- it was counting every marginal note the block ledger failed to
attach, and the Co-operative Societies Act's section 4 legitimately carries
"The Registrar." A second pass gave 1,514, which included 62 Code of Criminal
Procedure sections that are one name spelt two ways: contents `Issues of
process` against body `Issus of process`; `Special Judicial Magistrates` against
`Special Judicial 2[* * *] Magistrate`. Separated properly: **689 spelling and
marker variants in 338 documents**, which is a fidelity issue, and **140
genuinely different names**, which is a mis-citation. A residual ~10% of the 140
are false positives where a marginal note shares its block with operative text.

## The contents region swallowing the body: 510 gaps, 36% of the queue

**Corpus-wide, 20 Sep 2026 (`tools/audit/contents-region-overrun.sql`, measured
mid-replay so re-derive before quoting):**

| | |
|---|---|
| contents role outlasts the printed list | **3,119 of 3,212 instruments**, worst overrun 13 pages |
| the sharp form: operative law parked in the contents region | **934 blocks, 350 documents, 399,161 characters** |

The first row is mostly harmless -- the overrun usually catches blank and
apparatus blocks. The second row is the defect, and it is the **largest single
body of uncitable law in the corpus**: nearly 400,000 characters of operative
text that our own extraction holds, in the PDF's own words, attached to no
provision and therefore reachable by no citation.

Worst by stranded characters: 4498 (92 blocks, 63,479 chars, pages 3-76),
2921 (63, 21,225), 4409 (20, 16,448), 4416 (25, 16,163), 4428 (25, 12,193),
3677 (44, 12,144), 4139 (40, 11,032), 3970, 2846, 3423 (25 blocks over pages
2-26).

**Corroborated from a disjoint measurement.** Classifying the contents-gap
`absent` class against raw PDF text -- a completely different route to the same
question -- found **74 of 93 `swallowed` gaps sit below a body floor set past the
page that prints them**: doc 3423 floor page 27 of 33, doc 4498 floor 76 of 1307,
doc 4400 floor 13 of 315. Two independent measurements name the same mechanism,
which is the strongest evidence this pattern has.


Measured while classifying `period_other`. **510 pending gaps across 82 documents
-- 36% of the whole queue -- are one cause**: the segmenter's contents region ran
into operative text, so the body it cut was never the body.

- **Document 4428**, Sindh Public Procurement Act 2009. The PDF is a compendium:
  the Act on pages 1-15, the Rules from page 16. The segmenter chose the RULES'
  table of contents on page 17 and set `body_starts_page = 17`, so the Act's
  entire body became "contents". Page 13 prints `12. The Authority may invest its
  surplus funds...`, 13, 14, 15 in a right-marginal-note layout. **All 27
  sections of the Act are uncitable.**
- **Document 4139**, Bahawalpur Museum Regulations 1998. No contents list exists.
  Pages 1-14 -- 38,414 characters, 50.6% of the document -- are filed as
  contents; the body floor is page 15, the Third Schedule. So regulations 1 to 38
  are absent and the only citable "sections" are the Third Schedule's 39 job-post
  rows, wearing the FIRST Schedule's names, because the parser read the First
  Schedule as the contents list and the two tables number differently: First
  Schedule 3 is "Research Officer", Third Schedule 3 is "Administrative Officer".

Constant contents-to-body offsets are a separate, smaller population:
`tools/census_contents_offset.py` finds **17 runs in 13 documents, 141 entries**,
of which three are page-verified (4499 at +1 over 27 entries, 3508 at +1 over 24,
3387 at +2 over 9). They barely intersect the gap queue -- only 3 of the 13 carry
a `period_other` gap -- for the same reason the mis-citations do not: an offset
list satisfies every entry.

Artefacts named so they are not re-found: document 4057's Police Order offsets
(-12/-24/-36/-48 all match the same four body labels, one repeated block), 4501's
CrPC "+2000" (a fused page digit), 4089's -2 (the right column of a two-column
amendment schedule restarting at 1), and 4273's Securities Act -19/-43, which
vanished once whole headings were compared instead of a 26-character stem: the
Act states the same rule twice, once for a securities exchange and once for a
clearing house.

## "Absent" is a statement about our block table, not about the Act

*20 Sep 2026. 348 gaps over 156 documents; 212 of them undecided.*

The gap census asks whether a text_block **starts** with a given label. A block
routinely carries several printed sections -- document 2467's page-2 block holds
the entire body of sections 1 to 8 in one row -- so a section printed mid-block
is invisible to the test and is filed as absent. The name has been reading as a
claim about the statute when it is a claim about our granularity.

Tested line by line against the raw PDF instead, the class breaks up:

| verdict | gaps | docs | what it means |
|---|---|---|---|
| `none` | 160 | 83 | not printed in the shapes tested -- still needs the page |
| `swallowed` | 93 | 44 | the section IS in the corpus, in a block filed as contents |
| `opener` | 42 | 28 | printed plainly on a body page; a parser defect |
| `range` | 23 | 7 | the body prints a collapsed range, "16-25. [Omitted]" |
| `bare` | 15 | 7 | label alone on its line, text starts at the first sub-clause |
| `starred` | 10 | 3 | a `1[14 * * *]` deletion marker |
| `unreadable` | 5 | 4 | no usable PDF text layer |

**74 of the 93 `swallowed` sit below a body floor set past the page that prints
them** -- doc 3423 floor 27 of 33 pages, doc 4498 floor 76 of 1307, doc 4400
floor 13 of 315. That is the contents-region-overrun defect arriving from a
completely disjoint measurement, which is the strongest corroboration it has.

And `none` still does not mean absent. Doc 2923 prints sections 3 to 6 as
`1[(3)* * * * * * *]` on page 4, a shape the classifier's own patterns missed.
Thirteen documents' worth of `none` were then read by hand and **not one turned
out to be a section the Act lacks.**

### Extraction is not the problem; segmentation is

Ignoring whitespace, the PDF and our block table agree to **0.13%** (doc 3186:
15,216 characters against 15,207). An earlier `-layout` ratio of 1.54 was an
artefact of the measurement counting column padding as text. The entire
disagreement is granularity (blocks merging several sections) and role (body
blocks filed as contents). Both live in segmentation. **No characters are being
lost on the way in.**

### A replay orphans TOC-gap decisions too, and there is no tool for it

`tools/reattach_orphaned_adjudications.py` repairs S7 readings across a replay by
re-keying them on `(document_id, source_block_id)`. Nothing does the same for the
contents-gap queue. After the 19 Sep replay, **496 of 497 TOC gap adjudications
point at a retired instrument and zero pending gaps bind to one**, while 176
pending gaps carry an unbound prior decision -- real readings of real pages,
doing nothing. Same root cause as the blocked disposition assertions on doc 3581.

### Do not rebind an orphaned claim without re-reading it

Of 93 `absent_in_source` claims, **29 must not be carried forward as they stand**:

- Doc 3149's four (ss. 14, 15, 16, 18) are **contradicted by pages 6 and 7**,
  which print `1[14 * * *]` with the footnote "Section-14 deleted by Khyber
  Pakhtunkhwa Adaptation of Laws Order, 1975." The section is not absent from the
  source; it is present and marked deleted.
- Doc 4427's 25 rest on a contested reading: the reviewer saw "16-25. [Omitted]"
  and declined to fabricate provisions, but on the natural legal reading the Act
  did have those sections.

A rebinding tool that carries every orphaned decision forward would re-assert all
29. Re-anchoring is a mechanical repair of a pointer; it is not a licence to
re-assert a judgement that later evidence contradicts.

### Two measurement tools are wrong in both directions

`find_truncated_acquisitions.py` misses doc 127 and doc 2205 -- its
"ends mid-sentence" test fails when footnotes follow the last provision, and its
"last provision on last page" test fails when a Schedule follows -- and at least
one of its 11 hits is false: doc **3291** is a numbering offset (contents 31/32/33
against body 25/26/27), not a truncation.

The text-layer test asks whether a page is empty. Doc **4573** yields exactly the
string "CamScanner" on every page and passes. **The question is volume, not
emptiness.**

## A prefix test is not a name comparison, and the count that caught it

*20 Sep 2026. Found mid-replay, replay stopped, fixed, replay restarted.*

The heading-linker repair earlier today was right in principle: refuse a contents
heading when the provision's own text names a different section. Its
implementation asked the question with a prefix test on alphanumeric-only keys:

    return not (key.startswith(want) or want.startswith(key))

Extraction in this corpus routinely drops a glyph -- most often the letter "s".
So document 4331's section 17 extracts as `In trument  executed in` against a
contents entry `Instruments executed in Pakistan`; the keys diverge at the third
character, neither prefixes the other, and the guard threw away a **correct**
heading. Document 2971 section 50 lost "Notifications as to release from
superintendence" against a body reading `Notification a  to relea e from
uperintendence`. Document 4286 section 26 lost "Immunity of persons attending
court-martial" against `Immunity of per on  attending court -martial`. One name
in every case.

Measured over the 1,341 instruments the replay had reached: **+21 sections
gained, and 829 section headings removed** -- heading coverage 82.18% -> 80.98%.
A large share of the 829 were correct.

`tools/census_heading_mislabel.py` had already solved this exact class, over six
rounds of false positives, and its note says so plainly: *"Prefix comparison
caught none of these."* The fix was to reuse that measured comparison --
per-token equality with a `difflib` ratio floor, tolerating front-truncation,
initialism and singular/plural -- rather than to invent a second one. The guard
still fires where it should: doc 3868 s.5 carries "Power of Delegation" while its
body opens `75. Application for mineral permit`.

### The lesson is about what was measured, not about regexes

The repair had been measured, carefully, and the measurement was of the right
thing for the question then being asked: the mis-labelled census fell from 101
to 3 with **zero sections lost**. Both halves were true. Neither could see this
defect, because the census only counts provisions whose heading DISAGREES with
their printed opener -- a provision that loses its heading entirely drops out of
the numerator *and* the denominator and reads as an improvement.

**A repair that can remove data needs a coverage measurement, not only a defect
measurement.** The defect count says "fewer things are wrong"; it cannot say
"and nothing went missing". The query that found it compared named-section counts
between each retired revision and its replacement, matched on
`source_observation_id` -- the append-only corpus makes that exact, and it should
be run after any change that can drop a field.

### And: stop the job

The replay was 30% through when this surfaced. Letting it finish would have
written the regression across 4,638 documents and required a third pass;
stopping cost 30 minutes. The advisory lock is released when the connection
drops, by design, so a killed segmentation run leaves nothing to clean up.
