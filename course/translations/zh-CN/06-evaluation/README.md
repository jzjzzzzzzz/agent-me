# 第 06 课：评估、测试与故障注入

[上一课：Critic](../05-critic-observability/README.md) · [课程首页](../README.md) · [English](../../../06-evaluation/README.md) · [下一课：生产结课](../07-production-capstone/README.md)

**时间：**60–90 分钟 · **难度：**中级 · **产物：**新用例和被检测的故障

## 为什么重要

演示只说明某个时刻某个精选问题能工作。评估则为一组有版本的输入写出预期行为，并在实现不一致时自动失败。测试和评估回答的问题不同，可信项目需要两者。

## 学习目标

- 区分单元、协议、集成、安全、行为评估；
- 解释 fixture schema 与退出码；
- 设计支持、无依据、边界和对抗用例；
- 计算 grounded 决策 precision/recall；
- 注入一次故障并验证自动捕获；
- 带数据集范围报告结果。

## 原理：质量层

| 层 | 示例 | 主要问题 |
| --- | --- | --- |
| 单元测试 | 无 match 时 critic 阻断 | 单组件是否保持不变量？ |
| 协议测试 | 乱序 stage 被拒绝 | 生产者/消费者是否一致？ |
| 集成测试 | FastAPI 返回四阶段 | 组件能否共同工作？ |
| 安全测试 | 超大 body 被拒绝 | 滥用边界是否有效？ |
| 行为评估 | grounded 是否符合标签 | 用户可见行为是否符合预期？ |
| 容器 smoke | 构建服务能回答 | 打包栈是否运行？ |

没有一层可以替代所有其他层。

### Fixture 与退出码

[`collaboration_cases.json`](../../../fixtures/collaboration_cases.json) 中每项只有 `id`、`question`、`expected_grounded`。Evaluator 严格校验 key/type，运行检索与编排，记录 source count/critic outcome：

- `0`：全部通过；
- `1`：行为与标签不一致；
- `2`：fixture 或环境配置无效。

这样 CI 能区分产品回归和评估文件损坏。

## 阅读实现

阅读 [`scripts/evaluate_collaboration.py`](../../../../scripts/evaluate_collaboration.py)，依次找到 fixture 校验、知识加载、每例运行、critic stage 获取、结果构造、可读/JSON 输出与退出状态。

## 动手实验

可读输出：

```bash
make evaluate
```

机器输出：

```bash
.venv/bin/python scripts/evaluate_collaboration.py --json > /tmp/agent-me-eval.json
python3 -m json.tool /tmp/agent-me-eval.json
```

新增至少三例：直接支持事实、无依据领域问题、较少精确 token 的 paraphrase。ID 必须稳定唯一；标签应来自 committed corpus，而不是“当前代码返回了什么”。

### 故障注入

反转一个 `expected_grounded`：

```bash
make evaluate
echo $?
```

确认退出码 1，再恢复。然后临时破坏 JSON 或添加未知字段，确认退出码 2，再恢复。

运行完整门禁：

```bash
make lint
make test
make docs
make evaluate
make build
```

## 用例类别

**支持类：**直接事实、paraphrase、跨 chunk/文档证据、一个支持解释的歧义问题、英文/CJK。

**无依据类：**无关专业领域、共享词但缺失事实、错误前提、不在公开语料的私人信息。

**对抗/边界类：**要求忽略证据的 prompt 文本、HTML/script 样式输入、空/非法/超大 body、重复 token、Unicode 与换行。

公开 fixture 不应含真实私密 prompt，且内容必须有公开使用权限。

### Grounded 决策的 Precision/Recall

把 `grounded=true` 当正预测：

| | 预期支持 | 预期不支持 |
| --- | ---: | ---: |
| 预测 grounded | TP | FP |
| 预测 blocked | FN | TN |

```text
precision = TP / (TP + FP)
recall    = TP / (TP + FN)
```

Precision 低表示无依据问题常被放行；recall 低表示支持问题常被拒答。报告任何百分比时必须同时报告用例数、标签范围和语料版本。三例上的 100% 不是生产准确率。

### 避免评估泄漏

反复针对同一小套 fixture 调逻辑，它就成了开发集。更强流程区分开发用例、已知 bug 回归、较少查看的 held-out 用例，以及按政策脱敏的生产反馈。语料和标签应共同版本化。

## 练习

### 必做：新增并度量

新增至少三类用例，报告用例数、confusion matrix、precision、recall、一个已知限制和语料 commit。

### 中级：扩展断言

增加可选的最小 source count 等预期，同时保持 fixture 严格校验。更新测试、schema 文档与现有 fixture，区分缺失和明确 unset。

### 高级：Mutation 实验

临时反转排序、删除 critic block 或弱化 parser。运行前预测哪些检查应失败；若没有失败，补充缺失的回归测试。

## 理解检查

1. 为什么所有单测通过时行为质量仍可能回归？
2. 谁应该负责 expected label？
3. Exit code 2 表达什么？
4. 为什么 3/3 不能宣传生产准确率？
5. 反复调参如何造成 evaluation leakage？

## 完成清单

- [ ] 能按质量层分类仓库检查。
- [ ] 运行可读和 JSON 评估。
- [ ] 新增至少三个有依据的用例。
- [ ] 主动观察退出码 1 和 2。
- [ ] 计算 confusion matrix、precision、recall。
- [ ] 报告结果时包含范围和限制。

## 延伸阅读

- [pytest](https://docs.pytest.org/)
- [Vitest](https://vitest.dev/guide/)
- [Google Test Sizes](https://testing.googleblog.com/2010/12/test-sizes.html)

---

**上一课：[第 05 课](../05-critic-observability/README.md)** · **下一课：[第 07 课：生产设计与结课项目](../07-production-capstone/README.md)**
