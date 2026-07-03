<!-- DAE-ROADMAP -->
# Roadmap

> DAE-managed strategic feature list. Edit items freely; DAE reads and writes this block.

## now
- [x] **File ingestion & agentic data profiling** `id:file-ingestion-agentic-data-profiling` priority:1 status:shipped area:ingestion → feature:file-ingestion-and-profiling
      CSV/Excel -> profiling (nullability, cardinality, distributions) -> Parquet/DuckDB catalog. Claude Agent SDK drives cataloguing.
- [ ] **Natural-language Q&A over a dataset** `id:natural-language-q-a-over-a-dataset` priority:2 status:planned area:query → feature:—
      Confidence-gated NL->query with expandable assumptions/lineage/SQL trail. Ambiguity resolved via the structured AskQuestion primitive (native React multiple-choice), which is then reused product-wide.
- [ ] **Auth & workspaces** `id:auth-workspaces` priority:3 status:planned area:platform → feature:—
      Google + Microsoft OAuth; first-user-becomes-admin; admin creates workspaces and permissions users; per-workspace isolation of sources/catalog/conversations. Foundational for real team use (MVP value-loop can be built workspace-light before this lands).

## next
- [ ] **Relational database federation** `id:relational-database-ingestion` priority:1 status:planned area:ingestion → feature:—
      Attach relational DBs and query through (federated, DuckDB attaches Postgres/MySQL/etc.) — nothing copied. Profile via the live connection.
- [ ] **PK/FK relationship discovery & validation** `id:pk-fk-relationship-discovery-validation` priority:2 status:planned area:profiling → feature:—
      Discover candidate PK/FK relationships not formally declared; validate via tests.
- [ ] **Data normalization detection** `id:data-normalization-detection` priority:3 status:planned area:profiling → feature:—
      Detect normalization needs (case standardization upper/lower/proper, etc.) and propose rules.

## later
- [ ] **Cross-dataset joins via discovered FKs** `id:cross-dataset-joins-via-discovered-fks` priority:1 status:planned area:query → feature:—
      Answer questions spanning multiple datasets using discovered relationships.
- [ ] **Interactive dashboards (agent-authored, filterable)** `id:exports-visualizations-dashboards` priority:2 status:planned area:output → feature:—
      Tableau-like: agent assembles a multi-widget dashboard from an NL request, then fully interactive (filters, cross-filtering, chart-type switching, drill-down). Built/refined via the agentic AskQuestion workflow. Each widget keeps its trust trail; queries run locally in DuckDB.
- [ ] **Charts & data exports** `id:charts-and-exports` priority:3 status:planned area:output → feature:—
      Save answers as charts (type inferred, overridable); export result sets to CSV/Parquet/Excel.
- [ ] **React/Tailwind/shadcn frontend app shell** `id:react-tailwind-shadcn-frontend-app-shell` priority:4 status:in-progress area:frontend → feature:api-and-frontend
      Swiss International Design System UI; zustand state; renders the AskQuestion primitive, trust trail, and interactive dashboards; consumes FastAPI backend.

<!-- /DAE-ROADMAP -->
