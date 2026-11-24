# Privacy and security

## API keys

- API keys are stored in VS Code SecretStorage, not in `settings.json`.
- The extension sends the selected key only to the configured Node API for the
  corresponding provider call.
- Self-hosted deployments can keep all requests inside your network.

## Code diffs

- Diffs are read locally from `git diff --cached`.
- Client-side preprocessing normalizes line endings, filters binary patches,
  masks common token/credential patterns, and truncates long input.
- The processed diff is sent to:
  - your self-hosted Node/Python backend;
  - the selected LLM provider (if not in mock mode).

## Data retention

- The Node service stores feedback logs, selected/edited messages, exemplars,
  and model scores in MySQL.
- The extension itself does not upload files other than the staged diff needed
  for generation.
- For a hosted deployment, define a retention policy and tell users what is
  stored.

## Recommendations for deployment

- Change default MySQL and Redis credentials.
- Do not expose MySQL/Redis ports publicly.
- Put the Node API behind TLS if remote.
- Restrict access to the resource directory.
- Use mock mode for demos without external provider calls.