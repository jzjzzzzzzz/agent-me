# Lesson 06 — Evaluation, Tests, and Failure Injection

[Previous: Critic and observability](../05-critic-observability/README.md) · [Course home](../README.md) · [简体中文](../translations/zh-CN/06-evaluation/README.md) · [Next: Production capstone](../07-production-capstone/README.md)

**Time:** 60–90 minutes · **Level:** Intermediate · **Produces:** new cases and a detected failure

## Why this lesson matters

A demo answers one selected question at one moment. An evaluation states what behavior is expected
for a versioned set of cases and fails automatically when the implementation disagrees. Tests and
evaluations answer different questions, so a trustworthy project needs both.

## Learning objectives

By the end, you can:

- distinguish unit, contract, integration, security, and behavioral evaluation;
- explain the fixture schema and evaluator exit codes;
- design supported, unsupported, boundary, and adversarial cases;
- calculate grounded-decision precision and recall;
- inject a failure and verify CI-relevant detection;
- report results with dataset scope instead of exaggerated quality claims.

## Quality layers

| Layer | Example | Primary question |
| --- | --- | --- |
| Unit test | critic with no matches blocks | Does one component preserve an invariant? |
| Contract test | malformed stage order is rejected | Do producer and consumer agree on shape? |
| Integration test | FastAPI route returns four stages | Do components work together? |
| Security test | oversized body is rejected | Does an abuse boundary hold? |
| Behavioral evaluation | expected grounded decision | Does user-visible behavior match labeled cases? |
| Container smoke test | built services answer a request | Does the packaged stack run? |

No single layer substitutes for all others.

## Evaluation fixture

[`course/fixtures/collaboration_cases.json`](../fixtures/collaboration_cases.json) is a nonempty array:

```json
{
  "id": "project-planning",
  "question": "How does the example agent plan a project?",
  "expected_grounded": true
}
```

The evaluator enforces unique case IDs, validates exact keys and value types, runs retrieval and
orchestration, records source count and critic outcome, and exits:

- `0` when all expectations pass;
- `1` when behavior disagrees with labels;
- `2` when fixture or environment setup is invalid.

Stable, unique case IDs let CI map a case across runs and compare regressions without confusing two
different examples that share a label.

That distinction helps CI separate a product regression from a broken evaluation file.

## Read the implementation

Read [`scripts/evaluate_collaboration.py`](../../scripts/evaluate_collaboration.py) from fixture validation through result construction, human/JSON rendering, and exit-status selection. Then inspect the evaluation job in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) to see how a local failure becomes a pull-request failure.

## Hands-on lab

### Step 1 — run readable output

```bash
make evaluate
```

Expected baseline:

```text
case    expected    actual    sources    critic    result
...
COLLABORATION_EVAL 3/3 passed
```

### Step 2 — run machine-readable output

```bash
.venv/bin/python scripts/evaluate_collaboration.py --json > /tmp/agent-me-eval.json
python3 -m json.tool /tmp/agent-me-eval.json
```

CI uses this form because it is deterministic and parsable.

### Step 3 — add a small evaluation matrix

Add at least three cases:

1. a direct supported fact;
2. an unsupported domain question;
3. a paraphrase with fewer exact tokens.

Use unique stable IDs. Expected labels must come from the committed corpus, not from what the current
code happens to return.

### Step 4 — inject failure

Change one `expected_grounded` value to the opposite, then:

```bash
make evaluate
echo $?
```

Verify the case fails and exit status is `1`. Restore the correct label.

Next, make the JSON malformed or add an unknown key. Verify exit status `2`, then restore it. You
have now observed behavior and setup failures separately.

### Step 5 — run the complete quality gate

```bash
make lint
make test
make docs
make evaluate
```

If Docker is available:

```bash
make build
```

## Designing evaluation categories

A useful starter set includes:

### Supported

- exact sentence lookup;
- paraphrase;
- evidence split across chunks/documents;
- ambiguous question with one supported interpretation;
- English and CJK input.

### Unsupported

- unrelated specialist domain;
- nearby vocabulary without the requested fact;
- false premise;
- requested personal/private information absent from the public corpus.

### Adversarial and boundary

- prompt-like text asking the system to ignore evidence;
- HTML/script-looking input treated as plain text;
- blank, malformed, and oversized bodies;
- many repeated tokens;
- Unicode and intentional line breaks.

Behavioral fixtures should avoid real private prompts and should be licensed for public use.

## Precision and recall for grounded decisions

Treat `grounded=true` as a positive prediction:

| | Expected supported | Expected unsupported |
| --- | ---: | ---: |
| Predicted grounded | true positive | false positive |
| Predicted blocked | false negative | true negative |

```text
precision = TP / (TP + FP)
recall    = TP / (TP + FN)
```

- Low precision means unsupported questions often proceed.
- Low recall means supported questions often abstain.

Always publish case count and label scope with a metric. “100%” on three simple fixtures is not a
general quality claim.

## Avoid evaluation leakage

If you tune logic repeatedly against the same tiny fixtures, the suite becomes a development set.
A stronger workflow separates:

- development cases used during implementation;
- regression cases for known bugs;
- held-out review cases checked less frequently;
- production feedback sampled and sanitized under a documented policy.

Version the corpus and evaluation cases together so changed knowledge does not silently invalidate
labels.

## Exercises

### Required — add measured cases

Add at least three cases covering three categories above. Run evaluation and write:

- case count;
- grounded confusion matrix;
- precision and recall;
- one known limitation;
- corpus commit/version.

### Intermediate — extend evaluator assertions

Add an optional expectation such as minimum source count while preserving strict fixture validation.
Update tests, schema documentation, and existing fixtures. Distinguish missing from intentionally
unset expectations.

### Advanced — mutation/failure experiment

Temporarily mutate one behavior: reverse rank order, remove the critic block, or weaken response
parsing. Predict which checks should fail before running them. If nothing fails, add the missing
regression test.

## Check your understanding

1. Why can all unit tests pass while behavioral quality regresses?
2. Who should own expected labels?
3. What does exit code `2` communicate?
4. Why is 3/3 not enough for a “production accuracy” claim?
5. How can repeated tuning leak evaluation knowledge into the implementation?

## Completion checklist

- [ ] I can classify each repository quality check by layer.
- [ ] I ran readable and JSON evaluation output.
- [ ] I added at least three justified cases.
- [ ] I observed exit codes `1` and `2` deliberately.
- [ ] I calculated a confusion matrix, precision, and recall.
- [ ] I reported limitations and dataset scope with results.

## Further reading

- [pytest documentation](https://docs.pytest.org/)
- [Vitest guide](https://vitest.dev/guide/)
- [Google testing blog: test sizes](https://testing.googleblog.com/2010/12/test-sizes.html)

---

**Previous: [Lesson 05](../05-critic-observability/README.md)** · **Next: [Lesson 07 — Production design and capstone](../07-production-capstone/README.md)**
