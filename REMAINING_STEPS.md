# Remaining Steps

## Prerequisites (do these manually before running the pipeline)

### Docker Hub
- Create an account at https://hub.docker.com if you don't have one
- Create a repository named `mediassist-pro` (can be private)
- Generate an access token: Account Settings → Security → New Access Token
- Add to GitHub repository secrets:
  - `DOCKERHUB_USERNAME` — your Docker Hub username
  - `DOCKERHUB_TOKEN` — the access token you generated

### Minikube
- Install: `curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 && sudo install minikube-linux-amd64 /usr/local/bin/minikube`
- Install kubectl: `sudo snap install kubectl --classic`
- Start cluster: `minikube start --driver=docker`
- Verify: `kubectl get nodes`

---

## Step 1 — Update requirements.txt & rebuild Docker image

Add `mlflow` and `deepeval` to `requirements.txt` then rebuild and push.

---

## Step 2 — Kubernetes Manifests (`k8s/`)

Files to create:
- `namespace.yaml` — `mediassist` namespace
- `secret.yaml` — `SECRET_KEY`, `POSTGRES_PASSWORD`
- `configmap.yaml` — `OLLAMA_BASE_URL`, `CHROMA_DIR`, `OLLAMA_MODEL`, `DATABASE_URL`
- `postgres-deployment.yaml` — Postgres 16 pod + PersistentVolumeClaim
- `postgres-service.yaml` — ClusterIP service so the app pod can reach Postgres
- `app-deployment.yaml` — app pod, pulls image from Docker Hub, mounts chroma_store volume
- `app-service.yaml` — NodePort service to expose the API (accessible via `minikube service`)

### Ollama in Minikube
Minikube runs inside Docker so `host.docker.internal` won't resolve to your host by default.
Fix: use `minikube ssh -- ip route` to get the host IP and set `OLLAMA_BASE_URL` in the configmap to `http://<host-ip>:11434`.

---

## Step 3 — GitHub Actions CI/CD (`.github/workflows/ci-cd.yml`)

Pipeline triggers on push to `main`/`master`:

1. **test** job
   - Spin up Python 3.12
   - Install dependencies
   - Run `pytest tests/`

2. **build-push** job (needs: test)
   - Log in to Docker Hub using secrets
   - Build image with BuildKit cache
   - Tag as `<DOCKERHUB_USERNAME>/mediassist-pro:latest` and `:<sha>`
   - Push both tags

3. **deploy** job (needs: build-push)
   - Set up Minikube in the runner
   - Apply all `k8s/` manifests
   - Update the app deployment image to the new SHA tag
   - Wait for rollout to complete: `kubectl rollout status deployment/mediassist-app -n mediassist`

---

## Step 4 — Prometheus & Grafana Monitoring

### What to instrument in the app
Add `prometheus-fastapi-instrumentator` to expose `/metrics` endpoint automatically.
Metrics exposed:
- Request count, latency, error rate (automatic)
- Custom RAG metrics: query count, response time, MLflow-logged quality scores

### Prometheus
- Runs as a pod in Minikube
- Scrapes `/metrics` from the app pod
- Config: `prometheus.yml` with scrape interval and app target

### Grafana
- Runs as a pod in Minikube
- Datasource: Prometheus
- Dashboard panels:
  - CPU/RAM (from kube-state-metrics)
  - Pod status
  - Request latency (p50, p95, p99)
  - Error rate
  - RAG query count
  - Answer relevancy / Faithfulness scores (from MLflow metrics pushed to Prometheus)

### Alerting rules
- Latency p95 > 5s → alert
- Error rate > 5% → alert
- Pod not running → alert
- Answer relevancy < 0.5 → alert
