# User guide

## 0. Before you start

| Check | How | Expected |
|---|---|---|
| Backend is running | `curl http://127.0.0.1:3001/api/health` | `{"status":"ok",...}` |
| Extension is installed | Extensions view shows `CoRaCommit` | enabled, VS Code reloaded |
| Backend URL is correct | `auto-gen-message.apiUrl` | `http://localhost:3001/api` |
| One API key exists | sidebar → **Set GPT / Qwen / Deepseek Key** | status **Configured** |

If a check fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 1. Prepare a staged diff

In a Git repository:

```bash
git add <files>
```

CoRaCommit reads `git diff --cached`; unstaged changes are not used.

## 2. Open the sidebar

Open the CoRaCommit icon in the activity bar (or the command palette:
`CoRaCommit: Generate Commit Message`). The sidebar shows the processed staged
diff.

## 3. Set an API key

Click **Set API Key** and choose the model family:

| Family | Example models | Key source |
|---|---|---|
| GPT | `gpt-4o`, `gpt-4` | OpenAI API key |
| Qwen | `qwen-plus`, `qwen-max` | Aliyun DashScope key |
| DeepSeek | `deepseek-chat` | DeepSeek API key |

Keys are stored in VS Code SecretStorage. They are not written to
`settings.json`.

Each model family calls its provider endpoint directly (`api.openai.com`,
DashScope, or `api.deepseek.com`).

> 📷 **Screenshot placeholder:** `docs/images/api-keys.png` — the API Keys
> block with GPT/Qwen/DeepSeek buttons and the status lines showing
> **Configured**.

After saving a key, the matching status line should change from **Not set** to
**Configured**. The key is stored in VS Code SecretStorage, not in
`settings.json`.

## 4. Configure generation

Choose:

- **Model**: one or more models (multi-select in the sidebar).
- **Template**: Conventional / Angular / Emoji / custom.
- **Format**: Conventional Commits or Karma.
- **Language**: English, Chinese, Japanese, etc.

The backend URL is controlled by:

```json
"auto-gen-message.apiUrl": "http://localhost:3001/api"
```

## 5. Generate

Click **Generate**. The extension:

1. reads the staged diff;
2. retrieves similar commit exemplars;
3. builds prompts;
4. calls the selected models in parallel;
5. returns candidate messages.

The first run may be slower while the backend loads the embedding model and
index (typically 10–30 s). Later runs reuse the loaded model.

> 📷 **Screenshot placeholder:** `docs/images/generating.png` — the sidebar
> while **Generate** is running, or the candidate panel immediately after.

## 6. Compare and commit

The candidate panel shows each model, its message, and latency.

- Select a candidate to fill the Git commit input box.
- Edit the message if needed.
- Commit normally from VS Code.

> 📷 **Screenshot placeholder:** `docs/images/candidates.png` — three candidate
> rows with model names, latency, one selected, and the edit/commit area.

If multiple models are enabled, each candidate row is labeled with its model
name. The selected row is highlighted; editing the message before committing
still records the selection and edit as feedback.

## 7. Feedback and leaderboard

When a candidate is selected or edited, CoRaCommit records:

- selected model;
- final message;
- whether it was edited;
- the exemplars used.

A background worker scores the candidates and updates global and
exemplar-level model scores. The leaderboard shows the current ranking.

> 📷 **Screenshot placeholder:** `docs/images/leaderboard.png` — the model
> leaderboard and the 7-day usage trend.

The leaderboard updates after the background worker finishes scoring; it is a
suggestion, not an automatic replacement of your chosen model.

## 8. Mock mode

For a no-key smoke test:

1. Backend `.env`: `ALLOW_MOCK_LLM=true`.
2. VS Code settings: `"auto-gen-message.mockLLM": true`.
3. Generate; messages are prefixed with `[MOCK:model]`.

## 9. First success in 5 minutes (mock mode, no API key)

Use this to verify the extension end to end before adding real keys.

1. Backend `.env`:
   ```text
   ALLOW_MOCK_LLM=true
   RESOURCE_DIR=resource_demo
   ```
2. Restart the stack with the compose file you started with.
3. VS Code settings:
   ```json
   "auto-gen-message.mockLLM": true
   ```
4. Stage a change and click **Generate**.
5. Expected result: the candidate message starts with `[MOCK:<model>]`, and the
   sidebar shows model, latency, and message.

If nothing appears, check the Node API log and the `apiUrl` setting.

## 10. Common issues

- **No staged changes**: run `git add` first.
- **Missing API key**: set the key for the selected model's family.
- **401**: the key does not match the selected provider.
- **Backend unavailable**: check `auto-gen-message.apiUrl` and port 3001.
- **Empty candidates**: check the backend logs and the selected model.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for details.