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

已确认的偏好无需词项命中也可进入私有回答上下文，其他记忆采用词项匹配检索。
记忆最多选取 20 条，发送给模型的上下文仍受 `MAX_CONTEXT_CHARS` 限制。
没有配置模型时仅返回相关原文，不会智能模仿语气。
如需模型生成，在本地 `.env` 配置 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL`，重启后生效。
普通问答与协作模式保持原有行为，**不会读取私有工作区**。

### 4. 更新、冲突与删除

- 修改已确认条目后，它重新变为待确认状态，旧内容立即退出记忆检索。
- 相同 `kind + key` 的已确认条目视为冲突，必须明确确认替换；替换在数据库事务内完成。
- 不同字段之间的语义矛盾尚不自动识别；请使用一致的字段命名。
- 删除记忆后不再用于生成。聊天记录中已有的原文仍在，可另行清空全部聊天。
- 历史聊天持久化用于显示（最近 100 条），本版不自动重新发送历史聊天给模型，避免删除的记忆通过旧对话重新进入上下文。因此不是完整的多轮指代对话。
- 导出包含所有档案、记忆与完整聊天，请将导出文件视作私有资料。当前不提供导入接口。
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

Add profile fields as typed entries (`fact`, `preference`, `event`, `decision`). All new or edited
entries are pending until confirmed. Use `Remember: ...` in private chat to propose a preference,
then review it in the memory list. The default extracted key is `conversation.preference`; edit it
to a specific key before confirmation when needed. Matching kind/key conflicts require explicit
replacement. Cross-key semantic contradiction detection is not implemented.

Confirmed preferences are eligible without lexical overlap; other entries use lexical
retrieval. At most 20 memory entries are selected, and provider context is bounded by
`MAX_CONTEXT_CHARS`. Optional private Markdown belongs in `private/knowledge/`, never the tracked `knowledge/`.
Private Markdown is operator-maintained knowledge and bypasses candidate confirmation.
The public chat and collaboration endpoints never read this workspace.

The database persists chat for display (latest 100 turns); it does not replay history to the model,
so deleted memory cannot leak back through old turns. This first version does not provide full
multi-turn contextual conversation. Deleting memory does not erase its existing chat transcript:
use Clear history separately. Export includes the full transcript and all entries; import is not
implemented. Stop the backend before removing `private/` to erase the entire workspace and token.

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
| GET | `/entries` | List profile and memory entries with provenance and timestamps |
| POST | `/entries` | Add pending `{kind, key, content}` |
| POST | `/entries/{id}/edit` | Replace fields and return to pending |
| POST | `/entries/{id}/confirm` | Confirm with `{replace_ids: []}`; 409 reports conflicts |
| POST | `/entries/{id}/delete` | Delete memory |
| GET | `/history` | Latest 100 persisted turns |
| POST | `/history/clear` | Delete all turns, retain entries |
| GET | `/export` | Export all entries and turns |
| POST | `/chat` | Private grounded answer for `{question}` and persist exchange |
