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
