<div align="center">

# 通过动手构建学习 Agent-Me

**从确定性检索到经过评估的多智能体结课项目。**

[English](LEARN.md) · [简体中文](LEARN.zh-CN.md) · [完整中文课程](course/translations/zh-CN/README.md) · [提问](https://github.com/jzjzzzzzzz/agent-me/discussions/categories/q-a)

</div>

## 你会学到什么

Agent-Me 是一门免费、可运行的 grounded agent 工程课程。你不是复制一个不可解释的最终
Demo，而是通过小而可测试的步骤逐渐构建完整系统。核心学习路径不需要付费模型 API，检索、
协作、评估与隐私边界都可以直接从源码中检查。

完成课程后，你将能够：

- 在可审阅的 Markdown 知识库上实现确定性检索；
- 设计 planner、researcher、critic 与 writer 的职责边界；
- 使用不可变、强类型对象完成角色交接；
- 区分安全的运行轨迹与不应暴露的隐藏思维过程；
- 对证据不足的问题拒答，而不是编造依据；
- 编写行为评估与故障注入测试；
- 解释本地协作编排与分布式生产系统之间的差异；
- 在作品集或技术面试中展示可复现、可衡量的结课项目。

## 开始之前

你需要 Git、Python 3.11+、Node.js 20+ 与 npm；推荐但不强制安装带 Compose 的 Docker。
extractive 与 collaboration 实验都不需要 API Key。

如果希望学习记录出现在自己的 GitHub 主页，可先 Fork 再克隆；也可以直接克隆本仓库：

```bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
make setup
make lint
make test
make docs
make evaluate
```

最后一条命令应输出：

```text
COLLABORATION_EVAL 4/4 passed
```

## 八个构建检查点

第一次学习 agent 工程时，请按顺序完成。每课均包含原理、源码导读、动手实验、练习、验证
命令、面试题与完成清单。

1. **复现基线** — 完成[第 00 课](course/translations/zh-CN/00-course-setup/README.md)，启动服务并保存质量门禁结果。
2. **分离检索与生成** — 完成[第 01 课](course/translations/zh-CN/01-grounded-qa/README.md)，比较有依据回答与主动拒答。
3. **构建并挑战检索器** — 完成[第 02 课](course/translations/zh-CN/02-retrieval/README.md)，增加一条知识与相应回归测试。
4. **按职责拆分工作** — 完成[第 03 课](course/translations/zh-CN/03-role-design/README.md)，解释四个角色各自负责什么。
5. **让交接强类型且可检查** — 完成[第 04 课](course/translations/zh-CN/04-typed-orchestration/README.md)，扩展一个安全的可观测字段及测试。
6. **增加 critic 门禁** — 完成[第 05 课](course/translations/zh-CN/05-critic-observability/README.md)，观察通过与阻断两条路径。
7. **用评估取代 Demo 自信** — 完成[第 06 课](course/translations/zh-CN/06-evaluation/README.md)，先制造一次评估失败，再修复它。
8. **交付可解释的结课项目** — 完成[第 07 课](course/translations/zh-CN/07-production-capstone/README.md)，按 [Rubric](course/RUBRIC.md) 自评并记录局限。

每个检查点至少保留一种可复核证据：命令输出、测试、响应样例、架构决策、CI 链接或已脱敏
截图。不要把密钥、个人资料、私有提示词或专有文档提交到仓库。

## 启动完整本地栈

```bash
cp .env.example .env
docker compose up --build
```

- 应用：<http://localhost:5173>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>
- 就绪检查：<http://localhost:8000/ready>

使用 `docker compose down` 停止服务。

## 把成果整理成作品集

不要只写“做了一个多智能体聊天机器人”，而要整理其他工程师能够验证的证据：

1. 你解决的 grounded Q&A 问题；
2. 角色与强类型交接存在的原因；
3. 定义成功的评估用例与指标；
4. 无依据问题、非法输入与 provider 故障的处理；
5. 目前仍在单进程中的部分及生产化所需工作；
6. 完整复现、测试与演示命令。

## 提问与贡献

- 环境、课程与架构问题：使用 [Q&A Discussions](https://github.com/jzjzzzzzzz/agent-me/discussions/categories/q-a)。
- 展示 Fork、结课项目或评估结果：使用 [Show and tell](https://github.com/jzjzzzzzzz/agent-me/discussions/categories/show-and-tell)。
- 可复现 Bug 与明确任务：使用 [Issues](https://github.com/jzjzzzzzzz/agent-me/issues)。
- 提交 PR 前阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

安全问题请按照 [SECURITY.md](SECURITY.md) 私下报告。
