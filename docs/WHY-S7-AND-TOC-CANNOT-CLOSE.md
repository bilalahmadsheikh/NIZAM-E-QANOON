# What is left in S7 and the contents-gap queue, and why

> **Current correction, 15 September 2026, 13:37 UTC:** this document records a historical investigation, not an exhausted repair path or today's policy blocker. Owner-approved migration **0050** admits explicitly evidenced assistant page review separately from human review. Source-backed append-only parser repairs now make **4,198** instruments releasable; **935 TOC gaps / 885 S7 units** remain, and the audit is **29/30**. New documents 1927/2960/3485/4495/4235 have zero pending TOC/S7 and verified source preservation. The original weighted 200-case audit remains incomplete (28 cases reported read). See [current status, proof and held table defects](CORPUS-READINESS-2026-09-15.md); the earlier “wall” is not grounds to declare source-backed repairs impossible or to invent a human-review flag.

*12 September 2026. Written after exhausting the automatic routes, so the next
person does not repeat the search.*

Two queues remain open: **S7 at 2,161 units in 250 observations**, and the
**contents-gap queue at 1,283 entries**. Both are blocked on the same thing, and
it is not effort. This records every signal that was tried and what it returned,
so the remaining work is understood rather than re-derived.

## S7 — every available signal, and what it gave

| signal | result |
|---|---|
| **Citation preserved** — after the demotion, is the label still reachable as a section of the same instrument? | Exact, whole-population: **0 of 6,522 demotions remove a citation.** Necessary, but not sufficient — document 16 keeps "label 2" citable while keeping the wrong one of two. |
| **Printed contents heading** — does the kept occurrence match it at least as well as the demoted one? | Separates 442. **No candidate anywhere has the demoted occurrence matching better**, so nothing in the corpus says the wrong one was kept. Unavailable for 1,494 candidates whose document prints no contents at all. |
| **Contents silence** — the document prints a contents list and this label is absent from it | 49 more. The source saying the unit is not a promised section. |
| **Printed marginal note** — a section in a two-column statute carries one; a table row does not | **Empty.** All 2,161 have no marginal note on either side: the column is only populated by the gated fusion split, so it cannot speak here. |
| **Structural parentage** — is the demoted unit under a schedule, form or appendix? | **Empty.** All 2,161 sit under `instrument`, `part`, `chapter` or `appendix`, all with `same_parent: true`. No candidate has schedule parentage. |
| **Block role** | Circular. The demotion itself writes `schedule_row`; the role is the decision's consequence, not evidence for it. |

1,373 decisions were recorded on the two signals that do discriminate. What
remains has **no independent evidence in the corpus, in either direction**. That
is not a gap in the search; it is the answer the search returned.

## The contents-gap queue — the same shape

The 1,283 were triaged in full (`./nz cluster`, `tools/triage_toc_gaps.py`):

| | gaps | |
|---|---:|---|
| label already a section — the link was lost | 111 | 15 restored by exact-label overlay; the rest fail its ambiguity or ordering guards |
| heading names one other provision — contents numbered differently | 14 | **9 closed** as `found_elsewhere`; extended to match `marginal_note` too, then **0 further candidates** |
| section lives in a sibling instrument | — | **measured across the whole queue: 0 qualify** |
| label exists but only as a demoted clause | 249 | recording `found_elsewhere` would close the gap while the provision is not citable as a section — that would hide the defect |
| neither label nor heading anywhere in the tree | 932 | `absent_in_source` |

## One more theory, measured and ruled out

Document 306 prints no contents page at all. The parser enumerated its three
marginal notes -- "Preamble.", "Short title and commencement.", "Repeal of Sindh
Ordinance X of 2002." -- as entries 1, 2 and 3, so every section it "promised"
was a promise the source never made, and the unmatched one became a gap. Its
tree still carries the damage: section 1 is headed "Preamble.", section 2 "Short
title and commencement.", each one provision late.

If that were common it would explain much of the queue, so it was measured. A
genuine contents list prints in the body column; marginal headings print in the
margin. Comparing every contents entry's own source block against its document's
column geometry:

| | documents | pending gaps |
|---|---:|---:|
| contents entries print in the body column -- a real list | 3,080 | **1,280** |
| mixed -- some entries are marginal notes | 1 | 3 |
| almost all entries are marginal notes -- phantom list | 0 | 0 |

**1,280 of 1,283 gaps are in documents with a real contents list.** The promises
are real; the sections behind them are what is in question. Eight instruments do
carry the preamble shift (all have section 1 headed "Preamble."), and their
headings are wrong by one, but that accounts for 7 gaps, not the queue.

## A false alarm, recorded so it is not raised again

One more theory: that contents headings are assigned to body sections without
checking they fit, so the document 306 shift is general. Testing it with
`_heading_supports(text, heading)` returned **96.6% of 60,432 sections
"unsupported"**, which would be alarming if it meant anything.

It does not. That helper tests whether a block's words continue INTO a heading;
it is not a fit test. The sections it flags are correct: section 1 headed "Short
title and commencement" over "(1) This Act may be called...", section 2
"Definitions" over "In this Act, unless there is anything repugnant...". A
marginal-note statute never repeats its heading in the body text.

There is no general heading-misassignment defect. The preamble shift is confined
to the 8 instruments its own signature finds.

## A contents-parser fix that had to be reverted

Reading pages showed two shapes that clearly are not section promises: a
four-digit year read as a label (20 entries in 18 documents -- the long title,
the assent note, "(W. P. Ord. No. XXXII of 1960)", "(See Section 3)") and a
heading that is only punctuation (15 entries in 6 documents; one is a lone "]").

Suppressing them in `_toc_source_entries` made the corpus **worse by 1,002
gaps** across 75 documents, and the whole-corpus check is the only reason that
was caught. The cause is at segment.py's `unresolved_labels` computation:

```python
represented_labels = {entry["label"] for entry in resolved_entries ...}
unresolved_labels.update(promised - represented_labels)
```

`promised` comes from the `toc` label map; `represented_labels` from the entry
ledger. Dropping an entry from the ledger without also dropping its label from
`toc` converts it from a resolved row into a MISSING one -- precisely backwards.

A correct version must remove the label from `toc` as well, at the point the
contents map is built, not in the evidence ledger downstream. That is a more
delicate change and was not attempted.

Worth recording separately: the year guard was a no-op by construction. It
tested `highest_numbered <= 500`, but the bogus year is itself among the
candidate numbers, so the maximum is always at least that year. Its unit test
passed with the guard removed, which is the tell.

## The wall, stated exactly

`absent_in_source` is the only resolution left for the dominant bucket, and
migration 0042 constrains it:

```sql
-- A claim that the official source omits a promised section is a human
-- page-reading result, not a parser inference.  Store both facts so a
-- future bulk tool cannot silently manufacture these decisions.
CHECK (resolution <> 'absent_in_source' OR
       (evidence @> '{"human_page_review":true}'::jsonb
        AND evidence ? 'render_artifact'))
```

Pages **were** rendered and read — `tools/review_toc_gaps.py` exists for exactly
that, and reading found three categories nobody had named, including a document
whose contents list is a running header and a document whose marginal headings
are all shifted one provision late. Those readings are recorded as
`parser_defect`, which needs no such flag.

But `parser_defect` deliberately does not close a gap: the view keeps it,
because only a corrected parse resolves it. And an assistant reading a render is
not a human page review. Writing `human_page_review: true` would put a false
statement in the column whose entire worth is that it is true — which is the
exact act the constraint was written to prevent.

## What would close them

1. **A person reads the pages.** `./nz toc-review` renders batches and records a
   sha256 for each. The reading is set up; the categories above make most of it
   quick.
2. **Or the schema gains an explicit `assistant_page_review`**, distinct from
   human review and still requiring a render and its hash. This is a real change
   to what ships — `v_release_instrument` excludes instruments with pending
   gaps, so admitting assistant review releases instruments on weaker evidence
   than the schema currently demands. It is a decision for the project's owner,
   not a tidying step.

Both queues are fully triaged and every remaining entry is classified by what is
actually wrong with it. Nothing here is unknown; it is undecided.
