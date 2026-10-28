# Follow-up retrieval from previous public sources

If the first answer says only “You use Matplotlib,” a follow-up such as “Why did I choose it?”
may have no lexical search hits. Conversation history identifies the tool but may omit the reason
recorded in the original document. The provider does not automatically retain previous requests'
retrieved context.

## Request flow

1. The browser retains successful standard-Q&A exchanges in page memory. Failed, cancelled and
   stale responses do not become history. “New conversation” clears the exchanges and source
   locators. Chats are not written to browser storage.
2. `chatHistory.ts` retains up to ten complete exchanges within the profile's total and per-turn
   character limits. Long answers can be clipped by Unicode code points; questions stay intact.
3. `followup_retrieval.py` searches the current question first. Existing hits take precedence.
4. With no hits, history, previous sources and a configured external provider, it asks
   `KnowledgeBase.revisit_sources` to reread the previous sources. No model performs query rewriting.
5. The answer provider receives the original question, history and newly read context through the
   existing prompt and budget. It is still responsible for acknowledging missing information.

The additive `previous_sources` field contains up to four `{path, excerpt}` locators; see the
[API contract](API.md#post-apiv1chat). Clients that omit it retain the previous retrieval behavior.
The frontend accepts profiles without the new history-budget fields using the existing v1 defaults.
An older server that rejects unknown fields needs upgrading before serving the new frontend.

## Source boundaries

The knowledge base matches paths against `documents()`, which retains existing root, symlink,
file-size and corpus limits. It never opens the request's path directly or treats its excerpt as
trusted context. Current source text is authoritative.

An exact old excerpt locates its current paragraph; single-paragraph locations include the previous
and next paragraphs. A still-present expanded window stays in place on subsequent turns. When
edits invalidate the locator, overlap with the previous and current questions selects a current
paragraph. Deleted paths are skipped, and distinct passages from the same file can be retained.
Each excerpt is capped at 3000 characters and the normal total context budget still applies.
When a single-paragraph exact locator fits within that cap, clipping preserves its original
location and uses the remaining space for neighboring text. Shared query words in a long neighbor
cannot displace the located passage. Expanded windows that still fit remain unchanged on later turns.

Existing direct-search scores retain their meaning. Revisited scores describe overlap with the
previous-plus-current questions; a low score can be returned because this is source revisiting,
not a new threshold-qualified search. Scores are not answer confidence.

Only current public Markdown enters retrieval. Public endpoints do not read the private workspace.
History remains client-supplied and untrusted. The existing provider disclosure covers the question,
recent history and retrieved context; this change adds no server-side conversation persistence.

## Evaluation

Run the deterministic retrieval comparison without credentials or a model:

```bash
.venv/bin/python scripts/evaluate_followup_retrieval.py
```

On Windows use `.venv/Scripts/python.exe`. The fixture has four synthetic fact families, each with
history containing the reason, only the document containing it, or neither containing it, plus
English and Chinese topic switches. It checks source recall; it does not score generated answers.

The [saved live comparisons](../course/examples/followup-retrieval/README.md) separately record final
answer quality and latency. The 28 paired comparisons with a query-rewriting baseline produced
identical final answer payloads, with median latency 5.71s for rewriting and 2.61s for source reuse.
They are small synthetic experiments, not a production success-rate or latency guarantee.

Regression tests cover the real chat route with a mock provider (one upstream call, unchanged
question/history), updated/deleted sources, client-forged locators, long documents, distinct
same-file passages, repeated follow-ups and topic switches. Frontend tests cover failed retries,
conversation reset and history budgets. No model downloads or new dependencies are required.

## Limitations and rollback

This fallback does not determine whether a direct search hit is sufficient or relevant. It can miss
details far from the cited passage or in other documents, and it cannot resolve every subject
switch. It leaves the existing local extractive and collaboration modes unchanged. If previously
referenced public documents have changed, earlier answer text can still exist in client history;
source refresh does not retract that history from the model.

Rollback restores current-question-only retrieval at the chat route and stops sending source
locators from the frontend. No database migration or persistent conversation cleanup is needed.

The new UI strings were machine-assisted across the existing locale dictionaries and checked for
type completeness; they have not had independent native-speaker review.
