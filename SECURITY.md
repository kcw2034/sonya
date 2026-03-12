# Security Policy

## Supported Versions

All packages are currently in active pre-release development (`0.x`).
Security fixes are applied to the **latest commit on `main`** only.

| Package | Version | Supported |
|---------|---------|-----------|
| `sonya-core` | 0.0.1 | ✅ |
| `sonya-gateway` | 0.0.1 | ✅ |
| `sonya-cli` | 0.1.0 | ✅ |
| `sonya-pipeline` | 0.0.1 | ✅ |
| `sonya-pack` | 0.0.1 | ✅ |
| `sonya-extension` | 0.0.1 | ✅ |

No stable release line exists yet; older commits are not patched.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Use [GitHub Private Security Advisories](https://github.com/kcw2034/sonya/security/advisories/new)
to report a vulnerability privately. You can expect an initial response
within **7 days** and a status update within **14 days** of submission.

If a report is accepted we will coordinate a fix and disclosure timeline
with you before publishing. If declined, we will explain why the behaviour
is considered out of scope or intentional.

## Security Design Notes

### API Key Handling

- API keys are read from environment variables
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`) or a local
  `.env` file written by `sonya auth`.
- Keys are **never logged or printed** by the framework.
  The `_safe_error_message` helper in `sonya-gateway` returns only the
  exception class name so that raw error strings (which may contain key
  fragments or internal paths) are never forwarded to API clients.

### Gateway Network Exposure

- `sonya-gateway` binds to `127.0.0.1` (localhost) by default.
  Remote access requires an explicit `--host 0.0.0.0` flag.
- Do **not** expose the gateway to an untrusted network without adding
  an authentication layer in front (e.g. a reverse proxy with basic auth
  or mTLS).
- The gateway is intended for local/personal use. There is currently no
  built-in authentication or rate-limiting on the REST/SSE endpoints.

### Dependency Supply Chain

- Dependencies are pinned via `uv.lock`. Run `uv lock --upgrade` and
  review the diff before updating dependencies.
- Only official provider SDKs (Anthropic, OpenAI, Google Generative AI)
  are used for LLM communication.

## Out of Scope

The following are **not** treated as security vulnerabilities in this
project:

- Prompt injection via user-supplied messages (this is an LLM-level
  concern outside the framework's control).
- Denial-of-service via unlimited LLM token usage (use `GuardrailConfig`
  to set per-run limits).
- Security issues in transitive dependencies not directly used by Sonya.
