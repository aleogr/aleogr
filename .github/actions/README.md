# Composite actions

Composite actions reusable by projects (one subfolder per action, with `action.yml`).

Source of truth: [`docs/DESIGN.md` — sections 3 and 4](../../docs/DESIGN.md#3-public-repository-conditions).

## Local rules

- Reference from projects: `aleogr/aleogr/.github/actions/<name>@<sha>` — always pinned by **SHA** (Dependabot/Renovate update it). Within this repository: `./.github/actions/<name>`.
- Versioning by prefixed tags: `actions-v1`, `actions-v2`...
- Generic tooling only; never data, IDs or secrets (the repository is public).
- Not published to the GitHub Marketplace (it would require a dedicated repository).

> Warning: never create `.github/README.md` — it would replace the profile README.
