# 示例 Capstone：增加失败关闭的验证器策略

[课程首页](../../translations/zh-CN/README.md) · [第 07 课](../../translations/zh-CN/07-production-capstone/README.md) · [English](README.md)

这是可复现的结课项目示例，不代表生产流量或语义真值。示例只使用仓库中的确定性本地
运行时与公开 fixture，不需要 API key 或付费模型服务。

## 问题与可测验收标准

基线协作流程在 writer 后结束。若引用路径错误或 `grounded` 标记不一致，只要 writer 的
某条路径漏掉检查，错误就可能越过最终响应边界。

验收标准：

1. 基线请求继续使用四阶段工作流标识与行为；
2. verified 请求只增加一个最终 `verifier` 阶段；
3. 验证器接受与检索来源一致的响应元数据和引用路径；
4. 不变量失败时返回固定的阻止回答，不返回候选回答；
5. 两种策略都通过四个已提交评估标签。

## 架构决策

**决定：**在 writer 后增加第五个本地确定性 verifier，由显式 `verified` 策略选择。验证器
检查机械性的响应不变量并返回类型化 artifact；HTTP 响应保持兼容，同时使用独立的五阶段
工作流标识。

**否决方案一：**把检查放进 writer。代码更少，但同一角色会同时生成并批准输出，writer
重构也可能绕过门禁。

**否决方案二：**调用第二个模型做语义裁判。这会增加成本、延迟、隐私披露、非确定性和
新的失败边界，却不能证明真值，因此不属于本地示例范围。

## 使用的公开 Fixture

- 知识 fixture：[`knowledge/example-profile.md`](../../../knowledge/example-profile.md)
- 评估标签：[`course/fixtures/collaboration_cases.json`](../../fixtures/collaboration_cases.json)
- 编排与类型化 artifact：[`backend/app/collaboration.py`](../../../backend/app/collaboration.py)
- API 协议测试：[`backend/tests/test_api.py`](../../../backend/tests/test_api.py)
- 浏览器解析测试：[`frontend/src/api.test.ts`](../../../frontend/src/api.test.ts)

评估集包含两个支持问题和两个不支持问题。四个用例能发现本示例针对的回归，但不能估计
广泛的真实世界质量。

## 复现证据

```bash
make setup
make lint
make test
make docs
.venv/bin/python scripts/evaluate_collaboration.py --json
.venv/bin/python scripts/evaluate_collaboration.py --workflow verified --json
```

在已提交公开 fixture 上观察到：

```text
baseline：4/4 通过；trace 长度 4
verified：4/4 通过；trace 长度 5
支持问题：2 个 grounded，每个 1 个来源
不支持问题：2 个 blocked，每个 0 个来源
```

这些数字来自上述命令，不代表用户量、流量、延迟或总体准确率。

## 前后对比

| 行为 | 之前：baseline | 之后：verified 策略 |
| --- | --- | --- |
| 角色顺序 | planner → researcher → critic → writer | planner → researcher → critic → writer → verifier |
| 最终机械不变量门禁 | 仅由 writer 承担 | 独立的类型化 verifier artifact |
| 无效引用/元数据 | 依赖 writer 路径 | 固定的失败关闭阻止回答 |
| 现有评估标签 | 4/4 | 4/4 |
| 外部模型服务 | 无 | 无 |

改动加强了职责分离并让一类协议失败可观察，但不能证明每个受支持句子都被来源语义蕴含。

## 安全与隐私检查

- 问题和 trace 保持进程内处理，starter 不持久化它们；
- 运行 ID 由服务器生成，不包含问题文本；
- trace 摘要和指标是有界运行 artifact，不是隐藏推理；
- verifier 不进行网络调用，也不接收密钥；
- 引用路径必须属于检索到的公开来源集合；
- 浏览器的“下载脱敏运行记录 JSON”只导出已验证协作响应，不含提交的问题、个人资料、
  模型服务设置或隐藏状态。

## 已知限制与下一步实验

限制包括：词法检索可能漏掉语义改写；引用成员关系不是语义蕴含；执行同步且仅在进程内；
四个用例不能刻画生产质量；没有持久取消、租户隔离或 SLO。

下一步实验是在类型化 verifier artifact 后增加逐句 claim-to-source 映射，先编写误报和漏报
标签，再修改策略；不要在看到结果后替换证据集。

## 诚实的作品集表述

> 为本地 FastAPI 多 Agent 工作流增加并测试了可选的第五个 verifier 角色，在保留四阶段
> 基线的同时执行失败关闭的引用与响应元数据不变量；两种策略均通过仓库中的四个确定性
> 公开评估用例。

这句话不声称真实用户、分布式 worker、生产规模、语义真值或多模型执行。
