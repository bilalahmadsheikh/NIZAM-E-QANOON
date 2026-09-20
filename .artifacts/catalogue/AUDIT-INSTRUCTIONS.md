# Audit reader instructions (the weighted 200-decision audit)

You are auditing decisions that were ALREADY MADE about the Nizam-e-Qanoon legal
corpus. Each row is one recorded S7 structural adjudication: two units in a
statute carried the same printed label, the segmenter kept one and demoted the
other to a non-citable node, and somebody then recorded a decision about it.

**Your job is to say whether that decision was right, by looking at the page.**
You change nothing: no database writes, no repository edits, no git.

The sample is frozen and weighted by band, so every row must be judged — a row
you skip biases the estimate. Judge the ones you can and mark the rest honestly.

## Environment

- Windows host. Repo root: `E:\Nizam_e_Qanoon`.
- **Page images:** each row's `renders[]` gives a POSIX path such as
  `/mnt/e/nizam-data/s7-audit/audit-doc1580-p2-2.png`. Open it with the Read
  tool as `E:\nizam-data\s7-audit\audit-doc1580-p2-2.png`.
- **Read-only database lookups** (Bash tool, exactly this form, single quotes):
  ```
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh subtree <candidate_id>'
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh page <document_id> <page>'
  wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/Nizam_e_Qanoon && bash .cq.sh tree <document_id> <from_page> <to_page>'
  ```

## What a row gives you

`adjudication_id`, `candidate_id`, `document_id`, `printed_label`, `source_page`
(where the demoted unit sits), `canonical_source_page` (where the kept unit
sits), `kept_text`, `demoted_text`, `band` and `group_size` (the sampling
weights — do not change them), and `heuristic` / `heuristic_why`, which is what
an automatic rule guessed. **The heuristic is not evidence.** It is there so you
can see what a rule would have said; the page decides.

## The three verdicts

These are the definitions `tools/s7_audit_batch.py` counts against. Use them
exactly. **The only question that moves the estimate is: was LAW demoted?**

- **`correct`** — the demoted block is not a provision distinct from the kept
  one: it is apparatus (a contents entry, a footnote, a table row, a form field,
  a masthead, quoted amendment text) or a duplicate of the kept unit, while the
  kept unit is the real provision.
- **`wrong`** — **law was demoted.** The demoted block is an operative provision
  that is now uncitable. This includes every inversion (the kept unit is a
  contents line, footnote or running header and the real section was demoted),
  AND every case where the demoted block is real law of a *different* instrument
  or part printed in the same PDF (a compendium, an appended schedule of
  statutes, a second notification), AND a real section demoted because its
  number was misread. If operative text sits under the demoted node's subtree,
  that is `wrong` too, whatever its label says.
- **`not_s7`** — **both** blocks are apparatus (for example two contents lines,
  two footnotes, two table rows), so the decision could not have demoted law.

If the page cannot settle it, use `needs_second_read` with `confidence: low` and
say exactly what you would need. An honest unsure verdict is worth more than a
confident wrong one, and it is counted separately rather than silently as
correct.

## Traps

1. **Read both pages.** `canonical_source_page` and `source_page` are usually
   different. A verdict formed from one page is a guess.
2. **Check the subtree when the demoted node is not tiny.** Run
   `.cq.sh subtree <candidate_id>`. A footnote or table-row node with the next
   section's operative text under it means law is hidden, whatever the labels
   say.
3. **A matching first sentence is not a duplicate.** Compare the whole text.
4. **Quoted amendment text** ("the following shall be substituted:-" then a
   quoted section) is not a section of the amending law — but if that quoted
   text is the whole substance of the amending section, demoting it leaves the
   amending law uncitable, and the decision is `wrong`.
5. **Superscript markers flatten.** `¹1.` becomes `11.`, `⁴*[294B.` becomes
   `4*[294B.`. Look at the image before calling a label wrong.

## Output

Write ONE JSON file per row, as soon as you finish it, with the Write tool, to:

`E:\Nizam_e_Qanoon\.artifacts\catalogue\results\<shard name>\<adjudication_id>.json`

```json
{
  "adjudication_id": "ea04b147-7b1e-4425-9e6a-419aeb8ebe0d",
  "document_id": 1580,
  "printed_label": "1",
  "verdict": "correct",
  "observed": "Page 3 prints ... and at the foot two amendment footnotes: '1. Insection-6 ...'. Page 2 prints '1. (1) This Ordinance may be called ...' with marginal note 'Short title and extent.'",
  "what_was_demoted": "amendment footnote 1 at foot of page 3",
  "what_was_kept": "section 1 (short title and extent) on page 2",
  "band": 2,
  "heuristic": "unclear",
  "instrument_active_now": true,
  "renders": [{"page": 2, "file": "/mnt/e/nizam-data/s7-audit/audit-doc1580-p2-2.png", "sha256": "891d..."}],
  "confidence": "high"
}
```

Copy `band`, `heuristic`, `renders` (with their sha256 values) and
`instrument_active_now` (from the row's `instrument_active_at_freeze`) straight
across — the estimate is computed from them. `observed` must quote what the
pages actually print, at least 60 characters, and must name both pages.

When the shard is done, reply with: rows judged, a count by verdict, and any row
you could not settle and why.

**Table rows.** Two rows of the same or different tables (a village schedule, a
recruitment schedule, a fee table, a form's numbered fields) colliding with each
other are `not_s7`: the schedule or table is the citable unit, not its row. It
is `wrong` only when one side is a real section or rule, or when operative text
is hidden under the demoted row's subtree.
