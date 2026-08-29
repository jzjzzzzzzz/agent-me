# Agent-Me 课程词汇表

[中文课程](README.md) · [English glossary](../../../course/GLOSSARY.md)

| 术语 | 本仓库中的含义 | 常见误解 |
| --- | --- | --- |
| Agent | 有职责、类型化输入和输出的角色 | 任何带人设名称的函数 |
| Multi-agent orchestration | Orchestrator 协调多个显式角色交接 | 必须使用多个模型或机器 |
| Artifact（工件） | 一个角色交给后续阶段的不可变数据 | 所有人共享并修改的字典 |
| Corpus（语料库） | 检索可读取的 Markdown 文档 | 模型知道的所有信息 |
| Chunk（分块） | 被独立检索和排序的规范化文本块 | 必然是固定 token 窗口 |
| Retrieval（检索） | 选择并排序候选证据 | 生成回答 |
| Match | 文档、片段与检索分数 | 片段一定能回答问题的证明 |
| Grounded | 至少一个匹配通过当前审批规则 | 保证真实或完全蕴含 |
| Abstention（拒答） | 明确返回证据不足 | 服务器崩溃 |
| Citation（引用） | 与回答关联的来源路径 | 自动证明逐句有依据 |
| Critic gate | 决定批准或阻断生成的策略阶段 | 永不出错的安全检测器 |
| Operational trace | 安全的阶段、结果、计数和摘要 | 私有 chain-of-thought |
| Contract（协议） | 跨边界依赖的字段、类型、不变量和行为 | 只有文档说明 |
| Idempotency（幂等） | 相同 key 的重复操作不会产生第二次效果 | 消息只投递一次 |
| At-least-once | 工作可能重复投递，执行方必须处理重复 | 每个任务恰好执行一次 |
| Backpressure（背压） | 限制接收或并发工作以保护容量 | 更快地重试 |
| Evaluation case | 有版本、有人类依据的输入与预期行为 | 随机演示问题 |
| Precision（准确率） | 预测为正的结果中真正为正的比例 | 总体正确率 |
| Recall（召回率） | 预期为正的结果中被预测为正的比例 | 引用数量 |
| Production-ready | 针对负载证明了可靠性、安全、运维等要求 | “本地能跑” |
