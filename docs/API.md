# API reference

## `GET /health`

Liveness check. Returns `{ "status": "healthy" }`.

## `GET /ready`

Readiness and public document count. It returns HTTP `503` with `status: "not_ready"` when no Markdown documents are loaded. It never exposes filenames or content.

## `GET /api/v1/profile`

Returns the configured public agent name, description, and `max_question_chars` so the browser can enforce the same input limit.

## `POST /api/v1/chat`

Request fields:

- `question`: required nonblank string, capped by `MAX_QUESTION_CHARS`.
- `history`: optional array of up to 20 `{role, content}` items. Roles are `user` or `assistant`; total content is capped by `MAX_HISTORY_CHARS`.

Unknown fields, invalid roles, blank content, and oversized fields are rejected. Unsafe symbolic links, unreadable Markdown, or documents larger than `MAX_DOCUMENT_BYTES` make readiness and chat return a safe `503` without exposing a private path. The response includes `answer`, `mode`, and grounding `sources`.


## Provider failures

Partial provider configuration makes `/ready` return `503` instead of silently changing answer mode. Provider timeouts, rejected requests, rate limits, invalid JSON, invalid completion shapes, and oversized answers return classified `502`/`503` errors. Upstream bodies, URLs, and credentials are never copied into client errors.
