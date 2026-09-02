<div align="center">

# Agent-Me

**构建、检查和评估可审计的多 Agent RAG 系统。**

Agent-Me 是一个面向可审计、基于角色的多 Agent RAG 工作流的开源参考实现，并配有中英双语动手工程课程。

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> 本文是项目概览的简体中文翻译。完整技术规范以[英文 README](../../README.md)和 <code>docs/</code> 文档为准。

## Agent-Me 是什么

Agent-Me 是一套可运行的 FastAPI + React 参考实现。它在单进程中依次运行 Planner、Researcher、Critic、Writer，并可选增加 Verifier；类型化交接、检索证据、阻断决定、安全轨迹和验证结果都可以检查。默认本地路径无需付费模型 API。

它同时提供[完整的简体中文工程课程](../../course/translations/zh-CN/README.md)，让学习者逐步重建、修改和评估同一套架构。

## Agent-Me 不是什么

它目前不是分布式多 Agent Runtime、通用 Agent SDK、企业托管平台，也不保证事实正确。这里的 “Agent” 是具有显式协议的角色阶段，由 orchestrator 在单进程中顺序执行；Verifier 只检查机械不变量，不证明语义或事实真实性。

## 工程课程

**参考实现：**直接运行、检查和扩展。

**课程：**逐步重建架构，理解每个组件为何存在。

- [简体中文课程](../../course/translations/zh-CN/README.md)
- [English curriculum](../../course/README.md)
- [评分标准](../../course/translations/zh-CN/RUBRIC.md) · [词汇表](../../course/translations/zh-CN/GLOSSARY.md)

课程包括角色拆分、类型化交接、Critic 门禁、安全轨迹、确定性评估、故障注入、扩展第五个角色和生产架构边界。

## 核心能力

| 能力 | 实现 |
| --- | --- |
| 知识来源 | 可审查、可版本管理的 Markdown 文件 |
| 检索 | 确定性的本地检索与来源片段 |
| 生成 | 可选 OpenAI 兼容模型服务 |
| 协作 | 本地 planner → researcher → critic → writer → 可选 verifier 工作流 |
| 后端 | FastAPI、严格请求模型和输入限制 |
| 前端 | React、安全纯文本渲染、响应式布局 |
| 国际化 | 自动识别地区，支持 9 种界面语言 |
| 工程化 | Docker Compose、CI、测试、Lint、类型检查 |
| 运维 | 健康检查与就绪检查接口 |

## 快速开始

需要安装 Docker 与 Compose 插件。

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

打开：

- 网页：<http://localhost:5173>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>
- 就绪检查：<http://localhost:8000/ready>

默认启用本地抽取模式，首次运行不需要任何 API Key。

## 自定义你的 Agent

1. 将 <code>knowledge/example-profile.md</code> 替换为你有权使用的 Markdown 内容。
2. 在本地 <code>.env</code> 中修改 <code>APP_NAME</code> 与 <code>APP_DESCRIPTION</code>。
3. 保留本地抽取模式，或者配置 OpenAI 兼容服务。
4. 发布前检查回答引用的来源并调整知识内容。
5. 生产密钥必须保存在托管平台的 Secret Manager 中，不能提交到 Git。

~~~dotenv
LLM_BASE_URL=https://provider.example/v1
LLM_API_KEY=replace-with-a-secret
LLM_MODEL=replace-with-a-model-id
~~~

## 国际化

界面支持 English、简体中文、繁體中文、日本語、한국어、Español、Français、Deutsch 和 Português (Brasil)。首次访问会按照浏览器地区选择语言，用户也可以手动切换；选择结果只保存在浏览器本地。未知语言统一回退到英文。

贡献新语言前请阅读[本地化指南](../LOCALIZATION.md)。

## 安全与隐私

- 提示词和知识文件都必须被视为不可信输入。
- 前端将内容渲染为纯文本，不会直接插入 HTML。
- 本地抽取模式不会把问题或文档发送给模型服务。
- 角色式多 Agent 模式完全在本地确定性运行，不会调用模型服务。
- 模型服务模式会向你选择的服务商发送问题、近期对话和有限的检索上下文。
- 本参考实现默认不持久化聊天内容，也不启用分析统计。
- 不要在知识目录中放入密钥、私人通信、受监管数据或个人敏感信息。

安全问题请按照 [SECURITY.md](../../SECURITY.md) 私下报告，不要发布到公开 Issue。

## 文档与贡献

- [API 参考](../API.md)
- [架构说明](../ARCHITECTURE.md)
- [信任、数据流与部署边界](../TRUST.md)
- [多 Agent 工程课程](../../course/translations/zh-CN/README.md)
- [部署指南](../DEPLOYMENT.md)
- [本地化指南](../LOCALIZATION.md)
- [贡献指南](../../CONTRIBUTING.md)

欢迎提交 Issue 和 Pull Request。提交前请运行 <code>make lint</code>、<code>make test</code>、<code>make evaluate</code> 和 <code>make build</code>。

## 相关项目与许可

需要由授权人员通过共享队列回答、同时兼容 OpenAI 协议的接口？请查看 [Human API](https://github.com/jzjzzzzzzz/human-api)。

本项目采用 [MIT License](../../LICENSE)。
