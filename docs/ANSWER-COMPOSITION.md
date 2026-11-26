# Answer composition: law and precedent in one grounded answer

**Status:** proposed (D-172, 27 Nov 2026). Design for review by the team before L4 starts. It changes no
interface silently: the two contract additions it needs are listed in §9 as proposals to docs/01, docs/05 and
docs/06.
**Layers:** L3 (two retrievers, as built), L5 (precedent context, new), L4 (generation and verification, not
built), L6 (orchestration, not built).
**Reads:** docs/01 §5 interface table, docs/04, docs/05 §3, §6–§7, docs/06 §2, §5, docs/13 §6,
PRECEDENT-MODEL.md, RETRIEVAL-STATE-2026-11-21.md.

---

## 1. The problem in one question

> *"I am accused in a cheque case in Lahore. Can I get bail?"*

A correct answer needs three kinds of material:

1. **The rule:** s.489-F PPC (the offence, its punishment) and s.497 CrPC (bail in a non-bailable offence, the
   prohibitory clause).
2. **How courts apply it:** the Lahore High Court and the Supreme Court on when a s.489-F case calls for
   further inquiry. These are binding on a Punjab trial court (Arts. 189, 201). A Sindh High Court judgment on
   the same point is persuasive only.
3. **The limits:** which courts and years the library holds, which facts the answer depends on, and that this is
   legal information, not advice.

Today the two halves exist separately. `retrieve()` returns the sections; precedent search
(`/v1/precedent/search`) returns judgments. Nothing joins them into one answer, and L4, which writes an answer,
has not started. This document fixes how they are joined, and how the answer's reasoning is made checkable.

## 2. What we already have (as built, 27 Nov 2026)

| Piece | What it gives the answer | Where |
|---|---|---|
| Statute retrieval | `retrieve(question, Filters(as_of, territory)) → GroundingContext \| Abstention`. Whole units with in-scope definitions, qualifications, references, conflicts and sub-questions, gated (GPU answered precision .944 on test) | `nizam/retrieval/gate.py`, `assembly.py` (D-102–D-112) |
| Precedent search | Judgment paragraphs by BM25, dense (bge-m3 or 8B), the statutes the question cites, and the case number. Fused, with a vote for judgments binding the forum | `nizam/retrieval/precedent.py` (D-116–D-167) |
| Judgment → law links | 329,141 of 437,377 statute citations resolved to the provision, and to the version in force on the decision date; a federal law also linked to the province's copy | `judgment_statute_reference` (D-122, D-136, D-164) |
| Law → judgments | `/v1/law/provisions/{id}/judgments`: the judgments on a provision, by how they treat it (interpreted before cited), court and date, with judicial status | `JudgmentRead.provision_judgments` |
| Authority | Dated binding rules read from Arts. 189, 201, 203 and 203GG, per territory, including AJK and GB courts | `court_*`, `nizam.storage.authority` (A24, D-141) |
| Treatments and lineage | 498 case treatments from the courts' own words; appeal chains and later history. Negative ones shown only when lawyer-verified | 0143–0145 (D-159, D-160) |
| Invalidation | Struck-down and repugnant provisions as review candidates (140). A verified whole-unit review removes a unit from `operative_provision` | 0146 (D-161) |
| Coverage | Per court: judgments held, years, undated share, sources not held | `/v1/precedent/coverage`, SOURCES-NOT-HELD |
| Route hint | The statute search abstains on "what did the court decide" with `gate.refer_to = "precedent"` | D-170 |

## 3. What we measured for this design

`evals/law_precedent_join_study.py` (dev splits only; `evals/results/join-study-2026-11-27.json`).

**A. Do the right sections have judgments on them?** Statute dev, 276 cases, 292 gold units:

| Gold units… | Share |
|---|---|
| cited by at least one released judgment | 72.6% |
| interpreted, quoted or challenged (not only mentioned) | 43.2% |
| cited by a court binding the case's forum (SC, or the forum's own High Court) | 65.1% |

A cited unit has a median of 17 citing judgments.

**B. Does "the law first, then the judgments citing it" reach the right judgment?** Precedent dev, 73 answerable
cases, case lookups excluded. The CPU statute search was run on each question:

| Measure | Value |
|---|---|
| The gold judgment cites some provision | 93.2% |
| The gold *paragraph* cites a provision | 52.1% |
| A provision the gold judgment cites is in the statute search's top 10 | 45.2% |
| A provision the gold paragraph cites is in the top 10 | 31.5% |
| Judgments citing the top-10 units (the pool a ranker must sort), median | 53 |

By stratum (top 10): provision questions .91, issue .43, Urdu .29, authority .25, temporal 0.

**C. What the join adds to precedent search** (same 73 cases; a gold judgment anywhere in the candidates):

| Profile | Precedent search alone | Plus the law join | Found only by the join |
|---|---|---|---|
| CPU | .712 | .795 | 6 cases |
| GPU (8B) | .767 | .836 | 5 cases |

**D. Can we tell that a court read an older text?** Each link stores the provision version in force on the
decision date. But only 27,550 of 329,141 resolved links (8.4%) have a dated version; the rest are `not_dated`,
because most laws are served only from their capture date (`text_known_from`). Of the dated links, none points to
a version that has since ended. The check is cheap and must run, but today it rarely has the data to fire.

**What follows:**

- The join is a second generator, not a replacement. Alone it reaches about half the gold. Together with
  precedent search it adds 7–8 points of candidate recall, and it carries the provision questions that precedent
  search finds hardest.
- It returns large pools (median 53), so it needs ranking against the question, never "all judgments citing
  s.497".
- About a quarter of the right sections have no judgment on them in the library. So "no precedent found" is a
  normal outcome, stated with its coverage, never a failure and never an answer.

## 4. What others found (external research, 27 Nov 2026)

Each source is summarised as reported. Figures from preprints or vendors are marked; none is our own measurement.

- **Commercial legal RAG still fails often.**
  - Magesh et al., *Hallucination-Free?* (Stanford, J. Empirical Legal Studies 2025): Lexis+ AI and Ask Practical
    Law AI gave misleading or false information on more than 1 in 6 queries; Westlaw AI-Assisted Research on
    about one in three.
  - The paper counts a citation that exists but does not support its proposition as a hallucination. It finds
    jurisdiction- and time-specific questions hard.
  - *For us:* existence of a citation is not enough. Every claim's support is checked (docs/05 T1–T3), and
    as_of and territory are hard filters, never hints.
- **Treatment is per point of law, not per case.** Shepard's and KeyCite flag a case as negatively treated if it is
  no longer good law on *at least one* point. Researchers are told to read headnote-level treatment, since other
  holdings may stand.
  - *For us:* we hold no headnotes (D-120). Our unit is the judgment paragraph and the proposition (docs/06 §5),
    and we never show a whole-case "good law" badge (docs/06 §5.1, docs/13 J-06).
- **Claim-level audits find the same weak spot.**
  - L-MARS (arXiv 2509.00761) decomposes answers into atomic claims and labels each against its source: supported,
    partially supported, unsupported, unreachable.
  - LegalCiteTrust (arXiv 2607.20872) checks three things: that the authority exists, that it is described
    faithfully, and that it applies to the local claim rather than merely sharing the topic.
  - A claim-level legal RAG benchmark (arXiv 2605.21071) finds NLI verifiers weakest at detecting contradiction.
  - *For us:* the three checks map onto INV-1 (existence by construction), T2 (faithfulness) and an applicability
    check (§7). Claims about authority, conflict and negative treatment go to T3 or to deterministic L5 findings,
    never to NLI alone.
- **Case retrieval is hard everywhere.** CLERC (Hou et al., NAACL Findings 2025; 1.84M US federal cases):
  zero-shot retrievers reached 48.3% recall@1000. In generation, the model with the best ROUGE also hallucinated
  most.
  - *For us:* our precedent figures are in a hard regime. Fluency is not a quality signal.
- **Statute + case structure helps.** An Indian legal hybrid of case-law, statute and penal-code retrieval with a
  knowledge graph (arXiv 2602.23371, preprint, not verified here) reports a 70% pass rate against 37.5% for
  RAG alone. Several knowledge-graph papers link judgments to provisions as we do.
  - *For us:* consistent with §3C; our links are the graph.
- **Pakistan's own rule for AI in courts.** The National Judicial (Policy Making) Committee issued national
  guidelines for AI in judicial institutions on 29 Apr 2026 (Dawn, The News, Geo, as reported): AI assists and
  does not replace judicial decision-making, with human validation checkpoints.
  - *For us:* the product register stays legal information with sources a person checks. We have read news
    summaries, not the guidelines' text; quote them only after reading the official text.

## 5. The design: one question, seven stages

```
question ─► 1 understand ─► 2 law evidence (L3 retrieve)  ─┐
                       └──► 3 precedent evidence (L5)  ─────┼─► 4 compose packet (L5) ─► 5 generate (L4)
                                                            │                        ─► 6 verify (L4) ─► 7 show (L7)
                       (each stage's decision and IDs persisted: INV-3)
```

### Stage 1: understand and route (L3 query understanding, L6 decides the route)

`parse()` already yields the territory, citations, sub-questions and scope findings. The route is chosen from
them, never by a model:

| The question asks… | Route |
|---|---|
| what the law says or requires (most citizen questions) | law first, precedent attached (stages 2–7) |
| what a court decided, a case by number, a law-report citation | precedent only. The statute search's `refer_to = "precedent"` (D-170) says so |
| "judgments on section X" | precedent, through the law join (§3B: .91 on this stratum) |

### Stage 2: law evidence (L3, as built)

`retrieve(question, Filters(as_of, territory))`. If it abstains, the answer abstains, with these exceptions:

- the abstention is a `refer_to` route (stage 1), or
- the question is precedent-only and stage 3 passes.

INV-2 is unchanged: no claim is made from material that did not pass a gate.

### Stage 3: precedent evidence (L5, new: `IPrecedent.contextFor`)

Input: the passed `GroundingContext` (its units, as_of, territory, forum) and the question.

1. **Two generators, fused by RRF** (k=60, as everywhere else):
   - (a) the **law join**: judgment paragraphs citing the context's top units or a unit inside them, roles
     `interpreted`, `quoted` or `challenged` before `cited`. The `treatmentsOf(provisionId)` path of docs/06 and
     the existing `provision_judgments` read.
   - (b) **precedent search** on the question (BM25, dense, cited, case), as served.
2. **Time:** only judgments existing at as_of (decided on or before; for an undated one, its latest possible day,
   D-124). Precedent search already enforces this, and the join must too.
3. **Authority, per judgment:** an `AuthorityFinding` from the recorded rules (`binding`, `persuasive`,
   `not_recorded`) for the forum at as_of (A24). The model never derives it (docs/05 §2).
4. **Treatment and lineage:** a judgment with a lawyer-verified negative treatment or reversal on the proposition
   is excluded. Unverified ones are carried as "awaiting review", never as fact (D-159, D-160).
5. **Version check:** where the link's version is dated and differs from the version at as_of, the paragraph is
   marked "decided on an earlier text of s.X" (§3D). Undated links say nothing either way. The packet records that
   the check could not be made, and no claim is written as if it had passed.
6. **Precedent gate:** a separate calibrated gate (logistic over rank and score features, fitted on precedent dev
   like D-106). Output `PrecedentContext | PrecedentAbstention`.
   - A precedent abstention on a law-first question is **not** an answer abstention. The answer goes on with the
     law and a coverage-limit block: "No judgment in the library clearly applies this provision. The library holds
     … (courts, years)".

### Stage 4: the evidence packet (L5)

One sealed packet for L4: provision units with their prefix text, judgment paragraphs, and for each paragraph:

- court, date, bench and opinion role;
- the `AuthorityFinding`;
- the provision(s) it interprets, with the link role;
- treatment status;
- the version note.

It also carries the conflicts (statutory `notwithstanding` and `subject to`, and judgments of equal authority
disagreeing) and the coverage.

Every item gets a request-local handle (E1, E2…, docs/05 §3), dynamically allow-listed in the output schema. A
judgment paragraph is a citable unit, exactly as a provision is (INV-4; docs/05 line "provenance ends at a provision
or judgment paragraph").

### Stage 5: generation, where the reasoning is a claim graph, not prose (L4)

The model writes **atomic claims in typed blocks** (docs/05 §3), never free text and never chain-of-thought
(docs/05 §6). The blocks are ordered as a lawyer reasons. This is IRAC, made checkable:

| Block (docs/05 kind) | Issue → Rule → Application → Conclusion | Must cite |
|---|---|---|
| `short_answer` | Conclusion, conditional where the facts decide it | the claims below it, by ID |
| `rule` | Rule: what the section says | provision units only |
| **`interpretation`** (proposed, §9) | Rule as courts read it | a judgment paragraph **with** its `AuthorityFinding` |
| `conditional_application` | Application: "if your case …, then …" | provisions and/or judgments |
| `qualification` | Provisos and exceptions | provision units |
| `conflict` | Disagreeing authority, `notwithstanding` | both sides |
| `procedure` | What to do next | provisions, or reviewed procedure rules (L5) |
| `coverage_limit` | What the library does not hold | coverage records |

Rules the schema enforces:

- An `interpretation` claim's text may say "binding" or "persuasive" only as the rendered value of its handle's
  `AuthorityFinding`. The model emits the handle; L4 renders the word (INV-1 for authority).
- A claim about a judgment never states that a case is good law, overruled or followed unless that is a verified
  L5 finding (docs/06 §5.1).
- Statute text controls. A judgment may narrow, explain or apply a rule, but where the packet's section text and a
  paragraph disagree, the answer states both and the dates (`conflict`). It never prefers the paragraph silently.
  A judgment on an earlier text (§3D) is labelled as such.
- Binding first: within `interpretation`, binding paragraphs precede persuasive ones. A persuasive paragraph alone
  is written "the X High Court has held …, which a court in Y may follow but is not bound by".
- Two equal binding authorities that disagree make a `conflict` block, never a resolution by the model. (Which one
  prevails: larger bench, later decision. That is a legal rule L5 does not yet encode, §10.)

### Stage 6: verification (L4, docs/05 T0–T4, with precedent checks)

On top of docs/05's tiers, every claim citing a judgment paragraph passes three checks, the three that the
external audits separate (§4):

1. **Exists:** by construction. The handle resolves to a released paragraph at as_of (INV-1).
2. **Faithful:** T1 (numbers, dates, negation, shall/may) and T2 (multilingual NLI) between the claim and the
   paragraph's text.
3. **Applies:**
   - (a) the paragraph is linked to a provision cited in the `rule` block, or is a precedent-route answer to the
     same issue;
   - (b) its `AuthorityFinding` matches the wording;
   - (c) no verified negative treatment;
   - (d) the date is at or before as_of.

   Claims of authority, conflict, liberty, custody and limitation also go to T3 (adversarial), because NLI is
   weakest at contradiction (§4).

Then the docs/05 T4 answer gate: the direct answer, the governing rule, required qualifications and any conflict
must all survive. Otherwise `ANSWER_INCOMPLETE_AFTER_VERIFICATION`.

### Stage 7: show (L7, docs/13)

- Plain conclusion first, then the reasoning blocks, then the sources. Each claim's chip opens the exact
  provision or paragraph.
- Judgment chips show court, date, binding/persuasive, opinion role and treatment.
- No green/red badge. The coverage-limit block is always visible when precedent abstained.

## 6. What is persisted (INV-3)

Per answer:

- the question, filters and route;
- both retrievers' IDs and scores, both gate decisions and their calibration versions;
- the packet digest, with every handle's resolved ID, `AuthorityFinding` and treatment state;
- the prompt hash, model and version;
- every claim's verdict per tier;
- the corpus version.

These are docs/05 §9's normalised `answer_claim`, `answer_claim_evidence` and `verification_result`, extended with
`answer_dependency` rows for judgments. Re-landing a judgment, or a new verified treatment, invalidates the answers
that depend on it in the same transaction (docs/05 §9).

## 7. How we measure it (docs/10)

- **Precedent context (stage 3):** on precedent dev v2 (89 cases, D-168), hit@10, recall@50 and paragraph@10 of
  the fused join + search, against search alone. The join ships if recall@50 rises with a paired CI clear of zero
  and hit@10 does not fall (§3C predicts +7 to +8 points of candidate recall). Precedent gate: answered precision
  ≥ .90 on dev, then test once.
- **Composition:** a new stratum is needed.
  - It is a **combined** golden stratum: law questions whose gold names both the provisions and the judgment
    paragraphs that apply them, with the forum's expected authority.
  - None exists yet. The statute sets name provisions only, and the precedent sets name paragraphs only.
  - It is built by reading, as D-133 and D-168 were. A first 50 cases can reuse the precedent set's families whose
    gold paragraphs cite the statute gold.
- **Generation:** docs/05's metrics (support, completeness, register, Urdu parity), plus two precedent ones:
  - authority wording errors: target 0;
  - claims citing a judgment that does not apply (check 3): target 0 on the locked set.

## 8. Build order (one slice at a time, CLAUDE.md)

1. **S1 — Precedent context in L5** (`IPrecedent.contextFor`).
   - Law join + search fusion, the time and authority filters, treatment exclusion, the version note.
   - Measured as §7 on precedent dev. No model is involved. This is the next slice.
2. **S2 — Precedent gate:** calibrated on dev, like D-106. `PrecedentContext | PrecedentAbstention`, with the
   coverage-limit wording.
3. **S3 — The combined golden stratum** (50 cases first). It needs reading. Two-person review and κ need people.
4. **S4 — L4 generation port** (docs/05 §3): schema with the `interpretation` block, data-only prompt, provider
   adapter, T0–T1.
   - Evaluated first with *oracle* packets, then retrieved ones.
   - The model and provider are chosen by the docs/05 §5 locked-set rule, verified online at the time, not from
     memory.
5. **S5 — T2/T3 verification**, including Urdu parity.
6. **S6 — L6 `/v1/answer`**: orchestration, SSE of verified blocks only, INV-3 persistence.
7. **S7 — L7 answer view** (docs/13 §6).

## 9. Contract changes this needs (proposals, not silent edits)

1. **docs/06 `IPrecedent`:** add `contextFor(context: GroundingContext | null, question, scope) → PrecedentContext |
   PrecedentAbstention`. It composes `treatmentsOf` and precedent search; L6 calls it between `retrieve()` and
   `generate()`.
2. **docs/05 `DraftBlock.kind`:** add `interpretation`. Its claims must cite at least one judgment-paragraph
   handle, and their authority words are rendered from `AuthorityFinding`.
3. **docs/01 interface table:** L6 orchestrates `IRetrieve → IPrecedent.contextFor → IGenerate`. Each layer still
   calls only the one below (L5 reads L3 results passed in, and L2 through its own reads).

## 10. Open questions

- **Which of two conflicting binding judgments prevails** (larger bench, later decision, per incuriam). That is a
  legal rule. Until L5 encodes it from the Constitution and from verified practice, the answer shows a `conflict`
  and does not choose. *Owner or lawyer decision.*
- **Coverage wording for citizens:** how much of "the library holds these courts from these years" a citizen
  should see (docs/13 §5 uncertainty). *UX decision.*
- **The 92% of links with no dated version (§3D):** acquiring dated amendment histories for the most-cited laws
  (CrPC, PPC, CPC, QSO, Constitution) would let stage 3's version check fire where it matters most. *Corpus work,
  scope to agree.*
- **The NJPMC guidelines' text:** read the official document before the product cites it, and check whether any
  provision bears on a citizen-facing tool (it addresses judicial institutions).

## Sources

- Magesh et al. (Stanford), *Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools*,
  J. Empirical Legal Studies (2025); preprint
  [arXiv 2405.20362](https://arxiv.org/abs/2405.20362);
  [Stanford HAI summary](https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-queries).
- *LegalBench-RAG: A Benchmark for Retrieval-Augmented Generation in the Legal Domain*
  ([arXiv 2408.10343](https://arxiv.org/abs/2408.10343)).
- Hou et al., *CLERC* ([ACL Anthology 2025.findings-naacl.441](https://aclanthology.org/2025.findings-naacl.441);
  [arXiv 2406.17186](https://arxiv.org/abs/2406.17186)).
- *L-MARS* ([arXiv 2509.00761](https://arxiv.org/pdf/2509.00761)); *LegalCiteTrust*
  ([arXiv 2607.20872](https://arxiv.org/pdf/2607.20872)); *Fine-grained Claim-level RAG Benchmark for Law*
  ([arXiv 2605.21071](https://arxiv.org/pdf/2605.21071)).
- *Domain-Partitioned Hybrid RAG for Legal Reasoning (India)*
  ([arXiv 2602.23371](https://arxiv.org/html/2602.23371v1)), preprint, figures not verified here.
- Shepard's signal indicators ([LexisNexis](https://www.lexisnexis.com/en-us/support/lexis/faqs/shepards-signal-indicators.page));
  KeyCite flags (law-library guides, e.g. [University of South Carolina](https://guides.law.sc.edu/LRAWSpring/LRAW/updatingfedcases)).
- NJPMC guidelines on AI in judicial institutions, 29 Apr 2026, as reported by
  [Dawn](https://www.dawn.com/news/1996074), [The News](https://www.thenews.pk/story/1412798-here-are-key-guidelines-for-ai-use-in-pakistan-courts)
  and [Geo](https://www.geo.tv/latest/662137-njpmc-unveils-national-guidelines-on-use-of-ai-in-courts); official text
  not yet read.
