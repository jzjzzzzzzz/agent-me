# Course Design and Source References

Agent-Me is tutorial-first: the working application is the laboratory for a numbered learning path,
not a code dump followed by a short README.

## Repositories studied

The information architecture was informed by established, primary open-course repositories:

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): numbered
  lessons, per-lesson objectives and samples, multilingual navigation, and visible contribution paths;
- [Microsoft Generative AI for Beginners](https://github.com/microsoft/generative-ai-for-beginners):
  course table, setup lesson, learn/build distinction, and additional-learning sections;
- [Learn PyTorch for Deep Learning](https://github.com/mrdbourke/pytorch-deep-learning): explicit
  audience/prerequisites, code-first experiments, exercises, and milestone projects;
- [OSSU Computer Science](https://github.com/ossu/computer-science): clear curriculum scope,
  progression, time expectations, completion outcome, and community contribution model.

Agent-Me does not copy their content or imply affiliation. It adopts broadly useful educational
patterns and applies them to this repository's own implementation.

## Design principles

### Course before feature catalog

The root README sends new learners to a path, states prerequisites and time, and shows what they
will produce. Reference documentation remains available after the curriculum.

### One observable artifact per lesson

Every lesson ends with evidence: a passing baseline, response comparison, regression test, contract
change, trace record, evaluation matrix, or capstone ADR.

### Concepts before framework syntax

Lessons define retrieval, grounding, role boundaries, contracts, observability, evaluation, and
distributed reliability before asking learners to edit code.

### Precise claims

The course calls the implementation local, sequential, deterministic role-based orchestration. It
does not imply multiple models, autonomous workers, or production guarantees.

### Failure is part of learning

Learners deliberately reverse labels, send unsupported questions, and add malformed response
fixtures. A quality gate is trustworthy only after the learner sees it catch a failure.

### Multilingual with visible coverage

English is canonical. Simplified Chinese mirrors the complete curriculum. Additional project and UI
languages are supported, but the language table does not label incomplete lesson sets as complete.

### Contribution as a learning outcome

Issue forms, a lesson template, translation workflow, scoped checks, and pull-request evidence make
a first contribution approachable without lowering review quality.

## Lesson contract

Every maintained lesson contains:

1. navigation and language links;
2. time, level, and output;
3. why the topic matters;
4. learning objectives;
5. concepts or mental model;
6. source reading order;
7. a runnable lab;
8. required and optional exercises;
9. understanding questions;
10. completion checklist;
11. primary further reading.

`scripts/check_docs.py` verifies the English and Simplified Chinese lesson inventory, required
headings, and local links. Human review remains responsible for technical and translation accuracy.
