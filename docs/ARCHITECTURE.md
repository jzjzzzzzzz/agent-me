# Architecture

## Trust boundaries

1. Browser questions are untrusted and validated by Pydantic.
2. Knowledge files are operator-controlled but bounded by the configured root and file-size limit; symbolic links are rejected and content is rendered as plain text.
3. Provider output is untrusted and rendered as text, never inserted as HTML.
4. Secrets are loaded from environment variables and excluded from source control.

## Request path

`POST /api/v1/chat` validates the body, enforces the configured question limit, tokenizes the question, scores Markdown paragraphs by token overlap, and returns up to four sources. If all provider settings are present, the service calls the provider's `/chat/completions` route using a grounded system message. Otherwise it returns the highest-ranked excerpt.

The starter does not persist requests. Add a database only when the product needs persistence, and document the purpose, retention, and access controls before collecting data.
