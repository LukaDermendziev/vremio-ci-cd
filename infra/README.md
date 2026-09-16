# Faculty CI/CD demo (КИИИ)

This folder is **only** for the university project. The live salon stays on Railway and is not started from these files.

## Four services

| Service | Container | Role |
|---|---|---|
| nginx | `vremio-nginx` | Browser entry, reverse proxy |
| web | `vremio-web` | Django + Gunicorn |
| db | `vremio-postgres` | PostgreSQL (data volume) |
| redis | `vremio-redis` | Cache (`CACHE_URL`) |

## Run with Docker Compose

From the repo root, with Docker Desktop running:

```bash
docker compose up --build
```

Open http://localhost:8080

Health check: http://localhost:8080/health/

Stop:

```bash
docker compose down
```

Dummy env is in `infra/compose.env` (not production secrets).
