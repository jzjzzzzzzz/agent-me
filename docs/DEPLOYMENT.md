# Deployment

1. Copy `.env.example` into a secret-managed environment configuration.
2. Set exact `CORS_ORIGINS`; do not use a wildcard for credentialed applications.
3. Mount a reviewed, read-only knowledge directory.
4. Build pinned container images and place TLS at the ingress.
5. Apply network rate limiting at the edge and request-size limits at the proxy.
6. Keep provider credentials in a secret manager and rotate them regularly.
7. Monitor `/health` and `/ready` without logging request bodies.

The included Compose file is intended for local evaluation. It binds both services to loopback, runs the API with all Linux capabilities dropped, runs both services with read-only root filesystems and `no-new-privileges`, and gives Nginx only the capabilities and temporary filesystems it needs. Set `API_BIND` or `WEB_BIND` only when you intentionally need a non-loopback development listener.

Production deployments must keep the application behind a TLS ingress; do not expose the API container directly.  Production deployments should use a managed ingress, runtime secret injection, immutable images, and automated backups for any persistence you add.
