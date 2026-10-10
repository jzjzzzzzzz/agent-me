# Personal Agent implementation and acceptance ledger

Tracking proposal: [#169](https://github.com/jzjzzzzzzz/agent-me/issues/169).
Scope: implement the [full AI Twin roadmap](../ROADMAP.md) through the independent Python
Agent core, authenticated adapters, and owner-facing CLI. No frontend changes are planned.
This ledger is not a release promise or a claim that the roadmap is complete.

## Acceptance requirements

| Workstream | Required behavior | Current evidence / remaining work |
| --- | --- | --- |
| Identity | Typed people, projects, organizations, events, ideas, preferences, decisions and relationships | Memory kinds exist; entities and relationships remain |
| Identity | Source, learned time, confidence, sensitivity and ownership | Source-linked revision snapshots and sensitivity labels exist; confidence/ownership and richer time remain |
| Identity | Correction, supersession, deletion and export | `memory.py`, lifecycle tests and memory evaluation; portable import remains |
| Learning | Explicitly approved document/project/conversation/event sources | `learning.py` registration/review; core/API/CLI approval tests |
| Learning | Candidate extraction before owner acceptance | `learning.py` exact field/paragraph candidates; `test_learning.py`; semantic inference remains out of scope |
| Learning | Deduplication, entity resolution, temporal conflict handling | Canonical exact deduplication, Unicode-equivalent key conflicts and same-kind/key review exist; entity/temporal resolution remain |
| Learning | Retention, forgetting and consolidation | Record/snapshot/origin deletion and replay-aware digest forgetting exist; retention/consolidation remain |
| Learning | Sensitive/identity-defining review policies | Every extracted candidate needs owner confirmation; sensitivity floor is enforced; richer policy configuration remains |
| Learning | Replayable traces and recoverable failure | `learning.py` atomic batches, durable failed/completed runs, stable retry IDs; concurrency/failure tests |
| Retrieval | Hybrid documents/memory and relationship-aware context | Public/private documents and memory coexist; unified retrieval contracts remain |
| Retrieval | Temporal selection and stale/disputed knowledge | Superseded exclusion exists; event time, expiry and disputes remain |
| Retrieval | Sensitivity-aware assembly and evidence sufficiency | Provider context is bounded; explicit sensitive-record disclosure exists; unified evidence policy remains |
| Retrieval | Factual, temporal, preference, project and relationship evaluation | Memory and collaboration suites exist; broader retrieval fixtures remain |
| Agency | Typed routing and explicit tool/data permissions | Not yet implemented |
| Agency | Plan/approval gates and inspectable calls/results | Not yet implemented |
| Agency | Idempotency, retry, rollback and clear know/recommend/act boundaries | Memory transactions exist; actual bounded tools remain |
| Verification | Atomic claim/evidence mapping and temporal consistency | Source/citation checks exist; structured personal claims remain |
| Verification | Fidelity, contradiction, correction, deletion and injection/privacy regressions | Lifecycle and preference cases exist; broader adversarial/longitudinal suite remains |
| Verification | Calibration, coverage, provenance and correction-effort metrics | Boolean memory evaluation exists; longitudinal metrics remain |
| Owner control | Local/provider boundaries, labels, selective disclosure | Local core, structured sensitivity labels and explicit opt-in exist; document/provider policy expansion remains |
| Owner control | Review/correct/export/delete interfaces and portable formats | Core/API/CLI review, correction, export, deletion and restore exist; portable import remains |
| Owner control | Ingestion/access audit and connected-tool threat model | Not yet implemented |

## Execution order

1. Versioned, independently runnable memory foundation (implemented, commit `2a1a2db`).
2. Approved-source learning, exact source excerpts, deduplication, replay-aware forgetting,
   explicit sensitivity boundaries, and a CLI usable without an HTTP server (implemented;
   `test_learning.py`, `test_learning_api.py`, `test_agent_cli.py`, `evaluate_learning.py`).
3. Structured identity/relationships, confidence and temporal retention semantics.
4. Unified personal retrieval, disputed/stale evidence and atomic grounded answers.
5. Typed contextual agency and real bounded tools with permissions and approval gates.
6. Portability/import, audit/threat-model coverage, longitudinal metrics, complete acceptance audit.
7. Run all applicable quality gates, review public artifacts for private data, push the developed
   branch, and verify the remote commit and CI. Only then consider the full objective achieved.

Each implemented requirement needs direct tests or runnable evaluation evidence. A passing
unit suite does not by itself prove the entire roadmap. Docker execution, external integrations,
and hosted CI must be distinguished from local checks; unavailable checks are not marked passed.
