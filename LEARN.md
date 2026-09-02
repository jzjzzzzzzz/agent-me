<div align="center">

# Learn Agent-Me by Building It

**A step-by-step path from deterministic retrieval to an evaluated multi-agent capstone.**

[English](LEARN.md) · [简体中文](LEARN.zh-CN.md) · [Full syllabus](course/README.md) · [Ask for help](https://github.com/jzjzzzzzzz/agent-me/discussions/categories/q-a)

</div>

## How the curriculum uses the reference implementation

Agent-Me is an open-source reference implementation for auditable multi-agent RAG systems. This
free, runnable engineering curriculum rebuilds the same system in small, testable increments instead
of copying an opaque final demo. The core path works without a paid model API and keeps retrieval,
orchestration, evaluation, and privacy boundaries visible in the source code.

By the end, you will be able to:

- implement deterministic retrieval over a reviewable Markdown corpus;
- define planner, researcher, critic, and writer responsibilities;
- pass immutable typed artifacts between roles;
- distinguish an operational trace from hidden chain-of-thought;
- make unsupported questions abstain instead of inventing evidence;
- write behavioral evaluations and failure-injection tests;
- explain the difference between a local orchestration demo and a distributed production system;
- present a measured, reproducible capstone in a portfolio or technical interview.

## Before you begin

You need Git, Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/)
0.11 or 0.12, Node.js 22+, and npm. Docker with Compose is optional but recommended.
You do **not** need an API key for the extractive or collaboration labs.

Fork the repository if you want your work to remain visible on your GitHub profile, then clone your
fork. Otherwise, clone this repository directly:

```bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
make setup
```

Establish a known-good baseline before changing code:

```bash
make lint
make test
make docs
make evaluate
```

The final command should print:

```text
COLLABORATION_EVAL 4/4 passed
```

## Build the project in eight checkpoints

Do the checkpoints in order if this is your first agent project. Each lesson contains a mental
model, a source-code tour, a guided lab, exercises, verification commands, interview questions,
and a completion checklist.

### 1. Reproduce the baseline

Open [Lesson 00](course/00-course-setup/README.md). Run both services, call the health and readiness
routes, and save the quality-gate output in your own project notes.

**Evidence to keep:** the exact commands, your runtime versions, and the passing test summary.

### 2. Separate retrieval from answer generation

Open [Lesson 01](course/01-grounded-qa/README.md). Trace one supported and one unsupported question
through the single-path Q&A route. Compare extractive mode with optional provider mode without
confusing fluent output with grounded output.

**Evidence to keep:** one response with sources and one deliberate abstention.

### 3. Build and challenge the retriever

Open [Lesson 02](course/02-retrieval/README.md). Follow document loading, chunking, scoring, ranking,
and evidence packaging. Add a small Markdown fact and a regression test that retrieves it.

**Evidence to keep:** a failing test before the change and a passing test after it.

### 4. Decompose work by responsibility

Open [Lesson 03](course/03-role-design/README.md). Compare the direct answer path with the
planner → researcher → critic → writer workflow. Explain what each role owns and why extra roles
would not automatically improve the system.

**Evidence to keep:** a responsibility table and one example of a boundary you would not merge.

### 5. Make handoffs typed and inspectable

Open [Lesson 04](course/04-typed-orchestration/README.md). Read the immutable artifacts, follow their
construction order, and add one safe observable field without passing an untyped dictionary through
the workflow.

**Evidence to keep:** the contract change, tests, and a sample serialized response.

### 6. Add a critic gate and safe observability

Open [Lesson 05](course/05-critic-observability/README.md). Observe approved and blocked paths in the
browser. Verify that the trace reports operational stages and decisions without exposing private
reasoning or executing retrieved content.

**Evidence to keep:** screenshots or response excerpts for both paths, with private data removed.

### 7. Replace demo confidence with evaluation

Open [Lesson 06](course/06-evaluation/README.md). Add a supported or unsupported case, make the
evaluator fail on purpose, then fix the behavior. Run the complete quality gate again.

**Evidence to keep:** the versioned case, observed failure, fix, and passing CI link.

### 8. Ship a capstone you can defend

Open [Lesson 07](course/07-production-capstone/README.md). Choose one scoped extension, write its
acceptance criteria first, implement it, and assess it with the [rubric](course/RUBRIC.md). Document
limits honestly—especially concurrency, durability, tenant isolation, and provider privacy.

**Evidence to keep:** architecture decision, pull request, CI result, demo, evaluation result, and a
short explanation of trade-offs.

## Run the production-shaped local stack

At any checkpoint, you can verify the integrated application with Docker Compose:

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- application: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- health: <http://localhost:8000/health>
- readiness: <http://localhost:8000/ready>

Stop the stack with `docker compose down`.

## Turn the work into a portfolio case study

Do not describe the repository only as “a multi-agent chatbot.” Record evidence that another
engineer can verify:

1. **Problem:** what grounded question-answering failure you addressed.
2. **Architecture:** why the chosen roles and typed handoffs exist.
3. **Measurement:** which evaluation cases and thresholds define success.
4. **Failure handling:** how unsupported questions, invalid input, and provider failures behave.
5. **Operations:** what remains process-local and what production distribution would require.
6. **Reproduction:** exact setup, test, and demo commands.

A precise portfolio statement is stronger than an inflated one:

> Built and evaluated a typed, role-based Q&A workflow with deterministic retrieval, critic-gated
> abstention, safe operational traces, React/FastAPI contract tests, and Docker-based reproduction.

## Get help or contribute

- Use [Q&A Discussions](https://github.com/jzjzzzzzzz/agent-me/discussions/categories/q-a) for setup,
  lesson, and design questions.
- Use [Show and tell](https://github.com/jzjzzzzzzz/agent-me/discussions/categories/show-and-tell)
  to share a fork, capstone, evaluation result, or learning note.
- Use [Issues](https://github.com/jzjzzzzzzz/agent-me/issues) for reproducible bugs and scoped work.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Remove secrets, personal records, private prompts, and proprietary documents from logs, screenshots,
fixtures, knowledge files, and discussion posts. See [SECURITY.md](SECURITY.md) for private security
reporting.
