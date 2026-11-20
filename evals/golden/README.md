# Golden set — `golden-pk-v1`

The measuring instrument for retrieval and answers (docs/10 §4–§5).
Nothing in retrieval (L3) or generation (L4) can be tuned or claimed without it.

## What is here

| File | What it is |
|---|---|
| `golden-pk-v1-setN.draft.jsonl` | **Sets 1–10**: 50 cases each (500 in all, the docs/10 target; sets 5–10 added 20 Nov 2026, D-104), one `LegalEvalCase` record per line (docs/10 §5) |
| `golden-pk-v1-setN.draft.md` | The same cases in readable form: question, propositions, every expected provision with its text excerpt, status and official PDF link; at the end, what the system currently gets wrong on that set |
| `build_setN.py` | The cases of set N, written as data; running it rebuilds the set from the database and checks every case |
| `golden_common.py` | The shared builder and its checks (below) |
| `peek.py` | Reads a provision's text from the database while writing a case: `python evals/golden/peek.py 4441:379 4501:154` |
| `show_negatives.py` | Lists each case's hard negatives (trap laws) and whether the system would wrongly serve them |
| `make_review_sheets.py` | Makes one blank review sheet per annotator |
| `agreement.py` | Compares two filled sheets: agreement, Cohen's kappa, list of disagreements |
| `apply_review.py` | Writes the reviewed result into a new `*.reviewed.jsonl` |
| `review/` | Review sheets and disagreement lists |

### What each set covers

Every set has the same mix of strata:

| Stratum | Cases per set | Example |
|---|---|---|
| Citizen scenario | 20 | "My landlord in Lahore wants me out — on what grounds?" |
| Professional lookup | 12 | "CrPC provision on bail in non-bailable offences" |
| Procedural | 8 | "How do I get a succession certificate?" |
| Urdu / Roman Urdu | 5 | "Talaq dene ke baad shohar ko kis ko notice dena zaroori hai?" |
| Deliberately unanswerable | 5 | "What does the rent law in Gilgit-Baltistan say?" (the system must decline) |

| Set | Theme |
|---|---|
| 1 | A first sweep: rent, family, labour, consumer, the major codes, tax and the Constitution |
| 2 | The core codes (PPC, CrPC, CPC, Contract Act, Qanun-e-Shahadat, Limitation Act, TPA, Specific Relief Act), personal law and online offences |
| 3 | Provinces, territories and time: the same question in different provinces, and the same question at two dates (below) |
| 4 | Work, money, business, rights and regulation, including subordinate Rules (Family Courts Rules, the Punjab RTI and consumer Rules, the ICT consumer Rules) |
| 5 | Property and land: sale, mortgage, lease, gift, registration, stamp duty, easements, the Punjab land record and tenancy, women's property rights by place |
| 6 | Criminal law and procedure II: hurt, diyat, kidnapping, extortion, forgery, narcotics by province, remand, confessions, habeas corpus, the complaint case |
| 7 | Family II: dissolution grounds, dower, delegated divorce, guardianship, offences against women, Family Court procedure, Sikh and Christian marriage, NADRA |
| 8 | Public law: the rights articles, elections, the Exit Control List, emigration, civil service and tribunals |
| 9 | Commerce and money: the private-loan interest bans by place, guarantee, bailment, agency, partnership, insurance, competition, e-transactions, cheques |
| 10 | Welfare and regulation by place (environment, disability, healthcare commissions, food) and Gilgit-Baltistan's own Acts |

Together the sets cover the federation, Punjab, Sindh, KP, Balochistan, ICT, AJK and (set 10) Gilgit-Baltistan.

**Traps.** Many cases name hard negatives: laws a system must not serve for
that question. These are laws that have ended, another province's law, or
another territory's law. Examples are the Companies Ordinance 1984 for a
question about current company law, Punjab rent law for an Islamabad tenant,
and the Hindu Marriage Act 2017 in Sindh (that Act's own s.1 excludes Sindh).

**Temporal pairs (set 3).** Some questions are asked twice, today and at an
earlier date:
- Punjab child marriage: in June 2020 a girl was a "child" only under sixteen;
  today a child is anyone under eighteen;
- Punjab defamation: the Defamation Ordinance 2002 in January 2020, the Punjab
  Defamation Act 2024 now;
- anti-rape crisis cells: the Anti-Rape Ordinance 2020 in March 2021, the 2021
  Act now.

### How each case is checked (`golden_common.py`)

Every build reads each expected provision from the database. Its text, status
and official link are never typed by hand (INV-1). The build then checks:

1. **The provision exists and is served.** Each expected provision must
   resolve to exactly one provision and be served on the case's date in the
   case's territory.
2. **The text says what the answer says.** Every case in sets 2–4 lists the
   key words and numbers its answer depends on ("fifteen days", "one million"
   and so on). The build fails unless they appear in the provision's own text.
   Every answer was written from the provision text read with `peek.py`, never
   from memory.
3. **Provincial texts are compared.** Punjab, KP and Balochistan publish their
   own official copies of several federal codes (`PROVINCIAL_COPY`). For a
   case in such a province, the builder compares the two texts:
   - nearly identical: the provincial copy is recorded as an equivalent text
     (grade 3), so a system citing either one is not marked wrong;
   - different: the build fails until the author decides which text answers.

   This check corrected set 1 case S1-R03: Punjab's khula provision differs
   materially from the federal one.
4. **Families stay inside their set.** A family must not appear in two sets.

Two kinds of finding go into a report section of the readable file. They are
not failures, because the gold answer is right either way; they are what a
retrieval run is expected to get wrong until the system is fixed:

- **A trap the system serves.** At first build, set 3 found five, such as the
  federal Child Marriage Restraint Act 1929 still served in Punjab, ICT and
  Balochistan after each repealed it for its own territory. Migrations
  0095–0100 fixed all five: territorial repeals and printed extent clauses
  (docs/SCHEMA.md, "Where a law runs").
- **A past date the system cannot serve.** A held text is served before its
  capture only as far back as the corpus can prove it was the law: the law's
  start, or its latest dated amendment (`mv_provision_text_known_from`). A law
  with an amendment the corpus cannot date is not served before capture. Set
  3 has two such cases left, the Punjab texts of the Child Marriage Restraint
  Act 1929 and the Defamation Ordinance 2002. Both are correct refusals until
  their amendments are dated.

Language variants of a question share the same `familyId` as their English
case. They count as one statistical cluster and always go in the same split
(docs/10 §4).

## Status: DRAFT

All four sets have passed stage **A0** (cases authored without system output)
and stage **A3** (every provision is resolved to a stable ID with its official
source). Stages **A1** and **A2**, the legal review, have **not** been done.

Until they are done, the sets must not be used to tune anything or to report
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

The blank sheets for all four sets are already in `review/`. To make them for
a new set:

```
python evals/golden/make_review_sheets.py evals/golden/golden-pk-v1-set2.draft.jsonl --annotators A B
```

This writes `review/golden-pk-v1-set2-annotator-A.csv` and `…-B.csv`. It never
overwrites a sheet that already exists. Give one sheet to each annotator. Open
them in Excel, Google Sheets or LibreOffice.

The commands below use set 1; replace `set1` with the set being reviewed.
Review one set at a time.

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

## Adding sets 5 to 10

The target is **500** independently authored scenarios (docs/10 §4); all 500
are done in draft (sets 1–10, D-104). Further sets (11 onward) follow the same
rules and widen the unanswerable and Urdu strata first.

For each new set:
- copy `build_set4.py` to `build_set5.py` and write new cases without looking
  at system output;
- read every provision with `peek.py` and give every answer case a `check`;
- keep the strata mix (40% citizen, 25% professional, 15% procedural, 10%
  Urdu/Roman Urdu, 10% unanswerable);
- use family ids prefixed `F5-` so they stay inside the set.

A new case must not paraphrase an existing family. If it does, it joins that
family.

Build all sets with `python evals/golden/build_setN.py` for each N; every set
must report `problems: 0`.
