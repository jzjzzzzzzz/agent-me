.PHONY: setup dev test lint format docs evaluate build

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
