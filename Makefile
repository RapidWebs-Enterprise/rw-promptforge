# Makefile — rw-promptforge

.PHONY: help install test test-v lint fmt typecheck check clean dev

help: ## Show targets
	@grep -Eh '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install in dev mode
	uv sync --group dev

build: ## Build installable package
	uv build

test: ## Run tests
	uv run python -m pytest tests/ -q --tb=short

test-v: ## Run tests with verbose output
	uv run python -m pytest tests/ -v --tb=long

lint: ## Ruff lint
	uv run ruff check src/

fmt: ## Ruff format
	uv run ruff format src/

typecheck: ## Mypy strict check
	uv run mypy src/rw_promptforge

check: ## Run full quality gate: lint + typecheck + test
	uv run ruff check src/
	uv run mypy src/rw_promptforge
	uv run python -m pytest tests/ -q --tb=short
	@echo "✅ All checks passed"

clean: ## Remove artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache/ htmlcov/ .coverage coverage.out
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

dev: install test  ## Quick dev cycle