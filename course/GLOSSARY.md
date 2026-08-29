# Agent-Me Course Glossary

[Course home](README.md) · [简体中文词汇表](translations/zh-CN/GLOSSARY.md)

These definitions describe how terms are used in this repository. Broader literature may use them
differently; state your meaning when presenting the project.

| Term | Meaning in Agent-Me | Common misunderstanding |
| --- | --- | --- |
| Agent | A role with a responsibility, typed input, and typed output | Any function with a persona name |
| Multi-agent orchestration | An orchestrator coordinates several explicit role handoffs | Necessarily multiple models or machines |
| Artifact | Immutable data produced by one role for a later stage | Shared mutable scratch state |
| Corpus | The Markdown documents available to retrieval | All information known by a model |
| Chunk | A normalized block considered independently by retrieval | Always a fixed token window |
| Retrieval | Selection and ranking of candidate evidence | Answer generation |
| Match | A document, excerpt, and retrieval score | Proof that the excerpt answers the question |
| Grounded | At least one match passed the current approval rule | Guaranteed truth or full entailment |
| Abstention | Returning an explicit insufficient-evidence result | A server crash |
| Citation | A source path associated with an answer | Automatic proof of sentence-level support |
| Critic gate | A policy stage that approves or blocks synthesis | An infallible safety detector |
| Operational trace | Safe stages, outcomes, counts, and summaries | Private chain-of-thought |
| Contract | Fields, types, invariants, and behavior relied on across a boundary | Documentation alone |
| Idempotency | Repeating an operation with the same key does not create a second effect | Exactly-once message delivery |
| At-least-once delivery | Work may be delivered more than once and must tolerate duplicates | Every job executes once |
| Backpressure | Limiting admitted or concurrent work to protect capacity | Retrying faster |
| Evaluation case | Versioned input and human-justified expected behavior | A random demo prompt |
| Precision | Fraction of predicted positive outcomes that were expected positive | Overall accuracy |
| Recall | Fraction of expected positive outcomes predicted positive | Citation count |
| Regression | Previously expected behavior no longer holds | Any intentional behavior change |
| Provider mode | Optional generation through a configured OpenAI-compatible endpoint | Built-in provider endorsement |
| Production-ready | A claim requiring workload-specific reliability, security, operations, and evidence | “It works locally” |
