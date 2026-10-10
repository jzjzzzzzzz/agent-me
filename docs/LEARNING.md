# Controlled Agent learning

This pipeline is an independent Python capability, not a frontend feature or an autonomous
background collector. Tracking: [proposal #169](https://github.com/jzjzzzzzzz/agent-me/issues/169).
The remaining full-roadmap work is tracked in the [acceptance ledger](AGENT_IMPLEMENTATION.md).

## Trust boundary

- Register a document, project, conversation, or event source. It starts **unapproved**.
- Explicitly approve its current revision before ingestion. No connector, URL, or file path is
  fetched by the core; the owner submits the content. The CLI reads only the file explicitly named.
- Extraction proposes **pending** records. Identity-defining and sensitive data are never
  automatically confirmed. Approval of a source is not approval of every claim in it.
- Source instructions are data, not tool instructions. This pipeline never executes commands,
  calls a model provider, or grants permissions based on memory content.
- Revocation stops future ingestion **including replay**. It does not delete independently
  owner-confirmed memories; inspect and forget those records separately.

## Extraction contracts

`fields` mode accepts nonempty lines of this form (blank lines, headings, and fence-marker lines
are ignored):

```text
fact identity.name: Alex Example
preference response.style: Lead with the conclusion
 event events.demo.2026-10-09: Completed a fictional demo
 decision decisions.storage: Chose SQLite for this single-owner example
```

Kinds are `fact`, `preference`, `event`, and `decision`. Keys are non-whitespace strings without a
colon, at most 100 characters. Values are literal text, at most 2,000 characters. Multiline prose
belongs in `notes` mode. A malformed field line fails the entire extraction, never silently dropping
that line or truncating a claim. Use distinct dated event keys for repeated episodes until structured
event-time identity is implemented.

`notes` mode quotes whole nonempty Markdown paragraphs under their headings. Documents/projects
propose facts; event/conversation sources propose events. Generated keys use source name, heading,
and paragraph ordinal. These are **literal notes**, not inferred structured biographical claims.
Reordering paragraphs can change generated keys; review the resulting candidates. Entity resolution,
semantic duplicate detection, and model-assisted extraction are not implemented here.

Both modes retain the exact excerpt and its `[start, end)` **Unicode code-point offsets** in the
submitted string (not UTF-8 byte offsets or JavaScript UTF-16 offsets). No separate copy of the submitted document is
persisted; extracted quotations can cover an entire small document. Limits: 80,000 characters, 200,000 UTF-8 bytes, and 100 candidate records per ingestion.
The API also enforces the existing request-body byte limit before parsing.

## Deduplication, conflicts, and review

Exact normalized `(kind, key, content)` digests use Unicode NFC and CRLF normalization, not semantic
similarity. Kind/key conflicts also recognize Unicode-canonically equivalent keys.

- A new claim becomes a pending record with an exact source origin.
- A duplicate pending claim reuses its ID and adds a distinct source origin. A newly attached origin
  creates a `corroborated` revision, invalidating stale review preconditions. Sensitivity never drops.
- A duplicate confirmed claim is reported as `known`. Its content, approval and provenance are
  **not** silently mutated to absorb the new source.
- A conflicting current kind/key is reported in the run. The existing confirmed record is untouched;
  owner confirmation still needs the exact replacement set and can require reviewed revisions.

Run outcomes describe the ingestion **at that time**, not today's memory state. A referenced memory
may later be confirmed, superseded, edited, or deleted. Context always reads current confirmed records,
never a historical run's `created` result. Inspect the record rather than treating a run as live truth.

## Replay, failures, and forgetting

The replay key includes source ID/revision, document hash, mode, and extractor version. A completed
run replays without inserting candidates or origins. Revoked sources cannot replay.

Source/candidate/origin writes are transactional. A storage failure rolls back all candidates in that
batch and records a `failed` run with a generic code, not the private exception text. Retrying the same
input reuses the run ID and increments attempts. Extraction failures are also inspectable. A run with
`status: failed` is an unsuccessful job even though the API successfully returned its HTTP 200 status
record; the CLI exits 1. Permission, stale-source and invalid request errors remain HTTP 403/409/422.

Forgetting a record removes all its snapshots and source excerpts. Digests of its current and past
kind/key/content remain, so neither replay nor a fresh approved-source submission can automatically
recreate it. Traces retain only IDs, counts, document hashes and timestamps. Digests/hashes are still
private metadata, not encrypted or anonymous data. Deliberate manual re-addition is permitted and
creates a pending record; independently restored/archived records and transcript text are separate.
Previous exports and external providers are not retroactively erased. Erasing the entire stopped
workspace also removes the forgetting registry. There is no portable import contract yet.

## Sensitivity and provider boundaries

Sources and memories default to `private`; `public`, `private`, and `sensitive` are explicit labels.
A source's label is a floor for its candidates. A new sensitive duplicate can raise a pending record's
label, but `known` results do not retroactively reclassify an independently confirmed record.

Sensitive structured records are excluded from context unless the owner explicitly opts in. Editing
without a sensitivity field preserves it; restoring a historical version cannot implicitly lower the
current label. The CLI never calls a provider. On `/personal/chat`, `allow_sensitive: true` allows the
selected sensitive memory excerpts to reach the configured provider. It does not create automatic PII
classification, redact questions, or classify manually maintained private Markdown.

## Independent Python example

From the repository root, after installing the documented backend dependencies:

```bash
PYTHONPATH=backend .venv/bin/python - <<'PY'
from tempfile import TemporaryDirectory
from app.memory import Store
from app.memory_models import IngestionInput, SourceInput
from app.learning import LearningPipeline

with TemporaryDirectory() as directory:
    memory = Store(directory)
    learning = LearningPipeline(memory)
    source = learning.register(SourceInput(kind="document", name="Synthetic profile"))
    learning.approve(source["id"], expected_revision=1)
    run = learning.ingest(source["id"], IngestionInput(content="fact identity.name: Alex Example"))
    entry_id = run["items"][0]["memory_id"]
    assert not memory.context("Alex Example")
    memory.confirm(entry_id, [], expected_revision=1)
    assert memory.context("Alex Example")
    print(run["status"], learning.origins(entry_id)[0]["excerpt"])
PY
```

Expected: `completed Alex Example`. No server, `.env`, API token, frontend, or provider is required.

## Local owner CLI

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --help
```

All operations accept `--data-dir <directory>` before the command; the default is the ignored
`private/` directory. On PowerShell, set `$env:PYTHONPATH = "backend"` and use
`.venv\Scripts\python.exe -m app.agent_cli`. The CLI relies on filesystem ownership, not the HTTP
workspace token. It outputs JSON and never loads provider configuration.

| Command | Purpose |
| --- | --- |
| `source register --name NAME --kind document` | Register unapproved source; optional sensitivity |
| `source list` | Inspect source IDs, approval and revision |
| `source approve ID --expected-revision N` | Approve a reviewed source revision |
| `source revoke ID --expected-revision N` | Stop future ingestion/replay |
| `ingest SOURCE_ID FILE --mode fields` | Submit explicitly named UTF-8 file; `notes` also supported |
| `runs` | Inspect latest 100 ingestion runs |
| `memory list --include-superseded` | Inspect active records and optional archives |
| `memory show ID` / `memory history ID` / `memory origins ID` | Inspect current record, revisions, exact source excerpts |
| `memory add --key KEY --content TEXT` | Deliberately propose manual memory |
| `memory confirm ID --expected-revision N` | Accept the reviewed record |
| `memory confirm ... --replace OLD --replace-revision OLD:N` | Replace explicitly reviewed conflicting records |
| `memory edit ID --content TEXT --expected-revision N` | Correct a record; optional kind/key/sensitivity |
| `memory restore ID --revision N` | Propose an old version as a new candidate |
| `memory delete ID --yes` | Purge this record/versions/origins and register forgetting digests |
| `recall QUESTION --allow-sensitive` | Local current-memory retrieval, with optional explicit disclosure |
| `export FILE` | Export version-3 private snapshot; refuses overwrite unless `--force` |

Export permissions are restricted to 0600 on POSIX; Windows access protection depends on filesystem
ACLs rather than POSIX mode bits. Export is plaintext and is not an import, encryption, or backup-recovery
feature. Exit codes: 0 success, 1 failed ingestion run, 2 invalid/denied/stale/failed command.

## Authenticated API

All paths use `/api/v1/personal` and the existing owner token:

| Method | Path | Contract |
| --- | --- | --- |
| GET / POST | `/learning/sources` | List / register sources |
| POST | `/learning/sources/{id}/review` | `{approved: boolean, expected_revision?: integer}` |
| POST | `/learning/sources/{id}/ingest` | `{content, mode?: "fields" or "notes", expected_source_revision?: integer}` |
| GET | `/learning/runs` | Latest 100 durable run records |
| GET | `/entries/{id}/origins` | Exact source excerpts and code-point spans |

Private export is now version `3` and includes sources, ingestion runs, origins and forgetting digests
alongside entries/history/revisions, read in one database snapshot. Older export consumers must be
updated. The repository release version is unchanged; the reference UI downloads JSON without parsing it.

## Evaluation

```bash
make evaluate-memory
make evaluate-learning
```

Expected: memory 18/18 and learning 17/17. `make evaluate` includes both plus collaboration evaluation.
Tests additionally cover malformed/oversized input, Unicode normalization, concurrent replay, rollback,
source review races, sensitive opt-in, source revocation, and the CLI. These are deterministic regression
checks, not proof of semantic truth, personality imitation, or unattended long-term ingestion quality.
