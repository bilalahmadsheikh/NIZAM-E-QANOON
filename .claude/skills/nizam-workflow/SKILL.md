---
name: nizam-workflow
description: How to build Nizam-e-Qanoon — decompose a request into the smallest useful slice, take that one component all the way to done before starting the next, work in layer dependency order, trace every decision to a document, and satisfy the definition of done. Load whenever implementing, adding a feature, starting a module, or when a prompt asks for several things at once.
---

# Nizam-e-Qanoon — how work gets done here

**Reference:** `docs/01-master-architecture.html` §6 (layer specs), §8 (modules and ownership) · `CLAUDE.md`
**Intent:** Four people, twenty-four weeks, and a corpus that determines the ceiling on everything else. Breadth-first produces nine half-features and no product. Depth-first produces a product.

## The rule

**One small component, taken all the way to done, before the next one starts.**

Not one layer. Not one module. One *component* — the smallest thing that can be finished and verified on its own: a segmenter for one numbering pattern, a single QA gate, one repository method, one screen state.

## When a prompt asks for several things

Do not build them in parallel and do not produce an outline of all of them.

1. **Decompose out loud.** List the components the request actually contains, in dependency order.
2. **Name the first slice** and say why it is first — usually because everything else reads its output.
3. **Build that one, completely.** Definition of done below.
4. **Report, then take the next.** A short handover: what is done, what it does, what is next.

If the user wanted all of it sketched instead, they will say so. The default here is depth.

## Dependency order

```
L1 corpus → L2 storage → L3 retrieval → L4 generation → L5 services → L6 API → L7 clients
```

Building L3 against a corpus that is not yet trustworthy wastes both efforts — you cannot tell a
retrieval bug from a segmentation bug, and the evaluation numbers mean nothing. Within a layer,
follow the pipeline order the layer's document sets out.

Two exceptions, both from doc 01: the **curation console** is built in phase 1 alongside ingestion
rather than later, and the **golden set** is built before the retrieval it measures.

## Definition of done

A component is finished when all of these are true. Not four of five.

- **It runs** against real project data, not a toy fixture — for corpus work that means an actual PDF from `data/`.
- **It is tested**, including the failure the component exists to prevent. A test that only proves the happy path proves little here.
- **The invariants it touches are enforced in code**, not in a comment. If it produces a citation, INV-1 is structural. If it reads a provision, `as_of` is not optional.
- **It matches its document**, and where it deviates the deviation is recorded — either the code changes or the doc does, but they do not silently disagree.
- **Errors are handled the project's way**: abstention, offline, stale and degraded are outcomes with their own shapes, never exceptions or error responses.
- **Nothing was left half-built beside it.** No stub files, no `TODO: implement`, no second module started "while I was there".

## Trace every decision

Cite the doc and section when you make one: *"chunking at section level per `docs/02 §5.3`"*.

When the documents do not cover something, **say so explicitly** rather than inventing a convention
quietly. Then propose one, and record it where it belongs. The docs are the contract; undocumented
convention is how four people end up with four conventions.

Never re-derive the measured facts in `CLAUDE.md`. They were measured from the archives on disk.

## Verify externally, do not recall

Prices, free-tier limits, extension availability, library APIs, and the current status of any
Pakistani statute all change and have all been quoted wrongly here before. Look them up, or delegate
to `legal-source-scout` and `vendor-verifier`. Anything Anthropic-related goes through the
`claude-api` skill.

## Review before moving on

Delegate the finished slice to the agent that owns it rather than self-certifying:
`corpus-auditor` · `schema-reviewer` · `grounding-reviewer` · `client-reviewer` · `eval-runner`.

For anything touching retrieval, prompts or the corpus, the golden set runs and a regression blocks
the merge — that is a gate, not advice.

## When to stop and ask

Stop when a choice would be **expensive to reverse** and the documents do not settle it: a schema
shape, an interface signature, a dependency, anything that becomes load-bearing. Ask once, concisely,
with a recommendation.

Do not stop for ordinary judgment calls — naming, file placement, which test to write first. Make
the call, state it in one line, and keep going.

## Anti-patterns specific to this project

- Scaffolding all seven layers with empty modules "to see the shape". The shape is in doc 01.
- Tuning retrieval before the golden set exists. There is nothing to tune against.
- Writing the API before the repository it calls, so the contract gets designed backwards from a route.
- Starting the Flutter client before `IPublicAPI` is generated from a real OpenAPI spec.
- Adding a second datastore, a lower threshold, or a citation string builder — all three are settled
  and all three are tempting under deadline.
