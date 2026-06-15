# 🚀 CoRaCommit

English | [中文](README.zh-CN.md)

CoRaCommit is a VS Code extension for automated commit message generation. It uses retrieval-augmented examples from a commit-message corpus and LLM-based generation to produce commit messages from Git diffs.

The RAG corpus and embedding resources used by this project are built from the ApacheCM dataset.

## ✨ Overview

CoRaCommit consists of three runtime layers:

- **VS Code extension**: collects Git diffs and displays generated commit messages.
- **Node API service**: orchestrates retrieval, prompt construction, LLM calls, feedback, and model scoring.
- **Python backend**: provides embedding, FAISS retrieval, SQLite document lookup, and optional evaluation endpoints.

The full RAG corpus is built from the **ApacheCM dataset**. The committed `resource_demo/` directory is a small ApacheCM-derived sample for quickstart and smoke testing only.

## ⚡ Quick Start

### 📦 Prerequisites

- Conda or Miniconda
- Python 3.10.x in the `coracommit_env` environment
- Node.js 18+ and npm
- VS Code 1.85+

### 1. Clone

```bash
git clone https://github.com/T-rresa/CoRaCommit.git
cd CoRaCommit
```

### 2. Create `coracommit_env`

```powershell
conda env create -f fusion_search/environment.yml
conda activate coracommit_env
```

### 3. Verify demo RAG resources

The repository includes `resource_demo/`, a small backend-ready sample. Verify that it can be loaded by the backend resource manager:

```powershell
conda run -n coracommit_env python fusion_search/verify_backend_resources.py --resource-dir ../resource_demo --models codebert
```

Expected result:

```text
[INFO] docs.db rows=32
[INFO] codebert: index_ntotal=32 doc_ids=32 top_commit_id=0
[DONE] Backend resources are loadable.
```

### 4. Start the Python backend with demo resources

PowerShell:

```powershell
cd backend
$env:RESOURCE_PATH="..\resource_demo"
$env:EMBEDDING_MODEL="codebert"
conda run -n coracommit_env python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

cmd.exe:

```bash
cd backend
set RESOURCE_PATH=..\resource_demo
set EMBEDDING_MODEL=codebert
conda run -n coracommit_env python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check:

```powershell
curl http://127.0.0.1:8000/api/health
```

### 5. Start the Node API

Open a second terminal:

```powershell
cd node_service
npm ci
$env:PORT="3001"
$env:RETRIEVAL_BACKEND_URL="http://127.0.0.1:8000"
$env:EVALUATION_BACKEND_URL="http://127.0.0.1:8000"
npm run start
```

Check:

```powershell
curl http://127.0.0.1:3001/api/health
```

Then verify that Node can call the Python retrieval backend:

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:3001/api/similarity-search" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"diff":"diff --git a/a.txt b/a.txt\n+hello"}'
```

The response should contain a `matches` array.

### 6. Run the VS Code extension

Open a third terminal:

```powershell
cd vscode_extension
npm ci
npm run compile
```

Open `vscode_extension/` in VS Code and press `F5`. The extension defaults to the local Node API at `http://localhost:3001/api`.

## 🧩 Runtime Modes

### Single Python Backend

Recommended for local development. `app.main` exposes retrieval, embedding, and evaluation routes from one process:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use the same URL for both Node settings:

```bash
set RETRIEVAL_BACKEND_URL=http://127.0.0.1:8000
set EVALUATION_BACKEND_URL=http://127.0.0.1:8000
```

### Split Retrieval and Evaluation Backends

Recommended for production-like deployment. Online retrieval and background evaluation run separately:

```bash
uvicorn app.main_retrieval:app --host 127.0.0.1 --port 8000
uvicorn app.main_evaluation:app --host 127.0.0.1 --port 8001
```

Then configure Node with:

```bash
set RETRIEVAL_BACKEND_URL=http://127.0.0.1:8000
set EVALUATION_BACKEND_URL=http://127.0.0.1:8001
```

## 🗂️ Data and RAG Resources

The production retrieval corpus is derived from the ApacheCM dataset. The expected raw input is a JSONL file containing at least:

- `diff`
- `message`
- `repo`
- `commit_sha`

Place the full ApacheCM file at:

```text
fusion_search/data/raw/apachecm/full.jsonl
```

Build full RAG resources:

```bash
cd fusion_search
conda activate coracommit_env
python main.py build-index codebert
python main.py build-index jina
python main.py export-backend --output-dir ../resource
python verify_backend_resources.py --resource-dir ../resource --models codebert jina
```

For a quick resource-only smoke test against the committed demo resources, run this from the repository root:

```powershell
conda run -n coracommit_env python fusion_search/verify_backend_resources.py --resource-dir ../resource_demo --models codebert
```

Expected resource layout:

```text
resource/
  docs.db
  docs.jsonl
  embeddings/
    codebert.doc_ids.npy
    codebert.vecs.npy
    jina.doc_ids.npy
    jina.vecs.npy
  faiss/
    codebert.index
    jina.index
```

The backend `commit_id` is the source row id (`0`, `1`, `2`, ...). The same ids must be used by `docs.db` and `embeddings/*.doc_ids.npy`.

## 🧱 Repository Layout

```text
backend/          FastAPI retrieval, embedding, and evaluation services
node_service/     Node API, LLM orchestration, feedback queue, scoring
vscode_extension/ VS Code extension
fusion_search/    ApacheCM embedding and resource export scripts
experiment/       Experiment scripts and configs
resource_demo/    Small committed quickstart resource
```

## 🐳 Docker Deployment

Generate or provide `resource/` first, then run:

```bash
docker compose -f docker-compose.deploy.yml up -d --build
```

The compose stack starts retrieval backend, evaluation backend, Node API, Node worker, Redis, and MySQL. See `DEPLOY.md` for deployment details.
