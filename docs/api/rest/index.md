# REST API

OSSS exposes a REST/JSON API described by an OpenAPI schema and served via the FastAPI app.

## Interactive API docs

When OSSS is running, you can browse the live API documentation at:

- FastAPI interactive docs (Swagger UI) at `/docs`
- ReDoc (if enabled) at `/redoc`

These routes are served directly by the FastAPI application.

## OpenAPI schema

The OpenAPI schema is available at:

- `/openapi.json` from the running backend
- Or as a generated file in the docs build, under `api/python/openapi.json` (exported by the docs tooling)

You can download this schema and use it to:

- Generate client SDKs
- Configure API gateways
- Drive additional documentation tools

## Authentication

Most endpoints are protected and require an authenticated request:

- Use your configured Keycloak / identity provider to obtain an access token.
- Include the token in the `Authorization: Bearer <token>` header.

## Rate limiting and usage

OSSS is designed for internal school/district use. If you are exposing the API externally:

- Put OSSS behind a reverse proxy (e.g., NGINX, Envoy).
- Configure any rate limiting and WAF rules at the proxy layer.
- Monitor usage via OSSS audit logs and your infrastructure metrics.
