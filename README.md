# CoRaCommit

CoRaCommit is a VS Code extension for generating commit messages from staged
Git diffs. It retrieves similar historical commit-message pairs, invokes
multiple LLMs in parallel, and records user selection/editing feedback to
update model recommendations.

## What it does

- Extracts the staged Git diff and preprocesses it locally (masking, truncation).
- Retrieves similar commit exemplars from an ApacheCM-derived corpus.
- Generates candidate messages from one or more LLMs in parallel.
- Shows candidates side by side for selection and editing.
- Updates global and exemplar-level LLM scores from user feedback.

## Quick start (Docker, recommended)

### Fastest: one command (services + extension)

```bash
./scripts/install.sh
```

Windows PowerShell:

```powershell
.\scripts\install.ps1
```

This replaces the old three-terminal workflow: one command starts the stack,
waits for health, and installs the packaged extension. The installer copies
`.env.deploy.example` to `.env` if needed, pulls the prebuilt images (falling
back to a source build), waits for the health checks, and installs
`release/coracommit-2.1.0.vsix` with `code --install-extension`. Use
`./scripts/install.sh --source` to force a local image build.

After it finishes, reload the VS Code window
(`Developer: Reload Window`) and continue with
[Configure and use](#3-configure-and-use).

### Manual steps

#### 1. Start the services

Fastest path: pull the prebuilt images published on GHCR (no local build).

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
`ghcr.io/t-rresa/coracommit-node:2.1.0`, starts Redis/MySQL, initializes the
database, and waits for health checks. The images are `linux/amd64`; the
backend image includes CodeBERT, so the first request needs no Hugging Face
download.

To build the images from source instead (development or reproduction):

```bash
cp .env.deploy.example .env
./scripts/start_local.sh
```

```powershell
Copy-Item .env.deploy.example .env
.\scripts\start_local.ps1
```

The source-build script builds the retrieval backend, evaluation backend, Node
API, worker, Redis, and MySQL, initializes the database, and waits for health
checks.

Host ports (all configurable in `.env`; change them if a port is already in
use):

| Service | Default port | `.env` variable |
|---|---:|---|
| Retrieval backend | 8000 | `RETRIEVAL_PORT` |
| Evaluation backend | 8001 | `EVALUATION_PORT` |
| Node API | 3001 | `NODE_API_PORT` |
| MySQL | 3306 | `MYSQL_HOST_PORT` |
| Redis | 6379 | `REDIS_HOST_PORT` |

#### 2. Install the extension

A packaged `.vsix` is attached to the GitHub Release. If you are working from a
clone, build it once:

```bash
./scripts/package_extension.sh
```

Install it:

```bash
code --install-extension release/coracommit-2.1.0.vsix
```

Then reload the VS Code window (`Developer: Reload Window`).

> 📷 **Screenshot placeholder:** `docs/images/extension-installed.png` — the
> Extensions view showing `CoRaCommit` installed, or the CoRaCommit icon in the
> activity bar after reload.

#### 3. Configure and use

1. Open the CoRaCommit sidebar in VS Code.
2. Set the backend URL if needed:
   ```json
   "auto-gen-message.apiUrl": "http://localhost:3001/api"
   ```
3. Click **Set API Key** and provide a key for your model family
   (GPT / Qwen / DeepSeek). Keys are stored in VS Code SecretStorage.
4. Stage a change in Git.
5. Choose models, template, format, and language.
6. Click **Generate**.
7. Compare candidates, select or edit one, and commit.
8. Open the leaderboard to inspect feedback-driven model scores.

> 📷 **Screenshot placeholder:** `docs/images/sidebar.png` — the sidebar with a
> staged diff, API key status, model selection, and the **Generate** button.

> 📷 **Screenshot placeholder:** `docs/images/candidates.png` — three candidate
> messages with model names and latency, one selected, and the edit/commit area.

> 📷 **Screenshot placeholder:** `docs/images/leaderboard.png` — the model
> leaderboard and 7-day usage trend.

**What you should see**

- The sidebar lists the processed staged diff (the first Generate may take
  10–30 s while CodeBERT loads).
- The candidate panel shows one row per model: model name, latency, and message.
- Selecting a row fills the commit input box; **Commit Changes** commits it.
- The leaderboard updates after selection/editing feedback is scored by the
  background worker.
- In mock mode the message starts with `[MOCK:<model>]`.

### No API key? Use mock mode

For a smoke test without any LLM key:

1. In `.env`, set:
   ```text
   ALLOW_MOCK_LLM=true
   RESOURCE_DIR=resource_demo
   ```
2. Restart the stack with the compose file you started with:
   ```bash
   docker compose -f docker-compose.release.yml up -d   # prebuilt images
   # or: docker compose -f docker-compose.deploy.yml up -d   # source build
   ```
3. In VS Code settings, set:
   ```json
   "auto-gen-message.mockLLM": true
   ```
4. Generate as usual; the backend returns mock messages.

## Local development (without Docker)

This path is for contributors who want to run the services from source. End
users should use the one-command installer or the Docker quick start above.
It needs MySQL, Redis, Conda, Node.js, and VS Code. See
[`docs/QUICKSTART.md`](docs/QUICKSTART.md) for the full step-by-step commands.

```bash
conda env create -f fusion_search/environment.yml
conda activate coracommit_env

# Terminal 1: Python backend
cd backend
RESOURCE_PATH=../resource_demo EMBEDDING_MODEL=codebert \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Node API
cd node_service
cp .env.example .env
npm ci
npm run init-db
npm run init-model-scores
npm run start:api

# Terminal 3: extension
cd vscode_extension
npm ci
npm run compile
```

Then open `vscode_extension/` in VS Code and press `F5`.

**What happens after F5** (this is extension development, not the user path):

1. VS Code opens a second window titled `[Extension Development Host]`.
2. In that window, click the CoRaCommit icon in the activity bar.
3. The sidebar connects to `http://localhost:3001/api`.
4. Set an API key, stage a change, and click **Generate**.
5. After code changes, press `F5` again or reload the development host.

End users should install the packaged `.vsix` instead of running F5.

Windows PowerShell equivalents are in [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

## Architecture

```text
VS Code extension
  -> Node API / worker (orchestration, prompts, LLMs, feedback)
    -> Python retrieval backend (CodeBERT/Jina, FAISS, BM25)
    -> Python evaluation backend (metrics)
      -> SQLite/FAISS resources, MySQL, Redis
```

## Data and RAG resources

The committed `resource_demo/` is a 32-document ApacheCM sample for quickstart
and smoke tests. Build the full corpus from ApacheCM:

```bash
cd fusion_search
conda activate coracommit_env
python main.py build-index codebert
python main.py build-index jina
python main.py export-backend --output-dir ../resource
python verify_backend_resources.py --resource-dir ../resource --models codebert jina
```

Set `RESOURCE_DIR=resource` in `.env` to use the full corpus.

## Prebuilt Docker images

Images are published to GitHub Container Registry by
[`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml)
on every `v*` tag:

| Image | Contents | Tags |
|---|---|---|
| `ghcr.io/t-rresa/coracommit-backend` | Python 3.10, CPU PyTorch, CodeBERT, FAISS, FastAPI | `2.1.0`, `2.1`, `2`, `latest`, `sha-*` |
| `ghcr.io/t-rresa/coracommit-node` | Node 20 API, evaluation worker, DB initializers | `2.1.0`, `2.1`, `2`, `latest`, `sha-*` |

The application images run as non-root users and carry OCI labels. The corpus
is not baked into the images; mount it with `RESOURCE_DIR` (`resource_demo` by
default). Override image tags with `BACKEND_IMAGE` / `NODE_IMAGE` in `.env`.

If the packages are private, log in once:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
```

On networks where Docker Hub is slow, point the base images at a mirror in
`.env`:

```text
MYSQL_IMAGE=docker.1ms.run/library/mysql:8.0
REDIS_IMAGE=docker.1ms.run/library/redis:7-alpine
```

For maintainers, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#prebuilt-images-ghcr)
for manual `docker buildx` commands, digests, and the release checklist.

Tagging `v2.1.0` also runs
[`release.yml`](.github/workflows/release.yml), which builds the `.vsix` and
release bundle and attaches them (with `checksums.txt`) to the GitHub Release.
`./scripts/install.sh` installs from that packaged `.vsix`; no second VS Code
instance or three-terminal setup is needed.

## Documentation

| Document | Contents |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | Docker, local, and mock-mode startup |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | API keys, configuration, generation, feedback |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | Extension settings, environment variables, ports |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Docker, MySQL/Redis, resource build, maintenance |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Common failures and fixes |
| [`docs/PRIVACY_SECURITY.md`](docs/PRIVACY_SECURITY.md) | Diffs, keys, and data handling |

## Troubleshooting

- **Port already in use**: change `RETRIEVAL_PORT` / `EVALUATION_PORT` /
  `NODE_API_PORT` / `MYSQL_HOST_PORT` / `REDIS_HOST_PORT` in `.env` and restart.
  This is common when a local MySQL already listens on 3306; set
  `MYSQL_HOST_PORT=13306` and keep `DB_PORT=3306` (the port inside Docker).
- **MySQL authentication error**: verify `MYSQL_ROOT_PASSWORD` and `DB_PASSWORD`
  match in `.env`.
- **Redis connection error**: verify `REDIS_HOST=redis` in Docker mode or
  `localhost` in local mode.
- **Resource not found**: check `RESOURCE_DIR` and `RESOURCE_PATH`.
- **401 / invalid API key**: set the key again from the sidebar; the key family
  must match the selected model.
- **No staged changes**: run `git add` before generating.

## Privacy and security

- API keys are stored in VS Code SecretStorage, not in workspace settings.
- Diffs are preprocessed locally (tokens/credentials masked) before being sent
  to the backend and LLM provider.
- A self-hosted deployment keeps diffs and feedback on your server.
- See [`docs/PRIVACY_SECURITY.md`](docs/PRIVACY_SECURITY.md).

## License and citation

MIT License. If you use CoRaCommit in academic work, cite the accompanying
Science of Computer Programming software paper.

- Repository: https://github.com/T-rresa/CoRaCommit
- Dataset: https://zenodo.org/records/16926172