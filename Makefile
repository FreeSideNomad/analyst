# analyst — root Makefile (repo root: Python at ., frontend in ./frontend)
# One entry point for the whole app. Backend uses uv, frontend uses bun.
.DEFAULT_GOAL := help
UV  ?= uv
BUN ?= bun

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

## ── setup ──────────────────────────────────────────────────────────
install: install-api install-web ## Install backend + frontend deps

install-api: ## Install backend deps (uv)
	$(UV) sync

install-web: ## Install frontend deps (bun)
	cd frontend && $(BUN) install

## ── run ────────────────────────────────────────────────────────────
dev: ## Run API (:8000) + web (:5173) together
	@$(MAKE) -j2 api web

api: ## Backend API on :8000 (real DuckDB store — the default)
	$(UV) run uvicorn analyst.api.app:app --reload --port 8000

api-mock: ## Backend serving the in-memory Python fixtures (demos / e2e)
	ANALYST_FIXTURES=1 $(UV) run uvicorn analyst.api.app:app --reload --port 8000

web: ## Frontend dev server on :5173 (proxies /api → :8000)
	cd frontend && $(BUN) run dev

## ── build / check ──────────────────────────────────────────────────
build: ## Production build of the frontend → frontend/dist
	cd frontend && $(BUN) run build

test: ## Backend unit tests
	$(UV) run pytest tests/unit

lint: ## Backend ruff + mypy
	$(UV) run ruff check . && $(UV) run mypy src/analyst

typecheck-web: ## Frontend tsc (no emit)
	cd frontend && $(BUN) run typecheck

check: lint test typecheck-web ## Run all checks

## ── housekeeping ───────────────────────────────────────────────────
clean: ## Remove build artifacts, deps and local data
	cd frontend && rm -rf node_modules dist
	rm -rf .analyst-data

.PHONY: help install install-api install-web dev api api-real web build test lint typecheck-web check clean
