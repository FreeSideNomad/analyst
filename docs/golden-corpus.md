# Golden Test Corpus — analyst

> Curated real-world datasets for validating ingestion, profiling, type inference, PK/FK discovery, normalization detection, and NL-Q&A accuracy. Backs **AC-24** (feature 001) and future features. URLs verified live 2026-07-01.
> **Principle:** measure behavior on *messy real data with known ground truth*, not synthetic fixtures — this is our defense against the enterprise accuracy cliff (PRD §2, §11).

## Acquisition pattern (recommended)

- **Vendor** only permissive small files (MIT/BSD/public domain) into the repo.
- **Everything else:** a `download_datasets` script (curl + `kaggle` CLI) + a checksum manifest + separate ground-truth fixtures (declared keys / gold SQL / cleaned counterparts).
- **Kaggle-gated** sources need `kaggle` CLI + `~/.kaggle/kaggle.json`; competition datasets also need rules accepted in the web UI.

---

## 1. Single messy CSV/Excel — profiling & type inference (feature 001)

| Dataset | URL | Format | License | Messiness | Ground truth |
|---|---|---|---|---|---|
| Titanic | `raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv` | CSV 60KB | Public | Nulls (Cabin ~77%), quoted commas, int/float mix | Yes |
| Inside Airbnb listings | `insideairbnb.com/get-the-data/` (current dated `listings.csv.gz`) | CSV ~8MB | CC BY 4.0 | `$1,234.00` currency strings, `95%` percents, t/f booleans, high-card text | Partial dict |
| NYC 311 (subset) | `data.cityofnewyork.us/.../erm2-nwe9` (`rows.csv?...&$limit=50000`) | CSV (Socrata) | NYC OD | Inconsistent date/timestamp formats, case inconsistency | Yes — dict |
| NYC Yellow Taxi 2023-01 | `d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-01.parquet` | Parquet 48MB | Public | Cross-file schema drift, negative fares, impossible timestamps | Yes |
| Foresight BI "Dirty Data" | `foresightbi.com.ng/microsoft-power-bi/dirty-data-samples-to-practice-on/` | 8× .xlsx | ⚠️ no explicit license | Merged cells, subtotal rows, letters-for-numbers | Yes (clean target sheet) |
| Sample Superstore | `github.com/PacktPublishing/Tableau-10-Best-Practices/.../Sample - Superstore Sales (Excel).xls` | .xls (legacy) 3MB | MIT | Legacy .xls path, dates, currency, category hierarchy | Yes |

## 2. Multi-sheet Excel (each sheet = a table)

| Dataset | URL | Sheets | Ground truth |
|---|---|---|---|
| Superstore .xls | (as above) | Orders / Returns / Users — **Returns.OrderID→Orders.OrderID**, Users maps Region→Manager | Yes (best cross-sheet-FK case) |
| ONS ASHE Table 1 | `ons.gov.uk/file?uri=/.../ashetable12024revised.zip` (OGL v3.0) | Notes + 9 identical-schema demographic tabs | Yes — tests skipping the Notes sheet |
| World Bank Global Findex 2025 | `thedocs.worldbank.org/.../GlobalFindexDatabase2025.xlsx` (CC BY 4.0) | Notes, Data (8590×507), Series Table (dict), Updates | Yes — wide-table stress |
| Financial Sample (Power BI) | `go.microsoft.com/fwlink/?LinkID=521962` (MS) | Sheet1 only (701×16) | **Negative/control** — single table |

## 3. Relational with DECLARED PK/FK (relationship validation)

Cleanest core: **Chinook + Sakila + Pagila + AdventureWorks-for-Postgres.**

| DB | URL | Format | License | Keys |
|---|---|---|---|---|
| Chinook | `github.com/lerocha/chinook-database` | SQLite+SQL | MIT | PK+FK, self-ref Employee.ReportsTo — cleanest |
| Sakila | `dev.mysql.com/doc/sakila/en/` | SQL dump | New BSD | PK+FK, junction tables, address→city→country chain |
| Pagila | `github.com/devrimgunduz/pagila` | SQL/.backup | PostgreSQL | PK+FK (Postgres Sakila) |
| AdventureWorks (Postgres port) | `github.com/lorint/AdventureWorks-for-Postgres` | SQL scripts | MIT | PK+FK, 70+ tables, composite keys |
| Employees test_db | `github.com/datacharmer/test_db` | SQL dump 167MB | ⚠️ CC BY-SA 3.0 | PK+FK composite, ~4M rows |
| TPC-H | `github.com/electrum/tpch-dbgen` | generated | ⚠️ spec copyrighted, data free | Keys specified, FKs optional (you write DDL) |

**Gotcha:** `jpwhite3/northwind-SQLite3` declares PKs but **no FK constraints** (FKs only in the ER diagram) — use as PK-only/undeclared-FK case. For declared Northwind FKs use Microsoft `instnwnd.sql`.

## 4. Flat CSV — UNDECLARED but discoverable PK/FK (FK discovery)

| Dataset | URL | Format | License | GT |
|---|---|---|---|---|
| Northwind CSV | `github.com/graphql-compose/graphql-compose-examples/.../northwind/data/csv` | 11 CSV <1MB | MIT | Yes — **best committable case** |
| MovieLens ml-latest-small | `files.grouplens.org/datasets/movielens/ml-latest-small-README.html` | 4 CSV 1MB | Non-commercial | Yes — README |
| Olist E-Commerce | `kaggle.com/datasets/olistbr/brazilian-ecommerce` | 9 CSV 45MB | ⚠️ CC BY-NC-SA, Kaggle auth | Yes — ER diagram |
| IMDb Non-Commercial | `developer.imdb.com/non-commercial-datasets/` | 7 TSV 1-2GB | ⚠️ not redistributable | Yes |
| Instacart | `kaggle.com/c/instacart-market-basket-analysis/data` | 6 CSV 700MB | ⚠️ competition, Kaggle auth | Yes |

**Ground-truth hard cases:** Northwind `orders.ShipVia→shippers.ShipperID` (name mismatch), `employees.ReportsTo→employees` (self-ref), `order_details` composite PK; IMDb `title.akas.titleId→title.basics.tconst` (name mismatch) + comma-separated multi-valued FKs + `\N` nulls; Olist `customer_id` (per-order) vs `customer_unique_id` (true entity); MovieLens/Instacart orphan-dimension (no users table).

## 5. Known-answer semantics (NL-Q&A accuracy)

Best "compute-the-answer" fits (bundle SQLite + executable gold SQL): **Spider 1.0, BIRD (dev), WikiSQL, KaggleDBQA.** Most permissive: WikiSQL (BSD), Spider 2.0 (MIT).

| Dataset | URL | License | Notes |
|---|---|---|---|
| Spider 1.0 | `yale-lily.github.io/spider` | ⚠️ CC BY-SA 4.0 | Gold SQL/Q, 200 SQLite DBs |
| BIRD (dev split) | `bird-bench.github.io` / `huggingface.co/datasets/birdsql/bird_mini_dev` | ⚠️ CC BY-SA 4.0 | Gold SQL + evidence; test held out |
| WikiSQL | `github.com/salesforce/WikiSQL` | BSD-3 | Gold SQL, 24k tables |
| KaggleDBQA | `github.com/Chia-Hsuan-Lee/KaggleDBQA` | verify | Real un-normalized Kaggle data + gold SQL |
| Spider 2.0 | `github.com/xlang-ai/Spider2` | MIT | Some cloud-gated (Snowflake/BigQuery) |

## 6. Normalization exemplars (case / whitespace / synonyms)

| Dataset | URL | License | Inconsistency | Clean GT |
|---|---|---|---|---|
| Messy IMDB | `raw.githubusercontent.com/eyowhite/Messy-dataset/main/messy_IMDB_dataset.csv` | ⚠️ no license | **Best synonym case**: `USA`/`US`/`US.`, `New Zealand`/`New Zesland`, many date formats | Yes — `Cleaned_IMDB_Dataset.csv` |
| Messy HR | `raw.githubusercontent.com/eyowhite/Messy-dataset/main/messy_HR_data.csv` | ⚠️ no license | Whitespace `" grace "`, mixed case, `SIXTY THOUSAND`, `nan` vs empty | Yes |
| Powerhouse Museum | `programminghistorian.org/assets/cleaning-data-with-openrefine/phm-collection.tsv` | CC BY-SA | Case + singular/plural + spelling + `||` separator | No |
| SAFI survey | messy `ndownloader.figshare.com/files/11502815` / clean `.../11492171` | CC BY | Dates, capitalization/whitespace, missing-value inconsistency | Yes |

---

## Feature 001 starter set (single-file ingestion + profiling + type inference)

Small, mostly permissive, no Kaggle auth, covers every type-inference/profiling edge:

1. **Titanic** (MIT-safe) — canonical smoke: nulls, quoting, int/float mix.
2. **Inside Airbnb listings** (CC BY 4.0) — currency/percent-as-string, t/f booleans, high-card text.
3. **Messy IMDB** (+ cleaned) — synonyms, case, every date format; ground-truth clean file.
4. **Messy HR** (+ cleaned) — whitespace, mixed case, numeric-as-words, `nan` vs empty.
5. **Sample Superstore .xls** (MIT) — legacy Excel reader path; dates, currency, categories; also the multi-sheet case.
6. **NYC 311 subset** — real inconsistent dates + case inconsistency at moderate scale.
7. **Foresight BI dirty sample** — Excel structural mess (merged cells, subtotal rows); confirm terms before bundling.

## Licensing quick-reference

- **Safe to vendor (permissive):** Chinook, Sakila, Pagila, Northwind CSV/SQLite, AdventureWorks repo, Superstore .xls, WikiSQL, Spider 2.0, World Bank Findex, ONS ASHE, SAFI, Titanic, Inside Airbnb (attribution).
- **Share-alike (reference, don't vendor):** Spider 1.0, BIRD, Employees test_db, Powerhouse, Messy IMDB source.
- **Non-commercial / not redistributable (fetch at test time):** MovieLens, Olist, IMDb, Instacart.
- **No explicit license (fetch at test time, legal review before shipping):** eyowhite Messy-dataset, Foresight BI dirty samples.
- **Don't ship the copyrighted docs/specs:** TPC-H spec PDF, Sakila docs PDF (the data/schema are fine).
