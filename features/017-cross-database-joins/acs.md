---
ac_count: 9
high_priority_count: 6
discovered: 2026-07-18
mode: greenfield
note: Autonomous session (standing delegation). Grounded in the 2026-07-18 engine probe.
---

# Acceptance criteria — 017 cross-database joins

## AC-1: A question spanning two databases is answered (High · happy-path)
With a CRM database (customers, segments) and a billing database (invoices)
connected, "which customer segment generates the most revenue?" returns the
correct totals — a join no single database could answer.

## AC-2: The trust trail names both databases (High · happy-path)
The answer's SQL discloses both connections' tables, so the cross-system
nature of the answer is inspectable.

## AC-3: The cross-database key is discovered (High · happy-path)
Relationship discovery surfaces `billing.invoices.customer_id →
crm.customers` (origin: inferred, with evidence) without any declaration.

## AC-4: The join executes locally (High · invariant/governance)
Neither remote system receives the other's data; the join runs in the local
engine over both attachments, and only metadata + capped results cross to
the model — the standing invariant, now pinned for the two-database case.

## AC-5: Restart and reconnect keep it answerable (High · cross-cutting)
After a restart with persisted credentials (011), the same question
answers again without re-setup.

## AC-6: A detached database fails safe (Medium · error)
After one database is disconnected, a question needing it abstains or
fails plainly — never a crash, never a fabricated answer.

## AC-7: Single-database behavior is unchanged (Medium · regression guard)
Questions answerable within one connection keep answering exactly as
before (existing boards stay green).

## AC-8: The synthetic sample kit is reproducible (Medium · tooling)
A committed generator script produces the two sample databases with
deterministic contents and documented expected totals, connectable through
the normal UI.

## AC-9: Errors are clean (folded) (Medium · error)
Connecting the same file twice under different names, or asking before any
database is connected, produces clean behavior (no crashes; the existing
not-connected abstention covers the latter).
