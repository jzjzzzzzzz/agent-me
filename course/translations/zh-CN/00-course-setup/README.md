# 第 00 课：环境与证据优先的学习闭环

[课程首页](../README.md) · [English](../../../00-course-setup/README.md) · [繁體中文](../../zh-TW/00-course-setup/README.md) · **下一课：[有依据问答](../01-grounded-qa/README.md)**

**时间：**30–45 分钟 · **难度：**入门 · **产物：**可复现的基线

## 为什么重要

很多 Agent 项目在 Agent 逻辑执行前就已经出错：知识目录挂载错误、前端请求了错误的地址、依赖漂移，或演示依赖一个没有记录的环境变量。如果没先证明基线正常，之后任何失败都会有多个可能原因。

本课建立一个工程化实验闭环：**控制环境 → 运行已知用例 → 记录结果 → 只改变一个变量 → 重跑同一组检查。**

## 学习目标

完成后你能够：

- 找到课程、运行代码、测试与部署目录；
- 有意识地选择 Docker 或本地工具链；
- 解释每个质量命令检查什么、不检查什么；
- 运行确定性的协作评估；
- 区分环境失败与应用行为失败。

## 原理：四层证据

| 层级 | 问题 | 仓库中的证据 |
| --- | --- | --- |
| 静态质量 | 源码结构是否合法？ | Ruff、ESLint、TypeScript |
| 单元行为 | 独立组件是否保持协议？ | Pytest、Vitest |
| 行为评估 | 代表性问题是否得到预期结果？ | `collaboration_cases.json` |
| 集成运行 | 构建后的服务能否通信？ | Compose 健康检查与 smoke request |

单元测试通过不代表容器能启动；浏览器演示成功也不代表无依据问题一定会拒答。

## 阅读实现

按顺序阅读：

1. [`Makefile`](../../../../Makefile)：学习者使用的稳定命令；
2. [`.env.example`](../../../../.env.example)：安全默认值和配置面；
3. [`docker-compose.yml`](../../../../docker-compose.yml)：服务拓扑与健康检查；
4. [CI workflow](../../../../.github/workflows/ci.yml)：每个 PR 自动运行的检查；
5. [评估用例](../../../fixtures/collaboration_cases.json)：预期行为。

公开仓库不应包含生产数据库、分析数据、私人文档、密钥或 `.env`。

## 动手实验

### 1. Fork 或 Clone

建议先 Fork，再运行：

```bash
git clone https://github.com/<your-username>/agent-me.git
cd agent-me
git remote add upstream https://github.com/jzjzzzzzzz/agent-me.git
git switch -c learner/baseline
```

只学习、不保存练习时可以直接 clone 上游。

### 2. 选择一种环境

Docker：

```bash
cp .env.example .env
docker compose config --quiet
docker compose up --detach --build --wait
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:5173/ >/dev/null
docker compose down --volumes
```

本地工具链（Python 3.11+、uv 0.11/0.12、Node 22+）：

```bash
make setup
make lint
make test
make docs
make evaluate
```

#### Windows PowerShell

Windows 默认不包含 Make。请从仓库根目录运行以下原生 PowerShell 等效命令：

```powershell
python --version
uv --version
node --version
npm --version
git --version

if (!(Test-Path .env)) { Copy-Item .env.example .env }
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) ".venv"
uv sync --project backend --locked --extra dev

Set-Location frontend
npm ci
Set-Location ..
```

不依赖 Make，运行同样的四组质量门禁：

```powershell
# Lint 与类型检查
.\.venv\Scripts\ruff.exe check backend scripts
.\.venv\Scripts\ruff.exe format --check backend scripts
Set-Location frontend
npm run lint
npm run typecheck
Set-Location ..

# 测试
.\.venv\Scripts\pytest.exe backend\tests
Set-Location frontend
npm test
Set-Location ..

# 文档
.\.venv\Scripts\python.exe scripts\check_docs.py

# 确定性评估
.\.venv\Scripts\python.exe scripts\evaluate_collaboration.py
```

如需在本地运行应用，请在两个独立的 PowerShell 终端中分别启动后端和前端。

后端（从仓库根目录运行）：

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload
```

前端（从仓库根目录运行）：

```powershell
Set-Location frontend
npm run dev
```

在另一个 PowerShell 终端中验证后端：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

随后可通过 <http://localhost:5173/> 打开 Web 应用。

预期最后一行：

```text
COLLABORATION_EVAL 4/4 passed
```

### 3. 理解命令边界

| 命令 | 能发现 | 不能证明 |
| --- | --- | --- |
| `make lint` | Python 格式/Lint、ESLint、TypeScript 错误 | 运行行为 |
| `make test` | 后端和前端组件回归 | 容器连接 |
| `make docs` | 本地链接与课程结构错误 | 解释一定准确 |
| `make evaluate` | 已知支持/拒答行为变化 | 真实世界总体质量 |
| `make build` | 容器无法构建 | 生产部署可靠 |

### 4. 记录基线

在自己的 Fork 建立 `LEARNING_NOTES.md`，记录 commit、系统、Python/Node/Docker 版本、执行命令、`4/4` 结果和一个意外点。不要粘贴 `.env`、token 或完整系统环境。

## 练习

### 必做：证明门禁真的有效

临时反转一个 `expected_grounded`，运行 `make evaluate`，确认有一个 `FAIL` 且退出码非 0；恢复文件后必须重新变绿。不要提交故意制造的失败。

### 挑战：比较环境

分别在本地和容器内运行相同评估。若结果不同，先调查路径、依赖和工作目录，再进入下一课。

## 常见问题

- **找不到 uv 或 lock 已过期：**安装 uv 0.11.x/0.12.x，并运行 `uv lock --project backend --check`。若 manifest 有意变更，运行 `make lock` 并审查完整 lock diff；不要绕过 `--locked`。
- **前端连不上 API：**检查 `VITE_API_BASE_URL`、端口、CORS 和 `/health`。
- **Ready 显示 0 文档：**检查 `KNOWLEDGE_DIR` 和 UTF-8 Markdown 文件。
- **端口占用：**在 `.env` 修改 `API_PORT`/`WEB_PORT`，先运行 `docker compose config`。

## 理解检查

1. 为什么截图比可重复评估命令更弱？
2. 哪项检查会验证 TypeScript 响应解析？
3. 为什么 `.env.example` 可以提交，而 `.env` 不可以？
4. 测试通过但 Compose readiness 失败时先检查什么？
5. 一次故障注入后为什么必须恢复？

## 完成清单

- [ ] 能指出运行代码、课程、测试、fixture 与 CI。
- [ ] Docker 或本地工具链至少一种成功。
- [ ] Lint、测试、文档与评估通过。
- [ ] 观察过一次评估失败并恢复。
- [ ] 记录结果但没有存储密钥。
- [ ] 能解释 `4/4` 能证明和不能证明什么。

## 延伸阅读

- [Python venv](https://docs.python.org/zh-cn/3/library/venv.html)
- [Docker Compose](https://docs.docker.com/compose/)
- [GitHub Actions](https://docs.github.com/zh/actions)

---

**下一课：[第 01 课：有依据问答基础](../01-grounded-qa/README.md)**
