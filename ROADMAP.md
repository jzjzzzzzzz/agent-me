# Agent-Me Roadmap

## Toward a continuously learning AI Twin

Agent-Me is building an AI Twin: a persistent, evidence-grounded representation that can learn from a person's knowledge, projects, conversations, decisions, preferences, and experiences over time.

The destination is not a chatbot that merely sounds like its owner. It is a system that can increasingly work with the owner's context while remaining attributable, uncertain when appropriate, private, correctable, and inspectable.

This roadmap describes direction, not release promises. Proposed capabilities become part of Agent-Me only when their behavior, trust boundary, and evaluation method are explicit.

## Design principles

Every roadmap contribution should preserve these principles:

1. **The owner stays in control.** Learning, retention, correction, export, and deletion must have clear user controls.
2. **Memory has provenance.** A personal claim should retain where it came from, when it was learned, and how confidently it is held.
3. **Learning is not silent accumulation.** Ingestion requires boundaries, review, deduplication, conflict handling, and forgetting.
4. **Important decisions are inspectable.** Public traces expose evidence, tool activity, stage outcomes, and verification results—not private chain-of-thought.
5. **Uncertainty is a feature.** The twin should distinguish known, inferred, disputed, outdated, and unknown information.
6. **Progress is evaluated.** New capability needs supported, unsupported, adversarial, privacy, and temporal test cases.
7. **The architecture stays understandable.** Prefer typed contracts and bounded components over hidden behavior or unnecessary complexity.

## Current foundation

The repository currently provides:

- reviewable, version-controlled Markdown as the personal knowledge source;
- bounded deterministic retrieval with exact source excerpts;
- Planner, Researcher, Critic, Writer, and optional Verifier roles;
- typed handoffs between agent stages;
- evidence-sufficiency and citation-path checks;
- sources, grounding status, safe public execution traces, and run IDs;
- deterministic evaluation fixtures; and
- a runnable FastAPI + React application powering John Zhou's AI Twin.

Current boundaries are equally important: conversations are not persisted, the knowledge source is not yet a structured identity store, continuous ingestion is not implemented, and the Verifier does not prove factual truth or semantic entailment.

## Workstreams

### 1. Structured identity and memory

Move from a collection of documents toward explicit, source-linked personal knowledge.

Proposed work includes:

- typed entities for people, projects, organizations, events, ideas, preferences, and decisions;
- relationships between entities without requiring one fixed graph backend;
- episodic, semantic, and preference memory boundaries;
- source, timestamp, confidence, sensitivity, and ownership metadata;
- correction, supersession, deletion, and export semantics; and
- compatibility between structured records and existing Markdown knowledge.

**Completion signal:** the twin can explain what it believes about a person, where that belief came from, and whether it is current or disputed.

### 2. Continuous learning pipeline

Build controlled learning over time rather than silently storing every interaction.

Proposed work includes:

- opt-in ingestion from approved documents, projects, conversations, and events;
- extraction into reviewable candidate memories before acceptance;
- deduplication and entity resolution;
- temporal updates and conflict detection;
- configurable retention, forgetting, and memory consolidation;
- human approval policies for sensitive or identity-defining memories; and
- replayable ingestion traces and failure recovery.

**Completion signal:** new information can update the twin predictably without erasing provenance, accumulating duplicates, or overwriting conflicting history.

### 3. Retrieval over personal context

Retrieve the right mixture of facts, episodes, preferences, decisions, and relationships.

Proposed work includes:

- hybrid retrieval over documents and structured memory;
- temporal and relationship-aware retrieval;
- sensitivity-aware context assembly;
- evidence sufficiency and contradiction detection; and
- retrieval evaluation beyond simple lexical overlap.

**Completion signal:** retrieval quality can be measured across factual, temporal, preference, project, and relationship questions.

### 4. Contextual agency and tools

Allow the twin to help with bounded tasks while keeping actions attributable and reversible.

Proposed work includes:

- typed intent routing;
- explicit tool permissions and per-tool data boundaries;
- plan and approval gates for consequential actions;
- inspectable tool calls and results;
- idempotency, retry, and rollback behavior; and
- separation between what the twin knows, recommends, and is allowed to do.

**Completion signal:** every action can be traced to an intent, plan, permission, tool result, and owner-visible outcome.

### 5. Verification and longitudinal evaluation

Evaluate whether the AI Twin remains faithful and useful as its memory changes.

Proposed work includes:

- atomic claim-to-evidence verification;
- temporal consistency and stale-memory cases;
- preference fidelity without rigid personality imitation;
- contradiction, correction, and deletion tests;
- privacy leakage and prompt-injection cases;
- regression suites for memory and tool behavior; and
- longitudinal measures for calibration, coverage, provenance, and user correction effort.

**Completion signal:** improvements can be demonstrated with repeatable evidence rather than subjective conversations alone.

### 6. Privacy, portability, and owner control

Treat personal context as user-controlled data, not an incidental prompt cache.

Proposed work includes:

- local-first and provider-boundary documentation;
- sensitivity labels and selective disclosure;
- review, correction, export, and deletion interfaces;
- portable memory formats;
- audit records for ingestion and access; and
- threat models for personal knowledge and connected tools.

**Completion signal:** an owner can understand, move, correct, and remove what the twin knows without depending on opaque internal state.

## How to contribute

Contributions are welcome across code, research, design, evaluation, documentation, and security.

Good starting points include:

- propose a small typed memory schema with provenance and correction semantics;
- add an adversarial, temporal, contradiction, or deletion evaluation case;
- design a reviewable candidate-memory ingestion flow;
- improve evidence and execution-trace presentation;
- document a concrete privacy or threat-model boundary;
- prototype a bounded tool contract with explicit permissions; or
- improve the current retrieval, verification, tests, accessibility, or documentation.

Before implementing a substantial workstream item:

1. Search existing issues and discussions.
2. Open a [feature proposal](https://github.com/jzjzzzzzzz/agent-me/issues/new?template=feature.yml).
3. Define the user problem, current boundary, proposed contract, privacy impact, and evaluation plan.
4. Keep the first pull request focused and independently testable.
5. Follow [CONTRIBUTING.md](CONTRIBUTING.md) and run the documented quality gates.

Roadmap proposals do not need to introduce a large dependency or a new agent. A precise schema, test case, threat model, or failure analysis can move the project forward substantially.

## What success looks like

Agent-Me should become more useful as it learns more about its owner—but also more accountable, not less.

The long-term test is not whether it can imitate a person convincingly. It is whether the owner can ask:

- What do you know about me?
- Where did that come from?
- When did it change?
- What are you uncertain about?
- Why did you answer or act this way?
- Can I correct or delete it?

and receive clear, inspectable answers.
