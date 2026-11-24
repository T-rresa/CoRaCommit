# Quick start

Three paths:

1. **Docker** (recommended): one command for the service stack.
   - **Prebuilt images** (fastest): pull the released GHCR images.
   - **Source build**: build the images locally.
2. **Local development**: MySQL/Redis + Python + Node + extension.
3. **Mock mode**: no API key, for UI smoke tests.

## Prerequisites

- Docker Desktop / Docker Engine + Compose (Docker path)
- Or: Conda, Python 3.10, MySQL 8, Redis 7, Node.js 18+, npm, VS Code 1.85+
- A Git repository with staged changes

## Path 1: Docker

### 1a. Prebuilt images (recommended)

One command for the services **and** the extension:

```bash
./scripts/install.sh
```

Windows PowerShell:

```powershell
.\scripts\install.ps1
```

If you only want the backend, start it separately:

```bash
cp .env.deploy.example .env
./scripts/start_release.sh
```

Windows PowerShell:

```powershell
Copy-Item .env.deploy.example .env
.\scripts\start_release.ps1
```

This pulls `ghcr.io/t-rresa/coracommit-backend:2.1.0` and
`ghcr.io/t-rresa/coracommit-node:2.1.0` instead of building. The images are
`linux/amd64`; if your Docker daemon has no network access to GHCR, mirror them
or use the source build below.

### 1b. Source build

```bash
cp .env.deploy.example .env
./scripts/start_local.sh
```

Windows PowerShell:

```powershell
Copy-Item .env.deploy.example .env
.\scripts\start_local.ps1
```

The script builds and starts:

| Service | Default host port | `.env` variable | Purpose |
|---|---:|---|---|
| retrieval-backend | 8000 | `RETRIEVAL_PORT` | embeddings + FAISS retrieval |
| evaluation-backend | 8001 | `EVALUATION_PORT` | message metrics |
| node-api | 3001 | `NODE_API_PORT` | extension API |
| mysql | 3306 | `MYSQL_HOST_PORT` | feedback, scores, logs |
| redis | 6379 | `REDIS_HOST_PORT` | evaluation queue |

It also runs `init_db.js` and `init_model_scores.js` before the Node API starts.

If a port is already taken (a local MySQL on 3306 is common), set the matching
`*_PORT` / `*_HOST_PORT` variable in `.env` and restart. The container-internal
ports do not change, so `DB_PORT=3306` and `REDIS_PORT=6379` stay as they are.

Health checks:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8001/api/health
curl http://127.0.0.1:3001/api/health
```

### Install the extension

```bash
./scripts/package_extension.sh
code --install-extension release/coracommit-2.1.0.vsix
```

Set the backend URL in VS Code settings if the default is not used:

```json
"auto-gen-message.apiUrl": "http://localhost:3001/api"
```

Open the CoRaCommit sidebar, set an API key, stage a change, and click
**Generate**.

> 📷 **Screenshot placeholder:** `docs/images/sidebar.png` — the sidebar with a
> staged diff and the **Generate** button.

### First success checklist

1. Reload the VS Code window after installing the `.vsix`
   (`Developer: Reload Window`).
2. Health checks return 200:
   ```bash
   curl http://127.0.0.1:8000/api/health
   curl http://127.0.0.1:8001/api/health
   curl http://127.0.0.1:3001/api/health
   ```
3. The CoRaCommit icon is visible in the activity bar.
4. Open the sidebar; it shows the staged diff after `git add`.
5. Click **Set API Key** and choose the family that matches the selected model.
6. Click **Generate**; the candidate panel shows model, latency, and message.
7. Select a candidate, edit if needed, and click **Commit Changes**.

If you have no API key, use the mock mode below. The candidate message will
start with `[MOCK:<model>]`.

## Path 2: Local development

### 1. Python environment

```bash
conda env create -f fusion_search/environment.yml
conda activate coracommit_env
```

### 2. MySQL and Redis

Create the database:

```sql
CREATE DATABASE auto_gen_message;
```

Start Redis locally (or use Docker):

```bash
docker run -p 6379:6379 redis:7-alpine
```

### 3. Node API

```bash
cd node_service
cp .env.example .env
# edit DB_PASSWORD / DB_NAME / REDIS_HOST if needed
npm ci
npm run init-db
npm run init-model-scores
npm run start:api
```

The API listens on `http://127.0.0.1:3001`.

### 4. Python backend

```bash
cd backend
RESOURCE_PATH=../resource_demo EMBEDDING_MODEL=codebert \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
cd backend
$env:RESOURCE_PATH="..\resource_demo"
$env:EMBEDDING_MODEL="codebert"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. Extension

```bash
cd vscode_extension
npm ci
npm run compile
```

Open `vscode_extension/` in VS Code and press `F5`. This path is for extension
development only.

**After F5:**

1. A new `[Extension Development Host]` window opens.
2. Click the CoRaCommit icon in its activity bar.
3. The sidebar connects to `http://localhost:3001/api`.
4. Set an API key, stage a change, and click **Generate**.
5. Re-run `F5` after code changes.

End users should install the packaged `.vsix` instead.

## Path 3: Mock mode (no API key)

Use this for a complete UI smoke test without any LLM account.

1. In `.env` (Docker) or `node_service/.env` (local), set:
   ```text
   ALLOW_MOCK_LLM=true
   ```
2. For Docker, set `RESOURCE_DIR=resource_demo` and restart with the compose
   file you started with:
   ```bash
   docker compose -f docker-compose.release.yml up -d   # prebuilt images
   # or: docker compose -f docker-compose.deploy.yml up -d   # source build
   ```
3. In VS Code settings, set:
   ```json
   "auto-gen-message.mockLLM": true
   ```
4. Generate as usual. The backend returns messages prefixed with `[MOCK:model]`.

This path does not call any external LLM API.

## Smoke test

```bash
./scripts/smoke_test.sh
```

Windows:

```powershell
.\scripts\smoke_test.ps1
```

## Next

- [USER_GUIDE.md](USER_GUIDE.md): how to use the extension.
- [CONFIGURATION.md](CONFIGURATION.md): settings and environment variables.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md): common failures.