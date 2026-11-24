# Configuration

## Extension settings

| Setting | Default | Meaning |
|---|---|---|
| `auto-gen-message.apiUrl` | `http://localhost:3001/api` | Node API base URL |
| `auto-gen-message.model` | `deepseek-chat` | Default model |
| `auto-gen-message.template` | `conventional` | Commit style |
| `auto-gen-message.format` | `conventional` | Conventional / Karma |
| `auto-gen-message.language` | `en` | Output language |
| `auto-gen-message.useCustomTemplate` | `false` | Use the custom template |
| `auto-gen-message.customTemplate` | empty | Custom template text |
| `auto-gen-message.mockLLM` | `false` | Use backend mock LLM |

API keys are **not** settings; they are stored in VS Code SecretStorage via the
sidebar.

## Docker environment (`.env`)

| Variable | Example | Meaning |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `change_me` | MySQL root password |
| `MYSQL_DATABASE` | `auto_gen_message` | Database name |
| `DB_HOST` | `mysql` | MySQL host in Docker |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | DB user |
| `DB_PASSWORD` | same as root password | DB password |
| `DB_NAME` | `auto_gen_message` | DB name |
| `REDIS_HOST` | `redis` | Redis host in Docker |
| `REDIS_PORT` | `6379` | Redis port |
| `PORT` | `3001` | Node API port |
| `NODE_ENV` | `production` | Node environment |
| `RESOURCE_DIR` | `resource_demo` | Host resource directory |
| `RESOURCE_PATH` | `/app/resource` | Container resource path |
| `EMBEDDING_MODEL` | `codebert` or `jina` | Embedding model |
| `ALLOW_MOCK_LLM` | `true` / `false` | Enable mock LLM |
| `PROMPT_MAX_EXAMPLES_DIFF_CHARS` | empty (no limit) | Total exemplar diff character cap |
| `PROMPT_MAX_SINGLE_EXAMPLE_DIFF_CHARS` | empty (no limit) | Per-example diff character cap |
| `RETRIEVAL_BACKEND_URL` | `http://retrieval-backend:8000` | Retrieval URL |
| `EVALUATION_BACKEND_URL` | `http://evaluation-backend:8001` | Evaluation URL |
| `EVAL_WORKER_CONCURRENCY` | `1` | Feedback worker concurrency |
| `EVAL_JOB_DELAY_MS` | `300000` | Feedback delay |
| `EVAL_BUSY_CHECK_INTERVAL_MS` | `15000` | Busy-check interval |
| `EVAL_CPU_THRESHOLD` | `0.75` | CPU threshold for evaluation |
| `ONLINE_BUSY_TTL_SECONDS` | `30` | Busy flag TTL |

## Local Node environment (`node_service/.env`)

Use `DB_HOST=localhost`, `REDIS_HOST=localhost`, and
`RETRIEVAL_BACKEND_URL=http://localhost:8000`.

## Ports

| Service | Default host port | `.env` variable |
|---|---:|---|
| Retrieval backend | 8000 | `RETRIEVAL_PORT` |
| Evaluation backend | 8001 | `EVALUATION_PORT` |
| Node API | 3001 | `NODE_API_PORT` |
| MySQL | 3306 | `MYSQL_HOST_PORT` |
| Redis | 6379 | `REDIS_HOST_PORT` |

The `*_PORT` variables only change the host-side mapping. Container-to-container
traffic keeps using 8000/8001/3001/3306/6379, so `RETRIEVAL_BACKEND_URL`,
`DB_PORT`, and `REDIS_PORT` do not need to change.

## Resource layout

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

`resource_demo/` contains a 32-document sample for quickstart. Set
`RESOURCE_DIR=resource` for the full corpus.

## Model registry

The Node service seeds model scores from `node_service/src/config/settings.js`
(`AVAILABLE_MODELS`). Run `npm run init-model-scores` after adding a model.

## Prompt exemplar cap

Exemplar diffs are **not capped by default**. Set
`PROMPT_MAX_SINGLE_EXAMPLE_DIFF_CHARS` and `PROMPT_MAX_EXAMPLES_DIFF_CHARS` to
positive character counts (for example `2000` and `6000`) to restore a cap.
An empty, invalid, or non-positive value means no limit.