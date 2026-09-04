# Trust, Data Flow, and Deployment Boundaries

This document describes the behavior of the Agent-Me reference implementation as shipped. A fork
or deployment can change these boundaries, so operators must review their configuration and code.

## What “multi-agent” means here

Agent-Me implements a **role-based multi-agent workflow**. Planner, Researcher, Critic, Writer, and
Verifier are local Python objects with explicit input/output contracts. The orchestrator invokes
them sequentially in one process.

They are not autonomous processes, independently deployed workers, a distributed swarm, or a
general-purpose agent runtime. The safe trace contains role names, outcomes, summaries, and metrics;
it is an operational record, not hidden chain-of-thought.

## Local modes

With `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` all unset:

- `POST /api/v1/chat` uses deterministic local retrieval and returns a matching excerpt;
- `POST /api/v1/collaborate` runs the four-stage or five-stage workflow locally;
- questions, chat history, retrieved excerpts, and traces are not sent to a model provider; and
- no paid model API is required.

The service reads reviewed Markdown beneath `KNOWLEDGE_DIR`. It rejects symbolic links and bounds
each file, the Markdown document count, and aggregate corpus bytes before parsing document bodies.
Returned content is rendered as text. Local processing does not make the knowledge safe to publish;
the operator still controls and must review that content.

## Provider mode

Provider mode is enabled only when all three provider settings are present. For
`POST /api/v1/chat`, Agent-Me sends the question, recent chat history, and retrieved context to the
configured OpenAI-compatible `/chat/completions` endpoint. The API key is sent to that provider as
an authorization credential.

Provider mode is not used by `POST /api/v1/collaborate` in the current implementation. Before
enabling a provider, review its identity, transport security, retention, training, regional, and
data-processing terms. Provider behavior is outside this repository's control.

## Persistence and telemetry

The reference implementation has no database and does not persist questions, answers, sources, or
traces. The React client keeps the active interaction in page memory and stores only the selected
locale in browser local storage. A user can explicitly download a sanitized collaboration response;
that export excludes the original question, profile, provider settings, and hidden browser state.
It still contains the answer, evidence excerpts, paths, and trace, so users must review it before
sharing.

The application includes no analytics SDK, product telemetry, or remote error reporting. Hosting
platforms, reverse proxies, model providers, browsers, and operator-added monitoring may still
produce logs or retain data. Operators are responsible for documenting and controlling those
systems.

## What the verifier verifies

The optional Verifier checks mechanical invariants after writing:

- every expected evidence path appears in the answer citations;
- the reported citation count equals the number of unique evidence paths; and
- the answer is non-empty.

On failure it replaces the candidate answer with a server-controlled fallback. It does **not**
verify factual truth, semantic entailment, source quality, freshness, completeness, or absence of
contradictions. The `grounded` field means the implemented retrieval and policy checks passed; it is
not a factual-correctness guarantee.

## Trust boundaries

1. Browser requests and prompts are untrusted input and are validated and size-limited.
2. Knowledge files are operator-controlled input constrained to the configured root.
3. Retrieved excerpts can contain untrusted text and are returned as text, not raw HTML.
4. Provider output is untrusted and is parsed, size-limited, and rendered as text.
5. Environment variables are the secret boundary; `.env` must never be committed.
6. Safe traces are designed for inspection but can still reveal filenames, counts, and operational
   details that an operator may consider sensitive.

## Production deployment limitations

The Compose stack is a reproducible local evaluation environment, not a hosted enterprise platform.
Before production use, a deployment needs workload-specific controls such as:

- authentication, authorization, tenant isolation, and abuse prevention;
- TLS ingress, network policy, rate limiting, and secret management;
- durable state only where required, with retention and deletion policies;
- queueing, idempotency, retries, timeouts, cancellation, and backpressure for distributed work;
- structured observability with prompt/body redaction and access controls;
- knowledge provenance, update review, backups, and incident response; and
- security, privacy, reliability, and evaluation evidence for the actual workload.

See [Deployment](DEPLOYMENT.md), [Architecture](ARCHITECTURE.md), and the private vulnerability
reporting process in [SECURITY.md](../SECURITY.md).
