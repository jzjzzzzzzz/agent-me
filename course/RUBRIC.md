# Assessment and Capstone Rubric

[Course home](README.md) · [Capstone lesson](07-production-capstone/README.md) · [简体中文](translations/zh-CN/RUBRIC.md)

Score each dimension from 0 to 3. A portfolio-ready submission should score at least 18/24 with no
zero in correctness, verification, or security/privacy.

| Dimension | 0 — Missing | 1 — Beginning | 2 — Complete | 3 — Strong evidence |
| --- | --- | --- | --- | --- |
| Reproducibility | no setup evidence | runs on existing machine | clean documented setup passes | clean clone/container plus troubleshooting evidence |
| Conceptual accuracy | vague agent claims | names components | explains exact local scope | compares alternatives and rejects inflated claims |
| Contracts | shared/untyped state | types exist but invariants unclear | typed handoffs and public validation | safe migration with invalid-case tests |
| Grounding | answer-only demo | sources displayed | supported and blocked paths | measured retrieval/decision limitations |
| Verification | no automated checks | existing tests run | new focused tests and cases | failure injection proves checks catch regressions |
| Security/privacy | secrets or private data | generic warning | input limits, safe rendering, data boundary documented | threat model and negative authorization/abuse tests |
| Production reasoning | calls local app production-ready | lists missing features | ADR covers reliability and operations | implements and tests one production boundary |
| Communication | feature list | walkthrough without evidence | measured demo and accurate resume bullet | clear tradeoffs, limitations, and reproducible evidence |

## Required review evidence

Attach or link:

- commit SHA;
- tool versions or container image path;
- complete quality-gate output;
- behavioral evaluation results and case count;
- one approved and one blocked response;
- architecture diagram;
- ADR;
- capstone tests;
- limitations and next steps.

## Reviewer questions

1. Can the learner reproduce the result without hidden local state?
2. Can they identify the owner and enforcement of every important invariant?
3. Do metrics include scope and denominator?
4. Does the implementation fail safely when evidence is missing?
5. Are privacy and security boundaries specific rather than ceremonial?
6. Does portfolio wording claim only demonstrated properties?
