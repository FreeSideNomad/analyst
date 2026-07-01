# ADR: Additional Agent-Honesty Controls — Deferred

**Status:** Decided — do **not** build (2026-07-01)
**Context:** research in this folder; `CHARTER.md`

## Decision

We considered building a set of enforcement controls (and a reproducible Claude Code plugin to carry them across repos) to mechanically enforce what DAE currently documents: oracle isolation / anti-test-gaming, a deterministic command monitor, independent verifier agents, least-privilege/secrets, and verification-before-done.

**We decided to defer all of it**, keeping only one idea as a candidate for later (below).

## Why

A control earns its place only when three things hold at once:
1. the agent *would* violate the rule,
2. existing safety nets *wouldn't* catch it, **and**
3. the cost of the miss is high.

For most proposed controls, condition 2 fails. This repo already has DAE's human-approved checkpoints, `.engineer` handoffs, git history, and (assumed) CI running the two test streams + mutation. Oracle-lock hooks, command monitors, and verifier agents largely **duplicate existing nets** — marginal insurance at real build-and-maintenance cost.

The "reproducible plugin across many repos" ambition also failed a YAGNI test: building for reuse before the controls have proven their value **even once** is speculative generality. Extract to a plugin *after* it earns its keep, not before.

## The one idea worth keeping

The CHARTER **governance boundary** — *"raw bulk data never leaves the box… what is sent to the model must be auditable/logged."* This clears all three bars:
1. an agent can silently place raw rows in a prompt — easy to do,
2. **code review won't reliably catch it** — it's a runtime data-flow property, not a visible diff, so existing nets miss it,
3. the cost is a data-leak / compliance incident — high and irreversible.

**If** we revisit this, the minimal slice is a single hook/wrapper on the Claude API call path that (a) logs every payload's size and shape and (b) flags/blocks payloads that look like bulk rows. No plugin. If it fires in real use and saves us, *then* consider extracting it. If it never fires in a month, we've learned the whole effort was unnecessary — cheaply.

## Consequences

- No new hooks, agents, or plugin are added now.
- DAE + CI + human review remain the control surface.
- The governance-boundary logger/guard is parked as a candidate, to be built only against evidence of need.
- The broader landscape of what we are *not* doing (CoT monitoring, AI Control protocols, interpretability) is documented in [`04-keeping-agents-honest-landscape.md`](04-keeping-agents-honest-landscape.md) so the gap is explicit, not forgotten.
