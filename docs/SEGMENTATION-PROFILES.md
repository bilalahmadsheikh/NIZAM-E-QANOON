# Segmentation profiles

> **Status (29 September 2026):** built, tested and in use. Four profiles
> exist: `unreleased-v1` (five rules, frozen), `unreleased-v2` (v1 plus
> twenty more, migration 0057, frozen), `unreleased-v3` (v2 plus twenty-three,
> migration 0058, frozen) and `unreleased-v4` (v3 plus one hundred and sixty-six, migration
> 0059, open). The pinned released population changes with bounded releases;
> query it before each replay and compare all of its rebuilt trees (the list
> below is historical, not an exhaustive current inventory):
> - v1: 244, 306, 847, 1014, 1021, 1065, 1486, 2803, 2922, 2954;
> - v2: 264, 1017, 2019, 2027, 2215, 2386, 2622, 2846, 2857, 2950, 3415, 3635;
> - v3: 258, 1142, 1521, 1934, 2818, 2923, 2983;
> - v4: 876 and 1695 (two observations each; the second instrument is an exact
>   duplicate of the first), 589, 904, 1144, 1413, 1515, 1534, 1563, 1794, 1834, 1874,
>   1918, 1950, 2344, 2357, 2459, 2508, 2875, 3002, 3092, 2299, 3132, 3138, 3144, 3149, 3177, 3284, 3302, 3350, 3442, 3486, 3665, 3672, 3794,
>   3836, 3904, 4318.
>
> Every rule change is checked against all of them for an identical rebuild
> (`tools/measure_segmenter_against_stored.py`). Tests:
> `tests/test_unreleased_profile_shapes.py` (pure shapes),
> `tests/test_unreleased_tables.py` (docs 2019 and 1521),
> `tests/test_unreleased_v3_sequence.py` (docs 2923 and 2818),
> `tests/test_unreleased_v3_layouts.py` (docs 1142, 2983, 258, 1934) and
> `tests/test_unreleased_v4.py` (doc 876 from a frozen fixture, and the
> printed shapes of 1563, 3350, 1695 and 4318); the v2 and v3 test files
> also use frozen fixtures.
> Migration 0056, `nizam/corpus/segment.py` (`SEGMENTATION_PROFILES`,
> `profile_rule`), `nizam/workers/segment.py` (`build`, `segmenter_identity`),
> `tools/pin_segmentation_profile.py`, `tests/test_segmentation_profile.py`,
> `tests/test_contents_heading_alignment.py`.

A segmentation profile is a named set of extra segmenter rules. The default
profile is exactly today's parser. A document is parsed under another profile
only when its source observation is **pinned** to it, and only an observation
with nothing released may be pinned to a non-default profile.

## Why

By 25 September 2026, 390 instruments were blocked, and almost all of them were
blocked by parser shapes: a contents list numbered one off from the body,
schedule headings never opened, repeal stubs inside a block, membership tables
read as sections. Every candidate fix for those shapes also changed trees that
were already released; the mid-block stub shape alone occurs in 80 released
documents. Changing a released tree is a correction that needs its own review,
so a rule shipped only if every released document came out identical. Most
rules could not meet that bar without being cut down to nothing.

A profile separates the two populations. The released corpus keeps the default
parser. A blocked document can be parsed with rules that the released corpus
has never been measured against, because those rules can no longer reach it.

This is not a second parser. There is one code path, and a profile rule is a
branch inside it guarded by `profile_rule(name)`. A fork would drift, and every
default-parser fix would then have to be ported by hand.

## How the choice is made

`segmentation_profile_pin` (migration 0056, [SCHEMA](SCHEMA.md)) is an
append-only table with one row per decision. `v_segmentation_profile_latest`
gives the head per observation, and an observation with no row is `default`.

`nizam.workers.segment.build()` reads the pin for the observation it builds
unless the caller names a profile. Every builder therefore agrees: the worker,
the multi-instrument materializer, `find_stale_trees.py`,
`fingerprint_segmentation.py`, `second_parser_release.py`, `inspect_segment.py`
and the probe tools.

**Why a pin, and not "is it released?"** The corpus is replayed constantly.
Suppose the parser chose its rules by asking whether a document is released. A
document released under a profile would, on its next replay, count as
released, fall back to the default rules, lose the repair and be withdrawn. The
choice is therefore made once, recorded, and honoured by every later replay.

## What may be pinned

| Pin | Allowed? |
|---|---|
| Non-default profile on an observation with a released instrument | **Refused** by the trigger and by the tool |
| Non-default profile on an observation with nothing released | Allowed |
| `default` on an unreleased observation | Allowed; it undoes an earlier pin |
| `default` on a released observation | Only with `--allow-released`, because it removes the repair that released it. That is a released-tree correction and needs review first |
| UPDATE / DELETE of a pin | **Refused**; supersede it with a new row |
| Superseding a pin from another observation | **Refused** |
| Any profile not in the closed list | **Refused** by the CHECK constraint |

## Identity

A tree built under a profile records its writer as
`nizam.corpus.segment/<N>+<profile>` in `block_assignment_set.segmenter`,
`segmentation_run.segmenter` and the S7 candidate rows. The multi-instrument materializer records
`nizam.multi_expression_materializer/1+<profile>`. Default trees record the
bare string exactly as before, so no existing comparison changes.
`tools/verify_corpus_repair.py` asserts the bare string, so it expects
default-profile documents.

## Workflow

```bash
# 1. preview: parse under the profile without pinning (dry-run only; the
#    worker refuses --profile on a write)
python -m nizam.workers.segment --documents 1014 --redo --dry-run --profile unreleased-v1

# 2. read the pages the change touches, then pin (dry run, then --apply)
python tools/pin_segmentation_profile.py --documents 1014 --profile unreleased-v1 \
    --reason "contents numbered one off from the body; heading-shift rule" \
    --evidence '{"pages":[3,4],"render":".artifacts/..."}' --apply

# 3. replay, re-attach, re-check the gates
python -m nizam.workers.segment --documents 1014 --redo
python tools/reattach_orphaned_toc_adjudications.py --document 1014 --apply
python tools/reattach_orphaned_adjudications.py ...        # S7 readings, as usual

# 4. prove no collateral change against a signed baseline
python tools/second_parser_release.py verify --run <baseline>
```

A replay of a pinned document can release it only through the usual gate:
`v_toc_gap_pending` and `v_structural_adjudication_pending` empty, and quality
passed. A profile opens no gate on its own. Every decision that closes a TOC
row or an S7 candidate is still read from the rendered page and recorded with
its render path and SHA-256.

## Adding a rule

1. Guard the new branch in `segment.py` with `profile_rule("<name>")` and add
   the name to the profile's set in `SEGMENTATION_PROFILES`.
2. Add a fixture test that runs the rule's shape under the profile, plus a
   control showing the default profile unchanged.
3. `tests/test_segmentation_profile.py` must stay green. It checks that the
   default profile rebuilds whole stored documents byte for byte, that a
   profile with no rules changes nothing, and that rules never leak into a
   later parse.

**A profile is frozen once something is released under it.** Adding a rule to
`unreleased-v1` changes the next replay of every document pinned to it, and
that includes documents already released under it. The default parser has the
same problem, on a smaller population. A rule may therefore join an existing
profile only if every instrument released under that profile rebuilds
identically, which is the same A/B gate the default parser uses but over far
fewer documents. If that gate would cut the rule down, open the next profile
instead: a migration adds `unreleased-v2` to the CHECK list, and new pins use
it.

**Promotion into the default parser** is a separate, reviewed correction to
released trees. A profile never does it.

## Ungated changes and released trees (as built 11 Oct, owner decision)

Agent CT's sweep on 11 Oct found 451 released default-profile expressions
that rebuild differently from what is stored. Three ungated global fixes from
late September caused them: the `N[Provided` proviso opener, the
`_INNER_AMEND_SUBSECTION` cut, and the `_split_heading_base` index fix.
Nothing caught this, for three reasons. frozen-all covers pinned documents
only. `verify` compares stored trees with stored trees. And SEGMENTER had not
been bumped since 15 Sep. Three guards now hold:

1. **A released tree is replaced only by an identical rebuild, or under an
   explicit approval.**
   - `legal_write.save()` and `save_many()` compare the rebuild with the stored
     tree. The tree identity is: path, parent, kind, label, ordinal, pages,
     first block, text and heading. Each contents entry is compared on its
     link and its source anchor (block, offset, page).
   - A rebuild that differs in any of these is refused unless the run passes
     `--approve-release-change "<reason; owner approval ref>"`. Both
     `python -m nizam.workers.segment` and
     `tools/materialize_multi_instrument.py --apply` take the flag, or
     `NIZAM_APPROVE_RELEASE_CHANGE` from the environment.
   - An anchor-only change counts as a change. Identical rebuilds pass as
     before. The release-gate guard is unchanged.
   - An approved replacement records the reason and a summary of what changed.
     It goes into `segmentation_run.detail` (`release_change_approval`,
     `release_change`), and for a multi-expression document also into the
     changed manifest's `evidence.release_change_approval`.
   - The exact-tree overlay tools (`tools/materialize_toc_dispositions.py`,
     `tools/relink_toc_typography.py`) call `save()` too. On a released
     instrument whose tree they would change, they are now refused.
2. **Every run records which segmenter built it.** The worker writes
   `segmenter_sha256` (the sha256 of `nizam/corpus/segment.py`) and `profile`
   into `segmentation_run.detail` on every run: segmented, rejected or error.
   The materializer does the same. `SEGMENTER` stays a hand-bumped tag, and
   the digest is what tells two parsers apart.
3. **A change to any rule that is not gated by a profile must pass the
   released sweep.** It reaches every default-profile tree, which frozen-all
   does not cover. So it must pass the sweep under the heavy lock (about 17
   minutes), or come with an approved correction list:

   ```bash
   flock /tmp/nizam-heavy.lock python tools/measure_segmenter_against_stored.py \
       nizam/corpus/segment.py --released-only --out .scratch/released
   python tools/measure_segmenter_against_stored.py --summarise .scratch/released.jsonl \
       --gate [--approved APPROVED.txt]     # exit 1 on any unapproved released difference
   ```

**Same-blob observations and new releases (as built 12 Oct, after doc 4419).** A replay rebuilt the Constitution's
byte-identical duplicate observation (132) without the readings recorded on its canonical (507); it stopped being an
exact duplicate and a second, uncorrected copy entered the release, which no withdrawal check could see. Three
changes hold now:

- `tools/record_curation_patch.py` records a reading on every observation behind an active instrument of the
  document, duplicates included; one blob means every such observation, different blobs still need
  `all_observations`; an observation already carrying the identical patch is skipped and reported.
- The worker and `tools/materialize_multi_instrument.py` refuse, before building, a document whose same-blob
  observations carry different effective patch sets, active TOC disposition sets (label, disposition,
  contents block, page) or profiles (`same_blob_observation_problem`; the message names each observation and what
  it lacks). `tools/review_toc_dispositions.py` records a disposition on every same-blob observation, idempotent
  per observation (docs 4501 and 2605 carried a disposition on one observation only).
- `tools/post_replay_sequence.sh` step 2c runs `tools/released_count_guard.py`: against the newest signed baseline,
  any document holding more released expressions stops the sequence unless a reviewed split plan
  (`tools/evidence/multi-instrument-plans/doc-N.json`) covers the count or a run's approval reason says
  "new released expression". Tests: tests/test_recorder_observations.py,
  tests/test_same_blob_and_release_count_guards.py.

**Data-gated rules (every profile, inert without a reviewed reading).** These were added in stage 3 with owner
approval (11-12 Oct). Agent DB's three are the gated form of the 23 Sep parser-drift repair `.patch_drift.py`.
Applied ungated, that repair moved 168 released expressions outside its group, so it is not applied
(tests/test_parser_drift_repair.py stays skipped). Agent DF's four serve docs 4347 and 4451, and agent DE's
underscore-dash declaration serves the RE batch. For each, a full released sweep with no readings shows the
gated form equal to the parser without it. Tests: tests/test_db_gated_rules.py, tests/test_df_gated_rules.py,
tests/test_decoded_underscore_dash.py.

| Rule (reading key) | What it does | Documents |
|---|---|---|
| `contents_marker_block` (`source_contents_marker_blocks`: block ids on the reading's page) | In exactly the named blocks, a bare contents column word (C O N T E N T / Sections / Rules) counts as the contents marker where it is SET OFF as a header: no sentence text above it, and it closes the block or heads the first entry. Fails closed if a named block is missing or its word is not set off. | 423, 1067, 1119, 1132, 1704 |
| `heading_scan_section_only` (`source_heading_scan_section_only: true`) | The marginal-heading scan skips the unit's own block only for a SECTION label, and only over a same-block subsection, proviso, clause or long continuation (`.patch_drift.py` C). Without it, a sub-section "(3)" reaches the next section's margin heading. | 1139, 1341, 1382, 2034, 2669, 2786, 3063, 3255, 3860, 4229 |
| `not_running_header_blocks` in every profile (`source_not_running_header_blocks`) | The reviewed blocks are no longer dropped as running headers, now in every profile, not only `unreleased-v4`. | 3255 (pp80-83, rate '15%') |
| `reviewed_decimal_cut` (`source_decimal_cut_blocks`; agent DF) | In exactly the named blocks, a new line opening a decimal label (N.M, N.M.K, N.M.K.L, optional stop) before a capital, a quote or '(' -- on the same line or the next -- starts its own unit, as does a line printing only 'N.' whose next line opens 'N.1'. A decimal unit of such a block gets no first-sentence heading guess. Fails closed if a named block is missing. | 4347 (regulations 1-14 and their sub-regulations) |
| `reviewed_table_row_blocks` (`source_table_row_blocks`; agent DF) | A unit of a named block that the grammar reads as a section is a row (clause, printed serial) of the open unit. | 4347 p4 (classification table) |
| `reviewed_division_continues` (`source_division_continues_blocks`; agent DF) | While an annexure or schedule is open, the naming formula at label 1 ('1. These Rules may be called ...') in a named block does not resume the instrument's body (the doc 2754 exit). | 4347 p64 (Provident Fund rules) |
| `reviewed_marked_label_cut` (`source_marked_label_cut_blocks`; agent DF) | In exactly the named blocks, a new line opening 'M[N. Mx[Capital' -- a section label behind a note bracket whose text opens behind a lettered note marker -- starts its own unit. | 4451 p51 (s.25 '31[25. 31b[Value ...') |
| `owner_cited_label_reviewed_default` (`source_owner_cited_labels`; agent DC round 2, owner 12 Oct 'cite-47A') | A reviewed owner-cited label entry is honoured in ANY profile (the key exists only in recorded, owner-cited readings; a released default observation cannot be pinned). An entry may cite a lettered label ('47A', an insertion: neighbours 47 and 48) and name which print it relabels (`source_occurrence` >= 2). | 2756 p25 (second '47.' cited as s.47A; held for the owner's export) |
| owner-cited choices admitted 13 Oct (`OWNER_CITED_LABEL_CHOICES`, nizam/workers/segment.py; lead decision) | The closed set of decision-review answers a `source_owner_cited_labels` entry may cite gains 'repealed-stubs' (export j doc 4222 q1: the repealed sections are held as stubs under their cited numbers; 4222 itself stays blocked) and 'printed-6' (export j doc 4154 q2: the section printed '7. 6.' is s.6, opening at its second number). Any other answer is still refused where the reading enters the system. Inert: a reading citing either answer was refused before. | tests/test_owner_decision_overrides.py::test_owner_cited_choices_admitted_13_oct |
| `reviewed_clause_section_reparent` (`source_reparent_blocks`; agent JE, owner export j 4441 q2 'printed') | A reviewed reparent may move a numbered section that the walk demoted to a clause of the section before it (an indented opener after an unpunctuated cross-heading) back to the chapter or part that prints it, retyped section. The spec must say kind section, source_kind clause, the source_label, and parent_kind chapter or part; `_apply_source_reparents` fails closed as for every reparent. Inert: such a spec was refused before. | 4441 s.390 under Chapter XVII; tests/test_je_rules.py |
| `printed_heading_reviewed_default` (`source_printed_headings`; agent JE, doc 4441) | A reviewed printed-heading entry is honoured in ANY profile, as owner-cited labels are (the key exists only in recorded, owner-cited readings). Full released A/B 0 differing. | 4441 s.390 'Robbery', s.462N; tests/test_unreleased_v4.py::test_printed_heading_override_reviewed_in_any_profile |
| `reviewed_figure_subsections` (`source_figure_subsections`; agent JE, owner export j 4521 q1 'subsections') | Bare figures printed beside one margin note ('1.', '2', '3.') are the sub-sections of one section: the named blocks are taken out of whatever the walk made of them, and one top-level section is opened at the first, headed as printed, with one sub-section per block labelled by its printed figure; the text after each printed prefix is the sub-section's. Fails closed: owner decision cited, figures 1..n, every prefix printed at its block, each block found once. | 4521 s.1(1)-(3); tests/test_je_rules.py |
| `reviewed_margin_note_pieces` (`source_margin_note_pieces`; agent JE, doc 4426) | A gazette margin note printed over several blocks names the rule opened at `target_block_id`: the pieces (set aside as apparatus by the same readings) are joined in order as its heading. Fails closed: the pieces must be apparatus, on the target's page, join to exactly `heading`, and exactly one section or article with `label` must open at the target block. | 4426; tests/test_je_rules.py |
| materializer refuses unknown keys (lead 13 Oct, after agent JE's doc 4431) | `tools/materialize_multi_instrument.py` REFUSES, naming the key, a reading or a recorded patch whose key it does not know, instead of dropping it. That covers an unrecorded dry-run reading outside STRUCTURAL_PATCH_KEYS plus the non-structural reading keys, and a recorded patch's structural override outside STRUCTURAL_PATCH_KEYS. On the legacy (PRIMARY/COMPILATION) route, which applies none, any recorded structural override is refused (doc 4497's own path excepted). STRUCTURAL_PATCH_KEYS equals the recorder's STRUCTURAL_KEYS. After the fix, every multi-instrument document rebuilt equal to its stored release (26 documents). | tests/test_multi_instrument.py::test_materializer_refuses_unknown_patch_keys_rather_than_dropping_them |
| export j ports (14 Oct 2026, builder BZ; one combined full released A/B over the group, $S/agBZ-ab-g4) | Agents JB, JC, JA and JE rules ported by name. Profile rules joining unreleased-v4: `reviewed_link_in_division`, `number_line_half_paren_subrule`, `order_suffix_after_reparent` (JB) and `namely_lead_not_heading`, `apparatus_contents_rows`, `amount_cell_not_label` (JC). The rest are data-gated by reviewed keys. Each ported document's build on the live code equals its agent's prediction (in memory, before recording). | tests/test_export_j_ports.py, tests/test_je_rules_3_5.py |
| `reviewed_link_in_division` (JB A; docs 2862, 3277, 3291, 3189, 3334, 2825-2827, 2852, 4154) | `reviewed_contents_alignment`'s reviewed contents row link may end on a section or article that hangs under parts or chapters reaching the root, not only one at the root. JC's duplicate `contents_row_links_in_divisions` is merged in (dedupe, lead 13 Oct), together with its second piece: a row that a reviewed link gives a unit is looked up under that unit even when its name opens 'Schedule ...' (doc 3606 row 13 'Schedule of establishment.' -> rule 14). JC's 3606 and 3624 build identically under the merged rule. | JB, JC trees |
| `number_line_half_paren_subrule`, `order_suffix_after_reparent` (JB B, C; docs 3099, 3219) | B: a rule number alone on its line over its first sub-rule '1) A ...' starts its unit. C: reviewed reparents run before the order-suffix completeness check, so a clause group that becomes siblings only under its reviewed parent is suffixed there. | JB trees |
| `statute_row_headings` (JB D; docs 2872, 3327, 3330, 3456) -- DATA-GATED | A First-Statutes schedule may number its statutes as any contiguous run, and a statute the parser opened without a heading takes its contents row's words where the page prints them at that statute. Switched on only by the reviewed observation flag `source_statute_row_headings: true` (lead 13 Oct: as a profile rule it changed released doc 2731's headings). | test_profile_rules_and_the_data_gated_statute_row_headings |
| JB E-I: `owner_cited_clause_label`, `reviewed_explanation_of_heading` (`source_explanation_of_heading`), `reviewed_no_cut_block` (`source_no_cut_blocks`), `reviewed_margin_heading_owner` (`source_margin_heading_owners`), `reviewed_root_reparent` (`source_root_reparent_blocks`) | E: an owner-cited entry of kind clause relabels one lettered clause print (doc 3240), with the recorder checking the '(x)' print. F: explanation_of_heading by observation flag in any profile (doc 3389). G: a named block is never cut (doc 3216); the recorder admits apparatus on a reading's cited pages. H: a page-read margin heading names the unit it is printed beside (doc 2949), with a recorder page check. I: a named section or article moves to the root (doc 3216). All fail closed. | test_export_j_ports.py |
| JC `namely_lead_not_heading`, `apparatus_contents_rows`, `amount_cell_not_label`, `owner_cited_bracketed_per_label` (docs 3708, 3520, 3509, 3700) | A first sentence followed by 'Namely:' is no heading; a contents block set aside as apparatus yields no rows; 'N.NNN Million/Lac/Crore' is an amount, not a label; bracketed owner-cited prints are read per (block, label). | JC trees; test_amount_cell_is_no_label_under_v4_only |
| JA C, E, F, G, H: `reviewed_chapter_over_part` (`source_chapter_over_part`), `reviewed_contents_schedule_rows` (`source_contents_schedule_rows`), `reviewed_form_text_blocks`, `reviewed_lettered_part_blocks`, `reviewed_unheaded_section_blocks` | C: parts inside chapters (doc 2359). E: contents rows are the rows of the named schedule (doc 2556). F: a form's blocks are one unit's text (doc 2479). G: 'A. CAPITALS' opens a lettered part (doc 2668). H: a named section prints no heading, so no guess names it (doc 2668). Data-gated; all fail closed. | JA trees; test_export_j_ports.py |
| JE rules 3-5: `owner_cited_compound_label`, `reviewed_list_item_text`, `reviewed_decimal_item_cut`, `reviewed_text_unit`, `reviewed_quoted_definition_cut`, `reviewed_division_opener`, `reviewed_division_caption` | Compound N-M / N.M owner-cited labels (docs 4498, 4400); bare list items as a regulation's text, decimal item cuts and text units (docs 4408, 4409, 4416); quoted definition cuts, division openers and captions (docs 4426, 4408). Data-gated; JE's full A/B over rules 1-7 read 0. | tests/test_je_rules_3_5.py (JE's own tests on the live code) |
| choices admitted 13-14 Oct (lead) | Owner-cited 'regulations' (3700 q1) and 'other-copy' (2985 q2); schedule group caption 'body' (2611 q1); APPENDIX opener 'appendix-rows' (2658 q1, same effect as 'appendix-rows-by-serial'). | test_choices_admitted_13_oct_group4 |
| recorder: no structural key dropped (lead 13 Oct, doc 4521) | `tools/record_curation_patch.py` records keys whose parser check is fail-closed through a generic branch (GENERIC_STRUCTURAL_KEYS: every block id named must be in the document), and refuses, naming it, any reading whose structural key did not reach the recorded evidence. | tests/test_recorder_observations.py::test_every_structural_key_has_a_recording_branch |
| export j group 5 (14 Oct 2026, builder BZ; agent JD; one combined full released A/B, e2a92b68 vs 46cc0c0a: 4,503 identical, 0 different; 245 v4-pinned identical) | Profile rules joining unreleased-v4: `roman_chapter_line` (C), `marked_dash_section_cut` (D), `subsection_line_cut` (E), `hyphen_letter_division_stop` (H), `reviewed_link_unit_kind` (K), `root_provision_contents_row` (L), `chapter_note_contents_row` (N), `quoted_row_paren_serial` (P, with the '8.)' extension), `quoted_table_rows_in_block` (Q), `range_to_contents_row` (R), `subpart_scan_unlabelled_schedule_bound` (S), `body_start_unmarked_contents` (U), `contents_named_division` (V). C/D/E are fail-closed on reviewed block lists (`source_chapter_line_blocks`, `source_marked_dash_section_blocks`, `source_subsection_line_cut_blocks`); V on the keyed `source_contents_named_divisions` (first_block_id). K: a reviewed contents row link may name a unit by kind, admitted only for `unit_kind` part or schedule (lead: a 'chapter' kind needs schema review). Docs 3892, 3998, 4044, 4068, 4234, 3901, 3926. | tests/test_jd_dash_and_first_subsection.py; JD trees |
| export j group 6 (14-15 Oct 2026, builder BZ; agent JD) | `reviewed_division_line` (F; reviewed block list `source_division_line_blocks`) and `owner_unnumbered_section` (G; reuses `source_unnumbered_section_openers`; doc 2491). `kind_link_counted` (W) and `range_link_counted` (M) change only the run's label arithmetic (absent_row / represented_labels), never a tree: W counts a contents row resolved through a reviewed kind link (K) as represented under its own printed label (docs 3926, 3933, 4142); M lets a contents range row 'N to M' linked to the node carrying that same range label represent every number N..M and nothing else (doc 3901's run-only '11'). JD's W+M full released A/B: 4,508 / 4,508 identical. | tests/test_reviewed_division_line.py, test_owner_unnumbered_section.py, test_kind_link_counted.py, test_range_link_counted.py |
| `reviewed_schedule_heading` (`source_schedule_heading_blocks`; agent DC round 2) | A page-read Schedule display-heading block opens the Schedule when no default proof fires. Fails closed when a named block opens no Schedule. | 2703 p7 ('THE SCHEDULE / LIST OF INSTITUTIONS') |
| `reviewed_repeal_stub_cut` (`source_repeal_stub_cut_blocks`; agent DC round 2) | Profile rule `bracketed_repeal_stub_cut`'s cut ('N. [Heading.] Rep./Omitted ...' after a sentence end starts its own unit), in a named block only. Fails closed when a named block yields no cut. | 2703 p7 (s.9, s.10 stubs) |
| `reviewed_running_header_blocks` (`source_running_header_blocks`; agent DC round 2) | Named blocks take the role running_header and leave the body. Supplied by tools/materialize_multi_instrument.py for doc 4497 only (its page-numbered ESTACODE running titles, exact printed shapes; plus block 885517 in REJECTED_EDITORIAL_BOUNDARIES for E1). | 4497 (127 phantom chapters -> 0) |
| `reviewed_marker_run_cut` (`source_marker_run_cut_blocks`; agent DF, lead 12 Oct) | In a named block (or its tail after a fused margin heading), a new line opening a section label behind a note-marker run starts its own unit: a comma run with a lower-case word straight after the stop ('2,7[12.power ...'), or an '&' run before a bracketed lettered label the contents promise ('5&7[(14A. ...'). No character changes. | 4451 pp38, 40 |
| `reviewed_half_paren_items` (`source_half_paren_item_blocks`; agent DF) | In a named block, sub-rules printed 'a)' and 'i.' (also 'b) i.' and 'N. ... a)' on one line) start their own units and read as clauses (labels as printed). The data-gated form of the v4 rule `half_paren_clause_label`. | 4347 E6 (PF Rules pp64-75) |
| `reviewed_inline_table_blocks`, `reviewed_group_heading_blocks` (`source_inline_table_blocks`, `source_group_heading_blocks`; agent DF) | A caption read as a division opener in a named block is the open unit's text; a numbered or Roman group heading in a named block opens a group (kind part). `reviewed_table_row_blocks` now reads only INTEGER serials as rows. | 4347 split (E0, E2) |
| `leading_margin_heading_unit` for reviewed blocks (`source_leading_margin_heading_blocks`; agent DB, owner 12 Oct) | The v3 rule in named blocks only (any profile): a unit that is the contents heading of the section opening next in the same block (a bare label owning its line included) is that section's heading, and no first-sentence guess splits the text. Fails closed if a named block is not reached. | 252 |
| `order_suffix_label` data-gated (`source_order_suffix_labels`; agent DE, owner 12 Oct) | The profile rule OR a reviewed order-suffix spec on the observation: a released default observation cannot be pinned. | 3500, 4225 |
| `reviewed_long_suffix_section` (`source_long_suffix_section_openers`: [{block_id, label: digits + 4-8 capitals}]; agent DE) | A reviewed long-suffix label opens a section, only at the start of its named block and only when the contents print that label as a row on an earlier page (fail closed). One identical value per observation. | 4225 (s.11EEEE, s.11EEEEE) |
| `keep_first_subsection_blocks` on the dash declaration (agent DE) | In named blocks the heading-closing run before (1) stays as extracted and (1) is not cut (regions with a known structural defect; paths stay as released). Fails closed if a named block holds no such run. | 4036, 4424, 4463 |
| `reviewed_schedule_chapter_reparent` (`source_reparent_blocks` kind 'chapter'; agent DG) | A reparent spec may move a schedule's printed CHAPTER (with its subtree) under the schedule that prints it -- only {kind chapter, source_kind chapter, parent_kind schedule}. Worker and recorder only. | 4236 |
| `decoded_underscore_dash` (`source_decoded_underscore_dash`: one glyph declaration per observation; agent DE, owner 12 Oct) | The declaration names the glyph the page prints, with its glyph-ink counts and 1-3 measured runs. `decoded` (the page prints an em dash the text layer maps to '__'/'___'; no underscore ink): every 2-3 underscore run in a proven dash context reads as U+2014 in the DERIVED block text (text_block stays verbatim), and sub-section (1) after a heading-closing dash on the same line starts its own unit. `typed` (the page prints underscores; no dash ink): the text is kept as printed and only that (1) is cut. Never a run after a digit, on a form line (4+ underscores, ellipsis, dot leader), ending the block, or before a letter label. A `decoded` declaration may also name `typed_runs` [{block_id, left}] -- runs the page prints as REAL underscores among decoded dashes (runs_underscore = their number): each keeps its underscores and still gets the (1) cut; each must be found exactly once or the build fails closed (lead 12 Oct; docs 3853, 4385). A malformed declaration fails closed; a second patch must carry the identical value. | batches RE, REX, MO, MOH, NE, TE; typed_runs 3853, 4385 |

Ungated rules admitted under this gate:

| Rule | What it does | Sweep / approval |
|---|---|---|
| `amending_heading_guard` | With no contents list, a guessed first-sentence heading is refused when it is the section's own amending or repealing words. That is a span which opens a quotation it does not close, carries 'the following shall be', or ends 'hereby [stands] repealed'. The section then keeps no heading, and its text is the whole printed body in order. Only the no-contents guess is guarded; the contents fall-through guess is unchanged. | Stage 3, agent DA, owner approval 11 Oct. In the full released sweep it changes only the 24 C3-class documents plus 329, 670, 705, 859, 993, 1008 and 4335, each page-read. Heading/text only, with no path, S7 or contents change. All were replayed under approval. Examples: doc 31 s.2, doc 428 s.3, doc 798 s.3. |
| `body_evidenced_disposition` | A reviewed contents-disposition assertion (omitted/repealed) also matches a contents row that prints NO lifecycle word, when block, page and label match as before, the row's heading equals the recorded `printed_heading` exactly (whitespace-normalised), and the assertion's evidence carries the rendered BODY page (`body_render` + `body_sha256`) that prints the omission or repeal. A row printing the other lifecycle word still refuses. | Stage 3, agent DC, owner approval 11 Oct. Only assertions that raised 'stale TOC disposition assertion' on every rebuild are affected: in the full released sweep it changes exactly 1351, 1366, 1609, 1846 and 4379 (error -> built); their trees came from the exact-tree overlay, which never ran this identity check. tests/test_body_evidenced_disposition.py. |

**Replay carry of an accepted S7 judgement (`equivalent_candidate_subtree_carry`, legal_write.py; stage 3, agent DC,
owner approval 11 Oct).** Not a segmenter rule: it changes no tree, only whether `save()` carries an existing
`accept_non_citable` decision onto the replay's matching candidate. The match is today's (same candidate row and
evidence, unique) with paths compared without positional collision suffixes (`_n92_1`). Exact subtrees carry as
before. Otherwise the decision carries when the CANDIDATE is equivalent -- same root, same (block, role, chars)
footprint and same letter-word sequence, or differing only by source blocks that left the law (assigned no law role
in the new tree, words lost == those blocks' words) -- and the CANONICAL keeps its root and is not a stub against the
candidate on the new sizes (the two guards of tools/adjudicate_citation_preserving.py). Recorded append-only with
method `carried_by_equivalent_candidate_subtree/1`, decided_by `nizam.equivalent_candidate_subtree/1`, the review
basis unchanged, and evidence `equivalent_candidate_subtree_replay`. tests/test_equivalent_s7_carry.py.

## Rules in `unreleased-v1`

### `contents_heading_alignment`

**The shape.** Some printed contents lists are numbered at an offset from the
body they list:

- Doc 1014 lists "3. Constitution of Governing Body", which the Act does not
  have, so every later row runs one ahead of the body.
- Doc 1486 skips 4.
- Doc 2803 runs one behind from row 2 and two behind from row 14.

The default parser links contents rows to units by number. As a result:

- each unit in the offset run takes the heading of the wrong row;
- the body's own heading lines are read as text of the previous unit;
- the last row is left unlinked, which blocks release.

**What the rule does.** After the normal parse, `_contents_heading_alignment`
aligns contents rows to top-level body units by the heading each unit itself
prints: in its opening block, on the short line above it (only when the unit
opens that block), or on a short line just after it. The alignment is monotone,
and ties go to the printed number. Rows between two aligned rows are paired
with the units between them only when the counts agree. A row with no unit
between its neighbours is marked as naming nothing in the body.

**When it fires.** All of these must hold:

- at least 3 aligned rows, covering at least 60% of the contents;
- at least one row whose heading is printed at a unit with a different number;
- none of those rows also has its heading printed at the unit carrying its own
  number;
- no gap is ambiguous.

If any condition fails, nothing changes. When the rule fires, the parse is
re-entered with the mapping from contents row to body label. The body walk then
reads each unit's own heading, and the linker joins each row to the unit its
heading names. The recorded rows keep their printed labels, and the match
method is `heading_alignment:*`. The re-parse is kept only if:

- the citable (kind, label) sequence is identical;
- no S7 candidate is added;
- no contents row loses its link.

**What the rule never decides.** A row marked as naming nothing (`None` in the
alignment) stays unlinked and pending. It is closed only by a
page-read `absent_in_source`, or by `found_elsewhere` when the page shows the
unit somewhere else. The rule decides nothing about the source that the
reviewer has not seen.

The mapping is recorded in `segmentation_run.detail.contents_alignment`.

**A contents list that numbers the preamble.** Docs 244, 306, 1021, 1065,
2954 and 3078 print "1. Preamble." as the first contents row, while the body
prints the preamble unnumbered and numbers its sections from 1. The general
alignment usually has too few anchors for such short lists, so this shape is
handled by `_preamble_row_alignment`. It applies only when all of these hold:

- the later rows are numbered consecutively;
- each later row has exactly one unit one number below it;
- no row's heading is printed at the unit with its own number;
- at least one row's heading is printed one below.

The preamble row is then left unlinked and closed by a page-read reading. The
project owner decided on 26 Sep 2026 that such a row is "not a numbered section
in the body". It is recorded as `absent_in_source`, with the observation
saying so.

A printed line names only the row(s) it matches best. Doc 244's contents
lists "Amendment of 3[..] Act XII of 1973" and "Amendment of 4[..] Act X of
1977", and a looser test let one printed line name both.

### `printed_heading_extent`

Each case below is the body's own heading, in the body's own words:

- **Longer heading.** The contents shortens a heading the body prints in full
  (doc 2803 rule 9). The heading extends to the body's own terminator.
- **Heading line alone.** A unit's line that is only its heading, in words the
  contents corroborates, becomes the heading rather than text.
- **Margin heading merged into the block.** Doc 1065 prints "The Gift Tax Act,
  1963 (XIV of 1963), is hereby repealed. Repeal of Act XIV of 1963." When the
  merged sentence exactly repeats the contents heading, it is the heading.
- **Shorter printed name.** Doc 2954 prints "1. Short title.___(1) ..." against
  the contents' "Short title, commencement". A shorter name closed by a dash is
  the heading.
- **Underscore dashes** are stripped.
- **Heading guesses.** A first-sentence guess never ends at an abbreviation.
  Doc 1021's "In the .. Ordinance No. V of 1982" was cut at "No.". Nor may the
  guess contain operative words.
- **Aligned rows.** A row joined by the alignment gives its heading to its
  unit even when the unit's text opens with an operative clause.

Two released trees carry defects this rule repairs: 252 s.21 and 983 s.1.
They are listed in `tests/test_contents_heading_alignment.py` `KNOWN_REPAIRS`
for the released-correctness lane.

### `prose_explanation_word`

A lowercase "explanation" running straight into a lowercase word ("the
following / explanation shall be inserted, namely:", doc 1021 s.2(b)) is
prose, not an Explanation opener.

### `first_statutes_schedule`

A university Act's "THE FIRST STATUTES" is its schedule of statutes. The
heading must be printed alone or with only its reference "(see section 34)".
The contents row that names it ("39. Statutes.") links to it. So does a
trailing run of rows listing the statutes, but only when the counts match,
the statutes are numbered 1..n, and at least half are corroborated on the page
(doc 2922).

### `schedule_reference_lines`

An uppercase SCHEDULE display heading, possibly carrying its title ("SCHEDULE
STANDING ORDERS"), is proof of a schedule when it is followed on the same page
by its section reference. The reference may cite a sub-clause ("( see section
2(1)(k))"), and at most one uppercase title line may stand between them
(docs 2846, 2950). This rule is not yet enough to release those documents.

## Rules added in `unreleased-v2`

`unreleased-v1` froze once documents were released under it. The first rule
that would have changed one of them opened v2 (migration 0057):
`margin_heading_blocks` would take the trailing margin heading out of doc 1014
s.3's text. v2 has every v1 rule plus these:

| Rule | Shape | First document |
|---|---|---|
| `margin_heading_blocks` | A right-margin block that repeats one of the document's own contents headings exactly is a heading, not text. Page breaks otherwise set it inside a sentence. | 2386 |
| `contents_false_rows` | A contents page's own footnote ("Subs vide ...", "*Rep. by ...") or a title line ("No. XXIII of 1918") parsed as a row is dropped from the ledger. | 264, 2027, 2215 |
| `download_stamp_furniture` | A Pakistan Code download stamp ("Date: 05-08-2024") and the rule line above it are page furniture. | 2027, 2215 |
| `page_number_furniture` | A block that is only its own page number is furniture. | 3635 |
| `heading_guess_to_be` | "X to be Y" can be a heading ("Power of Act to be cumulative"). | 2215 |
| `abbreviated_name_guard` | A sentence cut at an abbreviation ("...Ord.") is not the unit's own name. | 264 |
| `lowercase_heading_split` | "N. lowercase heading." on a new line after a sentence end opens unit N. | 2622, 3635 |
| `fuzzy_printed_heading` | The body's own wording of the contents heading, closed by ".--", is the heading ("Ground of penalty" / "Grounds of penalty"). | 3635 |
| `introduced_member_list` | "1. 2. 3." after "consist of the following members:-" are items of the introducing provision, not sections, until an item names the next contents heading. | 258, 1017, 2019, 1521 |
| `designation_cells` | A membership table's designation column ("Chairman", "Member(s)", "Member/ Secretary", ".." leaders), emitted out of order, goes back beside the row whose span holds it. The plural "Members" was added for doc 1521 with every v2 tree unchanged. | 1017, 1521 |
| `quoted_form_letter` | "FORM 'C' [See Rule 3 (6)]" is form C; "Form of Certificate" is not a form labelled "Form of". | 2857 |
| `divisions_end_body` | A form, schedule or appendix heading that cites the provision it is made under ("[See Rule 3]", "(See section 5)") is a division even after an unfinished line. The word must stand as a heading: "Schedule, the following shall be substituted" (doc 589) is the sentence. | 2857, 2950, 2019 |
| `quoted_division_letter` | "APPENDIX ―A‖" (quotes decoded as U+2015/U+2016) is appendix A; the generic rule labelled both appendices "APPENDIX". | 2019 |
| `row_aligned_cells` | A short table cell printed level with a numbered row but emitted before it goes directly after that row. The page must show a table: two or more rows at one left edge that stop well short of the text column, another of them with a cell beside it. A margin heading level with a full-width opener is never a cell (docs 2386, 2846 were the tripwires). | 2019 |
| `column_number_cells` | A line of "(1) (2) (3)" column indices under a table's heads is table text, not three sub-sections. | 2019 |
| `decoded_quote_openers` | "(b) ―Board‖ means" opens clause (b) mid-block like "(b) “Board”". | 2019 |
| `enacting_formula_ends` | "It is hereby enacted as follows :—" is a finished sentence; the CHAPTER/PART after it opens. | 2019 |
| `sequential_chapter_heading` | A bare "CHAPTER—III" on its own line, followed by an upper-case title and numbered one after the last chapter opened, opens even after a sentence printed without its full stop. | 2019 |
| `member_list_closing_words` | A capitalised paragraph outdented from a finished member list ("In the absence of Chairman ...") and the proviso after it belong to the list's parent, not the last member. | 1521 |
| `tight_first_subsection` | "10.(1) Health workers ..." with no space after the section's full stop opens sub-section (1). | 1521 |

v2 froze in turn when documents were released under it. The first rule that
would have changed one of them, `wrapped_bracket_reference`, opened v3.

**A finding about released trees.** The download stamp sits inside the
provision text of 326 released instruments. Among them is 2954, released under
v1, whose s.6 ends with the stamp. The trigger forbids re-pinning a released
observation to v2. Correcting those trees is a released-tree correction. It is
listed for the project owner and the released-correctness lane, not made here.

## Rules added in `unreleased-v3`

Migration 0058. v3 has every v2 rule plus these:

| Rule | Shape | First document |
|---|---|---|
| `wrapped_bracket_reference` | A line ending in a reference word ("sub-section", "sub-paragraph", "clause") whose bracketed number wraps to the next line, followed by a lower-case word, continues the sentence and opens nothing. | 1521 |
| `level_margin_heading_owner` | A heading block with no node belongs to the single provision whose opener is printed level with it (3 pt) to its left on the same page, not to whatever node comes next in reading order. | 1521 |
| `schedule_contents_run` | Inside a schedule, a label the contents prints only after its numbering restarts at 1 belongs to the schedule, not to the Act resuming. | 2983 (not yet released) |
| `sequence_omission_stub` | An omission stub "1[(3)* * * * *]" is section 3 when the contents lists 3 and 3 is the next section after the highest the walk has met; otherwise (an omitted sub-section is printed the same way) it stays what it was. A stub line inside a block starts its own unit. | 2923 |
| `bracketed_omission_stub` | "3[5 * * *]" (footnote marker, bracketed number, asterisks, no full stop) is section 5's stub. | 1142 (not yet released) |
| `decoded_dash_first_subsection` | "Heading.―(1) The ..." with U+2015 (a decoded em dash) opens sub-section (1); the bar left behind is not the section's text. | 2923 |
| `promulgating_formula_ends` | "... promulgate the following Ordinance :—" is a finished sentence; the CHAPTER after it opens. | 2923 |
| `sequence_bare_number` | A block opening "26 Certificates ..." (number, no full stop) is rule 26 when the contents lists 26 and it is the next after the highest section met. | 2818 |
| `mark_only_heading_none` | A heading of nothing but asterisks or leader dots, copied from the contents, is no heading. | 2818 |
| `exception_word_boundary` | "Exceptional cases ..." is not an Exception labelled "Exception" with the text "al cases". | 2818 |
| `tight_first_clause` | "…provisional order.(a) When …" opens clause (a). | 2818 |
| `inblock_footnote_tail` | After a blank line inside a block, "60Inserted by ..." / "56Numbered as ..." starts its own unit, which the footnote grammar reads as apparatus. | 4222 (not yet released) |
| `heading_only_rest` | With no contents heading (sections inserted after the contents was printed), a rest that is only "Reward and punishment.-" is the heading. | 4222 |
| `row_cells_within_rows` | The row-cell rule for tables whose rows are wide single blocks: a cell lying inside another worded numbered row's span is a table cell (a page number is not a row). | 4222 |
| `marked_clause_opener` | "1(b) all laws ..." (note marker before the letter) opens clause (b) when the open clause is (a). | 1142 |
| `margin_heading_tail` | A margin block that is the last two or more words of a contents heading ("of laws." of "Application of laws.") is a heading fragment. Only the tail: taking every piece out of the body removed the evidence the contents linker reads, and 24 of 2983's 28 rows fell unlinked. | 1142 |
| `schedule_item_list` | Inside a schedule, rows 1, 2, 3 nest under the open lettered item when it ends introducing a list ("... gets: - Categories"). | 2983 |
| `body_start_keeps_contents` | A reviewed body start that the contents overran keeps the ordinary contents parse and moves only the boundary; rebuilding the contents as a label map lost a two-run contents list. | 2983 |
| `margin_heading_pieces` | Margin headings over several blocks ("Tax treatment of the" / "income of the" / "workers.") join greedily while they stay the start of a contents heading; a completed group is kept out of the provision's text but stays in the walk. Left margins count too. | 2983, 258 |
| `leading_margin_heading_unit` | "Definitions. / 2. In this Act ..." -- a unit that is the contents heading of the section opening next in the same block is that section's heading, not the previous section's tail. | 258 |
| `designation_before_opener` | A designation cell is set before a block that opens (or contains) a "(4)" opener, not inside it. | 258, 1934 |
| `designation_bracket_rows` | Designation cells belong beside "(i)" / "(a)" rows as well as "1." rows. | 1934 |
| `printed_disposition_rows` | A contents row that is itself the disposition mark -- "[Repeal.]", or only asterisks/dots -- can carry a reviewed `toc_disposition_assertion`. For a row of marks, the record may say `omitted` or `repealed`, as the body's note decides. **The marks alone prove nothing**: doc 2818 prints "*****" for rules that exist and are merely unnamed. So record an assertion only after reading the body and its note. | none yet (4222 is the case, blocked on footnotes read as text) |

Widened in place (every v3 tree rebuilt identically after each): `decoded_dash_first_subsection` also cuts after an em dash ("commencement.—(1)", doc 1934); `wrapped_bracket_reference` admits bracket labels up to six characters ("clause / (xxxii) of section 2", doc 2983); `level_margin_heading_owner` accepts an opener on either side (left margins, doc 258).

**A vacuous pass to watch for.** A parse whose contents agreement falls below the refutation threshold is re-run without contents. It then records no contents entry, and both gates pass. During this work 2983 did exactly that under an intermediate v3. Every pin is therefore checked against its stored `instrument_toc_entry` count.


**A second finding about released trees.** `wrapped_bracket_reference` would
mend doc 2846 standing order 13(3), released under v2: "... under clause / (1)
shall bear ..." opened a false sub-section (1). That is why the rule could not
join v2. Correcting 2846 is a released-tree correction. It is listed for the
project owner, not made here.

## Rules added in `unreleased-v4`

Migration 0059. v3 froze when documents were released under it. The first rule
that would have changed one of them opened v4: `level_margin_heading_text`
would also name doc 2983's Scheme paragraphs 4 and 6. v4 has every v3 rule plus
these:

| Rule | Shape | First document |
|---|---|---|
| `level_margin_heading_text` | A provision with no heading takes the margin heading printed level with its opener. | 876 |
| `contents_bare_number_rows` | "11 Chancellor." in the contents, with no full stop, is a row when the row before is 10 and the next block opens 12. Without it, a second contents run's "11." named the Act's s.11. | 876 |
| `paren_amendment_opener` | "4. 1(The authority ..." -- a round amendment bracket after the note number -- opens section 4 mid-block. | 1563 |
| `detached_heading_after_division` | A contents number set alone ("10.") takes no heading from the block above when that block sits directly under a CHAPTER or PART line; that block is the division's title. | 3350 (row 10 under "CHAPTER IV / FUNCTIONS OF THE CORPORTION") |
| `long_romanettes` | "(xxv)", "(xxx)", "(xxxv)", "(xli)" -- labels of three or more letters that are well-formed roman numbers below fifty -- open a clause. The romanette grammar ends every label in i, ii, iii, iv or ix. | 1695 (reg 8(2), (i)-(xli)) |
| `dash_closed_heading_guess` | With no contents list, "6. Recruitment, tenure of office ... of service.- Subject to ..." names the section up to the stop and dash. The name holds no sentence end and enacts nothing. | 1695 |
| `bracketed_rule_reference_division` | "FORM D [Rule 22(1)]" -- a division label plus nothing but a bracketed rule or section reference, without "see" -- opens the division even after a table cell with no full stop ("Total Area"). | 4318 |
| `preamble_not_in_auxiliary` | A "WHEREAS" recital inside an open form or schedule is that division's text, not the instrument's preamble. | 4318 (Form B's transfer deed) |
| `presidency_act_abbreviation` | "Bom.", "Ben."/"Beng.", "Mad." (Bombay, Bengal, Madras Acts) end no guessed heading: "3. [Repeal of Bom. Act III of 1879.] rep. by ..." is named from its contents row, not "[Repeal of Bom". | 1918 |
| `quoted_insertion_span` | Text an amending provision introduces ("the following sections shall be substituted:-") and quotes is that provision's text until the quotation closes, however many lines and blocks it spans: the quoted new sections 8-11 stay in the amending s.6 instead of opening as units of the amending Ordinance. Spans are found before the walk; one that does not close within 80 units and two pages, or that reaches the next amending section ("7. In the said Ordinance ...") or amending clause ("(ii) for Article 2 ..."), is refused. A decoded opening quote "―" counts only after whitespace (it is also a heading dash). | 1144, 1950 |
| `repeated_label_note_rows` | A contents row "N. Omitted vide ..." / "Rep. by ..." whose number repeats a real row's is the contents page's footnote, not a row ("2. Omitted vide Khyber Pakhtunkhwa Ordinance No.I of 1975." under row "2. Definitions."). v2's `contents_false_rows` covers only starred and "Subs./Ins. vide" notes. | 1413 (found by agent F), 1534 |
| `heading_prefix_of_sentence` | A contents name the printed text runs straight on from into a lower-case word ("Exemptions from patrol duty may be granted.-" against the contents' "Exemption.") is the sentence's start: the section keeps the contents name as its heading and the whole sentence as its text, instead of losing its first word. | 1534 |
| `subsection_then_clause_cut` | A line opening a sub-section number followed at once by a clause label and a capital ("(2) (i) Where recruitment ...") starts its own unit, so the sub-section opens and its clause (i) nests under it. | 1515 (drafted by agent F) |
| `part_range_label` | "PART I AND II", "PART IV to XIV. [Criminal Jails; ...]" -- the stubs of repealed parts -- are one division labelled by the range ("I AND II", "IV TO XIV"), not Part I headed "AND II" or a cross-reference run into the section before. | 904 (drafted by agent H) |
| `bracketed_repeal_stub_cut` | "7. [Exercise by Governor General in Council ...] Rep. by A.O., 1937." printed inside the block of the text before it, after a sentence end, starts its own unit (the grammar already reads it as section 7). | 3284 (ss.7 and 16) |
| `sequential_chapter_title` | "CHAPTER II / THE INSTITUTE" -- the next chapter's label and its upper-case title in one unit -- opens the chapter even after a unit that ends without a stop ("... declared to be teachers by regulations,"). v2's `sequential_chapter_heading` wants the label alone on its unit. The title holds no sentence punctuation and the number is one after the last chapter opened. With no chapter opened yet, a first printed chapter numbered I or II qualifies (doc 3002 prints no Chapter I). | 3672 (Chapter II after s.2(y)), 3002 |
| `lettered_part_label` | "PART A", "PART B", "PART D" -- the word PART in capitals and one capital letter outside the Roman numerals -- open a part labelled by the letter. The part grammar wants a Roman numeral or a digit, so only "PART C" (a hundred) opened and the other three ran into the part before. "PART A of the Schedule ..." (a lower-case word after the letter) is no part. | 1563 (Schedule Parts A-D) |
| `hyphen_suffix_labels` | Inserted sub-sections and clauses labelled with a hyphen -- "1[“(1-A). On such appeal ...", "(1-B)", "2[(a-i) “adjacent province’s waters” ..." -- open as units labelled "1-A", "a-i". The grammar reads digits with an optional letter, or one or two letters, so each ran into the unit before. A new line must open the label, and the line before must not end in a reference word ("sub-section / (1-A)"). 26 blocked documents print such labels. | 1794 (s.21 (1-A)-(1-E)) |

Widened in place on 2 October (every pinned released v4 tree rebuilt identically): `hyphen_suffix_labels` also admits a roman numeral with a capital suffix, "2[(xvi-A) “officer” means ..." (doc 4240 p8).
| `percent_led_item` | "10. 50% of the members of the board shall be women." -- a numbered item whose text opens with a percentage and a lower-case word -- starts its own unit when item 9 opens a line earlier in the same block. Every other cut wants a capital after the number, so the item ran into the one before. | 3794 (s.6's member list; found by agent I) |
| `contents_banner_block` | A block of nothing but contents-banner lines -- "CONTENT / Preamble / Sections" -- with the word CONTENT(S) among them marks a contents list. The singular banner was accepted only as a whole block, so the list's rows became sections 1-21. | 2875 (found by agent I) |
| `form_code_number` | "FORM PCT-2", "FORM PCT—13", "FORM PCT-I" -- a letter code joined by a dash to a number -- is one form label. v2's `quoted_form_letter` took "PCT" as the form's letter (its lookahead admits the hyphen), so every form was "FORM PCT" and its number went into its heading. | 3665 (Forms PCT-I to PCT-13) |
| `unbracketed_division_reference` | A form or schedule heading in capitals whose unit, or the next unit on its page, opens "See rule/section N" without brackets ("FORM PCT-8 / See rule 12 and 17.") opens the division even after a line ending in a colon or a signature. v2's `divisions_end_body` and v4's `bracketed_rule_reference_division` want the reference bracketed. | 3665 (Forms PCT-8, PCT-I) |
| `rs_line_item` | The tariff guard keeps a number after "Rs." in its cell; an item number of one or two digits followed on its own line by a capitalised word ("Rs. / 2. Arrears Rs.") is item N when item N-1 opens a line earlier in the same block. | 3665 (Form PCT-9's items 1-2) |
| `form_word_not_letter` | "FORM OF NOTING FOR DISHONOUR." -- a title line under a form's heading -- is no form lettered "OF": v2's `quoted_form_letter` refuses a letter that is an ordinary word (of, for, to, the, and, in, no, on, by). | 2344 (found by agent K) |
| `bracketed_sub_rule_reference` | A form or schedule heading in capitals whose unit, or one of the next two units on its page, reads "(See Sub-Rule (1) of RULE 12)" -- the sub-rule's number in brackets of its own -- opens the division even after a line without a stop ("Signature of Notary"). v2's `divisions_end_body` wants a digit straight after the word. | 2344 (Form IV; found by agent M) |
| `marked_first_subsection` | After a heading's dash (em, horizontal bar, or -- since 29 Sep, doc 3177 -- en dash), "(1) 1[Under the said Act], ..." -- a note marker between (1) and its capital -- parts (1) from the heading; `decoded_dash_first_subsection` admits the marker only before the bracket ("1[(1) The"), so (1) stayed in the section's text while (2) and (3) opened. | 3144 (s.18) |
| `marked_clause_cut` | A new line opening a note marker and a clause label -- "2[(l) “criminal offence” means ..." -- starts its own unit. Only sub-sections behind a marker ("1[(2) The") had a cut, so an inserted definition ran into the last item of the one before it (s.2(k)(v)). | 3144 (s.2(l)) |
| `quoted_schedule_heading` | A quote straight before SCHEDULE and its number -- "“SCHEDULE -II" -- opens the schedule when the unit is nothing but that heading or states the section it is made under ("(See section 4)"). The schedule grammar wants the word first, so the annexure's Schedule II (the text s.4 substitutes) ran into Schedule I's rows. | 2508 (found by agent L) |
| `serial_abbreviation` | "Sr." (serial) ends no guessed heading: s.4 "In the Sindh Finance Act, 1964, ... for entries at Sr. No.1, 4 and 5, ..." was named "... for entries at Sr". | 3442 (found by agent L) |
| `joint_schedule_heading` | "THE THIRD AND FOURTH SCHEDULES. [ENACTMENTS REPEALED. ENACTMENTS AMENDED.] Rep. by ..." -- two schedules named in one capitalised heading -- opens a schedule labelled "THIRD AND FOURTH SCHEDULES". No schedule grammar read it, so the stub ran into the Second Schedule's last item. Released doc 3187 (another copy of the Act, default profile) carries the stub inside its Second Schedule's item 5; that tree is not changed here. | 3132 |
| `bracket_not_division_label` | "ANNEXURE / (See regulation 14 )" -- a "(See ..." reference straight after the word ANNEXURE or APPENDIX -- is the division's reference, not its identity: the annexure was labelled "ANNEXURE (See" and headed "regulation 14 )". | 3302 (found by agent O) |
| `member_designation_row` | Inside a member list the open provision introduces (`introduced_member_list`), a row that continues the list, ends in a membership designation (Chairperson, Member, Member/Cum-Secretary ...) and carries no heading dash is the list's item even when its words support the contents heading of its number: s.6(1)'s row 7 "Chief Executive Officer of the Authority | Member/Cum- Secretary" had opened a fake s.7. | 3836 (found by agent O) |
| `quoted_definition_cut` | A new line opening "(N)" and a quote -- '(16) "commencement" used with reference to ...' -- starts its own unit when definition N-1 opened in an earlier block (no "(N-1)" opens a line before it in the same text) and not after a reference word. The sub-section cut wants a letter after the label, so eleven of doc 2299's definitions ran into the one before. A definitions list held whole in one section's text (released 3486, 3665, 3794) is left alone. | 2299 (found by agent Q) |
| `lowercase_suffix_subsection` | "(39-a)", "(50-a)", "(65-a)", "(17a)" -- digits and a lower-case letter -- are sub-section labels; the grammar admitted a capital suffix only. | 2299 |
| `lowercase_section_start` | "19." alone on its line followed by a lower-case word ("where, by any 3[Provincial] Act ...") starts its own unit, so the section no longer runs into the cross-heading before it. | 2299 |
| `quote_before_bracket` | '3"[28. The Provisions ...' -- a quote between the note marker and the amendment bracket -- is read with the quote after the bracket, as '3["28.' already was. | 2299 |
| `closed_marked_first_subsection` | A line opening "N[(1)]" and a capital ("7. / 5[(1)] Where this Act ...") starts its own unit; the marked sub-section cut wanted a letter straight after "(1)". | 2299 (s.7) |
| `letter_closing_finished` | A letter's subscription line ("Yours faithfully", "Yours obediently") ends the unit it closes, so a division heading after it opens; the line has no stop and read as an unfinished sentence, and "FORM 'B'" ran into Form A. | 1874 (found by agent P) |
| `new_section_paragraph_not_note` | A numbered paragraph "12. New section 24-A.– After section 24 of the said Act ..." -- 'New section X.' closed by a heading dash -- is enacting text, not the editorial note the footnote grammar's "New section" alternative reads it as. | 3785 (found by agent N); case-insensitive since 1 Oct for 4240's 'New Section' |
| `bracketed_section_number` | "1[11]. Meetings of the Authority.– ..." -- a renumbered section's number inside the amendment bracket -- opens section 11 (cut at a line start, and classified). | 3785 (found by agent N) |
| `schedule_title_reference_unit` | The unit after an uppercase SCHEDULE heading may hold the title line and the reference together ("SCHEME / [(See section 2(e)]", with a doubled bracket); the schedule then opens. | 4263 (found by agent Q) |
| `repeated_letter_clause` | "5[(ccc) “Institution” means ..." -- one letter printed three to five times -- is a clause label; the grammar read at most two letters. | 4263 |
| `guessed_heading_guard` | With no contents list, an amending sentence containing an abbreviation such as "Act No." or enacting words such as "shall be inserted" is provision text, not a guessed heading. The split uses the normalized text's own offset. | 1746 (ss.2, 5, 8, 9) |
| `quoted_item_label` | A line opening with a quotation mark immediately before `(v)` or `(5)` keeps the numbered item as a clause or subsection under its amending section; only the quote is excluded from the label. | 1746 (ss.3, 4) |
| `stray_close_extends_span` | When an instruction explicitly says "following new sections shall be inserted", a premature closing quote in the first inserted section does not terminate the insertion if later units carry its actual unmatched closing quote. The extension remains within 80 units/two pages and stops before the next amending opener. This narrow wording guard prevents changes to released doc 3442's separate quoted substitutions. | 1746 (s.5, inserted 20-A and 20-B) |
| `quoted_definitions_after_omission` | A block containing an omission-star stub followed by new-line numeric labels and quoted defined terms ending in `means` cuts each term into its own subsection. Without the cut, s.2's `(2) “Collector”` and `(3) “defaulter”` stayed inside the parent's text. The omission and definition shape are both required; all 69 previously released profile-pinned trees rebuilt unchanged before this release. | 2783 (s.2(2), (3)) |
| `referenced_table_heading` | "1[TABLE [see section 7(1)]" -- a TABLE heading with its substitution marker and a bracketed section, rule or regulation reference, and nothing else -- is a source-labelled table like a bare "TABLE": its numbered rows stay rows of the owning unit until the next contents-promised section whose heading matches, and the heading and the column heads after it are that owning unit's text (s.7(1)), not the text of a proviso that happened to be open. Without it the 37 rate rows of s.7 became sections 8 to 37, the first three under the contents headings of the real ss.8-10. All 84 pinned released trees rebuilt unchanged. | 4276 (s.7 TABLE) |
| `no_cut_after_number_abbreviation` | No unit is cut straight after the abbreviation "No.": s.29(a) of the Stamp Act lists Schedule I articles as "No.    2. (Administration Bond), No. 6 ...", and the sentence-end cut opened the article numbers as units of the Act. All 84 pinned released trees rebuilt unchanged. | 4453 (s.29(a)) |
| `page_first_running_header` | "6 \| P a g e THE STAMP ACT, 1899 (ACT II OF 1899)" -- the page number first, then a title ending in the bracketed Act number, at most 140 characters -- is page furniture; the existing test reads only the order "(ACT ...) N \| P a g e". Without it all 79 page heads of doc 4453 stood in the text of the unit each page continues. All 84 pinned released trees rebuilt unchanged. | 4453 (79 page heads) |
| `whole_schedule_quote` | A quotation that opens with a SCHEDULE heading after amending words naming a Schedule ("for the existing Second Schedule, the following shall be substituted, namely: “SECOND SCHEDULE [see ...]") is held as the amending clause's text until its closing quote, beyond the usual 80-unit / two-page bound; it may open past the next page's running-head units, and only a numbered amending opener ("7. In the said Act ...") stops it -- the Schedule's own rows print lower-case instructions such as "(i) for Umrah services; and". Without it the substituted First and Second Schedules of the Sales Tax on Services Act (pp9-32) became parts and sections 11-37 of the Finance Act, two of them under the contents headings of the real ss.11-12. All 84 pinned released trees rebuilt unchanged. | 4433 (s.10(r), (s)) |
| `amendment_items_owner` | A section whose text ends "shall stand amended as under:-" (or "as follows") owns the numbered items that follow as its rows, through the same path as a source-labelled TABLE. The list closes at the next contents-promised section whose heading the text supports, or -- because a margin heading may be emitted after its section -- at the next promised label whose text is not itself an amending instruction ("In section 3, ...", "For the words ..."). Without it items 3-6 of doc 715's s.2 became sections 3-6, item 3 under the contents heading "Saving." of the real s.3, which became a clause of item 6. All 84 pinned released trees rebuilt unchanged. | 715 (s.2 items 1-6) |
| `in_respect_of_not_opener` | Inside a quoted insertion, "(a) in respect of ..." is a row of the quoted text, not a new amending instruction: the clause-form opener ("(ii) in Article 2, ...", doc 3442) no longer matches "in respect of". Without it doc 4276 s.6(d)'s substituted Serial No. 10 -- both quotation marks printed -- broke at its first row and rows (a)-(f) became clauses of s.6. All 84 pinned released trees rebuilt unchanged. | 4276 (s.6(d)) |
| `parenthesised_letter_label` | A line opening "6(A).", "1[6(A).", "12(A) BANK GUARANTEE" -- a number with a capital letter in brackets, then a capital word -- opens a provision labelled exactly as printed ("6(A)"). The grammar opened "6A." but never the bracketed form, so each inserted Schedule I article of doc 4453 ran into the one before it; a reading dropping the brackets would have changed the printed citation. All 86 pinned released trees rebuilt unchanged. | 4453 (Sch.I 6(A), 6(B), 11(B), 12(A), 12(B), 22(A)) |
| `clause_then_romanette_cut` | A line opening a lettered label followed at once by a romanette label and a word ("(a) \n(i) when executed ...") starts clause (a); the clause cut wants a word after the label, so (a) stayed in the article's own text and its (i)/(ii) attached to the article. All 86 pinned released trees rebuilt unchanged. | 4453 (Sch.I Arts. 33, 35) |
| `suffixed_decimal_label` | A rule number of an inserted chapter -- "11-A.2.", "11-A-9." -- or a decimal number with a letter part -- "7.2.A" -- is one label, kept as printed. The section grammar took "11-A" / "7.2" and left the rest in the text, so every rule of the chapter shared one label. All 87 pinned released trees rebuilt unchanged. | 2418 (rules 11-A.1 to 11-A-29) |
| `rule_range_not_opener` | A line opening "Rules 9.12 to 9.27 ..." -- a rule prefix followed by a range ("to", "and", "&") -- is a reference, not a rule: the rule-prefix cut opened a fabricated rule 9 inside rule 11-A.6. A single "Rule 9. ..." still opens. All 87 pinned released trees rebuilt unchanged. | 2418 (rule 11-A.6) |
| `sequential_part_heading` | A PART heading whose label is the next in sequence after the last part opened in the same appendix, schedule, annexure or form (B after A, D after C, II after I) opens even after a line that reads unfinished -- a table row ending in an amount such as "10000/-" -- and "Part-B" in mixed case is read like "PART B". The part's title ends at a blank line followed by a sentence, which becomes the part's text. Without it doc 4433's "Part-B", "Part-D" and "PART-II PARKING VIOLATIONS" ran into the rows before them. All 88 pinned released trees rebuilt unchanged. | 4433 (Appendix II Parts B, D; Appendix IV Part II) |
| `hyphen_letter_division_label` | "CHAPTER VII-A" or "FORM II-A" -- a Roman numeral joined by a hyphen to one capital letter, alone on its line -- is the division's whole label. The division grammar ate the hyphen as a separator and opened a second Chapter VII / Form II headed "A", whose regulations collided with the real chapter's. | 4330 (Chapter VII-A, Form II-A) |
| `lettered_paragraph_sequence` | After a block printing "(N)-A. Capital ..." (doc 4330 reg 53: "21[(2)-A. Proper arrangements ..."), blocks opening "B.", "C.", ... in printed order, up to the next "(n)" or numbered provision, open paragraphs labelled as printed under sub-section (N); "(2)" before "-A." is that sub-section. The run is found per document before the walk; a lone "B." anywhere else is untouched. Without it A stayed as "-A. ..." in (2) and B-K ran into clause (d) and a proviso. | 4330 (reg 53(2) A-K) |
| `quoted_schedule_word_owner` | An amending unit whose text ends "the following shall be substituted- "SCHEDULE"" -- only the heading word quoted -- owns the numbered rows that follow, through the same path as a source-labelled TABLE (closed by the next contents-promised section whose heading matches; with no contents list the Schedule runs to the end of the copy). Without it doc 3056's substituted Schedule articles 3-31 became sections 3-31 of a two-section Ordinance. The quoted heading may be "THE SCHEDULE" followed by "(See section 3)" (doc 1087), and the rows also end at the amending Act's own next section -- the owning section's number plus one, opening "In the <...> Act, ..." -- where no contents list can close them. All 91 pinned released trees rebuilt unchanged. | 3056 (s.2(viii)), 1087 (s.3(ii)) |
| `schedule_word_rows_own_items` | Under quoted_schedule_word_owner, each row is pushed on the walk's stack and a sub-section or clause opened while a row of that owner is open goes below the row: a substituted Schedule's article owns its "(a)", "(1)", "(i)" items. Without it ~170 items of doc 3056 unwound past s.2(viii) and became clauses and sub-sections of s.2 (Art.5's "(2)" became a fabricated s.2(2)). All 91 pinned released trees rebuilt unchanged. | 3056, 1087 |
| `sequential_form_label` | A form label alone on its line that continues the sequence of the form labels printed before it in the document (C -> C1, C1 -> C2, C2 -> D) opens even after an unfinished line ("Form C1" after Form C's witness block). The sequence is read per document before the walk. | 4317 (Forms C1, C2) |
| `first_lettered_part_in_schedule` | Inside a schedule with no part yet, a unit that is nothing but a part label of value one (A, I or 1), followed on its page by a unit opening "N. ", is the schedule's first part -- even after an item ending ";", which reads as unfinished (`sequential_part_heading` then opens B, C, D). | 4353 (Schedule-II Part-A) |
| `sequential_schedule_heading` | A schedule label alone on its unit, first on its page, numbered one after the last schedule opened (II -> III), and followed on its page by a capitalised unit, is that schedule -- even after a lower-case table cell and with a title-case title. Without it Schedule-III's item 1 became a row of Schedule-II Part E. | 4353 (Schedule-III) |
| `quoted_sequential_form_label` | `sequential_form_label` with a printer's quote on either side of the letter (FORM 'A' -> FORM "B"); Form B had run into Form A's signature lines. | 3108 (Form B) |
| `decimal_rule_resumes` | With no contents list, inside a form, schedule, appendix or annexure, a decimal rule number of the chapter of rules opened before ("7.3" after 7.1-7.2.D), one to three above the highest opened, resumes the body. Rules 7.3-7.23 printed after Forms A-D had become rows of Form D. | 3108 (rules 7.3-7.23) |
| `appended_form_at_page_top` | A form label alone, first on its page, before a capitalised unit, whose code the earlier text cites as "Form <code> appended" ("Form L-37-A appended hereto"), opens even after a line ending ":-". | 3108 (Form L-37-A) |
| `letter_number_form_code` | "FORM L-37-A" -- FORM, one capital, a hyphen, 1-3 digits and an optional hyphen and capital, alone on its line -- is one label (it was "FORM L" with rest "37-A"). | 3108 |
| `label_only_heading_none` | Without a contents heading, a guessed heading made only of bracketed labels ("7.2.D (1) (a). In this rule ...") is no heading; the text keeps the labels. | 3108 (rule 7.2.D) |
| `not_reproduced_text` | Without a contents heading, a guessed heading opening "Not reproduced" is the placeholder rule's text, not its heading. | 3108 (rules 7.13A, 7.17, 7.19) |
| `enactment_chapter_reference` | Inside a schedule, appendix, annexure or form, a chapter label whose rest names another enactment ("Chapter VIII, Pakistan Penal Code.", comma optional, the name may wrap) is row text, not a division; doc 2221's First Schedule had opened eight root-level chapters that pulled its rows out of the schedule. | 2221 (First Schedule) |
| `repeated_label_section_note_rows` | Contents rows such as "N. Section 21-A, added vide ...", "Section 25 Omitted vide ...", "Omitted vid ..." whose number repeats a real row's are the contents page's footnote and are dropped from the contents; the real row keeps the heading. | 2221 (p2) |
| `left_column_margin_heading` | With no contents list, a page set in three columns (margin heading / number / text): a left-column block (x1 < 320) of 1-7 lines, capital first, ending with a stop, with no quotation mark and no operative word, printed level (3 pt) with a block that opens a section, is that section's heading. Only where such a level pair exists in the document, heading lines before "N." in one block -- or the last lines of the previous piece after a sentence or quotation end -- name the next section. Doc 1144 shows no level pair and is unchanged. | 4399 (ss.1-66) |
| `whole_section_quote` | An amending unit "for Section N, the following shall be substituted" or "the following (three) new sections shall be inserted/added" whose quotation opens '“N. Capital' holds the quotation past the 80-unit / two-page bound, stopped only by a numbered amending opener; if the quote count has not closed there, the quotation ends at the last unit before that opener ending with a closing quote. With "new sections" it runs on over further quoted sections. | 4399 (s.3's quoted s.2, pp1-38; s.65's 90-92) |
| `numbered_marked_first_subsection` | A block opening 'N.' then '(1)' followed (same or next line) by a note marker, '[' and a letter -- '4. / (1) / 6[The Provincial Government] ...', no heading dash -- is cut after the number, so (1) opens; `marked_first_subsection` cuts only after a heading's dash. | 1295 (ss.2, 4, 5, 7, 11) |
| `quoted_first_definition` | A new line opening '(1)' and a quote, after text in the same block ending in '--', an em/en dash or a colon, starts its own unit ('In this Act-- / (1) / “furnace” means ...'); `quoted_definition_cut` takes only N >= 2. | 1295 (s.3) |
| `marked_suffixed_definition` | A new line opening a note marker, '[', a suffixed label '(1A)' / '(1-A)' and a quote ('2[(1A)] “Flue” ...') starts its own unit. | 1295 (s.3(1A)) |
| `bare_trailing_label_cut` | A label alone on the last line of a block ('20. Regulations. / 21.'), whose predecessor opens a line earlier in the block, is cut off, so the previous contents row's heading does not carry it. | 2452 (contents row 20) |
| `apparatus_over_margin_heading` | A block a reviewed page reading names in source_apparatus_blocks is not also a margin-heading block; it had been re-roled heading and hung on the page's first unit. | 2452 (s.2(viii), s.13(1)(m), statutes 5(3), 6(4)) |
| `dotted_omission_stub_cut` | A new line opening a bracketed note number, a section number and its stop, followed (same or next line) only by three or more dots or ellipsis characters and ']' ('5[3. .........]'), starts its own unit; the mid-block cut wants a letter or asterisks after the number. | 3805 (s.3) |
| `ordinal_schedule_reference` | An upper-case ordinal FIRST ... TENTH before SCHEDULE, with a division reference ('(See Section 4)') in the unit or the next two units on its page, is the division even after a unit with no stop. | 3805 (Second and Third Schedules) |
| `enacting_formula_not_member_list` | A provision whose text ends in the enacting formula ('It is hereby enacted as follows:-') introduces no numbered list, so `introduced_member_list` does not take '1.' as its item. | 4296 (Preamble (f)) |
| `dotted_contents_row_cut` | A new line holding only a number, its stop and four or more space-separated dots ('26. . . . . .') starts its own unit, so the previous contents row's heading does not carry it; unspaced dot leaders (a form blank '2.........', doc 1874) do not match. | 4296 (contents row 26) |
| `last_promised_section_after_schedule` | Inside a schedule, a plain-number label the contents promises and the body has not produced resumes the body when it is the contents' last and highest row, every other row is a plain number already produced, and the unit opens with that row's contents heading (rule 12 'REPEAL' printed after the Schedule). | 3142 (rule 12) |
| `serial_column_header_owner` | A section whose text ends with an upper-case 'S.NO.' header plus two or more column words owns the following '01'/'1' rows as heading-less clause rows; a schedule opening clears the owner. | 3142 (rule 11) |
| `colon_closed_contents_heading` | Where the body closes the contents name with a colon exactly at the name's length ('Ground for penalty:'), the printed heading ends there and does not run on to the next colon. | 3142 (rule 3) |
| `contents_row_decimal_cut` | A new line opening 'N.M Capital' starts its own unit when that label and first word match a decimal contents row printed alone in its own block in the same document. Known limit: in doc 4416 (decision-blocked) a contents run leaks into a heading; a guard is needed before 4416 relies on it. | 3103 (4.1-4.4, 5.1-5.6) |
| `titled_appended_form` | With no contents list and no division open, after two or more sections, a unit that starts its block and is the first on its page, whose first line is an upper-case title of two or more words with no label, opens a form labelled with that title -- only when an earlier unit cites 'the form attached/appended/annexed to these rules / this Order'. | 1385, 3064 |
| `definition_lead_not_heading` | An interpretation lead-in ('In this Act/Ordinance/Order/these rules ...') alone on its line is never the section's heading. | 3064 (s.2) |
| `schedule_amendment_item` | Inside an open schedule, a block 'N. / In section X, ... shall be substituted/inserted/omitted/deleted/added' (the verb outside quotes) whose N follows the schedule's last item is a schedule item, not an amendment footnote, at unit build and in the walk. | 2739 (Schedule items 2, 5-9, 12-13) |
| `schedule_item_rows_in_order` | A contents run restarting at '1.' after the main rows links its row 1 to the schedule's first numbered item when the last linked row precedes that schedule; the following rows then link in clause context. | 2739 (contents p2) |
| `quoted_part_span` | 'in Schedule N, for Part I, the following shall be substituted' whose quotation opens '“PART—I' is held like whole_section_quote, stopped only by a numbered amending opener (which may carry its moved margin heading); if the quote count has not closed there, it closes at the last unit ending with a closing quote. | 2621 (ss.13, 14(a)) |
| `body_start_without_contents` | Where the ordinary parse finds no contents list and the region before a reviewed source_body_start_block prints no contents marker, that block is still the body boundary and the blocks before it are preface (not contents); no contents list is invented. | 4639 (Gazette copy: Act XL before Act XLI) |
| `ordinal_quoted_schedule_word` | A section ending 'the following shall be substituted:- "TWELFTH SCHEDULE" (See section 116-A)' -- an ordinal FIRST..TWENTIETH quoted Schedule word, with an optional section reference -- owns the following numbered rows as its table rows (beside `quoted_schedule_word_owner`). | 255 (s.3, rows 1-28) |
| `repeated_decimal_label_cut` | A decimal label of two to four levels printed after a blank line mid-block starts its own unit when the same label opens a line in another block of the document (its contents row). | 2324 (1.2, 1.4.2.1, 2.4, 2.12.1) |
| `dotted_other_heading` | '2.7 / Other Leaves:-' -- a decimal label before a capitalised 'Other' and a capitalised word -- is a heading, not the tariff value 'Others' that `_DOTTED_VALUE_REST` refuses. | 2324 (2.7) |
| `indented_list_item_continues` | An indented item N whose words do not support contents row N, printed in the same column (x0 within 3 pt) as the open clause N-1, continues that list instead of opening section N. | 2324 (1.2's items 2-4) |
| `schedule_title_first_statutes` | 'THE SCHEDULE' followed on the same page by 'THE FIRST STATUTES' names one schedule: the empty SCHEDULE node is relabelled and stays the open container. | 2731 (p19) |
| `statute_rows_margin_evidence` | First Statutes contents rows are corroborated also by the margin-note column printed beside the statute on its page. | 2731 (rows 37-47) |
| `bare_number_schedule_name_row` | A block that is only a number and an ordinal Schedule name ('31. / First Schedule.') is one contents row, not a number and a division. | 2731 (contents row 31) |
| `side_noted_definition_cut` | A new line opening '(N) “Term”.' followed by the same term quoted again and means/includes/implies (a side-noted definition) starts its own unit. | 3649 (s.3) |
| `numbered_schedule_form` | Inside a schedule headed '...OF FORMS', a line 'No. N.—UPPER-CASE TITLE' opens a form labelled 'No. N' under that schedule, headed by the title. | 3649 (Forms No. 1-14) |
| `misprinted_chapter_word` | 'CHAPER-IV' (a misprint of CHAPTER) opens Chapter IV. | 4003 (p14) |
| `misprinted_form_word` | A line that is only 'FROM A' / 'FROM ‘C’' (a misprint of FORM, the rules citing Form A-C) opens FORM A-C and counts in the form sequence. | 4003 (pp25-27) |
| `quoted_hyphen_form_label` | 'FORM ‘F-1’' and 'FORM-‘I’' are labelled FORM F-1 and FORM I (not three forms 'FORM F' and a 'FORM' headed ‘I’). | 4003 (pp30-32, 35) |
| `appendix_number_label` | A line holding only 'APPENDIX [-/.] [NO.] <I.1 | 1.2 | II. 1 | III>' is labelled 'APPENDIX <number>' and is a division even after an unpunctuated form line (upper case only). | 3803 (Appendices I.1-III) |
| `lowercase_hyphen_label_cut` | A new line '(1-a)' followed by a capital opens its own unit (unless the text before ends in a reference word). | 3803 (rule 6) |
| `ditto_item_cut` | A new line '(N) -----do' opens a unit when '(N-1)' opened earlier in the block. | 3803 (rule 21(4)) |
| `dotted_nameless_contents_row` | A contents row 'N. / ........ / N+1.' (a row printing only dots) is cut before N+1. | 3803 (contents row 21) |
| `number_abbreviation_line_end` | `no_cut_after_number_abbreviation` still cuts when the line ending in 'No.' itself opens item N-1 and the next line opens item N ('2. National Identity Card No. / 3. District.'); doc 4453's 'namely:-- No. / 2. Administration Bond' keeps no cut. | 3803 (Appendix 1.2) |
| `definition_lead_not_name` | An interpretation lead-in ('In these rules ...') names no other section, so the contents heading ('Definitions.') applies. | 3803 (rule 2) |
| `contents_leader_page_strip` | A contents name ending in leader dots and a page number is stripped to the name. | 4447 |
| `omission_stub_closes_table` | A stub of the next promised section whose contents row is a disposition closes an open table (s.33's penalty table ends at '506[33A***]'). | 4447 |
| `fbr_definition_label` | Definition labels with a note marker or a 2-3 letter suffix open; a bare label line only where the block also prints such a label. | 4447 |
| `label_then_marked_text_cut` | '(x)' followed by 'N[' text, and '691[(1)] 692[The', start units. | 4447 |
| `marked_proviso_cut` | 'NNN[Provided' starts a proviso. | 4447 |
| `bare_marker_label` | A note marker glued to a label ('713(d) persons') is read as the label. | 4447 |
| `multi_letter_subsection` | '(29AA)' is a sub-section label. | 4447 |
| `marked_chapter_heading` | 'N[Chapter-I' (dash required) opens a chapter. | 4447 |
| `marked_lettered_omission_stub` | 'N[(iv) ***' (unspaced stars) is an omission stub unit. | 4447 |
| `bare_bracket_clause_cut` | '[(a) word' and '[(1B) Capital' start units (not after a split note marker). | 4447 |
| `inserted_three_letter_clause` | '(caa)' is a clause label. | 4447 |
| `closed_marked_clause_cut` | 'N[(d)] word' starts a clause. | 4447 |
| `four_letter_section_suffix` | '30DDDA.' is a section label. | 4447 |
| `bare_omission_stub` | '(4) 
***' and '600[601(2A)***]' are omission stubs. | 4447 |
| `e_prefix_section_start` | '52A. e-intermediaries' opens s.52A (lower-case 'e-' word). | 4447 |
| `high_ordinal_schedule` | EIGHTH..FIFTEENTH SCHEDULE behind a note marker with a '[See ... section N]' reference, or over only its omission stub, opens the schedule. | 4447 |
| `column_head_line_cut` | An 'S. No ... (1) (2)' column-head line starts its own unit. | 4447 |
| `schedule_tables_annexes_parts` | Inside a schedule, Table-N, Annex(ure)[-X], CONDITIONS headings and 'Procedure and conditions' are Parts; 'Notes:--' is a Part; 'Note:' is an explanation. | 4447 |
| `roman_stub_item_cut` | A roman item omission stub starts its own unit. | 4447 |
| `stub_row_cut` | A table row omission stub starts its own unit. | 4447 |
| `schedule_table_rows_own_items` | A schedule table's numbered rows own their lettered/roman items. | 4447 |
| `capital_letter_item` | '(A).', bold capital categories (no colon, no closing stop) and rate bands 'A. Not exceeding US$ 500 ...' are items. | 4447 |
| `figure_led_item` | A numbered item whose text starts with figure-hyphen-capital ('10. 3-D Cardiac') or only a heading number ('143. 9937') opens. | 4447 |
| `four_digit_marker_label_cut` | A romanette behind a 4-digit marker with its label alone on the line ('1010[(ix)') starts a unit. | 4447 |
| `range_stub_row` | Range/joint stub rows ('955[35 to 42]. [...', '2 & 2A ***]', '[15& 15A ***]') are one omitted row each. | 4447 |
| `marked_quoted_label` | '1020[“(4)' -- a quoted label behind a marker -- starts a unit. | 4447 |
| `stacked_marker_row` | '909[910[13. ***' -- stacked note markers before a serial -- is a row. | 4447 |
| `schedule_division_heading_lines` | A high-ordinal schedule or schedule Part takes as its heading only its '(...)' subtitle and '[See ...]' lines (or a short ':' caption for a Part); the TABLE caption, intro sentence or grid stays text. | 4447 |
| `unnumbered_tail_provision` | A reviewed `source_unnumbered_section_openers` entry whose `after_section_label` is `__AFTER_SCHEDULE__` closes the open top-level SCHEDULE and opens an Act-level provision at the root: kind `section`, label the printed lead word ("Repeal"), heading the same, text after `source_prefix`. It fails closed unless no grammar opener matches the block, a schedule is open, the label carries no numeral, is not in the contents and is not already used, and label, heading and prefix share one printed lead. No number is invented; the label with no numeral is the "unnumbered" marker (docs/SCHEMA.md, `provision`). Inert without such an opener; under v3 or default that opener is refused. | 128 (p5 "Repeal: ... are hereby repealed.", owner decision 2026-10-06) |
| `unnumbered_root_provision` | The same reviewed opener with `after_section_label` `__ROOT__`, where no unit is open yet and there is no contents row. With a word label it opens a root-level `section` labelled by its printed caption or lead word (doc 268 p1: "AMENDMENTS" over "For the existing Schedule the Schedules appended here to shall be substituted"). Label, heading and prefix must share one printed lead, and the label carries no numeral. A numeric label is allowed only as "1", with an empty heading (none is printed), and only when the opener carries `owner_decision` {export, document_id, question_id}. That citation's shape is checked by the parser. That the export holds the answer is checked by `tools/record_curation_patch.py` and by the multi-instrument dry run, through `owner_decision_answer` in `nizam/workers/segment.py` (doc 268 p3: the 1998 Order's unnumbered para 1, owner decision 2026-10-06 q1 "para 1 / para 2"). A later unit of the opener's block ("2. He is further ...") is read by the grammar. A display "SCHEDULE" directly after such a provision opens the Schedule when the provision's text names the Schedules "appended" or "annexed": the clause is the evidence that `unlisted_display_schedule` otherwise takes from two opened units. Without `owner_decision`, a numeric `__ROOT__` opener is the old contents-backed opener, unchanged. Under v3 or default, a word-label `__ROOT__` opener is refused. | 268 (expressions 1 and 2) |
| `colon_closed_heading_guess` | With no contents list and no other guessed name, "32. Fee for revised plan and service designs: A sponsor shall ..." (or "13. Maintenance of the farm: - The owner ...", doc 3110) is named up to the colon: a capitalised span of 4-110 characters with no sentence end and no operative word, closed by a colon before a capital. | 4317 (rules 32-35) |
| `starred_letter_stub_cut` | A new line opening a clause letter '(x)' followed (same or next line) by '*' -- an omitted clause printed as its label then stars, '3[(a) / * * * / (b) / * * * / (c) ...' -- starts its own unit when '(x-1)' opens a line earlier in the block; every clause cut wants a letter after the label, so (b)-(e) stayed inside (a). | 4490 (s.104(1), p83) |
| `status_row_order_only` | A contents row whose name is only a status word ('Omitted', 'Deleted', 'Repealed') carries no heading evidence: it is not linked by heading containment (which had linked Act row 25 'Omitted' to Order XLI rule 25, '... has omitted to frame ...') and is left to the bounded-order pass between its linked neighbours, which links it to its own stub. | 4490 (contents rows 7, 8, 25; Order XXI rows 4, 23) |
| `order_rule_owns_subrules` | Inside a schedule, while a numbered rule (a clause whose parent is an Order) is open, its sub-rules '(1)', '(2)' and clauses are placed relative to that rule; they took the fixed sub-section depth, unwound past the rule and became the Order's children. | 4490 (First Schedule, Orders I-LI) |
| `marked_order_heading` | An inserted Order printed behind its note marker, alone on the line -- '2[ORDER IV-A', '5[ORDER XXVIIA', '1[ORDER LI' -- opens the Order; the order grammar wants 'ORDER' at the line start, so its rules ran on under the Order before. | 4490 (Orders IV-A, IX-A, IX-B, XXVIIA, XXXIII, XLIV, XLV-A, LI) |
| `amendment_word_heading_not_note` | A unit opening 'N.' then 'Substituted', 'Inserted' or 'Added' and a lower-case noun phrase (not 'by/for/ibid/in/vide') closed by '.' and an en or em dash -- '20. / Substituted service.– 1[(1) ...' -- is a rule's heading, not the footnote grammar's 'N Substituted ...' note. | 4490 (Order V rule 20, p111) |
| `ordinal_schedule_closes_part` | An ordinal schedule heading ('[THE] FIRST' ... 'TENTH SCHEDULE') closes an open body Part (one not itself inside a schedule, form, appendix, annexure or order): THE FIRST SCHEDULE after s.159 had nested under Part XI. | 4490 (First to Fifth Schedules) |
| `appendix_numbered_form` | Inside an appendix, a form number alone on its line -- 'No. / 1.', 'No.  23.', 'No 15.', '4[No.  15-A.', '1[No. 1A. * *]', 'FORM No. 7B.', '1[Form No. / 13 (Order IX-A)', 'No.  1[9].', 'No.  1[10]' -- opens a form labelled 'No. N' ('FORM No. N' when FORM is printed), a child of the appendix or of its printed group sub-section ('(3) PLAINTS.'). Such a line is never a running header (the same 'No. 12.' recurs in several appendices), it opens even after the previous form's unpunctuated last line, and the form keeps no heading: what its block carries after the number is the form's text. | 4490 (Appendices A-H) |
| `form_schedule_caption` | Inside an appendix, a bare 'SCHEDULE.' / 'Schedule.' / 'The Schedule.' is the form's own caption (the property schedule annexed to a decree or warrant), not a schedule division; it had opened sixteen root-level schedules. | 4490 (Appendices D, E) |
| `appendix_form_paragraphs` | Inside an appendix, while a numbered paragraph of a form is open, its '(1)', '(a)' items are placed under it; a capitals-only group heading '(4) WRITTEN STATEMENTS.' is not an item. | 4490 (Appendices A-H) |
| `connective_not_clause_label` | A line opening '(or)' / '(and)' -- an italic connective in a form -- is a word, not a clause labelled 'or'. | 4490 (App A(4) form No. 13, p288) |
| `unlabelled_schedule_opener` | A reviewed `source_unlabelled_schedule_openers` entry {source_block_id, label, source_text, owner_decision} opens a top-level schedule at that exact block, for a table the copy prints with no heading. The block's text must equal `source_text`, the label must be "SCHEDULE" (the only label the owner's word supports), nothing may be open but the root or a preface, no schedule may have opened before, and `owner_decision` must cite one answer; the block's own text (the column heads) is the schedule's text and the rows then open under their printed serials. It raises if the opener is not reached exactly. Inert without the override. The recorder checks the block's text and that the export holds the answer. | 691 (p9; owner decision 2026-10-06 q2 "rows-by-serial": the 1997 recruitment table is the Rules' Schedule) |
| `quoted_table_row_text` | A block named in a reviewed `source_quoted_table_row_blocks` list (a page-read row of a table an amending notification quotes) is kept whole: the cells' own enumerators ('... Journal. (i) By promotion ... (ii) If none ...') are not cut into units of the amending paragraph, and the row stays that paragraph's text. Inert without the override. | 691 (pp1-8, the 2011 and 2007 notifications' quoted rows) |
| `range_repeal_stub` | '8. / to 10. [Suits against Revenue-officers. ...] Rep. by the Bombay Revenue Jurisdiction Act, 1880' -- a range of numbers, then a bracketed former heading and Rep./Repealed/Omitted -- is one section labelled as printed, '8 to 10', cut after the sentence end before it; it takes no guessed heading (the former headings and the note are its text). | 1003 (p4; owner decision 2026-10-06 q3 "one-stub") |
| `range_contents_row` | A contents row 'N-M. (Repealed.)' / 'N-M. Omitted' is a row labelled as printed, 'N-M', cut at its line start, so it no longer runs into the previous row's heading. A page-read found_elsewhere reading links it to the range stub. | 1003 (contents p1, row '8-10') |
| `printed_heading_override` | A reviewed `source_printed_headings` entry {label, source_block_id, heading, use, owner_decision} names one top-level section (not inside a schedule or other auxiliary division) and the block printing the words: with `use` "heading" the words become its heading, with "marginal_note" they are kept as `provision.marginal_note` beside the contents heading. The words must be printed in that block (whitespace-normalised) and exactly one section must carry the label; otherwise it raises. Nothing is inferred; inert without the override. | 1003 (owner decisions 2026-10-06 q2 ss.7, 11 printed; q1 s.12 margin note kept); also serves 999 |
| `order_suffix_label` Extensions (9 Oct, docs 1692, 1949, 1827; owner q1 keep-both): (1) a later print that a reviewed group names by its block is not demoted at open time after the last contents row; (2) a reviewed contents link naming a label kept twice links the first print, and a contents label printed k times whose k body prints are a group links row i to print i; (3) a group whose prints are top-level sections in different top-level parts or chapters is applied as a sibling group is. | A reviewed `source_order_suffix_labels` entry {kind section\|article\|subsection, label, source_block_ids, owner_decision} names, in print order, every sibling print of one label that the owner kept citable. Nothing in that group is demoted and no S7 candidate is written; the label stays as printed on each print; each records its print-order occurrence, and the later prints' paths end `__o2`, `__o3` (cited "s.2 (second)"; docs/SCHEMA.md "Order suffix"). In a preamble-shape contents alignment the kept prints are one numbering slot, and the row is looked up under the label (its heading picks the print). Fail-closed: the blocks must be exactly one sibling group's prints in print order, and the entry must cite one owner answer (the recorder checks the export, and the blocks must be on the reading's page); otherwise it raises. Inert without the override. Sub-sections (8 Oct): a `subsection` entry is matched by a pass over every node's sub-section children before the section pass, with the same refusals; the second print's path ends `ss_2__o2` ("s.5(2) (second)"). Entries are distinct by the prints they name (the recorder: no block in two groups; the worker's merge keys on kind, label and first print), so two sections may each keep a duplicate (2). | 999 (p2, two sections 2; owner q1 keep-both, 7 Oct order suffix); 1034 (s.5, two sub-sections (2); owner q2 keep-both, 7 Oct); 1457 (s.20, clauses (i) and (ii) printed twice: kind `clause`, matched in the same pass as sub-sections; owner q4 keep-both, 8 Oct; every entry's answer must be 'keep-both') |
| `named_schedule_row` | A reviewed `source_named_schedule_rows` entry {source_block_id, schedule_block_id, label, source_text, owner_decision} opens a `clause` under the open top-level schedule (the one whose first block is `schedule_block_id`) at that exact block, for a table that prints no serial column and identifies each row only by its post. The block's text (after its reading) must equal `source_text`; the label is the printed post cell verbatim (with its grade), printed exactly once in the row, holding a word of two letters or more and not a bare serial or enumerator; no sibling may carry it; the entry must cite one owner answer. The block is kept whole (its cells' own '1.', '(i)', 'a)' open nothing) and all of it, the post cell included, is the row's text: no printed word is removed and no number is supplied. The path is `…cl_<full label slug>__nr` (never cut at 40 characters; a collision raises), and the `__nr` marker is what a renderer reads (docs/SCHEMA.md "Named schedule rows"). It raises if an entry is not reached exactly. Inert without the override. The recorder checks the export holds the answer and that its choice asks for rows by post name (`NAMED_SCHEDULE_ROW_CHOICES`), that the row block is on the reading's page, and the text after the reading is applied. | 1078 (pp3-4, four posts; owner q1 "schedule-rows-by-post"), 1121 (pp2-4, twenty posts; owner q2 "rows-by-post"), 1106 (owner q3 "rows-by-group": rows with no serial under a group caption, which becomes their parent; the label drops the cell's closing stop) |
| `contents_opener_later_units` | A block opened by the contents-evidenced reviewed opener (`source_unnumbered_section_openers`, after_section_label `__ROOT__`, label from the contents row) is cut into units before the grammar runs; once its opener has been applied, the block's later units ('(1) These rules may be called ...', '(2) They shall come into force ...') are read by the grammar as usual and open sub-sections under the opened rule, as the root-path opener already allows. They used to re-enter the opener branch and raise. The first unit is still checked in full (contents row, heading, prefix) and 'override not reached' is untouched. | 1337 (p2 rule 1 'Short title and commencement.- (1) ... (2) ...'; owner q1 'contents-number') |
| `reviewed_contents_alignment` | A reviewed, page-read `source_contents_row_links` list [{ordinal, printed_label, unit_label or null, owner_decision}] is the contents alignment: each ordinal must be a printed contents row with that printed label; null means the row names no numbered unit (it is then left to a contents reading); no unit may be named twice; it may not be combined with an inferred alignment, and the profile's own `contents_heading_alignment` inference is not run over it; every row given a unit must end linked to the one top-level section or article with that label, or it raises. The printed labels stay the stored evidence. Inert without the entries. The recorder checks the shape and that the export holds the cited answer; patches carrying the list must agree. Since 9 Oct (docs 1889, 1635, owner q1 "body") a link may carry `index_row: true`: the row is linked to its unit, but its words never become the unit's heading, because a compiler's index names a topic, not the rule's heading. | 1368 (p1: 'Preamble.' is row 1 and rows 6/7 name ss.6/5 -- the contents swaps the two schedule amendments; owner q1 'body', rows linked by name); 1889, 1635 (index rows) |
| `schedule_group_caption` | A reviewed `source_schedule_group_captions` entry {source_block_id, caption, level 1\|2, owner_decision} opens, at exactly that block and only inside the open top-level schedule, a caption division: kind `part`, label = heading = the caption as printed; level 1 is a child of the schedule, level 2 a child of the open level-1 caption, and a later caption closes the open one at its level or deeper. While a caption is open, the rows the walk opens and their sub-units sit one level below it, so each row is the caption's child and keeps its printed serial (`…pt_<wing>__gc.pt_<group>__gc.cl_<serial>`, no positional suffix), and a `named_schedule_row` opened under it is the caption's child, its label unique among that caption's children. The caption's path ends `__gc` (docs/SCHEMA.md "Schedule group captions"). Fail-closed: an entry not reached exactly once, a caption outside a schedule, a level-2 caption with no open level-1 caption, a repeated caption under one parent, unit text that is not the caption, or no owner citation raises. Inert without the override. The recorder checks the caption is printed in a block on the reading's page and that the export holds the cited answer with a choice asking for rows by group caption (`SCHEDULE_GROUP_CAPTION_CHOICES`). | 1106 (pp3-6: wing titles and group captions; owner q3 "rows-by-group") |
| `uncontented_subpart_scan_schedule_bound` | With no contents list there is no last body section to bound the scan for a later print of a section number, so a Schedule row '2. Assistant Horticulturist' counted as a second rule 2 and buried rule 2 'They shall come into force at once.' in rule 1(2). With no contents, the scan now stops at the first SCHEDULE heading after the unit (the doc 1886 principle). | 1106 (p1, rule 2) |
| `owner_cited_label` Since 10 Oct (doc 2055, owner q1 "contents"): the neighbour sequence check passes over lettered insertions of the number ('12-A' after cited 12). | A reviewed `source_owner_cited_labels` list [{kind section\|article, printed_label, cited_label, source_block_id, owner_decision} or, for a unit the copy prints with no number of this instrument, {..., printed_label null, source_prefix}] carries out an owner's choice of the contents numbering. With a printed label, the unit the grammar opens at that block with that printed label and kind takes `cited_label` before its label is seen, recorded or linked, so the contents links, the S7 ledger and the sequence all see the cited number. With null, the block's unit is cut at `source_prefix` (verbatim, exactly once in the block) and a top-level unit labelled `cited_label` opens with the printed words as its text. The print is kept on the path, `__pN` or `__pnone` (docs/SCHEMA.md "Printed number markers"). Fail-closed: a malformed entry (printed label outside [A-Za-z0-9] or 'none', cited label not digits or equal to the print, a prefix under 12 characters, no owner citation); an entry not applied exactly once; a renumbered unit not top-level; cited labels out of sequence with their top-level neighbours (cited-1 before, cited+1 after); a print that also carries an order suffix. Inert without the override. The recorder checks the export holds the answer and its choice is one of `OWNER_CITED_LABEL_CHOICES` ('contents', 'open-at-p3', 'release-as-is', 'rule-3', 'assign', 'rules', 'number-1'), that the block is on the reading's page, and that the prefix occurs there once or the printed number is printed there. | 1225 (p2 the quoted Stamp Act s.29 cited s.3; body ss.3-8 printed 3-8, cited 4-9; owner q1 "contents", export -f); 1457 (8 Oct: s.6 is opened at p3's '6["(1) ...' and its words open s.6(1). A `continues_opened` entry, printed == cited, keeps p4's '1[6.' in s.6 and reads '(2) ...' inside it. Every continuation must be used, and an opened unit printed again at the root without one raises. An opener with a used continuation, printed == cited, carries no printed-number marker: the path is `s_6`, because the number is printed on p4 (lead decision 8 Oct). Owner q3 "open-at-p3"); 1463 (p5: an opener read while a top-level Part or Chapter is open belongs to that division -- s.11 of 'PART-HI', path `pt_PART_HI.s_11__pnone`; owner q1 "release-as-is", export -g); 1973 (p8-9: the three unnumbered West Pakistan notifications, each its own instrument holding one provision '1', printed_label null, path `s_1__pnone`; owner q4 "number-1", export -i) |
| `substituted_schedule_items` | A reviewed `source_substituted_schedule_items` span {owner_block_id, schedule_block_id, source_text, resume_block_id, owner_decision} holds an UNQUOTED substituted Schedule as numbered items of the section that substitutes it, as `quoted_schedule_word_owner` holds a quoted one. At exactly `schedule_block_id`, whose text must be `source_text`, the open top-level section whose first block is `owner_block_id` becomes the table owner: the Schedule's heading, caption and column heads before its first article are that section's text, the articles are its `clause` rows, each owning its own items, and no contents row closes the list inside the span. The span closes at the first unit of `resume_block_id`, the Act's own next provision, where the walk resumes at the root. Fail-closed: at most one span; the owner must be that top-level section, nothing else may own a table, no schedule may be open, and the entry must cite one owner answer. Inert without the override. The recorder checks that the answer's choice is 's2-text', that the schedule block is on the reading's page with that text, and that the owner and resume blocks are blocks of the document in reading order (owner < schedule < resume). | 1431 (pp3-37, Stamp Act Schedule-I substituted by s.2; owner q2 "s2-text": articles are items of s.2, s.3 opens after article 65) |
| `not_running_header_blocks` | The blocks named in a reviewed `source_not_running_header_blocks` list are exempt from the page-top repetition test for running headings. The generic `_is_running_header` shapes still apply. Each is then read as ordinary text: doc 1431's Schedule sub-heading 'Exemptions' heads pp4, 13 and 22, so all 19 prints had been set aside. No reading can un-set a running heading, because a reading may not empty or invent text. Inert without the override. The recorder checks the blocks are on the reading's page. | 1431 (pp4-37, 'Exemptions' x19) |
| `level_cell_blocks` | A reviewed `source_level_cell_blocks` list [{cell_block_id, row_block_id}] puts each named cell directly after the row, item or band block it is printed level with, left to right. The cell must be on the same page as the row, with tops within 2.5 pt, and must start right of the row's start; otherwise it raises. The text layer emits a two-column table's duty cell BEFORE the article it sits beside when both start on one line, and `row_aligned_cells` cannot see it here, because the median long-line edge is the description column's. No text changes and no block is dropped. Inert without the override. The recorder checks that both blocks are on the reading's page. | 1431 (pp3-39, 114 duty/rate cells) |
| `quoted_letter_annexure_title` | An annexure or appendix unit whose first line is only its label with a quoted capital letter (`ANNEXURE "A"`), and whose next line (or the next unit on the same page) is a capitals title line (`FORM OF NOMINATION`), is the division, even when its reference names a clause ('(See Clause 12)') and it follows a line with no stop. Doc 1415's Annexure A ran into the Schedule after 'Twenty thousand', and Annexure C into Annexure B's subscription. No override. | 1415 (pp9, 13) |
| `notification_preamble_row` | Where a reviewed `source_contents_row_links` entry names no unit on a contents row printed only 'Notification', the notification's enacting paragraph is the instrument's preamble. That paragraph is 'No. ...' and then 'In exercise of the powers conferred', printed before any unit has opened. Needs `reviewed_contents_alignment`; inert without the reviewed link. The row itself is closed by a found_elsewhere contents reading to the Preamble. | 1440 (p2, 'No. SO (Tax) 6 (1) /75 ... namely;'; owner q1 "body") |
| `unlabelled_appendix_opener` | A reviewed `source_unlabelled_schedule_openers` entry may carry the label 'APPENDIX'. It runs the same exact-evidence checks as `unlabelled_schedule_opener` and opens a top-level division of kind `appendix`, which is treated as a schedule is for rows. The recorder requires that an 'APPENDIX' label cites an answer whose choice asks for appendix rows (`APPENDIX_OPENER_CHOICES`), and refuses any label other than 'SCHEDULE' or 'APPENDIX'. No new key; inert without such an entry. | 1491 (pp14-22, printed under the caption 'INDEX'; owner q1 "appendix-rows-by-serial") |
| `bare_serial_row` | Inside a top-level schedule or appendix opened by a reviewed unlabelled opener, a whole page-read row block (`source_quoted_table_row_blocks`) that opens with a bare printed serial (1-3 digits, then a space) opens its row as 'N.' does. The serial is the label, as printed, and is not normalised. Inert outside such an opener. | 1491 (serials printed with and without a stop) |
| `appendix_note_caption` | Inside an appendix opened by a reviewed unlabelled opener, a unit whose whole text is 'Note:-' or 'Notes:-' opens the appendix's Part 'Note', even after a row that ends without a stop. The notes (i)-(v) are the Appendix's own, not clauses of its last row. Inert in a schedule. | 1491 (p22) |
| `half_paren_clause_label` | A block named in a reviewed `source_half_paren_clause_blocks` list is cut before every line that opens with one lower-case letter and a closing parenthesis ('c)'). Each such unit is clause <letter>: the label is as printed, without the parenthesis, and the rest is its text. Nothing is added to the text: the owner kept the print 'exactly as printed', so no reading may add the opening parenthesis. Fail-closed: every named block must open at least one such clause. Inert without the key. The recorder checks the blocks are on the reading's page. | 1626 (p2 r.4 'a)' ... 'c)'; owner q3 "keep-both") |
| `order_suffix_one_block` | A clause order-suffix group whose prints all stand in ONE source block may name that block once per print, in print order ([101082, 101082]). The list must still equal the group's first blocks exactly. Everything else in `order_suffix_label` is unchanged. A block may repeat within one group and never across two groups (recorder `order_suffix_groups_ok`). | 1626 (r.4's two 'c)'; owner q3 "keep-both": r.4(c) and r.4(c) (second)) |
| `dotted_form_code` | A form label of two or more 'X.' letters, optionally closed by a numeral, is the whole code: 'FORM H.T.I', 'FORM H.T.', as printed. While a form so labelled is the open top-level unit, a line printing only the same letter code and a numeral ('H.T. 3.') opens the next form, labelled as printed without the spaces ('H.T.3'); no FORM word is supplied. The next code of the series is a division, not the open form's words. | 1889 (pp6-10, FORM H.T.I to H.T.6) |
| `bracketed_repeal_stub_text` | With no contents name, a guessed heading whose span is a repeal stub -- '[Former heading.] Rep. Act XII of 1873.' / '... Repealed ...' -- is no heading: the stub is the section's text, as released stubs printing 'Rep. by ...' already are. | 1656 (s.6, p3) |
| `numbered_starred_first_subsection` | '10. / (1)2[***] 3["**"] 4[10. The ...' -- sub-section (1) opens with omission stars behind a note marker -- is cut after the section number before '(1) N[*', so (1) opens and the stars are its text. `numbered_marked_first_subsection` wants a letter after the marker. | 1692 (s.10, p7) |
| `parenthesised_lettered_division` | A bracketed capital and a capitals-only name alone on their line(s) -- '(A) DEFINITIONS.' ... '(I) EXEMPTIONS.' -- opens a part labelled by the letter with that name. A new line opening so starts its own unit. A name printed over two lines ending in 'AND' or a comma takes its capitals-only second line ('(F) APPROVAL, ... PASSES AND / PERMITS.'). | 1827 (parts A-I) |
| `stray_label_continuation` | A reviewed `source_continuation_parent_blocks` entry whose unit prints the SAME label as the open section owning the parent block ('3. Removal from service ...' after byelaw 3(2)) is that section's continuing text. No unit is opened, the printed number stays in the text, and the block's other units are read as usual. Fail-closed through 'source continuation not reached'. CAVEAT: a unit's own text precedes its children in the data model, so such a closing paragraph displays before (1). | 1946 (byelaws 3 and 6; owner q1, q2) |
| `blank_rule_heading_none` | A section or article heading made only of underscores (three or more, an optional stop) names nothing, as `mark_only_heading_none` does for '*****'. A contents row '5. ________' had headed rule 5 with its rule line. Run on the finished parse; the row stays linked. | 1970 (contents row 5) |
| `root_provision_member_list` | While a reviewed root provision with a WORD label (never a numeric one, so doc 268's para '1' is excluded) is the open section, a unit classified as section N, where N continues 1, 2, 3 ... among that provision's numbered clauses, is its clause N, with the label as printed and no heading guess. The members of a 'NOTIFICATION' list are the notification's clauses, as the membership lists of docs 1017 and 1934 are clauses of their provision. Inert without a reviewed word-labelled root provision. | 1970 (pp5-6 notifications; owner q1 "split") |
| `numeric_quote_definition_cut` | A new line opening '(N)' then an opening quote and a letter starts its own unit, but only after an unterminated line (one ending in a letter or digit): '(4) "Board" means ... Lahore' / '(5) "Complex" means ...'. `_INNER` cuts '(N)' only before a letter. The broad form, after any line, changed five released documents (3142, 3486, 3665, 3794, 4453); only the narrowed form is ported. | 1970 (p2 r.2(5)) |
| `apparatus_over_left_margin_heading` | A block a page reading sets aside as apparatus is never a `left_column_margin_heading` (A) heading, as `apparatus_over_margin_heading` does for the margin-note column. The pairing was computed over the body before the apparatus was removed, so a set-aside table cell ('Directorat / e of / Agricultura / l ...') had become every row's heading. | 1839 (pp2-21) |
| `unlabelled_schedule_before_row` | A reviewed `source_unlabelled_schedule_openers` entry whose block's unit is a numbered item ('4. Municipal Committee Street Rules, 1962.') opens the schedule BEFORE it, with no text, and the item is then read in it. The same override raised before, so no stored tree changes. The label stays 'SCHEDULE'; no lost heading is invented. | 2211 (p2, the tail of Schedule-II; owner q1 "release-as-is") |
| `stray_number_continuation` | A reviewed `source_continuation_parent_blocks` entry whose unit prints a section number the contents does not list ('14. A copy of the minutes ...' after rule 13(2), the contents ending at 13) is the open section's continuing text, provided it is the first unit of its block and the section owning the parent block is open. The printed number stays in the text and no unit is opened. A sibling of `stray_label_continuation`, with the same display-order caveat (text before children). | 2055 (p4; owner q2 "first-only") |
| `bracketed_omit_section_stub` | Outside a schedule, a unit that is only '[Omit section N.]' (an optional note marker before the bracket), where N is the next section after the highest the walk has met and not yet used, is the omitted section N's stub: section N, no heading, its text the printed line, in the open top-level Part/Chapter. The number is the one printed. | 2186 (p11 '7[Omit section 26.].') |
| `contents_split_division_name` | A Part or Chapter linked to a contents row, whose whole text is capitals and whose heading plus text is the row's name (after 'PART-N' / 'CHAPTER N'), takes that text into its name. Doc 2009's 'PART-VIII / ACTION AGAINST CANDIDATE SON' then 'GROUNDS OF CHEATING, ETC.' had kept the second line as the Part's text. | 2009 (pp6, 8, 9, 11) |
| `terse_sentence_not_heading` | A first-sentence heading guess with an auxiliary ('will', 'would', 'should', 'can', 'could', 'be', 'been') is an enacted sentence, not a heading: '57. The allocation of posts to Committees for interview will be made by the Chairman.' is the regulation's text. | 2009 (reg.57, p10) |
| `decimal_paragraph_cut` | A body that numbers its paragraphs N.1, N.2 ... (at least five consecutive decimal labels of one integer N, each opening a line before a capital word or '(1)') is cut before every line opening one of those labels, with an optional letter suffix ('3.9 A', '3.13-A'), before a capital word or '(1)'. `repeated_decimal_label_cut` wanted a blank line and a repeat in another block, so 3.3 (after a line ending '/') and 3.9 (after ',') ran into the paragraph before. | 1973 (pp2-7, paragraphs 3.1-3.19) |
| `spaced_letter_decimal_label` | '3.9 A Under section 13(b) ...' -- a decimal label, one space, a single capital letter, then a capitalised word -- is paragraph '3.9 A' as printed (3.13-A cites it 'order 3.9-A'). The decimal grammar took '3.9' and left 'A' in the text. | 1973 (p4) |
| `decimal_name_contents_row` | A contents row printed as its serial on one line and only a paragraph number on the next ('3. / 3.3', '14. / 3.14 to 3.18', '16. / 4') is the row with that serial whose name is that number, and a new line opening one starts its own unit -- only in a run of at least three such rows with consecutive serials in one block. Released doc 4433's rate table prints '11. / 10 / 9.' (the run guard is what keeps it SAME). | 1973 (p1 contents, 20 rows) |
| `decimal_paragraph_item_list` | While a paragraph of the body's decimal series (`decimal_paragraph_cut`) is the open top-level unit and its own text ends introducing a list ('... namely: -'), the numbered lines that follow, with or without a stop ('1 / The Punjab Intoxicants ...', '3. The ...'), are its clauses 1, 2, 3 ... numbered on from 1, not sections. The next series paragraph ends the list. | 1973 (3.9 A and 3.13-A, items 1-13) |
| `lettered_power_group` | A line holding a single capital A-H followed by a line of words ('B / Powers of an Excise Officer of the 2nd class.'), when the block prints that letter or the one before on a lone line earlier, starts its own unit. Inside a top-level unit whose text ends introducing a list ('... as follows: -'), it opens a lettered group: clause, label the letter as printed, one level below the unit -- A first, then the next letter or the same again (kept by `order_suffix_label`). The group's (1), (2) ... sit one level below it. | 1973 (3.5 groups A, B, C, C; NWFP 5 groups A, B) |
| `bare_number_paragraph` | In a span whose blocks print at least four consecutive integers each alone on its line before 'Under ...' (or '(a) / Under ...'), such a line before a capitalised word or '(a)' starts its own unit and, when its number is one above the integer part of the last top-level unit, opens that paragraph as printed. | 1973 (NWFP Orders 4-8 after 3.19, p8; owner q2 "body") |
| `dashed_stub_clause_cut` | A new line opening '(b)' (any letter after 'a') followed straight by three or more dashes -- a clause printed as its label and a rule -- starts its own unit when the letter before opens a line earlier in the block. Every clause cut wants a letter after the label, so (b) and (c) stayed in (a)'s text. | 1973 (3.4, p3) |
| `explanation_of_heading` | 'Explanation' followed directly by the word 'of' opens no Explanation and is no cut point: '21. Explanation of Estimates of Revenue. While explaining ...' is the rule's heading. An Explanation is printed 'Explanation.--', 'Explanation:', 'Explanation I' or 'Explanation 1', never 'Explanation of'. | 2146 E1 (rr.21-34, pp11-13) |
| `unclosed_paren_heading_guess` | A first-sentence heading guess that opens a parenthesis it does not close ('(Act' from '5. (Act. (XVII of 1967), Schedule, Part-2.') is no heading; the contents row names the section. | 1003 (p3, s.5) |

`chapter_colon_label` ("CHAPTER: VII", doc 4137) was built and then taken out
on 28 September: 4137 is bound on an owner decision (its contents number the
chapters 1-9 against the body's I-X), and no other blocked document prints a
colon after CHAPTER. It returns with 4137 if the owner releases it.

**Two observations of one document.** Doc 876 is catalogued twice (1207 and
1208) over the same blocks. `tools/record_curation_patch.py` recorded its
patches for 1207 only, so the pinned replay of 1208 ran without them. The rows
were copied to 1208 by `tools/evidence/record-876-second-observation-patches-
2026-09-26.sql`. Doc 1695 has the same shape (2372 and 2781); its patches were
copied at record time by `tools/evidence/record-1695-second-observation-
patches-2026-09-27.sql`. After any replay, `tools/resolve_exact_instrument_duplicates.py
--apply` must run so that the byte-identical copy is linked as a duplicate
(`nz`, `tools/post_replay_sequence.sh`); otherwise the release shows it as an
unexpected second instrument.

## Page-read apparatus without an S7 case

Also authorised on 26 Sep 2026: a verified identity curation patch may name
`source_apparatus_blocks` on its page, as well as the reparents it could
already carry. This covers footnotes or endnotes the parser read as law where
no collision exists to carry an S7 reading, such as doc 2803's closing
amendment notes. `tools/record_curation_patch.py` records both, and
`reviewed_structural_overrides` unites patch-borne apparatus lists.

Since 6 Oct 2026 the recorder refuses a reading carrying a key it does not know
(`READING_KEYS` in `tools/record_curation_patch.py`) instead of recording the
patch without it: doc 691's prototype keys would otherwise have been dropped
silently and the replay would have built a different tree from the one the
reading was checked against. The structural keys it records are the same set
the worker merges and the multi-instrument dry run shapes
(`STRUCTURAL_PATCH_KEYS`); `source_unlabelled_schedule_openers`,
`source_quoted_table_row_blocks`, `source_printed_headings`, (7 Oct)
`source_order_suffix_labels` and (8 Oct) `source_named_schedule_rows` name
blocks on the reading's own page (a named row's `schedule_block_id` may be on
an earlier page of the same document). All of them except the quoted row
blocks must cite an owner answer the export holds; a named row's answer must
also be one whose choice asks for rows held by their printed post name. (8 Oct)
`source_contents_row_links` names contents rows, not blocks; it too must cite
an answer the export holds, and the segmenter checks the rows at replay.
`source_schedule_group_captions` and `source_owner_cited_labels` name blocks on
the reading's page. Their answers must ask for rows by group caption, or for
the contents numbering ('contents'), respectively. (8 Oct, doc 1431)
`source_not_running_header_blocks` and `source_level_cell_blocks` name blocks on
the reading's page. A `source_substituted_schedule_items` span names its
schedule block on that page. Its owner and resume blocks may be on other pages,
so they must be blocks of the document in reading order, and its answer must be
's2-text'.

## Compatibility

### Reviewed 4331 printed-opener extensions (19 October 2026)

The existing `source_printed_rule_openers` key now admits reviewed lettered
Schedule article divisions as subsections (`A-INSTRUMENT OF`, `B. Revocation
of`), lettered clauses containing note-marked omission stubs, and printed
Explanation/Exception openers. These entry shapes are data-gated on every
profile. Existing Roman I/V/X subsection grammar remains unchanged, including
parenthesized labels. Tests are in `tests/test_k6_printed_opener_extensions.py`.

Document 4331 uses its reviewed `unreleased-v4` pin; no v5 profile is introduced.
The owner's existing rate mapping is retained. Independent source review also
corrects the scope of exemptions and registration Notes using existing
continuation-parent and bound-note keys; the Notes remain operative article
text with their printed labels. Evidence, merged commutative readings and
before/after accounting are in
`.artifacts/release-work-2026-09-24/codex-4331/`. Only observation 2080 is replayed;
the separate proposed corrections to 4374 and 4453 are not part of this release.

### Reviewed 3912 captions, form recitals and marked appendices (19 October 2026)

Three corrections extend existing source-review keys on every profile, including
the default profile of document 3912's released Act. They remain inactive when
the corresponding reviewed blocks are absent:

- `form_text_not_preamble`: `source_form_text_blocks` keeps a blank form's
  WHEREAS recital in that form instead of opening the instrument's preamble.
- `reviewed_group_caption_line`: `source_group_heading_blocks` also accepts a
  complete sentence-case caption line as a numbered group. Decimal rules remain
  beneath it; a following auxiliary division closes that group. Contents rows
  match unique reviewed groups by their printed number and auxiliary divisions
  by their printed name. The owner's export m q1 establishes these targets for
  3912, rather than changing printed rule numbering.
- `reviewed_division_opener_star_marker`: `source_division_openers` accepts a
  footnote star before the printed appendix/form/schedule name (3912 Appendix IV).

The source spans and release approval are recorded in
`tools/evidence/multi-instrument-plans/doc-3912.json`. The materializer's optional
`--require-all-released` gates every replacement expression before commit.
For 3912 the invocation additionally shares one database transaction across
`save_many` and its segmentation-run records, checks both expressions through
the actual release view, and rolls back if either fails. This is necessary
because correcting the Act's source span is authorised only together with the
Rules' release. Evidence and the rollback rehearsal are in
`.artifacts/release-work-2026-09-24/codex-3912/`; parser regressions are in
`tests/test_jf_rules_lmn.py`.

- `tools/measure_segmenter_against_stored.py` and `tools/diff_segment_trees.py`
  load another copy of `segment.py`. `build()` passes `profile=` only for a
  non-default profile, so older copies still work for default documents. A
  pinned document needs a copy that has profiles.
- A pin belongs to one observation and covers every expression built from it.
  Another observation of the same blob keeps its own pin. The tool pins every
  active observation of a document unless `--observation` names one.

### Source-reviewed amendment-table ordering (4089, 20 October 2026)

Observation 4499 uses `unreleased-v4` with exact, source-backed readings.
No document-ID branch or new profile is needed. The official 45-page source
prints two Act sections as `(i)/(ii)` and thirty Schedule SR rows as 1–30;
contents rows 3–32 name those Schedule rows, not thirty additional sections.
The existing owner export-m answers (`q1: contents`, `q2: body`) determine the
cited section numbers 1/2 while retaining printed-number path markers `__pi`
and `__pii`, and the Schedule rows retain their printed serials.

- `source_unit_moves` moves an exact-prefix unit before another exact-prefix
  unit **on the same page**, after splitting but before quote-span indexing.
  The original block objects, text and provenance remain unchanged. Missing,
  ambiguous, repeated, self-referential and cross-page moves fail closed.
  This avoids moving a previous row's quoted ending when a PDF block also
  contains the next row's title. No entries means no ordering change.
- `source_contents_schedule_rows` optionally takes `row_kind` and an explicit
  `row_labels` mapping from printed contents ordinal to Schedule serial. Each
  target must exist uniquely directly under the exact named Schedule. A
  successfully mapped row is represented, not an absent-body adjudication.
  Legacy readings without this mapping retain their existing behavior.
- An exact owner-cited Roman section entry promotes only its named block and
  printed label; ordinary Roman list items remain clauses. A reviewed opener
  may name a lone dotted serial embedded on its own unique source line.
- Existing printed-openers and quote spans keep the 60 amendment items and
  118 instructions under their correct Schedule rows. Inserted subsection
  labels remain quoted operative text, not sections of the amending Act.

The source's unusual amendment labels (including row 7's `3`, row 20's `(c)`
and row 28's `(a)/(ii)`) are preserved. Only three column-header numerals and
one parsing delimiter are changed in parser input; raw text blocks are never
edited. Evidence, independent review, transactional results and limitations:
`.artifacts/release-work-2026-09-24/codex-4089/`. The complete immutable-block
regression fixture is `tests/fixtures/doc4089-source-reviewed.json`, exercised
by `tests/test_reviewed_amendment_table.py`. This review establishes the stated
operative structural scope, not a legal-status or all-metadata certificate.

### Source-reviewed grids and partial source openers (4058, 20 October 2026)

Observation1397 is pinned to `unreleased-v4`. Its 67 source-reviewed readings
are observation-scoped; no document-ID branch or corpus-wide replay was added.
The qualified release preserves readable law while source-incompleteness64
records the official PDF's covered sections49–51, opening52, six clipped
penalty-table fragments and unfinished row14(g). Acquisition attempt203 returned
the identical official source. Invisible PDF text is not reconstructed as law.

- `source_reviewed_grid_rows` names an exact printed label/prefix, structural
  parent block and disjoint whole source cells in column order. This preserves
  a cell's cross-page continuation without interleaving offences, penalties or
  references. Missing/overlapping cells, unprinted labels, unavailable parents,
  apparatus conflicts and reversed source continuations fail closed. Schedule
  finalization retains its existing clause-kind normalization. Explicit bold
  group parents and printed `(a)/(b)` qualifiers retain their hierarchy; decimal
  arithmetic never supplies a parent or corrects a printed code/rate.
- A partial owner-cited opener may declare `missing_before` and an actual
  `source_incompleteness_id`. Its predecessor must bound that exact contiguous
  list, every missing label must have a contents promise, and none may already
  have an operative body node. Both intake and build require the latest source
  record for the same document/observation to bind the exact visible prefix,
  block and missing list. Superseded or unrelated evidence refuses replay.
- An explicitly reviewed `exact_block_locator` can distinguish identical table
  cell text. It requires the exact block ID, physical page and complete unchanged
  before-text locator. It is extraction-bound and fails closed after a changed
  extraction; ordinary stable text locators retain their existing behavior.

The source's printed803.1000 remains803.1000. All553 tariff rows, six tariff
qualifiers and14 penalty rows have exact source-cell and parent checks. The
section15 footnote is excluded without losing16A's operative continuation;
section66 and its first subsection are retained. Two response JSONs are tool
reviews, not impersonated human approvals. The three missing contents entries
were accepted as `source_incomplete` through the established adjudicator.

Evidence, actual test results, rollback rehearsal and committed release ledger:
`.artifacts/release-work-2026-09-24/codex-4058/`. The review does not certify
full-instrument source completeness, current statutory force, or unreviewed
pages. Previously released instruments were not replayed.
