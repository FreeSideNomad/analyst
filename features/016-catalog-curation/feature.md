---
slug: catalog-curation
title: Catalog curation — answerable clarifications & meaning corrections
outcome: The semantic catalog becomes genuinely human-curatable (charter promise). A "Needs review" clarification is a real form — selectable options plus a free-form "Something else" answer — and submitting it sends the answer through the Claude Agent SDK as ground truth to COMPLETE the semantic analysis, updating at most that column's description and its own table's description, clearing the clarification, and recording the answer as provenance. Any column/table description carries a "suggest a correction" affordance with the same pipeline; curated entries are badged human-confirmed and are STICKY — later automatic re-cataloguing never silently overwrites a human-settled meaning. Offline fallback applies the user's words verbatim (still sticky) and reconciles when AI is next available. Settled meanings immediately sharpen NL Q&A, which plans against the catalog.
status: done
autonomy_level: high
assignee: local
owner: igormusic
area: profiling
roadmap_ref: catalog-curation
tracker_ref: local://catalog-curation
branch: catalog-curation
validation_method: "Acceptance board: answer a clarification (option AND free-form) -> description updated within the column+own-table blast radius, clarification cleared, provenance recorded (cassette-replayed agent turns); stickiness pinned across re-catalogue and restart; offline fallback = verbatim edit; browser e2e for the form and the correction affordance. Mutation gates on stickiness and on blast-radius containment."
size: M
created: 2026-07-18
---

# Feature 016 — Catalog curation

> Promoted from discuss 2026-07-18 (owner decision: "ahead of dashboards —
> completes the feature", i.e. completes the semantic-catalog spine). 015
> dashboards remains parked at its AC-review gate; 016 builds first.

Decisions fixed in discussion (owner-confirmed):
- **Blast radius v1**: the corrected column's description + its own table's
  description. NO cross-table ripple — that is a named later slice reusing
  the 010 workspace-context machinery.
- **Curation model**: suggest → agent synthesizes (user note authoritative,
  catalog voice consistent); direct-verbatim edit is the offline fallback,
  reconciled later. Both paths mark the entry human-confirmed + sticky.
- Clarification answers and corrections share one pipeline and one
  provenance record.

Charter anchors: "per-workspace, agent-built, human-curatable" catalog;
AskQuestion as the product-wide clarification primitive; prompts + expected
structured outputs are versioned artifacts; governance unchanged (the model
sees profile metadata + the user's answer, never bulk rows).
