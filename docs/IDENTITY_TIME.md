# Structured identity, uncertainty, time and retention

This is pure Agent core/API/CLI functionality. It does not add a frontend or require a graph database,
model provider, or server. The [acceptance ledger](AGENT_IMPLEMENTATION.md) tracks the full roadmap;
unified retrieval, local contextual tools, portable import and operational audit are implemented;
longitudinal metrics are implemented; final full-roadmap acceptance is tracked in the ledger.

## Owner-reviewed identity

`IdentityStore` supports `person`, `project`, `organization`, `event`, `idea`, `preference`, and
`decision` entities. Each record has a server-generated ID, workspace `owner_id`, manual source,
UTC timestamps, sensitivity label, revision, and pending/confirmed state. Creation and edits require
review before aliases can resolve or memory can bind to the identity.

Alias resolution uses Unicode NFC, case folding and whitespace normalization. It never guesses that
similar names describe the same person. An exact duplicate name/alias set with the same kind and
sensitivity reuses the entity; deliberate distinct identity creation is supported. Multiple confirmed
matches produce `ambiguous`, never an implicit merge. Source registration accepts either a confirmed
`entity_id` or an explicitly supplied `entity_alias`; unknown or ambiguous aliases fail.

Entities are identifiers curated by the owner, not machine-certified biographical facts. Their
names/aliases do not establish a real-world identity or factual truth. Confirmed memory still provides
claim provenance. Entity edits preserve unspecified labels/aliases and make the identity pending again.
An unreviewed identity temporarily excludes linked memory from context.

Relationships are owner-proposed predicates linking two confirmed entities to a **specific confirmed
memory revision**. They require separate confirmation. Current relationship context checks both
endpoints, owner, sensitivity, evidence revision, epistemic state and validity. Changed/deleted evidence
cannot silently keep an old edge current. Semantic entailment of the predicate is not proven by the
source link; the owner reviews it. Neighbour context is one hop, at most 32 entities and 64 edges.

## Memory boundaries and uncertainty

Every memory now has:

- workspace ownership and optional subject entity;
- category: `semantic` for facts, `preference` for preferences, `episodic` for events/decisions;
- optional owner-declared `confidence` in [0, 1]; and
- belief: `known`, `inferred`, `disputed`, `outdated`, or `unknown`.

Confidence defaults to **null**, not an invented probability. It is an owner-declared strength signal,
not a calibrated likelihood of truth. Pending lifecycle state still excludes all new claims; confirmation
is owner acceptance, not automatic factual verification. Current factual context includes confirmed
`known` records only. Other beliefs remain inspectable through explicit uncertain-memory selection.

Entity binding scopes kind/key conflicts, so two people may have different values for `role` without
one replacing the other. A subject's sensitivity is a live floor for its memory and relationship context.
Historical queries also respect the current record and current/historical subject privacy floors.
No historical query can restore a deleted record or bypass a later sensitivity increase.

## Two time axes

Times must be timezone-aware. Persistence normalizes declared times to UTC.

- `created_at` / revision `updated_at`: when the workspace observed or reviewed a state.
- `valid_from` / `valid_until`: optional owner-declared half-open validity interval `[from, until)`.
- `occurred_at`: optional actual episode time for events/decisions, not facts/preferences.

An absent validity bound is unbounded, not a guessed date. Expired/not-yet-valid information is excluded
from ordinary context. Inspection returns `effective_belief` separately from the stored owner belief.
Nonoverlapping same-subject/key intervals may coexist; overlapping intervals still require explicit
replacement. Distinct dated episodes are not deduplicated into one event. Equal instants written with
different offsets share an episode identity/replay key. Undated episodes remain conservative same-key
conflicts: no occurrence time is inferred from the ingestion timestamp.

`as_of` selects declared valid time. `known_at` selects the latest recorded revision observed before a
knowledge-time cutoff. These axes differ: a fact learned today about 2020 can appear in a retrospective
2020 validity query, but not in a "what did the twin know in 2020?" query. This is recorded-state selection,
not proof of historical truth or a prediction of future reality.

Current queries do not use superseded snapshots. Explicit knowledge-time queries can inspect a prior
confirmed revision while the original record still exists and current privacy permits it. Deletion
removes the whole revision chain; historical lookup does not resurrect it.

Scheduled changes should use explicitly nonoverlapping validity intervals. Explicit replacement
supersedes an old record immediately; it does not silently keep that old record until a future new start.
Edits preserve unspecified temporal/confidence/subject metadata. To change an episodic record to a
semantic kind, explicitly clear incompatible occurrence time rather than losing it implicitly.

## Ownership and deletion

Workspace owner IDs are local persistent identifiers, not multi-user authentication. All API operations
still use the existing single-owner token; the CLI uses local filesystem ownership. Clients cannot set
owner IDs, categories, revisions, source or confirmation status through memory creation.

Deleting an entity purges its aliases, entity revisions, endpoint relationships, bound sources/runs,
and **entire memory revision chains ever bound to it**, including chains later rebound to another subject.
That conservative boundary prevents a rebinding from retaining forgotten historical data. Independently
created records mentioning an unlinked person are not semantically detected or automatically erased.
Memory forgetting digests remain opaque private metadata. Source uploads bound to a deleted entity cannot
replay. Current/historical subject bindings and episode/validity qualifiers participate in deduplication;
legacy unscoped forgetting remains conservative against later automatic re-binding.

Schema-3 and older workspaces migrate transactionally. Existing snapshots, content and timestamps are
preserved; no confidence or event/validity time is fabricated. Existing records gain the workspace owner
and category, with null subject/confidence/time bounds. Export version is now `4` with identity histories,
relationships, ownership and retention state. There is still no import contract.

## Configurable, reviewable retention

All retention periods default to null: **no automatic purge**. The owner can set positive integral days
for pending memories, superseded memories, expired confirmed memories, chat turns, and ingestion runs.
Expiry is context selection; purging is a separate owner operation.

1. Configure a policy with its reviewed revision.
2. Preview a persisted plan of specific record IDs/revisions or content-free fingerprints.
3. Inspect the target records, then explicitly apply that plan.

Execution is atomic and checks policy/target freshness. An edited target, retried ingestion run or
changed policy invalidates the plan. A forecast preview cannot execute before its effective time.
Re-applying a successful plan is idempotent. At most 1,000 targets can be planned in one operation;
excess requires a narrower policy, not silent partial deletion. Record purge also clears snapshots,
origins and dependent relationship evidence, and retains replay-prevention digests. Transcript/run
purge does not delete independent memories. Historical run IDs in retained origins may refer to purged
runs. Nothing periodically purges in the background without an explicit apply call.

## CLI

Use the existing prefix from the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --help
```

| Command / flags | Operation |
| --- | --- |
| `entity add --kind person --name NAME --alias ALIAS` | Propose identity; optional sensitivity/distinct flag |
| `entity confirm ID --expected-revision N` | Confirm reviewed identity |
| `entity edit ID --name NAME --expected-revision N` | Correct identity; preserves unspecified aliases/label |
| `entity list` / `entity history ID` | Inspect records and change history |
| `entity resolve NAME --allow-sensitive` | Explicit alias lookup; optional sensitive disclosure |
| `entity neighbours ID --allow-sensitive` | Bounded current evidence-linked neighbourhood |
| `entity delete ID --yes` | Purge identity and the linked chains described above |
| `relationship add --from-entity-id A --to-entity-id B --predicate works_on --evidence-id M` | Propose evidence-linked relation |
| `relationship confirm ID --expected-revision N` | Confirm reviewed relation |
| `relationship list` / `relationship history ID` / `relationship delete ID --yes` | Inspect or remove links |
| `memory add/edit ... --entity-id ID --confidence 0.8 --belief known` | Subject and uncertainty metadata |
| `memory add/edit ... --valid-from TIME --valid-until TIME --occurred-at TIME` | Declared aware times |
| `memory edit ... --unset occurred_at` | Explicitly clear nullable metadata |
| `source register ... --entity-id ID` or `--entity-alias NAME` | Bind approved source proposals |
| `ingest ... --valid-from TIME --valid-until TIME --occurred-at TIME` | Document-level declared temporal qualifiers |
| `recall QUESTION --entity-id ID --as-of TIME --known-at TIME` | Local selected context |
| `select --include-uncertain --allow-sensitive --as-of TIME --known-at TIME` | Inspect effective state and original records |
| `retention policy` / `retention plans` | Inspect policy and plans |
| `retention configure --policy-json '{"expired_days":30}' --expected-revision N` | Configure forgetting policy |
| `retention preview --as-of TIME` | Inspect a plan; time is optional |
| `retention apply ID --yes` | Execute reviewed targets atomically |

## Authenticated API

Prefix `/api/v1/personal`; all routes require owner authorization and return `Cache-Control: no-store`.

| Method | Route | Contract |
| --- | --- | --- |
| POST | `/memory/select` | TemporalQuery, including subject/time/privacy/uncertain selection |
| GET / POST | `/identity/entities` | List / propose typed identity |
| POST | `/identity/entities/{id}/edit` | Entity fields plus required `expected_revision` |
| POST | `/identity/entities/{id}/confirm` | Required `expected_revision` |
| GET | `/identity/entities/{id}/history` | Versioned identity snapshots |
| POST | `/identity/entities/{id}/delete` | Purge linked identity data |
| POST | `/identity/resolve` | `{name, kind?, allow_sensitive?}`; names stay out of URLs/access logs |
| GET | `/identity/entities/{id}/neighbours` | Bounded current context; optional sensitive flag |
| GET / POST | `/identity/relationships` | List / propose evidence-linked relation |
| POST | `/identity/relationships/{id}/confirm` | Required `expected_revision` |
| GET | `/identity/relationships/{id}/history` | Relation snapshots |
| POST | `/identity/relationships/{id}/delete` | Remove relation and history |
| GET / POST | `/retention/policy` | Inspect / configure `{policy, expected_revision}` |
| POST | `/retention/preview` | `{as_of?}`; unsupported filtering fields are rejected |
| GET | `/retention/plans` | Latest 100 retained plans |
| POST | `/retention/plans/{id}/apply` | Explicit application of an existing reviewed plan |

## Verification

```bash
make evaluate-identity
```

Expected: `IDENTITY_EVAL 19/19 passed`. The suite checks positive/negative alias resolution, ambiguity,
subject scope, reviewed relationships, evidence invalidation, ownership, historical privacy and
forgetting, valid/knowledge time separation, future/expired/disputed states, and retention preview/apply.
Additional tests cover native contracts, API/CLI operations, source binding, policy/target races,
rollback, UTC equivalence, and migration without invented evidence. These checks do not establish
semantic entailment, factual truth, automatically calibrated confidence, or personality imitation.
