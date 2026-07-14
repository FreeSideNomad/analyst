# 03 — Sample datasets: verified research, selections, rejections

> Web-verified 2026-07-14. Licenses and access mechanics re-check cheaply;
> the *reasons* below are the durable part.

## Selection criteria (evolved during discussion — order matters)

1. **Real data with real signal.** Synthetic sets teach nothing: there is no
   signal to discover, only the generator's rules. (This criterion killed
   Northwind/Pagila as ML samples.)
2. **Feature richness** — elevated to near-top priority by the product
   owner. A dataset with 8 columns cannot host a conversation about feature
   judgment; one with 80 can.
3. **Meaningful size** for the task (682 labeled loans is a toy).
4. **One-click automated download**, at most a T&C acknowledgment. A
   one-time credential setup (Kaggle API token) is acceptable; a manual
   request to a government office is not.
5. For the relational tiers: **multi-table with genuine FK structure and
   timestamps** (out-of-time splits; join exercises).

## The gallery (accepted)

| Order | Dataset | Access | Why |
|---|---|---|---|
| 1 | **Ames Housing** — 2,930 real sales, Ames Iowa 2006–2010, **80 features** (23 nominal, 23 ordinal, 14 discrete, 20 continuous) | OpenML, fully automated, no account (it is scikit-learn's `fetch_openml("house_prices")`) | The teaching starter. Purpose-built by De Cock as the definitive house-price set. Rich features = real material for guided feature judgment (ordinal quality ratings, missingness decisions). Small = trains in seconds while learning. Strong signal (~90%+ variance explainable). Exactly the owner's "predict house price from features". |
| 2 | **King County house sales** — 21,613 real sales, Seattle area 2014–15, 21 features incl. lat/long | OpenML id 42092, automated, no account | Scale-up a notch; teaches geography-as-feature. |
| 3 | **NYC Rolling Sales ⨝ PLUTO** — trailing-12-months real NYC sales (updated monthly) joined on borough-block-lot to PLUTO's ~90 lot/building attributes (year built, floors, units, areas, zoning, coordinates) | Both direct downloads from NYC.gov | The *recent + rich* option — and rich **only through a join**, which showcases analyst's relationship machinery on real open data. |
| 4 | **Home Credit Default Risk** — 307k real loan applications, real default outcomes, **seven linked tables** (bureau, bureau_balance, previous_application, POS/cash balance, installments, card balance) | Kaggle: account + one-time competition-rules acceptance on their site + API token; then fully scriptable. **Redistribution prohibited → download-on-demand only.** Token stored in the feature-011 encrypted vault. | The flagship relational sample — the canonical multi-table feature-engineering dataset; the shape the relgraph paper cares about. Product-owner picked. |
| 5 | **UK Price Paid ⨝ EPC** — ~30M real transactions since 1995, current to last month (OGL v3.0, direct CSV) joined to ~23M energy certificates (~90 fields: floor area, rooms, construction age band; free registration) | PPD direct; EPC needs a free registered API key | The stretch: biggest AND most recent. The join is genuinely messy real-world linkage (published research reaches ~79%) — an honest advanced exercise. |
| 6 | **RelBench** (v2, Jan 2026: 11 databases, 66 tasks — rel-hm, rel-stack, rel-amazon, MIMIC-IV…) | Automated loader, no credentials | The graph-tier proving ground: real data at GNN-worthy scale with published baselines, so "does the graph model earn its keep" gets an external answer key. |

## Rejected (and why — keep to prevent re-proposal)

- **Berka (PKDD'99)** — the original candidate; rejected by the product
  owner on our *own findings*: anonymization destroyed cross-account payee
  structure (31 shared counterparties of ~8,000), and 682 labeled loans is
  too small for reasonable ML. Remains valid inside relgraph as a research
  benchmark; wrong as a product sample.
- **Northwind / Pagila** — synthetic; nothing to learn from generated data
  (owner's call, correct). They stay as *federation demo* databases only.
- **Connecticut Real Estate Sales 2001–2023** — real, recent, 1.1M rows,
  official one-click Socrata/OData… but ~8 usable features. Falsified by the
  feature-richness criterion. Footnote-only.
- **Canada (any)** — structurally unavailable: transaction-level sales
  belong to MLS boards (litigated); StatCan publishes aggregates only; Nova
  Scotia bulk sales require a manual request to a GIS office; the Kaggle
  "Ontario properties" set is scraped *asking* prices (wrong signal). The
  owner accepted "nothing useful" here.
- **Olist** — real and multi-table but weak signal (relgraph AUROC 0.51–0.63)
  and Kaggle-credentialed; optional at best.
- **KKBox / IEEE-CIS fraud / other Kaggle competition data** — strong data,
  but competition rules prohibit redistribution and require rules acceptance;
  fits "bring your own" documentation later, not the gallery.
- **MovieLens** — permissive for research but non-commercial without
  permission, and recsys is not the MVP's task family. Revisit with the
  graph/recommendation tier if ever.

## The durable insight

**Feature-rich single-file datasets are old teaching sets; recent real data
is thin per file and becomes rich only through joins.** (Ames/King County
vs NYC+PLUTO and PPD+EPC.) Consequence: analyst's existing differentiators —
relationship discovery, validated joins, the semantic catalog — are not
adjacent to the ML feature; they are **load-bearing** for it. Kumo makes the
same argument from the enterprise side.

## Gallery mechanism (design decisions)

- Samples are **downloaded on demand, user-initiated**: gallery entry shows
  source, license, T&C acknowledgment; click → download → **normal ingestion
  pipeline** (profiling, cataloguing, relationship discovery — samples are
  ordinary datasets afterwards).
- **Never baked into the Docker image** (license-safe, image stays slim).
- Credentialed sources (Kaggle) prompt once for the API token; the token is
  a credential → feature-011 vault, encrypted at rest.
