---
name: nizam-services
description: Rules for the Nizam-e-Qanoon domain services layer (L5) — the precedent citator and treatment classification, judgment profiles, the limitation engine, court fee, stamp duty and forum calculators, the document factory with its deterministic clause engine, and procedure guides. Load when working on precedent, drafting, calculators, stamp duty, limitation periods, or any feature that produces a legally operative artefact.
---

# Nizam-e-Qanoon — domain services

**Reference:** `docs/06-domain-services.html` · `docs/03b-legal-data-model.html` §4 (schedules as tables)
**Intent:** The features here either answer exactly or they must not answer. Several involve no model at all — and that is the point, because they are the questions with the most direct consequences for a person's liberty or property.

## Schedules are already tables — store them as tables

~700 rows of expert data entry that remove whole question classes from the model:

| Source | Rows | Answers exactly |
|---|---|---|
| CrPC Schedule II | ~300 | Cognizable? Bailable? Compoundable? Which court tries it? |
| Limitation Act 1908 Schedule | ~180 | How long do I have, and from what date does the clock run? |
| Court Fees Act 1870 | ~110 × province | Filing cost at this suit value |
| Stamp Act 1899 Schedule I | ~65 × province | Duty this instrument attracts |
| Civil courts pecuniary limits | ~40 | Which court has jurisdiction at this value |

**"Is theft bailable?" becomes a `SELECT`.** These are **expert-entered and expert-verified, never model-extracted** — a 97%-accurate limitation table is not 97% as good as a correct one, it is a liability. Double-entry: two people enter independently, rows are diffed.

Every row carries `validity` and `source_note`. Schedules are amended like anything else; a fee table without a validity range silently answers 2019 questions with 2026 rates.

## The limitation engine is the highest-consequence feature

Missing a limitation period is one of the most common and most irreversible self-representation errors. The calculator surfaces the **article it applied, its period, and its trigger event** so a user or advocate can check the reasoning rather than trust a number. Where a matter is time-sensitive, the deadline is surfaced **before** the substantive right — a correct explanation of a remedy that is already time-barred is not a useful answer.

## Document factory — AI interviews, code decides

Four stages, and the authority boundary is the whole design:

1. **Interview** — schema-driven. The field list is code; the model handles phrasing, clarification and validation only. Every answer typed and validated (CNIC format, dates, amounts, jurisdiction).
2. **Clause selection** — a **deterministic rule table** keyed on document type, province and interview answers. Each rule cites the statute that requires the clause. Fully auditable.
3. **Duty and fee computation** — per-province, date-versioned tables.
4. **Typeset** — Jinja2 → LaTeX → sandboxed `pdflatex`. XeLaTeX with a Nastaliq face for bilingual.

**A model must never choose which clause enters a legally operative document.**

Every output carries a **provenance block**: template version, rules fired, statutes relied on, and an unambiguous statement that it has not been settled by an advocate. A rejected document is a bad day; a document that costs someone their property because it looked official ends the project.

Start with three templates reviewed by a practising advocate, then scale. Template count is a poor proxy for value and a good proxy for liability.

## Precedent citator

- Treatment list via recursive CTE over `citation_edge`, ordered by court seniority then date.
- **Always show coverage** — "from 3,412 SC judgments indexed, 2009–2026". Missing judgments must never read as "no precedent".
- **Good-law signal shows its evidence**, never a bare badge. A confident wrong "still good law" badge is a malpractice generator.
- Treatment classification carries a confidence and the paragraph that produced it. The grammar finds the reference; the model classifies the treatment.
- Outcome statistics disclose selection bias on the chart — only reported judgments are indexed and they are not a random sample.

## Procedure guides

Expert-authored, versioned, each step citing its statutory basis. **Official URLs are stored data with a weekly health check, never model-generated** — that eliminates the hallucinated-link failure mode entirely.

## Verify online before you claim

- **Provincial amendments to the Stamp Act and Court Fees Act** diverge sharply and change. Verify current rates before entering or updating a schedule row.
- **Official portal URLs** (NADRA, FBR, SECP, provincial revenue) before adding them to the procedure database.
- **Whether a judgment has been overruled or a provision struck down** — never assert from training data; delegate to `legal-source-scout`.

## Common failures

- Letting the model pick clauses "because it knows the law".
- A calculator that returns a number without the article it applied.
- A citator that renders silence as "no precedent" instead of stating coverage.
- Shipping a document template no advocate has reviewed.
