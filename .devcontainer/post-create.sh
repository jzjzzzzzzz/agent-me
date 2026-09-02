#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python -m pip install --user --disable-pip-version-check 'uv==0.12.7'
export PATH="$HOME/.local/bin:$PATH"
if [[ ! -f .env ]]; then cp .env.example .env; fi
UV_PROJECT_ENVIRONMENT="$PWD/.venv" uv sync --project backend --locked --extra dev
npm --prefix frontend ci
printf '\nAgent-Me dependencies installed. Run make lint, make test, make docs, and make evaluate.\n'
