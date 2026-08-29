# 第 01 课：有依据问答基础

[上一课：环境](../00-course-setup/README.md) · [课程首页](../README.md) · [English](../../../01-grounded-qa/README.md) · [下一课：检索](../02-retrieval/README.md)

**时间：**45–60 分钟 · **难度：**入门 · **产物：**证据流图

## 为什么重要

流畅不等于有依据。Grounded 系统先在明确语料中寻找证据，再限制返回或生成的内容。这样失败可以被观察：没有证据、证据很弱、证据不相关，或回答超出了证据。

Agent-Me 返回检索片段，让你检查这些失败，而不是只看最终文案。

## 学习目标

- 定义语料、分块、检索、grounding、生成、引用和拒答；
- 从 HTTP 校验追踪到来源片段；
- 区分本地抽取模式与可选 provider 模式；
- 准确说明当前 `grounded` 能证明什么；
- 不使用付费 API 测试支持和无依据问题。

## 原理：检索和生成是两个决定

```text
问题 → 规范化/校验 → 检索分块 → 证据决策 → 回答
                         │          └→ 无依据时拒答
                         └→ 排序来源
```

| 阶段 | 常用指标 | 失败示例 |
| --- | --- | --- |
| 检索 | 召回率、准确率、排序质量 | 相关段落没进入结果 |
| 证据决策 | 覆盖率、阈值、策略 | 只共享一个词却被当作支持 |
| 生成 | 忠实度、完整性、清晰度 | 添加来源里没有的事实 |
| 引用 | 来源准确、粒度 | 有引用但不能支持该句 |

### 本地抽取模式

未配置 provider 时，API 搜索本地 Markdown，直接使用最强片段作为回答，并返回排序来源。问题和文档不会发送到外部模型。

### OpenAI-compatible provider 模式

配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 后，检索仍在本地完成；有限上下文和近期历史会发往指定端点，再校验回答大小和错误。这个模式增加了隐私和网络边界。

## 阅读实现

依次阅读：

1. [`ChatRequest`/`ChatResponse`](../../../../backend/app/schemas.py)；
2. [`chat` 路由](../../../../backend/app/main.py)；
3. [`KnowledgeBase.search`](../../../../backend/app/knowledge.py)；
4. [Provider 边界](../../../../backend/app/provider.py)；
5. [浏览器 `ask`](../../../../frontend/src/api.ts)。

记录每个字段由谁提供、谁校验、是否可信。

## 动手实验

启动 API：

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

先阅读 [`knowledge/example-profile.md`](../../../../knowledge/example-profile.md)，预测下列问题会命中哪段：

```text
How does the example agent plan a project?
```

标准路径：

```bash
curl --silent http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
```

协作路径：

```bash
curl --silent http://localhost:8000/api/v1/collaborate \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
```

比较 `answer`、`mode`、`sources`、`grounded`、`trace`。

无依据路径：

```bash
curl --silent http://localhost:8000/api/v1/collaborate \
  -H 'Content-Type: application/json' \
  -d '{"question":"Explain quantum chromodynamics renormalization."}' \
  | python3 -m json.tool
```

应看到 `grounded=false`、空来源、critic `blocked`、writer 返回证据不足文案且引用为 0。

### 准确理解 `grounded`

当前实现只要检索返回至少一个 match 就批准。`query_coverage` 被记录但不参与阈值：

```text
grounded = 词法检索找到了匹配
```

它不代表语料一定正确、回答逐句被来源蕴含、top match 最优、已人工审核或不会受 prompt injection 影响。

## 练习

### 必做：建立证据流表

为一个请求记录 `question → normalized question → matches → grounded → answer`，写出示例值、所有者、信任边界和对应源码符号。

### 挑战：Provider 隐私审查

不填写真实密钥，只阅读实现，列出会发到外部的数据、超时、输出大小、配置和错误边界。

### 挑战：解释引用限制

用具体反例说明“回答带引用”为什么弱于“引用片段支持回答”。

## 理解检查

1. 检索正确时，生成还能不忠实吗？
2. 抽取模式为什么仍要显示来源？
3. Provider 模式增加了什么隐私边界？
4. Token overlap 为什么会误报 grounded？
5. 什么情况下明确拒答优于看似合理的回答？

## 完成清单

- [ ] 能不用框架术语定义 grounding 相关概念。
- [ ] 用同一问题观察两条路径。
- [ ] 观察过无依据与 critic 阻断。
- [ ] 完成工件所有者和信任边界图。
- [ ] 能准确说明 `grounded` 的限制。
- [ ] 理解 provider 模式改变隐私和确定性。

## 延伸阅读

- [FastAPI Request Body](https://fastapi.tiangolo.com/tutorial/body/)
- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/)
- [OWASP GenAI Security](https://genai.owasp.org/)

---

**上一课：[第 00 课](../00-course-setup/README.md)** · **下一课：[第 02 课：构建检索流水线](../02-retrieval/README.md)**
