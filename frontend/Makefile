.DEFAULT_GOAL := help
BUN ?= bun

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

install: ## Install dependencies
	$(BUN) install

dev: ## Run the Vite dev server (http://localhost:5173)
	$(BUN) run dev

build: ## Production build → dist/
	$(BUN) run build

preview: ## Serve the production build locally
	$(BUN) run preview

typecheck: ## Type-check with tsc (no emit)
	$(BUN) run typecheck

clean: ## Remove node_modules and dist
	rm -rf node_modules dist

.PHONY: help install dev build preview typecheck clean
