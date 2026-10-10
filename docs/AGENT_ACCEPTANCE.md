# Personal Agent roadmap acceptance audit

Scope: the six numbered [roadmap workstreams](../ROADMAP.md) and proposal
[#169](https://github.com/jzjzzzzzzz/agent-me/issues/169), implemented as an independent,
single-owner Python Agent with authenticated API and local CLI. No frontend source changes.
This accepts the implemented bounded contracts, not objective truth, autonomous semantic
inference, arbitrary external integrations, multi-tenant security or personality imitation.

## Completion signals and direct evidence

| Roadmap workstream | Completion signal | Authoritative implementation and evidence |
| --- | --- | --- |
| 1. Structured identity/memory | Explain beliefs, sources, learned/valid times and dispute/currentness | `memory.py`, `identity.py`, `memory_time.py`; seven entity kinds, three memory categories, relationships, source/revision metadata, optional confidence, five belief states, ownership, aliases, correction/supersession/restore/deletion; memory 18/18, identity 19/19 plus Core/API/CLI lifecycle tests |
| 2. Continuous controlled learning | Predictable updates without duplicate accumulation, lost provenance or silent conflicting overwrite | `learning.py`, `learning_policy.py`, `retention.py`, `consolidation.py`; approved four-kind sources, literal pending candidates, dedup/entity resolution, time-aware conflict review, configured retention/forgetting/review, exact selective consolidation, atomic replay/recovery; learning 24/24 plus failure/concurrency/CAS tests |
| 3. Personal retrieval | Measured factual, temporal, preference, project and relationship retrieval | `retrieval.py`; lexical + controlled-field + alias + graph hybrid, namespaces/subject scopes, validity vs knowledge time, sensitivity/confidence/budget gates, sufficiency and overlapping-interval contradictions; retrieval 16/16 plus current identity-label/preference boundary regressions |
| 4. Contextual agency/tools | Trace each action to intent, permission, reviewed plan, actual result and outcome | `agent_runtime.py`, `agency.py`; know/recommend/act, three real local task/note tools, default-off per-tool data scopes, exact digest/revision approval, live preconditions, inspectable calls/results/events, concurrent idempotency, bounded explicit retry and unchanged-effect rollback; agency 17/17 plus API/CLI tests |
| 5. Verification/longitudinal evaluation | Repeatable evidence of fidelity as data changes | `personal_agent.py`; live atomic field/value/subject/belief/confidence verification, uncertain/unsupported distinction, contradiction/correction/deletion/privacy/injection cases; 20-stage longitudinal report measures calibration/coverage/provenance/style/privacy and actual accepted/rejected correction operations; mutation tests fail when retrieval/audit controls are removed |
| 6. Privacy/portability/owner control | Understand, move, correct and remove personal state without opaque authority | `portability.py`, `owner_control.py`, `audit.py`, `disclosure.py`; typed version-8 portable export, reviewed transactional import of v6/7/8, inert historical grants, explicit copy deletion/SQLite purge, content-free audit, default-off scoped target-bound dual-opt-in disclosure, documented host/provider/tool limits; owner control 14/14, rich import/erasure tests and actual mock-HTTP payload checks |

The [implementation ledger](AGENT_IMPLEMENTATION.md) provides finer requirement-by-requirement
mapping. Each private feature is native Core/API/CLI, not an unimplemented frontend button.
Public Python/TypeScript reference contracts remain compatible; new private-only routes do not
require adding frontend consumers. Export is downloaded as opaque JSON by the unchanged UI.

## Local final verification

Executed on the developed branch after the final capability changes:

- `make lint`: locked dependency/version checks, Python lint/format and unchanged frontend
  lint/typecheck pass.
- `make test`: **473 backend tests** and **153 unchanged frontend regression tests** pass.
- `make docs`: Markdown links and 16 maintained bilingual lesson pages pass.
- `make evaluate`: collaboration 4/4, memory 18/18, learning 24/24, identity 19/19,
  retrieval 16/16, agency 17/17, owner control 14/14 and longitudinal 20 stages pass.
- Verified collaboration workflow evaluation also passes 4/4.
- `make knowledge-check`: the committed fictional corpus passes.
- `git diff --check`: passes; `git diff 2a1a2db^ --name-only -- frontend` is empty.
- Real loopback Uvicorn acceptance: unauthorized access denied; owner review and grounded
  ask work; planning has no effect; exact approval executes a real task; revision-bound
  erasure removes it; memory deletion removes the returned claim; no-store, v8 export and
  default-off disclosure verified. Temporary server/workspace cleaned up.
- Docker Compose images build and both hardened services become healthy using only
  `.env.example` and the fictional public corpus on isolated ports. API health/readiness,
  direct and proxied grounded collaboration, private disabled defaults and `nosniff` pass.
  Temporary acceptance containers/network are removed. No owner environment was injected.
- Staged private-data scan and explicit review are required before the final commit/push.

CI repeats tests/evaluations on Python 3.11, Python 3.12 and Windows, builds the unchanged
web reference, checks documentation/private data, and runs container acceptance. Remote
head equality and hosted CI are verified after push and recorded on the pull request;
local success is not substituted for an unobserved hosted check.

The capability commit `ebd0820` was pushed and its exact remote SHA verified. Hosted
[CI](https://github.com/jzjzzzzzzz/agent-me/actions/runs/38032439586) passed. A CodeQL parser
performance finding was then addressed by a linear scanner and focused regressions.
The current delivery head, review state and re-run gate results are available on
[PR #170](https://github.com/jzjzzzzzzz/agent-me/pull/170); this records delivery, not an
automatic merge into `main`.

## Accepted boundaries

- Literal reviewed learning/consolidation and controlled semantic fields are implemented;
  unconstrained semantic inference or prose entailment is not claimed.
- Atomic evidence fidelity is implemented; owner declarations/source quotes can be false.
  Confidence calibration here is fictional declared-record calibration, not LLM probability.
- Local SQL tools have real rollback; provider/network delivery does not. No arbitrary
  shell/browser/mail/network action plugin is registered.
- SQLite purge covers all database copies, not operator Markdown, environment credentials,
  backups/exports/Git history, provider copies or already returned answers.
- The owner token and host are trusted, not delegated/multi-tenant boundaries; audit is
  content-free, bounded and owner-removable, not immutable security attestation.
- Frontend source/dependencies are intentionally untouched under the user's Agent-only scope.

These are explicit trust/measurement limits of the shipped contracts, not hidden unfinished
roadmap rows. Future capability expansions must add their own contracts and evaluation evidence.
