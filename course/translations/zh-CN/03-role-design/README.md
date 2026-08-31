# 第 03 课：设计协作角色

[上一课：检索](../02-retrieval/README.md) · [课程首页](../README.md) · [English](../../../03-role-design/README.md) · [下一课：类型化编排](../04-typed-orchestration/README.md)

**时间：**45–60 分钟 · **难度：**中级 · **产物：**角色边界决策记录

## 为什么重要

很多项目把包含多个职位名称的 prompt 都叫 multi-agent，但这并没有形成工程边界。有效拆分要求每个角色都有清晰职责、输入、输出和失败策略，并且在可观测性、测试、隔离或扩展上带来足够收益，才能抵消复杂度与延迟。

## 学习目标

- 用协议和职责定义角色，而不是人设；
- 解释 planner/researcher/critic/writer 的所有权；
- 实际比较单路径和协作路径；
- 找出协调开销与耦合；
- 准确说明 Agent-Me 的 multi-agent 范围；
- 为新增或拒绝一个角色写决策记录。

## 原理：角色是否值得存在

新增角色前回答：

1. 它独占什么决定？
2. 最小输入工件是什么？
3. 下游依赖什么输出？
4. 失败时阻断、重试、降级还是只报告？
5. 如何独立验证它改善了系统？

如果答案只是“同一份上下文”“自由文本”“换了一个 Agent 名字”，先保留单函数。

| 角色 | 输入 | 输出 | 负责 | 不负责 |
| --- | --- | --- | --- | --- |
| Planner | 规范化问题 | `Plan` | 检索意图与证据优先任务 | 检索结果 |
| Researcher | `Plan` + 注入的 retriever | `EvidenceBundle` | 执行检索并封装证据 | 最终批准 |
| Critic | 问题 + 证据 | `Critique` | grounded/block 决定 | 回答措辞 |
| Writer | 证据 + critique | `WrittenAnswer` | 组合回答 | 发现来源 |

Orchestrator 负责顺序和公开 trace；角色不直接相互调用。

### 项目的准确范围

它实现了：同一 Python 进程内四个职责、类型化工件、明确编排、运行轨迹、通过/阻断测试。

它没有实现：多个模型、自主循环、并发/分布式 Worker、持久工作流、Agent 网络协议或 chain-of-thought 暴露。

## 阅读实现

按顺序阅读 [`collaboration.py`](../../../../backend/app/collaboration.py)：类型别名、frozen dataclass、四个 `run`、构造器依赖注入、`orchestrator.run`。再比较
[`main.py`](../../../../backend/app/main.py) 的 `/chat` 和 `/collaborate`。

## 动手实验

启动 API，并用同一问题调用两条路径：

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload
curl --silent http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
curl --silent http://localhost:8000/api/v1/collaborate \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
```

记录差异：两者都显示来源；协作路径额外包含 run ID、显式 grounded 决定和四阶段 trace，也因此有更多协议和测试成本。

### 依赖替换实验

`CollaborationOrchestrator` 构造器接收 retriever 和可选角色实例。编写 planner test double 改变 `Plan.retrieval_query`，再用 recording retriever 证明 researcher 检索的正是该值。不要用任意 `dict` 绕开协议。

### 诚实度量开销

循环调用或使用 HTTP 工具比较两条本地路径。记录硬件、commit、预热、次数、中位数和一个高百分位。不要用一次请求宣称性能。若每个角色未来调用外部模型，顺序执行的成本/延迟会完全不同。

## 权衡

**收益：**角色级测试和所有权、写作前审批、可检查阶段、易插入 verifier/policy。

**成本：**更多类型和 schema、前后端顺序耦合、迁移测试、外部调用时的延迟/费用，以及“只有名字没有价值”的仪式化角色。

正确问题不是“multi-agent 更高级吗”，而是“这个边界对该负载产生了可测价值吗”。

## 练习

### 必做：角色 ADR

选择 verifier、router、privacy reviewer 或 formatter，写一页说明：当前失败、输入/输出字段、它拥有的不变量、序列位置、阻断/重试、测试/评估、预计成本，以及在什么条件下拒绝加入。

### 中级：识别仪式化角色

在不改变原始 HTTP 问题的前提下，临时修改 planner 的 `retrieval_query`。编写测试，确保 researcher 如果忽略 plan、仍检索原问题，测试就会失败。再说明什么证据能支持保留或删除 planner 边界。

### 高级：并行研究设计

设计两个可独立执行的 researcher 和合并协议，处理稳定顺序、重复证据、部分失败、超时和来源。

## 理解检查

1. 什么让两个角色不只是两个“人设”？
2. 为什么顺序属于 orchestrator？
3. 何时单函数更好？
4. 四次外部模型调用如何改变成本和可靠性？
5. 什么证据能证明新增 critic 有价值？

## 完成清单

- [ ] 能定义每个角色的输入、输出与职责。
- [ ] 用同一问题比较过两条 API。
- [ ] 能准确说出项目没有实现什么。
- [ ] 测试或设计了一个角色替换边界。
- [ ] 完成角色决策记录并包含拒绝标准。
- [ ] 能同时解释收益与成本。

## 延伸阅读

- [Python dataclasses](https://docs.python.org/zh-cn/3/library/dataclasses.html)
- [Bounded Context](https://martinfowler.com/bliki/BoundedContext.html)
- [Google SRE critical state](https://sre.google/sre-book/management-of-critical-state/)

---

**上一课：[第 02 课](../02-retrieval/README.md)** · **下一课：[第 04 课：类型化交接与编排](../04-typed-orchestration/README.md)**
