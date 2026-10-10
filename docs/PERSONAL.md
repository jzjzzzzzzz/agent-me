# Private AI Twin / 私有 AI 分身

## 中文：从零开始

这一版提供单用户、本地运行的档案与长期记忆闭环，不是自主学习或自主执行系统。
公开仓库只有通用代码与虚构示例；请勿把真实资料写入 `knowledge/`、测试或 README。

### 1. 安装

按仓库 [快速开始](../README.md#quick-start) 安装 Python 和前端依赖。在仓库根目录运行：

```bash
python3 scripts/init_personal.py
.venv/bin/uvicorn app.main:app --app-dir backend --env-file private/personal.env --host 127.0.0.1 --port 8000
```

另开终端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

打开 `http://localhost:5173`。在 `private/personal.env` 中查看 `PERSONAL_TOKEN`，
粘贴到“我的 AI 分身”的密钥输入框。密钥只保存在当前页面内存中，刷新后重新解锁。
Windows 可使用 `.venv\Scripts\uvicorn.exe` 和 `python` 替换对应命令。
私有工作区的控件与数据去向说明会跟随页面语言切换；切换语言不会重新锁定工作区、清除草稿，
也不会重新请求私有数据。记忆正文、聊天内容、字段键和 API 类型值始终保持原样。

初始化脚本具有幂等性：保留已有工作区数据和 `.env`，同时重新创建缺失的非敏感基础文件。
不使用该命令时私有模式默认关闭。已有 `.env` 中的模型配置仍然有效。

### 2. 填写档案

在“我的档案与记忆”中新增字段，保存后点击确认：

| 类型 | 推荐字段 | 虚构示例 |
| --- | --- | --- |
| fact | identity.name | Alex Example |
| fact | identity.skills | Python、数据分析 |
| fact | projects.current | 正在开发一个天气笔记应用 |
| fact | goals.current | 完成本月的演示版本 |
| preference | response.style | 先给结论，再给细节 |
| preference | boundaries.actions | 发送消息前先让我确认 |
| event | events.demo | 今天完成了第一次演示 |
| decision | decisions.storage | 选择 SQLite，因为先做单用户本地版本 |

档案就是结构化记忆，不另建一份相互矛盾的个人简介。
需要更多资料时，将 Markdown 文件放入 `private/knowledge/`，它们只用于私有聊天。
这里的文件由你手工维护，被视为已授权知识，不经过候选记忆确认。

### 3. 聊天与确认

在**私有聊天**输入 `记住：先给结论，再给细节` 或 `Remember: Keep answers concise`。
系统保存对话，并将指令后的文本作为待确认偏好；点击确认后才用于后续回答。
本版采用明确指令提取，不会从普通聊天中自动推断事实；事实、事件和决策请在表单中选择类型。
从聊天提取的默认字段为 `conversation.preference`，可先编辑成更具体的字段再确认。

已确认的偏好无需词项命中也可进入私有回答上下文，为其保留 20 条名额中的 5 条底线配额，
避免被大量匹配的事实挤出；预算有余时仍优先纳入偏好而非低相关事实。其他记忆采用词项匹配检索。
记忆总计最多选取 20 条；若已确认偏好与相关事实合计超出该预算，底线配额之外得分最低的偏好会被舍弃。
发送给模型的上下文仍受 `MAX_CONTEXT_CHARS` 限制。
没有配置模型时仅返回相关原文，不会智能模仿语气。
如需模型生成，在本地 `.env` 配置 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL`，重启后生效。
普通问答与协作模式保持原有行为，**不会读取私有工作区**。

### 4. 更新、冲突与删除

- 修改已确认条目后，它重新变为待确认状态，旧内容立即退出记忆检索，但保留为只读版本快照。
- 相同 `kind + key` 的已确认条目视为冲突，必须明确确认替换；替换在数据库事务内完成，旧条目变为 `superseded`，不会再用于回答。
- 记忆历史与恢复通过 API 或独立记忆核心操作；现有界面只显示活跃条目，不提供版本浏览。恢复旧版本会创建新的待确认候选，不会直接复活旧记忆。
- 不同字段之间的语义矛盾尚不自动识别；请使用一致的字段命名。
- 删除记忆会同时删除该条目的全部版本快照。被替代条目和恢复产生的候选是独立记录，需要分别删除；删除新条目不会重新激活旧条目。聊天记录中已有的原文仍在，可另行清空全部聊天。
- 历史聊天持久化用于显示（最近 100 条），本版不自动重新发送历史聊天给模型，避免删除的记忆通过旧对话重新进入上下文。因此不是完整的多轮指代对话。
- 导出版本 `4` 包含所有活跃与已替代记忆、版本历史及完整聊天；通过同一数据库快照读取。当前不提供导入接口，旧导出不会被后续删除追溯清除。
- 清空聊天不会删除记忆；删除所有本地数据时，先停止后端，再删除 `private/`，重新初始化会生成新密钥。

### 5. 隐私与发布

默认路径：`private/twin.sqlite3`、`private/knowledge/`、`private/personal.env`。
Git 和 Docker 构建上下文都排除 `private/`、环境文件和数据库文件。
不要把 `PERSONAL_DATA_DIR` 改成公开目录；自定义目录需要自行添加忽略规则。

**本地保存不等于不发送到模型。** 启用模型后，私有问题、检索到的已确认记忆（包括偏好）、
私有及公开知识片段会发送给你配置的服务商。密钥验证仅限制工作区访问，不会加密磁盘数据库。
请保持服务绑定 `127.0.0.1`；这是单用户工作区，不是具备用户隔离的公网多租户服务。
若要只在本机处理信息，请清空三个 `LLM_*` 配置，使用本地摘录模式。

提交前执行：

```bash
python3 scripts/check_private_data.py
git diff --cached
```

检查器检查 Git 暂存内容中的私有路径与常见密钥格式，CI 也执行检查。
可通过 `.git/hooks/pre-commit` 调用此脚本实现本地提交前拦截。
它不能识别所有个人信息，仍需人工检查。`.gitignore` 不会清除 Git 历史或已跟踪内容。
本次公开介绍已移除维护者个人演示引用；历史提交不会因此消失。

## English quick start

This is an opt-in, single-owner local workspace. Install the dependencies using the
[repository quick start](../README.md#quick-start), then run the initialization and launch commands above.
Unlock the new panel using `PERSONAL_TOKEN` from `private/personal.env`.
The initializer is idempotent: it preserves existing workspace data and `.env`, while recreating any missing non-secret scaffolding.
Private-workspace controls and data-destination disclosures follow the selected interface language.
Changing locale does not relock or refetch the workspace, and it preserves the in-memory token and
drafts. Memory/chat content, keys, and API type values remain verbatim.

Add profile fields as typed entries (`fact`, `preference`, `event`, `decision`). All new or edited
entries are pending until confirmed. Use `Remember: ...` in private chat to propose a preference,
then review it in the memory list. The default extracted key is `conversation.preference`; edit it
to a specific key before confirmation when needed. Matching kind/key conflicts require explicit
replacement. Replaced records become read-only `superseded` archives, excluded from answer context.
Edits preserve prior revision snapshots. Version browsing and restoration are API/core capabilities,
not new reference-UI features. Cross-key semantic contradiction detection is not implemented.

Confirmed preferences are eligible without lexical overlap; a reserved floor (5 of the 20
total slots) keeps them from being evicted by a flood of matching facts, and any unused
budget still favors preferences before low-relevance facts. Other entries use lexical
retrieval. At most 20 memory entries are selected in total; if confirmed preferences and
relevant facts together exceed that budget, the lowest-scoring preferences beyond the
reserved floor are dropped. Provider context remains bounded by `MAX_CONTEXT_CHARS`.
Optional private Markdown belongs in `private/knowledge/`, never the tracked `knowledge/`.
Private Markdown is operator-maintained knowledge and bypasses candidate confirmation.
The public chat and collaboration endpoints never read this workspace.

The database persists chat for display (latest 100 turns); it does not replay history to the model,
so deleted memory cannot leak back through old turns. This first version does not provide full
multi-turn contextual conversation. Deleting memory does not erase its existing chat transcript:
use Clear history separately. Deleting a record purges its own revision snapshots, not independently
restored candidates or archived replacements. Export version `7` includes the full transcript,
active and archived entries, and revision snapshots. [Portable import and explicit owner erasure](OWNER_CONTROL.md)
are available through Core/API/CLI. Stop the backend before removing `private/` and its
`personal.env` token to erase the initialized filesystem workspace.

Without model credentials, answers are excerpts, not personalized generation. Configure the three
`LLM_*` values in your ignored `.env` and restart for generated answers. When enabled, your question,
retrieved memories/preferences and knowledge excerpts are sent to that provider. The browser token
is held only in page memory. The database is not encrypted. Bind services to loopback; this is not
a public multi-user deployment. Git exclusion does not imply provider privacy or erase Git history.

Run `python3 scripts/check_private_data.py` and inspect `git diff --cached` before committing.
The checker examines indexed files for private paths and common secret patterns, not arbitrary PII.
Use it from `.git/hooks/pre-commit` for a local guard; CI also runs it. Keep customized data paths
ignored, and never commit exported personal data.

## API

All routes below require personal mode and `Authorization: Bearer <PERSONAL_TOKEN>`.
The token must contain at least 32 characters. Disabled mode returns 404, failed authentication 401.

| Method | Path (prefix `/api/v1/personal`) | Purpose |
| --- | --- | --- |
| GET | `/entries` | List active entries; `?include_superseded=true` includes archives |
| POST | `/entries` | Add pending `{kind, key, content}` |
| POST | `/entries/{id}/edit` | Replace fields, snapshot the change, and return to pending |
| GET | `/entries/{id}/history` | Read ordered revision snapshots |
| POST | `/entries/{id}/restore` | Propose a historical `{revision, expected_revision?}` as a new pending entry |
| POST | `/entries/{id}/confirm` | Confirm with `{replace_ids: []}`; 409 reports conflicts |
| POST | `/entries/{id}/delete` | Delete a record and all of its revision snapshots |
| GET | `/history` | Latest 100 persisted turns |
| POST | `/history/clear` | Delete all turns, retain entries |
| GET | `/export` | Version-7 snapshot including learning provenance and forgetting digests |
| POST | `/chat` | Private grounded answer for `{question}` and persist exchange |

### Typed memory contract / 结构化记忆契约

The independent [memory core](../backend/app/memory.py) owns the lifecycle, SQLite transactions,
source links, snapshots, and retrieval. It does not import FastAPI, HTTP clients, configuration,
or the model provider. The [personal API](../backend/app/personal.py) is a transport adapter;
`MemoryNotFound` and `MemoryConflict` domain errors map to HTTP 404 and 409.

OpenAPI describes `MemoryRecord`, `MemoryRevision`, `StoredTurn`, and `MemoryExport`.
A memory contains `kind`, `key`, `content`, server-generated `id`, `source`, `status`
(`pending`, `confirmed`, or `superseded`), `sensitivity` (`public`, `private`, `sensitive`), UTC `created_at` / `updated_at` timestamps,
a monotonically increasing `revision`, and nullable `superseded_by`.
The default list excludes superseded records; export includes them.

- Manual sources are `manual`; explicit remember instructions use `turn:<id>`.
- An edit attributes the new version to `manual`, while snapshots preserve the previous source.
- Restore creates a **new pending record** with `source = memory:<original-id>@<revision>`.
  Its confirmation still needs explicit replacement if the original kind/key has a current record.
- `created`, `edited`, `confirmed`, and `superseded` snapshots are stored with their mutations
  in the same transaction. Repeated confirmation without a version precondition is a no-op.
- Existing databases migrate automatically. Their known state becomes a `baseline` snapshot;
  pre-migration edits or deleted replacements cannot be reconstructed.
- The source turn, explicitly requested candidate, and initial snapshot are written atomically.
  Ordinary conversation still creates no inferred memory. Remember text remains capped at 2,000 characters.

Entry creation rejects client-set provenance, IDs, timestamps, revision, or status.
Confirmation rejects unknown fields, duplicate or blank replacement IDs, non-string IDs,
IDs longer than 100 characters, and lists longer than 100 IDs with HTTP 422.
Valid but mismatched conflict sets return HTTP 409 with `conflict_ids` and `conflict_revisions`.

For race-safe review, clients should send `expected_revision` on edit, confirmation, and restore.
Confirmation can also send `replace_revisions: {"<conflict-id>": <reviewed-revision>}`.
The server compares these preconditions inside the write transaction; stale requests return 409
without changing any entries or snapshots. These fields are optional for compatibility with
existing clients; callers omitting them do **not** receive stale-review protection.

Export uses version `7` (separate from the repository release version) and includes `revisions`,
`sources`, `ingestion_runs`, `origins`, and `forgotten` digest records.
Entries, full history, and snapshots are read in one database transaction. An older version-1 or version-2
export consumer must be updated; the existing reference UI downloads the JSON without parsing it.
The [portable import contract](OWNER_CONTROL.md) accepts supported snapshots into an empty
workspace through exact digest review; execution permissions/plans are inert archives, not restored grants.

Deletion removes the selected record, all of its snapshots, and its ingestion excerpts in one transaction.
Opaque digests of current and historical kind/key/content are retained to block automatic re-ingestion. It does not
cascade to separate archived/restored records, transcript text, previous exports, or provider data.
A deliberate manual re-add remains possible; replay of an earlier ingestion cannot recreate the record.
A historical `source` or `superseded_by` ID can refer to a record subsequently deleted by its owner.
Retrieval reads only current confirmed records, never snapshots or chat history. Deleting a
replacement never makes an archived record current again. Already-running generation is not
cancelled by a later deletion.

记忆核心可脱离 HTTP 服务和模型服务独立运行。创建、修改、确认、替代的快照与状态变更在同一
事务提交；旧数据库自动迁移为已知状态的基线，不伪造之前的变化历史。API 默认只列出活跃条目，
历史和已替代条目可显式查询；它们不参与回答。恢复只创建来源可追溯的新候选，仍须确认。
删除会清除所选条目及其全部快照，不自动删除独立的恢复候选、已替代条目或聊天原文。

### Structured-memory sensitivity / 结构化记忆敏感性

Structured records default to `private`. `sensitive` records are excluded from `Store.context`
and private chat unless the owner explicitly sets `allow_sensitive=True` / `{"allow_sensitive": true}`.
When an external model is configured, that opt-in permits the selected sensitive memory excerpts to
be sent with the question. CLI recall is local and never calls a provider. Source labels become a
floor for extracted candidates; cross-source duplicate pending candidates retain the highest label.
Edits without an explicit sensitivity field preserve the label, and restoration never implicitly
lowers the current classification. Label lowering requires a separate explicit owner edit.

Labels do not automatically classify PII, redact the owner's question, or classify manually maintained
private Markdown. Those existing Markdown and question/provider boundaries remain unchanged.
The reference UI does not provide sensitive-memory opt-in; use the API or CLI for that operation.

### Pure Agent verification / 纯 Agent 验证

Run from the repository root, without credentials or a running server:

```bash
make evaluate-memory
```

Expected: `MEMORY_EVAL 18/18 passed`. The synthetic longitudinal cases cover positive retrieval,
pending exclusion, unsupported queries, correction, stale approval, supersession, provenance,
restore-as-candidate, deletion, preference fidelity, and empty export after forgetting.
`make evaluate` runs these cases alongside the existing collaboration evaluation.
These deterministic checks do not measure semantic entailment, embedding quality, or personality imitation.


### Controlled learning

Approved-source registration, candidate extraction, exact provenance, deduplication, replay,
failed-run recovery, revocation, CLI use, and forgetting semantics are described in
[Controlled Agent learning](LEARNING.md). These are core/API/CLI capabilities, not frontend additions.


Entity binding, declared confidence, belief states, validity/knowledge time and owner-reviewed retention
are documented in [Structured identity and time](IDENTITY_TIME.md).


The grounded-local `ask`/`retrieve`/`verify` Agent contracts, owner binding, source-value verification,
and bilingual/temporal retrieval are described in [Personal retrieval](PERSONAL_RETRIEVAL.md).
The older private chat endpoint remains a separate compatibility contract.


## Local owner agency

Snapshot version `7` additionally includes `tool_permissions`, `action_plans`, `tasks`, `notes`,
and `action_events`. Tool defaults remain disabled. These are independent private data copies;
memory deletion does not delete task/note/plan arguments. The [agency contracts](AGENCY.md)
document explicit approval, inspection, rollback and current deletion boundaries.


## Portability, audit and independent-copy control

Snapshot version `7` adds `audit_events`, `import_archives` and `ingestion_replay_keys`.
The [owner-control contracts](OWNER_CONTROL.md) describe exact reviewed import into an empty
workspace, non-restoration of execution authority, content-free operational audit and explicit
source/action/output/archive/transcript/SQLite-state deletion boundaries.
