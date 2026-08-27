.PHONY: setup dev test lint build

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
	cd frontend && npm run lint && npm run typecheck

build:
	docker compose build
