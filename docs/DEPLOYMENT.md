# Deployment

## One-command install

From the repository root:

```bash
./scripts/install.sh            # prebuilt images + extension
./scripts/install.sh --source   # build images from source, then install the extension
```

PowerShell:

```powershell
.\scripts\install.ps1
.\scripts\install.ps1 -Source
```

The script starts the stack, waits for the three health endpoints, builds the
`.vsix` if needed, and runs `code --install-extension`. This is the supported
user path; the local three-terminal setup is only for contributors.

## Prebuilt images (GHCR)

Recommended for reviewers and users who do not need to modify the code.

```bash
cp .env.deploy.example .env
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

Or use the helper script:

```bash
./scripts/start_release.sh          # Bash
.\scripts\start_release.ps1         # PowerShell
```

| Image | Contents |
|---|---|
| `ghcr.io/t-rresa/coracommit-backend:2.1.0` | Python 3.10 + CPU PyTorch + CodeBERT + FAISS + FastAPI |
| `ghcr.io/t-rresa/coracommit-node:2.1.0` | Node 20 API, evaluation worker, DB initializers |

- Tags: `2.1.0`, `2.1`, `2`, `latest`, and `sha-<commit>`.
- Platform: `linux/amd64`.
- The backend image pre-downloads `microsoft/codebert-base` into
  `HF_HOME=/opt/hf-cache`, so startup does not need Hugging Face access.
- Both application images run as non-root users and carry OCI labels.
- The corpus is mounted from the host (`RESOURCE_DIR`, default
  `resource_demo`) read-only; it is not baked into the image.
- Override the tags with `BACKEND_IMAGE` / `NODE_IMAGE` in `.env` to use a
  mirror or a pinned `@sha256:` digest.

If the GHCR packages are private:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
```

On restricted networks, override the Docker Hub base images in `.env`:

```text
MYSQL_IMAGE=docker.1ms.run/library/mysql:8.0
REDIS_IMAGE=docker.1ms.run/library/redis:7-alpine
```

The application images can also be mirrored with `BACKEND_IMAGE` /
`NODE_IMAGE`.

## Source build

```bash
cp .env.deploy.example .env
docker compose -f docker-compose.deploy.yml up -d --build
```

Windows users can run:

```powershell
Copy-Item .env.deploy.example .env
.\scripts\start_local.ps1
```

## Services

| Service | Role |
|---|---|
| `retrieval-backend` | CodeBERT/Jina embedding + FAISS retrieval |
| `evaluation-backend` | candidate-message metrics |
| `node-api` | extension API, prompts, LLM calls |
| `node-worker` | asynchronous feedback evaluation |
| `redis` | evaluation queue and busy flags |
| `mysql` | feedback logs, LLM scores, stats |
| `db-init` | one-shot schema + score initialization |

## MySQL

- Host port: `3306` (`MYSQL_HOST_PORT` in `.env`; change it if a local MySQL
  already uses 3306)
- Database: `MYSQL_DATABASE` (default `auto_gen_message`)
- User/password: `DB_USER` / `DB_PASSWORD`
- Tables: created by `node_service/init_db.js`
- Initial scores: created by `node_service/init_model_scores.js`

The `db-init` service runs both before the Node API and worker start.

## Redis

- Host port: `6379` (`REDIS_HOST_PORT` in `.env`)
- Used by BullMQ for the evaluation queue and by the priority service for
  online/busy state.

## Resources

The backend reads `RESOURCE_PATH` inside the container (default `/app/resource`).
The host directory is `${RESOURCE_DIR}`:

- `resource_demo` (committed): 32-document quickstart sample.
- `resource` (built from ApacheCM): full corpus.

Build the full corpus:

```bash
cd fusion_search
conda activate coracommit_env
python main.py build-index codebert
python main.py build-index jina
python main.py export-backend --output-dir ../resource
python verify_backend_resources.py --resource-dir ../resource --models codebert jina
```

Then set `RESOURCE_DIR=resource` in `.env` and restart.

## Health checks

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8001/api/health
curl http://127.0.0.1:3001/api/health
```

The commands below work with either compose file. Set `COMPOSE_FILE` once:

```bash
export COMPOSE_FILE=docker-compose.release.yml   # or docker-compose.deploy.yml
docker compose logs -f
```

## Logs

```bash
docker compose logs -f
docker logs -f auto_gen_msg_retrieval
docker logs -f auto_gen_msg_node_api
```

## Stop / reset

```bash
docker compose down
# remove MySQL data (destructive)
docker compose down -v
```

## Updating

Prebuilt images:

```bash
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

Source build:

```bash
git pull
docker compose -f docker-compose.deploy.yml up -d --build
```

If the database schema changed, run the initializer against the same compose
file:

```bash
docker compose -f docker-compose.release.yml run --rm db-init
```

## Building images locally

```bash
docker build --build-arg VERSION=2.1.0 \
  --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
  -t coracommit-backend:2.1.0 ./backend

docker build --build-arg VERSION=2.1.0 \
  --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
  -t coracommit-node:2.1.0 ./node_service
```

The backend build pre-downloads `microsoft/codebert-base` (about 0.5 GB) so the
container does not need Hugging Face at runtime. Pass
`--build-arg PRELOAD_EMBEDDING_MODEL=` to skip that download.

On networks where the default hosts are slow or blocked, all mirrors are
optional build arguments:

```bash
docker build --network=host \
  --build-arg APT_MIRROR=http://mirrors.tuna.tsinghua.edu.cn \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg TORCH_INDEX_URL=https://mirror.sjtu.edu.cn/pytorch-wheels/cpu \
  --build-arg HF_ENDPOINT=https://hf-mirror.com \
  --build-arg VERSION=2.1.0 --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
  -t coracommit-backend:2.1.0 ./backend
```

`--network=host` is needed on Docker Desktop when the engine proxy is set but
unreachable. To run the locally built images through the release compose, set
`BACKEND_IMAGE` / `NODE_IMAGE` in `.env` to the local tags.

## Publishing images (maintainers)

The workflow [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml)
publishes both images to GHCR on any `v*` tag. The companion
[`.github/workflows/release.yml`](../.github/workflows/release.yml) builds the
`.vsix` and release bundle and attaches them (with `checksums.txt`) to the
GitHub Release.

```bash
git tag v2.1.0
git push origin v2.1.0
```

It builds `linux/amd64` images with Buildx layer caching and produces these
tags per image: `2.1.0`, `2.1`, `2`, `latest`, and `sha-<commit>`. The workflow
also supports `workflow_dispatch` with a version input.

Repository settings needed:

- Actions: read and write permissions for the `GITHUB_TOKEN` (or the default
  workflow permissions, which already grant `packages: write` per the workflow
  file).
- Packages: allow the repository to publish packages. The first push creates
  the packages as private; make them public from **Package settings** if the
  release should be downloadable without a token.

Manual build (equivalent to the workflow):

```bash
VERSION=2.1.0
OWNER=t-rresa
SHA=$(git rev-parse --short HEAD)

docker buildx build --platform linux/amd64 \
  --build-arg VERSION=$VERSION --build-arg VCS_REF=$SHA \
  -t ghcr.io/$OWNER/coracommit-backend:$VERSION \
  -t ghcr.io/$OWNER/coracommit-backend:latest --push ./backend

docker buildx build --platform linux/amd64 \
  --build-arg VERSION=$VERSION --build-arg VCS_REF=$SHA \
  -t ghcr.io/$OWNER/coracommit-node:$VERSION \
  -t ghcr.io/$OWNER/coracommit-node:latest --push ./node_service
```

Record the digests in the release notes for a fully reproducible citation:

```bash
docker buildx imagetools inspect ghcr.io/$OWNER/coracommit-backend:2.1.0
docker buildx imagetools inspect ghcr.io/$OWNER/coracommit-node:2.1.0
```

Before tagging, bump `vscode_extension/package.json`, the image tags in
`docker-compose.release.yml` and `.env.deploy.example`, and the release bundle
name in `scripts/package_release.*`.

## Security

- Change `MYSQL_ROOT_PASSWORD` and `DB_PASSWORD` from the example values.
- Do not expose MySQL/Redis ports publicly in production.
- Put the Node API behind a reverse proxy/TLS if it is remote.
- API keys stay in VS Code SecretStorage; the server does not need them at rest.