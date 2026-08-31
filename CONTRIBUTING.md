# Contributing to Agent-Me

Thank you for improving the course or reference implementation. Contributions from first-time
learners, educators, translators, frontend/backend engineers, security reviewers, and operators are
welcome.

By participating, follow the [Code of Conduct](CODE_OF_CONDUCT.md). By submitting a contribution,
you agree that it is licensed under the repository's [MIT License](LICENSE).

## Start with the right channel

| Need | Channel |
| --- | --- |
| Reproducible software bug | [Bug report](https://github.com/jzjzzzzzzz/agent-me/issues/new?template=bug.yml) |
| Confusing lesson or exercise | [Course feedback](https://github.com/jzjzzzzzzz/agent-me/issues/new?template=course.yml) |
| New feature or role design | [Feature proposal](https://github.com/jzjzzzzzzz/agent-me/issues/new?template=feature.yml) |
| New or corrected translation | [Translation issue](https://github.com/jzjzzzzzzz/agent-me/issues/new?template=translation.yml) |
| Security vulnerability | Private process in [SECURITY.md](SECURITY.md), never a public issue |
| Setup question | Search Issues first; open course feedback with sanitized diagnostics |

Do not put credentials, `.env` contents, private documents, production prompts, personal records,
security exploit details, or database dumps in an issue or pull request.

## Good first contributions

A useful contribution does not need to be large:

- correct one unclear paragraph and explain why it confused learners;
- add a missing expected-output example;
- reproduce and fix a broken command on a supported platform;
- add one retrieval or response-parser regression test;
- add a justified supported/unsupported evaluation case;
- improve keyboard, screen-reader, contrast, or small-screen behavior;
- review and correct one translated lesson;
- add a troubleshooting entry backed by a reproduction.

Search existing issues and comment before duplicating work. For significant behavior, curriculum,
public schema, dependency, or architecture changes, open an issue before implementing.

## Development workflow

### 1. Fork and configure remotes

```bash
git clone https://github.com/<your-username>/agent-me.git
cd agent-me
git remote add upstream https://github.com/jzjzzzzzzz/agent-me.git
git fetch upstream
git switch -c docs/clear-lesson-02 upstream/main
```

Use a descriptive branch such as `fix/retrieval-heading`, `docs/lesson-04-contracts`, or
`i18n/ja-course-00`.

### 2. Install

Local toolchain:

```bash
uv --version  # supported range: 0.11.x or 0.12.x
make setup
```

`make setup`, CI, and the backend image all enforce `backend/uv.lock`. When intentionally changing
Python dependencies, edit `backend/pyproject.toml`, run `make lock`, review the complete lock diff,
then run the full gate. Do not hand-edit `uv.lock` or merge a manifest change without its lock
update.

Or use the repository's Docker Compose path:

```bash
cp .env.example .env
docker compose up --build
```

### 3. Make one focused change

- preserve existing architecture unless the issue explains a broader migration;
- add tests for behavior changes;
- update docs when commands, contracts, UI, configuration, or guarantees change;
- use the [lesson template](course/LESSON_TEMPLATE.md) for new course content;
- keep examples deterministic and runnable without paid services when possible;
- never weaken a security check only to make a demo pass.

### 4. Run scoped checks while developing

Backend:

```bash
.venv/bin/ruff check backend scripts
.venv/bin/ruff format --check backend scripts
.venv/bin/pytest -q backend/tests
```

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Course and evaluation:

```bash
make docs
make evaluate
```

### 5. Run the complete gate before a pull request

```bash
make lint
make test
make docs
make evaluate
make build
```

If Docker is unavailable, state that clearly in the pull request. Do not mark a check as passed
unless you ran it successfully.

### 6. Commit clearly

Prefer small commits with an imperative subject:

```text
docs: clarify retrieval precision exercise
test: cover duplicate collaboration stages
feat: add typed verifier artifact
fix: preserve headings during chunking
i18n: translate lesson 00 to Japanese
```

Do not create artificial empty commits or split one inseparable change only to increase commit
count. Reviewers should be able to understand and revert each commit.

### 7. Open the pull request

Complete every applicable section of the template. Include:

- problem and scope;
- screenshots only when UI changes require them;
- exact commands and summarized output;
- behavior before/after;
- security/privacy impact;
- compatibility or migration impact;
- translation status;
- known limitations.

A maintainer may request smaller scope, new tests, wording changes, or a design issue before merge.

## Change-specific requirements

### Backend behavior

- use typed request/response models;
- reject unknown request fields where the current API does;
- enforce limits before expensive work;
- keep server-controlled IDs and status fields server-controlled;
- test success, malformed, boundary, and failure paths;
- avoid logging request bodies or secrets.

### Public API contracts

When a collaboration response changes, update together:

1. internal artifact if relevant;
2. Pydantic schema;
3. route serialization;
4. TypeScript type;
5. runtime response parser;
6. backend and frontend valid/invalid tests;
7. UI and documentation;
8. workflow/version compatibility decision.

### Frontend

- treat API text as untrusted;
- render plain text rather than unsafe HTML;
- preserve keyboard access and visible focus;
- add tests for loading, success, empty, error, and malformed-response states;
- keep all locale dictionaries type-complete.

### Evaluation cases

An evaluation case must:

- use a unique, stable ID;
- contain public synthetic/example content, not a real private conversation;
- justify the expected label from committed knowledge;
- add a category the suite needs or preserve a known regression;
- avoid being rewritten merely to match current output.

In the pull request, name the category and source paragraph that justifies the expectation.

## Contribute a lesson

Use [`course/LESSON_TEMPLATE.md`](course/LESSON_TEMPLATE.md). A maintained lesson needs:

- navigation and language links;
- time, level, and observable output;
- engineering motivation;
- explicit learning objectives;
- conceptual model and limitations;
- ordered source-reading guide;
- commands tested from a documented directory;
- expected results and what they prove;
- at least one required exercise;
- understanding questions and completion checklist;
- primary documentation or paper references.

Do not add a lesson that is only a feature description, long code dump, or collection of external
links. Commands and internal links are checked by CI; technical accuracy still requires review.

## Translate the course

Language coverage is tracked in [`course/LANGUAGES.md`](course/LANGUAGES.md).

### Directory layout

Full courses use:

```text
course/translations/<locale>/README.md
course/translations/<locale>/00-course-setup/README.md
...
course/translations/<locale>/07-production-capstone/README.md
course/translations/<locale>/GLOSSARY.md
course/translations/<locale>/RUBRIC.md
```

Use a BCP 47-style locale already used by the project (`zh-CN`, `pt-BR`, and so on).

### Translation rules

- preserve commands, file paths, identifiers, JSON fields, and code semantics;
- translate explanation and navigation, not code syntax;
- verify every relative link from the translated file;
- preserve warnings, limitations, and precise scope claims;
- do not add private examples or credentials;
- state whether translation was human-written, machine-assisted, and human-reviewed;
- do not mark a language complete until all 8 lessons, syllabus, glossary, and rubric pass review;
- when English behavior changes, update affected maintained translations in the same PR when
  practical, or open a linked translation issue.

Machine assistance is allowed, but raw unreviewed output is not treated as a maintained translation.
A fluent translation that changes a command or guarantee is a bug.

## Documentation style

- lead with the problem and learning outcome;
- use short paragraphs and descriptive headings;
- define specialized terms on first use;
- distinguish implemented behavior from proposed architecture;
- state expected commands/output and limitations;
- prefer repository-relative links for local files;
- prefer primary official documentation and research papers;
- use inclusive, direct language;
- do not copy protected course content from another repository.

## Review checklist

Before requesting review:

- [ ] The issue and pull request contain no secrets or private data.
- [ ] Scope is focused and commits are understandable.
- [ ] Behavior changes have focused tests.
- [ ] Public Python/TypeScript contracts are synchronized.
- [ ] New course commands were actually run.
- [ ] Local Markdown links pass `make docs`.
- [ ] Evaluation still passes and new labels are justified.
- [ ] UI changes are keyboard-usable and safely render text.
- [ ] Security, privacy, compatibility, and migration impact are described.
- [ ] Translation coverage/status is honest.
- [ ] `make lint`, `make test`, `make docs`, and `make evaluate` pass.
- [ ] Container build was run, or the reason it was unavailable is stated.

## Reporting security issues

Do not open a public issue for a suspected vulnerability. Follow [SECURITY.md](SECURITY.md). Include
a minimal reproduction without real credentials or user data. Maintainers will coordinate disclosure.
