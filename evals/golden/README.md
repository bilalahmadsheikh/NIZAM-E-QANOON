# Golden set — `golden-pk-v1`

The measuring instrument for retrieval and answers (docs/10 §4–§5).
Nothing in retrieval (L3) or generation (L4) can be tuned or claimed without it.

## What is here

| File | What it is |
|---|---|
| `golden-pk-v1-set1.draft.jsonl` | **Set 1**: 50 cases, one `LegalEvalCase` record per line (docs/10 §5) |
| `golden-pk-v1-set1.draft.md` | The same 50 cases in readable form: question, propositions, every expected provision with its text excerpt, status and official PDF link |
| `build_set1.py` | Rebuilds set 1 from the database and checks every case: each expected provision must resolve and be servable on its date in its territory |
| `show_negatives.py` | Lists each case's hard negatives (trap laws) and whether the system would wrongly serve them |
| `make_review_sheets.py` | Makes one blank review sheet per annotator |
| `agreement.py` | Compares two filled sheets: agreement, Cohen's kappa, list of disagreements |
| `apply_review.py` | Writes the reviewed result into a new `*.reviewed.jsonl` |
| `review/` | Review sheets and disagreement lists |

### Set 1 composition

| Stratum | Cases | Example |
|---|---|---|
| Citizen scenario | 20 | "My landlord in Lahore wants me out — on what grounds?" |
| Professional lookup | 12 | "CrPC provision on bail in non-bailable offences" |
| Procedural | 8 | "How do I get a succession certificate?" |
| Urdu / Roman Urdu | 5 | "Talaq dene ke baad shohar ko kis ko notice dena zaroori hai?" |
| Deliberately unanswerable | 5 | "What does the rent law in Gilgit-Baltistan say?" (the system must decline) |

The cases cover the federation, Punjab, Sindh, KP, Balochistan, ICT and AJK.
Some cases carry **traps**: laws that are no longer current, such as the
Companies Ordinance 1984 or the Prevention of Electronic Crimes Ordinance 2008.
The system must not serve these as current law.

Language variants of a question share the same `familyId` as their English
case. They count as one statistical cluster and always go in the same split
(docs/10 §4).

## Status: DRAFT

Set 1 has passed stage **A0** (cases authored without system output) and stage
**A3** (every provision is resolved to a stable ID with its official source).
Stages **A1** and **A2**, the legal review, have **not** been done.

Until they are done, the set must not be used to tune anything or to report
any number. Every record says so in `review.status`.

## How to review (docs/10 §5)

### Who

| Role | Who |
|---|---|
| Annotator A, annotator B | Two people with legal training. They work independently and must not talk about cases until both are finished. |
| Adjudicator | A senior advocate who settles every disagreement and gives a reason. |
| Data engineer | Resolves any provision an annotator adds, and freezes the split. |

Each annotator writes down their practice area, language competence and any
conflicts of interest in their first `your_notes` cell (docs/10 §5).

### Step 1: make the sheets (data engineer)

```
python evals/golden/make_review_sheets.py evals/golden/golden-pk-v1-set1.draft.jsonl --annotators A B
```

This writes `review/golden-pk-v1-set1-annotator-A.csv` and `…-B.csv`. Give one
to each annotator. Open them in Excel, Google Sheets or LibreOffice.

### Step 2: annotate (each annotator alone, stage A1)

Read `golden-pk-v1-set1.draft.md` for context, and open the official PDF link
when you need the full text. Fill **only** the `your_` columns.

| Row type | What to fill |
|---|---|
| `outcome` | `your_outcome`: `answer`, `conditional` (the answer depends on facts not given) or `abstain` (the system must decline) |
| `unit` | `your_grade`: 0–3 (scale below), or `remove` if the provision has nothing to do with the question. `your_role` is optional. |
| `missing` | `your_missing_law_and_section`: any provision you think is needed but not listed, e.g. "Specific Relief Act 1877 s.21" |
| any row | `your_notes`: your reasoning, especially where you were unsure |

**Grading scale (graded relevance over provisions, docs/10):**

| Grade | Meaning |
|---|---|
| **3** | Necessary: the answer cannot be given correctly without this provision |
| **2** | Strongly relevant: supports or qualifies the answer |
| **1** | Marginally relevant: useful background |
| **0** | Not relevant, or a trap the system must not use (wrong province, repealed, lapsed, a different Act) |

Judge the law as at the case's `as_of` date and in its `territory`. A Punjab
question is answered by Punjab and federal law, never by Sindh law.

### Step 3: measure agreement (data engineer)

```
python evals/golden/agreement.py evals/golden/review/golden-pk-v1-set1-annotator-A.csv \
                                 evals/golden/review/golden-pk-v1-set1-annotator-B.csv
```

This prints percent agreement and Cohen's kappa for grades and for outcomes,
and writes `review/golden-pk-v1-set1-disagreements.csv`.

Low agreement does not mean taking a vote. It means improving these
instructions, or keeping the legal ambiguity as alternative answers (docs/10
§5). Before a kappa figure goes in the thesis, confirm the definition against a
cited source (nizam-evals skill).

### Step 4: adjudicate (senior advocate, stage A2)

In the disagreements sheet, fill `adjudicated_value` and `adjudicator_reason`
for every row. Where two answers are both legitimate, choose one and record the
other in the reason. Alternative gold sets are kept, not discarded (docs/10 §5).

### Step 5: write the reviewed set (data engineer)

```
python evals/golden/apply_review.py evals/golden/golden-pk-v1-set1.draft.jsonl \
       evals/golden/review/golden-pk-v1-set1-annotator-A.csv evals/golden/review/golden-pk-v1-set1-annotator-B.csv \
       evals/golden/review/golden-pk-v1-set1-disagreements.csv \
       --annotator-a "Name A" --annotator-b "Name B" --adjudicator "Name C"
```

This writes `golden-pk-v1-set1.reviewed.jsonl`; the draft is never edited. The
tool refuses to write while anything is unfilled or unadjudicated.

Provisions the annotators added are listed in `review.missingProposed`. The data
engineer resolves each one to a provision ID (stage A3) and runs
`build_set1.py`'s checks again.

### Step 6: freeze (stage A4)

Assign every family (`familyId`) to one split: Fit, Calibration, Locked release
or Sealed challenge (docs/10 §4). Record a content digest, and never move a
family between splits afterwards.

## Sets 2, 3 and 4

The target is **500** independently authored scenarios (docs/10 §4); each set
adds 50 (or more).

For each new set:
- copy `build_set1.py` to `build_set2.py` and author new cases without looking
  at system output;
- keep the strata mix (40% citizen, 25% professional, 15% procedural, 10%
  Urdu/Roman Urdu, 10% unanswerable);
- widen into Rules, Notifications, ICT, AJK, temporal pairs (the same question
  at two dates) and jurisdiction pairs (the same question in two provinces).

A new case must not paraphrase an existing family. If it does, it joins that
family.
