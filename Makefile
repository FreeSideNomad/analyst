# analyst — build and run the whole app in Docker.
#
#   make build   build the local image (web UI + API in one)
#   make run     start the app (:8000, or ANALYST_PORT in .env) + seeded demo DBs
#
# App config comes from ./.env (see .env.example). Underlying pieces stay
# directly runnable: docker compose (app), scripts/dbs_up.sh (demo DBs),
# `uv run pytest tests/unit`, `uv run ruff/mypy` (also the pre-commit gate).

.DEFAULT_GOAL := help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-8s\033[0m %s\n",$$1,$$2}'

build: ## Build the local Docker image
	docker compose build

run: ## Start the app container + demo databases (Pagila/Northwind/DB2)
	sh scripts/dbs_up.sh
	docker compose up -d
	@echo "analyst → http://localhost:$${ANALYST_PORT:-8000}"

.PHONY: help build run
