# Long-term conversation memory / 对话长期记忆

This is the local, token-protected, **single-owner** Agent-Me workspace, not the public Interview
deployment. It reuses the existing SQLite schema, review and replacement operations, exact digests,
temporal selection and scoped provider-disclosure gate. There are no new services, dependencies,
database migrations, provider calls for extraction, or public endpoint changes.

## Try it / 使用

1. Enable and unlock the [private workspace](PERSONAL.md). Use **Private chat**, outside the review workbench.
2. Send `记住：偏好 response.style = 给导师写项目更新，先说结论，再给进展和下一步` or
   `Remember: preference response.style = Put the conclusion first in mentor updates`.
   Review and confirm the candidate under **Profile & memories**. This command itself never calls
   a model, even if provider delivery was checked.
3. Start another visit or restart the app using the same private data directory. Ask about
   your preference to see a local excerpt and its source, or ask the configured and individually
   authorized model to draft an update. Local mode cannot draft prose; model adherence is not guaranteed.
4. To set a project-only exception, confirm a `project` identity, load project scopes, select it, and
   submit the same preference key with the new value. Confirm it without replacing the personal
   default. Only that project's chat gives the project preference precedence.
5. To change a current value, use `更正：偏好 response.style = 先说风险，再给下一步` in the
   same scope, then review the old and new records and explicitly approve the replacement. The
   previous record stays effective until this approval. Use **Delete** to forget a specific record.
6. An ordinary message can be captured later via **Propose memory from this message**. Select the
   type, key and scope, and provide a verbatim excerpt. The server checks the excerpt against
   the stored owner message; assistant text and fabricated excerpts cannot be captured this way.

## Current behavior and limits

- **Chat, candidates and active memory are separate.** Write commands create pending records of
  type `fact`, `preference`, `event` or `decision`; Chinese type aliases are accepted.
  Legacy `Remember: …` / `记住：…` still produces a preference at `conversation.preference`.
  Typed keys use ASCII letters, digits, periods, underscores or hyphens (start with a letter).
  The right-hand side must be nonblank and at most 2,000 code points. Malformed explicit commands
  do not invoke a provider. The backend does not accept a model or assistant turn as write authority.
- **Optional local suggestions do not learn silently.** An unchecked-by-default chat control can
  propose a pending record for a single, short, explicitly forward-looking statement such as
  “From now on, start mentor updates with the conclusion” or “我们决定后续周报只保留两个里程碑”.
  Temporary, hypothetical and question-like cues are screened conservatively. This is a finite
  English/Chinese rule set, not a semantic classifier, and it can miss or misclassify language.
  No backfill scans past chats. Suggested fields have distinct deterministic keys; name the
  canonical field before confirming a replacement of an existing preference.
- **Read scope is selected before relevance.** Default chat sees unbound and owner-linked
  memories, not other entities' records. Project chat adds only its selected confirmed project;
  its active same-key preference shadows the default for that request. Pending, superseded,
  unknown, out-of-time and unapproved sensitive records do not enter current chat context.
  Topical fields require lexical overlap; broad presentation defaults such as `response.style`
  can guide generation without overlap, but do not become unrelated facts in local answers.
  Selection and provider character limits remain bounded. Disable **Use confirmed long-term
  memories** for a chat request to compare behavior with the durable store withheld; this does not
  turn off Markdown retrieval or change any records.
- **Local capture is exact and deduplicated.** A persisted user turn, candidate and initial
  revision are committed together for in-chat proposals. The original quote is attributed
  to `turn:<id>`. Exact active repeats reuse the entry; superseded values are not recreated.
  Record digests block exact deleted values, and quote digests prevent reusing the same
  deleted excerpt from its old turn via a renamed field. This is not fuzzy semantic erasure.
- **The transcript is not context.** An old chat stays readable until separately cleared, but
  is never replayed to the model or mined to replenish memory. Independent copies such as
  superseded entries, private Markdown, archived exports, backups or already delivered model
  prompts are governed separately. See [owner control](OWNER_CONTROL.md).
- **Generation is a separate boundary.** Default chat is local. Optional provider use requires a
  reviewed target and data policy and explicit opt-in for that request. Current scope and sensitive
  data are checked before disclosure. Broad style preferences are treated as defaults: a direct
  request for a different format takes precedence for that reply and does not write a change.
  The last answer shows available sources, not proof that a model used or entailed each source.

## Recall precision / 检索准确性

Private chat now distinguishes two forms of recall:

- **Closed owner/project fields:** a small, bilingual, whole-question catalog maps phrases such as
  `我做什么工作？` to role fields and `When is this due?` to the selected project's deadline.
  It is not free-form semantic search and does not infer a different project from the words in
  the question. Closed-field answers do not fall through to an operator Markdown note, public
  example, or external model when the field is missing. If distinct active fact values exist under
  equivalent keys, the chat reports disagreement rather than choosing the newer value.
- **Other questions:** punctuation and common conversational terms are removed before lexical
  coverage is scored. A topical hit needs at least 75% meaningful-term coverage and an anchor:
  a shared multi-character non-Han token or a contiguous two-Han-character phrase. A single
  common character is not enough. This favors abstention over exposing a vaguely similar memory;
  broad presentation defaults can still be offered to an explicitly authorized generator.

The source panel displays the reason (field, text match, or writing default) and stored revision.
That metadata describes what was **offered**, not what a model actually used. Before optional
delivery, the backend also rechecks the revision and active field agreement against live state.
This remains SQLite-only: no embedding service and no automatic recall of old transcripts.

## API integration

- `POST /api/v1/personal/chat`: adds optional `project_id`, `suggest_memory` (default false)
  and `use_memory` (default true). Existing `allow_sensitive` and `allow_provider` stay opt-in.
  A command response uses `mode: "memory-review"`. A command or actual proposal adds
  `capture: {turn_id, outcome, memory_id}`; non-proposal answers need not include it.
  Closed-field answers add `recall: {field, status}` (available, unavailable, disabled, disputed).
  Memory sources add `reason` and `revision`; document sources keep their original shape.
- `POST /api/v1/personal/history/{turn_id}/capture`: accepts the typed `Entry` fields, but
  sensitivity is `private` or `sensitive` and a non-null `entity_id` must be a confirmed project.
  `content` is checked as a contiguous exact excerpt from a persisted user turn.
  An assistant or missing turn returns 404, a fabricated excerpt returns 422.
- Outcomes: `created`, `existing`, `superseded`, `forgotten`, and `ignored`
  (an explicit command that did not parse). None of these is an approval. Confirm,
  replace, restore and delete through the [existing lifecycle](API.md#private-memory-lifecycle).

## Research and repo comparison

| Reference reviewed | What we incorporated | What we did not port |
| --- | --- | --- |
| [Mem0 paper, §2.1](https://arxiv.org/html/2504.19413v1#S2.SS1) and [Mem0 implementation](https://github.com/mem0ai/mem0/blob/main/mem0/memory/main.py) | Separate extraction from update; distinguish add, existing, stale and ignored outcomes; scope before comparison. | The paper's model-selected updates/deletes and vector similarity; paper and current repo are not assumed to implement an identical policy. |
| [LangMem hot path](https://github.com/langchain-ai/langmem/blob/main/docs/docs/hot_path_quickstart.md), [background path](https://github.com/langchain-ai/langmem/blob/main/docs/docs/background_quickstart.md) and [tool code](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/tools.py) | Distinguish explicit owner requests from opportunistic extraction; separate long-lived scope from a chat thread. | Agent-controlled mutation and unattended transcript processing. |
| [Zep paper, temporal invalidation](https://arxiv.org/html/2501.13956v1#S2.SS2.SSS3) and [Graphiti edge code](https://github.com/getzep/graphiti/blob/main/graphiti_core/utils/maintenance/edge_operations.py) | Honor validity separately from when a record was saved; retain replaced versions for inspection without returning them as current. | A new knowledge graph and inferred validity dates from raw chat. |
| [MemGPT paper](https://arxiv.org/abs/2310.08560) and [Letta](https://github.com/letta-ai/letta) | Keep durable records outside the active prompt and recall only selected material. | Letting the model manage transport between memory tiers or rewrite the private store. |
| [A-MEM paper](https://arxiv.org/abs/2502.12110) and [A-MEM repository](https://github.com/agiresearch/A-mem) | Compared memory linking and evolving notes against Agent-Me's existing identities, links and revision history. | Automatic rewriting of old notes or expanding the graph as a side effect of chat. |
| [Hindsight (ACL 2026)](https://aclanthology.org/2026.acl-demo.27/) and [Hindsight repo](https://github.com/vectorize-io/hindsight) | Retain/recall/reflect separation reinforces keeping an exact owner utterance distinct from the extracted candidate and from answer-time evidence. | Model-generated observations or mental models as durable facts, parallel search infrastructure, and serving a second memory system. |
| [EverMemOS (ACL 2026)](https://aclanthology.org/2026.acl-long.2125/) and [EverOS repo](https://github.com/EverMind-AI/EverOS) | Compared its staged trace, consolidation and recollection to the independent history, review and read paths here. | Automatically creating scenes or rewriting the owner profile; these require separate owner-review and deletion rules in Agent-Me. |
| [LongMemEval paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/d813d324dbf0598bbdc9c8e79740ed01-Paper-Conference.pdf) and [benchmark repo](https://github.com/xiaowu0162/LongMemEval) | Design acceptance cases for cross-session recall, knowledge replacement, temporal exclusion and abstention. Also test project isolation and deletion, which are app-specific. | We did not run the public benchmark or claim a comparative accuracy score. |

Design ideas were adapted to Agent-Me's own memory contracts; no external source code was copied.
The review was targeted engineering reconnaissance, not an exhaustive literature review.

## Verification

The [API tests](../backend/tests/test_chat_memory.py) exercise recall from persisted state,
candidate review, updates/duplicates, explicit opt-in, unchanged normal chat, project boundaries,
time filtering, deletion/replay and optional provider delivery with a fake completion. The
[browser test](../frontend/e2e/chat-memory.spec.ts) covers project-scoped capture, confirmation,
a page reload, evidence display and forgetting on desktop and mobile. These are synthetic
product checks, rather than an evaluation on real users or a comparison with the papers.


### Fictional recall comparison

Run `make evaluate-chat-recall` or `.venv/bin/python scripts/evaluate_chat_recall.py --json`.
The [24 labeled scenarios](../course/fixtures/chat_recall_cases.json) exercise English and Chinese
paraphrases, project boundaries, ambiguous fields, pending and time boundaries,
expired/sensitive records and corrected/deleted memories. The comparator recreates v1's
local literal-overlap rule on the same scoped records and compares the first evidence ID,
explicitly excluded evidence and expected dispute state. It does not call any provider, use
real users or rank a generated response. This is a branch-specific acceptance set designed
to exercise known gaps, not an independent dataset or a LongMemEval score.
