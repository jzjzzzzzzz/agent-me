# Lesson 01 — Grounded Q&A Foundations

[Previous: Setup](../00-course-setup/README.md) · [Course home](../README.md) · [简体中文](../translations/zh-CN/01-grounded-qa/README.md) · [Next: Retrieval](../02-retrieval/README.md)

**Time:** 45–60 minutes · **Level:** Beginner · **Produces:** an evidence-flow map

## Why this lesson matters

A fluent answer is not automatically a supported answer. A grounded system first finds evidence in
a defined corpus, then constrains what it returns or generates. This creates inspectable failure
modes: no evidence, weak evidence, irrelevant evidence, or an answer that exceeds the evidence.

Agent-Me exposes the retrieval result so you can reason about these failures instead of treating a
model response as the only artifact.

## Learning objectives

By the end, you can:

- define corpus, chunk, retrieval, grounding, generation, citation, and abstention;
- trace the standard chat request from HTTP validation to source excerpts;
- distinguish extractive mode from optional provider mode;
- state what the current `grounded` signal proves and does not prove;
- test a supported and unsupported question without a paid provider.

## Mental model: retrieval and generation are separate

```text
question ──▶ normalize/validate ──▶ retrieve chunks ──▶ decide evidence ──▶ answer
                                      │                    │
                                      ▼                    └── abstain when unsupported
                                 ranked sources
```

**Retrieval** selects candidate evidence. **Generation** turns evidence into an answer. Even when a
single API call appears to do both, they have different quality measures:

| Stage | Useful measures | Example failure |
| --- | --- | --- |
| Retrieval | recall, precision, ranking quality | the relevant paragraph is not returned |
| Evidence decision | coverage, thresholds, policy | one shared word is mistaken for support |
| Generation | faithfulness, completeness, clarity | the answer adds facts absent from sources |
| Citation | source accuracy, granularity | citation exists but does not support the sentence |

The local extractive path avoids generative variation by returning the strongest excerpt. It is a
teaching baseline, not proof that extractive answers are always sufficient.

## Modes in Agent-Me

### Local extractive mode

When no provider is configured:

1. the API searches local Markdown;
2. the best excerpt becomes the answer;
3. ranked source objects are returned;
4. no external model service receives the question or documents.

### OpenAI-compatible provider mode

When `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` are configured:

1. retrieval still happens locally;
2. limited source context and recent history are assembled;
3. the provider generates an answer;
4. the complete streamed response is bounded by `MAX_PROVIDER_RESPONSE_BYTES` before JSON parsing,
   then answer text is bounded by `MAX_ANSWER_CHARS`;
5. source excerpts remain visible to the caller.

Sampling settings cannot repair missing retrieval evidence. Provider mode also changes the privacy
boundary because selected context leaves the local process.

## Read the implementation

Read in this order:

1. [`ChatRequest` and `ChatResponse`](../../backend/app/schemas.py) — public contract;
2. [`chat`](../../backend/app/main.py) — orchestration at the HTTP boundary;
3. [`KnowledgeBase.search`](../../backend/app/knowledge.py) — evidence selection;
4. [`OpenAICompatibleProvider`](../../backend/app/provider.py) — optional generation boundary;
5. [`ask`](../../frontend/src/api.ts) — browser request and runtime response parsing.

While reading, write down who owns each field. The server owns answer mode and source records; the
caller supplies only the question and permitted history.

## Hands-on lab

### Step 1 — Start the API

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

### Step 2 — Inspect the corpus

Read [`knowledge/example-profile.md`](../../knowledge/example-profile.md). Before calling the API,
predict which paragraph should match:

```text
How does the example agent plan a project?
```

### Step 3 — Call the standard route

```bash
curl --silent http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
```

Identify:

- `answer`;
- `mode`;
- source `path`;
- source `excerpt`;
- source `score`.

### Step 4 — Call the collaboration route

```bash
curl --silent http://localhost:8000/api/v1/collaborate \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
```

Both paths use local retrieval. The collaboration response adds a decision and role trace; it does
not magically improve the corpus.

### Step 5 — Ask an unsupported question

```bash
curl --silent http://localhost:8000/api/v1/collaborate \
  -H 'Content-Type: application/json' \
  -d '{"question":"Explain quantum chromodynamics renormalization."}' \
  | python3 -m json.tool
```

Expected properties:

- `grounded` is `false`;
- `sources` is empty;
- critic outcome is `blocked`;
- writer returns the configured insufficient-evidence text;
- citation count is zero.

## Interpreting `grounded` correctly

In this starter, the critic marks a run grounded when retrieval returned at least one match. Query
coverage is exposed as a metric, but it is not currently a threshold. Therefore:

```text
grounded = retrieval found a lexical match
```

It does **not** mean:

- the corpus is factually correct or current;
- every answer sentence is entailed by a source;
- the top match is the best possible evidence;
- the system passed human review;
- prompt injection is impossible.

This limitation is intentional and measurable. Lesson 06 shows how to create cases that reveal it.

## Exercises

### Required — create an evidence-flow map

For one supported request, record a table:

| Artifact | Example value | Owner | Trust boundary |
| --- | --- | --- | --- |
| question | your text | external caller | untrusted |
| normalized question | trimmed text | Pydantic schema | validated |
| matches | ranked excerpts | `KnowledgeBase` | local corpus |
| grounded decision | boolean | critic | policy output |
| answer | excerpt or synthesis | server | returned output |

Add the source file and line or symbol responsible for each transition.

### Challenge — provider privacy review

Without entering a real key, read the provider implementation and list exactly which data would be
sent to an external endpoint. Identify configuration, timeout, response-size, and error boundaries.

### Challenge — terminology test

Explain in three sentences why “the answer has a citation” is weaker than “the cited excerpt
supports the answer.” Use one concrete counterexample.

## Check your understanding

1. Can retrieval be correct while generation is unfaithful? Give an example.
2. Why is source visibility useful even in extractive mode?
3. What new privacy boundary appears in provider mode?
4. Why can a token-overlap match create a false grounded decision?
5. When might returning no answer be better product behavior than a plausible response?

## Completion checklist

- [ ] I can define the main grounding terms without referring to a framework.
- [ ] I observed standard and collaboration responses for the same question.
- [ ] I observed the unsupported path and critic block.
- [ ] I mapped every important artifact to an owner and trust boundary.
- [ ] I can state the exact limitation of the current `grounded` flag.
- [ ] I understand that provider mode changes privacy and determinism.

## Further reading

- [FastAPI request bodies](https://fastapi.tiangolo.com/tutorial/body/)
- [Pydantic model configuration](https://docs.pydantic.dev/latest/concepts/models/)
- [OWASP guidance for LLM applications](https://genai.owasp.org/)

---

**Previous: [Lesson 00](../00-course-setup/README.md)** · **Next: [Lesson 02 — Build the retrieval pipeline](../02-retrieval/README.md)**
