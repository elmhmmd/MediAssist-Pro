# MediAssist Pro — Agent Handoff Document

## What This Project Is

RAG-based REST API for biomedical lab equipment support. Lab technicians ask questions in natural language; the system retrieves relevant chunks from a PDF technical manual and generates precise, sourced answers using an LLM (Ollama/mistral). The project also includes MLflow observability, DeepEval quality metrics, Prometheus/Grafana monitoring, Kubernetes deployment, and a GitHub Actions CI/CD pipeline.

---

## Current State: FULLY IMPLEMENTED

Everything in Brief.md is implemented. There is nothing left to build. The remaining manual steps before the CI/CD pipeline can run are documented in the "Prerequisites Before Running" section below.

---

## Project Structure

```
MediAssist Pro/
├── app/
│   ├── main.py                  # FastAPI app entrypoint, Prometheus instrumentation, lifespan
│   ├── core/
│   │   ├── config.py            # Settings via pydantic-settings + .env
│   │   └── security.py          # bcrypt password hashing, JWT encode/decode
│   ├── db/
│   │   ├── base.py              # SQLAlchemy engine, session, Base, get_db()
│   │   └── models.py            # User and Query ORM models
│   ├── schemas/
│   │   ├── user.py              # UserCreate, UserOut, Token schemas
│   │   └── query.py             # QueryRequest, QueryOut schemas
│   ├── api/routes/
│   │   ├── auth.py              # POST /auth/register, /auth/login, GET /auth/me
│   │   ├── query.py             # POST /query/, GET /query/history
│   │   └── admin.py             # GET /admin/users, DELETE /admin/users/{id}, GET /admin/stats
│   └── services/
│       ├── auth.py              # register_user, authenticate_user, get_current_user
│       ├── rag.py               # handle_query() — calls ask(), persists to DB
│       └── admin.py             # require_admin, list_users, delete_user, get_global_stats
├── rag/
│   ├── pdf_extractor.py         # pdfplumber-based PDF→text extractor (two-column aware)
│   ├── pdf_chunker.py           # chapter/section-aware chunker → LangChain Documents
│   ├── indexer.py               # build_vectorstore() / load_vectorstore() with ChromaDB
│   ├── retriever.py             # retrieve() — query expansion + MMR reranking
│   ├── rag_pipeline.py          # ask() — full RAG pipeline with MLflow logging
│   └── mlflow_logger.py         # log_rag_config, log_llm_config, log_query_response + DeepEval
├── tests/
│   ├── conftest.py              # SQLite test DB, engine patching, client/db fixtures
│   ├── test_auth.py             # register, login, /me endpoint tests
│   └── test_rag.py              # chunker tests + ask() mock test
├── k8s/
│   ├── namespace.yaml
│   ├── secret.yaml              # SECRET_KEY, POSTGRES_PASSWORD — edit before applying
│   ├── configmap.yaml           # OLLAMA_BASE_URL=http://192.168.49.1:11434, DATABASE_URL, etc.
│   ├── postgres-pvc.yaml
│   ├── postgres-deployment.yaml
│   ├── postgres-service.yaml    # ClusterIP, port 5432
│   ├── chroma-pvc.yaml
│   ├── app-deployment.yaml      # pulls from Docker Hub, mounts chroma PVC
│   ├── app-service.yaml         # NodePort 30080
│   ├── prometheus-config.yaml   # scrape config + alerting rules (configmap)
│   ├── prometheus-deployment.yaml
│   ├── prometheus-service.yaml  # NodePort 30090
│   ├── grafana-datasource.yaml
│   ├── grafana-dashboard.yaml   # pre-built dashboard JSON + provider config
│   ├── grafana-deployment.yaml
│   └── grafana-service.yaml     # NodePort 30030
├── .github/workflows/
│   └── ci-cd.yml                # 3-job pipeline: test → build-push → deploy
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                         # local dev env vars (do NOT commit)
├── data.pdf                     # source technical manual
├── data.txt                     # pre-extracted text from data.pdf
└── chroma_store/                # persisted ChromaDB embeddings (already indexed)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.133, Uvicorn 0.41 |
| Validation | Pydantic v2, pydantic-settings |
| ORM | SQLAlchemy 2.0 |
| Auth | JWT (python-jose), bcrypt |
| Database | PostgreSQL 16 (prod), SQLite (tests) |
| RAG pipeline | LangChain (core, chroma, ollama, text-splitters) |
| Vector store | ChromaDB 1.5, all-MiniLM-L6-v2 embeddings (built-in ONNX) |
| LLM | Ollama — mistral model |
| PDF parsing | pdfplumber 0.11 |
| LLMOps | MLflow 2.22 |
| RAG eval | DeepEval 2.7 (AnswerRelevancy, Faithfulness) |
| Monitoring | prometheus-fastapi-instrumentator 7.1, Prometheus, Grafana |
| Containers | Docker, docker-compose |
| Orchestration | Kubernetes (Minikube for local/CI) |
| CI/CD | GitHub Actions |

---

## API Endpoints

All `/query` and `/admin` routes require a Bearer JWT token.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /auth/register | No | Register user — body: `{username, email, password}`, optional `role: "admin"` |
| POST | /auth/login | No | OAuth2 form login — fields: `username`, `password` → returns `access_token` |
| GET | /auth/me | Yes | Returns current user info |
| POST | /query/ | Yes | Ask a RAG question — body: `{question: "..."}` → returns answer + metadata |
| GET | /query/history | Yes | Returns all past queries ordered by date desc |
| GET | /admin/users | Admin | List all users |
| DELETE | /admin/users/{id} | Admin | Delete a user |
| GET | /admin/stats | Admin | Returns total_users, total_queries, admin_count |
| GET | /health | No | Health check — returns `{"status": "ok"}` |
| GET | /metrics | No | Prometheus metrics endpoint |

---

## Database Models

**users** table: `id`, `username` (unique), `email` (unique), `hashed_password`, `role` (enum: "user"/"admin")

**queries** table: `id`, `query` (text), `reponse` (text), `created_at` (timestamptz)

Tables are auto-created at startup via `Base.metadata.create_all()` in the FastAPI lifespan.

---

## RAG Pipeline (how it works)

1. **PDF extraction** (`pdf_extractor.py`): pdfplumber extracts text from `data.pdf`, handles two-column layouts, strips noise, outputs `data.txt`
2. **Chunking** (`pdf_chunker.py`): splits by chapter (regex `Chapitre N`), then by section (hardcoded French section title patterns), then by `RecursiveCharacterTextSplitter` (chunk_size=800, overlap=150). Each chunk gets metadata: `source`, `chapter`, `chapter_title`, `section`, `chunk_index`, `sub_chunk`
3. **Indexing** (`indexer.py`): embeds chunks with ChromaDB's bundled all-MiniLM-L6-v2 (ONNX, no download needed), persists to `chroma_store/`
4. **Retrieval** (`retriever.py`): query expansion via Ollama (2 reformulations), similarity search (k=10) across all query variants, dedup, then MMR reranking to final k=4
5. **Generation** (`rag_pipeline.py`): builds LangChain chain with system prompt enforcing French responses, sources from context, chapter citations. Calls Ollama mistral. Wrapped in MLflow run.
6. **Evaluation** (`mlflow_logger.py`): optionally runs DeepEval AnswerRelevancy + Faithfulness using Ollama as the eval LLM, logs scores to MLflow

---

## Running Locally (dev)

### Prerequisites
- Python 3.12
- Ollama running locally: `ollama serve` + `ollama pull mistral`
- PostgreSQL running on port 5432 (or use docker-compose)

### Setup
```bash
cd "MediAssist Pro"
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### .env (already exists, check values)
```
DATABASE_URL=postgresql://mediassist:mediassist@localhost:5432/mediassist
SECRET_KEY=<your-secret-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
CHROMA_DIR=chroma_store
OLLAMA_MODEL=mistral
```

### Run with docker-compose (recommended)
```bash
docker compose up --build
```
This starts PostgreSQL on port 5433 (host) and the app on port 8000. Ollama must still run on the host.

### Run bare
```bash
uvicorn app.main:app --reload
```
API docs at http://localhost:8000/docs

### Re-index the PDF (only needed if data.pdf changes)
```bash
# Step 1: extract PDF to text
python rag/pdf_extractor.py data.pdf data.txt

# Step 2: build ChromaDB vectorstore
python rag/indexer.py data.txt --source data.pdf
```
The `chroma_store/` directory already contains indexed embeddings so this is not needed unless you change the document.

### Run tests
```bash
pytest tests/ -v
```
Tests use SQLite (hardcoded in `tests/conftest.py`). No postgres or Ollama needed — RAG tests are fully mocked.

### View MLflow UI
```bash
mlflow ui --backend-store-uri mlruns
```
Open http://localhost:5000 — experiment is called `mediassist-rag`.

---

## Running in Kubernetes (Minikube)

### Prerequisites
1. Install Minikube: `curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 && sudo install minikube-linux-amd64 /usr/local/bin/minikube`
2. Install kubectl: `sudo snap install kubectl --classic`
3. Start cluster: `minikube start --driver=docker`
4. Ollama running on host: `ollama serve`

### Before applying manifests
1. Edit `k8s/secret.yaml` — replace `SECRET_KEY` value with a strong key
2. Find the host IP from Minikube's perspective:
   ```bash
   minikube ssh -- ip route | grep default
   # output example: default via 192.168.49.1 dev eth0
   ```
   The IP (e.g. `192.168.49.1`) is already set in `k8s/configmap.yaml` as `OLLAMA_BASE_URL`. Verify it matches.
3. Edit `k8s/app-deployment.yaml` — replace `DOCKERHUB_USERNAME/mediassist-pro:latest` with your actual Docker Hub image

### Apply everything
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/chroma-pvc.yaml
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/app-service.yaml
kubectl apply -f k8s/prometheus-config.yaml
kubectl apply -f k8s/prometheus-deployment.yaml
kubectl apply -f k8s/prometheus-service.yaml
kubectl apply -f k8s/grafana-datasource.yaml
kubectl apply -f k8s/grafana-dashboard.yaml
kubectl apply -f k8s/grafana-deployment.yaml
kubectl apply -f k8s/grafana-service.yaml
```

### Access services
```bash
minikube service mediassist-service -n mediassist    # app API
minikube service prometheus-service -n mediassist    # Prometheus UI
minikube service grafana-service -n mediassist       # Grafana UI (admin/admin)
```

---

## GitHub Actions CI/CD Pipeline

File: `.github/workflows/ci-cd.yml`

Triggers on push to `main` or `master`.

**Job 1 — test**: installs deps, runs `pytest tests/` with SQLite (no postgres service needed)

**Job 2 — build-push** (needs: test): logs into Docker Hub, builds image, pushes `latest` and `<7-char-sha>` tags

**Job 3 — deploy** (needs: build-push): starts Minikube in the runner, applies all k8s/ manifests, updates app image to the SHA tag, waits for rollout

### GitHub Secrets required
Go to repo → Settings → Secrets and variables → Actions → New repository secret:
- `DOCKERHUB_USERNAME` — your Docker Hub username
- `DOCKERHUB_TOKEN` — Docker Hub access token (Account Settings → Security → New Access Token)

---

## Monitoring

### Prometheus alerts (in `k8s/prometheus-config.yaml`)
- `HighLatencyP95`: p95 response time > 5s for 2 minutes → warning
- `HighErrorRate`: HTTP 5xx rate > 5% for 2 minutes → critical
- `PodNotRunning`: any pod in mediassist namespace not in Running phase → critical

### Grafana dashboard (auto-provisioned)
Pre-built dashboard "MediAssist Pro — RAG Monitoring" with panels:
- Request rate (req/s)
- Latency p50 / p95 / p99
- Error rate
- Pod status

Grafana default login: `admin` / `admin`

---

## Known Issues / Things to Be Aware Of

1. **chroma_store is already indexed** — The `chroma_store/` directory in the repo contains pre-built embeddings for `data.pdf`. In Kubernetes, this store is empty on first deploy (new PVC). You need to either copy the chroma_store into the pod or run the indexer as an init container / manual job after deploy.

2. **Ollama is external** — The project assumes Ollama runs on the host machine, not inside Kubernetes. In the k8s configmap, `OLLAMA_BASE_URL` is set to `http://192.168.49.1:11434`. If your Minikube host IP is different, update `k8s/configmap.yaml`.

3. **DeepEval evaluation is slow** — `log_query_response` with `evaluate=True` runs two full LLM calls through Ollama for scoring. This adds latency to every query response. If this is a problem, pass `log=False` in `ask()` or set `evaluate=False`.

4. **User role assignment** — The `UserCreate` schema accepts a `role` field. There is no restriction preventing a self-registered user from claiming `role: "admin"`. If this is a concern for production, the role field should be removed from the registration endpoint and set server-side.

5. **MLflow runs locally** — MLflow logs to `mlruns/` directory. There is no MLflow server in the k8s manifests. For production, consider adding an MLflow tracking server pod or using a remote tracking URI.
