# Shared collaboration contract fixtures

`baseline.json` and `verified.json` are canonical, synthetic responses with deterministic
server-shaped run IDs. Both the Python and TypeScript contract tests consume these exact files.
They are test-only data, never runtime fallback answers; do not import them from application code.

The synthetic corpus and question used to verify route serialization live in
[`test_collaboration_contract.py`](../../../../backend/tests/test_collaboration_contract.py).
Update the fixtures deliberately when changing the public contract; do not regenerate them merely
to silence a regression. Invalid cases are derived in tests rather than stored as duplicate payloads.

This directory is inside the existing `frontend/` Docker build context. Native tests, CI, and the
frontend image's TypeScript build need no extra copy scripts or broadened Docker context. Vite does
not bundle test files or these fixtures into the production application.
