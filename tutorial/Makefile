# Tutorial runner — everything the UI cannot do, one target each.
# Run from this folder: `cd tutorial && make <target>`.

ROOT := $(abspath ..)
BERKA_PORT := 55433
BERKA_CONNINFO := host=127.0.0.1 port=$(BERKA_PORT) dbname=berka user=postgres password=tutorial

.DEFAULT_GOAL := help

help: ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

app: ## build + start the app (:8000) and the demo databases (Pagila etc.)
	$(MAKE) -C $(ROOT) build run

app-ml: ## build + start the ML-variant app (:8001) + the Berka Postgres
	cd $(ROOT) && docker build --platform linux/amd64 --target ml -t analyst:ml .
	docker compose up -d
	@echo "ML app → http://localhost:8001"

dbs: ## demo databases only (Pagila / Northwind / DB2)
	cd $(ROOT) && sh scripts/dbs_up.sh

berka-db: ## start + seed the Berka Postgres (real PKDD'99 banking data)
	docker compose up -d berka-db
	@until docker exec analyst-tutorial-berka pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done
	cd $(ROOT) && ANALYST_ML_CACHE=$(ROOT)/tests/.ml_cache uv run python scripts/seed_berka_db.py postgres "$(BERKA_CONNINFO)"
	@echo "Berka is seeded. Connect from the ML app with:"
	@echo "  host=berka-db  port=5432  database=berka  user=postgres  password=tutorial"

data: ## generate tutorial data: the cross-database SQLite pair + sample copies
	mkdir -p data
	cd $(ROOT) && uv run python scripts/make_cross_dbs.py $(abspath data)
	cp $(ROOT)/samples/*.csv $(ROOT)/samples/*.xlsx data/ 2>/dev/null || true
	cp $(ROOT)/samples/verify/*.csv data/ 2>/dev/null || true
	cd $(ROOT) && uv run python tutorial/make_linked_pair.py $(abspath data)
	@echo "tutorial/data/ ready:" && ls data

status: ## what is running
	@docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'analyst|NAMES' || true

down: ## stop the tutorial containers (data volumes survive)
	docker compose down
	cd $(ROOT) && docker compose down 2>/dev/null || true

clean: down ## stop everything and remove tutorial volumes + generated data
	docker compose down -v
	rm -rf data

.PHONY: help app app-ml dbs berka-db data status down clean
