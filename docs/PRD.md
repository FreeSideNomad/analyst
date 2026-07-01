# analyst — Product Requirements Document

> **Status:** Draft v0.1 · 2026-07-01 · Owner: igormusic
> **Companion docs:** `CHARTER.md` (engineering constitution), `.engineer/roadmap.md` (strategic feature list)
> This PRD is the product-level anchor. Individual features are formalized and built through the DAE/ATDD pipeline.

---

## 1. One-liner

**analyst** is a self-hosted, team AI data analyst: drop in Excel/CSV files or connect a database, and an agent automatically profiles, catalogues, and understands your data so anyone can ask questions in plain English and get trustworthy answers — with the profiling, relationships, SQL, and assumptions always one click away.

**Product metaphor: _autopilot by default, grab the wheel on demand._**

---

## 2. Problem & opportunity

Natural-language-to-SQL looks solved in demos and breaks in reality. The single most important finding from our competitive research:

- **The enterprise accuracy cliff.** Text-to-SQL systems reporting 85–90% execution accuracy on academic benchmarks (Spider 1.0) drop to **6–21%** on realistic enterprise datasets. [src: medium/visrow 2026]
- **The proven fix is a semantic layer.** Grounding the model in a curated semantic/context layer — metrics, relationships, disambiguation rules — is *structural*: a ~4KB hand-authored semantic doc lifts first-shot accuracy **+17–23 points** across frontier models (Claude Opus 4.7, Sonnet 4.6, GPT-5.4), and the semantic layer accounts for essentially all significant variance while model choice within a tier does not. [src: arxiv 2604.25149] dbt's 2026 benchmark: **~83% with a semantic layer vs ~40% raw text-to-SQL**; Snowflake+Atlan reported **3× accuracy at 95%+ reliability** on a 522-query benchmark when grounding in enriched semantic metadata.

So a semantic layer is table stakes for trust — **but building one is manual, expert work today.** That is the opportunity.

**The white space analyst can own:** no shipping product bundles all of these into a self-hosted, governance-first package:
1. Fully-automatic **agentic profiling** of uploaded/connected data,
2. Discovery of **undeclared PK/FK relationships, validated by tests**,
3. **Confidence-gated clarifying questions** when a query is ambiguous,
4. **Editable, revealable lineage/assumptions/SQL** on every answer,
5. Delivered as a **single self-hosted Docker image** where raw bulk data never leaves the box (federated query-through, local DuckDB execution).

Cloud incumbents (Snowflake, Databricks) have agentic auto-cataloguing and PK/FK inference but are warehouse-locked and send data to the warehouse's LLM stack. The leading open-source semantic-layer tool (WrenAI) is self-hostable and governed but its cataloguing is **manual/human-authored** (value profiling only on its roadmap as of v0.11.0, Jun 2026). Research systems (DBAutoDoc, LLM-FK, ProSPy, Intuit's Executable Schema Contracts) prove the auto-profiling/FK-discovery/abstention pieces individually, but they are papers, not shipped self-hosted team products. **analyst's differentiation is integration + local-first governance, not any single novel capability** — which also means execution quality is the moat.

---

## 3. Target users & personas

| Persona | Needs | How analyst serves them |
|---|---|---|
| **Business user** (primary reach) | Ask a question, get a correct answer + chart. Doesn't write SQL. | Autopilot: just ask. Confidence-gated clarification prevents silent wrong answers. |
| **Analyst / power user** (primary trust-builder) | Verify *how* the answer was derived; correct the agent; curate meaning. | Grab the wheel: reveal profiling, semantic catalog, generated SQL, lineage; edit via chat. |
| **Workspace admin** (first user) | Set up the team, control access, govern data egress. | First-user-becomes-admin; workspace permissioning; governance defaults. |

**Setting:** self-hosted server for a **team** (not single-user, not multi-tenant SaaS in v1). Deployed as one self-contained Docker image.

---

## 4. Product principles

1. **Autopilot by default, grab the wheel on demand.** Everything is automatic; every artifact is revealable and editable, but never forced on the user.
2. **Answer-first, trust-on-demand.** Lead with the plain-English answer + visual; progressive disclosure of assumptions → lineage → SQL → profiling for those who care.
3. **Confidence-gated, not confidently wrong.** Answer directly when confident; ask a clarifying question when ambiguity is high; abstain rather than guess on out-of-scope questions.
   - **Structured clarification is universal (the "AskQuestion" primitive).** Whenever the agent hits ambiguity — *anywhere*: ingestion, query, dashboard-building — it resolves it by emitting a **structured question with a small set of concrete options**, rendered as native React UI (selectable chips/cards, optionally with previews), not free-text ping-pong. One tap resolves it and the answer feeds back into the workflow. Free text is the fallback, not the default.
4. **Local-first governance.** Raw bulk data never leaves the box. Only schema, profiles, small samples, and small result sets cross the LLM boundary; SQL executes locally in DuckDB.
5. **The semantic layer is the product's spine.** Accuracy and trust both flow from a curated, per-workspace semantic catalog that improves over time.
6. **Validate inferences, don't assert them.** Discovered relationships and normalizations are *tested candidates*, not silent facts — because a wrong join silently corrupts every downstream answer.

---

## 5. Competitive landscape (verified, last ~6 months)

| Product | Self-host / single-image | Auto-profiling | Undeclared PK/FK discovery | Semantic layer | Confidence-gated clarify | Reveal/edit lineage+SQL | Governance (data stays local) |
|---|---|---|---|---|---|---|---|
| **analyst (vision)** | ✅ single Docker | ✅ agentic | ✅ + test-validated | ✅ auto, curated | ✅ | ✅ editable via chat | ✅ bulk never leaves |
| **WrenAI** (OSS, Apache 2.0) | ✅ Docker | ⚠️ roadmap | ❌ manual | ✅ MDL (manual) | partial | ✅ shows SQL | ✅ |
| **Databricks Genie / Genie Ontology** | ❌ cloud | ✅ | ✅ (Ontology, Preview Jun 2026) | ✅ auto | partial | ✅ SQL, thinking traces citing defs, lineage w/ cert icons, Inspect self-verify | ❌ warehouse |
| **Snowflake Cortex Analyst / Semantic View Autopilot** | ❌ cloud | ✅ | ✅ Relationships Agent (GA Feb 2026) | ✅ auto (~20% gain) | partial | ⚠️ | ❌ warehouse |
| **MotherDuck Flights/Dives** | ❌ cloud (DuckDB-native) | ✅ agentic ingest via MCP (Jun 2026) | ⚠️ | ⚠️ | ❌ | ⚠️ | ❌ cloud |
| **Definite** | ✅ on-prem/BYOC, DuckDB | ⚠️ | ⚠️ | ⚠️ | ❌ | ⚠️ | ✅ |
| Vanna / Dataherald / Defog / PandasAI | mixed (libs) | ❌ | ❌ | RAG examples | ❌ | ⚠️ | varies |

**What to borrow (patterns that demonstrably work):**
- **Genie's trust surface:** view SQL behind every widget; agent "thinking traces" that *cite the semantic definitions applied*; lineage with certification/deprecation icons; **Genie Inspect** — the agent reviews its own SQL and writes smaller *verification* SQL statements (checking filters, date ranges, joins, aggregations). This maps directly onto analyst's assumptions+lineage+SQL trail and should inform our answer-verification step.
- **Closed-world grounding (Intuit Executable Schema Contracts):** constrain all LLM schema references to an attested field catalog; compute **FieldValidity** (fraction of referenced fields that actually exist); flag/repair before executing. Prevents hallucinated column/table references.
- **Two-stage reliability gating (Intuit QA agent):** a pre-retrieval schema-coverage gate routes out-of-domain questions to **abstention**; a post-retrieval grounding filter checks the answer is supported. This is the mechanism behind "confidence-gated."
- **Ground-truth-free hallucination detection (SQLHD):** structure-aware + logic-aware metamorphic checks catch the three documented failure classes without needing a gold query — a candidate for our automated SQL self-check.

---

## 6. Scope

### In scope (product vision)
- Ingest Excel & CSV files; connect relational databases (federated).
- Agentic profiling: types, nullability, cardinality, value distributions.
- Discovery + **test-validation** of undeclared PK/FK relationships.
- Normalization-need detection (case standardization and similar) with proposed rules.
- Persistent, curated **semantic catalog** per workspace (relationships, metrics, plain-English descriptions, synonyms).
- Confidence-gated NL Q&A with expandable assumptions/lineage/SQL trail, ambiguity resolved via the structured **AskQuestion** primitive.
- Charts and data exports.
- **Interactive dashboards** (Tableau-like): agent-authored from a request, then interactively **filterable and re-visualizable** — filters, cross-filtering, chart-type changes, drill-down — built and refined through the agentic AskQuestion workflow.
- Workspaces, permissions, Google + Microsoft OAuth.

### Explicitly out of scope (v1)
- Multi-tenant SaaS; real-time/streaming ingestion; non-tabular (image/audio) data; write-back to source systems; a full BI report-builder rivaling Tableau/PowerBI.

### MVP (first slice — confirmed)
Single-file Excel/CSV ingestion → agentic profiling → Parquet/DuckDB catalog → **confidence-gated NL Q&A over that one dataset**, with the reveal-on-demand trust trail. RDBMS federation, cross-dataset FK-joins, and dashboards are subsequent features.

---

## 7. Key product decisions (locked)

| # | Decision | Choice |
|---|---|---|
| 1 | Primary users & setting | Mixed (business + technical); self-hosted team server, single Docker image |
| 2 | Primary surface & unit of work | Workspace/catalog-first; permissioned workspaces; Google+MS OAuth; first-user→admin; embedded persistence |
| 3 | Answer & trust loop | Confidence-gated (answer when confident, clarify when ambiguous); every answer carries expandable assumptions/lineage/SQL |
| 4 | Data governance | Only schema/profiles/samples/small result sets leave the box; SQL runs locally; **no raw bulk data leaves** (hard invariant) |
| 5 | Cataloguing model | Autopilot by default; reveal + steer-via-chat + review-before-apply on demand; persistent curated semantic layer |
| 6 | Relational DBs | **Federate / query-through** (DuckDB attaches source), nothing copied |

---

## 8. Functional requirements

### 8.1 Ingestion & agentic cataloguing (the differentiator)
- **FR-1** On adding a source (file or DB), the system auto-profiles every column: inferred type, null rate, cardinality, distinct/sample values, min/max/quantiles, value-distribution summary.
- **FR-2** The agent proposes **candidate PK/FK relationships** across tables/files, including undeclared ones. Each candidate is **validated by executable tests** (uniqueness for PKs; value-overlap / referential-integrity checks for FKs) and carries a confidence score and the evidence behind it.
- **FR-3** **Hybrid discovery pipeline** (resolving the LLM-vs-statistics debate in the literature — DBAutoDoc found LLM FKs at 89% precision vs 20% for statistics-only, while Intuit delegates to statistics because "LLMs reason poorly about cardinality"): deterministic statistics compute cardinality/uniqueness/value-overlap to *propose and gate* candidates; the LLM reasons about *semantic* plausibility of joins; **every surviving candidate is test-validated against the data** before it can affect answers. The LLM-vs-stats leadership split is an **open question to settle empirically** (see §12).
- **FR-4** The agent detects normalization needs (e.g. case standardization upper/lower/proper, whitespace, obvious enum variants) and proposes rules — applied only when confirmed or when autopilot policy permits, always reversibly and with lineage.
- **FR-5** The agent writes plain-English table/column descriptions and assembles them, with relationships/metrics/synonyms, into the **per-workspace semantic catalog**.
- **FR-6** All of the above happens automatically (autopilot). Nothing blocks the user from asking questions immediately.

### 8.2 Grab-the-wheel curation
- **FR-7** Any catalog entry (profile, relationship, normalization rule, description, metric, synonym) is **revealable** in the UI.
- **FR-8** The user can **suggest changes in the chat** ("no, `cust_region` is the region, not `zip`"); the agent proposes a concrete diff to the catalog entry; the user **reviews and approves before it applies**.
- **FR-9** Curation is durable and workspace-shared: confirmed knowledge persists and improves future answers (e.g. "revenue" → `rev_amt`).

### 8.3 Query & answering
- **FR-10** User asks in natural language. The agent plans against the semantic catalog (not raw schema), generates SQL, executes it **locally in DuckDB**, and returns a plain-English answer + table/chart.
- **FR-11** **Confidence gating via structured AskQuestion:** when ambiguity is high (multiple candidate columns/metrics, unclear time grain, out-of-domain), the agent emits a **structured AskQuestion** (a question + a few concrete options, rendered as native React UI per FR-11a) instead of guessing; when confident, it answers directly. Genuinely out-of-scope questions **abstain** rather than fabricate.
- **FR-11a** **AskQuestion primitive (cross-cutting).** A single structured-clarification mechanism serves the *entire* product — ingestion ("Is `dob` a date? Is `cust_id` the primary key?"), querying ("Which revenue: `rev_gross` or `rev_net`?"), and dashboard-building ("Filter by region or by segment?"). Contract: the agent returns a question, 2–N labelled options (each with an optional description/preview), and single- or multi-select; the React app renders it inline as selectable cards/chips; the selection feeds back into the agent workflow. Free-text answers are always allowed as an escape hatch. This is how "grab the wheel" and "confidence-gated" are made concrete and fast.
- **FR-12** **Every answer carries an expandable trust trail:** assumptions made (columns/metrics/filters chosen, rows excluded and why), data lineage (which sources/columns), and the exact generated SQL. Business users never see it unless they expand; technical users can drill all the way down.
- **FR-13** **Answer self-verification** (borrowing Genie Inspect / SQLHD): before presenting, the agent runs lightweight checks on its own SQL — closed-world field validity (all referenced fields exist), and structure/logic sanity checks on joins, filters, date ranges, aggregations. Failures trigger repair or a lowered-confidence disclosure.

### 8.4 Workspaces, auth & permissions
- **FR-14** Auth via Google and Microsoft OAuth.
- **FR-15** First user to sign in becomes **admin**. Admin creates workspaces and adds/permissions other users. Non-admins access only workspaces they're added to.
- **FR-16** Data sources, catalogs, and conversations are scoped to a workspace.

### 8.5 Visualization, interactive dashboards & exports (later horizon)
- **FR-17** Export result sets (CSV/Parquet/Excel).
- **FR-18** Save any answer as a visualization (chart type inferred, overridable).
- **FR-19** **Interactive dashboards (Tableau-like), agent-authored.** The user describes a dashboard in natural language ("sales by region over time, with a filter by product line"); the agent assembles a multi-widget dashboard — autopilot. It is then **fully interactive**: filters and slicers, cross-filtering between widgets, chart-type switching, drill-down/roll-up, and date-range controls, all rendered in the React app.
- **FR-20** **Dashboard construction and refinement run through the agentic AskQuestion workflow** (FR-11a): when the agent must choose a dimension, grain, filter, or chart and it's ambiguous, it asks a structured question rather than guessing. The user can also refine any widget by asking in chat ("make this a stacked bar, filter to 2026") — grab the wheel.
- **FR-21** Every dashboard widget retains the same trust trail as an answer (assumptions/lineage/SQL, expandable), and dashboards are workspace-shareable. Widget queries execute locally in DuckDB; interactive filters push down as parameterized queries (bulk data stays local).

---

## 9. Architecture (summary; see CHARTER §2 for engineering detail)

- **Backend:** Python (latest, uv-managed), FastAPI. Thin orchestration layer.
- **Analytical engine:** DuckDB + Parquet. Files materialized to Parquet; **relational DBs attached and queried through (federated), nothing copied.**
- **Agentic layer:** Claude Agent SDK, prompt-driven. Owns profiling, PK/FK discovery, normalization detection, cataloguing, query planning, answer generation, and self-verification. **Suggested model tiering** (to validate): a Haiku-class model for cheap routing/confidence-triage, a Sonnet-class model for profiling/description/SQL-generation/answer-phrasing, an Opus-class model for hard semantic FK reasoning and ambiguous query planning. Prompts and expected structured outputs are versioned artifacts.
- **Persistence:** embedded, single-image (no separate DB container). **Open design point:** app/transactional state (users, workspaces, permissions, catalog metadata, conversations) wants a transactional store — SQLite is the natural embedded fit; DuckDB is OLAP and weaker for concurrent transactional writes. Recommendation: **SQLite for app state, DuckDB/Parquet for analytical data**, both file-backed inside the image/volume. To be confirmed at architecture planning (CHARTER autonomy: this is a reversible v1 call).
- **Governance boundary (hard invariant):** only schema + profiles + small samples + small result sets cross to the Claude API. Raw bulk tables never leave; all bulk computation is local DuckDB.
- **Frontend:** React + TypeScript, Tailwind, shadcn/ui, zustand, Swiss International Design System.
- **Packaging:** single self-contained Docker image.

---

## 10. Non-functional requirements

- **Governance/privacy (P0):** enforce and make *auditable* that no raw bulk data leaves the box. Log exactly what payloads go to the LLM.
- **Security:** OAuth only; per-workspace isolation; secrets (DB creds, API keys) encrypted at rest.
- **Accuracy targets:** treat the semantic catalog as the primary accuracy lever. Establish an internal eval harness early (representative messy Excel/CSV + RDBMS) and track answer accuracy and clarification precision. Do **not** trust benchmark numbers from clean datasets — the 6–21% real-world cliff is the thing to beat.
- **Performance:** DuckDB sweet spot is MB–low-GB local analytics; federated queries push down to the source. Profiling must stay responsive on typical uploads.
- **Scale (v1):** spreadsheets/CSVs in MB–low-GB; federated DBs of arbitrary size (we don't copy them).

---

## 11. Risks & mitigations

| Risk | Evidence | Mitigation |
|---|---|---|
| **Enterprise accuracy cliff** (85–90% → 6–21% on real data) | arxiv/visrow 2026 | Semantic-catalog-first planning; confidence gating + abstention; answer self-verification; internal eval on messy data. |
| **Join / schema hallucination** | SQLHD failure taxonomy; Intuit | Closed-world field validity; **test-validated** FKs before use; structure/logic SQL checks. Note: closed-world grounding stops hallucinated *fields* but **not spurious joins among valid fields** — hence mandatory join test-validation. |
| **FK discovery doesn't transfer to messy denormalized Excel/CSV** | benchmarks are clean (MusicBrainz/AdventureWorks) | Empirical eval on representative uploads before committing the discovery approach; always test-validate; keep human-in-loop reveal. |
| **Fast-moving competitors** (Genie Ontology, Flights, Autopilot all <6mo old) | 2026 release cadence | Compete on the *self-hosted, governance-first, integrated* bundle they structurally can't match; re-scan before major positioning. |
| **LLM-vs-statistics FK leadership unresolved** | DBAutoDoc vs Intuit disagree | Ship the hybrid+test-validate pipeline; make the split a tunable, measure it. |
| **Cloud-LLM dependency vs "self-hosted" expectation** | governance-conscious buyers | Be explicit that metadata/samples reach Claude; log it; keep the door open to local/on-prem model backends later. |

---

## 12. Open questions (to resolve in design/architecture)

1. **PK/FK discovery: LLM-led vs statistics-led?** Literature disagrees. Settle empirically on representative Excel/CSV + RDBMS workloads.
2. **Accuracy transfer:** how well do auto-cataloguing/FK figures from clean benchmarks hold on messy real uploads?
3. **Clarifying-question UX:** best practice and user acceptance for *asking a clarifying question* (vs silent abstention) is under-studied — needs its own design + testing.
4. **Embedded store:** SQLite (app state) + DuckDB (analytics) split vs DuckDB-only — confirm at architecture planning.
5. **Model tiering & cost:** which Claude tier for which agentic step; cost/latency envelope per ingestion and per query.

---

## 13. Phasing (maps to `.engineer/roadmap.md`)

- **Now:** (1) File ingestion & agentic profiling → catalog; (2) Confidence-gated NL Q&A over a dataset with trust trail. The **AskQuestion primitive (FR-11a)** is delivered here — it's the mechanism confidence-gating rides on — and is then reused everywhere. *(MVP = these two, single-dataset.)*
- **Next:** Relational DB federation; PK/FK discovery & validation across sources; normalization detection.
- **Later:** Cross-dataset joins via discovered FKs; charts & exports; **interactive dashboards (Tableau-like, agent-authored, filter/visualize)**; React frontend app shell (Swiss design).

---

## 14. Success metrics (v1)

- **Trust:** % of answers where a user expands the trust trail; correction rate trending down as the catalog matures.
- **Accuracy:** internal-eval answer accuracy on messy representative data (target: beat the raw-text-to-SQL floor by a wide margin via the semantic layer); clarification precision (clarify only when it would otherwise be wrong).
- **Autopilot health:** % of sources catalogued with zero human edits that still yield correct answers.
- **Adoption:** active workspaces; questions per user; time-to-first-answer after upload.

---

## 15. Appendix — key sources

Verified via adversarial multi-vote (22/25 claims confirmed; 3 refuted and excluded). Selected:
- WrenAI (open semantic layer, self-hosted) — github.com/Canner/WrenAI
- Semantic-layer accuracy benchmark (+17–23 pts) — arxiv 2604.25149
- DBAutoDoc (auto-doc, LLM FK 89% vs stats 20%) — arxiv 2603.23050
- LLM-FK (4-agent FK discovery, 93% F1) — arxiv 2603.07278
- Intuit Executable Schema Contracts (statistics-led FK, closed-world grounding, confidence gating) — arxiv 2606.05415
- SQLHD (ground-truth-free hallucination detection; failure taxonomy) — arxiv 2512.22250
- Databricks Genie / Genie Ontology / Inspect (trust UX) — docs.databricks.com/.../release-notes/2026
- Snowflake agentic semantic model + Semantic View Autopilot — snowflake.com/en/blog/engineering/agentic-semantic-model-text-to-sql
- MotherDuck Flights (agentic ingestion, Jun 2026) — siliconangle.com 2026-06-10
- Enterprise accuracy cliff (6–21%) — medium/visrow 2026

**Caveat:** several headline numbers come from 2026 arXiv preprints (self-benchmarked, sometimes vendor-adjacent) and vendor blogs (self-asserted). Treat as directional. This space moves monthly — re-scan before major positioning decisions.
