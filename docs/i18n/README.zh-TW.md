<div align="center">

# Agent-Me

**建立、檢查並評估可稽核的多 Agent RAG 系統。**

Agent-Me 是可稽核、角色式多 Agent RAG 工作流程的開源參考實作，並附有中英雙語的實作工程課程。

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> 本文是專案概覽的繁體中文翻譯。完整技術規格以[英文 README](../../README.md)與 <code>docs/</code> 文件為準。

## Agent-Me 是什麼

Agent-Me 是可執行的 FastAPI + React 參考實作。Planner、Researcher、Critic、Writer 與可選的 Verifier 會在單一程序內依序執行；型別化交接、檢索證據、阻擋決策、安全軌跡與驗證結果都可供檢查。本機核心路徑不需要付費模型 API。

## Agent-Me 不是什麼

它目前不是分散式多 Agent Runtime、通用 Agent SDK、企業託管平台，也不保證事實正確。這裡的 Agent 是具有明確合約的角色階段，由 orchestrator 依序協調。

## 工程課程

課程會逐步重建參考實作使用的相同架構。完整課程目前提供[英文](../../course/README.md)與[簡體中文](../../course/translations/zh-CN/README.md)；[語言覆蓋表](../../course/LANGUAGES.md)會標示其他翻譯的範圍。

## 核心能力

| 能力 | 實作 |
| --- | --- |
| 知識來源 | 可審查、可進行版本管理的 Markdown 文件 |
| 檢索 | 確定性的本機檢索與來源片段 |
| 生成 | 可選的 OpenAI 相容模型服務 |
| 後端 | FastAPI、嚴格請求模型與輸入限制 |
| 前端 | React、安全純文字呈現、響應式版面 |
| 國際化 | 自動識別地區，支援 9 種介面語言 |
| 工程化 | Docker Compose、CI、測試、Lint、型別檢查 |

## 快速開始

需要安裝 Docker 與 Compose 外掛程式。

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

開啟網頁 <http://localhost:5173>，API 文件位於 <http://localhost:8000/docs>。預設使用本機擷取模式，首次啟動不需要 API Key。

## 自訂你的 Agent

1. 將 <code>knowledge/example-profile.md</code> 換成你有權使用的 Markdown 內容。
2. 在本機 <code>.env</code> 設定應用程式名稱與說明。
3. 保留本機擷取模式，或設定 OpenAI 相容服務。
4. 發布前檢查回答來源並調整知識內容。
5. 正式環境密鑰必須放在託管平台的 Secret Manager，不可提交到 Git。

## 國際化

介面支援 9 種語言。首次造訪會依照瀏覽器地區選擇語言，也可以手動切換；選擇結果只儲存在瀏覽器本機。未知語言會回退到英文。詳見[本地化指南](../LOCALIZATION.md)。

## 安全與隱私

- 將提示詞與知識文件視為不受信任的輸入。
- 前端只以純文字呈現內容，不直接插入 HTML。
- 本機擷取模式不會將問題或文件傳送到模型服務。
- 本參考實作預設不持久化聊天內容，也不啟用分析統計。
- 不要在知識目錄放入密鑰、私人通訊、受監管資料或個人敏感資訊。

安全問題請依照 [SECURITY.md](../../SECURITY.md) 私下回報。

## 文件、貢獻與授權

請參閱 [API](../API.md)、[架構](../ARCHITECTURE.md)、[部署](../DEPLOYMENT.md)及[貢獻指南](../../CONTRIBUTING.md)。提交前請執行 <code>make lint</code>、<code>make test</code> 與 <code>make build</code>。

相關專案：[Human API](https://github.com/jzjzzzzzzz/human-api)。本專案採用 [MIT License](../../LICENSE)。
