# API reference

## Request correlation

Every HTTP response includes a server-generated `X-Request-ID` header, for example
`req_0123456789abcdef0123456789abcdef`. It is created fresh per request from a
collision-resistant source and is present on successful responses and on responses handled by an
application exception handler (validation, size-limit, provider, and knowledge-base errors). Any
`X-Request-ID` header sent by the client is ignored — it is never read, trusted, or reflected back.
The header contains no user input, prompt content, or knowledge-base data; it exists only to let a
learner correlate one browser request with the corresponding server-side response or log line.

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

Unknown fields, invalid roles, blank content, and oversized fields are rejected. Unsafe symbolic
links, unreadable Markdown, a file larger than `MAX_DOCUMENT_BYTES`, more than
`MAX_KNOWLEDGE_DOCUMENTS` Markdown files, or a corpus larger than `MAX_KNOWLEDGE_BYTES` make
readiness, chat, and collaboration return a safe `503` without exposing private paths or filenames.
The response includes `answer`, `mode`, and grounding `sources`.

Each source has `title`, `path`, `excerpt`, and a finite normalized relevance `score` in the
inclusive range **0..1**. Both `0` and `1` are valid; negative values, values greater than `1`,
NaN, and infinities are rejected. The backend response model and the browser's shared source
validator enforce this range for both chat and collaboration responses. This score measures
retrieval overlap, not answer confidence or factual correctness.

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

## Compare workflows in the browser

**Compare workflows** is a separate action, not a fourth mode. It submits two requests to
`/api/v1/collaborate`, one with `baseline` and one with `verified`, using the same trimmed question
regardless of the selected radio mode. Both policies remain local; this action never uses the
standard Q&A provider path.

Baseline is first in the semantic DOM order and left on desktop; verified is second/right, with an
explicit **Extra stage: Verifier** label. At narrow widths the same articles stack baseline first.
Each side displays its own loading/error state or answer, grounding, sources, run ID, stage
outcomes, and metrics. One failure does not hide the other result. Once both settle, **Retry both
workflows** clears the old results/errors and runs a fresh pair using the captured comparison
question, even if the input has since been edited. **Ask** returns to the selected single workflow.

This is a comparison of public artifacts, not a correctness ranking. A verified response only
adds mechanical citation/metadata checks, not a guarantee of factual truth. Questions and results
remain in memory: comparison does not put them into URLs, analytics, or browser storage. Copy and
JSON export are still explicit user actions on each validated result.

## Local run-record replay

After a collaboration response, **Download sanitized run JSON** exports the response object above,
without a version envelope. **Open run record** accepts these baseline and verified `.json` files
up to **1 MiB (1,048,576 bytes)**. The browser checks the byte limit before reading or parsing, then
uses the same `parseCollaborationResponse` validator as network responses. Unknown workflows,
version envelopes/discriminators, invalid stage order, non-finite numbers, source scores outside
the inclusive **0..1** range, and malformed records are rejected rather than migrated or partially
rendered. Invalid source scores produce the existing safe `replayInvalid` error without exposing
file contents or parser diagnostics.

The imported answer, sources, run ID, stages, and metrics use the same plain-text result view as a
live response, with a visible **Local replay — not a new run** label. A valid shape does not
establish authenticity or correctness: the record is not rerun or re-verified.

Import is local to the current tab's memory: it makes no API request, upload, browser-storage write,
telemetry event, URL change, or automatic export. The normal app startup can still request public
profile metadata and remember the locale; those actions do not receive the imported record. Once
the app has loaded, replay also works when the API is offline (this is not an offline-installable
app). Files and imported text are never evaluated as HTML, Markdown, URLs, or code.

**Review before sharing:** “sanitized” means a restricted response-field set, not anonymization.
The answer and source excerpts can still contain personal information from your knowledge files.
A run ID in an imported file is an untrusted label, not proof of server execution.

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
