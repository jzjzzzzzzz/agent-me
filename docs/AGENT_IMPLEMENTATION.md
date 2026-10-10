# Personal Agent implementation and acceptance ledger

Tracking proposal: [#169](https://github.com/jzjzzzzzzz/agent-me/issues/169).
Scope: implement the [full AI Twin roadmap](../ROADMAP.md) through the independent Python
Agent core, authenticated adapters, and owner-facing CLI. No frontend changes are planned.
This ledger is not a release promise or a claim that the roadmap is complete.

## Acceptance requirements

| Workstream | Required behavior | Current evidence / remaining work |
| --- | --- | --- |
| Identity | Typed people, projects, organizations, events, ideas, preferences, decisions and relationships | `identity.py` typed entities, reviewed evidence-linked relationships; alias ambiguity and privacy tests |
| Identity | Source, learned time, confidence, sensitivity and ownership | Source snapshots, labels, persistent workspace ownership, optional declared confidence, category and temporal fields; `test_identity_temporal.py` |
| Identity | Correction, supersession, deletion and export | `memory.py`, lifecycle tests and memory evaluation; portable import remains |
| Learning | Explicitly approved document/project/conversation/event sources | `learning.py` registration/review; core/API/CLI approval tests |
| Learning | Candidate extraction before owner acceptance | `learning.py` exact field/paragraph candidates; `test_learning.py`; semantic inference remains out of scope |
| Learning | Deduplication, entity resolution, temporal conflict handling | Canonical exact deduplication, Unicode-equivalent key conflicts and same-kind/key review exist; confirmed alias resolution and interval/episode conflict handling exist; semantic inference remains unproven |
| Learning | Retention, forgetting and consolidation | Record/snapshot/origin deletion and replay-aware digest forgetting exist; `retention.py` preview/apply policy exists; explicit cross-record consolidation remains |
| Learning | Sensitive/identity-defining review policies | Every extracted candidate needs owner confirmation; sensitivity floor is enforced; richer policy configuration remains |
| Learning | Replayable traces and recoverable failure | `learning.py` atomic batches, durable failed/completed runs, stable retry IDs; concurrency/failure tests |
| Retrieval | Hybrid documents/memory and relationship-aware context | `retrieval.py` lexical/field/alias/relationship hybrid, namespaced bounded documents and temporal selection; retrieval tests |
| Retrieval | Temporal selection and stale/disputed knowledge | Valid-time and knowledge-time selection, expiry/future exclusion and effective belief states; `evaluate_identity.py` |
| Retrieval | Sensitivity-aware assembly and evidence sufficiency | Typed bounded evidence assembly, live privacy/confidence checks, sufficiency states and presentation-vs-fact separation |
| Retrieval | Factual, temporal, preference, project and relationship evaluation | `evaluate_retrieval.py` covers factual/temporal/preference/project/relationship, unsupported/privacy/adversarial cases |
| Agency | Typed routing and explicit tool/data permissions | `agent_runtime.py`, `agency.py`: three registered local task/note tools, disabled defaults, labels and entity scopes; Core/API/CLI tests |
| Agency | Plan/approval gates and inspectable calls/results | Digest/revision-bound review, live preconditions, inspectable plans/results/events; `test_agency.py`, `test_agency_api.py` |
| Agency | Idempotency, retry, rollback and clear know/recommend/act boundaries | Real SQLite effects, atomic failure, concurrent idempotency, bounded explicit retries and unchanged-output rollback; `evaluate_agency.py` 17 cases |
| Verification | Atomic claim/evidence mapping and temporal consistency | `personal_agent.py` constrained atomic values and live authoritative verification; arbitrary paraphrase entailment remains unproven |
| Verification | Fidelity, contradiction, correction, deletion and injection/privacy regressions | Lifecycle, relationship, temporal, privacy, injection-as-data, forged-claim and in-flight deletion suites exist; full metrics remain |
| Verification | Calibration, coverage, provenance and correction-effort metrics | Boolean memory evaluation exists; longitudinal metrics remain |
| Owner control | Local/provider boundaries, labels, selective disclosure | Local core, structured sensitivity labels and explicit opt-in exist; document/provider policy expansion remains |
| Owner control | Review/correct/export/delete interfaces and portable formats | Core/API/CLI review, correction, export, deletion and restore exist; portable import remains |
| Owner control | Ingestion/access audit and connected-tool threat model | Not yet implemented |

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
7. Run all applicable quality gates, review public artifacts for private data, push the developed
   branch, and verify the remote commit and CI. Only then consider the full objective achieved.

Each implemented requirement needs direct tests or runnable evaluation evidence. A passing
unit suite does not by itself prove the entire roadmap. Docker execution, external integrations,
and hosted CI must be distinguished from local checks; unavailable checks are not marked passed.
