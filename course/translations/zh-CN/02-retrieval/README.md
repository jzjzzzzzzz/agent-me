# 第 02 课：构建并测试检索流水线

[上一课：Grounding](../01-grounded-qa/README.md) · [课程首页](../README.md) · [English](../../../02-retrieval/README.md) · [下一课：角色设计](../03-role-design/README.md)

**时间：**60–75 分钟 · **难度：**入门–中级 · **产物：**检索回归测试

## 为什么重要

多数 grounded 系统的失败在 writer 执行前就已决定：加载器丢掉标题，分块拆开限定条件，分词器无法处理某种语言，或者排序把通用段落放到第一位。下游角色只能基于收到的证据工作。

检索器必须是有明确输入、输出、限制和质量指标的可测试子系统，而不是黑盒数据库调用。

## 学习目标

- 追踪加载 → 分块 → 分词 → 评分 → 排序；
- 手算当前 overlap 分数；
- 解释稳定 tie-break；
- 区分检索准确率和召回率；
- 添加多文档/多语言回归测试；
- 找出生产检索器仍需增强的位置。

## 原理：当前算法

Agent-Me 使用一个刻意简单的词法基线：

1. 在 `KNOWLEDGE_DIR` 递归寻找 Markdown；
2. 拒绝 symlink、越界路径、非法 UTF-8 和过大文件；
3. 把每个非空 Markdown block 变成候选 chunk；
4. 保留 ATX 标题文字但移除 `#`；
5. 先做 Unicode NFKC 规范化与大小写折叠，再将 Unicode 单词和每个汉字分词；
6. 从 query token 中移除一小组明确的英文停用词；
7. 计算其余 query token 与 chunk token 的交集；
8. 分数为 `|Q ∩ P| / max(|Q|, 1)`，默认拒绝低于 `0.75` 的结果；
9. 按分数降序，再按路径和片段稳定排序；
10. 默认最多返回四个 match。

该分数类似 query coverage，但不理解词频、罕见度、语义、顺序、否定或段落是否真的回答问题。阈值只是保守拒答规则，不能证明语义蕴含。

简单基线的价值在于分数可解释、无外部服务、测试快速稳定，后续改进也有对照；它不是先进检索质量声明。

## 运行时 I/O 与缓存边界

只有文件系统签名不变时，API 才会复用不可变的 `Document` 解析结果。每次访问仍会扫描元数据，
并重新执行根目录、symlink、文件类型和大小检查；新增、修改或删除 Markdown 都会让缓存失效。
API route 会在线程池运行同步扫描与检索，避免阻塞 FastAPI 的 async event loop。

这是进程内性能缓存，不是存储或事实来源。进程重启后缓存为空，配置的文件系统始终是权威来源。

## 阅读实现

先打开 [`backend/app/text.py`](../../../../backend/app/text.py) 阅读 `normalized_tokens`，再打开
[`backend/app/knowledge.py`](../../../../backend/app/knowledge.py)，依次读 `_query_tokens`、
`_content_chunks`、`documents`、`search` 和数据类；再阅读
[`test_knowledge.py`](../../../../backend/tests/test_knowledge.py)，把每个安全分支对应到测试。

## 动手实验

运行聚焦测试：

```bash
.venv/bin/pytest -q backend/tests/test_knowledge.py
```

观察真实 token 与得分：

```bash
.venv/bin/python - <<'PY'
from app.knowledge import _query_tokens
from app.text import normalized_tokens
q = "How does the agent plan a project?"
p = "For project planning, the example agent starts with user goals."
print("query:", sorted(_query_tokens(q)))
print("chunk:", sorted(normalized_tokens(p)))
print("overlap:", sorted(_query_tokens(q) & normalized_tokens(p)))
print("score:", len(_query_tokens(q) & normalized_tokens(p)) / len(_query_tokens(q)))
PY
```

`_query_tokens` 是私有 helper，这里只用于学习探针，不应成为应用外部依赖。
`normalized_tokens` 由检索评分与协作覆盖率指标共同使用。它采用 NFKC 加大小写折叠，
所以组合形式 `résumé` 与分解形式 `re\u0301sume\u0301` 会得到相同 token。

打印排序结果：

```bash
.venv/bin/python - <<'PY'
from app.knowledge import KnowledgeBase
for rank, m in enumerate(KnowledgeBase("knowledge").search(
    "How does the example agent plan a project?"
), 1):
    print(rank, m.score, m.document.path)
    print(m.excerpt, "\n")
PY
```

每次只换一个名词，观察结果何时消失、何时一个通用词带来意外匹配。

### 编写回归测试

使用 pytest `tmp_path` 创建两个 Markdown 文档，验证：

- 覆盖更好的文档排名第一；
- 返回路径是相对 POSIX 路径；
- 同分排序稳定；
- `limit=1` 只返回一个；
- 无关问题无结果。

再次运行 `test_knowledge.py`。

## 准确率与召回率

若有三个真正相关的 chunk：

- **Recall@4：**前三个相关 chunk 有多少进入前四；
- **Precision@4：**前四结果有多少真正相关。

召回高但准确率低会让 critic 面对噪声；准确率高但召回低可能漏掉关键限定条件。权衡取决于语料大小、问题类型、时延和上下文限制。

### 文件安全边界

加载器拒绝 symlink、越出根目录的解析路径、超大文件、非法 UTF-8、非目录配置。这些保护文件系统边界，不保证 Markdown 事实可信。内容审核和授权是另一层责任。

## 练习

### 必做：多语言检索

在临时测试目录建立英文/CJK 小语料，验证两种语言都有确定性结果，并说明“每个 CJK 字符一个 token”的重要限制。

### 中级：调整最小分数

用 `search(..., min_score=...)` 测试 0、恰好等于边界和高于所有结果，并新增一个与语料共享词汇的 hard-negative fixture。解释阈值如何改变准确率、召回率和拒答，同时不能证明 entailment。

### 高级：比较排序方法

实验 BM25 或 semantic ranking。除非有版本化相关性标签、量化对比、依赖/隐私评审和延迟/失败说明，否则不要直接替换基线。

## 理解检查

1. 稳定 tie-break 对测试和事故分析有什么价值？
2. 使用 token set 会丢失什么信息？
3. 高 overlap 能证明 entailment 吗？
4. 哪些控制保护文件系统，哪些保护回答质量？
5. 召回提高但 grounded 误报增加时，下一步检查什么？

## 完成清单

- [ ] 能手算 overlap 分数。
- [ ] 追踪了加载、分块、分词、排序、限制。
- [ ] 运行了检索测试。
- [ ] 新增多文档或多语言回归用例。
- [ ] 能解释本系统的 precision/recall。
- [ ] 能说出至少三个词法基线限制。

## 延伸阅读

- [Python pathlib](https://docs.python.org/zh-cn/3/library/pathlib.html)
- [scikit-learn 文本特征](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction)
- [Ranked retrieval evaluation](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-ranked-retrieval-results-1.html)

---

**上一课：[第 01 课](../01-grounded-qa/README.md)** · **下一课：[第 03 课：设计协作角色](../03-role-design/README.md)**
