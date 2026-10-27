# Local verification for the focused PR

Base: `504eab3e300ed21b60a871182535531989610c97`.
Environment: Windows, Python 3.12.14, uv 0.12.11, Node 24.19.0; fresh locked dependencies.

Commands below ran from the repository root, except npm commands, which ran in `frontend/`.
PowerShell equivalents were used because GNU Make is not installed.

| Check | Result |
| --- | --- |
| `uv sync --project backend --locked --extra dev` and `npm ci` | Passed |
| `uv lock --project backend --check` | Passed |
| `.venv/Scripts/ruff.exe check backend scripts` | Passed |
| `.venv/Scripts/ruff.exe format --check backend scripts` | Passed |
| `.venv/Scripts/python.exe scripts/check_versions.py` | Passed, 2.0.0 |
| `.venv/Scripts/python.exe -m pytest backend/tests -q` | 714 passed, 4 skipped; one existing Windows symlink-privilege failure |
| `npm run lint` and `npm run typecheck` | Passed, including E2E types |
| `npm test -- --maxWorkers=1` | 371 passed |
| `npm run build` | Passed |
| `npm run test:e2e -- request-cancellation.spec.ts` | 6 passed, desktop/mobile |
| `.venv/Scripts/python.exe scripts/check_docs.py` | Passed |
| `.venv/Scripts/python.exe scripts/check_knowledge.py` | Passed |
| `.venv/Scripts/python.exe scripts/evaluate_followup_retrieval.py` | 14 source-recall cases passed, no network/model |
| `docker info` / container build | Docker engine unavailable; build not run |

All existing deterministic evaluation entrypoints also passed: collaboration baseline and verified
(4 cases each), memory (18), learning (24), semantic fixture validation (12; not model performance),
identity (19), retrieval (16), agency (17), owner control (14) and longitudinal metrics (20 observations).
These were run with `.venv/Scripts/python.exe scripts/evaluate_<name>.py`; semantic learning used
`--check-fixture`, and collaboration ran both default and `--workflow verified`.

The backend failure is the unchanged
`backend/tests/test_check_knowledge.py::test_oversized_and_symlinked_files_are_rejected`:
Windows denied `Path.symlink_to` with WinError 1314. Other symlink tests skip when that privilege is
unavailable. No test was changed to hide this environment limitation.

The initial `npm run audit:deps -- --registry=https://registry.npmjs.org` check reported the existing
locked transitive `zod <4.6.6` advisory GHSA-mrhx-c7xc-m3w5. Remote frontend CI confirmed the same
failure. A separate follow-up commit updates only that ESLint development dependency's lock entry
from 4.5.4 to 4.6.7 within its existing range; package manifests and runtime dependencies are unchanged.
The configured npm mirror did not provide an audit endpoint, so the official registry was used.

Saved live measurements were collected in the earlier experiments described in [README](README.md).
No new model calls or training were needed to validate the extracted implementation.
