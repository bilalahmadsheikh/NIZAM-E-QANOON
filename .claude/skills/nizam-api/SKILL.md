---
name: nizam-api
description: Rules for the Nizam-e-Qanoon backend API layer (L6) — FastAPI module boundaries, the HTTP contract and problem responses, phone-first identity, anonymous mode, authorization and tenancy, answer orchestration, the audit and challenge record, the two sync engines, jobs, SLOs and degradation. Load when writing endpoints, auth, sessions, background jobs, sync, rate limits, or anything on the request path.
---

# Nizam-e-Qanoon — backend API

**Reference:** `docs/07-backend-api.html` · `docs/01-master-architecture.html` §4.1 (interface contracts)
**Intent:** One synchronous entry point, one place authorization is decided, and a record complete enough to replay any answer a user disputes.

## Modular monolith, not microservices

Domains as packages: `corpus` · `retrieval` · `generation` · `documents` · `procedure` · `identity` · `billing`. One deployable until a metric forces a split.

**One deliberate seam:** inference workers are a separate process from day one, because they need different hardware from the API and we want to move them to a GPU box without touching request handling.

## Every request carries a resolved context

`jurisdiction` · `as_of` · `language` + `script` · `reading_level` · `scope` (which corpus tiers this deployment serves) · `request_id`.

The context is resolved once, at the edge of the request, and threaded down. No layer re-derives it. `as_of` defaults to today and is never optional (INV-5).

## The audit record is not logging

INV-3: persist query, resolved filters, retrieved provision IDs **with stage scores**, gate decision, prompt hash, model version, verifier verdicts, corpus version — for every answer. This is what makes "the system told me the wrong thing" investigable rather than arguable, and it is the mechanism behind the challenge flow.

`/ask/{request_id}` is a real route. An answer is addressable.

## Anonymous mode swaps the object graph

Not a boolean checked at call sites — a boolean will eventually be missed. The container binds `NullTelemetrySink`, an in-memory history store, and **no write queue at all**. Routes, handlers and services are byte-identical; the code that could persist is simply not present.

Assert it in a test: the anonymous container binds no durable writer.

## Two sync engines, because two trust models

- **Corpus sync** — one way, signed, no merge logic, device is never a writer. That is what lets the pack be authoritative rather than a cache. Patches also carry `INVALIDATE` ops for stored answers whose cited provisions changed.
- **User-data sync** — bidirectional, last-writer-wins on a **server-assigned version**, tombstones for deletes. The cursor is a sequence value, **never a timestamp** — device clocks are wrong often enough that a timestamp cursor silently loses writes, and the failure is invisible until a user notices a deleted bookmark returned.

## Outcomes, not exceptions

Abstention, offline, stale and degraded are **outcomes** with their own response shapes — never HTTP errors. Only an actual fault is an error. A client that receives an abstention as a 4xx will render it as a failure, which inverts the meaning.

## Degradation is announced and narrower, never silent and approximate

The system may say "I can only search the text right now". It may **never** quietly answer with a lower confidence bar. No failure path anywhere may lower τ, skip verification, or substitute an ungrounded answer.

## Cost and concurrency

- Prompt-prefix caching, semantic response cache, and the offline answer tier are the levers — at scale, infrastructure is ~3% of the bill.
- PgBouncer in transaction mode when connections exceed ~60% of `max_connections`. Do not raise `max_connections` instead.
- Send SMS OTP on signup and new-device sign-in only, never per session.

## Verify online before you claim

- **Model provider rate limits, pricing and context windows** — via the `claude-api` skill, never from memory.
- **SMS aggregator rates** for Pakistan before quoting a per-message cost.
- **OWASP / auth guidance** if implementing token rotation or session fixation defences — do not improvise crypto.

## Common failures

- Returning an abstention as `4xx`.
- Re-deriving `as_of` or jurisdiction inside a service instead of taking it from context.
- A background job that writes to the corpus outside the publish transaction.
- Timestamp-based sync cursors.
- Logging query text while an anonymous session is active.
