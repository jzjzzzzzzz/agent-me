.PHONY: setup dev test lint format docs evaluate build lock lock-check

UV_PROJECT_ENVIRONMENT ?= $(CURDIR)/.venv

setup:
	cp -n .env.example .env || true
	UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" uv sync --project backend --locked --extra dev
	cd frontend && npm ci

lock:
	uv lock --project backend

lock-check:
	uv lock --project backend --check

dev:
	docker compose up --build

test:
	.venv/bin/pytest backend/tests
	cd frontend && npm test

lint: lock-check
	.venv/bin/ruff check backend scripts
	.venv/bin/ruff format --check backend scripts
	cd frontend && npm run lint && npm run typecheck

format:
	.venv/bin/ruff format backend

docs:
	python3 scripts/check_docs.py

evaluate:
	.venv/bin/python scripts/evaluate_collaboration.py

build:
	docker compose build
