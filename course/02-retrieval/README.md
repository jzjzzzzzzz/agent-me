# Lesson 02 — Build and Test the Retrieval Pipeline

[Previous: Grounded Q&A](../01-grounded-qa/README.md) · [Course home](../README.md) · [简体中文](../translations/zh-CN/02-retrieval/README.md) · [Next: Role design](../03-role-design/README.md)

**Time:** 60–75 minutes · **Level:** Beginner–Intermediate · **Produces:** a retrieval regression test

## Why this lesson matters

Most grounded-system failures are decided before a writer role runs. If document loading drops a
heading, chunking separates a key qualifier, tokenization mishandles a language, or ranking favors
a generic paragraph, downstream roles receive the wrong evidence.

A retriever should be treated as a testable subsystem with explicit inputs, outputs, limits, and
quality measures—not as a mysterious database call.

## Learning objectives

By the end, you can:

- trace loading → chunking → tokenization → scoring → ranking;
- calculate the reference implementation's overlap score by hand;
- explain deterministic tie-breaking;
- distinguish retrieval precision from recall;
- add a focused regression test for multiple documents;
- identify where a production retriever would need stronger controls.

## The current algorithm

Agent-Me uses a deliberately small lexical baseline:

1. recursively find Markdown files under `KNOWLEDGE_DIR`;
2. reject symlinks, paths outside the root, invalid UTF-8, oversized files, or an oversized corpus;
3. turn each nonempty Markdown block into a candidate chunk;
4. retain ATX heading text while stripping heading markers;
5. apply Unicode NFKC normalization and case folding, then tokenize Unicode words and individual
   Han characters;
6. remove a small, explicit set of English stop words from query tokens;
7. compute overlap between the remaining unique query tokens and chunk tokens;
8. score `|query ∩ chunk| / |query|` and reject scores below `0.75` by default;
9. sort by descending score, then path and excerpt for stable ties;
10. return at most four matches by default.

For meaningful query token set \(Q\) after stop-word removal and paragraph token set \(P\):

```text
score(Q, P) = |Q ∩ P| / max(|Q|, 1)
```

This resembles query coverage. It does not consider term frequency, document rarity, semantic
similarity, word order, negation, or whether the paragraph actually answers the question. The
threshold is a conservative abstention guard, not proof of entailment.

## Why use a simple baseline?

A deterministic lexical retriever is useful for teaching because:

- every score can be explained;
- no embedding service or vector database is required;
- tests are fast and stable;
- regressions in loading and chunking are visible;
- later improvements can be compared against a known baseline.

Its simplicity is not a claim of state-of-the-art quality.

## Runtime I/O and cache boundary

The API reuses immutable parsed `Document` values only while a filesystem signature is unchanged.
It still scans metadata and repeats the root, symlink, file-type, per-file size, document-count, and
aggregate-byte checks on every access; adding, editing, or removing a Markdown file invalidates the
cached corpus. API routes run the synchronous scan/search in a worker thread so it does not block
FastAPI's async event loop.

This is a process-local performance cache, not storage or a source of truth. A restart begins with
an empty cache, and the configured filesystem remains authoritative.

## Read the implementation

Open [`backend/app/text.py`](../../backend/app/text.py) and then
[`backend/app/knowledge.py`](../../backend/app/knowledge.py). Follow:

1. `normalized_tokens`;
2. `_query_tokens`, `_ATX_HEADING`, and `_content_chunks`;
3. `KnowledgeBase.documents`;
4. `KnowledgeBase.search`;
5. `Match`, `Document`, and `KnowledgeLoadError`.

Then read [`backend/tests/test_knowledge.py`](../../backend/tests/test_knowledge.py). Connect each
security or behavior branch to at least one test.

## Hands-on lab

### Step 1 — run focused tests

```bash
.venv/bin/pytest -q backend/tests/test_knowledge.py
```

### Step 2 — calculate a score

Given:

```text
Question: How does the agent plan a project?
Chunk: For project planning, the example agent starts with user goals.
```

Use a short Python probe to see the actual tokens:

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

The underscore-prefixed query helper is used here only as a learning probe; application code
should not depend on it. `normalized_tokens` is shared by retrieval and collaboration metrics. It
uses NFKC plus case folding, so composed `résumé` and decomposed `re\u0301sume\u0301` produce the
same term.

### Step 3 — inspect ranked matches

```bash
.venv/bin/python - <<'PY'
from app.knowledge import KnowledgeBase
kb = KnowledgeBase("knowledge")
for rank, match in enumerate(kb.search("How does the example agent plan a project?"), 1):
    print(rank, match.score, match.document.path)
    print(match.excerpt, "\n")
PY
```

Change one noun at a time. Observe when results disappear and when a generic token creates an
unexpected result.

### Step 4 — inspect chunk boundaries

Add a temporary file to your branch:

```markdown
# Retrieval Notes

## Constraint
The service must remain offline in local mode.

## Different topic
The garden needs water every morning.
```

Search for `offline constraint`. Confirm the heading and sentence stay in the same normalized
chunk. Delete the temporary file after the experiment unless it is part of your exercise.

### Step 5 — add a regression test

Add a test using `tmp_path` to create two Markdown documents and verify:

- the better-covered document ranks first;
- both returned paths are repository-relative POSIX paths;
- ties are stable;
- `limit=1` returns one match;
- an unrelated question returns no match.

Run:

```bash
.venv/bin/pytest -q backend/tests/test_knowledge.py
```

## Retrieval quality: precision and recall

Suppose a case has three truly relevant chunks.

- **Recall@4:** how many of those relevant chunks appear in the first four results?
- **Precision@4:** how many of the first four results are relevant?

High recall with low precision burdens the critic with noise. High precision with low recall may
omit a qualifier needed for a complete answer. The best tradeoff depends on corpus size, question
type, latency, and downstream context limits.

For this course, relevance labels are human-authored in fixtures. A production evaluation should
record who labeled the data, ambiguity, corpus version, and language.

## Security boundaries in loading

The loader rejects several unsafe or unreliable cases:

- symbolic links that could escape the intended knowledge root;
- resolved paths outside that root;
- files above `MAX_DOCUMENT_BYTES`;
- more than `MAX_KNOWLEDGE_DOCUMENTS` Markdown files;
- a combined Markdown size above `MAX_KNOWLEDGE_BYTES`;
- unreadable or invalid UTF-8 content;
- a configured path that is not a directory.

The first size limit is per file; the latter two bound the whole discovered snapshot. Count and
aggregate-byte failures are determined from metadata before any document body is parsed. The loader
fails the entire snapshot instead of silently skipping files, and readiness, chat, collaboration,
and cache refreshes all use the same limits.

These controls address filesystem trust. They do not make the Markdown factually trustworthy.
Corpus review and authorization are separate responsibilities.

## Exercises

### Required — multilingual retrieval case

Add one small English/CJK Markdown fixture inside a test temporary directory. Verify both languages
produce deterministic matches. Describe the important limitation of treating each CJK character as
a token.

### Intermediate — tune the minimum score

Call `search(..., min_score=...)` with values `0`, a boundary equal to a result score, and a
threshold above all results. Add a hard-negative fixture that shares vocabulary with the corpus.
Explain how the threshold changes precision, recall, and abstention without proving entailment.

### Advanced — compare a second ranking method

Implement a test-only BM25 or semantic-ranking experiment. Do not replace the baseline without:

- versioned relevance labels;
- measured comparison;
- dependency and privacy analysis;
- latency and failure-mode documentation.

## Check your understanding

1. Why does a deterministic tie-break matter in tests and incident analysis?
2. What information is lost by using sets of tokens?
3. Can a high overlap score prove entailment? Why not?
4. Which loader controls protect the filesystem, and which protect answer quality?
5. If recall improves but grounded false positives rise, what should you inspect next?

## Completion checklist

- [ ] I can calculate the overlap score by hand.
- [ ] I traced loading, chunking, tokenization, ranking, and limiting.
- [ ] I ran focused retrieval tests.
- [ ] I added a multi-document or multilingual regression case.
- [ ] I can explain precision versus recall for this system.
- [ ] I can name at least three limitations of the lexical baseline.

## Further reading

- [Python `pathlib`](https://docs.python.org/3/library/pathlib.html)
- [scikit-learn text feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction)
- [Information retrieval evaluation overview](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-ranked-retrieval-results-1.html)

---

**Previous: [Lesson 01](../01-grounded-qa/README.md)** · **Next: [Lesson 03 — Design collaborating roles](../03-role-design/README.md)**
