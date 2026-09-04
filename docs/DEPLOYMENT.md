# Deployment

Read [Trust, Data Flow, and Deployment Boundaries](TRUST.md) before deploying. The included stack is
a reproducible local reference environment, not a production-ready hosted platform.

1. Copy `.env.example` into a secret-managed environment configuration.
2. Set exact `CORS_ORIGINS`; do not use a wildcard for credentialed applications.
3. Mount a reviewed, read-only knowledge directory.
4. Build pinned container images and place TLS at the ingress.
5. Apply network rate limiting at the edge and set its request-size limit no higher than the application's `MAX_REQUEST_BODY_BYTES` defense-in-depth limit.
6. Keep provider credentials in a secret manager and rotate them regularly.
7. Monitor `/health` and `/ready` without logging request bodies.

`MAX_DOCUMENT_BYTES` limits each Markdown file. `MAX_KNOWLEDGE_DOCUMENTS` and
`MAX_KNOWLEDGE_BYTES` independently limit the document count and aggregate bytes in one corpus
snapshot. The defaults are 1 MB per file, 256 documents, and 16 MB total. Tune them to the reviewed
corpus and available memory rather than disabling the bounds; a limit violation fails readiness,
chat, and collaboration closed with a path-free `503`.

The included Compose file is intended for local evaluation. It binds both services to loopback, runs the API with all Linux capabilities dropped, runs both services with read-only root filesystems and `no-new-privileges`, and gives Nginx only the capabilities and temporary filesystems it needs. Set `API_BIND` or `WEB_BIND` only when you intentionally need a non-loopback development listener.

The web image sends browser requests to same-origin `/api` by default. Its Nginx configuration
proxies that path to the Compose service `api:8000`, avoiding browser-visible internal hostnames and
cross-origin configuration for the normal stack. If web and API are deployed into different
networks, either provide an equivalent ingress route or set `VITE_API_BASE_URL` at image build time
and configure an exact matching `CORS_ORIGINS` value. Do not set `VITE_API_BASE_URL=/api`; it is an
origin prefix and would duplicate the API path.

Production deployments must keep the application behind a TLS ingress; do not expose the API container directly.  Production deployments should use a managed ingress, runtime secret injection, immutable images, and automated backups for any persistence you add.

## Refresh locked Python dependencies

The backend image installs the exact direct and transitive graph recorded in `backend/uv.lock`.
CI runs a locked sync and fails when `backend/pyproject.toml` and the lock disagree. For an
intentional dependency change:

```bash
# Edit backend/pyproject.toml first, then:
make lock
uv lock --project backend --check
make lint
make test
make evaluate
make build
```

Review the complete lock diff, including source URLs and hashes. Do not hand-edit the lock or
replace the locked install with an unconstrained `pip install`. The backend Dockerfile also pins
the uv installer image by digest so both the resolver input and installer are reviewable.

## Refresh pinned base images

Each Dockerfile keeps a readable image tag and pins the corresponding multi-platform image index
by digest. Dependabot checks the backend and frontend Dockerfiles weekly so digest changes remain
visible and reviewable. To inspect the current tags manually, run:

```bash
docker buildx imagetools inspect python:3.14-slim
docker buildx imagetools inspect ghcr.io/astral-sh/uv:0.12.7
docker buildx imagetools inspect node:22-alpine
docker buildx imagetools inspect nginx:1.31-alpine
```

Copy the reported top-level `Digest` into the matching `FROM tag@sha256:...` instruction without
removing the readable tag. Keep digest-only refreshes separate from version changes; for a version
change, review upstream release/support notes and explain the compatibility decision. Then run the
same container checks as CI:

```bash
cp -n .env.example .env
docker compose config --quiet
docker compose up --detach --build --wait
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/ready
curl --fail --silent --show-error http://127.0.0.1:8000/api/v1/collaborate \
  --header 'Content-Type: application/json' \
  --data '{"question":"How does the example agent plan a project?"}' \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["grounded"] and len(data["trace"]) == 4'
curl --fail --silent --show-error http://127.0.0.1:5173/ >/dev/null
docker compose down --volumes
```

Do not merge a digest refresh unless both images build and all four smoke checks pass. Review any
base-image release notes independently; an immutable digest makes the selected content stable but
does not establish that the update is safe.
