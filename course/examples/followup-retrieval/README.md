# Follow-up source revisiting: synthetic evaluation

The previous answer may name a tool without repeating the personal reason recorded in its source.
A follow-up such as “Why that one?” can identify the tool through history but retrieve no text.
The fix revisits the previous public source locally before making the usual single answer request.
See the [implementation guide](../../../docs/FOLLOWUP_RETRIEVAL.md).

## Offline reproduction

From the repository root, with the normal development dependencies installed:

```bash
.venv/bin/python scripts/evaluate_followup_retrieval.py
```

On Windows use `.venv/Scripts/python.exe`. All 14 synthetic source-recall cases pass without a
model or network call: 12 source-revisit cases across four fact families and two topic switches.
The missing-reason cases still retrieve the tool document; source recall alone does not establish
that a question is answerable.

## Saved live answer comparisons

Both experiments used the same `deepseek-flash` model and original answer prompt at baseline commit
`504eab3e300ed21b60a871182535531989610c97`, with fixed identical histories, original questions,
context budgets and provider defaults. Each has 14 cases repeated twice with alternating arm order.
There is no first-turn generation in the paired measurements.

`original-vs-rewrite.json` compares current-question-only search (`old`) against an extra LLM query
rewrite plus optional subject-anchor search (`new`). The eight cases whose reasons existed only
in the corpus changed from safe refusal to answers giving the actual reason. Histories already
containing the answer usually worked without rewriting. One rewrite connection timeout remains
recorded; it was not silently retried. This motivated testing local source reuse.

`rewrite-vs-reuse.json` compares that rewriting baseline (`new`) against source revisiting
(`source_reuse`):

| Measure | Rewrite | Source reuse |
| --- | --- | --- |
| Completed answers | 28/28 | 28/28 |
| Final-answer review passed | 28/28 | 28/28 |
| API requests | 56 | 28 |
| Median elapsed time | 5.71s | 2.61s |
| P95 elapsed time | 10.18s | 3.44s |
| Mean total tokens | 657.8 | 215.9 |

All 28 pairs produced identical **final answer request bodies**, including retrieved context.
The median of per-pair time savings was 3.28s. This differs from subtracting the two medians.
The requests here contain short synthetic documents; they do not show equivalence for long,
cross-document or ambiguous conversations, or establish production accuracy and latency.

The review checked actual personal reasons, explicitly missing reasons and topic switches, rather
than counting HTTP success or source hits as correct answers. Core reasons were reproducible Python
figures, an editable club SVG requirement, a lab handoff file requirement and logger connector
compatibility. Labels and costs were hidden during review, but the same assistant reviewed all
answers; this is not independent human evaluation. Partial answers and execution failures in the
first experiment are preserved separately.

## Evidence format

`cases.json` supplies the fixed public synthetic facts and histories. Each live evidence JSON
contains the original results-file hash, common instructions, model/defaults, all paired answers,
request timings and API usage, review labels/mapping, and the original summary. Request bodies are
deduplicated by a canonical JSON SHA256 in `requests_by_sha256`; each call references its body hash.
No authorization headers, credentials, private documents, local paths or hidden reasoning text
are included. Original result hashes identify the source exports; canonical request hashes use
the format recorded in each file.

The experiments were run before extracting this focused PR from a larger local research workspace.
Production behavior and the answer prompt were preserved when extracting it; unrelated model
experiments and the query-rewrite implementation are not part of this change. The committed offline
runner and regression tests reproduce retrieval behavior. Repeating the live comparisons requires
an external provider and is not claimed to be an offline check.
