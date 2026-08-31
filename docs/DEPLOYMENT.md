# Deployment

1. Copy `.env.example` into a secret-managed environment configuration.
2. Set exact `CORS_ORIGINS`; do not use a wildcard for credentialed applications.
3. Mount a reviewed, read-only knowledge directory.
4. Build pinned container images and place TLS at the ingress.
5. Apply network rate limiting at the edge and set its request-size limit no higher than the application's `MAX_REQUEST_BODY_BYTES` defense-in-depth limit.
6. Keep provider credentials in a secret manager and rotate them regularly.
7. Monitor `/health` and `/ready` without logging request bodies.

The included Compose file is intended for local evaluation. It binds both services to loopback, runs the API with all Linux capabilities dropped, runs both services with read-only root filesystems and `no-new-privileges`, and gives Nginx only the capabilities and temporary filesystems it needs. Set `API_BIND` or `WEB_BIND` only when you intentionally need a non-loopback development listener.

Production deployments must keep the application behind a TLS ingress; do not expose the API container directly.  Production deployments should use a managed ingress, runtime secret injection, immutable images, and automated backups for any persistence you add.

## Refresh pinned base images

Each Dockerfile keeps a readable image tag and pins the corresponding multi-platform image index
by digest. Dependabot checks the backend and frontend Dockerfiles weekly so digest changes remain
visible and reviewable. To inspect the current tags manually, run:

```bash
docker buildx imagetools inspect python:3.12-slim
docker buildx imagetools inspect node:22-alpine
docker buildx imagetools inspect nginx:1.27-alpine
```

Copy the reported top-level `Digest` into the matching `FROM tag@sha256:...` instruction without
removing the tag or changing its major version. Then run the same container checks as CI:

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
