<!-- DAE-ROADMAP -->
# Roadmap

> DAE-managed strategic feature list. Edit items freely; DAE reads and writes this block.

## now
- [x] **File ingestion & agentic data profiling** `id:file-ingestion-agentic-data-profiling` priority:1 status:shipped area:ingestion → feature:file-ingestion-and-profiling
      CSV/Excel -> profiling (nullability, cardinality, distributions) -> Parquet/DuckDB catalog. Claude Agent SDK drives cataloguing.
- [x] **Natural-language Q&A over a dataset** `id:natural-language-q-a-over-a-dataset` priority:2 status:shipped area:query → feature:nl-qa
      Confidence-gated NL->query with expandable assumptions/lineage/SQL trail. Ambiguity resolved via the structured AskQuestion primitive (native React multiple-choice), which is then reused product-wide.
- [x] **Auth & workspaces** `id:auth-workspaces` priority:3 status:shipped area:platform → feature:auth-workspaces
      Google + Microsoft OAuth; first-user-becomes-admin; admin creates workspaces and permissions users; per-workspace isolation of sources/catalog/conversations. Foundational for real team use (MVP value-loop can be built workspace-light before this lands).

## next
- [x] **Catalog curation — answerable clarifications + meaning corrections** `id:catalog-curation` priority:1 status:shipped area:profiling → feature:catalog-curation
      Completes the charter promise of a human-curatable semantic catalog: clarifications become answerable (options + free-form + agent re-synthesis), descriptions get suggest-a-correction; human answers sticky/authoritative; v1 blast radius = column + own table. Sequenced ahead of dashboards (015 stays at AC-review).
- [x] **Relational database federation** `id:relational-database-ingestion` priority:1 status:shipped area:ingestion → feature:db-federation
      Attach relational DBs and query through (federated, DuckDB attaches Postgres/MySQL/etc.) — nothing copied. Profile via the live connection.
- [x] **PK/FK relationship discovery & validation** `id:pk-fk-relationship-discovery-validation` priority:2 status:shipped area:profiling → feature:semantic-depth
      Discover candidate PK/FK relationships not formally declared; validate via tests.
- [x] **Data normalization detection** `id:data-normalization-detection` priority:3 status:shipped area:profiling → feature:data-normalization-detection
      Detect normalization needs (case standardization upper/lower/proper, etc.) and propose rules.

## later
- [x] **Cross-dataset joins via discovered FKs** `id:cross-dataset-joins-via-discovered-fks` priority:1 status:shipped area:query → feature:files-x-db-qa
      Answer questions spanning multiple datasets using discovered relationships.
- [x] **Interactive dashboards (agent-authored, filterable)** `id:exports-visualizations-dashboards` priority:2 status:shipped area:output → feature:dashboards
      Tableau-like: agent assembles a multi-widget dashboard from an NL request, then fully interactive (filters, cross-filtering, chart-type switching, drill-down). Built/refined via the agentic AskQuestion workflow. Each widget keeps its trust trail; queries run locally in DuckDB.
- [x] **Charts & data exports** `id:charts-and-exports` priority:3 status:shipped area:output → feature:charts-and-exports
      Save answers as charts (type inferred, overridable); export result sets to CSV/Parquet/Excel.
- [x] **Joins across multiple connected databases** `id:cross-database-joins` priority:4 status:shipped area:query → feature:cross-database-joins
      Residual of cross-dataset-joins (008 shipped file x DB pushdown, 009 file x file): one NL question joining tables from TWO different connected databases. Needs a local-join execution path (both sides remote) + governance-safe row capping.
- [x] **React/Tailwind/shadcn frontend app shell** `id:react-tailwind-shadcn-frontend-app-shell` priority:4 status:shipped area:frontend → feature:data-workbench-ux
      Swiss International Design System UI; zustand state; renders the AskQuestion primitive, trust trail, and interactive dashboards; consumes FastAPI backend.
- [x] **Guided predictive models (Models area MVP)** `id:guided-predictive-models-mvp` priority:5 status:shipped area:models → feature:guided-predictive-models
      Parked feature 012: LLM-guided no-code ML — task definition, feature selection, local linear+LightGBM training, honest eval, predictions as datasets. MVP = single-table regression on Ames. Resume via /engineer.discuss guided-predictive-models.
- [ ] **Relational features, temporal splits & classification** `id:relational-temporal-models` priority:6 status:planned area:models → feature:—
      Models ladder 2: multi-table feature building along validated relationships, out-of-time splits with horizons, binary classification. Makes Home Credit runnable. Depends on feature 012 MVP.
- [ ] **Q&A over predictions (facts x models)** `id:qa-predictions-integration` priority:7 status:planned area:models → feature:—
      Models ladder 3: predict-X questions route into the model flow; questions span facts and predictions; models become catalog citizens.
- [ ] **Automated feature & algorithm discovery (spike first)** `id:ml-discovery-accelerators` priority:8 status:planned area:models → feature:—
      Models ladder 4: DFS-style FK-path window aggregates (generalizing the relgraph baseline) + algo/hyperparameter selection. Research spike before commitment.
- [ ] **Relational graph (GNN) model backend** `id:relational-graph-backend` priority:9 status:planned area:models → feature:—
      Models ladder 5: GNN behind the same task spec, gated on data size + FK integrity; torch as optional image variant; validated against RelBench baselines.
- [ ] **Full sample gallery (join-powered samples)** `id:sample-gallery-full` priority:10 status:planned area:models → feature:—
      Models ladder 6: NYC Rolling Sales + PLUTO, UK Price Paid + EPC, Home Credit via Kaggle token (011 vault). Download-on-demand, license-gated, never baked into the image.

<!-- /DAE-ROADMAP -->
