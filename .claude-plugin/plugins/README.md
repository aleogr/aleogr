# Plugins

One subfolder per plugin. Do not create a plugin's folder before the plugin itself.

Source of truth: [`docs/DESIGN.md` — sections 1, 8, 9, 10 and 12](../../docs/DESIGN.md#1-names).

## Names

- Orchestrator: `aleogr` (skills without provider, e.g. `project-declare`).
- Family plugins: `aleogr-<family>-<provider>` (e.g. `aleogr-repo-github`).
- Family skills: `<provider>_<action>`, given by the **folder name** (e.g. `skills/github_repo-create/`, `skills/aws-route53_record-add/`). Exactly one underscore, between provider and action; hyphens inside each part.
- Object first, action after, in every skill: `repo-create`, `branch-protect`, `project-declare` (the verb may carry a complement: `ci-set-secret`).
- **No `SKILL.md` has `name:` in its frontmatter.** The `description` names the provider.
- Never use built-in command names (`init`, `doctor`, `status`, `review`, `context`, `config`...).

## Family types

- **Exclusive** (one provider per project/domain), **combinable** (several at once); **project**, **component** or **domain** scope. Full map in section 9.
- Each family has a minimum contract of actions, defined in [`docs/CONTRACTS.md`](../../docs/CONTRACTS.md); extra skills follow the same naming convention.
- Every family has a `*-describe` action, and every skill ends with an `aleogr-result` block (CONTRACTS.md section 1).

## Plugin skeleton

```
aleogr-<family>-<provider>/
├── .claude-plugin/plugin.json   ← only the manifest in here
├── skills/<provider>_<action>/SKILL.md
├── agents/                      (optional)
├── hooks/hooks.json             (optional)
├── scripts/                     (optional; reference with ${CLAUDE_PLUGIN_ROOT})
└── .mcp.json                    (optional; official MCP when there is no good CLI)
```

## What exists

- `aleogr` (orchestrator): skills `tools-check` (`gcloud` by default, `gh` with `command=gh`), `platform-plan`, `platform-apply`, and `project-declare`, `project-plan`, `project-apply`, which write the declaration `.aleogr/project.json` (version 1: the project name, its GitHub repository and its components) and make the repository match it; `defaults.json`. After the birth a change takes three steps: `project-apply` proposes it as a pull request, the owner merges it, and `project-apply` updates the folder and applies it. A declared component gets its starting point and the project gets its `ci.yml` in that same pull request; after the merge the protection requires the check `ci`.
- `aleogr-cloud-gcp`: skills `gcp_environment-describe`, `gcp_environment-create`, `gcp_services-enable`, `gcp_budget-alert-setup`.
- `aleogr-db-gcp-cloud-sql`: skills `gcp-cloud-sql_instance-describe`, `gcp-cloud-sql_instance-create`, `gcp-cloud-sql_instance-start`, `gcp-cloud-sql_instance-stop`, `gcp-cloud-sql_instance-switch-setup`.
- `aleogr-repo-github`: skills `github_repo-describe`, `github_repo-create`, `github_repo-configure`, `github_branch-protect`, with the `gh` CLI, and, with `gh` and `git`, `github_checkout-setup`, which ties the current folder to the repository, sends the declaration at its birth and brings a folder that is behind up to date after a merge, `github_pull-request-open`, which proposes named files by pull request (a new branch `aleogr/change-<random>`, one open at a time per repository, never merged by the tooling); and `github_ci-setup`, which writes the project's `.github/workflows/ci.yml` from the declared components (a marker on its first line, one job per component calling `ci-go.yml` of `aleogr/aleogr` pinned by commit, and the job `ci`); `files/ruleset-main.json`, the ruleset `main` that `github_branch-protect` sends, and `files/ruleset-main-ci.json`, the same plus the required check `ci`, sent with `checks=ci`.
- `aleogr-stack-go`: skill `go_setup`, which writes the starting point of a Go component (`go.mod`, `main.go`, `main_test.go`, from the templates in `files/`) once, only when its folder has no `go.mod` and no Go file, and returns its CI parameters.
- Everything else in the design (other families, the other orchestrator skills, hooks) is planned; the tests are in `../tests/` and the declaration's schema in `../schemas/`.
