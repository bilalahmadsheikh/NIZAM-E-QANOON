# The mining series is one mechanism, not sixteen repairs

Read and measured 18 Sep 2026, while working the corrected `label-disagrees-with-first-block`
queue.

## What is wrong

`_repair_label()` in `nizam/corpus/segment.py` exists to undo superscript fusion: PyMuPDF glues
a footnote marker to the number after it, so section 366 carrying footnote 1 arrives as `1366`.
The contents list is the arbiter — if the label as read is absent from the contents but the label
with its leading digits removed is present, the leading digits were a marker.

That test is sound when the contents is speaking. **It is vacuous when the contents is nearly
empty**, because `1` is in essentially every contents list. Then every number ending in 1 finds a
match and is stripped to `1`:

```
toc = {"1"}                       # the degenerate case
_repair_label("11")  -> "1"
_repair_label("21")  -> "1"
_repair_label("101") -> "1"
_repair_label("121") -> "1"
_repair_label("12")  -> "12"      # unaffected: "2" is not in the toc
```

Only numbers ending in 1 collapse, which is exactly the signature observed.

The block-start classifier is **not** at fault. `segment.classify()` reads every one of these
openers correctly in isolation — `11.`, `21.`, `31.`, `51.`, `61.`, `71.`, `91.`, `101.`, `121.`
all return their true label. The label is correct when created and overwritten afterwards.

## What it did to two released mine-safety codes

| document | instrument | provisions labelled `1` | regulations lost |
|---|---|---|---|
| 4330 | COAL MINES REGULATIONS, 1926 | 9 | 11, 21, 31, 61, 71, 91, 101, 121 |
| 4122 | Metalliferous Mines Regulations, 1926 | 7 | 11, 21, 31, 51, 61, 71 |

Confirmed from rendered pages 6 and 30 of document 4330, twenty-four pages apart: page 6 prints
regulations 4–13 and page 30 prints 90–101, and the provisions stored under label `1` hold
regulation 11, regulation 91 and regulation 101 word for word.

The recognised contents for these documents is not a contents list at all — 4 entries for 4330
(`1, 42, 86, 123`) and 3 for 4122 (`1, 41, 89`). That is the degenerate case above.

## The single fix

> **Never strip a label down to a value already assigned to an earlier provision of the same
> instrument.**

Stripping to an already-used label cannot be a repair: it manufactures a duplicate, which is the
precise thing that makes law uncitable. The function already takes a `seen` set and already uses
it for one narrow case (`int(key) == max(numeric_seen) + 1`); this generalises that instinct to
every strip depth.

Tested against the mining series and against the repairs the function exists for — **9 cases,
0 mismatches**:

| case | today | with the guard | wanted |
|---|---|---|---|
| reg 11, toc `{1}`, `1` already seen | `1` | `11` | `11` |
| reg 21 | `1` | `21` | `21` |
| reg 101 | `1` | `101` | `101` |
| reg 121 | `1` | `121` | `121` |
| reg 121 with the stored toc `{1,42,86,123}` | `1` | `121` | `121` |
| `1366` → 366, 366 unseen | `366` | `366` | `366` |
| `1500` → 500, 500 unseen | `500` | `500` | `500` |
| CPC `125` → 25, 25 unseen | `25` | `25` | `25` |
| Sindh mining `21` stays 21 (wide hole in contents) | `21` | `21` | `21` |

Reproduce with `.pm3.py` (the mechanism) and `.pm4.py` (the guard).

## How far the one guard reaches

Released sections whose label is a truncation of their own printed opener **and** is duplicated
inside the instrument — the population this guard repairs:

**52 sections across 32 instruments in 32 documents.**

The mining pair is 14 of the 52. The rest is a long tail of one- and two-row instruments, among
them document 3386 labels 5, 7 and 8 — which I read independently in the withheld-accepts work
and confirmed to be sections 45, 47 and 48 of the Hyderabad Development Authority Act. That
independent confirmation is worth noting: the signature finds real defects, not a pattern in the
noise.

A further **132 sections in 49 instruments** carry the same truncation shape but with a label
that is *not* duplicated. The guard deliberately leaves those alone — it only refuses strips that
create a duplicate. They need the contents-quality test below, and they have not been read.

## A second guard worth considering, not yet measured

The root cause is that a 3- or 4-entry contents was trusted as an arbiter. A minimum-evidence
test — refuse to use the contents for label repair when it holds fewer than, say, 5 entries, or
when its entries cover less than some fraction of the body's numbering — would stop the same
failure arriving by a different route. I have not measured how many instruments that would
affect, so I am naming it as a question rather than a recommendation.

## Caveat on the reproduction

I isolated the mechanism from `_repair_label` directly, not by re-running `segment()` over these
documents end to end. The stored `instrument_toc_entry` ledger is a filtered subset of the raw
`toc` dict the repair consults, so the exact raw toc at segmentation time is inferred, not
observed. What is observed: the classifier gets every one of these openers right, the stored
labels are wrong, and `_repair_label` maps precisely this set of numbers to `1` when handed a
contents of the size these documents have.
