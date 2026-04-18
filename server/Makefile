.PHONY: help venv install lint fmt test test-int eval run db.up db.down db.reset migrate migration build up down logs

help: ## Show help
	@awk 'BEGIN{FS":.*?## "}/^[a-zA-Z_.-]+:.*?## /{printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

venv: ## Create local virtualenv
	python -m venv .venv
	.venv/bin/pip install -U pip wheel
	.venv/bin/pip install -r requirements.txt

install: venv ## Install dependencies

lint: ## Ruff + mypy
	ruff check src tests
	mypy src

fmt: ## Ruff format
	ruff format src tests

test: ## Unit tests
	pytest tests/unit -q

test-int: ## Integration tests (testcontainers)
	pytest tests/integration -q

eval: ## Run eval harness (costs tokens)
	python -m tests.eval.run_eval

run: ## Run locally (dev)
	uvicorn live150.main:app --reload --host 0.0.0.0 --port 8000

db.up: ## Start only postgres
	docker compose up -d postgres

db.down: ## Stop postgres
	docker compose stop postgres

db.reset: ## Wipe Postgres volume and recreate
	docker compose down -v
	docker compose up -d postgres

migrate: ## Alembic upgrade head
	docker compose run --rm migrator

migration: ## Create new migration (usage: make migration m="add foo")
	alembic revision --autogenerate -m "$(m)"

build: ## Build images
	docker compose build

up: ## Start full stack
	docker compose up -d

down: ## Stop everything
	docker compose down

logs: ## Tail logs
	docker compose logs -f --tail=200
