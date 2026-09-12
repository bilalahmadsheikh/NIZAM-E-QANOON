# An amending Act's sections read exactly like amendment footnotes

*Found and fixed 11 September 2026. Closes the C5 failure; measured over 1,599
documents.*

## The defect

An amending Act states its amendments as its own operative sections:

```
4.  In section 15 of the said Act, for the word and figures "and 24" the
    figures, word and letter "24 and 24-A" preceded by a comma, shall be
    deemed to be substituted.
```

That is the section. It is also, character for character, the shape of the
apparatus `_PUNCTUATED_AMENDMENT_FOOTNOTE` exists to catch — a note *about* an
amendment, which must never become a section. The pattern cannot tell them
apart from the text alone, and it was claiming the operative one.

The damage was not only a missing section. In these statutes the section's
heading prints in a narrow marginal column as its own block:

```
ord 649  x0=501  "Amendment of section 15."      ← the marginal heading
ord 650  x0= 86  "4. In section 15 of the …"     ← its section, taken as apparatus
ord 651  x0=501  "Amendment of section 17."      ← heads section 5, attaches fine
```

With its section demoted, the marginal heading had no provision to attach to.
`segment()` leaves such a block as `("heading", None)`, and
`legal_write.save()` — correctly — refuses to store a heading that owns
nothing, so it lands as `unassigned`. That is the C5 defect counter, and one
27-character block was enough to fail the gate.

Two details made this hard to see, and both are worth remembering:

- The **worker** downgrades only `role == "body"` with no node, while the
  **writer** also downgrades `heading`, `schedule_row` and `preamble`. A ledger
  that looks clean in `build()` can still store an unassigned block.
- `classify()` read the block correctly as `('section', '4', …)` throughout. The
  demotion happened in the body walk, not in classification, so reading
  `classify()` alone suggested nothing was wrong.

## The fix

Before the walk, `segment()` already matched that marginal heading to the
printed contents entry for the same label and proved it prints in its own
column — that is what `detached_heading_for_body` records. Where that evidence
exists, it outranks the text shape:

```python
if ((_FOOTNOTE.match(text)
        or _PUNCTUATED_AMENDMENT_FOOTNOTE.match(text))
        and b.get("id") not in detached_heading_for_body):
    mark(b, "footnote")
```

The guard is deliberately narrow. It does not claim that every block reading
"In section N of the said Act" is operative — only those the parser has already
tied to a printed contents heading in a separate column. An amending section
with no marginal heading, or in a document that prints no contents, is still
demoted; there is no evidence to prefer, and guessing is what the corpus rules
forbid.

## Measured

Every document containing a block that matches either apparatus pattern —
1,599 documents, 21,992 blocks, the exactly-necessary condition — was segmented
both with and without the guard and the results compared field by field.

**Eight documents move. All eight improve. Nothing regresses.**

| | before | after |
|---|---:|---:|
| sections | 24 | 43 |
| provisions | 877 | 898 |
| contents entries unmatched | 23 | 2 |
| blocks left unplaced | 30 | 0 |
| characters left unreachable | 617 | 0 |
| blocks held as apparatus | 65 | 44 |

Documents 19, 94, 114, 129, 145, 161, 3630 and 3901. After replay, seven of the
eight print a contents list that agrees exactly (1.0000).

## What the replay also removed, and why that is right

Replaying these documents carried the rest of the segmenter's accumulated
changes with it, and two documents ended with *fewer* sections. Both losses are
apparatus that had been masquerading as law:

- document 19 lost section `1278` — a fused superscript footnote marker read as
  a section number;
- document 114 lost section `1126`, headed *"This Act was passed by the W.P…"* —
  the assent note.

No text left the corpus. C4 and C5 both read zero: those characters are still
stored, still reachable, now under the `footnote` role where they belong. This
is the same defect class the S7 audit identified — apparatus becoming sections —
repaired at its root rather than adjudicated away afterwards. S7's pending queue
fell from 2,345 to 2,332 as a side effect, and document 3901 alone went from 32
structural candidates to 1.

## Audit position

C5 returns to 0 and the corpus audit stands at **29 of 30**, S7 the only
remaining failure.
