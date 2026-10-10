# Personal Agent implementation and acceptance ledger

Tracking proposal: [#169](https://github.com/jzjzzzzzzz/agent-me/issues/169).
Scope: implement the [full AI Twin roadmap](../ROADMAP.md) through the independent Python
Agent core, authenticated adapters, and owner-facing CLI. No frontend changes are planned.
This ledger records the implemented bounded contracts and their acceptance evidence,
not a promise about future external integrations or semantic truth guarantees.
The [final acceptance audit](AGENT_ACCEPTANCE.md) maps all six completion signals to
implementation, direct tests/evaluations, runtime acceptance and explicit contract boundaries.

## Acceptance requirements

| Workstream | Required behavior | Current evidence / remaining work |
| --- | --- | --- |
| Identity | Typed people, projects, organizations, events, ideas, preferences, decisions and relationships | `identity.py` typed entities, reviewed evidence-linked relationships; alias ambiguity and privacy tests |
| Identity | Source, learned time, confidence, sensitivity and ownership | Source snapshots, labels, persistent workspace ownership, optional declared confidence, category and temporal fields; `test_identity_temporal.py` |
| Identity | Correction, supersession, deletion and export | `memory.py` lifecycle plus `portability.py` digest-reviewed transactional import; rich round-trip and malformed snapshot tests |
| Learning | Explicitly approved document/project/conversation/event sources | `learning.py` registration/review; core/API/CLI approval tests |
| Learning | Candidate extraction before owner acceptance | `learning.py` exact field/paragraph candidates; `test_learning.py`; semantic inference remains out of scope |
| Learning | Deduplication, entity resolution, temporal conflict handling | Canonical exact deduplication, Unicode-equivalent key conflicts and same-kind/key review exist; confirmed alias resolution and interval/episode conflict handling exist; semantic inference remains unproven |
| Learning | Retention, forgetting and consolidation | Replay-aware forgetting and reviewed retention exist; `consolidation.py` provides exact cross-record preview/digest apply, preserved histories/origins and no auto-acceptance; Core/API/CLI tests |
| Learning | Sensitive/identity-defining review policies | Every candidate requires owner confirmation; `learning_policy.py` configures source/label/size/key boundaries and stricter revision-bound label/identity review; `evaluate_learning.py` now 24 cases |
| Learning | Replayable traces and recoverable failure | `learning.py` atomic batches, durable failed/completed runs, stable retry IDs; concurrency/failure tests |
| Retrieval | Hybrid documents/memory and relationship-aware context | `retrieval.py` lexical/field/alias/relationship hybrid, namespaced bounded documents and temporal selection; retrieval tests |
| Retrieval | Temporal selection and stale/disputed knowledge | Valid-time and knowledge-time selection, expiry/future exclusion and effective belief states; `evaluate_identity.py` |
| Retrieval | Sensitivity-aware assembly and evidence sufficiency | Typed bounded evidence assembly, live privacy/confidence checks, sufficiency states and presentation-vs-fact separation |
| Retrieval | Factual, temporal, preference, project and relationship evaluation | `evaluate_retrieval.py` covers factual/temporal/preference/project/relationship, unsupported/privacy/adversarial cases |
| Agency | Typed routing and explicit tool/data permissions | `agent_runtime.py`, `agency.py`: three registered local task/note tools, disabled defaults, labels and entity scopes; Core/API/CLI tests |
| Agency | Plan/approval gates and inspectable calls/results | Digest/revision-bound review, live preconditions, inspectable plans/results/events; `test_agency.py`, `test_agency_api.py` |
| Agency | Idempotency, retry, rollback and clear know/recommend/act boundaries | Real SQLite effects, atomic failure, concurrent idempotency, bounded explicit retries and unchanged-output rollback; `evaluate_agency.py` 17 cases |
| Verification | Atomic claim/evidence mapping and temporal consistency | `personal_agent.py` constrained atomic values and live authoritative verification; arbitrary paraphrase entailment remains unproven |
| Verification | Fidelity, contradiction, correction, deletion and injection/privacy regressions | Lifecycle, relationship, temporal, privacy, injection-as-data, forged-claim and in-flight deletion suites; longitudinal evaluation and conflict/interval/preference regressions |
| Verification | Calibration, coverage, provenance and correction-effort metrics | `evaluate_longitudinal.py`: 20 labeled stages, declared-confidence Brier/coverage, answer/provenance coverage, abstention, privacy/style fidelity and accepted/rejected correction effort; mutation and missing-denominator tests |
| Owner control | Local/provider boundaries, labels, selective disclosure | Provider-free atomic Core/CLI, dual opt-in target-bound provider policy, labels, server namespaces and entity/record/document scopes; actual mock-HTTP payload tests in `test_disclosure.py` |
| Owner control | Review/correct/export/delete interfaces and portable formats | Core/API/CLI lifecycle, portable import with inert authority archives, revision-bound independent-copy erasure and SQLite purge; `test_portability.py`, `test_owner_control.py` and API/CLI tests |
| Owner control | Ingestion/access audit and connected-tool threat model | Content-free core ingestion/retrieval and authenticated API/CLI operational audit, explicit rotation/clear; `docs/THREAT_MODEL.md`, owner-control evaluation 14 cases |

## Execution order

1. Versioned, independently runnable memory foundation (implemented, commit `2a1a2db`).
2. Approved-source learning, exact source excerpts, deduplication, replay-aware forgetting,
   explicit sensitivity boundaries, and a CLI usable without an HTTP server (implemented;
   `test_learning.py`, `test_learning_api.py`, `test_agent_cli.py`, `evaluate_learning.py`).
3. Structured identity/relationships, declared confidence, ownership and temporal retention semantics
   (implemented; `identity.py`, `memory_time.py`, `retention.py`, Core/API/CLI tests and identity evaluation).
4. Unified personal retrieval, disputed/stale evidence and atomic grounded answers (implemented;
   Core/API/CLI ask/retrieve/verify, `test_personal_retrieval.py`, `evaluate_retrieval.py`).
5. Typed contextual agency and real bounded tools with permissions and approval gates
   (implemented; [contracts](AGENCY.md), Core/API/CLI tests and 17-case agency evaluation).
6. Portability/import, audit/threat-model coverage, longitudinal metrics, complete acceptance audit.
   Learning-policy configuration, selectively previewed exact consolidation, portable import,
   independent-copy deletion, operational audit and threat model are implemented; see
   [learning controls](LEARNING_CONTROL.md) and [owner control](OWNER_CONTROL.md).
   Provider/document disclosure policy and 20-stage longitudinal metrics are implemented; see
   [disclosure](DISCLOSURE.md) and [longitudinal evaluation](LONGITUDINAL_EVALUATION.md).
   All six workstream contracts have implementation/test and runtime acceptance evidence.
   Delivery and hosted verification are recorded on [PR #170](https://github.com/jzjzzzzzzz/agent-me/pull/170);
   this does not claim that external truth or future integrations are solved.
7. Run all applicable quality gates, review public artifacts for private data, push the developed
   branch, and verify the remote commit and CI. Only then consider the full objective achieved.

Each implemented requirement needs direct tests or runnable evaluation evidence. A passing
unit suite does not by itself prove the entire roadmap. Docker execution, external integrations,
and hosted CI must be distinguished from local checks; unavailable checks are not marked passed.

## Delivery record

Branch `feat/personal-agent-roadmap` is pushed to the requested `jzjzzzzzzz/agent-me` repository.
Local/remote capability commit `ebd0820` matched exactly. Its hosted
[CI run](https://github.com/jzjzzzzzzz/agent-me/actions/runs/38032439586) passed backend,
Python 3.11, Windows PowerShell, unchanged frontend, documentation/private-data and container gates;
CodeQL scanning identified a field-parser performance finding, addressed by a linear scanner
with large-whitespace/span regressions. The pull request's current-head CI and security checks
remain the authoritative final status, rather than the earlier scan's workflow completion alone.
