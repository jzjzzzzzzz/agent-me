# Deployment

1. Copy `.env.example` into a secret-managed environment configuration.
2. Set exact `CORS_ORIGINS`; do not use a wildcard for credentialed applications.
3. Mount a reviewed, read-only knowledge directory.
4. Build pinned container images and place TLS at the ingress.
5. Apply network rate limiting at the edge and request-size limits at the proxy.
6. Keep provider credentials in a secret manager and rotate them regularly.
7. Monitor `/health` and `/ready` without logging request bodies.

The included Compose file is intended for local evaluation. Production deployments should use a managed ingress, runtime secret injection, immutable images, and automated backups for any persistence you add.
