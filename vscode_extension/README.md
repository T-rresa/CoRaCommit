# CoRaCommit

CoRaCommit generates commit messages inside VS Code using retrieval-augmented
examples and multiple LLMs. The extension collects the staged Git diff,
retrieves similar historical commit-message pairs, generates candidates from
several models in parallel, and records selection/editing feedback to update
model recommendations.

## Features

- Staged diff extraction and client-side preprocessing (masking, truncation).
- Hybrid retrieval over an ApacheCM-derived commit corpus.
- Parallel generation with multiple LLM providers.
- Side-by-side candidate comparison.
- Feedback-driven global and exemplar-level model recommendation.
- One-line and Conventional Commits templates; custom templates.

## Requirements

- VS Code 1.85+
- A running CoRaCommit backend (Node API + Python retrieval backend)
- An API key for at least one supported model family (GPT / Qwen / DeepSeek)
  unless the backend is running in mock mode

## Install

From a clone of the repository, one command starts the backend stack and
installs this extension:

```bash
./scripts/install.sh
```

Windows PowerShell:

```powershell
.\scripts\install.ps1
```

Or install a released `.vsix` manually:

```bash
code --install-extension coracommit-2.1.0.vsix
```

## First use

1. Reload the VS Code window (`Developer: Reload Window`).
2. Set the backend URL in VS Code settings:
   ```json
   "auto-gen-message.apiUrl": "http://localhost:3001/api"
   ```
3. Click the CoRaCommit icon in the activity bar.
4. Click **Set GPT Key**, **Set Qwen Key**, or **Set Deepseek Key**; the
   matching status line changes to **Configured**.
5. Stage a change (`git add`), choose models/template/language, and click
   **Generate**.
6. Select a candidate, edit if needed, and click **Commit Changes**.

The first Generate may take 10–30 s while the backend loads CodeBERT. Without an
API key, see the mock mode section below; messages start with `[MOCK:<model>]`.

> 📷 **Screenshot placeholder:** `media/screenshots/sidebar.png` — the
> CoRaCommit sidebar with a staged diff and the Generate button.

> 📷 **Screenshot placeholder:** `media/screenshots/candidates.png` — candidate
> messages with model names and latency.

## Development

This section is only for working on the extension itself:

```bash
npm ci
npm run compile
```

Open this directory in VS Code and press `F5`. A new
`[Extension Development Host]` window opens; use the CoRaCommit sidebar there.
End users should install the packaged `.vsix` instead.

## Mock mode

For a no-API-key smoke test, set the backend `ALLOW_MOCK_LLM=true` and enable:

```json
"auto-gen-message.mockLLM": true
```

## Backend

See the repository README and `docs/QUICKSTART.md` for the one-command Docker
setup, local development setup, and mock mode. The backend exposes:

- Retrieval backend: `http://localhost:8000`
- Evaluation backend: `http://localhost:8001`
- Node API: `http://localhost:3001/api`

## Links

- Repository: https://github.com/T-rresa/CoRaCommit
- Documentation: https://github.com/T-rresa/CoRaCommit/tree/main/docs
- Issues: https://github.com/T-rresa/CoRaCommit/issues

## License

MIT