# API reference

## `GET /health`

Liveness check. Returns `{ "status": "healthy" }`.

## `GET /ready`

Readiness and public document count. It returns HTTP `503` with `status: "not_ready"` when no Markdown documents are loaded. It never exposes filenames or content.

## `GET /api/v1/profile`

Returns the configured public agent name, description, and `max_question_chars` so the browser can
enforce the same input limit. The safe boolean `external_provider_enabled` lets the browser disclose
the question's data destination before submission. It never reveals the provider URL, model ID, or
credentials.

## `POST /api/v1/chat`

Request fields:

- `question`: required nonblank string, capped by `MAX_QUESTION_CHARS`.
- `history`: optional array of up to 20 `{role, content}` items. Roles are `user` or `assistant`; total content is capped by `MAX_HISTORY_CHARS`.

Unknown fields, invalid roles, blank content, and oversized fields are rejected. Unsafe symbolic links, unreadable Markdown, or documents larger than `MAX_DOCUMENT_BYTES` make readiness and chat return a safe `503` without exposing a private path. The response includes `answer`, `mode`, and grounding `sources`.

The application rejects HTTP request bodies larger than `MAX_REQUEST_BODY_BYTES` with `413`, before JSON parsing. This applies both when `Content-Length` is present and when a body is streamed without it.

## `POST /api/v1/collaborate`

Runs the local planner → researcher → critic → writer role-based workflow. The request is a strict
object containing a required nonblank `question`, capped by `MAX_QUESTION_CHARS`, and an optional
`workflow` policy:

```json
{
  "question": "How does the example agent plan a project?",
  "workflow": "baseline"
}
```

`workflow` is either `baseline` (the default four-stage contract) or `verified` (the same four
stages followed by a mechanical verifier). Unknown values and fields are rejected with `422`.

The response contains a server-generated run ID, the fixed workflow and mode identifiers, a grounded decision, sources, and four ordered operational trace stages:

```json
{
  "run_id": "run_0123456789abcdef0123456789abcdef",
  "workflow": "planner-researcher-critic-writer",
  "mode": "multi-agent-local",
  "answer": "For project planning...\n\nSources: [example-profile.md]",
  "grounded": true,
  "sources": [],
  "trace": [
    {
      "sequence": 1,
      "agent": "planner",
      "outcome": "completed",
      "summary": "Created an evidence-first execution plan.",
      "metrics": {
        "task_count": 3,
        "query_term_count": 9
      }
    }
  ]
}
```

The actual response always contains planner, researcher, critic, and writer stages in that order. The shortened example shows only the first stage. Trace summaries describe workflow operations and counts; they are not hidden model reasoning. This endpoint is deterministic, local, and does not use `LLM_BASE_URL`.

For the verified policy, submit:

```json
{
  "question": "How does the example agent plan a project?",
  "workflow": "verified"
}
```

Its response uses `workflow: "planner-researcher-critic-writer-verifier"` and appends a fifth
`verifier` stage. The verifier independently checks that the writer-reported citation count matches
the unique evidence paths and that every expected path occurs in the answer. If an invariant fails,
the stage is `blocked`, the candidate answer is discarded, `grounded` becomes `false`, and the API
returns a fixed safe verification-failure message. This is output-contract verification, not a
semantic proof that every natural-language claim is true.

When retrieval finds no evidence, `grounded` is `false`, the critic outcome is `blocked`, and the
writer returns the fixed insufficient-evidence message with zero citations. In verified mode, the
verifier records that this safe fallback satisfies the zero-citation invariant.

## Request-size errors

Size-limit failures use HTTP `413` and the existing flat error shape:

```json
{
  "detail": "question exceeds configured limit",
  "code": "question_too_large"
}
```

Clients should branch on `code`, not on the human-readable `detail` text:

| Limit | Affected endpoints | Code |
| --- | --- | --- |
| Raw HTTP body exceeds `MAX_REQUEST_BODY_BYTES` | All endpoints | `request_body_too_large` |
| Normalized question exceeds `MAX_QUESTION_CHARS` | `/api/v1/chat`, `/api/v1/collaborate` | `question_too_large` |
| Aggregate history content exceeds `MAX_HISTORY_CHARS` | `/api/v1/chat` | `history_too_large` |

Malformed request schemas, unknown fields, invalid roles, and blank strings continue to use FastAPI's standard HTTP `422` validation response rather than these size-limit codes.


## Provider failures

Partial provider configuration makes `/ready` return `503` instead of silently changing answer mode. Provider timeouts, rejected requests, rate limits, invalid JSON, invalid completion shapes, and oversized answers return classified `502`/`503` errors. Upstream bodies, URLs, and credentials are never copied into client errors.
