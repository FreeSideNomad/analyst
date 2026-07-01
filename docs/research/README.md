# Research — ATDD, Agentic Coding, and the State of the Art (2026)

Background research for `analyst`, which is built under **DAE (Disciplined Agentic Engineering)** with **ATDD** at its core (see [`CHARTER.md`](../../CHARTER.md)). These documents map where that methodology sits in the 2026 landscape, the intellectual lineage it descends from, and the open problems it does *not* solve.

## How this research was produced

- **Method:** a two-hop citation network rooted at **Robert C. Martin (Uncle Bob)**. Hop-1 = his documented ATDD lineage and collaborators; hop-2 = the sources *those* nodes cite, ranked by how many hop-1 nodes point at each (a centrality measure *within* the tradition).
- **Gathering:** a 58-agent research run built the hop-2 network and collected dated developments from **April–July 2026**.
- **Verification:** every development claim passed **3-vote adversarial verification** (15 of 16 survived; 1 was killed). "Verified" means *published and datable to the window* — it does **not** certify vendor performance numbers or settle the contested debates.

## Documents

1. [`01-sota-atdd-agentic.md`](01-sota-atdd-agentic.md) — the narrative: how the acceptance test went from safety net to steering wheel, told from Uncle Bob out.
2. [`02-trusted-source-network.md`](02-trusted-source-network.md) — the citation-graph methodology, hop-1 / hop-2 tables, and network diagram.
3. [`03-developments-apr-jul-2026.md`](03-developments-apr-jul-2026.md) — the 15 verified developments, annotated with dates, sources, and verification status.
4. [`04-keeping-agents-honest-landscape.md`](04-keeping-agents-honest-landscape.md) — the eight schools of thought on keeping agents honest, and which failure mode each addresses.
5. [`05-controls-decision.md`](05-controls-decision.md) — ADR: we considered adding enforcement controls to this repo and decided **not** to; the reasoning, and the one idea worth keeping.
6. [`references.md`](references.md) — master source list `[1]`–`[23]`.

## Standing caveat

This is a snapshot of a fast-moving field, assembled from web sources in mid-2026. Treat the narrative as *oriented opinion grounded in cited evidence*, not settled fact — especially section 05 of document 01 ("Contested ground").
