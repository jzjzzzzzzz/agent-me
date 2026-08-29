# Lesson 00 — Environment and the Evidence-First Learning Loop

[Course home](../README.md) · [简体中文](../translations/zh-CN/00-course-setup/README.md) · **Next: [Grounded Q&A](../01-grounded-qa/README.md)**

**Time:** 30–45 minutes · **Level:** Beginner · **Produces:** a reproducible baseline

## Why this lesson matters

Agent projects often fail before agent logic is involved: the corpus is mounted from the wrong
path, the frontend calls the wrong origin, dependencies drift, or a demonstration depends on an
unrecorded environment variable. If you change orchestration before proving the baseline, every
later failure has multiple possible causes.

This lesson establishes a scientific loop: **control the environment, run a known case, record the
result, change one variable, and rerun the same checks**.

## Learning objectives

By the end, you can:

- identify the course, runtime, test, and deployment directories;
- choose Docker or a local toolchain intentionally;
- explain what each quality command verifies;
- run the deterministic collaboration evaluation;
- separate a setup failure from an application-behavior failure.

## Mental model: four layers of evidence

| Layer | Question | Evidence in this repository |
| --- | --- | --- |
| Static quality | Is source structurally valid? | Ruff, ESLint, TypeScript |
| Unit behavior | Do isolated components preserve contracts? | Pytest and Vitest |
| Behavioral evaluation | Do representative questions reach expected outcomes? | `collaboration_cases.json` |
| Integrated runtime | Do built services communicate? | Compose health and smoke requests |

A green unit suite does not prove the container starts. A working browser demo does not prove
unsupported questions abstain. Keep the layers distinct.

## Repository tour

Read these files before running commands:

1. [`Makefile`](../../Makefile) — stable learner commands;
2. [`.env.example`](../../.env.example) — safe defaults and configuration surface;
3. [`docker-compose.yml`](../../docker-compose.yml) — service topology and health checks;
4. [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — the checks run on contributions;
5. [`course/fixtures/collaboration_cases.json`](../fixtures/collaboration_cases.json) — behavior expected by evaluation.

The public repository intentionally excludes production databases, analytics, private documents,
and secrets. Your clone should do the same.

## Hands-on lab

### Step 1 — Fork or clone

For course exercises, fork the repository so your commits remain visible in your own account. Then:

```bash
git clone https://github.com/<your-username>/agent-me.git
cd agent-me
git remote add upstream https://github.com/jzjzzzzzzz/agent-me.git
git switch -c learner/baseline
```

If you only want to read and run:

```bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
```

### Step 2 — Choose one setup path

#### Docker path

```bash
cp .env.example .env
docker compose config --quiet
docker compose up --detach --build --wait
```

Verify:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:5173/ >/dev/null
```

Stop cleanly:

```bash
docker compose down --volumes
```

#### Local toolchain path

Check prerequisites:

```bash
python3 --version
node --version
npm --version
git --version
```

Python must be 3.11 or newer and Node.js must be 20 or newer. Install and validate:

```bash
make setup
make lint
make test
make docs
make evaluate
```

Expected final line:

```text
COLLABORATION_EVAL 3/3 passed
```

### Step 3 — Understand each command

| Command | What it catches | What it does not prove |
| --- | --- | --- |
| `make lint` | Python lint/format, ESLint, TypeScript contract errors | runtime behavior |
| `make test` | backend and frontend component regressions | container wiring |
| `make docs` | missing local links and course structure errors | explanation accuracy |
| `make evaluate` | known grounded/unsupported decision regressions | broad real-world quality |
| `make build` | container build failures | deployment reliability |

### Step 4 — Record a baseline

Create `LEARNING_NOTES.md` in your fork (the upstream course does not require you to submit it):

```markdown
## Lesson 00
- Commit tested: `<git rev-parse --short HEAD>`
- Platform: `<OS, Python, Node, Docker>`
- Commands: `make lint`, `make test`, `make docs`, `make evaluate`
- Evaluation: `3/3 passed`
- One surprise: ...
```

Record results, not secrets or complete environment dumps.

## Read the implementation

Follow one baseline evaluation case:

1. the fixture is parsed in [`scripts/evaluate_collaboration.py`](../../scripts/evaluate_collaboration.py);
2. the knowledge directory is loaded by [`backend/app/knowledge.py`](../../backend/app/knowledge.py);
3. the roles run in [`backend/app/collaboration.py`](../../backend/app/collaboration.py);
4. expected and actual `grounded` decisions are compared;
5. a nonzero exit status tells CI that behavior changed.

Do not try to understand every line yet. The goal is to locate the boundaries.

## Exercises

### Required — prove the checker is real

Temporarily replace one expected value in
[`collaboration_cases.json`](../fixtures/collaboration_cases.json), run `make evaluate`, and verify:

- one case reports `FAIL`;
- the process exits nonzero (`echo $?` on macOS/Linux);
- restoring the file returns the suite to green.

Do not commit the intentional failure.

### Challenge — compare environments

Run the evaluation locally and inside the API container. Record any path or dependency difference.
If results differ, investigate before continuing.

## Common failures

### `make setup` cannot create the virtual environment

Confirm `python3 -m venv --help` works. On some Linux distributions the venv package is separate.
Remove a partially created `.venv` only after confirming it contains no work you need.

### Frontend cannot reach the API

Check `VITE_API_BASE_URL`, published ports, CORS origins, and `/health`. The default browser-facing API
is `http://localhost:8000`.

### Readiness reports zero documents

Confirm `KNOWLEDGE_DIR` points to the repository's `knowledge` directory and contains UTF-8 `.md`
files. The runtime resolves relative paths from its working directory.

### Docker port is already allocated

Set `API_PORT` or `WEB_PORT` in `.env`, then rerun `docker compose config` before startup.

## Check your understanding

1. Why is a browser screenshot weaker evidence than a repeatable evaluation command?
2. Which check validates TypeScript response parsing?
3. Why does `.env.example` belong in Git while `.env` does not?
4. What would you inspect first if tests pass locally but Compose readiness fails?
5. Why should an intentional failure be restored before the next lesson?

## Completion checklist

- [ ] I can identify the runtime, course, tests, fixtures, and CI workflow.
- [ ] I used either Docker or the local toolchain successfully.
- [ ] Lint, tests, docs, and evaluation pass.
- [ ] I observed a deliberate evaluation failure and restored it.
- [ ] I recorded tool versions and results without storing secrets.
- [ ] I can explain what the `3/3` result proves and what it does not prove.

## Further reading

- [Python virtual environments](https://docs.python.org/3/library/venv.html)
- [Docker Compose overview](https://docs.docker.com/compose/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)

---

**Next: [Lesson 01 — Grounded Q&A foundations](../01-grounded-qa/README.md)**
