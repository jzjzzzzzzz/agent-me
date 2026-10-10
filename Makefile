.PHONY: setup dev test lint format docs evaluate evaluate-memory evaluate-learning evaluate-identity evaluate-retrieval evaluate-agency evaluate-owner-control evaluate-longitudinal knowledge-check build lock lock-check version-check

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

lint: lock-check version-check
	.venv/bin/ruff check backend scripts
	.venv/bin/ruff format --check backend scripts
	cd frontend && npm run lint && npm run typecheck

format:
	.venv/bin/ruff format backend

docs:
	python3 scripts/check_docs.py

version-check:
	python3 scripts/check_versions.py

evaluate:
	.venv/bin/python scripts/evaluate_collaboration.py
	.venv/bin/python scripts/evaluate_memory.py
	.venv/bin/python scripts/evaluate_learning.py
	.venv/bin/python scripts/evaluate_identity.py
	.venv/bin/python scripts/evaluate_retrieval.py
	.venv/bin/python scripts/evaluate_agency.py
	.venv/bin/python scripts/evaluate_owner_control.py
	.venv/bin/python scripts/evaluate_longitudinal.py

evaluate-memory:
	.venv/bin/python scripts/evaluate_memory.py

evaluate-learning:
	.venv/bin/python scripts/evaluate_learning.py

evaluate-identity:
	.venv/bin/python scripts/evaluate_identity.py

evaluate-retrieval:
	.venv/bin/python scripts/evaluate_retrieval.py

evaluate-agency:
	.venv/bin/python scripts/evaluate_agency.py

evaluate-owner-control:
	.venv/bin/python scripts/evaluate_owner_control.py

evaluate-longitudinal:
	.venv/bin/python scripts/evaluate_longitudinal.py

knowledge-check:
	.venv/bin/python scripts/check_knowledge.py

build:
	docker compose build
