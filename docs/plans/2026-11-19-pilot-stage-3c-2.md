# Reference project, stage 3c-2: Go components and CI — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A component declared in `.aleogr/project.json` gets a Go starting point generated once, the project gets a `ci.yml` generated from the declaration, both reach the repository through the pull-request cycle, and after the merge `main` requires the check `ci`.

**Architecture:** A new plugin `aleogr-stack-go` (skill `go_setup`) writes the starting point from files it ships. A new GitHub skill `github_ci-setup` writes the project's thin `ci.yml`, which calls a new reusable workflow `ci-go.yml` of `aleogr/aleogr`. `project-plan` gains the rows `components` and `ci`; `project-apply` generates, then proposes everything in one pull request (the cycle of stage 3c-1). The protection gains a second ruleset file that requires the check `ci`.

**Tech Stack:** Claude Code plugin skills (Markdown), `gh`, `git`, Go 1.27, GitHub Actions (reusable workflow, `dorny/paths-filter`), JSON Schema, the bash harness under `.claude-plugin/tests/`.

**Spec:** [`2026-11-19-pilot-stage-3c-design.md`](2026-11-19-pilot-stage-3c-design.md), part 3c-2. Models of style: the skills of `aleogr-repo-github` and `aleogr/skills/project-*`.

## Global Constraints

- Everything versioned is in English. The repository is public: fixtures use only `example-org`, `example-repo`, the project `demo`, the components `web` and `api`, the account `example-user` with id `1234567`. `aleogr-sandbox` appears only in documents, never under `.claude-plugin/`.
- No `SKILL.md` has `name:` in its frontmatter. Every skill validates before any command, shows each command before running it, runs only the commands (or invokes only the skills) its steps list, and ends with exactly one fenced `aleogr-result` block.
- The orchestrator skills run no `gh` or `git` command; they invoke skills. Skills never wait for an answer. Status `pending` means nothing was changed; once something was done the status says what and leftovers are items in the `pending` list.
- A component: `name` 1 to 20 characters of `a-z`, `0-9`, `-`, starting with a letter, unique; `path` a relative folder with no `..`, no leading or trailing `/`, no space, not `.aleogr` or `.github` or under them, unique, default the name; `stack` `go`; `version` matches `^[0-9]+\.[0-9]+$`.
- The Go module of a component is `github.com/<repo.owner>/<repo.name>/<path>`. One module per component folder; no `go.work`.
- The files of a component's starting point are exactly `<path>/go.mod`, `<path>/main.go`, `<path>/main_test.go`. They are written only when `<path>/go.mod` does not exist, and never overwritten.
- The project's CI file is `.github/workflows/ci.yml`. Its first line is the marker `# aleogr-ci 1 <name>:<path>:<stack>:<version>,…` with the components sorted by name. "As declared" is decided by comparing that line.
- The required status check is named `ci`. The protection requires it exactly when `.github/workflows/ci.yml` is on the repository's default branch.
- The default Go version is `1.27` (the latest stable on go.dev on 2026-11-19 is 1.27.4).
- Third-party actions are pinned by full commit SHA with the version in a comment. Reusable workflows of this repository have only `on: workflow_call`, `permissions: contents: read`, receive no secrets and print no variables.
- A proposal carries only named files (never a folder): the declaration plus the files the generating skills report.
- "The declaration's rules" stay byte-identical in `project-declare` and `project-plan`: Task 1 changes the section in both, in the same commit, and proves it with a diff.
- A command whose result decides a step is run alone; each decision names its identifying text; raw error text is never quoted. The paragraph that says so is identical in every `aleogr-repo-github` skill: copy it.
- Do not change the root `README.md`; never create `.github/README.md`; no skill, plugin or workflow beyond this plan. `docs/DESIGN.md` states decisions in the present tense; its section 16 gets no entry.
- Commit messages end with the line the session gives; no model name anywhere. `.superpowers/` is never committed.
- Scenarios: `bash .claude-plugin/tests/run.sh <scenario>`; four at a time, two at a time for `project-apply-*`. Each run costs model usage. A thing that does not exist answers with an error and exit 1; expectations pin content; no bare `NOT_CALLED ^git`; "before and after" uses `+after+` state files (the longest prefix wins a tie).

## Review Focus

1. A component's folder already has code but no `go.mod` (the owner started by hand), or has a `go.mod`: nothing is overwritten. Tests: `go-setup-existing`, `go-setup-folder-not-empty` (Task 2).
2. A component `path` that points into `.github`, `.aleogr`, or outside the folder: refused before anything is written. Tests: `project-declare-component-bad-path` (Task 1), `go-setup-invalid-path` (Task 2).
3. The check `ci` must not be required before `ci.yml` is on the default branch. Tests: `project-plan-ci-not-merged` (Task 6), `project-apply-generate` (Task 7: no ruleset write in that run).
4. A pull request that changes neither component must still be mergeable (the job `ci` passes when every component job was skipped), but a failed change detection must not pass (the job `ci` requires `changes` to have succeeded). Test: the YAML of Task 4 is checked by `actionlint` and by reading; proven in the real run.
5. Regenerating `ci.yml` when nothing changed must not produce a difference (the pinned commit is kept). Test: `gh-ci-setup-unchanged-keeps-ref` (Task 4).
6. A declaration with no components behaves exactly as before stage 3c-2. Tests: every existing `project-plan-*` and `project-apply-*` scenario passes unchanged (Tasks 6, 7).

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/schemas/project.schema.json`, `examples/with-components.json`, `schemas/README.md` | `components` |
| `.claude-plugin/plugins/aleogr/defaults.json` | `stacks.go.version`, `ci.workflowsRepository` |
| `.claude-plugin/plugins/aleogr/skills/project-declare`, `project-plan`, `project-apply` | components; rows; generate |
| `.claude-plugin/plugins/aleogr-stack-go/` (`plugin.json`, `skills/go_setup/SKILL.md`, `files/go.mod.tmpl`, `files/main.go.tmpl`, `files/main_test.go.tmpl`) | the starting point |
| `.claude-plugin/plugins/aleogr-repo-github/skills/github_ci-setup/SKILL.md`, `files/ruleset-main-ci.json` | `ci.yml`; the ruleset with the check |
| `.../skills/github_branch-protect`, `github_repo-describe` | argument `checks` |
| `.github/workflows/ci-go.yml`, `self-test-ci-go.yml`, `.github/testdata/ci-go/`, `.github/dependabot.yml`, `.github/workflows/README.md` | the reusable workflow and its test |
| `.claude-plugin/marketplace.json`, the three `plugin.json`, `tests/run.sh` | catalog, versions, the new plugin in the tests |
| `docs/…`, `docs/plans/2026-11-19-pilot-stage-3c-2-run.md` | documents |

---

### Task 1: Components in the declaration

**Files:**
- Modify: `.claude-plugin/schemas/project.schema.json`, `.claude-plugin/schemas/README.md`, `.claude-plugin/plugins/aleogr/defaults.json`, `.claude-plugin/plugins/aleogr/skills/project-declare/SKILL.md`, `.claude-plugin/plugins/aleogr/skills/project-plan/SKILL.md` (only the section "The declaration's rules")
- Create: `.claude-plugin/schemas/examples/with-components.json`, scenarios `project-declare-component-*`

**Interfaces — produces:**
- Schema: optional top-level `components`, after `repo` and before `notes`: an array (may be empty) of objects with exactly `name`, `stack`, `path`, `version` (all required; rules of Global Constraints; `stack` enum `["go"]`). Uniqueness of `name` and of `path` is prose in "The declaration's rules" (JSON Schema cannot express it per key).
- `defaults.json` gains `"stacks": { "go": { "version": "1.27" } }` and `"ci": { "workflowsRepository": "aleogr/aleogr" }`.
- `project-declare` gains `component=<name>` with `stack=<go>` (required when the component is new), `path=<folder>` (default the name), `version=<major.minor>` (default `stacks.<stack>.version`): adds the component, or changes the given keys of an existing one; components are kept sorted by name. `stack`, `path` or `version` without `component` is `failed`. Changing a component's `path` or `stack` is refused ("that is another component"); only `version` changes. `outputs.changes` gains `components.<name>`.
- Canonical form: each component on one line, `{ "name": "…", "stack": "go", "path": "…", "version": "…" }`.

- [ ] **Step 1: Write the scenarios** (seed: `examples/repo-only.json` unless said):

```
# project-declare-component-add          (component=web stack=go)
FILE .aleogr/project.json "name": "web", "stack": "go", "path": "web", "version": "1\.27"
OUTPUT "status": "updated"
OUTPUT components\.web
# project-declare-component-second       (seed has web; component=api stack=go path=services/api)
FILE .aleogr/project.json "name": "api", "stack": "go", "path": "services/api"
FILE .aleogr/project.json "name": "web"
OUTPUT "status": "updated"
# project-declare-component-version      (seed has web 1.27; component=web version=1.26)
FILE .aleogr/project.json "name": "web", "stack": "go", "path": "web", "version": "1\.26"
OUTPUT "status": "updated"
# project-declare-component-unchanged    (seed has web; component=web stack=go)
OUTPUT "status": "unchanged"
# project-declare-component-bad-path     (component=web stack=go path=.github/web)
FILE .aleogr/project.json "topics"
OUTPUT "status": "failed"
OUTPUT_NOT "name": "web"
# project-declare-component-path-refused (seed has web at web; component=web path=other)
FILE .aleogr/project.json "path": "web"
OUTPUT "status": "failed"
# project-declare-component-no-stack     (component=web)
OUTPUT "status": "failed"
# project-declare-component-duplicate-path (seed has web at web; component=api stack=go path=web)
OUTPUT "status": "failed"
# project-declare-stack-without-component (stack=go)
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Schema, example, defaults.** Validate with a JSON Schema validator in a temporary folder outside the repository: both examples pass; a component with an unknown key, with `stack` `rust`, with `version` `1.27.4`, with `path` `../x` each fail. Run `platform-plan-empty` (it reads `defaults.json`).
- [ ] **Step 4: `project-declare`**, and the same new text in "The declaration's rules" of `project-plan`; extract both sections and `diff` them: no output.
- [ ] **Step 5: Run the nine scenarios plus `project-declare-new`, `project-declare-edit`, `project-plan-nothing-to-do`; expected PASS.**
- [ ] **Step 6: Commit:** `Add components to the project declaration`.

### Task 2: `aleogr-stack-go` and `go_setup`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-stack-go/.claude-plugin/plugin.json` (`0.1.0`, description `Go stack: the starting point of a Go component.`), `skills/go_setup/SKILL.md`, `files/go.mod.tmpl`, `files/main.go.tmpl`, `files/main_test.go.tmpl`, scenarios `go-setup-*`
- Modify: `.claude-plugin/marketplace.json` (entry: `category` `stack`, `displayName` `Go (stack)`), `.claude-plugin/tests/run.sh` (`--plugin-dir` for the new plugin), `.claude-plugin/tests/README.md`

**Interfaces:**
- Arguments: `component`, `path`, `version`, `module`, `mode`. `module` must be `github.com/` + two path segments + `/` + `path`.
- The three template files hold the placeholders `{{MODULE}}`, `{{COMPONENT}}`, `{{GO_VERSION}}` and nothing else to fill. `main.go`: package `main`; an HTTP server listening on `:` + the environment variable `PORT` (default `8080`); `GET /` answers `{{COMPONENT}}: ok` and `GET /healthz` answers `ok`, both `text/plain`; the handlers are built by a function `newMux() *http.ServeMux` so the test needs no network. `main_test.go`: one test per handler with `net/http/httptest`. Standard library only. `go.mod`: `module {{MODULE}}` and `go {{GO_VERSION}}`.
- Steps: read whether `<path>/go.mod` exists (Read tool or a listing; no shell command that changes anything).
  - It exists: `unchanged`, nothing written.
  - It does not exist but `<path>` holds any `.go` file: `pending`, item `{ "item": "<path> has Go files but no go.mod", "reason": "manual", "how": "add a go.mod to <path>, or empty the folder" }`, nothing written.
  - Otherwise `plan`: `would-create`; `apply`: read the three templates with the Read tool from `${CLAUDE_PLUGIN_ROOT}/files/`, replace the placeholders, write the three files with the Write tool: `created`.
- `outputs`: `{ "component", "path", "module", "files": ["<path>/go.mod", "<path>/main.go", "<path>/main_test.go"], "written": true|false, "ci": { "workflow": "ci-go.yml", "inputs": { "working-directory": "<path>", "go-version": "<version>" } } }` — `files` is always the three expected paths; `written` says whether this run wrote them. Result block `"family": "stack"`, `"provider": "go"`, `"action": "setup"`. It runs no command.

- [ ] **Step 1: Write the scenarios:**

```
# go-setup-apply         (component=web path=web version=1.27 module=github.com/example-org/example-repo/web mode=apply)
FILE web/go.mod ^module github\.com/example-org/example-repo/web$
FILE web/go.mod ^go 1\.27$
FILE web/main.go func newMux\(\)
FILE web/main.go web: ok
FILE web/main_test.go httptest
OUTPUT "status": "created"
OUTPUT "working-directory": "web"
NOT_CALLED ^gh
# go-setup-plan          (mode=plan)
NO_FILE web/go.mod
OUTPUT "status": "would-create"
# go-setup-existing      (files/web/go.mod = "module example.com/kept" and files/web/main.go = "package main // kept")
FILE web/go.mod example\.com/kept
FILE web/main.go kept
NO_FILE web/main_test.go
OUTPUT "status": "unchanged"
# go-setup-folder-not-empty (files/web/handler.go exists, no go.mod; mode=apply)
NO_FILE web/go.mod
OUTPUT "status": "pending"
# go-setup-nested-path   (path=services/api component=api … mode=apply)
FILE services/api/go.mod ^module github\.com/example-org/example-repo/services/api$
FILE services/api/main.go api: ok
# go-setup-invalid-path  (path=.github/web)
NO_FILE .github/web/go.mod
OUTPUT "status": "failed"
# go-setup-module-mismatch (module=github.com/example-org/example-repo/other path=web)
NO_FILE web/go.mod
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios, the manifest and the `run.sh` line.
- [ ] **Step 3: Write the templates and prove them for real**, in a temporary folder outside the repository: fill the placeholders by hand for `web`, then `gofmt -l .` prints nothing, `go vet ./...`, `go test ./...` and `go build ./...` pass (the local toolchain may be older than 1.27: let `go` fetch the right one, or test with the `go` line set to the local version and say so). Put the commands and output in the report.
- [ ] **Step 4: Write `SKILL.md`; run the scenarios; expected PASS.**
- [ ] **Step 5: Commit:** `Add the Go stack plugin and go_setup`.

### Task 3: The reusable workflow `ci-go.yml`, tested here

**Files:**
- Create: `.github/workflows/ci-go.yml`, `.github/workflows/self-test-ci-go.yml`, `.github/testdata/ci-go/go.mod`, `main.go`, `main_test.go`, `.github/dependabot.yml`
- Modify: `.github/workflows/README.md`

**Interfaces — produces:**
- `ci-go.yml`: `on: workflow_call` with inputs `working-directory` (string, required) and `go-version` (string, required); `permissions: contents: read`; one job `go` on `ubuntu-latest`, `defaults.run.working-directory: ${{ inputs.working-directory }}`; steps: `actions/checkout`, `actions/setup-go` (with `go-version` and `cache: false`), "Format" (`test -z "$(gofmt -l .)"`, printing the unformatted files when it fails), `go vet ./...`, `go test ./...`, `go build ./...`. Inputs reach `run:` steps only through `env:` or the `defaults` key, never by direct interpolation into a script.
- `self-test-ci-go.yml`: `on: pull_request` with `paths` `.github/workflows/ci-go.yml`, `.github/workflows/self-test-ci-go.yml`, `.github/testdata/ci-go/**`; `permissions: contents: read`; one job that `uses: ./.github/workflows/ci-go.yml` with `working-directory: .github/testdata/ci-go` and `go-version: "1.27"`.
- The fixture module is the Task 2 starting point filled for a component `sample` and module `github.com/aleogr/aleogr/.github/testdata/ci-go`.
- `dependabot.yml`: version 2, ecosystem `github-actions`, directory `/`, weekly.

- [ ] **Step 1: Look up the current release and its full commit SHA** of `actions/checkout` and `actions/setup-go` (their GitHub releases pages or `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`; a tag that points to a tag object is dereferenced to the commit). Record tag, SHA and where they were read in the report.
- [ ] **Step 2: Write the five files.**
- [ ] **Step 3: Check them:** run `actionlint` on the two workflows if it can be installed in a temporary folder (otherwise parse both with a YAML parser and say `actionlint` was not available); run the same four Go commands as the workflow in `.github/testdata/ci-go`.
- [ ] **Step 4: Update `.github/workflows/README.md`** (`ci-go.yml`, its inputs, how it is tested, `self-test-ci-go.yml`) and commit: `Add the reusable Go CI workflow and its self-test`.

The real proof of this task is the self-test running green on the pull request of this stage.

### Task 4: `github_ci-setup`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-repo-github/skills/github_ci-setup/SKILL.md`, scenarios `gh-ci-setup-*`

**Interfaces:**
- Arguments: `owner`, `name`, `components` (comma-separated `name:path:stack:version`, sorted by name by the skill; may be empty), `workflows` (the repository of the reusable workflows, `<owner>/<name>`, required when `components` is not empty), `ref` (`keep`, the default, or `latest`), `defaultBranch` (default `main`), `mode`.
- Reads, both modes:
  1. The local `.github/workflows/ci.yml` with the Read tool: missing, or its first line.
  2. `gh api repos/<owner>/<name>/contents/.github/workflows/ci.yml -H "Accept: application/vnd.github.raw"` — exit 0: `inRepository` true and its first line; `HTTP 404` (the file or the repository): false; anything else `failed`.
- `outputs.local`: `as-declared` (the first line equals the expected marker), `missing`, `differs`, or `not-needed` (no component and no file). No component but a local file: `differs` (the file is left alone and the answer says to remove it by hand: removal is not in this stage).
- `plan`: `as-declared`/`not-needed` → `unchanged`; `missing`/`differs` with components → `would-create`/`would-update`.
- `apply` when `missing` or `differs` with components:
  3. The commit to pin: the one in the existing file's `uses:` lines when the file exists and `ref` is `keep`; otherwise `gh api repos/<workflows>/commits/main` and its `sha`.
  4. Write `.github/workflows/ci.yml` with the Write tool, exactly in this shape (two components shown; one job per component, in name order; `<sha>` is the pinned commit, `<paths-filter-sha>` and its version comment are fixed in the skill):

```yaml
# aleogr-ci 1 api:services/api:go:1.27,web:web:go:1.27
# Generated by aleogr from .aleogr/project.json. Do not edit: change the declaration and run project-apply.
name: ci

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  changes:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
    outputs:
      api: ${{ steps.filter.outputs.api }}
      web: ${{ steps.filter.outputs.web }}
    steps:
      - uses: actions/checkout@<checkout-sha> # <version>
      - id: filter
        uses: dorny/paths-filter@<paths-filter-sha> # <version>
        with:
          filters: |
            api:
              - 'services/api/**'
              - '.github/workflows/ci.yml'
            web:
              - 'web/**'
              - '.github/workflows/ci.yml'

  api:
    needs: changes
    if: needs.changes.outputs.api == 'true'
    uses: <workflows>/.github/workflows/ci-go.yml@<sha>
    with:
      working-directory: services/api
      go-version: "1.27"

  web:
    needs: changes
    if: needs.changes.outputs.web == 'true'
    uses: <workflows>/.github/workflows/ci-go.yml@<sha>
    with:
      working-directory: web
      go-version: "1.27"

  ci:
    needs: [changes, api, web]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: The change detection passed, and every component job passed or was skipped
        env:
          CHANGES: ${{ needs.changes.result }}
          RESULTS: ${{ needs.api.result }} ${{ needs.web.result }}
        run: |
          if [ "$CHANGES" != "success" ]; then echo "the job changes ended: $CHANGES"; exit 1; fi
          for r in $RESULTS; do
            case "$r" in success|skipped) ;; *) echo "a component job ended: $r"; exit 1 ;; esac
          done
```

  `branches:` holds `defaultBranch`. A change to `ci.yml` itself runs every component. The job `ci` needs `changes` too and requires it to have succeeded: if the change detection failed, every component job would be skipped, and skipped must not read as passed.
- `outputs`: `{ "path": ".github/workflows/ci.yml", "local", "inRepository", "repositoryAsDeclared": true|false|null, "marker", "ref": "<sha or null>", "written": true|false, "checks": ["ci"] }` (`checks` is `[]` when there is no component).
- It never commits or pushes: the pull request carries the file.

- [ ] **Step 1: Look up the current release and full commit SHA of `dorny/paths-filter`** (as in Task 3; `actions/checkout` is the one of Task 3). Record them.
- [ ] **Step 2: Write the scenarios:**

```
# gh-ci-setup-apply            (components=web:web:go:1.27,api:services/api:go:1.27 workflows=example-org/tooling mode=apply; no local file; repo copy 404; commits/main answers sha 2222…)
CALLED ^gh api repos/example-org/tooling/commits/main
FILE .github/workflows/ci.yml ^# aleogr-ci 1 api:services/api:go:1\.27,web:web:go:1\.27$
FILE .github/workflows/ci.yml uses: example-org/tooling/\.github/workflows/ci-go\.yml@2{40}
FILE .github/workflows/ci.yml working-directory: services/api
FILE .github/workflows/ci.yml needs: \[changes, api, web\]
FILE .github/workflows/ci.yml if: always\(\)
OUTPUT "status": "created"
OUTPUT "inRepository": false
OUTPUT "checks": \["ci"\]
NOT_CALLED ^git (add|commit|-c credential)
# gh-ci-setup-plan-missing     (mode=plan)
NO_FILE .github/workflows/ci.yml
OUTPUT "local": "missing"
OUTPUT "status": "would-create"
# gh-ci-setup-as-declared      (files/ has a ci.yml whose marker matches; repo copy answers the same file)
NOT_CALLED commits/main
OUTPUT "local": "as-declared"
OUTPUT "inRepository": true
OUTPUT "status": "unchanged"
# gh-ci-setup-unchanged-keeps-ref (files/ has ci.yml pinned to 1{40} with the marker of ONE component; components now two; mode=apply)
NOT_CALLED commits/main
FILE .github/workflows/ci.yml ci-go\.yml@1{40}
FILE .github/workflows/ci.yml ^# aleogr-ci 1 api:
OUTPUT "status": "updated"
# gh-ci-setup-ref-latest       (same seed; ref=latest)
CALLED ^gh api repos/example-org/tooling/commits/main
FILE .github/workflows/ci.yml ci-go\.yml@2{40}
# gh-ci-setup-not-needed       (components= ; no file)
NO_FILE .github/workflows/ci.yml
OUTPUT "local": "not-needed"
OUTPUT "checks": \[\]
OUTPUT "status": "unchanged"
# gh-ci-setup-invalid-component (components=web:web:rust:1.0)
NOT_CALLED ^gh
OUTPUT "status": "failed"
# gh-ci-setup-read-refused     (the contents read exits 1 with HTTP 502)
NO_FILE .github/workflows/ci.yml
OUTPUT "status": "failed"
```

- [ ] **Step 3: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 4: Write `SKILL.md`.** Generate the two-component file once by hand from the skill's text into a temporary folder and check it with `actionlint` (or a YAML parser); put the result in the report.
- [ ] **Step 5: Run the scenarios; expected PASS. Commit:** `Add github_ci-setup`.

### Task 5: The protection may require the check `ci`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-repo-github/files/ruleset-main-ci.json`, scenarios `gh-protect-checks-*`, `gh-describe-checks-*`
- Modify: `skills/github_branch-protect/SKILL.md`, `skills/github_repo-describe/SKILL.md`, `.claude-plugin/plugins/aleogr-repo-github/.claude-plugin/plugin.json` (`0.4.0`)

**Interfaces:**
- `ruleset-main-ci.json` is `ruleset-main.json` plus one rule: `{ "type": "required_status_checks", "parameters": { "required_status_checks": [ { "context": "ci" } ], "strict_required_status_checks_policy": false } }` (check the parameter names against GitHub's REST documentation for repository rulesets before writing; add `do_not_enforce_on_create` only if the API requires it).
- Both skills gain `checks=ci|none` (default `none`). The file read, compared with and sent is `ruleset-main-ci.json` when `checks=ci`, `ruleset-main.json` otherwise. The comparison rule is unchanged, with `required_status_checks` compared as a set of `context` values. A ruleset that has the check when `checks=none`, or lacks it when `checks=ci`, differs.
- `github_repo-describe` `outputs.protection` gains `"requiredChecks": ["ci"]` (what the ruleset has, `[]` when none); `github_branch-protect` `outputs` gains the same key.

- [ ] **Step 1: Write the scenarios:**

```
# gh-protect-checks-plan-update    (checks=ci mode=plan; the ruleset main equals ruleset-main.json)
NOT_CALLED --method
OUTPUT "status": "would-update"
# gh-protect-checks-apply          (checks=ci mode=apply; same ruleset, id 123)
CALLED ^gh api --method PUT repos/example-org/example-repo/rulesets/123 --input .*ruleset-main-ci\.json
CALLED <<< .*"required_status_checks".*"context":"ci"
OUTPUT "status": "updated"
OUTPUT "requiredChecks": \["ci"\]
# gh-protect-checks-equal          (checks=ci; the ruleset already has the check)
NOT_CALLED --method
OUTPUT "status": "unchanged"
# gh-protect-checks-extra          (checks=none; the ruleset has the check)
OUTPUT "status": "would-update"
# gh-protect-checks-create         (checks=ci mode=apply; no ruleset)
CALLED ^gh api --method POST .* --input .*ruleset-main-ci\.json
OUTPUT "status": "created"
# gh-describe-checks-match         (checks=ci; ruleset with the check)
OUTPUT "matches": true
OUTPUT "requiredChecks": \["ci"\]
# gh-describe-checks-missing       (checks=ci; ruleset without the check)
OUTPUT "matches": false
OUTPUT "requiredChecks": \[\]
# gh-protect-checks-invalid        (checks=lint)
NOT_CALLED ^gh
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Change the two skills and add the file.** No step is renumbered.
- [ ] **Step 4: Run the eight scenarios plus `gh-protect-apply`, `gh-protect-equal-handmade`, `gh-protect-differs-apply`, `gh-describe-protected`, `gh-describe-protected-differs`; expected PASS.**
- [ ] **Step 5: Commit:** `Let the protection require the check ci`.

### Task 6: `project-plan` — the rows `components` and `ci`

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-plan/SKILL.md`
- Create: scenarios `project-plan-components-*`, `project-plan-ci-*`

**Interfaces:**
- A declaration with no `components` (or an empty list): the skill behaves exactly as today, invokes nothing new, and its table has the five rows of today.
- With components, the steps become: validate → `tools-check command=gh` → `github_ci-setup owner name components=<…> workflows=<defaults ci.workflowsRepository> mode=plan` (for `inRepository`, `local`) → `github_repo-describe owner name` with `checks=ci` when `inRepository` is true → `github_checkout-setup … mode=plan` → `github_pull-request-open owner name paths=<all tooling paths> mode=plan` → for each component `aleogr-stack-go:go_setup component path version module mode=plan`.
- All tooling paths: `.aleogr/project.json`, `.github/workflows/ci.yml`, and the three files of every component.
- Two new rows, after `declaration`:

| Item | State → action |
|---|---|
| `components` | every `go_setup` `unchanged` → `as declared` / `none`; some `would-create` → `to generate: <names>` / `generate`; one `pending` → `needs attention: <name>` / `fix the folder`, with its item |
| `ci` | `local` `as-declared` → `as declared` / `none`; `missing` → `missing` / `generate`; `differs` → `differs` / `generate` |

- The `declaration` row is `changed here` / `propose` when the checkout says `differs` **or** the pull-request skill's `changed` is not empty (generated files not yet in the repository), the folder being `ready`.
- While the declaration action is `merge it`, `update` or `fix the folder`, the two new rows are `not checked until the change is merged` / `none` and the generating skills are not invoked. While it is `propose` or `none`, they are computed from the local declaration and folder.
- The protection is compared with `checks=ci` exactly when `ci.yml` is in the repository. Its row says `protected, requires ci` when it does.
- Status: `would-update` when the plan has `generate`. `nothing to do` only when all seven actions are `none`. `outputs.items` has seven items; `outputs.generate` is true when any action is `generate`.

- [ ] **Step 1: Write the scenarios** (seed `examples/with-components.json`: `web` at `web`, `api` at `services/api`):

```
# project-plan-components-to-generate   (repository as declared but for the code; no local go.mod; no ci.yml anywhere)
OUTPUT to generate: api, web
OUTPUT "item": "ci", "state": "missing", "action": "generate"
OUTPUT "generate": true
OUTPUT "status": "would-update"
NOT_CALLED --method|^git (switch|add|commit|-c credential)
# project-plan-components-as-declared   (files/ has both modules and a matching ci.yml; the repository has ci.yml; ruleset with the check)
OUTPUT "item": "components", "state": "as declared"
OUTPUT "item": "ci", "state": "as declared"
OUTPUT requires ci
OUTPUT nothing to do
OUTPUT "status": "unchanged"
# project-plan-ci-not-merged            (files/ has the generated files; git status lists them as untracked; ci.yml not in the repository; ruleset WITHOUT the check)
OUTPUT "item": "declaration".*"action": "propose"
OUTPUT "item": "protection".*"action": "none"
OUTPUT_NOT requires ci
# project-plan-ci-merged-protection     (ci.yml in the repository; ruleset without the check)
OUTPUT "item": "protection".*"action": "update"
OUTPUT "status": "would-update"
# project-plan-ci-differs               (local ci.yml has the marker of one component)
OUTPUT "item": "ci", "state": "differs", "action": "generate"
# project-plan-components-proposed      (an open tooling pull request)
OUTPUT proposed in pull request #4
OUTPUT "item": "components", "state": "not checked until the change is merged"
NOT_CALLED contents/\.github/workflows|go\.mod
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Change `SKILL.md`** ("The declaration's rules" untouched).
- [ ] **Step 4: Run them and every existing `project-plan-*` scenario (unchanged, none may need a new fixture); expected PASS.**
- [ ] **Step 5: Commit:** `Give project-plan the components and ci rows`.

### Task 7: `project-apply` — generate, then propose

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md`, `.claude-plugin/plugins/aleogr/.claude-plugin/plugin.json` (`0.8.0`), the `aleogr` description in `marketplace.json`
- Create: scenarios `project-apply-generate*`, `project-apply-require-ci`

**Interfaces:**
- A plan with `generate` needs `confirm=yes` (it exposes nothing).
- New first part of step 4, when the plan has `generate` or the `declaration` action is `propose`:
  1. For each component in `to generate`: `aleogr-stack-go:go_setup component path version module mode=apply`. `failed` or `pending`: stop.
  2. `ci` `generate`: `github_ci-setup owner name components workflows mode=apply`. `failed`: stop.
  3. `github_pull-request-open owner name paths=<all tooling paths, comma-separated> title="<title>" mode=apply`, with the title `Change the project declaration` when only the declaration changed, `Add the components <names> and CI` when components were generated, `Update CI` when only `ci.yml` was regenerated. It ends as the proposal of stage 3c-1 ends (`updated`, the `pending` item to merge, no final plan).
- After the merge, the run that updates the folder plans again; that plan lists `protection` `update` (now with the check), applied by `github_branch-protect owner name checks=ci mode=apply`. `checks=ci` is passed whenever the plan's protection row was computed with the check.
- The birth is unchanged: a declaration born with components is created, configured, sent and protected without the check, and its final plan lists `generate` — the run ends `created` with a `pending` item `run /aleogr:project-apply confirm=yes to generate the components`.

- [ ] **Step 1: Write the scenarios:**

```
# project-apply-generate              (confirm=yes; seed with-components; repository exists, protected without the check, no code, no ci.yml)
FILE web/go.mod ^module github\.com/example-org/demo/web$
FILE services/api/main.go api: ok
FILE .github/workflows/ci.yml ^# aleogr-ci 1 api:services/api:go:1\.27,web:web:go:1\.27$
CALLED ^git add -- .*web/go\.mod
CALLED ^git commit -m "?Add the components api, web and CI"? -- 
CALLED ^gh pr create --repo example-org/demo
NOT_CALLED --method|^git .*push .*origin main
OUTPUT "status": "updated"
OUTPUT merge https://github\.com/example-org/demo/pull/7
# project-apply-generate-unconfirmed  (no argument)
NO_FILE web/go.mod
NO_FILE .github/workflows/ci.yml
OUTPUT "status": "pending"
# project-apply-require-ci            (confirm=yes; folder behind; after the pull: code and ci.yml local and in the repository; ruleset without the check)
ORDER ^git -c credential.* pull --ff-only origin main >> ^gh api --method PUT repos/example-org/demo/rulesets/123
CALLED --input .*ruleset-main-ci\.json
OUTPUT "status": "updated"
OUTPUT ^[[:space:]]*nothing to do[[:space:]]*$
# project-apply-generate-folder-not-empty (confirm=yes; files/web/handler.go exists, no go.mod)
NO_FILE web/go.mod
NOT_CALLED ^gh pr create|^git (switch|commit)
OUTPUT "status": "pending"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Change `SKILL.md`**; bump the version.
- [ ] **Step 4: Run them and every existing `project-apply-*` scenario (unchanged); expected PASS.**
- [ ] **Step 5: Commit:** `Let project-apply generate components and CI and propose them`.

### Task 8: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md`, `docs/CONTRACTS.md`, `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`, `.claude-plugin/schemas/README.md`
- Create: `docs/plans/2026-11-19-pilot-stage-3c-2-run.md`

- [ ] **Step 1: `docs/DESIGN.md`**, as decisions: section 2 (tree: the new plugin, skill, workflow, self-test, fixture, `dependabot.yml`, the second ruleset file); section 4 (the project `ci.yml` as built: marker, `changes`, one job per component, the job `ci`; the pinned commit is kept on regeneration; tags and Dependabot in projects stay open); section 11 (`components`; the starting point is generated once; generation uses the local declaration, application the merged one); section 12 and 12.2 (generate → propose; the check required after the merge); section 17 (3c-2 built; stage 3 complete); section 18 (new unchecked "First real run of stage 3c-2"; open items: tags `workflows-v1` and updates of the pinned commit in projects; removing a component).
- [ ] **Step 2: `docs/CONTRACTS.md`**: stack-\* (`setup` creates at most a minimal starting point, once, and never changes existing code; its output `files`, `ci`); repo-\* (`ci-setup` as built; `branch-protect` and `repo-describe` with `checks`).
- [ ] **Step 3: `docs/cloud-shell.md`, READMEs**: the new plugin (`claude plugin install aleogr-stack-go@aleogr`), the skills, declaring a component.
- [ ] **Step 4: The run checklist**, in the form of `2026-11-19-pilot-stage-3c-1-run.md`: update the two plugins and install the third; in `~/pilot`: `/aleogr:project-declare component=status stack=go`, then `component=admin stack=go`; `/aleogr:project-plan` (`to generate: admin, status`; `ci` `missing`); `/aleogr:project-apply` (`pending`); `/aleogr:project-apply confirm=yes` (the files are written, one pull request opens, the folder returns to `main`); on GitHub, the pull request's **Checks**: the workflow `ci` runs `changes`, `admin`, `status`, `ci` and all are green — what to send back if a job is red or the workflow did not start (the organization's Actions settings must allow actions and reusable workflows from other repositories); the owner merges; `/aleogr:project-apply confirm=yes` (updates the folder, updates the ruleset to require `ci`, `nothing to do`); `/aleogr:project-plan` (`unchanged`). Last proof, by hand on GitHub: edit `status/main_test.go` in the web editor on a new branch so that a test fails, open the pull request, see `ci` fail and the merge button blocked, then close the pull request and delete the branch. Nothing costs money (public repository).
- [ ] **Step 5: Check:** `grep -rn "aleogr-sandbox" .claude-plugin` prints nothing; every relative link in the changed documents resolves.
- [ ] **Step 6: Commit:** `Document stage 3c-2 and add its run checklist`.
