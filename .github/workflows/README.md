# Workflows

Flat folder (GitHub requirement), organized by prefix.

Source of truth: [`docs/DESIGN.md` — sections 3, 4 and 15](../../docs/DESIGN.md#4-cicd) (names in [section 1](../../docs/DESIGN.md#workflows)).

## Local rules

- **Reusable** (`ci-`, `deploy-`, `release-`): only `on: workflow_call`, so they don't run on every commit here. Called by the projects' thin workflows (`ci.yml`/`cd.yml`), pinned by SHA.
- **This repository's own**: prefix `self-` (e.g. `self-validate-marketplace.yml`, `self-lint.yml`, `self-test-features.yml`, `self-publish-features.yml`, `self-cleanup-tests.yml`).
- Versioning by prefixed tags: `workflows-v1`, `workflows-v2`...
- Secrets received explicitly by name; **never** `secrets: inherit`.
- Logs of public workflows are public: **no workflow prints variables or secrets**.

> Warning: never create `.github/README.md` — it would replace the profile README.
