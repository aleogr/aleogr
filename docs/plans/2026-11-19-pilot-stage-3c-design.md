# Reference project, stage 3c: design of the pull-request cycle, the Go components and CI

Status: waiting for the owner's approval. Source of truth after approval: [`DESIGN.md`](../DESIGN.md) and [`CONTRACTS.md`](../CONTRACTS.md); this document is what the implementation plans are written from.

## Intent

After stage 3b, `pilot` is a configured, protected repository that holds only its declaration. Stage 3c gives it code and a gate: two Go components, `status` and `admin`, each born from a minimal starting point that a skill generates, and CI that runs on every pull request and must pass before a merge.

Everything now reaches the repository through a pull request, because `main` is protected. In stage 3b that step was a long sentence the owner pasted for Claude Code. Stage 3c makes it part of the tooling: `project-apply` opens the pull request, the owner merges it, `project-apply` finishes.

The work is done in **two parts, each with its own plan, pull request and real run**:

- **3c-1, the cycle:** `project-apply` proposes a change by pull request and, after the merge, updates the folder and applies. Proven with a change to the declaration alone.
- **3c-2, the code:** components in the declaration, the Go starting point, the reusable CI workflow, the project's `ci.yml`, and the protection requiring the check.

## Goals

- One cycle for every change to a project: `project-apply` → the owner merges → `project-apply`.
- A pull request opened by the tooling has a new branch, never a commit on the default branch, GitHub's no-reply identity, and no change to any git configuration outside the folder.
- A component declared in `.aleogr/project.json` gets a starting point that compiles, has one test, and is generated once.
- `aleogr/aleogr` has its first reusable workflow, `ci-go.yml`, tested in this repository before a project uses it.
- A project has one `ci.yml`, generated from the declaration, that checks only the components a pull request touched and ends in a single job named `ci`.
- The protection of `main` requires the check `ci`, and only once `ci.yml` is on `main`.
- No cost: public repositories only use free Actions minutes; nothing runs in a cloud.

## Non-goals

- Deploy (`cd.yml`), the cloud project, the database: stage 4.
- Dev containers and Features, LSP, per-directory `CLAUDE.md`.
- A linter beyond `gofmt` and `go vet`.
- Shared Go code between components (`go.work`, a common module): when a component needs it.
- Dependabot in projects, and the tags `workflows-v1`/`actions-v1`: an open item (see "Versions of the reusable workflow").
- Merging a pull request: always the owner.
- The Windows app (PowerShell) as a proven path: the open item of stage 3b stands.

## Anti-goals

- A commit on a protected default branch, or a pull request that carries anything but the files the tooling names.
- A required check that no workflow produces (it would block every merge).
- Generated starting-point code overwriting code that already exists.
- A real e-mail address in a commit; a token or an account name printed.
- Any cost.

## Constraints

- The rules of stages 3a and 3b hold: skills never wait for an answer; status `pending` means nothing was changed; the orchestrator runs no provider command; one confirmation per run; decisions name the identifying text as well as the exit code; values are quoted for bash and PowerShell; no JSON body inline.
- `main` of `aleogr-sandbox/pilot` is protected by the ruleset `main` (pull request required, no bypass).
- `git` authenticates through `gh` for one command (`-c credential.helper= -c 'credential.helper=!gh auth git-credential'`), proven in the stage 3b run.
- Reusable workflows in `aleogr/aleogr` have only `on: workflow_call`, receive no inherited secrets and print no variables ([`DESIGN.md`](../DESIGN.md) sections 3 and 4). Third-party actions are pinned by commit SHA.
- `aleogr/aleogr` is public: fixtures and examples use fictitious values.

## Approaches

How generated and changed files reach a protected repository:

- **1. As in stage 3b:** the skills write files, the owner pastes a sentence for Claude Code to open the pull request. Nothing new to build; the sentence, with the push command inside, would be needed for every change of every project.
- **2. `project-apply` generates and opens the pull request (chosen).** A new GitHub skill opens it the safe way; the cycle is apply → merge → apply.
- **3. A separate `project-generate` skill** plus the pull-request skill, `project-apply` only comparing and applying. Cleaner split, four commands per change.

Who writes the first code of a component:

- **A skill generates a minimal starting point (chosen):** repeatable, and CI has something real to check from the first pull request.
- Claude Code writes it freely, the skills only prepare tooling. Less to build; every project would start differently.

The owner chose **2** and **the generated starting point**.

## Decided by the owner

- The generated starting point, and the change to the stack contract that it needs.
- Form 2: `project-apply` opens the pull request; the owner merges.

## My calls (the owner can overrule any of them)

### Part 3c-1: the cycle

**New skill `github_pull-request-open`** (contract action `pull-request-open`):

- Arguments: `owner`, `name`, `paths` (the **files** to include, comma-separated, relative; never a folder, so that nothing the tooling did not write — a built binary, a local `.env` — can ride along), `title`, `body`, `mode`.
- It requires the folder to be a checkout of the repository, on the default branch, with no local commit that is not in the repository. Otherwise `failed`, nothing changed.
- `apply`: brings the default branch up to date first (a fast-forward; if the local change conflicts with what the repository now has, `failed`, nothing committed); creates a branch `aleogr/change-<6 random characters>`; sets the checkout's identity to the no-reply address (always, as `github_checkout-setup` does); commits only `paths`; pushes the branch with the per-command credential form; opens the pull request with `gh pr create`; returns the folder to the default branch. Changes outside `paths` are neither committed nor discarded.
- **After a proposal the folder shows the merged state again**: the proposed files live in the pull request (and in the local branch, which is kept), not in the working tree. To drop a proposal the owner closes the pull request; to make it again, the change is declared again.
- **One open tooling pull request at a time per repository.** If an open pull request whose branch starts with `aleogr/change-` exists, nothing is created: `pending`, "merge or close pull request #N first".
- `plan`: reports that open pull request, if any (number and address), and whether `paths` differ from the default branch. It changes nothing.
- Status `created` with the pull request's number and address in `outputs`; it never merges.

**`github_checkout-setup` learns to tell a stale folder from a local change**, and to update the folder:

- State `behind`: the folder is on the default branch with no local change to the tooling's files, its last commit exists in the repository, and the repository's default branch is at a newer commit (the case right after a merge). `apply` then fast-forwards the folder (`git pull --ff-only` with the credential form). Nothing is pushed.
- State `needs-attention`: the folder is on another branch (an interrupted run), or its last commit is not in the repository (local commits). Nothing is done; the plan says what to fix by hand.
- To tell these apart, `plan` mode may run read-only `git` in the folder (`rev-parse`, `branch --show-current`, `status --porcelain`), never `git fetch`; what the repository has is still read through the API. In a folder that is not a checkout only the birth states occur.
- State `differs` keeps meaning a local change that the repository does not have.
- The birth (state `not-sent`) is unchanged.

**`project-plan`, row `declaration`:**

| State | Action |
|---|---|
| `in the repository` | `none` |
| `not sent yet` | `send` (the birth, unchanged) |
| `changed here` (local change) | `propose` |
| `proposed in pull request #N` | `merge it` (the owner's step) |
| `this folder is behind` | `update` |
| `not in the repository` (history, no declaration) | `propose` |
| `this folder needs attention` | `fix the folder` (by hand; the run stops) |

While the declaration is `changed here`, `proposed` or `behind`, the rows `settings`, `visibility` and `protection` stay `not checked until the change is merged`, as in stage 3b. When an open tooling pull request exists, the row is `proposed in pull request #N` whatever the folder holds. When there is a local change and the repository is also newer, `changed here` wins and the proposal starts by bringing the folder up to date.

**`project-apply`:**

- `propose`: invokes `github_pull-request-open` and ends with status `updated` and a `pending` item "merge pull request #N, then run /aleogr:project-apply confirm=yes".
- `merge it`: `pending`, nothing changed, naming the pull request.
- `update`: updates the folder, then plans again. If the new plan exposes nothing, the run goes on with it under the same `confirm=yes` (the owner reviewed the change when merging it). If the new plan changes exposure, the run stops there, `updated`, with the `pending` item that names `confirmVisibility=<value>`: a merged visibility change always takes one more run, on purpose.
- Confirmation is unchanged: `confirm=yes` for a run that exposes nothing (opening a pull request and updating the folder expose nothing); `confirmVisibility=<value>` when the plan being applied changes exposure.

The checklist of stage 3b's step 7 becomes: declare the change, apply, merge, apply.

### Part 3c-2: the code

**The declaration gains `components`** (optional list; version stays 1, existing files stay valid):

```json
"components": [
  { "name": "status", "stack": "go", "path": "status", "version": "<go version>" },
  { "name": "admin",  "stack": "go", "path": "admin",  "version": "<go version>" }
]
```

- `name`: 1 to 20 characters of `a-z`, `0-9`, `-`, starting with a letter; unique. `path`: a relative folder, default the name; unique; not under `.aleogr` or `.github`. `stack`: `go`, the only one implemented. `version`: the language version, `major.minor`.
- `defaults.json` gains `stacks.go.version`: the latest stable Go release at the time of building, checked on go.dev.
- `project-declare` gains `component=<name>` with `stack=`, `path=`, `version=`: it adds or changes one component per call. Removing a component is not in this stage.

**New plugin `aleogr-stack-go`, skill `go_setup`** (contract action `setup`):

- Arguments: `component`, `path`, `version`, `module` (the Go module path, `github.com/<owner>/<repository>/<path>`), `mode`.
- When `<path>/go.mod` does not exist it writes the starting point, from files shipped with the plugin: `go.mod`, `main.go` (an HTTP server on the port in `PORT`, default 8080; `/` answers the component's name and `ok`; `/healthz` answers `ok`) and `main_test.go` (one test of each handler, with `net/http/httptest`). No dependency outside the standard library, so no `go.sum`.
- When `go.mod` exists it writes nothing: `unchanged`. **The starting point is generated once and never overwritten.**
- One module per component folder. It needs no Go toolchain on the owner's machine: CI is where the code is compiled and tested.
- It returns the CI parameters of the component (the reusable workflow's name and its inputs) and the list of files it wrote.
- [`CONTRACTS.md`](../CONTRACTS.md), stack-\*: "`setup` never creates application code" becomes "`setup` creates at most a minimal starting point, once, and never changes existing code".

**Reusable workflow `.github/workflows/ci-go.yml` in `aleogr/aleogr`:**

- `on: workflow_call`, inputs `working-directory` and `go-version`; `permissions: contents: read`.
- Steps: checkout, set up Go, `gofmt -l` (fails when it lists a file), `go vet ./...`, `go test ./...`, `go build ./...`.
- `actions/checkout` and `actions/setup-go` pinned by commit SHA, with the version in a comment.
- **Tested here before a project uses it:** a small Go module under `.github/testdata/ci-go/` and a workflow `self-test-ci-go.yml` that calls `ci-go.yml` on it, on pull requests that touch the workflow or the fixture.
- `.github/dependabot.yml` for this repository's own action references (already in the design's tree).

**New skill `github_ci-setup`** (contract action `ci-setup`):

- Arguments: `owner`, `name`, `components` (name, path, stack and version of each), `mode`.
- It writes `.github/workflows/ci.yml` in the folder (it pushes nothing; the pull request carries it):
  - triggers: `pull_request`, and `push` to the default branch;
  - a job `changes` (`dorny/paths-filter`, pinned by SHA) with one output per component;
  - one job per component, `needs: changes`, `if:` on its output, `uses: aleogr/aleogr/.github/workflows/ci-go.yml@<sha>` with its `working-directory` and `go-version`;
  - a last job `ci`, `needs:` every component job, `if: always()`, that fails when a needed job failed or was cancelled and passes when they passed or were skipped.
- **The first line of the file is a marker**, `# aleogr-ci 1 <name>:<path>:<stack>:<version>,…`, built from the declaration. "Is `ci.yml` as declared?" is answered by comparing that line, not by comparing YAML.
- `ci.yml` is fully owned by the tooling: it is regenerated when the declaration's components change.
- Output `checks`: `["ci"]`.

**Versions of the reusable workflow.** `ci.yml` pins `ci-go.yml` to the commit of `aleogr/aleogr`'s `main` at the time it is first generated, and keeps that commit when regenerated (so that a plan does not differ every time `aleogr/aleogr` moves); `ref=latest` moves it. Tags (`workflows-v1`) and automatic updates in projects are an open item: they need a release step this repository does not have yet.

**`github_branch-protect` gains `checks=ci`:** a second ruleset file, equal to the first plus the rule that requires the status check `ci`. The file compared and sent is chosen by the argument. No JSON is built at run time.

**`project-plan` gains two rows, and one rule:**

| Item | States | Action |
|---|---|---|
| `components` | `as declared`; `to generate: <names>` (declared, no `go.mod` in the repository) | `none`; `generate` |
| `ci` | `as declared`; `missing`; `differs` (the marker); `not needed` (no component) | `none`; `generate`; `generate`; `none` |

- The protection is expected **with** the check `ci` exactly when `ci.yml` is on the default branch; otherwise without it.

**Generation works from the local declaration; application works from the merged one.** "After the birth only the merged declaration is applied" ([`DESIGN.md`](../DESIGN.md) section 11.4) is about changes to the provider (settings, visibility, protection). Writing files in the folder and proposing them changes nothing on the provider, so the rows `components` and `ci` are computed from the local declaration even while it is `changed here`.

**`project-apply`:** `propose` and `generate` are one step and one pull request. It runs `go_setup` for each component to generate, then `github_ci-setup`, then a single `github_pull-request-open` whose `paths` are the declaration plus exactly the files those two skills report having written. After the merge, the next run updates the folder and updates the protection to require `ci`.

### Tests

- Part 1: scenarios for `github_pull-request-open` (new pull request; one already open; not a checkout; on another branch; local commits; push refused; only `paths` committed), for the two new checkout states, and for the new plan and apply paths.
- Part 2: scenarios for `go_setup` (new, existing, invalid arguments; the generated files pinned by content), `github_ci-setup` (one and two components, regenerate keeps the pinned commit, marker), `github_branch-protect checks=ci`, the new plan rows and the apply that generates. The generated Go files are also compiled and tested for real once, in a temporary folder, as part of building the plugin.
- `ci-go.yml` is tested by `self-test-ci-go.yml` on the pull request of part 2.

### Versions

After 3c-1: `aleogr` 0.7.0, `aleogr-repo-github` 0.3.0. After 3c-2: `aleogr` 0.8.0, `aleogr-repo-github` 0.4.0, `aleogr-stack-go` 0.1.0 (new entry in `marketplace.json`).

## The real runs (checklists are written with each plan)

**3c-1**, in `~/pilot`: `project-declare topics=status-page,demo` → `project-apply confirm=yes` opens a pull request → the owner merges → `project-apply confirm=yes` updates the folder and adds the topic → `project-plan` says `nothing to do`.

**3c-2**: `project-declare component=status stack=go` and `component=admin stack=go` → `project-apply confirm=yes` generates `status/`, `admin/` and `ci.yml` and opens one pull request → **CI runs on that pull request and passes** → the owner merges → `project-apply confirm=yes` updates the folder and makes `ci` required → `project-plan` says `nothing to do`. Last proof: a pull request that breaks a test cannot be merged.

## Documents changed with this work

[`DESIGN.md`](../DESIGN.md) (sections 2, 4, 11, 12, 12.2, 17, 18), [`CONTRACTS.md`](../CONTRACTS.md) (repo-\*: `pull-request-open`, `ci-setup`, `checkout-setup`, `branch-protect`; stack-\*), [`cloud-shell.md`](../cloud-shell.md), the READMEs of plugins, workflows, schemas and tests.

## Left to the builder

- The exact `git` and `gh` commands, checked against the installed versions' help, and the random branch suffix in a form that works in bash and PowerShell.
- The commit SHAs of the third-party actions and the latest stable Go version, looked up when building.
- The exact YAML of `ci-go.yml` and of the generated `ci.yml`, and the expression of the job `ci`.
- How `project-plan` learns that `go.mod` and `ci.yml` exist on the default branch (which skill reads them), with the fewest extra calls.
- Wording of states, notices and scenarios.
