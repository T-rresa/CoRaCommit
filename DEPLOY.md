# CoRaCommit deployment

This file is a short deployment entry point. The full guide is
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## One command (services + extension)

```bash
./scripts/install.sh
```

PowerShell:

```powershell
.\scripts\install.ps1
```

Use `--source` / `-Source` to force a local image build.

## Prebuilt images (fastest)

```bash
cp .env.deploy.example .env
./scripts/start_release.sh
```

PowerShell:

```powershell
Copy-Item .env.deploy.example .env
.\scripts\start_release.ps1
```

This pulls `ghcr.io/t-rresa/coracommit-backend:2.1.0` and
`ghcr.io/t-rresa/coracommit-node:2.1.0` instead of building.

## Source build

```bash
cp .env.deploy.example .env
docker compose -f docker-compose.deploy.yml up -d --build
```

PowerShell:

```powershell
Copy-Item .env.deploy.example .env
.\scripts\start_local.ps1
```

The stack starts:

- retrieval backend on `8000`
- evaluation backend on `8001`
- Node API on `3001`
- MySQL on `3306`
- Redis on `6379`
- a one-shot `db-init` service that runs `init_db.js` and
  `init_model_scores.js`

## Resources

`RESOURCE_DIR` selects the host resource directory:

- `resource_demo` (committed): 32-document quickstart sample.
- `resource` (built from ApacheCM): full corpus.

Inside the containers the backend reads `RESOURCE_PATH=/app/resource`.

## Health checks

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8001/api/health
curl http://127.0.0.1:3001/api/health
```

## Logs

```bash
docker compose -f docker-compose.deploy.yml logs -f
```

## Full documentation

- Quick start: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- Configuration: [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
- Deployment: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- Troubleshooting: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)