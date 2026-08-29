# 第 04 课：类型化交接与编排

[上一课：角色设计](../03-role-design/README.md) · [课程首页](../README.md) · [English](../../../04-typed-orchestration/README.md) · [下一课：Critic 与可观测性](../05-critic-observability/README.md)

**时间：**60–90 分钟 · **难度：**中级 · **产物：**经过测试的协议修改

## 为什么重要

如果所有阶段都修改同一个共享字典，拼错 key 可能在很后面才失败，一个角色也能覆盖另一个角色的数据。类型化交接把假设变成工具和测试可检查的协议。

Agent-Me 有两层协议：内部角色使用 frozen Python dataclass；公开 HTTP 边界使用 Pydantic 和 TypeScript 运行时解析。

## 学习目标

- 从 `Plan` 追踪到 `CollaborationResponse`；
- 解释 `frozen=True` 与不可变性的价值；
- 区分内部工件和公开 schema；
- 找到后端与浏览器强制的不变量；
- 修改一处交接并同步所有受影响层；
- 避免 `dict[str, Any]` 让协议失效。

## 原理：协议地图

```text
内部 Python                                HTTP / 浏览器
Plan                                       CollaborationRequest
EvidenceBundle         ┐                   CollaborationStage
Critique               ├→ orchestrator →  CollaborationResponse
WrittenAnswer          │                   TypeScript runtime parser
StageTrace             ┘                   React view model
CollaborationResult
```

内部工件可以包含不适合跨 HTTP 的实现细节；公开 schema 只应包含稳定、安全且调用者需要的信息。

| 工件 | 关键不变量 |
| --- | --- |
| `Plan` | 任务有序，query count 非负 |
| `EvidenceBundle` | match 保留排序，来源只来自检索 |
| `Critique` | 决定与覆盖率描述当前证据 |
| `WrittenAnswer` | 阻断时引用为 0 |
| `StageTrace` | 序号为正，角色/结果闭集，metric 为安全标量 |
| `CollaborationResult` | 服务端 run ID、固定 workflow、有序 stage |

必须区分：哪些由静态类型保证，哪些由构造/模型保证，哪些只有测试或文档保证。

## 阅读实现

1. [内部工件与角色](../../../../backend/app/collaboration.py)
2. [公开模型](../../../../backend/app/schemas.py)
3. [HTTP 序列化](../../../../backend/app/main.py)
4. [浏览器类型和运行时解析](../../../../frontend/src/api.ts)
5. [解析测试](../../../../frontend/src/api.test.ts)
6. [UI 渲染](../../../../frontend/src/App.tsx)

TypeScript 编译类型无法校验任意网络 JSON，所以必须保留运行时 parser。

## 动手实验

验证不可变：

```bash
.venv/bin/python - <<'PY'
from dataclasses import FrozenInstanceError
from app.collaboration import Plan
plan = Plan(tasks=("retrieve",), query_term_count=1)
try:
    plan.query_term_count = 99
except FrozenInstanceError as error:
    print(type(error).__name__)
PY
```

`tuple` 也避免任务列表被修改；但 frozen dataclass 内部如果包含可变对象，仍要单独约束。

### 追踪字段

追踪 `query_coverage`：Critic 计算 → `Critique` → `StageTrace.metrics` → Pydantic JSON → TypeScript 有限标量检查 → React 展示。再对 `run_id` 做同样追踪，并写出格式在哪里强制。

### 运行协议测试

```bash
.venv/bin/pytest -q backend/tests/test_collaboration.py backend/tests/test_api.py
cd frontend
npm test -- --run src/api.test.ts src/App.test.tsx
cd ..
```

### 受控改动

给 `EvidenceBundle` 增加 `document_count: int`，由 researcher 计算，不再由 orchestrator 重算。更新 trace 与测试。判断它是否需要成为 trace 之外的公开字段；不要因为内部存在就自动暴露。

```bash
make lint
make test
make evaluate
```

可以在 learner branch 完成后保存 diff，再恢复。

## 协议演进步骤

1. 找到所有生产者与消费者；
2. 判断 additive 还是 breaking；
3. 更新服务端模型和序列化；
4. 更新浏览器运行时解析，而不只是 TS interface；
5. 增加合法与非法 fixture；
6. 更新 UI 状态和文档；
7. 运行集成与容器 smoke；
8. 旧客户端无法安全迁移时进行 API 版本化。

不受限的 `dict[str, Any]` 会允许字段缺失、类型歧义、覆盖、私密数据误序列化和跨角色泄露。Trace metrics 因此只允许 boolean 和有限 number。

## 练习

### 必做：标记强制机制

选择五个不变量，标记由静态类型、构造/模型校验、运行 parser、单测、行为评估或只有文档中的哪一层保证。把一个“只有文档”的不变量变成可执行校验。

### 中级：新增 verifier

在 critic 与 writer 间插入 `VerifierAgent`，检查引用路径、阻断时引用为 0、回答长度。同步 agent literal、stage 数量/顺序、Pydantic、TS parser、测试、评估、图与文档。

### 高级：公开 workflow 版本

比较新 endpoint、workflow discriminator 和 API 版本，设计四阶段客户端如何识别未来五阶段响应。

## 理解检查

1. Pydantic 与 TypeScript 为什么不重复？
2. Frozen dataclass 中哪些嵌套值仍可能可变？
3. 哪些内部字段不应公开？
4. 为什么必须测试非法网络响应？
5. 后端能启动时，schema 变化仍可能为何是 breaking？

## 完成清单

- [ ] 能画出内部与公开协议层。
- [ ] 从创建到浏览器追踪了两个字段。
- [ ] 运行前后端协议测试。
- [ ] 不使用 `Any` 修改一次交接。
- [ ] 按强制机制分类了不变量。
- [ ] 能描述安全公开协议迁移。

## 延伸阅读

- [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [Semantic Versioning](https://semver.org/)

---

**上一课：[第 03 课](../03-role-design/README.md)** · **下一课：[第 05 课：Critic 门控与安全可观测性](../05-critic-observability/README.md)**
