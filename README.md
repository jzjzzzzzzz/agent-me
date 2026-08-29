<div align="center">

# Agent-Me

**Build a transparent, grounded question-answering agent from knowledge you control.**

A privacy-conscious open-source foundation with a typed FastAPI backend, a React interface, local document retrieval, and an optional OpenAI-compatible provider.

[Quick start](#quick-start) · [Multi-agent course](course/README.md) · [Architecture](docs/ARCHITECTURE.md) · [API reference](docs/API.md) · [Deployment](docs/DEPLOYMENT.md) · [Security](SECURITY.md)

[English](README.md) · [简体中文](docs/i18n/README.zh-CN.md) · [繁體中文](docs/i18n/README.zh-TW.md) · [日本語](docs/i18n/README.ja.md) · [한국어](docs/i18n/README.ko.md) · [Español](docs/i18n/README.es.md) · [Français](docs/i18n/README.fr.md) · [Deutsch](docs/i18n/README.de.md) · [Português](docs/i18n/README.pt-BR.md)

[![CI](https://github.com/jzjzzzzzzz/agent-me/actions/workflows/ci.yml/badge.svg)](https://github.com/jzjzzzzzzz/agent-me/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/jzjzzzzzzz/agent-me?display_name=tag)](https://github.com/jzjzzzzzzz/agent-me/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-4c1.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab.svg)](backend/pyproject.toml)
[![React](https://img.shields.io/badge/React-18-149eca.svg)](frontend/package.json)

</div>

---

## Overview

Agent-Me is a small, auditable foundation for publishing a Q&A agent over Markdown documents. It deliberately separates knowledge retrieval from answer generation:

- **Local extractive mode** works without an external model or API key.
- **Provider mode** sends only the retrieved context and recent conversation to an OpenAI-compatible endpoint that you configure.
- **Multi-agent lab mode** runs planner, researcher, critic, and writer roles with typed handoffs and an inspectable operational trace.
- Every response can include the document excerpts used as grounding sources.

This public repository contains reusable application code only. It does not contain a production database, private memory, analytics records, credentials, or deployment secrets.

## Why Agent-Me?

| Capability | Included |
| --- | --- |
| Knowledge source | Markdown files you can review and version |
| Retrieval | Deterministic local search with source excerpts |
| Generation | Optional OpenAI-compatible provider |
| Collaboration | Local planner → researcher → critic → writer workflow |
| Backend | Typed FastAPI routes and strict request schemas |
| Frontend | React, safe text rendering, responsive design |
| Languages | Automatic locale detection and 9 interface languages |
| Operations | Health/readiness endpoints, Docker Compose, CI |
| Quality | Backend/frontend tests, linting, type checking |
| Security | Input limits, no HTML injection, secrets kept outside Git |

Agent-Me is intentionally focused. It is a strong base for a personal knowledge agent, documentation assistant, portfolio Q&A, internal handbook, or product-support prototype without introducing a large orchestration framework.

## Architecture

~~~mermaid
flowchart LR
  User[Browser] --> Web[React interface]
  Web -->|POST /api/v1/chat| API[FastAPI service]
  Web -->|POST /api/v1/collaborate| Flow[Role orchestrator]
  API --> Search[Local document retrieval]
  Flow --> Search
  Flow --> Roles[Planner → Researcher → Critic → Writer]
  Search --> Docs[(Markdown knowledge)]
  API -. optional .-> Provider[OpenAI-compatible provider]
  API -->|answer, mode, sources| Web
  Flow -->|answer, sources, trace| Web
~~~

Request flow:

1. The API validates the question and conversation history.
2. The retriever ranks relevant Markdown excerpts.
3. Extractive mode returns the strongest grounded excerpt directly.
4. Provider mode submits limited retrieved context to your configured endpoint.
5. Multi-agent lab mode passes typed artifacts through four local roles and lets the critic block unsupported synthesis.
6. The browser renders answers, sources, and operational traces as plain text.

See the full [architecture guide](docs/ARCHITECTURE.md).

## Quick start

### Docker Compose

**Prerequisite:** Docker with the Compose plugin.

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

Open:

- Web application: <http://localhost:5173>
- Interactive API documentation: <http://localhost:8000/docs>
- Health endpoint: <http://localhost:8000/health>
- Readiness endpoint: <http://localhost:8000/ready>

Local extractive mode is enabled by default, so the first run does not require an API key.

### Local development

**Prerequisites:** Python 3.11+, Node.js 20+, and npm.

~~~bash
make setup
make lint
make test
make docs
make evaluate
make build
~~~

Run the services separately when developing:

~~~bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload
cd frontend
npm run dev
~~~

## Make it yours

1. Replace <code>knowledge/example-profile.md</code> with Markdown you are allowed to use.
2. Set <code>APP_NAME</code> and <code>APP_DESCRIPTION</code> in your local <code>.env</code>.
3. Keep local extractive mode, or configure an OpenAI-compatible provider.
4. Review source excerpts and tune your knowledge content before publishing.
5. Put production secrets in your hosting platform's secret manager—not in Git.

Example provider configuration:

~~~dotenv
LLM_BASE_URL=https://provider.example/v1
LLM_API_KEY=replace-with-a-secret
LLM_MODEL=replace-with-a-model-id
~~~

## API example

~~~bash
curl http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}'
~~~

~~~json
{
  "answer": "For project planning, the example agent starts with user goals...",
  "mode": "extractive",
  "sources": [
    {
      "title": "Example profile",
      "path": "example-profile.md",
      "excerpt": "For project planning...",
      "score": 0.5
    }
  ]
}
~~~

See the [API reference](docs/API.md) for request limits, schemas, and response fields.

## Hands-on multi-agent course

The repository includes a detailed, runnable learning path rather than a diagram-only
“multi-agent” claim. It covers typed role handoffs, critic gating, browser traces, deterministic
evaluations, failure injection, a verifier-role extension, production design, and defensible resume
wording.

- [English course](course/README.md)
- [简体中文课程](course/README.zh-CN.md)

The default workflow is local and sequential in one process. It is intentionally described as
role-based multi-agent orchestration—not as multiple models, autonomous processes, or a distributed
agent platform.

## Configuration

The complete template is in [.env.example](.env.example).

| Variable | Purpose | Default |
| --- | --- | --- |
| <code>API_BIND</code> / <code>WEB_BIND</code> | Compose host bindings; loopback by default | <code>127.0.0.1</code> |
| <code>API_PORT</code> / <code>WEB_PORT</code> | Local published ports | <code>8000</code> / <code>5173</code> |
| <code>APP_NAME</code> | Public service name | <code>Agent-Me Starter</code> |
| <code>APP_DESCRIPTION</code> | Public service description | Starter description |
| <code>KNOWLEDGE_DIR</code> | Markdown knowledge directory, relative to the process working directory or absolute | <code>knowledge</code> |
| <code>MAX_QUESTION_CHARS</code> | Question length limit | <code>8000</code> |
| <code>MAX_DOCUMENT_BYTES</code> | Maximum UTF-8 size of one Markdown file | <code>1000000</code> |
| <code>MAX_HISTORY_CHARS</code> | Maximum total characters in submitted chat history | <code>24000</code> |
| <code>MAX_ANSWER_CHARS</code> | Maximum accepted provider answer size | <code>50000</code> |
| <code>MAX_REQUEST_BODY_BYTES</code> | Maximum HTTP request-body size before JSON parsing | <code>262144</code> |
| <code>PROVIDER_TIMEOUT_SECONDS</code> | Upstream provider timeout | <code>60</code> |
| <code>LLM_BASE_URL</code> | Optional OpenAI-compatible base URL | empty |
| <code>LLM_API_KEY</code> | Optional provider secret | empty |
| <code>LLM_MODEL</code> | Optional provider model ID | empty |
| <code>VITE_API_BASE_URL</code> | Browser-facing API URL | <code>http://localhost:8000</code> |

## Internationalization

The web interface supports:

- English
- 简体中文
- 繁體中文
- 日本語
- 한국어
- Español
- Français
- Deutsch
- Português (Brasil)

The initial language follows the browser locale. A manual selection is stored locally and English is the fallback. The localization layer is dependency-free and type-checked so every locale must implement every message key.

Read [localization guidance](docs/LOCALIZATION.md) before adding or updating a language.

## Project structure

~~~text
agent-me/
├── backend/             FastAPI application and backend tests
├── frontend/            React application and frontend tests
├── course/              Bilingual hands-on labs and evaluation fixtures
├── knowledge/           Versioned Markdown knowledge
├── docs/                API, architecture, deployment, localization
├── .github/             CI, dependency updates, contribution templates
├── docker-compose.yml   Local production-shaped stack
└── .env.example         Safe configuration template
~~~

## Security and privacy

- Treat prompts and knowledge files as untrusted input.
- The frontend renders returned content as text, not raw HTML.
- Request schemas, semantic input limits, and a streaming HTTP body-size limit are enforced server-side.
- Extractive mode does not transmit questions or documents to a model provider.
- Multi-agent lab mode is deterministic and local; it does not call a provider.
- Provider mode transmits retrieved context, the question, and recent history to the endpoint you choose.
- Chat content and analytics are not persisted by this starter.
- Never publish secrets, private communications, regulated data, or personal information in the knowledge directory.
- Review your provider's retention and data-processing terms before enabling provider mode.

Report vulnerabilities through the process in [SECURITY.md](SECURITY.md), not through a public issue.

## Documentation

- [API reference](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Hands-on multi-agent course](course/README.md)
- [Multi-Agent 协作实操课程](course/README.zh-CN.md)
- [Deployment guide](docs/DEPLOYMENT.md)
- [Localization guide](docs/LOCALIZATION.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## Contributing

Issues and pull requests are welcome. Before contributing:

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Keep changes focused and add tests for behavior changes.
3. Run <code>make lint</code>, <code>make test</code>, <code>make docs</code>, <code>make evaluate</code>, and <code>make build</code>.
4. Use GitHub Security Advisories for security reports.

Translations are maintained by contributors. English documentation is canonical when translations temporarily differ.

## Related project

Need an OpenAI-compatible endpoint whose answers are written by authorized people through a shared queue? See [Human API](https://github.com/jzjzzzzzzz/human-api).

## License

Agent-Me is available under the [MIT License](LICENSE).
