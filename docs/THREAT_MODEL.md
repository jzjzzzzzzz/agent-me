# Personal knowledge and connected-tool threat model

This model describes the implemented boundaries, not future external-tool promises.
Evidence: [learning](LEARNING.md), [identity/time](IDENTITY_TIME.md),
[retrieval](PERSONAL_RETRIEVAL.md), [agency](AGENCY.md),
[owner control](OWNER_CONTROL.md), and the acceptance ledger/tests linked below.

## Assets, actors and trust boundaries

Assets include personal facts/preferences/episodes, identity aliases/relationships, source
excerpts and timestamps, declared confidence, transcripts, action arguments/results,
approval metadata, forgetting hashes, audit metadata, plaintext exports and the owner token.

The deployment is single-owner and local-first. The host filesystem/process, local CLI
caller and configured owner bearer credential are trusted owner capabilities. Approved
documents, source text, memory content, model/provider prose and import files are **data**,
not execution authority. There is no tenant isolation, delegated agent credential, untrusted
client capability model or hostile-host defense. All holders of the owner token have owner
rights, including explicit permission configuration, approval and deletion.

Public chat/collaboration uses a separate fictional/versioned corpus and never reads the
private database. Private API is disabled by default and requires a >=32-character owner
token, constant-time comparison, bounded bodies and no-store responses. The independent
core and ordinary local CLI commands do not load HTTP configuration or provider credentials.
The opt-in [semantic CLI adapter](SEMANTIC_LEARNING.md#explicit-file-local-cli) reads only a named,
bounded private provider JSON file, never ambient `.env`/environment settings. Only `semantic ingest`
can deliver the exact reviewed source with target/revision/content hashes and per-attempt consent.
Local caller/configuration-file access is trusted owner authority, not delegated network permission;
the workspace's enabled source-scoped disclosure policy remains separately required.

## Threats, controls and direct regression evidence

| Threat | Implemented control | Evidence |
| --- | --- | --- |
| Public endpoint obtains private context | Separate public/private stores, disabled private defaults and owner dependency | `test_personal.py`, `test_personal_agent_api.py` |
| Source instruction grants tools or skips review | Literal candidate extraction; pending-only learning; typed intent/tool registry; permissions independent of memory | `test_learning.py`, `test_agency.py`, learning/agency evaluations |
| Sensitive evidence relabeled public or rebound through history | Source/entity/record privacy floors, current/historical checks, per-tool labels/subjects and inherited task lineage | `test_identity_temporal.py`, `test_personal_retrieval.py`, `test_agency.py` |
| Public fictional identity or another person impersonates owner | Explicit owner binding, namespace/subject scopes and ambiguity refusal | retrieval evaluation; `test_personal_retrieval.py` |
| Stale evidence or forged claims presented as current | Valid/knowledge time, explicit epistemic states, exact live atomic claim/evidence checks | identity/retrieval evaluations; forged/deleted-in-flight tests |
| Hidden conflicting update or forgotten data replay | Reviewed replacement CAS, histories, source revocation, digest dedup/forgetting and atomic runs | memory/learning/identity evaluations |
| Changed arguments/data after approval | Digest/revision-bound approval; live source, target, entity and permission checks under execution lock | `test_agency.py`, agency evaluation |
| Duplicate side effects or partial failure | Fixed SQLite tools, unique idempotency key, atomic effect/result events, bounded explicit retries | concurrent/fault tests in `test_agency.py` |
| Rollback destroys later work | Exact output owner/revision and creation provenance; status-only undo with new revision | agency evaluation and undo tests |
| Import smuggles live grants/approved plans | Typed/integrity validation, exact review digest, empty target and inert historical-authority archive | `test_portability.py`, owner-control evaluation |
| Import partially overwrites workspace | Write-locked destination recheck and atomic owner/data adoption | concurrent/fault tests in `test_portability.py` |
| Error/log/cache exposes private request | Private validation redacts input; safe failure codes; static content-free audit; no-store responses | `test_owner_control_api.py`, `test_learning_api.py`, `test_agency_api.py` |
| Erasure leaves inspectable independent copies | Separate output/action/source/archive/history/audit erasure and explicit all-SQLite purge | `test_owner_control.py`, owner-control evaluation |
| Excessive input or unbounded tool graph | Typed field/body/document/corpus/context limits, bounded graph/plan/import/audit sizes; no arbitrary plugins | input-limit/contract tests and documented component bounds |

## Provider and external-action boundaries

Personal atomic `ask/retrieve/verify`, learning, identity, retention, consolidation, local
tools and owner control do not call providers. Optional legacy `/personal/chat` generation
requires owner-configured credentials, an enabled target/data-scoped [disclosure policy](DISCLOSURE.md)
and per-request `allow_provider: true`; credentials alone do not enable transmission. Sensitive
context additionally requires per-request opt-in and allowed policy labels. Owner-maintained private Markdown is not automatically PII-classified.
The legacy free-prose path is not certified by the atomic verifier. Provider failures are
classified without copying upstream bodies, credentials or URLs into responses.

Only local task/note tools exist. They have no network, shell, mail, browser, arbitrary-path
write, plugin registration or external credentials. SQLite rollback is real only because
all current effects are in that database. Before adding an external adapter, its contract
must separately define credential/data scope, consent UX/approval, retry/idempotency keys,
delivery uncertainty, compensation limits, cancellation, disclosure audit and adversarial
fixtures. Reusing local transaction claims for external irreversible effects is invalid.

## Local storage, audit and removal limits

The database is plaintext. POSIX database/root permissions are 0600/0700 for newly created
paths; existing directory permissions and Windows ACLs remain owner/operator responsibilities.
Symlink database paths are rejected. Git/Docker ignore rules are not encryption, access
control against the host owner, or retroactive cleanup of past commits/exports.

Audit records are private aggregate operational metadata and rotate at 10000 events. The
owner can clear them and edit the database; no non-repudiation or append-only security
guarantee is claimed. Low-level filesystem/SQLite access is not intercepted. Invalid-token
traffic does not create private workspace events. External HTTP infrastructure logs are
outside this bounded application audit contract.

Deleting a memory prevents future live verification/retrieval of its deleted snapshots,
but cannot revoke an already returned answer. Local rollback does not erase plan text;
explicit action/output/archive deletion or SQLite purge controls those copies. SQLite
purge does not delete operator-maintained private Markdown, environment credentials,
previous backups/exports/Git history, provider copies or physical media remnants.
Deleting a stopped ignored workspace and separately managing those copies is owner control,
not a background purge promise. A deliberately reviewed old export can reintroduce older
data; automatic ingestion remains bounded by the active forgetting registry.

## Verification limits and change discipline

Owner acceptance, source-value verification and hashes establish attributable local state,
not objective truth or arbitrary prose entailment. Confidence is owner-declared, never
invented. Unknown/inferred/disputed/outdated answers retain their uncertainty. Literal
consolidation does not infer semantic equivalence. New external capabilities must update
this model and add supported, unsupported, privacy, injection, temporal and failure fixtures
before being considered implemented. See [full acceptance ledger](AGENT_IMPLEMENTATION.md).
