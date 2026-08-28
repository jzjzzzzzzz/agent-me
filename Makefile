.PHONY: setup dev test lint format docs build

setup:
	cp -n .env.example .env || true
	python3 -m venv .venv
	.venv/bin/pip install -e 'backend[dev]'
	cd frontend && npm ci

dev:
	docker compose up --build

test:
	.venv/bin/pytest backend/tests
	cd frontend && npm test

lint:
	.venv/bin/ruff check backend
	.venv/bin/ruff format --check backend
	cd frontend && npm run lint && npm run typecheck

format:
	.venv/bin/ruff format backend

docs:
	python3 scripts/check_docs.py

build:
	docker compose build
