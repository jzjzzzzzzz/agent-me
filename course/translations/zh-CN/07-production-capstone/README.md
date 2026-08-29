# 第 07 课：生产设计与作品集结课项目

[上一课：评估](../06-evaluation/README.md) · [课程首页](../README.md) · [English](../../../07-production-capstone/README.md) · [评分标准](../RUBRIC.md)

**时间：**90 分钟–3 天 · **难度：**中高级 · **产物：**ADR、扩展、度量与演示

## 为什么重要

在单进程正确运行的 workflow，一旦加入多 Worker、外部模型、用户账户、持久 trace 或不可信 tenant，并不会自动可靠。生产设计就是识别每增加一个边界后消失了哪些保证，再添加明确机制与测试。

结课项目要求你改进系统，同时不宣称没有实现的能力。

## 学习目标

- 区分当前保证和期望保证；
- 解释 at-least-once、幂等、重试、取消；
- 设计持久工作流状态与安全 trace 保留；
- 选择并实现一个有边界的扩展；
- 比较修改前后；
- 写 ADR；
- 做技术上可辩护的作品集展示。

## 原理：当前保证与缺失保证

当前已实现并测试：严格 request/body 限制、确定性本地检索与角色顺序、服务端 run ID、frozen 工件、批准/阻断路径、严格浏览器解析、安全纯文本、不持久化问题/trace、CI/评估/容器 smoke。

当前没有：重启后持久状态、多 Worker 协调、exactly-once、provider 冗余/预算、认证授权/tenant 隔离、加密 trace/retention job、生产规模语义检索、形式化忠实度、SLO 与事故响应。

不要隐藏缺失清单，它是可信系统设计的起点。

### 从本地调用到持久工作流

分布式版本可能保存：

```text
Run(id, tenant, status, version, created_at, deadline)
Stage(run_id, name, attempt, status, input_ref, output_ref, lease_until)
Event(run_id, sequence, type, safe_metadata, created_at)
```

Worker 原子 claim stage，幂等写输出，再 append event。

- **投递：**多数队列至少一次投递。Worker 完成后 ACK 前崩溃会重复收到，必须有稳定 idempotency key 与条件更新。
- **超时/重试：**只重试临时错误，使用有界次数、带 jitter 的指数退避和总 deadline。非法输入/策略阻断不应重试。
- **取消：**持久化取消，在昂贵工作和 commit 前检查。客户端断开不是跨 Worker 可靠取消信号。
- **背压：**限制排队、tenant 并发、provider 并发和输出大小，防止耗尽连接、内存、额度和费用。
- **隐私：**默认保存结构化 code/metric；持久化 prompt 前定义保留、删除、tenant 权限与脱敏。

## 阅读实现

重新检查你可能扩展的边界：[`collaboration.py`](../../../../backend/app/collaboration.py) 的角色状态与顺序、[`main.py`](../../../../backend/app/main.py) 的进程内 HTTP 执行、[`request_limits.py`](../../../../backend/app/request_limits.py) 的接收限制、[`docker-compose.yml`](../../../../docker-compose.yml) 的进程拓扑，以及 [CI](../../../../.github/workflows/ci.yml) 的打包验证。

对每个文件记录：加入 Worker 或持久化后，哪些保证会消失或必须重新设计。

## 结课选项

只选一个，深度与证据优先于功能数量：

1. **Verifier role：**加入第五个类型化角色，同步后端、schema、前端、测试、评估和图。
2. **检索升级：**配置第二种排序，建立 relevance label，对比 precision/recall 和 latency，保留 fallback。
3. **持久本地 run：**SQLite/PostgreSQL + migration + 幂等状态，加入重启/重复执行测试，默认不保存 raw prompt。
4. **认证与 tenant 隔离：**使用成熟认证，把 knowledge/run 按 tenant 约束，测试 IDOR、授权、删除、密钥脱敏。
5. **Provider 角色实验：**一个角色可选调用 OpenAI-compatible provider，默认关闭，并增加 timeout、错误分类、输出限制、隐私文档与 mock contract test。

## 动手实验：必写 ADR

在自己的 Fork 建立 `docs/adr/0001-<decision>.md`：

```markdown
# ADR 0001: <决策>
## Status
Proposed | Accepted | Superseded
## Context
有什么已度量问题或需求？
## Decision
构建什么，边界和不变量是什么？
## Alternatives considered
至少两个，包含什么都不做。
## Consequences
收益、成本、失败、隐私、运维、迁移。
## Verification
测试、评估、指标与回滚信号。
```

ADR 不是宣传文案，必须写被拒方案和负面后果。

### 实现流程

1. 建立聚焦 issue 和 branch；
2. 记录基线测试/评估；
3. 大改前写 ADR；
4. 为期望行为添加失败测试/用例；
5. 实现最小完整 vertical slice；
6. 公开数据变化时同步 Python/TypeScript；
7. 加失败和边界测试；
8. 更新英文文档与受影响翻译；
9. 运行完整门禁；
10. 记录度量和限制。

```bash
make lint
make test
make docs
make evaluate
make build
```

## 生产评审

### 正确性

状态是否原子？重复投递会不会重复副作用？输出是否关联正确 run/tenant？时间、顺序、ID 是否由服务端控制？

### 可靠性

每个网络边界是否有 timeout？哪些错误重试、几次？重启后如何？是否有背压与降级？

### 安全/隐私

谁能读 knowledge/trace/output？昂贵处理前是否限制 body/file？密钥是否不进入 Git/响应/日志？保留与删除是否实现并测试？

### 可观测性与评估

能否从 run ID 定位失败阶段？Metric 是否有界？报警是否对应用户影响？标签是否与语料版本化？是否覆盖无依据/对抗用例？

## 练习：作品集包

准备：2 分钟架构讲解、批准与阻断 live demo、角色协议图、clean commit 的测试/评估输出、ADR/PR、修改前后度量、限制列表。

准确简历写法：

> 构建并测试了一个单进程四角色 multi-agent 编排流程（planner → researcher → critic → writer），包含不可变类型化交接、本地 grounded 检索、拒答、运行轨迹、确定性评估与 FastAPI/React 界面。

新增度量后才写具体数字。除非已实现和测试，不要写 distributed、autonomous、production-ready、hallucination-free 或 multiple LLMs。

## 理解检查

1. 为什么队列不能默认 exactly-once？
2. Idempotency key 与 stage lease 应保存在哪里？
3. 哪些当前不变量在角色变成 Worker 后仍成立？
4. 如何证明 tenant trace 隔离且可删除？
5. 你的评估能测什么、不能泛化到什么？
6. 什么信号会触发 rollback？
7. ADR 拒绝了什么方案？
8. 负载一直很小时应简化什么？

## 完成清单

- [ ] 选择一个有明确 non-goal 的结课项目。
- [ ] 记录修改前基线。
- [ ] ADR 包含替代方案与后果。
- [ ] 实现前或同时加入失败验证。
- [ ] 完成含失败行为的 vertical slice。
- [ ] Lint、测试、文档、评估、build 全通过。
- [ ] 度量包含用例数和限制。
- [ ] Demo 展示批准与阻断。
- [ ] 作品集措辞与实际实现一致。
- [ ] 使用[评分标准](../RUBRIC.md)完成自评。

## 延伸阅读

- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)
- [AWS Retries and Backoff](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [Architecture Decision Records](https://adr.github.io/)

---

**上一课：[第 06 课](../06-evaluation/README.md)** · **返回[中文课程首页](../README.md)** · **查看[评分标准](../RUBRIC.md)**
