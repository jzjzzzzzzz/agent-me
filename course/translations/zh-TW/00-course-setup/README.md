# 第 00 課：環境與證據優先的學習迴圈

[英文課程首頁](../../../README.md) · [English](../../../00-course-setup/README.md) · [简体中文](../../zh-CN/00-course-setup/README.md) · **下一課（英文）：[有依據的問答](../../../01-grounded-qa/README.md)**

**時間：**30–45 分鐘 · **程度：**初學者 · **產出：**可重現的基準

> 繁體中文課程目前正在逐課維護；本頁是第 00 課的完整翻譯。後續課程暫時連結至英文原文。

## 為什麼重要

Agent 專案經常在 Agent 邏輯執行前就已失敗：語料庫掛載到錯誤路徑、前端呼叫錯誤的
來源、相依套件發生漂移，或展示依賴一個未記錄的環境變數。如果在證明基準可用前就
修改協作流程，後續每次失敗都會有多種可能原因。

本課建立一套科學化迴圈：**控制環境、執行已知案例、記錄結果、只改變一個變數，然後
重新執行相同檢查**。

## 學習目標

完成本課後，你可以：

- 找出課程、執行環境、測試與部署目錄；
- 有意識地選擇 Docker 或本機工具鏈；
- 說明每個品質命令驗證什麼；
- 執行具確定性的協作評估；
- 區分環境設定失敗與應用程式行為失敗。

## 心智模型：四層證據

| 層級 | 問題 | 此儲存庫中的證據 |
| --- | --- | --- |
| 靜態品質 | 原始碼的結構是否有效？ | Ruff、ESLint、TypeScript |
| 單元行為 | 獨立元件是否維持契約？ | Pytest 與 Vitest |
| 行為評估 | 代表性問題是否得到預期結果？ | `collaboration_cases.json` |
| 整合執行環境 | 建置後的服務能否互相通訊？ | Compose 健康檢查與煙霧測試請求 |

單元測試全部通過，不代表容器一定能啟動；瀏覽器展示可用，也不代表系統會對缺乏依據的
問題拒答。請將這些證據層分開看待。

## 儲存庫導覽

執行命令前，請先閱讀下列檔案：

1. [`Makefile`](../../../../Makefile)：提供給學習者的穩定命令；
2. [`.env.example`](../../../../.env.example)：安全的預設值與設定介面；
3. [`docker-compose.yml`](../../../../docker-compose.yml)：服務拓撲與健康檢查；
4. [`.github/workflows/ci.yml`](../../../../.github/workflows/ci.yml)：每次貢獻會執行的檢查；
5. [`course/fixtures/collaboration_cases.json`](../../../fixtures/collaboration_cases.json)：評估所期待的行為。

公開儲存庫刻意排除正式環境資料庫、分析資料、私人文件與機密。你的複本也應採取相同
原則。

## 動手實驗

### 步驟 1：Fork 或 Clone

進行課程練習時，建議先 Fork 儲存庫，讓提交記錄保留在自己的帳號中。接著執行：

```bash
git clone https://github.com/<your-username>/agent-me.git
cd agent-me
git remote add upstream https://github.com/jzjzzzzzzz/agent-me.git
git switch -c learner/baseline
```

如果只想閱讀與執行：

```bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
```

### 步驟 2：選擇一種設定方式

#### Docker 方式

```bash
cp .env.example .env
docker compose config --quiet
docker compose up --detach --build --wait
```

驗證：

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:5173/ >/dev/null
```

完整停止服務：

```bash
docker compose down --volumes
```

#### 本機工具鏈方式

檢查必要工具：

```bash
python3 --version
uv --version
node --version
npm --version
git --version
```

Python 必須為 3.11 或更新版本，uv 必須為 0.11 或 0.12，Node.js 必須為 22 或更新版本。安裝並驗證：

```bash
make setup
make lint
make test
make docs
make evaluate
```

##### Windows PowerShell

Windows 預設不包含 Make。請從儲存庫根目錄使用以下原生 PowerShell 等效命令：

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

不依賴 Make，執行相同的四組品質檢查：

```powershell
# Lint 與型別檢查
.\.venv\Scripts\ruff.exe check backend scripts
.\.venv\Scripts\ruff.exe format --check backend scripts
Set-Location frontend
npm run lint
npm run typecheck
Set-Location ..

# 測試
.\.venv\Scripts\pytest.exe backend\tests
Set-Location frontend
npm test
Set-Location ..

# 文件
.\.venv\Scripts\python.exe scripts\check_docs.py

# 確定性評估
.\.venv\Scripts\python.exe scripts\evaluate_collaboration.py
```

若要在本機執行應用程式，請在兩個獨立的 PowerShell 終端機中分別啟動後端與前端。

後端（從儲存庫根目錄執行）：

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload
```

前端（從儲存庫根目錄執行）：

```powershell
Set-Location frontend
npm run dev
```

從另一個 PowerShell 終端機驗證後端：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

接著可在 <http://localhost:5173/> 開啟 Web 應用程式。

預期最後一行為：

```text
COLLABORATION_EVAL 4/4 passed
```

### 步驟 3：理解每個命令

| 命令 | 可以發現 | 無法證明 |
| --- | --- | --- |
| `make lint` | Python Lint/格式、ESLint、TypeScript 契約錯誤 | 執行時行為 |
| `make test` | 後端與前端元件的迴歸 | 容器連線 |
| `make docs` | 缺少本機連結與課程結構錯誤 | 說明內容一定正確 |
| `make evaluate` | 已知有依據／不支援決策的迴歸 | 廣泛的真實世界品質 |
| `make build` | 容器建置失敗 | 部署可靠性 |

### 步驟 4：記錄基準

在自己的 Fork 中建立 `LEARNING_NOTES.md`（上游課程不要求你提交此檔案）：

```markdown
## Lesson 00
- Commit tested: `<git rev-parse --short HEAD>`
- Platform: `<OS, Python, Node, Docker>`
- Commands: `make lint`, `make test`, `make docs`, `make evaluate`
- Evaluation: `4/4 passed`
- One surprise: ...
```

請記錄結果，不要記錄機密或完整的環境傾印內容。

## 閱讀實作

依序追蹤一個基準評估案例：

1. fixture 由 [`scripts/evaluate_collaboration.py`](../../../../scripts/evaluate_collaboration.py) 解析；
2. 知識目錄由 [`backend/app/knowledge.py`](../../../../backend/app/knowledge.py) 載入；
3. 各角色在 [`backend/app/collaboration.py`](../../../../backend/app/collaboration.py) 中執行；
4. 系統比較預期與實際的 `grounded` 決策；
5. 非零結束狀態會告訴 CI 行為已發生變化。

你現在不必理解每一行程式碼；本步驟的目標是找出各個邊界。

## 練習

### 必做：證明檢查器真的有效

暫時更改 [`collaboration_cases.json`](../../../fixtures/collaboration_cases.json) 中的一個預期值，
執行 `make evaluate`，並確認：

- 有一個案例顯示 `FAIL`；
- 程序以非零狀態結束（在 macOS/Linux 執行 `echo $?`）；
- 還原檔案後，測試套件重新變綠。

不要提交這個刻意製造的失敗。

### 挑戰：比較不同環境

分別在本機與 API 容器內執行評估，記錄路徑或相依套件的差異。若結果不同，請先調查，
再繼續後續課程。

## 常見問題

### `make setup` 找不到 uv 或 lock 已過期

安裝 uv 0.11.x 或 0.12.x，並執行 `uv lock --project backend --check`。如果 manifest 是有意
變更，請執行 `make lock` 並審查完整 lock diff；不要繞過 `--locked`。

### 前端無法連上 API

先開啟 `http://localhost:5173/api/v1/profile`。預設 Vite 與 Compose 設定會將同源 `/api`
請求代理到後端；只有主動設定 `VITE_API_BASE_URL` 時，才需要繼續檢查獨立 API 位址、連接埠、
`CORS_ORIGINS` 與 `/health`。

### Readiness 顯示零份文件

確認 `KNOWLEDGE_DIR` 指向儲存庫的 `knowledge` 目錄，且其中包含 UTF-8 `.md` 檔案。執行
環境會從工作目錄解析相對路徑。

### Docker 連接埠已被占用

在 `.env` 設定 `API_PORT` 或 `WEB_PORT`，然後在啟動前重新執行 `docker compose config`。

## 理解檢查

1. 為什麼瀏覽器截圖的證據力弱於可重複執行的評估命令？
2. 哪一項檢查會驗證 TypeScript 回應解析？
3. 為什麼 `.env.example` 適合提交至 Git，而 `.env` 不適合？
4. 如果測試在本機通過，但 Compose readiness 失敗，你會先檢查什麼？
5. 為什麼在刻意注入失敗後，必須先還原再繼續下一課？

## 完成清單

- [ ] 我能找出執行環境、課程、測試、fixture 與 CI workflow。
- [ ] 我已成功使用 Docker 或本機工具鏈其中一種方式。
- [ ] Lint、測試、文件與評估全部通過。
- [ ] 我觀察過一次刻意造成的評估失敗，並已還原。
- [ ] 我記錄了工具版本與結果，且未儲存機密。
- [ ] 我能說明 `4/4` 結果可以證明什麼，以及不能證明什麼。

## 延伸閱讀

- [Python 虛擬環境](https://docs.python.org/zh-tw/3/library/venv.html)
- [Docker Compose 概觀](https://docs.docker.com/compose/)
- [GitHub Actions 文件](https://docs.github.com/zh-tw/actions)

---

**下一課（英文）：[第 01 課：有依據問答的基礎](../../../01-grounded-qa/README.md)**
