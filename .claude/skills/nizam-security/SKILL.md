---
name: nizam-security
description: Security and privacy rules for Nizam-e-Qanoon — data classification, the threat model, the anonymous-mode proof, identity and RLS, cryptography and key handling, AI and RAG-specific attacks, legal evidence integrity, mobile and supply-chain hardening, audit telemetry and incident response. Load when handling user data, authentication, secrets, logging, PII, the audit record, or anything with a privacy or abuse dimension.
---

# Nizam-e-Qanoon — security and privacy

**Reference:** `docs/11-security-and-privacy.html`
**Intent:** Users type the facts of criminal exposure, family disputes and immigration status into this product. The data is more sensitive than the software is impressive, and the design has to reflect that ordering.

## Anonymous mode is proved, not configured

The container binds `NullTelemetrySink`, an in-memory history store, and **no durable write queue at all**. Routes, notifiers and repositories are byte-identical between modes — there is no `if (anonymous)` anywhere, because a boolean checked in twenty places will eventually be missed in the twenty-first.

**The proof is a test asserting the anonymous container binds no durable writer.** Absence of a writer cannot be forgotten; a flag can.

Consequences that follow: no query text in logs, no analytics events, ephemeral session key, and **voice server-fallback disabled entirely** — a voice query leaving the device is a recording of someone describing a legal problem aloud.

## Data classification drives everything else

Corpus text is public. **User query content, draft field values, saved matters and voice audio are the sensitive tier** — and the audit record straddles both, which is why it stores query text only when the session is not anonymous.

Telemetry **drops rather than truncates**: a truncated legal query is still a legal query. Crash reports strip strings from any type marked sensitive.

## Identity and authorisation

- Phone-first — most users have no email. OTP on signup and new-device sign-in only, never per session.
- `FORCE ROW LEVEL SECURITY`, not merely `ENABLE` — without it policies are bypassed for the table owner, which is the role migrations run as.
- The application role has **no write grant on corpus tables at all**. That is the database-level expression of "there is no second write path".
- Deletion propagates to backups, anticipating the Personal Data Protection Bill.

## Cryptography — do not improvise

Tokens in platform keystore/keychain only, never shared preferences, never in the SQLite pack, never logged. Pack authenticity is Ed25519 with the public key compiled into the binary; the signature is checked **before** the transaction opens and the integrity hash **after** it commits. Certificate pinning uses an SPKI pin set with at least one backup pin and a signed kill switch.

Look up current guidance for anything involving token rotation, password hashing parameters or session fixation. Do not recall a parameter.

## AI and RAG-specific exposure

- **Prompt injection through corpus content.** Statutory text is trusted; judgment text and any user-uploaded document are not. Retrieved content is data in the prompt, never instruction.
- The model never receives credentials, never emits URLs, and never has tool access on the answer path.
- Cached and pre-generated answers carry the same access rules as live ones — the answer tier must not become a way to read another jurisdiction's scoped corpus.

## Legal evidence integrity

INV-3's audit record is also the challenge record. It must be **append-only**, tamper-evident, and complete enough to reconstruct a disputed answer exactly: query, filters, retrieved IDs with scores, gate decision, prompt hash, model version, verifier verdicts, corpus version. An answer nobody can reproduce is an answer nobody can defend.

## Verify online before you claim

- **Current OWASP guidance** (Top 10, ASVS, LLM Top 10) rather than a remembered list.
- **Library CVEs** before pinning a dependency version.
- **The status of the Personal Data Protection Bill** — it was pending, and its obligations shape retention and deletion. Never assert its content from training data; delegate to `legal-source-scout`.
- Platform keystore behaviour and backup-exclusion flags per OS version.

## Common failures

- An `if (anonymous)` branch, anywhere.
- Query text in an error log or a crash report.
- Treating retrieved judgment text as trusted input to a prompt.
- `ENABLE` without `FORCE` on RLS.
- A secret in the compose file rather than a `0600` file.
- Assuming a deleted row is gone when it is still in the backup repository.
