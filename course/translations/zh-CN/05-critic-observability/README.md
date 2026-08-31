# 第 05 课：Critic 门控与安全可观测性

[上一课：类型化编排](../04-typed-orchestration/README.md) · [课程首页](../README.md) · [English](../../../05-critic-observability/README.md) · [下一课：评估](../06-evaluation/README.md)

**时间：**45–60 分钟 · **难度：**中级 · **产物：**通过/阻断轨迹证据

## 为什么重要

Agent 系统必须分别回答两个问题：工作流是否应继续？用户和运维人员可以安全看到什么？Critic 能阻止无依据生成，运行轨迹能显示顺序、状态和计数；两者都不要求公开私有推理。

## 学习目标

- 解释当前 critic 规则与限制；
- 区分策略决定与回答写作；
- 定义安全运行 trace；
- 在 API 和浏览器观察批准/阻断；
- 测试浏览器拒绝非法 trace；
- 设计更强证据检查但不夸大保证。

## 原理：Critic 是策略边界

Critic 接收 question 与 `EvidenceBundle`，输出：

```python
Critique(grounded: bool, query_coverage: float)
```

当前策略：有至少一个 match 就批准，否则阻断。Coverage 只记录、不参与阈值。更强版本可以检查最小分数、覆盖率、矛盾、来源时效/权威、claim-to-source entailment、逐句引用或领域权限，但每个检查都必须评估误报/漏报并定义失败行为。

### Critic 与 Verifier 是两个不同的门

页面现在提供两种协作策略：

| 策略 | 阶段 | 作用 |
| --- | --- | --- |
| `baseline` | planner → researcher → critic → writer | 稳定的四阶段教学协议 |
| `verified` | planner → researcher → critic → writer → verifier | 增加写作后的输出不变量检查 |

Critic 在写作前判断证据是否允许继续；Verifier 在写作后检查候选工件：writer 报告的引用数必须等于唯一证据路径数、每个路径必须以 `[path]` 出现在回答中、无证据固定回复必须保持零引用。

任何检查失败时，Verifier 会阻断候选回答，把 `grounded` 改为 `false`，并换成服务端固定失败文案。这能捕获交接损坏、引用丢失和不兼容 writer，但不能证明自然语言 claim 一定被来源蕴含，更不能称为“真理验证”。

### 安全 trace 与 chain-of-thought

| 可以公开的运行信息 | 不应作为 trace 公开 |
| --- | --- |
| stage 名称和顺序 | 自由形式隐藏推理 |
| completed/blocked | 私有 chain-of-thought |
| evidence/document count | 密钥、Authorization header |
| 有界覆盖率 | 完整私有 prompt |
| 简短固定摘要 | 内部 system instruction |
| 服务端 run ID | 文档里的个人数据 |

Telemetry 回答“发生了什么、在哪里”，不声称暴露模型私有思考。当前本地流程没有模型推理，但相同纪律能保护未来 provider 集成。

## 阅读实现

依次阅读：[`CriticAgent`、`VerifierAgent` 与 trace](../../../../backend/app/collaboration.py)、[公开 trace schema](../../../../backend/app/schemas.py)、[浏览器运行校验](../../../../frontend/src/api.ts)、[UI](../../../../frontend/src/App.tsx)、[parser/UI 测试](../../../../frontend/src/api.test.ts)。

## 动手实验

启动完整应用：

```bash
cp .env.example .env
docker compose up --build
```

打开 <http://localhost:5173>，选择 **Multi-agent lab**。

### 批准路径

输入：

```text
How does the example agent plan a project?
```

记录 run ID、grounded badge、四角色顺序、critic 的 `approved`/`query_coverage`、来源路径、writer 引用数。

### 阻断路径

输入：

```text
Explain quantum chromodynamics renormalization.
```

确认 researcher 证据为 0、critic `blocked`、writer 正常返回证据不足、来源为空且引用 0。阻断是成功策略结果，不是请求崩溃。

### 验证路径

选择 **已验证多 Agent**，再次提交有依据的问题，确认 workflow 以 `-verifier` 结尾、trace 有五个有序阶段，且 verifier 显示 `approved`、`citation_paths_valid`、期望引用数和报告引用数。

```bash
curl --silent http://localhost:8000/api/v1/collaborate \
  --header 'Content-Type: application/json' \
  --data '{"question":"How does the example agent plan a project?","workflow":"verified"}' \
  | python3 -m json.tool
```

请求只能从封闭枚举中选择策略；角色顺序、run ID、检查结果与失败文案都由服务端控制。阅读注入 `UnsupportedWriter` 的后端测试，确认丢失引用的候选回答不能通过。

### 检查原始 JSON 与 parser

用 curl 或开发者工具确认摘要是固定运行说明，metrics 只有有限数值/布尔值。运行：

```bash
cd frontend
npm test -- --run src/api.test.ts
```

阅读 run ID 错误、stage 缺失/重复/乱序、未知角色/结果、非法 metrics、错误 workflow/mode 测试。新增一个非法 fixture 并断言 `invalid_trace`。

## 设计运行 Telemetry

生产系统常需 run correlation ID、阶段时间和耗时、attempt、provider/model ID、token/cost budget、错误码/重试决定、证据 ID，以及只在权限日志出现的 tenant 信息。

存储字段前必须定义用途、读取者、保留期、脱敏、权限和删除。“更多可观测性”不意味着可以永久保存所有 prompt。

## 练习

### 必做：Trace 威胁模型

对每个当前 trace 字段记录：用途、外部可控性、大小/类型限制、隐私风险、应该在响应、日志、两者还是都不出现。

### 中级：更强审批规则

设计最小 coverage 规则，覆盖恰好边界、0 token、低词法重叠但相关的 paraphrase、高重叠但无关段落和用户拒答文案。比较错误后再决定默认值。

### 高级：冲突状态

把 critique 从 boolean 概念扩展为 `approved | insufficient | conflicting`，定义 writer、schema、UI 和评估如何反应，解释为何冲突不能伪装成正常答案。

## 理解检查

1. 为什么 blocked 是合法结果而不是 exception？
2. 当前 critic 漏掉什么？
3. 为什么调试方便也不应保存完整 prompt？
4. 浏览器运行校验如何降低不兼容/被破坏服务端风险？
5. 哪些 telemetry 只应在受权限保护的日志？
6. 为什么 Verifier 位于 Writer 之后，而不能替代 Critic？
7. 所有机械检查通过后，仍然不能声称哪种质量保证？

## 完成清单

- [ ] 在浏览器观察批准和阻断。
- [ ] 检查两条路径原始 JSON。
- [ ] 能准确说出 critic 当前规则。
- [ ] 新增一个非法 trace parser 测试。
- [ ] 完成 trace 字段威胁模型。
- [ ] 能区分运行轨迹和 chain-of-thought。
- [ ] 对比 baseline 与 verified trace，并能解释 fail-closed 及其语义限制。

## 延伸阅读

- [OpenTelemetry Concepts](https://opentelemetry.io/docs/concepts/)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [React JSX](https://react.dev/learn/writing-markup-with-jsx)

---

**上一课：[第 04 课](../04-typed-orchestration/README.md)** · **下一课：[第 06 课：评估、测试与故障注入](../06-evaluation/README.md)**
