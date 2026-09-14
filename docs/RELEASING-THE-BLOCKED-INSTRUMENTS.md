# How to release the instruments the gate is holding

*12 September 2026. Measured, not estimated: every number here is reproduced by
`./nz psql < tools/audit/blocked-release-worklist.sql`, which reads only.*

`v_release_instrument` excludes an expression while it has **any** pending
contents gap or **any** pending S7 unit. At the time of writing that is
**765 of 4,694 active expressions** — 3,929 released — held by 1,601 contents
gaps and ~1,600 S7 units.

An instrument releases only when **every** unit blocking it is covered, so the
value of a repair is the number of instruments it frees, not the number of units
it closes. That distinction reorders the work completely, and it is why this
document leads with yield.

## Yield, by repair

| | repair | frees | what it needs |
|---|---|---:|---|
| R6 | adjudicate the `probably-correct` S7 units | 9 | a decision row |
| R1 | relink class-a contents gaps | 16 | exact-tree overlay, **no replay** |
| R2 | `found_elsewhere` for class-b gaps | 2 | a decision row |
| R5 | reparent the `nesting` S7 units | 12 | tree edit + re-segment |
| R4 | split the `compendium` S7 units (S10) | 0 alone | document split |
| R3 | **the layout repair**: class-d gaps + `inverted` S7 | **161** | parser fix + re-segment |
| | *cumulative R1–R6* | **216** | |
| R3+ | *extend R3 to the class-e gaps whose section is printed* | **327** | parser fix + re-segment |
| R7 | the residue | — | **a person reading pages** |

**Ceiling without any human reading: 3,929 + 327 = 4,256 released.**
**438 instruments then remain**, 128 of them blocked by a single unit, spread
over 235 documents and 548 gaps.

## The contents-gap queue, classified

`tools/triage_toc_gaps.py` splits it five ways:

| class | gaps | what it is | repair |
|---|---:|---|---|
| a | 220 | the label **is** a section; only the link is missing | relink |
| b | 6 | the heading names exactly one other provision | `found_elsewhere` |
| c | 11 | the heading names several — ambiguous | page |
| d | 464 | the label exists, but only as a **demoted clause** | R3 |
| e | 900 | neither label nor heading anywhere in the tree | see below |

Class d is the S7 `inverted` class seen from the other side: the same defect,
counted twice, once per queue.

## Class e is not what its name suggests

"Neither label nor heading anywhere in the **tree**" is not "absent from the
**source**". C5 = 0 guarantees every character of every PDF sits in a
`text_block`, so the raw blocks can be searched directly — and must be, because
the tree is the very thing in question.

Searching them (excluding the contents list's own blocks, which otherwise match
themselves and return a meaningless 100%):

```
900  class-e gaps
 735  ... have a heading long enough to search on          (165 do not)
  505  ... whose heading IS printed in the body as well     (230 only in contents)
   109  ... in a block that also carries the number
   396  ... printed with NO number beside it
    318  ... with substantive text in the next two blocks
```

**318 promised sections have both their heading and their operative text printed
in the document.** They are not missing law. They are law the corpus holds and
cannot cite.

381 of those 396 heading blocks are already owned by a provision — the *wrong*
one, the section printed before them. Only 15 are orphaned. That is why C5 stays
green while the citation is wrong: nothing is lost, it is misfiled.

### What the pages actually look like

The dominant typesetting is a run-in or marginal heading with no number:

| document | contents promises | the body prints |
|---|---|---|
| 169 | `6. Amendment of West Pakistan Act No. XXXII of 1958.` | `Amendment of West Pakistan Act No. XXXII of 1958.` — no number, 416 chars following |
| 306 | `3. Repeal of Sindh Ordinance X of 2002.` | the heading alone, in the margin |
| 904 | `9.` / `10.` | two headings stacked, 176 and 1,548 chars following |
| 949 | `6.` `8.` `9.` | `Accommodation. Other facilities. Leave. Travelling Allowance …` — a whole column of headings in one block |
| 877 | `12. Medical facilities.` | `Medical facilities. 12. 2[The Speaker …` — heading and number fused |

The x-percentile column test finds only 76 of the 505 in "two-column" documents
and 14 geometrically in the margin, so **geometry alone will not drive this
fix**: the extractor has usually already merged the columns into one block. The
signal that does hold is textual — a heading-shaped run with no number,
immediately followed by operative text.

## The S7 queue, classified

`./nz s7` classifies it; the same rules are replicated in SQL in the worklist
script so the two queues can be joined per instrument.

| verdict | units | instruments | proposed |
|---|---:|---:|---|
| unclear | 739 | 205 | needs a person |
| inverted | 384 | 104 | `restore_citable` |
| probably-correct | 286 | 76 | `accept_non_citable` |
| nesting | 139 | 25 | `reparent` |
| compendium | 93 | 6 | `split_instrument` |

**The gate only opens on `accept_non_citable`.** `v_structural_adjudication_pending`
is `a.id IS NULL OR a.resolution <> 'accept_non_citable'`, so recording
`restore_citable`, `reparent` or `split_instrument` leaves the instrument
blocked until the tree is actually repaired. That is correct, and it is the
reason R3, R4 and R5 are parser-and-replay work rather than decision work: there
is no way to clear them by writing a row, and any attempt to do so would turn
the audit green over uncitable law.

## What no tool may do

Migration 0042 requires `absent_in_source` to carry
`evidence @> '{"human_page_review": true}'` **and** a `render_artifact`, with the
reason in the migration itself: *"A claim that the official source omits a
promised section is a human page-reading result, not a parser inference. Store
both facts so a future bulk tool cannot silently manufacture these decisions."*

So the true-absence residue cannot be closed by any amount of analysis. After
the layout repair it is 548 gaps across 235 documents; `./nz toc-review` renders
the pages, `tools/review_toc_gaps.py` writes the manifest a decision can cite.

## Order of work

1. **R1 + R2 + R6** — 27 instruments, all overlay or decision, no replay, no risk
   to S7 evidence. Use `tools/relink_toc_typography.py --exact-label`.
2. **R3, the layout repair** — the one that matters. 161 instruments on the
   demoted class alone, 327 once extended to class e, and it is the only repair
   that makes currently-uncitable law citable.
3. **R5, then R4** — 12 instruments and the six compendium documents.
4. **R7** — 235 documents' pages, read. Nothing else closes them.

## What this supersedes

`docs/WHY-S7-AND-TOC-CANNOT-CLOSE.md` concluded the residue had *"no independent
evidence in the corpus, in either direction."* That was true of the signals it
tried — all of which interrogate the **tree**. Searching the **raw blocks**
instead was not among them, and it separates 318 of the queue on exact evidence.
The earlier document's method table stands; its conclusion does not.

---

# Applied

## 1. The legacy run-only gap arm — closed, 5 instruments released

`v_toc_gap_pending` has two arms. The first is a real `instrument_toc_entry`
with a NULL `provision_id`. The second is legacy: a label in the latest
segmentation run's `detail->'missing'` with **no entry row behind it at all**.

Six instruments carried 64 of the second kind, and in them the arithmetic did
not hold:

| document | contents rows | all matched? | run says missing | sections in tree |
|---|---:|---|---:|---:|
| 3962 | 5 | yes | 37 | 58 |
| 3584 | 1 | yes | 14 | 16 |
| 3765 | 7 | yes | 10 | 56 |
| 1813 | 7 | yes | 1 | 145 |
| 3823 | 7 | yes | 1 | 10 |
| 3880 | 41 | no (32/41) | 1 | 9 |

Document 3584 prints a one-row contents list, the run matched that row, and the
run *also* reported 14 labels missing — `2`–`14` and `1.2.3.1`. Every one of
them is an active section of the instrument. **Where every contents entry is
matched, `missing` must be empty.** These runs overreport it.

All 64 resolved to exactly one active section each, none ambiguous, none already
answering another contents row. Recorded as `found_elsewhere` with
`found_provision_id` through the NULL-`toc_entry_id` path migration 0043 built
for exactly this — `tools/adjudicate_run_only_gaps.py`.

The **upstream defect is not repaired**: the segmenter still counts labels as
missing that were never promised. That needs a parser change and a replay.

This also unblocked `tools/relink_toc_typography.py`, which refuses any
instrument whose pending set contains a NULL entry id — a guard that was
rejecting five documents wholesale for one phantom row.

## 2. S7 citation-preserving — 11 more decisions

`tools/adjudicate_citation_preserving.py` became eligible on document 3584 once
its gaps closed (the method excludes any label the document's own gap queue
still reports). Applied.

## 3. What was deliberately NOT applied

`tools/adjudicate_toc_found_elsewhere.py` proposed one decision: document 3805,
contents row 13 "Electricity Duty." → body section **3**. The heading matches
exactly and the page order fits, so the tool is right that they are the same
provision. **It was not applied**, because the body label is a misreading:

```
contents  3. .........]          -> linked to section "3"
contents 13. Electricity Duty.   -> unlinked
sections  1, 2, 4, 5, 6, 7, 8, 9, 3 (heading "Electricity Duty.", p5), 14 … 17
```

The body's `3.` on page 5 sits after 9 and before 14 and is headed "Electricity
Duty." — it is `13.` with the leading digit lost. Contents row 3, which the
source marks repealed (`………]`), is currently linked to it. Recording
`found_elsewhere` for row 13 would close a gap while leaving a **wrong citation
live**: "section 3" would return the Electricity Duty provision. The repair is a
label correction, which is a tree change, not a decision row.

## Position after this work

| | before | after |
|---|---:|---:|
| released instruments | 3,929 | **3,935** |
| contents gaps pending | 1,601 | **1,537** |
| run-only gaps | 64 | **0** |
| S7 pending | 1,542 | **1,531** |

Audit 29/30 (S7 alone red), C5 = 0, A5 pass, lint unchanged bar
`many-top-level-sections-share-a-label` 28 → 26, 190 tests pass.

The pages for the 196 documents whose gaps a reading can actually close —
the only ones that can yield `absent_in_source` — are rendered under
`.artifacts/toc-gap-review/`.

## A false alarm, recorded so it is not raised again

Document 3805's misread label (`13.` parsed as `3.`) raised the obvious worry:
are contents rows linked to the wrong provision elsewhere, and is any of it in
the release set? Measured across all 81,870 linked contents rows:

| | rows |
|---|---:|
| linked rows whose citation key differs from the provision's | 84 |
| ... after treating `01` and `1` as one citation | 28 |
| ... of those, headings agree — benign | 3 |
| ... heading absent on one side — undecidable | 5 |
| ... **labels differ AND headings differ** | **20** |

All 20 were read. **None is a mislink.**

* Document 2009 supplies 16 of them: its contents numbers the Parts in arabic
  (`2`, `3`, `4` …) and the body prints them in roman (`II`, `III`, `IV` …).
  Headings agree exactly — `PART–III REQUISITIONS` against `REQUISITIONS`.
* The remaining four — documents 1337, 3154 and 4343, all released — are
  schedules the contents numbers (`15`, `19`, `20`, `22`) and the body names
  (`SCHEDULE I`, `Schedule`). Headings agree in substance.

So document 3805 is not the head of a class. A misread label shows up as an
*unlinked* contents row, which the gap queue already holds; it does not leave a
wrong citation live in the release set. Worth knowing before anyone builds a
relabelling tool on the strength of that one document.

The first measurement — "84 mislinks, 50 in the release set" — was wrong because
the citation key kept leading zeros, so every `01`→`1` link counted as a
mismatch. Strip them before comparing.

## A correction to the R6 row

The yield table credits R6 — "adjudicate the `probably-correct` S7 units" — with
9 instruments. That row uses `s7_triage`'s verdict, which is a **length rule**:
the kept block is at least three times the demoted one and at least 120
characters. The completed rendered-source audit
(`E:/nizam-data/s7-audit/RESULT.md`) is explicit that length is not sufficient:

> The sampler's automatic labels flagged 53 of 200 (26.5%) as WRONG … Rendering
> the pages showed that figure is wrong … a long "demoted" block is usually a
> schedule list, a table row, or a page footnote.

and that the required second signal is the source's own printed contents list,
which a no-contents document does not supply. `adjudicate_citation_preserving.py`
enforces that and found **11** eligible units, not 9 instruments' worth.

So R6 should be read as an upper bound on a rule the audit has already declined.
Treat the `probably-correct` verdict as a *triage ordering*, not a decision.
Extending it into an adjudication rule would overturn a considered conclusion on
weaker evidence, and would be the "program approving its own decisions" that
`./nz lint` exists to catch.

## Current yields

Re-measured after the work above:

| | instruments |
|---|---:|
| blocked | 760 |
| freed by the mechanisable repairs incl. the layout fix | **328** |
| still blocked, needing a person | **432** |
| ... of those, blocked by a single unit | 126 |
| documents behind the remaining contents gaps | 229 |

Ceiling without human reading: **3,935 + 328 = 4,263** of 4,695.

---

# Source evidence: what the rendered pages actually show

Four gaps were read against rendered source pages before any rule was written.
They settle the shape of the queue, and one of them overturned a rule that had
already been coded.

**Document 173, page 3 — printed, and not citable.** The page prints
`3. (1) The Government may, by notification in the official Gazette, declare any
Education Service to be an Essential Service`, with
`Declaration of Essential Service and prohibition of Strike, lockout and other
illegal acts.` set in the left margin across seven lines — the contents' exact
words. The tree holds that text as **`clause 3` under section 2**. The law is in
the corpus; it is not citable as section 3.

**Document 176, page 5 — the same.** `12. The provisions of this Act shall
prevail notwithstanding anything contained to the contrary in any other Law.`
with `Provisions of this Act to override other laws.` in the margin.

**Document 1248, page 4 — the same.** `12. The Provincial Government may after
previous publication, by notification in the official Gazette, make rules to
give effect to the purposes of this Act.` with `Power to make rules.` in the
margin.

**Document 169 — the counter-example, and it broke the first rule.** Its
contents prints:

```
4.  Amendment of Sindh Ordinance No. VIII of 2000.
5.  Amendment of Sindh Ordinance No. VIII of 2000.     <- identical to row 4
6.  Amendment of West Pakistan Act No. XXXII of 1958.
```

and the body ends at section 5, whose marginal note is *"Amendment of West
Pakistan Act No. XXXII of 1958."* — the heading listed at 6. So the contents
row is a duplicated line and the Act has five sections, not six.

A rule that matched the **heading** alone claimed document 169 had a printed
section 6. It does not. Requiring the promised **number** to be printed within
two blocks of the heading excludes it, and cuts the class from 593 gaps to 123 —
the ones where both the heading and the number are on the page.

## What was recorded

`tools/classify_printed_but_uncitable_gaps.py` recorded **123 gaps in 69
documents** as `parser_defect`, each carrying the page, the block id, the block's
text, whether the label exists in the tree as a non-section, and the render
artifact where one exists:

| defect class | gaps |
|---|---:|
| `printed_section_held_as_a_non_section` (label is a clause/subsection) | 43 |
| `printed_section_absent_from_tree` | 80 |

`parser_defect` **deliberately does not close the gap** —
`v_toc_gap_pending` keeps parser defects pending until a replay proves them
fixed. This classifies the queue with source evidence; it does not empty it and
it releases no instrument. Recording `found_elsewhere` for these instead would
close 123 gaps while leaving 123 sections uncitable, which is the trap named at
the top of this document.

## Position

| | |
|---|---:|
| released instruments | 3,935 |
| contents gaps pending | 1,537 |
| contents decisions recorded | 290 (was 103) |
| — `parser_defect` | 133 |
| — `found_elsewhere` | 106 |
| — `absent_in_source` | 46 |
| S7 pending | 1,531 |

Audit 29/30, 193 tests pass, lint unchanged, C5 = 0.

---

# The layout defect, found and fixed

Reading document 173 said the section was printed and not in the tree. It did
not say why. Instrumenting a *copy* of the segmenter — three `kind = "clause"`
sites, each printing its label — named the site in one run:

```
DEMOTE@2442 label='3'
  section '2' parent=instrument ''  blk=6383
  clause  '3' parent=section    '2' blk=6409
  section '4' parent=instrument ''  blk=6415
```

Line 2442 is the rule for *numbered lists inside an enacted provision* — the
typography where a statute prints `1.` `2.` `3.` for list items rather than
`(a)` `(b)` `(c)`. It demotes a numbered block when it is **indented past the
provision that owns it** and continues unfinished prose.

The indentation was measured against the **owner's first block**. The page
geometry shows why that fails:

| block | x0 | content |
|---|---:|---|
| 6383 | **118.0** | `Definition. 2. In this Act, unless there is anything repug…` |
| 6406 | 265.6 | `(m) "Strike" means the cession or refusal of work by a` |
| 6408 | 118.0 | `Declaration of` |
| **6409** | **230.5** | `3. (1) The Government may, by notification in the official…` |
| 6411 | 139.6 | `Essential Service and prohibition of Strike, lockout…` |

Section 2's first block starts at **118** because its marginal heading is
*fused into it*. Section 3's marginal heading is a **separate** block, so its
text starts at **230.5** — the ordinary body margin. `230.5 >= 118 + 18`, so
section 3 read as an indented sub-item of section 2 and was demoted to a clause.

**The owner's first block is not a baseline when marginal headings are set in a
left column and fused inconsistently.** The fix compares against the body
column as well — percentile 50 of x0, the same pair `_toc_marginal_share` and
`tools/audit` already use:

```python
def _indented_past_body(block, owner_block):
    """Deeper than its owner AND deeper than the body column's left edge."""
    ...
    return block["x0"] >= body_column_x0 + 18
```

A genuinely indented sub-item clears both edges and is still demoted; a section
merely sitting at the normal body margin no longer is. With no usable geometry
the original single-edge behaviour is kept rather than silently switched off.

## Measured, both ways, on 1,533 documents

The guard was run ON and OFF over the same set — 733 blocked documents plus an
800-document random control drawn from the **release set**, so a regression in
released law could not hide. OFF is produced by forcing `body_column_x0` to
`None`, which the helper documents as the original behaviour, so the baseline is
the pre-fix parser rather than an approximation of it.

| field | before | after | |
|---|---:|---:|---|
| sections | 46,291 | 46,415 | **+124** |
| unlinked contents rows | 1,861 | 1,737 | **−124** |
| missing_toc | 1,061 | 940 | −121 |
| provisions | 236,216 | 236,216 | 0 |
| stranded blocks / chars | 0 / 0 | 0 / 0 | 0 |
| demoted (new S7) | 2,184 | 2,213 | +29 |

**81 documents moved: 69 improved, 0 regressed**, 12 neutral (they gain S7
candidates only). Provisions unchanged at 236,216 — no text moved; what changed
is which node owns it and at what kind.

`unlinked` is the number that decides, because it is what the release gate
counts. The session's costliest error was verifying against `seg.missing`
instead, which let a change measure "zero regressions" while costing 56 release
instruments.

## Applied

69 documents replayed, chosen so that **no currently released instrument would
become blocked** — checked per document against the after-state, not assumed.

| | before | after |
|---|---:|---:|
| **released instruments** | **3,935** | **3,989** |
| contents gaps pending | 1,537 | 1,443 |
| S7 pending | 1,531 | 1,533 |

The replay cost 54 S7 decisions and 6 contents decisions; 23 were immediately
re-earned by `adjudicate_citation_preserving.py`. Audit 29/30, C5 = 0, A5 median
1.0000, S9 exact.

**3,989 is past the 3,982 high-water mark** this session had been measuring
against.

## Verified corpus-wide

The guard was then measured over the remaining **3,063 documents** the first pass
had not covered — the whole active corpus is now checked, both ways:

| | documents | moved | improved | regressed |
|---|---:|---:|---:|---:|
| blocked + released control | 1,533 | 81 | 69 | **0** |
| everything else | 3,063 | 20 | 2 | **0** |
| **total** | **4,596** | 101 | 71 | **0** |

In the second set, 16 documents would gain S7 candidates without gaining any
contents linkage — document 4440 alone accounts for 74 of them (1,188 → 1,262
demotions). They were **not** replayed: a replay that adds S7 pending and
returns nothing costs release. They are listed in `.do_not_replay.txt` so the
next person does not rediscover it the expensive way.

71 documents replayed in total. Nothing else was touched.

## Position

| | session start | now |
|---|---:|---:|
| **released instruments** | 3,982 *(peak)* | **3,992** |
| released provisions | — | 358,365 |
| contents gaps pending | 1,478 | **1,443** |
| S7 pending | 2,155 | **1,533** |
| acquisition exceptions open | 0 | 0 |

`./nz drift` for the repair itself: release +62, contents gaps −94, S7 −9,
structural decisions +34, 15,104 provisions retired (append-only; nothing
deleted).

Audit **29 / 30** — S7 alone red. **193 tests pass.** Lint unchanged. C5 = 0,
A5 median 1.0000, S9 exact.

And the invariant the whole S7 argument rests on was re-checked after every
change above: **0 of 3,930 demotions — 2,397 decided and 1,533 pending — leaves
its label uncitable.** 100% remain reachable as a section.

## What is left

| | instruments | who |
|---|---:|---|
| further parser repair (class-d gaps + inverted S7) | 106 | the same method: instrument a copy, name the rule, measure both ways |
| relink / reparent / split | 54 | tooling exists; the relinker's ambiguity guards refuse the rest |
| **needs a person to read a page** | **543** | 225 documents; 1,450 pages already rendered and hashed |

Ceiling without human reading: **3,992 + 274 = 4,266** of 4,695.

Document 3255 is the largest single remaining cluster — 82 gaps in the
Balochistan Sales Tax on Services Act. Its defect is *not* the one fixed here:
instrumenting it fires no demotion rule at all, and the tree shows **104
subsections parented directly to a chapter** where sections should be. That is
a third distinct defect and wants its own diagnosis.

---

# A second defect: a Table swallowing the rest of the Act

Document 3255 was the largest remaining cluster — 82 gaps. Instrumenting it
fired **no demotion rule at all**, and the node-kind histogram said why:

```
('subsection', 'chapter'): 104      ('section', 'chapter'): 39
```

Sections 49 to 62 were `clause`s parented to section 48's subsection (2).
Section 48 reads *"If a person commits any offence described in column 2 of the
Table below…"*, which makes it an `explicit_table_owner`; every later numbered
row then becomes a clause of that table unless the row is the next section the
contents promises **and** its own text supports the printed heading:

```python
next_promised_section = (
    _toc_label_is_next(table_key, toc, seen)
    and _heading_supports(rest, expected_heading)      # <- only `rest`
)
```

That is the same blind spot as the first defect. Where a gazette sets marginal
headings, the heading is a **separate block before the numbered one** — which
`previous_heading_context` exists to collect, and which the schedule branch
*three lines above* already consults. So the fix is the adjacent code's own
pattern:

```python
    and (_heading_supports(rest, expected_heading)
         or _heading_supports(heading_context, expected_heading))
```

## Measured, not assumed

679 blocked documents, guard on and off:

| field | before | after | |
|---|---:|---:|---|
| sections | 29,392 | 29,428 | **+36** |
| unlinked contents rows | 1,545 | 1,536 | **−9** |
| provisions · stranded · demoted | — | — | **unchanged** |

**1 document moved, 0 regressed.** Document 3880, the Sindh Control of Narcotic
Substances Act: **9 sections → 45**, 357 provisions, contents agreement 0.976.
Thirty-six sections of narcotics law became citable again.

Doc 3255 itself is **not** fixed by this, and should not be forced. Its page 44
interleaves the penalty Table with the body in one flattened reading order —
`Compounding of` at x0 82, a table row at 211, a table column at 343, then `51.`
at 194.5. The heading scan stops at the intervening prose, correctly. Repairing
it needs column-aware reading order at **L1**, not another parser guard, and
that is a different component.

# The next diagnostic: a zero gap count can still hide an uncitable section

Document 4058 has 101 contents rows and **one** gap — yet its tree holds 126
subsections parented directly to chapters. A contents entry may link to *any*
provision, so an entry pointing at a clause satisfies the gap queue while the
section it promises is not citable (INV-4).

Measured over every linked contents row whose `entry_kind` is `section`:

| the row links to a | rows | instruments | in release |
|---|---:|---:|---:|
| section | 81,053 | 3,095 | 60,654 |
| **clause** | **890** | 25 | 743 |
| **subsection** | **7** | 2 | 7 |

**Document 4490 is 604 of the 897 and is a false positive**: it is the Code of
Civil Procedure, whose contents lists Order *rules*, and a rule under an Order
is correctly not a section of the Act. That leaves roughly **290 rows across 26
instruments** worth reading — the largest being the Balochistan Sale Tax Act
(47), the Industrial and Commercial Employment Standing Orders (25) and Bolan
University of Medical Sciences (24).

This is not a release blocker and the gate does not test it. It is recorded
because it is the one measure that tracks the project's actual requirement —
every law citable at the number its source prints — and the gap queue does not
see it.

---

# Correction: class d was overstated tenfold, and this document said so

The yield table near the top credits the "layout repair" with 161 instruments on
the strength of **464 class-d gaps** — "the label exists, but only as a demoted
clause". That number was wrong, and the error was in the test, not the data.

`label exists somewhere in the tree as a non-section` matches almost any gap. A
contents row promising section 5 finds subsection (5) of section 3, or
definition clause (5) of section 2. Measured:

| | gaps |
|---|---:|
| match the loose test | 346 |
| ... where the non-section's **heading** is the promised heading | **0** |
| ... where the non-section hangs off the instrument, a part or a chapter | 35 |
| **class d, actually** | **35, in 13 documents** |

Worked examples of the false positives:

| document | contents promises | the loose test matched |
|---|---|---|
| 876 | `10. Finance and Planning Committee` | `(10) "Patron" means the Patron of the University` |
| 1034 | `5. Constitution of the Board` | `(5) If a question arises whether any matter is of policy…` |
| 141 | `2. Amendment of section 19…` | `(2) The Committee on Public Accounts shall scrutinize…` |

**Zero of 346** have a non-section carrying the promised heading. So the
"printed law demoted to a clause" story — true of documents 173, 176, 1248 and
3880, which were read and fixed — does **not** describe what remains in the
queue. It described the documents it was found in.

`tools/audit/blocked-release-worklist.sql` now requires the match to be
structurally plausible, and carries this reasoning in a comment so the next
person does not re-derive it.

## Yields, corrected

| repair | frees |
|---|---:|
| relink class-a gaps (overlay, no replay) | 19 |
| `found_elsewhere` class-b | 2 |
| reparent `nesting` S7 | 12 |
| parser repair, class-d + inverted S7 | 36 |
| *cumulative mechanisable* | **88** |
| **needs a person to read a page** | **615** |

| | instruments |
|---|---:|
| blocked | 703 |
| freed by every mechanisable repair | **221** |
| **still blocked, needing a person** | **482** |

Ceiling without human reading: **3,992 + 221 = 4,213** of 4,695.

## What this means for "production ready"

The remaining queue is **not** mostly machine-fixable, and saying otherwise
would be the comfortable answer rather than the true one. It is:

* **482 instruments** whose contents rows need a page read to say whether the
  source omits the section or the parser missed it, and
* **1,533 S7 units**, of which the completed rendered-source audit already
  established that no aggregate can settle the residue.

Both are gated on a human by deliberate design. Migration 0042 requires
`absent_in_source` to carry `human_page_review: true` and a render artifact, and
says why in its own text: *"a human page-reading result, not a parser
inference… so a future bulk tool cannot silently manufacture these decisions."*
`v_structural_adjudication_pending` opens only on `accept_non_citable`, so no
`restore_citable` or `reparent` row clears the gate without the tree actually
being repaired.

Those two rules are what stop the audit going green over uncitable law. The
corpus reaching 4,213 of 4,695 released with both intact is the honest ceiling
of machine work; the last 482 are a reading task, and 1,450 pages for 832 gaps
across 224 documents are already rendered and hashed under
`.artifacts/toc-gap-review/` for it.

---

# Final correction, and the honest ceiling

Two more rows of the yield table rested on the same kind of loose match, and
both are now tightened. **Every number in this document above this line that
came from the first version of the script is too high.**

## R1 (relink) is exhausted, not worth 19

184 class-a gaps remain across 40 instruments:

| | gaps |
|---|---:|
| several sections share the citation key | 65 |
| several pending entries share the key | 115 |
| the section already answers another contents row | 52 |
| **unambiguous** | **4** |

And all four of those are false matches, because `_citation_label_key` strips
dots, so `2.1` and `21` are the same citation:

| document | contents prints | matched body label |
|---|---|---|
| 3912 | `21`, `22` | `2.1`, `2.2` |
| 4347 | `2.5.5` | `25.5` |
| 4416 | `1.1` (p6) | `11` (p66) |

`relink_toc_typography.py` plans zero links and is right to. R1 is done.

## The closable set was counting heading matches

`_closable` included every gap whose promised heading appears in the body with
substantive text after it. That is the test **document 169 disproved**: it
prints `Amendment of West Pakistan Act No. XXXII of 1958.` as the marginal note
of section *five*, and its contents lists that heading at 6 only because rows 4
and 5 are a duplicated line. Counting heading matches alone gives 593 closable
gaps; requiring the promised **number** beside the heading gives **123**.

The script now requires the number, with the reasoning in a comment.

## Where it actually lands

| | instruments |
|---|---:|
| blocked | **703** |
| freed by **every** machine repair available | **113** |
| **needs a person to read a page** | **590** |
| ... of those, blocked by a single unit | 215 |
| documents behind the remaining gaps | 387 |

**Ceiling of machine work: 3,992 + 113 = 4,105 of 4,695 expressions.**

Successive honest measurements moved that ceiling 4,266 → 4,213 → **4,105**.
Every step down came from finding a test that matched more than it proved, and
in each case the looser number was the flattering one. The three that were wrong
— loose class d, heading-without-number, and dot-stripped citation keys — are
now fixed in the script and carry their reasoning inline.

The remaining 590 are a reading task, not an engineering one. 1,450 pages
covering 832 gaps in 224 documents are rendered and hashed under
`.artifacts/toc-gap-review/`, and `tools/merge_gap_render_manifest.py` keeps the
manifest whole.

---

# The "bigger twin" shortcut does not work

After the Raisani Hospital Act was fixed by fetching its complete Gazette copy,
the obvious next move was to look for documents whose complete twin is *already
in the corpus*: same year, similar title, more pages. Eleven instruments have
over half their contents unresolved; three of them matched such a twin.

**All three are wrong merges, each for a different reason.**

| truncated | twin | why it is not a duplicate |
|---|---|---|
| 1927 Land Preservation Act, 1900 (17p, **sindh**) | 2366 West Pakistan Land Preservation Act, 1900 (22p, **kp**) | the same 1900 Act **adapted by two provinces**. Two instruments, not one. |
| 4450 Sindh Civil Servants Promotion Rules 2022 (29p) | 4471 same title (40p) | 4450 is not the rules. It is **THE SINDH GOVERNMENT GAZETTE, Karachi, 31 March 2022, No. 13** — an entire gazette issue whose Part I carries many notifications; the first on page 1 concerns a doctor's ex-Pakistan leave. Linking it away would bury every other notification in it. It wants an S10 split. |
| 4564 Workers Compensation Rules, 2020 (36p) | 4483 Sindh Workers Compensation Rule, 2020 (37p) | unverified, and the two above are reason enough not to take it on title and page count. |

The signals that separate them are cheap and must be checked before any link:

* **jurisdiction** — a provincial adaptation is its own instrument;
* **what the document IS** — a gazette issue is a container of many
  instruments, and its page-one title says so;
* **the rendered first page** — both of the above were visible on it, and
  neither was visible in the metadata.

So the Raisani pattern does not generalise from the catalogue. It worked there
because the *same* Act existed in two acquisitions of the same jurisdiction, one
demonstrably truncated, and both were read. Absent that, a bigger twin is a
coincidence of title and length.

---

# A replay I should not have run, and what it exposed

`find_stale_trees` classifies a document as **costs** when today's parser would
make it worse, and refuses to emit it. Document 3691 was in that set. I replayed
it anyway, as a controlled test of whether a document blocked only by S7
collisions could be replayed and then re-adjudicated back into release.

It could not, and the tool was right.

**ESSENTIAL PERSONNEL (REGISTRATION) ORDINANCE**, 15 pages, was released with 7
sections. Today's parser gives **131**, with contents agreement **0.0534** — the
parser's own signal that the contents list it found is not one. The replay took
it out of the release set and added 60 gaps. Revisions only move forward, so the
prior tree is retired and this cannot be undone by re-running; only a corrected
parse will restore it.

None of today's ten parser changes caused this. Document 3691 reads 131 sections
in **all four** whole-corpus passes, including the earliest baseline. Today's
parser is simply worse than the one that wrote its stored tree, which is exactly
the case the *costs* classification exists to protect.

## The defect it exposed

The Ordinance's real contents has seven entries — Short title, Definitions,
Liability to register at employment exchanges, Place of Registration,
Registration Certificate, Penalties and Procedure, Powers to amend Schedules.
`raw_toc` runs straight past them into the **Schedule**:

```
"7": "Powers to amend Schedules", "8": "Chemist.", "9": "Metallurgist.",
"10": "Geologist.", "11": "Mineralogist.", "12": "Meteorologist.", ...
```

An occupations list, absorbed as contents entries and then materialised as
top-level sections.

`_TOC_MIN_AGREEMENT` is 0.30 and this scores 0.053, so the floor should have
rejected it. It did not, because the **marker path** overrides the floor: where a
document prints an explicit `CONTENTS` marker and an enacting formula and the
first three promised headings are visible at the opening, `parse_contents`
accepts the boundary and sets `best_score = _TOC_MIN_AGREEMENT`.

That override is there for a real reason — a marginal-heading layout where the
body parser sees few of the promised labels, so aggregate agreement rejects a
genuine contents list. What it does not do is **bound how far the contents list
extends**. Three corroborated headings at the top license the whole run,
including a Schedule that happens to be numbered.

The shape of a fix is therefore: on the marker path, stop the contents at the
last entry the body corroborates rather than accepting every numbered row after
the marker. That is a change to contents detection, which is the highest-risk
area in the segmenter -- a wrong contents cuts the body -- and it wants its own
whole-corpus measurement.

## The trade this was testing, measured

`tools/released_but_understructured.py` reports it. Of 4,026 released
single-expression instruments, **57 would gain sections but lose release**, with
**666 citable sections** at stake — sections that sit today as subsections under
a chapter or part and are therefore not citable at the number the statute prints.
The Sindh Public Procurement Act, 2009 is the clearest: released with 36
sections, where today's parser finds 87 and 232 of its subsections hang directly
off `part I`.

Those 57 are a real question and not a mechanical one. Document 3691 is why they
are not simply replayed.

---

# Sweeping for opener defects, and where the seam runs out

Three defects were found one document at a time, and all three had the same
signature: a block that OPENS with the promised label, whose text the contents
corroborates, and which the parser refuses.

    16 Zone approval criteria.- ...         no period after the number
    21.(1) Government may, by notification  no space after the period
    Power and Function of 4.  The follo...  the marginal note fused inline

`tools/find_unrecognised_openers.py` does that sweep over the whole pending
queue and groups the refusals by the SHAPE of the characters between the label
and the text, so a candidate defect arrives with its size attached. One block is
an anecdote; forty sharing a separator are a rule worth measuring.

**Its first version asked the wrong question.** It tested `classify()`, but the
contents-corroborated rules live in `_classify_body`, so it reported shapes that
are already handled -- 245 refusals where the real figure is smaller. Fixed to
ask what the parser asks.

## What the sweep says is left

| shape | count | verdict |
|---|---:|---|
| space only, no period | 121 | mostly `1 \| P a g e` footers, years, footnote markers |
| label runs into the text | 118 | `1ACT No. VI Of 1878`, `1967`, amendment brackets |

The real residue inside those is small, and two candidate rules were measured
and **rejected** rather than written:

**Re-parenting an unnumbered marginal heading.** The idea was to open a section
where the source prints the promised heading with no number beside it. Sizing it
honestly killed it: the first measurement said 927 of 927 gaps had their heading
printed in the document -- 100%, because it was matching the contents ROW. After
excluding contents blocks, 551; the safe "re-parent, nothing cut" subset looked
like 241, until one was read. Document 3475's match was not an unnumbered
heading at all but `16 Zone approval criteria.` **carrying** its number and
missing only a period. The class was largely not the class.

**Sequence-corroborated openers.** Where the body prints no heading at all
(`15 (1) Where any land has been acquired for a company ...`) the contents
cannot corroborate, so position would have to: the tree holds N-1 and N+1, and a
refused block opening with N sits between them in reading order. Exact, and too
small -- **15 gaps**, of which several are `3 | P a g e` and
`4 Substituted vide Khyber Pakhtunkhwa Act. No. IV of 2011.` About eight are
real. A rule that creates sections is not worth writing for eight when a page
footer is inside its blast radius.

## A bound on heading matching

Of 1,167 pending gaps, **104 have no usable printed heading** -- 42 blank, 25
stars or dots (`14. *******`), the rest under six letters. Those can never be
closed by any rule that matches a heading, whatever it does. The other 1,063
remain in scope.

That is where the opener seam runs out. The next defect will not be an opener
shape; the sweep has enumerated those.

---

# Document 3255, and why it is not fixed

The Balochistan Sales Tax on Services Act promises 89 sections and the tree
holds 48. Its 41 gaps are the largest single cluster in the queue, and it was
worth a long look because the sections ARE printed. It is recorded here as not
fixed, with what was ruled out, because the next reader should not repeat it.

`_classify_body` reads its section 49 correctly:

    'Default Surcharge. 49. (1) Notwithstanding the provisions of section 24 ...'
      classify        -> None
      _classify_body  -> ('section', '49')

So the inline-fused-marginal-note rule works on it. The section is still a
CLAUSE, nested under section 48's subsection (2) -- the "illustrative purposes"
subsection that follows its Table.

What was ruled out, each by measurement rather than reading the code:

* **Not a demotion.** `tools/name_the_demotion.py` fires nothing for label 49.
  Three `kind = "clause"` sites and none of them runs.
* **Not the schedule path.** A row inside a schedule becomes a clause OF the
  schedule; this one's parent is a subsection.
* **Not the trailing-table rule.** That demotes a repeated label after the body
  ends: it needs `idx > last_body_section` and the label already `seen`. For
  unit 555 both are false -- 555 < 945, and "49" has not been seen.
* **Not a broken body marker.** `last_body_section` reaches unit 945 and section
  89, the Act's last. The marker sees the whole body.
* **Not the schedule-resumption guard.** With a contents list, resumption needs
  `key in toc and key not in seen`, which holds, and `idx <= last_body_section`,
  which also holds.

The actual mechanism is upstream of all of them. `subdivide` cuts the block at
its internal provision start before anything classifies it, so the three units
that reach the grammar are

    'Default Surcharge.'   '49.'   '(1) Notwithstanding the provisions ...'

and `'49.'` arrives as a section with NO text. The contents-corroborated rules in
`_classify_body` never see the whole block, because the cut happened first. What
then attaches a textless section beneath the preceding subsection is a fourth
path, and the tree it produces is consistent with several of them.

A fix therefore has to change the ORDER in which cutting and contents
corroboration happen, not add another rule beside the existing ones. That is a
structural change to `subdivide`, the function every document passes through,
and it is not worth attempting at the end of a long session on the evidence of
one document. It wants its own measurement, and the 41 gaps will still be there.

---

# The right-margin layout, which is now most of what is left

**238 of the 350 documents holding pending contents gaps set their marginal
headings to the RIGHT of the body, and 753 of the 1,045 gaps sit in them** --
72%. Every heading-based rule in the segmenter reads the margin through
`previous_heading_context`, and that function walks BACKWARDS. In this layout it
can never see the heading it needs.

The Sind Agriculturists' Relief Act, 1879 (document 3353, 48 gaps, the largest
single cluster) shows the shape exactly. Page 11 holds sections 11 and 12, and
its blocks arrive in this order:

```
136  x0  72.0   THE SIND ACT NO. XVII OF 1879 ...        running title
144  x0  72.9   11. Every suit of the description ...    section 11
147  x0  72.9   12. In any suit of the description ...   section 12
148  x0  72.9   and in any suit for the descriptions ...
149  x0 459.7   <24 blank lines> Agriculturists to be    ALL the headings
                sued where they reside. ... History of
                transactions with agriculturists- ...
150  x0  90.0   1. See now the Code of Civil Procedure   footnotes
```

Two things make this hard, and both are visible above:

1. **The headings arrive last.** Block 149 follows every body block on the page,
   so a backwards scan from section 11 reaches the running title, never the
   note. The detached-heading pass has a forward arm for exactly this; the
   rules that consult `previous_heading_context` -- the Table rule, and both
   promotion guards -- do not.
2. **One block holds the whole column.** The page's marginal notes are a single
   text_block separated by blank lines, with one `y0` for all of them. They
   cannot be matched to their sections by geometry, because individually they
   have none. The only available correspondence is ORDER: the n-th note in the
   column belongs to the n-th numbered section on the page.

That second point is why this is not a small change. A rule keyed on order is
only as good as the assumption that every section on the page has a note and
every note belongs to a section, and a page with one un-noted section silently
shifts every pairing after it. It needs its own evidence -- probably the
contents list, checking the shifted pairing against what each label promises --
and its own whole-corpus measurement.

## Why reading cannot substitute for it

Document 3353's renders point at the wrong pages. Its stored tree anchors
section 1 to page 11, where the source prints sections 11 and 12, so
`review_toc_gaps` brackets the render around a page that cannot answer the
question. Reading it settles nothing, and recording a decision from it would be
recording the wrong evidence.

Where the tree is wrong about WHERE a section is, the rendered-page route
inherits that error. The parse has to be right first. That is the order of work
for the remaining queue, and it is why the 753 are not simply a reading backlog.

---

# Footnotes stored as sections, and why replaying does not fix them

**142 active sections across 73 documents are anchored to a block in the bottom
14% of its page whose label restarts well below what that page already
reached.** That is the signature of a footnote list read as law:

```
doc  930  "section 1"   1. Subs vide the Khyber Pakhtunkhwa Act No. IV of 2011.
doc  999  "section 1"   1. Repealed vide A.O 1937.
doc 1178  "section 3. 4"  3.  4. The words beginning with "and unless" ... rep. ibid.
doc 3353  "section 1"   1. See now the Code of Civil Procedure, 1908).
```

Those are the amendment apparatus. Document 3353's page anchors are wrong for
exactly this reason -- its "sections 1 and 2" are the footnotes at the bottom of
page 11, which is why `review_toc_gaps` renders page 11 when asked where section
1 is, and why reading that render settles nothing.

## The current parser already rejects them

`_is_furniture` marks a bottom-margin block as apparatus when it matches the
footnote vocabulary, and it fires correctly on these:

```
block 43684  y0 730.6 of 841.7   _FOOTNOTE.match True   _is_furniture True
```

So these are OLD STORED TREES, not a live defect. The guard was added after they
were written.

## And replaying them costs more than it gains

| document | stored | today's parser |
|---|---|---|
| 930 | 5 sections, 0 gaps | **0 sections**, 7 unlinked |
| 1026 | 7 sections, 0 gaps | 6 sections, 3 unlinked |
| 1181 | 8 sections, 0 gaps | **3 sections**, 16 unlinked |
| 3353 | 83 sections, 48 gaps | 86 sections, 45 unlinked |

Removing the footnote-sections is right, and it exposes that these documents'
REAL sections are not being parsed either. Document 930 goes to zero sections:
everything it had was apparatus. So a replay trades a tree that is wrong but
complete-looking for one that is right and nearly empty, and the gate counts the
second as worse.

That is what `find_stale_trees` has been reporting as its 80-document "costs"
set all along. The set is not noise and not a tuning problem -- it is documents
whose body the parser cannot read, wearing trees built from their footnotes.

Fixing them means parsing those bodies, which is the same right-margin gazette
problem recorded above. Until then the honest position is that these 73
documents hold sections that are not law, and the corpus knows which they are.

---

# Reading the "costs" set instead of counting it

`find_stale_trees` has reported 77-87 documents where replaying would make
things worse, all session, as an opaque number. `tools/where_the_parser_is_worse.py`
prints the difference per document instead:

```
blocked documents compared        : 527
today's parser would make worse   : 87
  sections it would lose in total : 462
  gaps it would add in total      : 437

   doc         sections           gaps  title
  4244     142 -> 20         0 -> 0     Sindh Law Officer (Conditions of Service)
  4473     106 -> 26         0 -> 0     Sind Standard Weights and Measures
  2146      95 -> 27         0 -> 0     Sindh Local Councils (Property) Rules
  3867     111 -> 75         7 -> 60    The Punjab Excise Act, 1914
  3949      30 -> 16         0 -> 61    Punjab Education Foundation Regulations
```

It is not one problem. Reading the entries separates them:

**Compendiums, and the S10 detector misses nearly all of them.** Document 3949
is four separate rule-sets in one PDF, each with its own `SECTIONS` list
restarting at 1:

```
THE PUNJAB EDUCATION FOUNDATION (CONDUCT OF BUSINESS) RULES, 2005
  SECTIONS   1. Short title ...  2. Definitions  3. Powers and ...
... RULES, 2005
  SECTIONS   1. Short Title ...  2. Definitions  3. Funds of the Foundation
THE PUNJAB EDUCATION FOUNDATION (CONTRACT APPOINTMENT) RULES, 2005
  SECTIONS   1. Short Title ...  2. Definitions  3. Employment on Contract
THE PUNJAB EDUCATION FOUNDATION SERVICE RULES 2006
  SECTIONS   1. Short title ...  2. Definitions  3. Senior ...
```

The parser reads the first contents list and then cannot find its sections,
because that Act's body sits after three more contents lists. It ends with 16
sections against 16 promised labels, none matched.

**34 blocked documents print three or more section-list headers and hold 185
pending gaps** -- 18% of the queue. `detect_multi_instrument.py` proposes THREE
splits in the whole corpus. The detector is far narrower than the evidence.

That is the next piece of work with a clear shape, and it is an S10 problem
rather than a segmentation one: no parser rule recovers an Act whose body is
separated from its contents by three other Acts. The remedy is to split the
document first, which the corpus already has a mechanism and an audit criterion
for.

**The rest are the containers already recorded above** -- 4244 a compendium of a
different shape, 2146 and 4264 with a schedule or form swallowing the body, 3867
and 3213 right-margin gazettes. None is a threshold to tune.

## Why the S10 detector misses them, confirmed

`detect_multi_instrument` requires `ordered_legal_form` before it will propose a
boundary: an enactment formula within seven blocks of the title, and a section-1
reset within four blocks after that formula. Tested against document 3949's
nineteen title-shaped blocks:

```
p1 'PUNJAB EDUCATION FOUNDATION (PEF) RULES &'   formula False   reset False
p1 'REGULATIONS'                                  formula False   reset True
p1 'RULES, 2005'                                  formula False   reset True
p2 'RULES, 2005'                                  formula False   reset True
p2 'THE PUNJAB EDUCATION FOUNDATION SERVICE RULES 2006'
                                                  formula False   reset True
```

Every internal title has its rule-1 reset. **None has an enacting formula beside
it**, because a front-loaded compendium prints its contents lists together and
its enacting formulae later, inside the bodies. The requirement is right for the
documents it was written against and wrong for this shape.

The fix has a clear specification: accept a boundary on title + contents marker
+ rule-1 reset, without requiring a formula, when the title is followed by a
printed section list rather than by enacted text.

**It is not done here, deliberately.** `--apply` writes boundary candidates,
which land in `v_boundary_adjudication_pending`, and S10 asserts that view is
empty. There is a detector and a materializer but no adjudication path between
them -- 44 candidates exist against 2 decisions. Widening detection without one
turns a passing criterion red with no mechanism to close what it opens, which is
worse than the gap it would document. The adjudication path has to come first.

## Correction: the compendium count above was wrong twice

Both numbers in the two sections above are withdrawn. The reasoning that
produced them failed in two independent ways, and both are worth stating because
each is a trap the next reader can fall into with the same tools.

**First: the costs set was contaminated by already-split documents.**
`where_the_parser_is_worse.py` compared a WHOLE-DOCUMENT fingerprint against one
expression's stored tree. A document that has already been split into several
instruments always loses that comparison, because the parser run covers all of
its expressions at once while the stored tree is only one of them. Document 3949
read as "30 sections -> 16, 0 gaps -> 61" on that basis and was written up as
the worked example of an unsplit compendium. **It already has three active
instruments.** Corrected, the set is 85 documents and 371 gaps, not 87 and 437.

This omission has now been made three times in this repository. `find_stale_trees`
carries the fix, `released_but_understructured` carries the fix, and this tool
did not until now.

**Second: counting section-list headers does not find compendiums.** The claim
that 31-34 blocked documents are unsplit compendiums rested on their printing
three or more `CONTENTS`/`SECTIONS` marker blocks. Reading the actual list kills
it:

```
doc 4451  29 markers  Customs Act, 1969
doc 4498  19 markers  Punjab Police Promotion Rules 1934
doc 3353  10 markers  Sind Agriculturists' Relief Act, 1879
doc 4387   6 markers  Cantonments Act, 1924
```

The Customs Act is one Act. A long statute's contents runs over many pages and
repeats its column header on each one, so the marker count measures CONTENTS
PAGES, not instruments. There is no compendium class here to widen the S10
detector for.

The detector was widened to accept `title + printed section list + rule-1 reset`
without an enacting formula, and that change is reverted with it: its premise
was this measurement. The detector still proposes three splits, which on this
evidence is the right number rather than a shortfall.

What survives is the earlier, narrower observation: document 3949's shape --
titles followed by their own section lists, formulae later in the bodies -- is
real and the detector cannot see it. It is simply already split, so it is not
evidence of a backlog.

---

# A superscript fused to the section number, and why it is left alone

The Dekkhan Agriculturists' Relief Act, 1879 prints its first section as

```
²1. Short title. Commencement.  This Act may be cited as the ³Dekkhan
Agriculturists' Relief Act, 1879 ...
```

The superscript `2` is a footnote marker. Extraction flattens it onto the number,
so the parser reads `21. Short title. Commencement. ...` and creates **section
21**. Section 1 is then missing and its contents row sits in the queue.

`_repair_label` exists for exactly this -- it strips a fused superscript when the
contents promises the shorter label -- and it does not fire here, for a reason
worth recording: **this Act has a real section 21 too.** The contents promises
both `1` (Short title) and `21` (Arrest and imprisonment in execution of decree
for money abolished), so the fused label is indistinguishable from a legitimate
one by label alone.

The heading could separate them, and does not: `_heading_supports` compares from
the first word, and the contents concatenates two marginal notes --
`Short title. Commencement Local extent` -- while the body prints them as
separate paragraphs. Three words match, then they diverge, and it returns False.

## Measured before deciding

A first count said 254 of 853 numeric gaps have their label as a suffix of an
existing section label. That number is useless: section 21 legitimately ends in
`1`, so every gap on label 1 in a document holding a section 21 matches it.

The signature that means something is a section whose label the contents **never
promised**, ending in a label that is promised and missing. That is **160
sections across 19 documents**.

It is not acted on. Those 19 documents carry only three or four pending gaps
each despite holding 21, 17 and 43 phantom sections, so the phantoms mostly are
not what blocks them; and the repair renames existing sections, which is the
riskiest edit in the parser for a yield of a few rows. Recorded with the
measurement instead.

---

# The citation survives and the provision does not

`./nz s7-citability` reports a clean corpus: over **2,371 demotions, 100% of
printed labels are still reachable as a section, 0 lost.** That report is
correct. It is also the wrong question, and asking only it has hidden the
largest quality defect now in the released set.

The right question is not *is the label citable* but *does the citable node
carry the provision*. Measured with `./nz stub-citations`, over accepted
`retype_non_citable` decisions whose retyped node still holds 500+ characters:

| the citable section holds | units | documents | released |
|---|---:|---:|---:|
| **under 200 chars — a stub** | **243** | 132 | **165** |
| much less than the retyped sibling | 116 | 85 | 72 |
| smaller, same order of size | 100 | 79 | 62 |
| at least as much — the retype was right | 122 | 81 | 81 |

**359 citations in 194 documents resolve to less than half the provision, and
237 of them are in released expressions.** Named, all released:

| statute | what citing the section returns | uncitable |
|---|---|---:|
| Prevention of Corruption Act 1947, **s.5** | nothing; heading `Criminal misconduct 5A.` | 4,272 ch |
| Usurious Loans Act 1918, **s.3** | nothing; note `Re-opening of transactions` | 4,223 ch |
| Explosives Act 1884, **s.2** | the *commencement* clause | 5,123 ch |
| Torture and Custodial Death Act, **s.2** | `2. It extends to the whole of Pakistan.` | 4,481 ch |
| Punjab Control of Narcotic Substances Act, **s.7** | 279 chars of a 10,072-char section | 9,793 ch |

Unreleased, and the largest in the corpus: **Punjab Pure Food Rules 2011, rule
10** — *Non-nutritive constituents and artificial sweetening agent in food* —
686 citable characters against **138,890 uncitable** across 298 descendants,
including operative text (`(11) Artificial sweetening agents … shall not be
sold`). The gate is holding that one, which is the gate working.

## The mechanism, measured rather than assumed

The first draft of this section named the right-margin marginal note as the
cause, by analogy with *The layout defect, found and fixed*. **That was wrong,
and checking one document is what showed it.** Document 2692 is a single column
at `x0=72` with no margin at all, and its note and body share one block:
`5. Criminal misconduct.⸺ (1) A public servant is said to commit the offence…`.
The mechanism is recorded here as measured.

What the surviving citable section is made of, over retyped nodes of 500+ chars:

| the citable section | units | documents | released |
|---|---:|---:|---:|
| carries real text, just less than the buried sibling | 297 | 170 | 183 |
| one small block — a note or heading | 165 | 84 | 111 |
| **no text blocks at all** | **119** | 81 | 86 |

For the 119 that hold no text, the block the tree anchors them to is not a
section opener. Read directly, it is a **wrapped continuation or a footnote**:

    (2) In case the persons so nominated are minors, or subject…   a subsection
    Provided that as regards the five professors and the members…  a proviso
    fifteen days, unless there are exceptional circumstances…      a mid-sentence wrap
    1For Statement of Objects and Reasons, see Gazette of India…   a footnote

Document 2692's phantom `section 5` is anchored to block 234951 —
`1The Act has been applied to Baluchistan, see Gazette of India, 1947` — a
footnote at `y0=575` on the page *before* the real section. So the sequence is:

1. A fragment that is not a section opener acquires a section number.
2. The segmenter builds it as a **section** with no text under it.
3. The real body, arriving later with the same label, becomes a **second
   sibling**, demoted to `clause` (2692's carries role `schedule_row`).
4. S7 flags `repeated_sibling_label` and proposes `retype_non_citable`.
5. The adjudicator accepts, keeping the empty node and burying the body.

This is the footnote-and-continuation family already fixed in `_section_numbers`
by the `_is_furniture` filter, not the margin family. **The fix has landed; these
trees predate it and have never been replayed.** That matters for the repair: for
some share of these documents the correction is a replay, not a new decision.
How large a share is not yet measured, and is the next thing to measure.

## The pending queue has the same shape, and the proposal is wrong on it

All **1,035** pending S7 units are a single shape — `repeated_sibling_label`
proposing `retype_non_citable`. Applying that proposal wholesale, which is what
"resolve S7" is usually taken to mean, would repeat the defect: in **138 units
across 63 expressions** the candidate proposed for retyping carries an average
of **8.0 children and 1,978 characters** against the canonical's **0.6 children
and 195 characters**. Those need `restore_citable` or `reparent`, not
acceptance.

Only **21 expressions** have pending units that are *all* structurally safe to
retype (candidate childless, ≤200 chars, canonical substantial).

**963 of the 1,035 sit on documents that print no contents list**, so no
aggregate over contents rows can settle them — which is why this queue has not
moved.

## S10 passes vacuously

`v_active_boundary_candidate` holds **0** rows, so S10 reports PASS. But 34 of
the S7 expressions carry a dense run of repeated labels restarting at 1 and
topping out near 9 inside trees of ~29 sections — the signature of a second
instrument in the same file. **None of the 34 is flagged by the boundary
detector.** S10 is green because the detector is narrow, not because the corpus
has no unsplit compendiums. A criterion that passes without having looked is
worse than one that fails.

## What is not done here

No decision was written and no tree was replayed. All **8,518** S7 decisions in
the corpus are `accept_non_citable`; the schema admits `restore_citable`,
`reparent`, `split_instrument` and `reject_candidate`, and **none has ever been
used**. Superseding a decision is append-only and cheap; doing it before the
parser stops producing note-sections would only move the error. The parser fix
comes first, measured ON/OFF corpus-wide like every other change here, and the
superseding adjudications follow it.

## Applied: 20 documents replayed, 47 released stub citations repaired

`would_replay_fix_stubs` found 87 of the 369 stubs (23.6%) already parsed
correctly by today's segmenter, in 51 documents. `replay_cost` then measured
what replaying those 51 would cost the gate and refused 26 of them — the Sales
Tax Act 1990 at 164 → 71 sections, the Punjab Excise Act at 111 → 75 sections
and 7 → 60 gaps. Replaying to fix stubs without that check would have destroyed
more than it repaired.

Of the 24 it cleared, the worker's dry run showed four keeping S7 candidates
(3644 at 20 → 10, 2649 at 10 → 1, 2815 at 3 → 1, 3305 at 2 → 2), which would
block them. Those four are held. **The other 20 were replayed.** Every one:

* stayed in the release set,
* went to **0 pending S7**, retiring 101 collisions that no longer occur,
* lost no section, and three gained one — Sindh Ferries 20 → 22,
  Co-operative Societies 49 → 50, Evacuee Trust 32 → 33,
* held contents agreement at **1.0000** across all 18 that print a list.

`resolve_exact_instrument_duplicates --apply` then linked 99 byte-identical
revisions, as it must after any replay. Nothing was deleted; `duplicate_of`
links them and the release views count the expression once.

| | before | after |
|---|---:|---:|
| stub citations, all | 359 in 194 docs | **312 in 174 docs** |
| stub citations, released | 237 in 147 docs | **190 in 127 docs** |
| audit | 29/30, S7 the only FAIL | **29/30, S7 the only FAIL** |
| released expressions | 4,146 | **4,146** |

Verified on one by name. **Usurious Loans Act 1918, section 3** was a citable
node holding 0 characters while 4,223 characters of *Re-opening of
transactions* sat in a sibling nobody could cite. It is now a section, headed
*Re-opening of transactions*, with 17 children and 4,223 characters.

The remaining 312 are not a replay. They need the parser fix for phantom
sections anchored to footnotes and wrapped continuations, and then superseding
adjudications — in that order, because writing decisions first would only move
the error.

---

# Measured out: the footnote-run rule, and what it proved on the way

A footnote block is apparatus, and `_is_furniture` already says so — but it asks
two questions a long footnote run answers no to: is the block in the bottom
margin (a run starts high *because* it is long — the Prevention of Corruption
Act's page-2 run opens at y0 575 of 792), and does the block **start** with
amendment vocabulary (its first line is usually the one line without an
amendment verb). So `subdivide` hands markers 1–5 to the grammar as section
numbers, and the phantoms that follow are where the stub citations come from.

`_is_footnote_run` asked about the run instead: three or more numbered lines,
strictly ascending and distinct, at least two matching `_FOOTNOTE`. Unit-checked
against a real run (True), a contents list (False) and a body run (False).

Measured ON/OFF over all 4,596 documents: **314 documents moved, 23 improved,
5 REGRESSED.** `unlinked 1,928 → 1,785 (−143)` and `missing_toc 166 → 130 (−36)`
— the largest gains any change produced this session.

**It does not land.** `./nz diff-trees` named the 17 sections it removes, and
they are not all phantoms:

* **doc 3184 — correct.** Its 11 lost "sections" are Schedule rows: `Nil. Nil.`,
  `Plant, materials and stores for maintenance`, `Raw materials such as cotton,
  silk, jute`, `Other miscellaneous goods`.
* **docs 1856, 4379, 4489, 4501 — real law.** CrPC s.131 (`When the public
  security is manifestly endangered by any such assembly`), Income Tax Ordinance
  s.201, Succession Act ss.146 and 269, and two sections opening `It shall be
  lawful for the [Provincial Government]`.

The rule is right about every block it claims — each one read against source is
a genuine footnote run. The damage is downstream: `_section_numbers` feeds only
contents/boundary logic (five call sites, no separate tree-building consumer),
so excluding apparatus moves the body floor. In doc 3184 it moves correctly and
strips phantoms; in the other four it moves later and swallows real sections.

**The next attempt should not re-derive this.** The fix is not a narrower rule —
narrowing cannot separate these, because the rule is already correct. It is that
**the body floor must never move later because apparatus was excluded.** Compute
it both ways and take the earlier.

## What the regression check exposed: 3 of 4 gap counts were false

Chasing doc 3184's "regression" showed its contents entries were linked to the
wrong provisions entirely — the contents promise the Act's sections, the links
point at Schedule rows because the numbers matched:

| the contents promises | the link resolves to |
|---|---|
| `1 Short title, extent, commencement` | `1. Stores (including medical stores) for relief` |
| `2 Interpretation` | `2. Arms, ammunitions, stores and equipment of` |
| `5 Protection of action taken` | `5. Foods stuffs (tinned, canned, bottled…)` |

So its gap count of 3 was never true, and the 17 the rule exposes is the honest
number. Generalised with `./nz empty-citations`, over 82,229 linked contents
entries:

| the citation returns | entries | documents | released |
|---|---:|---:|---:|
| law | 73,465 | 3,082 | 59,157 |
| **nothing: no body text, no children** | **4,483** | 816 | 3,596 |
| **nothing: no body text beneath it** | **1,357** | 424 | 1,123 |
| **under 60 characters** | **2,145** | 679 | 1,762 |
| a disposition marker, correctly empty | 779 | 343 | 563 |

**7,985 citations in 1,344 documents return no law; 6,481 are released.** The
gap queue's 1,005 is a floor, not a total: it counts rows with no link and
cannot see a link that resolves to nothing.

## The mechanism: the body absorbed into the contents region

Document 3523 promises section 8, *Costs of determination of pollution level*.
The entry links to a `section 8` node on page 6 carrying **zero** blocks; the
Act's real section 8 is block 400551 on page 3, and its role is `contents`.

Document 3289 is the extreme. The **Pakistan Single Window Act, 2021** — 17
pages, released — holds **173 blocks of role `contents` spanning pages 1–14**
and **3 of role `body`, on pages 15–17**. Almost the entire Act is filed as its
own contents list. Nothing is lost (C4 and C5 both pass, every block is
assigned); nothing is citable either.

Seven released documents have fewer body blocks than pages while their contents
exceed their body:

| doc | pages | contents | body | |
|---:|---:|---:|---:|---|
| 2989 | 15 | 375 | 12 | Punjab Mining Staff and Workers Training |
| 3289 | 17 | 173 | 3 | Pakistan Single Window Act, 2021 |
| 1822 | 7 | 112 | 1 | Environmental Tribunal Rules, 1999 |
| 2087 | 8 | 96 | 4 | Irrigation and Drainage Authority Rules |
| 2534 | 12 | 85 | 10 | KP Promotion, Protection… |
| 3960 | 38 | 23 | 14 | West Pakistan Repealing Ordinance, 1970 |
| 4422 | 77 | 19 | 17 | Punjab Lands Improvement Tax Act, 1975 |

## Retracted: 14,302 "disagreeing" contents links

A first pass compared each entry's printed heading against its linked node's
text with `similarity()` and reported 14,302 disagreements. **That number is an
artefact and is withdrawn.** This corpus drops `s` characters in many documents,
so `Treasurer.` extracts as `trea urer` and trigram similarity collapses on
correct links. `Acting Vice Chancellor` scored below threshold against a node
reading `acting vice chancellor 12 acting vice chancellor`. Sampling caught it.
The structural test above replaces it and cannot be reached by that artefact.

---

# S7 is a parser-repair queue, not a decision queue

This was assumed for most of the session and is worth stating with the view
that settles it. `v_structural_adjudication_pending` is:

```sql
  FROM v_active_structural_candidate c
  LEFT JOIN v_structural_adjudication_latest a ON a.candidate_id = c.id
 WHERE a.id IS NULL OR a.resolution <> 'accept_non_citable'
```

A candidate stays pending unless its resolution is **`accept_non_citable`**.
So `restore_citable`, `reparent` and `split_instrument` clear nothing: they
record that the demotion was wrong and leave the instrument blocked until the
tree is actually repaired. `v_release_instrument` blocks on that same view, so
the gate cannot be opened by declaring a defect — only by fixing it or by
accepting the demotion as correct.

That is the right design, and it explains why the queue has not moved. Run
`./nz s7` against the 1,035 pending:

| verdict | units | docs | what it needs |
|---|---:|---:|---|
| inverted | 207 | 73 | `restore_citable` — **parser fix, then replay** |
| nesting | 178 | 39 | `reparent` — **parser fix, then replay** |
| compendium | 66 | 3 | `split_instrument` — **S10 split, then replay** |
| probably-correct | 137 | 47 | `accept_non_citable` — a decision can close these |
| unclear | 447 | 120 | source review |

**Only 137 of 1,035 are closable by decision at all**, and the stub guard added
to `adjudicate_citation_preserving` refuses the subset of those whose candidate
carries the law. The other 451 need the parser to stop producing the collision;
a decision on them is a note, not a resolution.

This is confirmed in practice. The 20 documents replayed today carried 115 S7
decisions between them; after replay **101 of those collisions no longer occur
at all** and every one of the 20 went to 0 pending. No adjudication was written.

So the route to S7 = 0 is: fix the parser, replay what the fix improves, and
reserve adjudication for the residue. Not 1,035 decisions.

## What that means for the 41 acquisition exceptions

Nothing — that queue is closed and was closed before this session. Verified
again on the record: **40 declared exceptions, 0 unresolved.**

| reason | count |
|---|---:|
| catalogued URL no longer resolves | 28 |
| served content is not a PDF | 8 |
| no PDF URL catalogued | 2 |
| portal rejects the request | 1 |
| no English PDF published | 1 |

C1 passes at 0 unstored / 0 unsourced. The "41" in earlier notes was the queue
size when that work started, not a standing figure; 14 items were recovered by
refetch and 1 by an alternate official copy.

---

# Retracted: "176 of 192 S7 documents clear by replay"

That claim, recorded earlier today in `would_replay_clear_s7` and its commit,
is **wrong by two orders of magnitude** and the tool is deleted.

The tool segmented each document with today's parser and counted sibling groups
sharing a citation label, treating zero as "the collision is gone". But an S7
candidate is recorded at the moment the segmenter **demotes** one of the pair:
`inst.structural_decisions` is written as the tree is built, and the finished
tree therefore never holds two siblings with the same label. The tool was
counting the residue of a resolution, which is always zero. It measured nothing
and reported everything.

The segmentation worker already answers this correctly, and has all along —
`--dry-run` prints `S7=before->after` per document. Over the same 175:

| | documents |
|---|---:|
| S7 unchanged | **159** |
| S7 increases | 8 |
| S7 reduces | 5 |
| S7 clears to 0 | **3** |

and two of those three shed sections doing it (4244 at 142 → 20, 4473 at
106 → 26). **One** document clears without loss.

So the earlier conclusion is withdrawn with it. The S7 queue is **not**
mostly stale trees. The 20 documents replayed this morning were real — their
collisions did cease to exist, verified against the same worker output — but
they were selected as stub-citation repairs, and they do not generalise.

What stands from that section is the part the release view proves rather than
the part this tool measured: S7 remains a queue where only `accept_non_citable`
clears a unit, so 451 of the 1,035 need a parser fix rather than a decision.
How many of those fixes already exist is now **unknown again**, and the honest
instrument for finding out is `nizam.workers.segment --dry-run`, not a
reimplementation of its detector.

**The lesson, twice today.** This is the second count retracted in one session
— the first was 14,302 "disagreeing" contents links, an artefact of the
missing-`s` extraction defect. Both were caught the same way: by checking a
sample or a second instrument before acting on the number. Neither reached the
database.

---

# The weighted 200-decision audit, re-run and read

The goal names this component, so it is verified here rather than assumed.

**It exists and is cited.** `./nz s7-audit` draws 200 decisions from the 4,498
made by `nizam.structural_adjudicator/1`, weighted toward large sibling groups.
**3,758 of the 8,518 recorded decisions cite it by name in their rationale** —
3,747 from `nizam.citation_preserving_review/1` plus 11 carried by exact tree
revision. Re-run today it reports the same shape it did in September:

| verdict | n | share | meaning |
|---|---:|---:|---|
| **WRONG** | 53 | **26.5%** | the law was demoted and a heading kept in its place |
| SUSPECT | 32 | 16.0% | compendium — demoting is the wrong repair regardless |
| unclear | 58 | 29.0% | needs a person to read the page |
| not-law | 20 | 10.0% | both blocks are footnotes |
| right | 37 | 18.5% | the kept block does carry the provision |

The tool itself prints `HEURISTIC FLAG RATE (NOT SOURCE-AUDITED)` and says to
render and read before quoting an error rate. Five pages were rendered and
read. **This is a five-page reading, not a re-audit of 200**, and is recorded
with that limit.

| page | what the source prints | verdict |
|---|---|---|
| doc 3892 p48 · Sind Co-operative Societies Act 1925 | an **eight-line footnote run**, `1. Cls. (cca), (ccb) and (ccc) ins. by Sind 20 of 1947` … `8. Cl. (mm) … renumbered as cl. (gg)` | WRONG **supported** |
| doc 3825 p24 · a canal Act | a **seven-line footnote run** whose first line carries no amendment verb — `1. This Act. has been repealed to the Khyber Pakhtunkhwa…` — then six `Subs.` lines | WRONG **supported** |
| doc 2366 p20 · W.P. Land Preservation Act | right-margin marginal notes plus a footnote run `1/2/3` at the foot | WRONG **supported** |
| doc 4451 p230 · Customs Act 1969 | an **entire page** of footnotes numbered 40–54 | mechanism **confirmed** |
| doc 4460 p15 · Punjab Pure Food Rules 2011 | a food-colour schedule; label 2 is the table row `Loss on drying at 135°C … 13` | **false positive** |

**Four of five show footnote apparatus standing where a section should be.**

So the claim carried in the rationale of 3,758 decisions — that reading
"corrected the length heuristic that had flagged 26.5% as wrong", the long
demoted block being "almost always a schedule list, a table row or a page
footnote" — is **too strong**. Schedule rows do produce false positives, and
doc 4460 is one. They do not dominate. In this reading the dominant mechanism
is the footnote run, and the block kept as the section is the footnote.

That is the same defect as the stub citations, reached from a third direction,
and its repair landed today: `_is_footnote_run`, measured over 4,596 documents
at unlinked 1,928 → 1,781 and missing_toc 166 → 126.

The 3,758 decisions are **not** rewritten. They are append-only and a
superseding adjudication is the right instrument — after the parser stops
producing the phantoms, not before, or the error only moves.

Full reading in `/mnt/e/nizam-data/s7-audit/RESULT-2026-09-14.md`.

---

# The gap queue is 99.3% parser defect, and reading proved even the residue wrong

The goal asks for the TOC-gap queue to be closed **with source evidence**. The
source evidence says most of it cannot be closed by a disposition at all.

`review_absent_sections` selects the gaps where the section is plausibly not in
the source, on two machine checks that both rest on C5 = 0 (every character of
every PDF is in a `text_block`, so the raw blocks are searched rather than the
tree, which is the thing in question):

1. the promised heading, normalised and at least 12 characters, appears nowhere
   in the document outside the contents list's own blocks, **and**
2. the promised label never opens a body block either.

Run over the whole queue it returns **7 candidates in 6 documents** — out of
**1,005 pending gaps**. Every other gap fails one of those checks, which means
the section *is* in the source and the tree cannot see it. **99.3% of the queue
is a parser defect, not an absence**, and a disposition on any of it would be a
lie in exactly the way `review_toc_gaps` warns about.

## And then the residue did not survive reading either

Only one of the 7 was short enough to render in full: document 3606, the
Coastal Development Authority (Accounts, Works, Property and Record) Rules
1999, whose contents promises `23. Works Registrar.` Both checks passed. Page 8
prints:

```
22.(1) If any work is executed departmentally ...      [Works to be executed
                                                        departmentally.]
23(1). Unless a work is of urgent nature is to be      [Works executed by
       executed through the agency of any Department    contract.]
       of Government ...
24.(1) Every work executed whether departmentally or   [Works Register.]
       by contract shall be measured ...
```

Rule 23 is printed in full. Check 2 missed it because the number is fused to
its first subsection — `23(1).`, the period after the bracket — while `24.(1)`
three lines below is the form the grammar knows. **`absent_in_source` on that
row would have been false**, and the check that would have licensed it is
blind to precisely this shape.

The contents is also misaligned against its own body: `23. Works Registrar.`
matches the margin note printed at rule **24** (`Works Register.`). Document
1014, the Sind (Teaching, Promotion and Use of Sindhi Language) Act 1972, shows
the same off-by-one — its contents promises `8. Power to make rules.` while the
body prints that provision as section **7** and stops there. In both, the
stored headings come from the contents by label, so every heading after the
divergence names the wrong provision. `marginal_note` is populated on only 7
sections corpus-wide, so this cannot be measured without reading pages.

## The repair, found by reading

`_classify_body` requires a period immediately after the number:

    "24.(1) Every work executed whether departmentally"  -> section 24
    "23(1). Unless a work is of urgent nature"           -> None
    "23 (1) Unless a work is of urgent nature"           -> None

290 blocks in the corpus open this way, 232 of them already carrying role
`body`, and **16 pending gaps across 16 expressions** promise a label whose
block opens like that. The rule added is deliberately narrow, because `23(1)`
is also how a cross-reference is written: the subsection must be **(1)** — a
section opens at its first, never its fourth — the match must be at the very
start of the block, and the label must be one the contents promises.

Measured ON/OFF over all 4,596 documents before it lands, like every other
change here.

## Defect class 3: the contents numbers the preamble, so every link is one off

Found by reading document 306, the Sindh Disposal of Urban Land (Repeal) Act
2005 — a two-section Act whose single gap promises `3. Repeal of Sindh
Ordinance X of 2002.` Page 1 prints a real contents list:

```
1. Preamble.
2. Short title and commencement.
3. Repeal of Sindh Ordinance X of 2002.
```

and page 2 prints the body as **1.** Short title and commencement, **2.** Repeal
of Sindh Ordinance. The publisher numbered the preamble, so the printed contents
sits one ahead of the printed body. That is a property of the source, not a
parse error.

What the parser did with it is the defect. `match_method` for all three rows:

| contents entry | linked to | |
|---|---|---|
| 1 · Preamble. | section 1 · Short title and commencement | **wrong** |
| 2 · Short title and commencement. | section 2 · Repeal of Sindh Ordinance | **wrong** |
| 3 · Repeal of Sindh Ordinance | — | the gap |

**The gap is the visible symptom; two silently wrong links are the damage.** A
citation rendered from entry 1 would return the wrong provision, and no gate
sees it — the gap queue counts only the third row.

The cause is in `toc_node`. Its strongest path returns a match on label alone
when exactly one body provision carries the citation key, with **no heading
corroboration**:

```python
if (len(primary) == 1 and toc_key_counts[citation_key] == 1 and ...):
    method = "label" if exact_typography else "label_typography"
    return primary[0], method
```

Requiring a heading there is not the fix, and the file already records why:
doing so left "240 rows that had matched by plain `label` unmatched, taking 56
instruments out of the release view". Body sections frequently do not repeat
their marginal note in their text, so heading agreement fails on correct
matches as readily as wrong ones.

The fix has to be **document-level**: detect that the whole contents list is
offset — the first entry is apparatus, the entry count exceeds the section
count, and shifting by one raises total heading agreement — then shift, rather
than judging each row alone.

Scale, measured over the 182 expressions blocked by exactly one gap:

| shape | expressions |
|---|---:|
| off-by-one, one extra entry and the gap is the **last** row | **36** |
| one extra entry, gap elsewhere | 61 |
| contents longer than the body | 18 |
| other | 67 |

and separately, **11 expressions print a contents list whose first entry is
`Preamble`** — **10 of those 11 carry a pending gap**, a 91% hit rate that
confirms the mechanism, with 126 already-linked entries at risk in them.

Document 1014 is the same shape from a different cause: its contents lists
`3. Constitution of Governing Body.` which the body does not print, so entries
4 through 8 all sit one ahead, and its gap on `8. Power to make rules.` is the
provision the body prints as section **7**.

## Applied: the fused-subsection rule, and the first gap closed by reading

The rule landed after an **exhaustive** check rather than a sample. Only five
documents in the corpus hold a block it can match, so it provably cannot touch
anything else; all five were diffed. Three unchanged, two gained a section,
none lost one.

Replayed:

| | before | after |
|---|---|---|
| doc 3606 · Coastal Development Authority Rules | 34 sections, 1 gap, **blocked** | 35 sections, 0 gaps, **RELEASED** |
| doc 2973 · Offence of Qazf (Enforcement of Hadd) Ordinance | 19 sections, 1 gap, blocked | 20 sections, 0 gaps, blocked on S7 |

Rule 23 of the Coastal Development Authority Rules, *Works Registrar.*, is now
a citable section carrying 295 characters. It is the gap that
`review_absent_sections` proposed recording as **absent from the source** — the
reading is what stopped that, and the rule is what fixed it.

Document 2973 gained section 6, *Proof of qazf liable to hadd.*, and closed its
gap, but the replay recreated an S7 candidate, so it moves from blocked-on-gap
to blocked-on-S7. Better tree, same release state.

| | before | after |
|---|---:|---:|
| released expressions | 4,146 | **4,147** |
| contents gaps | 1,005 | **1,003** |
| S7 units | 1,035 | 1,036 |

**Still wrong in document 3606, and recorded rather than hidden**: its stored
headings remain offset by one. Rule 22 carries `Works executed by contract.`,
which page 8 prints beside rule **23**. That is defect class 3, found today and
not yet fixed — the section numbers and text are right, the headings name the
neighbouring provision.

---

# A batch replay that was not worth it, and why the filter selects against the fix

The footnote-run rule measured `unlinked 1,928 -> 1,781` across the corpus, but
a fingerprint is not a tree: the gain exists only after the documents are
replayed. So all 339 gap-blocked documents were put through `./nz replay-cost`
against the new parser, 271 came back safe, the worker's dry run showed **0
sections lost and 96 gained**, and the 252 with no new S7 candidates were
replayed. 260 instruments rebuilt, 0 failed.

The result was close to neutral, and one part of it was a mistake:

| | before | after replay | after adjudication |
|---|---:|---:|---:|
| released expressions | 4,147 | 4,147 | **4,147** |
| contents gaps | 1,003 | 1,000 | **1,000** |
| S7 units | 1,036 | **1,337** | **1,074** |
| expressions S7-blocked | 212 | 265 | **231** |
| citable sections (released) | 80,551 | 80,586 | **80,586** |

**The mistake**: the dry run reports S7 candidate counts per document, and 19
documents whose count would rise were excluded. But a replay gives every
candidate a **new provision id**, so previously *decided* candidates return as
undecided — `carried_by_exact_tree_revision` fires only on a byte-identical
tree revision, and these trees changed by design. 301 units went from decided
to pending. Re-running the citation-preserving adjudicator, now carrying the
stub guard, took 263 of them back on freshly-parsed trees, leaving a net **+38
units and +19 blocked expressions** against **−3 gaps and +35 citable
sections**.

**The deeper reason the yield was small** is worth more than the arithmetic.
`replay_cost` filters on what the gate counts — sections lost, gaps gained —
and the documents where the footnote fix helps most are exactly the ones it
refuses, because their honest gap count *rises* when phantoms are removed:

| refused by replay_cost | what it actually does |
|---|---|
| doc 2225 · Agricultural Produce Act 1937 | 27 phantom "sections" (`Fruit.`, `Eggs.`) → 6 real ones; gaps 2 → 0 |
| doc 4088 · KP Civil Servants | 42 → 33 sections, gaps 1 → **0** |
| doc 3184 · Railways (Transport of Goods) Act | 11 Schedule rows removed, gaps 3 → 17 (the honest number) |
| doc 3867 · Punjab Excise Act | 111 → 83 sections, gaps 7 → 8 |

So the batch replayed mostly documents where the parser produces the same tree,
and skipped the ones carrying the improvement. **A gate-based filter cannot
select for a fix whose effect is to make the gate's own number truer.** Those
documents need reading one at a time, which is what the rest of this file has
been doing.

Nothing was lost: C4 and C5 both still report 0, the audit is unchanged at
29/30 with S7 the only FAIL, and no provision, block or revision was deleted.

---

# The gap queue has no large tractable class left

Three parser fixes were found by reading pages today and were worth 2, 5 and 16
gaps against a queue of 1,000. `./nz gap-causes` was built to rank the classes
before spending another turn that way. After three corrections to its own
classification, over 958 pending gaps:

| class | gaps | share | |
|---|---:|---:|---|
| heading_only | 304 | 31.7% | **not a defect class — see below** |
| absent | 223 | 23.3% | neither label nor heading outside the contents |
| period_other | 178 | 18.6% | label matches a schedule row, heading does not |
| anywhere_at_start_other | 75 | 7.8% | |
| periodless_other | 68 | 7.1% | |
| period_nohead | 23 | 2.4% | heading too damaged to corroborate |
| **period** | **19** | **2.0%** | **printed plainly, heading agrees, tree missed it** |
| bracket_amend | 16 | 1.7% | |
| the rest | 52 | 5.4% | |

Three corrections were needed to get there, and each shrank the number that
looked actionable:

1. **Heading agreement required.** `period` first read 228. Document 1117's
   contents promises section 12 *Consequences of de-registration* while its
   Schedule prints `12. Welfare of the aged and infirm.`; taking the first block
   carrying the label called that "found". 228 → 52.
2. **Uncorroborated headings named.** A heading of `* * * *.`,
   `................` or `11l` cannot corroborate anything, and calling those
   corroborated kept them in `period`. 52 → **19**.
3. **heading_only is an artifact.** "Outside the contents" is decided from
   `provision_block.role`, and a contents list whose rows never linked has no
   role row, so it defaults to unassigned and reads as body. Document 308's
   page-2 list — `35. Acquisition lands.`, `36. Contract water and water
   rates.`, `38. Preferential treatment.` — is its own contents, counted as
   headings printed in the body. Two attempts to separate them, on
   `source_block_id` and on the run's `body_starts_page`, left it at 304.

**A parser change was written for heading_only and measured against all 138 of
its documents with `./nz diff-trees`: 0 sections gained, 0 lost, on every one.**
It is reverted.

And the 19 that survive every filter mostly parse correctly already. Tested
directly, `classify` reads `14.Information acquired to be confidential.___(1)`,
`128[6-A. Furnishing of statement in Form A.I.T. 5-A` and `133[7. Best judgment
assessment.-` as sections 14, 6-A and 7. Their gaps come from context — a
boundary, a parent, a seen-set — not from the grammar. The one genuine grammar
defect among them, `13. 1 The 2[Chairperson]` parsing as label `13. 1` because
a superscript marker is absorbed, appears in **5 blocks and one pending gap**
corpus-wide.

## What this means for the goal

Closing the TOC-gap queue was the first named component of this work, and the
honest position is now measurable rather than asserted: **it cannot be closed by
parser fixes at scale, and it cannot be closed by dispositions either.**

* `review_absent_sections` offers **7 candidates out of 1,000**, and reading the
  only fully-renderable one showed the rule *was* printed — so dispositions are
  not the route.
* No remaining defect class is worth more than ~20 gaps, and the largest-looking
  one was an artifact of the measurement.

What remains is a long tail: contents lists that do not correspond to their
body, labels that coincide with schedule rows, forms and wildlife schedules
promising entries no body section answers, and genuinely absent sections. Those
need per-document reading, at a scale of several hundred documents, and each
reading settles one expression. The rendering for all 1,005 is now in place and
indexed, which is what that work needs.
