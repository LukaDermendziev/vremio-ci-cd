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

## CI/CD (GitHub Actions → Docker Hub)

On every push to `master`, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs tests, then builds and pushes:

`lukad23/vremio-web:latest` and `lukad23/vremio-web:<short-sha>`

Image: [https://hub.docker.com/r/lukad23/vremio-web](https://hub.docker.com/r/lukad23/vremio-web)

GitHub secrets used (not stored in git):

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

## Kubernetes (minikube)

Same four services, as Kubernetes objects. Manifests are in [`k8s/`](k8s/).

| Course object | What we use it for |
|---|---|
| Namespace | `vremio` |
| ConfigMap | Django / DB host settings |
| Secret | dummy `DJANGO_SECRET_KEY` and DB password |
| StatefulSet | PostgreSQL (`db`) + PVC |
| Deployment | Redis, Django (`web`), nginx |
| Service | in-cluster DNS: `db`, `redis`, `web`, `nginx` |
| Ingress | `vremio.local` → nginx → Django |

Docker Desktop must be running. Then:

```powershell
minikube start --driver=docker
minikube addons enable ingress
kubectl apply -k infra/k8s
kubectl -n vremio get pods
```

Wait until all pods are `Running` / `Ready`. Pulling `lukad23/vremio-web:latest` from Docker Hub can take a minute.

**Option A — Ingress** (what the course asks for):

```powershell
minikube ip
```

Add that IP to `C:\Windows\System32\drivers\etc\hosts` (run Notepad as Administrator):

```
<minikube-ip> vremio.local
```

If `http://vremio.local` does not open, in another terminal (Administrator):

```powershell
minikube tunnel
```

Then open http://vremio.local/health/

**Option B — NodePort** (easier on Windows if Ingress is picky):

```powershell
minikube service nginx -n vremio
```

That opens the app in the browser. Health: add `/health/` to the URL.

Remove the demo (does not touch Railway):

```powershell
kubectl delete -k infra/k8s
# optional: minikube stop
```
