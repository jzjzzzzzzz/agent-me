# Owner-reviewed provider disclosure

Atomic personal `ask/retrieve/verify`, deterministic learning, identity, retention, local tools, owner
control and their CLI commands remain provider-free. Optional [scoped model-assisted literal learning](SEMANTIC_LEARNING.md)
adds a separately consented adapter for exact source quotations; broad Markdown grants never enable it. Optional legacy `/api/v1/personal/chat` generation
now requires **both** a matching enabled workspace policy and `allow_provider: true` on
each request. Configuring credentials alone does not enable private disclosure. Default
private chat is extractive/local, including when the public provider is configured.

## Policy and target binding

`DisclosureManager` runs without HTTP/configuration/provider imports. Its revisioned
policy includes disabled-by-default `enabled`, a required SHA-256 `target_id` when enabled,
allowed labels and namespaces, and optional exact entity, memory-ID and document-path
allowlists. Default namespaces are `public` and `memory`; private Markdown is excluded.
The API checks the policy target against the configured endpoint/model pair. Changing
that pair requires new owner review. The fingerprint is private metadata, not a provider
authenticity certificate, and does not contain or export API credentials.

Questions are classified `private` at this boundary; a public-only policy cannot transmit
them. Arbitrary question text and Markdown are not automatically PII-classified. Memory
uses live record/entity label floors; sensitive evidence additionally needs per-request
`allow_sensitive: true`. Namespaces are server-tagged, not inferred from document names.
`entity_ids=[]` excludes bound subjects; `memory_ids=[]` excludes all memories;
`document_paths=[]` excludes all documents. Null allowlists impose no additional restriction.
Private document selectors use `private/relative/path.md`; public selectors use
`public/relative/path.md`. These are selection names, never arbitrary-path file operations.

Before authorization, documents are refreshed and current known/confirmed memory values,
revisions, subjects, labels and validity are rechecked. Stale/edited/deleted context does
not enter the outbound body. The entire source record must fit the existing context budget.
Stored transcript is never sent. The provider configuration is copied for the dispatch so
the SDK uses the same endpoint/model that was authorized.

Authorization emits a content-free `disclosure.authorize` event with eligible-source counts;
it does not claim successful delivery. Network delivery is outside the SQLite transaction.
Revocation blocks future authorizations, not already authorized/in-flight external delivery.
Provider-held copies cannot be rolled back or erased by local memory deletion. Generated
free prose remains the legacy contract, not an automatically certified atomic answer.

## Owner interfaces

| Method | `/api/v1/personal` route | Contract |
| --- | --- | --- |
| GET | `/disclosure/target` | Configured boolean and opaque current target ID, no credentials/URL |
| GET | `/disclosure/policy` | Revision and typed policy |
| POST | `/disclosure/policy` | `{expected_revision, policy}`; target must match configured provider |
| POST | `/chat` | `{question, allow_provider: true, allow_sensitive?: false}` plus all policy gates |

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo disclosure policy
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo disclosure configure \
  --expected-revision 1 --policy-json '{"enabled":true,"target_id":"REVIEWED_64_HEX_TARGET_ID","labels":["private"],"namespaces":["memory"]}'
```

CLI `disclosure` commands manage policy without calling the provider or reading credentials. Obtain
the target through the authenticated API, explicit-file `semantic review`, or
`app.disclosure.target_id(base_url, model)` using owner-known configuration. Only `semantic ingest`
can dispatch a CLI model call, with an explicitly supplied private configuration file, reviewed hashes/
revisions and per-attempt consent. Ambient environment/`.env` is never used by that adapter.
Memory preferences and imported instructions cannot enable disclosure.

Schema/export `8` adds `disclosure_policy`. Migration defaults it to disabled. Portable
import accepts versions 6/7/8, places prior disclosure grants into inert archives, and
leaves the live provider policy disabled. SQLite purge resets it as well. Tests inspect
real HTTP request bodies through `httpx.MockTransport`, including dual opt-in, target
change, sensitive/entity privacy, record/document selection, revocation and import.

## Raw learning-source selectors

The semantic adapter uses reserved `learning-source/<SHA256-source-ID>` selectors in the existing
`document_paths` allowlist, together with private namespace/labels. They are not filesystem paths and
cannot match the public/private Markdown selection prefixes. Each delivery additionally carries an
explicit reviewed target and exact UTF-8 content digest plus source/policy revisions. Source/subject/
learning/disclosure state is revalidated after network I/O before candidate storage; completed replay
also needs current authority. See [semantic learning](SEMANTIC_LEARNING.md) for the full boundary.
The legacy private-question opt-in contract remains separate and unchanged; the shared policy does
not automatically send questions or sources merely because credentials/labels are configured.
