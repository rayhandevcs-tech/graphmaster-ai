.PHONY: help install migrate seed dev test lint format check up down logs reset-db

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Create the backend virtualenv and install dependencies
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev,reports]"
	# Scoring cannot run without the language model, and it is a separate
	# download rather than a package dependency. Without this the server still
	# starts, but every analysis request returns 503.
	cd backend && .venv/bin/python -m spacy download en_core_web_sm

migrate:  ## Apply database migrations
	cd backend && .venv/bin/alembic upgrade head

revision:  ## Autogenerate a migration: make revision m="add thing"
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(m)"

seed:  ## Seed reference data (idempotent)
	cd backend && .venv/bin/python -m app.db.seed.cli

dev:  ## Run the API with auto-reload
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

test:  ## Run the test suite with coverage
	cd backend && .venv/bin/python -m pytest tests -q -p no:warnings --cov=app --cov-report=term-missing

lint:  ## Check formatting and lint rules
	cd backend && .venv/bin/black --check --target-version py311 app tests alembic && .venv/bin/ruff check app tests alembic

format:  ## Apply formatting and auto-fixable lint rules
	cd backend && .venv/bin/black --target-version py311 app tests alembic && .venv/bin/ruff check --fix app tests alembic

check: lint test  ## Lint and test

up:  ## Start the stack with Docker Compose
	docker compose up -d --build

down:  ## Stop the stack
	docker compose down

logs:  ## Tail API logs
	docker compose logs -f api

reset-db:  ## Drop, recreate, migrate and seed the local database
	cd backend && .venv/bin/alembic downgrade base && .venv/bin/alembic upgrade head && .venv/bin/python -m app.db.seed.cli
