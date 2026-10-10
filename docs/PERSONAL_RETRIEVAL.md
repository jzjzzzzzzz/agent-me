# Personal retrieval and grounded answers

The pure Agent core now provides local `ask`, `retrieve`, and `verify` operations. They share typed
contracts and run without an HTTP server, model provider, `.env`, or frontend. Remaining roadmap
work is tracked in the [acceptance ledger](AGENT_IMPLEMENTATION.md).

## How an answer is formed

1. Route the **owner's question**, never source instructions, to recall/profile/preferences/projects/
   timeline/relationships. Callers can specify the intent instead of relying on bounded heuristics.
2. Resolve an explicit ID/alias or a detected confirmed entity mention. Ambiguous aliases require
   clarification, not a guessed merge. Owner identity binding is explicit.
3. Combine lexical matches, controlled field synonyms, aliases, current reviewed relationships,
   temporal selection and optional public/private Markdown. This hybrid does not require a vector
   service or graph backend; it is not a general embedding-semantic or unrestricted NLP guarantee.
4. Apply subject, current/historical privacy, temporal and optional confidence limits before assembly.
5. Detect differing accepted values of common semantic field aliases such as `identity.name` and
   `profile.name`. They become disputed, not two confident biographical assertions. This is a bounded
   field-consistency check, not general natural-language contradiction detection.
6. Assemble whole evidence records within count/character budgets. A presentation preference cannot
   evict the only primary answer. Preferences alone never establish an unsupported factual answer.
7. Draft typed atomic values and re-read current authority before verification/composition.

Every result includes evidence IDs/paths/revisions, belief, effective sensitivity, declared confidence,
observation/episode/validity time, deterministic match reasons, context size, and public stage outcomes.
Traces contain counts/outcomes, not private reasoning. A `known` result means exact source-backed values,
not proof of real-world truth or semantic entailment of an arbitrary paraphrase.

## Atomic claims and live verification

Claims have a constrained kind, subject, field, literal value, belief, declared confidence and one evidence
ID. Supported kinds are memory values, declared episode times, document quotations, owner-curated entity
labels, and reviewed relationship triples. A compound source paragraph remains a quotation; the system
does not pretend it has verified every implied proposition inside it.

`ClaimVerifier` recomputes eligible authoritative retrieval for the original request. It does not trust
caller-supplied excerpts or a claimed verified status. Changed/deleted/sensitive/newly unreviewed evidence,
changed values/subjects/fields/confidence, and out-of-budget records invalidate a claim. Uncertain beliefs
stay `uncertain`; style/context-only records cannot verify factual assertions.

The composer emits only literal verified/uncertain values with paths, never unconstrained generated
personal facts. Rejected stale claims and their old text are omitted from the answer object, including
when deletion occurs between retrieval and verification. Subsequent mutations after verification are
not a global cancellation mechanism; returned evidence describes its verified observation point.

No model provider is called by this new grounded-local path, even when the legacy service is configured
with `LLM_*`. The existing `/personal/chat` remains the separate reference generated/extractive-chat
contract; it does not acquire these stronger atomic guarantees. This separation preserves compatibility
and does not falsely label arbitrary existing provider prose as verified.

## Owner scope and uncertainty

Use `entity owner ID` or `/identity/owner` to bind a confirmed person as the local owner's identity.
The workspace owner UUID remains the ownership identifier; the bound entity is a separately curated
subject. Entity labels are identifiers, not certified legal names.

Profile/self questions include bound owner memory and conventional unbound owner fields, not a friend's
entire profile. Explicit subject questions do not borrow another person's matching field. Public fictional
repository examples and untimed/unbound Markdown cannot establish the owner's identity. Unknown or
hidden subjects remain unknown; sensitive aliases/records require owner opt-in.

Answer states are `known`, `partial`, `unknown`, `disputed`, `inferred`, `outdated`, and `ambiguous`.
Expired evidence can explain lack of a current answer, but an old version of a field becomes context-only
when an eligible current value already answers it. This prevents expired project information from
polluting a current-project assertion. Confidence is not fabricated: a minimum-confidence filter excludes
null/insufficient scores, including derived relationship evidence whose supporting memory lacks a score.

## Time and relationships

`as_of` is a declared-validity point; `known_at` is an observation cutoff. `since`/`until` form a half-open
validity/episode window. Explicit controls override natural time recognition. The bounded local router
recognizes English `in/during/year YYYY`, Chinese `YYYY年`, `last year`/`去年`, and `yesterday`/`昨天` using UTC
calendar windows. Multiple different implicit years require explicit bounds; complex expressions should
use the typed controls instead of relying on a guess.

Declared `occurred_at`, not learning time, answers "when" questions. An undated episode may be returned
as context, but it cannot fabricate the event date. Distinct episodes/windows are not mistaken for a
contradiction merely because they share a key. Untimed Markdown and current-only entity labels/relationship
triples are excluded from historical/window claims; dated ingested memories can supply historical evidence.

Current relationships are owner-reviewed edges with fresh confirmed memory evidence and confirmed
endpoints. Their triples are not inferred from nearby lexical matches. A changed/deleted supporting
revision removes the relationship from answer context. Relationship predicates are still owner assertions;
source linking alone does not prove their semantic truth.

## Documents and privacy

Native callers may supply public/private `KnowledgeBase` objects. The CLI uses the workspace's
`knowledge/` directory as private Markdown and only adds public documents when the owner explicitly
passes `--public-knowledge`. The authenticated API uses its existing configured public/private roots.
Paths are namespaced (`public/knowledge`, `private/knowledge`, `memory`, `identity`, `relationship`).

KnowledgeBase's existing symlink/file/corpus limits remain enforced. No arbitrary URL or path is fetched
from a question. Private Markdown remains manually maintained knowledge, not automatically classified
PII; structured sensitivity labels do not magically classify those files. The local path sends no context
outside the deployment. Source instructions remain quoted data and never grant tool authority.

## Local CLI

From the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --help
```

New operations (IDs come from the existing identity/memory list operations):

| Command | Purpose |
| --- | --- |
| `entity owner` / `entity owner ID` / `entity owner --clear` | Inspect, bind or clear the owner's confirmed person subject |
| `ask QUESTION` | JSON grounded answer, literal claims, live verification and trace |
| `retrieve QUESTION` | Inspect hybrid evidence selection without composing an answer |
| `verify FILE` | Revalidate bounded JSON VerifyRequest against live authority |

`ask`/`retrieve` support intent, subject ID/alias, `as_of`, `known_at`, `since`, `until`, sensitive opt-in,
minimum confidence, record/context budgets, locale, document opt-out, and an explicit public knowledge root.
Use `--help` on the operation for exact flags. Verification files are limited to 256 KiB. Unknown answers
are valid successful queries, not CLI errors. No ask operation silently persists a new belief or action.

## API

All paths have prefix `/api/v1/personal`, require the existing owner token, and use `Cache-Control: no-store`.

| Method | Route | Contract |
| --- | --- | --- |
| POST | `/ask` | AskRequest → PersonalAnswer |
| POST | `/retrieve` | AskRequest → RetrievalResult |
| POST | `/verify` | `{request: AskRequest, claims: AtomicClaim[]}` → VerifiedClaim[] |
| GET / POST | `/identity/owner` | Inspect / set `{entity_id: ID or null}` |

AskRequest controls are strictly typed; question/context are also bounded by server configuration.
Verification results distinguish exact source matches, uncertain beliefs, absent current context,
altered claims and non-factual presentation/context evidence. The optional owner-subject binding is
included in version-5 private export, not in public profile or public Q&A.

## Evaluation

```bash
make evaluate-retrieval
```

Expected: `RETRIEVAL_EVAL 16/16 passed`. Cases include bilingual/synonym support beyond lexical overlap,
profile and preference fidelity, unsupported questions, temporal/current projects, absent learning history,
known/unknown episode time, sensitive opt-in, relationship retrieval/deletion, ambiguity, semantic-field
conflicts and injection-as-data. Tests additionally cover namespace collisions, budgets, forged claims,
live deletion, confidence filters, owner scoping, API/CLI behavior and absence of provider calls.
The suite contains positive and negative cases; disabling field support is tested to make it fail.
