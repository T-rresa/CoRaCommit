# Troubleshooting

## Services do not start

```bash
docker compose -f docker-compose.deploy.yml ps
docker compose -f docker-compose.deploy.yml logs
```

Check that ports `8000/8001/3001/3306/6379` are free, or move the host port in
`.env`:

```text
RETRIEVAL_PORT=8000
EVALUATION_PORT=8001
NODE_API_PORT=3001
MYSQL_HOST_PORT=3306
REDIS_HOST_PORT=6379
```

A local MySQL on 3306 is the most common conflict. Set `MYSQL_HOST_PORT=13306`
and keep `DB_PORT=3306`; the Node service connects to the container network, not
the host port.

## MySQL errors

- `Access denied`: `MYSQL_ROOT_PASSWORD` and `DB_PASSWORD` must match in `.env`.
- `Unknown database`: `MYSQL_DATABASE` and `DB_NAME` must match.
- Schema missing: run
  ```bash
  docker compose -f docker-compose.deploy.yml run --rm db-init
  ```
- To reset the database (destructive):
  ```bash
  docker compose -f docker-compose.deploy.yml down -v
  ```

## Redis errors

- Docker mode: `REDIS_HOST=redis`.
- Local mode: `REDIS_HOST=localhost`.
- Check with `docker exec -it auto_gen_msg_redis redis-cli ping`.

## Backend health fails

- Check `RESOURCE_DIR` points to a directory containing `docs.db`, `faiss/`,
  and `embeddings/`.
- Check `EMBEDDING_MODEL` is `codebert` or `jina`.
- First startup can take 1–2 minutes while the model and index load.

## Extension cannot reach the backend

- Check `auto-gen-message.apiUrl` (default `http://localhost:3001/api`).
- Run `curl http://127.0.0.1:3001/api/health`.
- If remote, ensure the API is reachable and CORS/proxy settings are correct.

## 401 / 403 from the LLM provider

- Set the key for the selected model's family from the sidebar.
- GPT models need an OpenAI key; Qwen needs DashScope; DeepSeek needs a
  DeepSeek key.

## No candidates

- Check the Node API log for provider errors.
- Try a single model.
- Try mock mode:
  ```text
  ALLOW_MOCK_LLM=true
  ```
  and `"auto-gen-message.mockLLM": true`.

## Empty staged diff

- Run `git add <files>` before generating.
- CoRaCommit uses `git diff --cached`, not unstaged changes.

## `npm ci` fails

- Use Node.js 18+.
- Delete `node_modules` and `package-lock.json` only if you intentionally
  changed dependencies; otherwise keep the lockfile.
- For the extension, run `npm ci` inside `vscode_extension/`.

## `.vsix` packaging fails

- Run `npm run compile` first.
- Ensure `resources/icon.png` exists.
- Ensure `publisher`, `repository`, and `license` are set in
  `vscode_extension/package.json`.
- If `vsce` is missing, `npm run package` uses `npx --yes @vscode/vsce`.