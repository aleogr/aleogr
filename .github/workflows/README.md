# Workflows

Flat folder (GitHub requirement), organized by prefix.

Source of truth: [`docs/DESIGN.md` — sections 3, 4 and 15](../../docs/DESIGN.md#4-cicd) (names in [section 1](../../docs/DESIGN.md#workflows)).

## Local rules

- **Reusable** (`ci-`, `cd-`, `release-`): only `on: workflow_call`, so they don't run on every commit here. Called by the projects' thin workflows (`ci.yml`/`cd.yml`), pinned by SHA.
- **This repository's own**: prefix `self-` (e.g. `self-validate-marketplace.yml`, `self-lint.yml`, `self-test-features.yml`, `self-publish-features.yml`, `self-cleanup-tests.yml`).
- `self-shared-database.yml`: manual (`workflow_dispatch`) start/stop/status of the shared platform's Cloud SQL instance, on `main` only; uses the repository secrets `GCP_SHARED_PROJECT_ID`, `GCP_SHARED_WIF_PROVIDER` and `GCP_SHARED_SWITCH_ACCOUNT`.
- `ci-go.yml`: reusable check of one Go component (one module in one folder). Inputs `working-directory` (the module's folder, relative to the repository root) and `go-version` (`major.minor`), both required. Steps: checkout, set up Go (no cache), `gofmt -l` (fails and lists the files when one is not formatted), `go vet ./...`, `go test ./...`, `go build ./...`. Permission `contents: read`; no secrets. A project's `ci.yml` calls it once per component, pinned by commit SHA.
- `self-test-ci-go.yml`: tests `ci-go.yml` before a project uses it. On pull requests that change `ci-go.yml`, this file or `.github/testdata/ci-go/**`, it calls `ci-go.yml` on the fixture module in `.github/testdata/ci-go` (a small standard-library HTTP server with one test per handler) with Go `1.27`.
- Action references (`uses:`) are pinned by full commit SHA with the version in a comment; `.github/dependabot.yml` proposes their updates weekly.
- Versioning by prefixed tags: `workflows-v1`, `workflows-v2`...
- Secrets received explicitly by name; **never** `secrets: inherit`.
- Logs of public workflows are public: **no workflow prints variables or secrets**.

> Warning: never create `.github/README.md` — it would replace the profile README.
