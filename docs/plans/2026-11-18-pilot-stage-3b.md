# Reference project, stage 3b: the declaration and the `project-*` skills — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A project's repository is described in `.aleogr/project.json`, and three orchestrator skills write that file, compare it with GitHub and make GitHub match it; a new repository is born from its declaration in one run.

**Architecture:** `project-declare`, `project-plan` and `project-apply` are `SKILL.md` files in the orchestrator plugin `aleogr`; they read the declaration and the owner's `defaults.json` and invoke the skills of `aleogr-repo-github`, never a provider command. One new family skill, `github_checkout-setup`, ties the local folder to the repository and sends the declaration as the first content. Everything is tested headless against fake `gh` and `git`.

**Tech Stack:** Claude Code plugin skills (Markdown), `gh`, `git` (2.28 or later, for `git init -b`), JSON Schema (draft 2020-12), the bash harness under `.claude-plugin/tests/`.

**Spec:** [`2026-11-18-pilot-stage-3b-design.md`](2026-11-18-pilot-stage-3b-design.md). Models of style: `.claude-plugin/plugins/aleogr/skills/platform-plan/SKILL.md`, `platform-apply/SKILL.md`, and the four skills of `aleogr-repo-github`.

## Global Constraints

- Everything versioned is in English. The repository is public: fixtures and examples use only `example-org`, `example-repo`, the project name `demo`, the account `example-user` with id `1234567`, and `owner@example.com` as the e-mail that must never be used. The name `aleogr-sandbox` appears only in documents, never under `.claude-plugin/`.
- No `SKILL.md` has `name:` in its frontmatter. Every skill validates before any command, shows each command before running it, runs only the commands (or invokes only the skills) its steps list, and ends with exactly one fenced `aleogr-result` block. A skill it invokes ends with its own block: used as input, never repeated.
- The orchestrator skills run no `gh` or `git` command themselves; they invoke `aleogr:tools-check` and the `aleogr-repo-github` skills. Orchestrator result blocks have `"family": "orchestrator"`, `"provider": "aleogr"`.
- Skills never wait for an answer: a needed confirmation ends the run `pending`, with the confirming text in `pending[].how`.
- Status rule: `pending` as a status means nothing was changed. Once something was done the status says what (`created`/`updated`) and what is left is an item in the `pending` list.
- The declaration is `.aleogr/project.json` in the folder the skill runs in. Its rules (Task 2) are written identically in `project-declare` and `project-plan`.
- Project `name`: 1 to 14 characters of `a-z`, `0-9`, `-`, starting with a letter, not ending with `-`; not `test`, not `shared`, not starting with `test-`. `repo.owner`, `repo.name`, `visibility`, topics, description: the rules of the `aleogr-repo-github` skills (description without `"`, backtick, `$`, `\`, `“`, `”`, `„` or a line break).
- The topic `aleogr-<name>` is derived: the list sent to GitHub is that topic plus `repo.topics`, sorted, without duplicates.
- Nothing becomes public without `confirmVisibility=public`. A real e-mail address is never used in a commit or printed; the account login is never repeated in an answer or a result block. No global git or machine configuration is changed.
- Exit codes: a command whose exit code matters is run alone, not piped into another command, and each decision names the text that identifies the case as well as the exit code.
- Values with spaces, commas or quotes are quoted in commands, in a form that works in bash and in PowerShell.
- Do not change the root `README.md`; never create `.github/README.md`; no skill, plugin or workflow beyond this plan. `docs/DESIGN.md` states decisions in the present tense; its section 16 gets no entry from this work.
- Commit messages end with the two attribution lines given by the session; no model name anywhere else. `.superpowers/` is never committed.
- Scenarios: `bash .claude-plugin/tests/run.sh <scenario>`, four at a time with `xargs -P 4`. Each run costs model usage. A thing that does not exist answers with an error and exit 1; expectations pin content, not prose; before/after uses `+after+` state responses.

## Review Focus

1. A declaration that is not valid JSON, has an unknown key or a wrong type: `project-plan` ends `failed` naming the problem, with no command. Tests: `project-plan-invalid-json`, `project-plan-unknown-key` (Task 6).
2. `project-plan` or `project-apply` run in a folder with no `.aleogr/project.json`: `failed`, "declare the project first", no command. Tests: `project-plan-no-declaration` (Task 6), `project-apply-no-declaration` (Task 7).
3. The machine has a global git identity with a real e-mail: the birth commit still uses the no-reply address. Test: `gh-checkout-global-identity` (Task 3).
4. `confirmVisibility=public` given to a plan with no visibility change: `failed`, nothing changed. Test: `project-apply-confirm-without-change` (Task 7).
5. An existing repository with history and no declaration (private or public) is never pushed to. Tests: `gh-checkout-not-a-birth` (Task 3), `project-apply-adopt-stops` (Task 7).
6. `project-declare` asked to change the name or the repository of an existing declaration: refused, file untouched. Test: `project-declare-rename-refused` (Task 5).

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/tests/bin/git`, `bin/fake-cli`, `run.sh`, `README.md` | fake `git`; scenario files; `FILE`/`NO_FILE` |
| `.claude-plugin/schemas/project.schema.json`, `schemas/examples/repo-only.json`, `schemas/README.md` | declaration version 1 |
| `.claude-plugin/plugins/aleogr/defaults.json` | `repo` block |
| `.claude-plugin/plugins/aleogr-repo-github/skills/github_checkout-setup/SKILL.md` | folder ↔ repository, first content |
| the four existing `aleogr-repo-github` skills | exit-code rule |
| `.claude-plugin/plugins/aleogr/skills/project-declare/`, `project-plan/`, `project-apply/` | the three skills |
| both `plugin.json` | `aleogr` 0.6.0, `aleogr-repo-github` 0.2.0 |
| `.claude-plugin/tests/scenarios/*` | scenarios |
| `docs/DESIGN.md`, `docs/CONTRACTS.md`, `docs/cloud-shell.md`, READMEs, `docs/plans/2026-11-18-pilot-stage-3b-run.md` | documents |

---

### Task 1: Harness — fake `git`, files in the working folder, file expectations

**Files:**
- Create: `.claude-plugin/tests/bin/git`, `.claude-plugin/tests/scenarios/harness-selftest-files/`
- Modify: `.claude-plugin/tests/bin/fake-cli`, `.claude-plugin/tests/run.sh`, `.claude-plugin/tests/README.md`

**Interfaces — produces:**
- Fake `git`: a wrapper like `bin/gh` (`fake-cli git "$@"`). Log line `git <arguments>`; response files prefixed `git_`, spaces and `/` as `_`. Everything else as for `gh`.
- A scenario may have a `files/` folder: its content is copied into the working folder before Claude starts (`files/.aleogr/project.json` → `<cwd>/.aleogr/project.json`).
- Two expectation kinds, checked on the working folder after the run: `FILE <relative path> <regex>` (the file exists and some line matches) and `NO_FILE <relative path>` (it does not exist).
- `run.sh` adds `Write` and `Edit` to `--allowedTools`.

- [ ] **Step 1: Write scenario `harness-selftest-files`.** `files/seed.txt` contains `seed-content`. The prompt asks Claude to run exactly `git status --short`, then to create the file `out/result.json` containing `{"copied": "<the content of seed.txt>"}`, and to report. `responses/git_status.txt` holds `?? seed.txt`. `expect.txt`:

```
CALLED ^git status --short$
OUTPUT seed\.txt
FILE out/result.json "copied": ?"seed-content"
NO_FILE out/other.json
```

- [ ] **Step 2: Run it; expected FAIL** (unknown expectation kinds, no seed file).
- [ ] **Step 3: Implement.** In `fake-cli`, generalise the `gh` branch to "any tool other than `gcloud`" (prefix `<tool> ` / `<tool>_`, `/` as `_`, the `--input` rule kept for every such tool); `gcloud` stays byte-for-byte as it is. In `run.sh`: copy `files/` (dotfiles included) into the working folder; the two new kinds; the two extra allowed tools; in the printed call log, lines starting with `gh ` or `git ` are shown as they are and the others get the `gcloud ` prefix.
- [ ] **Step 4: Run `harness-selftest-files`, `harness-selftest`, `harness-selftest-gh`, `create-apply`, `gh-protect-apply`; expected PASS.** Then check one thing and write it in the report: does Claude Code itself call `git` during a run (lines in the call log that the prompt did not ask for)? If it does, say which, so that later scenarios never use a bare `NOT_CALLED ^git`.
- [ ] **Step 5: Update `tests/README.md`** (the fake `git`, `files/`, the two kinds) **and commit:** `Add a fake git and file checks to the skill tests`.

### Task 2: The declaration format and the defaults

**Files:**
- Create: `.claude-plugin/schemas/project.schema.json`, `.claude-plugin/schemas/examples/repo-only.json`
- Modify: `.claude-plugin/schemas/README.md`, `.claude-plugin/plugins/aleogr/defaults.json`

**Interfaces — produces (the rules Tasks 5 and 6 copy):**
- Top level, no other key allowed: `$schema` (optional string), `version` (required, the number `1`), `name` (required, the project name rule), `repo` (required object), `notes` (optional string).
- `repo`, no other key allowed, all required except `topics`: `provider` (`"github"`), `owner`, `name`, `visibility` (`"public"` or `"private"`), `description` (string, 1 to 350 characters, the description rule), `topics` (array of topic strings, unique, default `[]`; it may not contain `aleogr-<name>`, which is derived), `settings`.
- `settings`, no other key allowed, all seven required booleans: `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`; at least one of the first three is `true`.
- The canonical file is written with two-space indentation, keys in the order above, a final newline.
- `defaults.json` gains, after `domain`:

```json
"repo": { "provider": "github", "visibility": "private", "settings": { "mergeCommit": true, "squash": true, "rebase": false, "deleteBranchOnMerge": true, "issues": true, "wiki": false, "projects": false } },
```

- [ ] **Step 1: Write `examples/repo-only.json`** (name `demo`, owner `example-org`, repository `demo`, `private`, description `Demo project`, topics `["sample"]`, the default settings) and four broken variants in a temporary folder outside the repository: an unknown top-level key; `name` `test-demo`; `settings` without `wiki`; all three merge methods `false`.
- [ ] **Step 2: Write `project.schema.json`** (draft 2020-12; the "at least one merge method" and the name exclusions expressed in the schema; the derived-topic rule is prose only, in `description`).
- [ ] **Step 3: Validate** with any JSON Schema validator available without adding anything to the repository (for example `python3 -m venv` in a temporary folder with `jsonschema`): the example passes, each broken variant fails for its own reason. Put the commands and output in the report.
- [ ] **Step 4: Add the `repo` block to `defaults.json`; run `platform-plan-empty`** (it reads the same file); expected PASS.
- [ ] **Step 5: Update `schemas/README.md`** (what version 1 holds, the derived topic, the example) **and commit:** `Add the project declaration schema, version 1`.

### Task 3: `github_checkout-setup`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-repo-github/skills/github_checkout-setup/SKILL.md`, scenarios `gh-checkout-*`
- Modify: `.claude-plugin/plugins/aleogr-repo-github/.claude-plugin/plugin.json` (`0.2.0`), the `marketplace.json` description if it lists skills

**Interfaces:**
- Arguments: `owner`, `name`, `path` (default `.aleogr/project.json`; a relative path with no `..`, no leading `/`, no spaces), `message` (default `Add the project declaration`; the description rule), `mode`.
- Reading steps, both modes:
  1. `gh api repos/<owner>/<name>` — classified exactly as in `github_repo-describe` (copy the text). `HTTP 404`: state `not-sent`, no further command.
  2. The local file at `path` is read with the Read tool; missing or not valid JSON: `failed`.
  3. `gh api repos/<owner>/<name>/contents/<path> -H "Accept: application/vnd.github.raw"` — exit 0: the repository's copy; `HTTP 404`: absent; anything else: `failed`.
  4. Present: compare the two as JSON values (key order, spacing and line endings ignored). Equal: state `equal`. Different: state `differs`.
  5. Absent: `gh api "repos/<owner>/<name>/commits?per_page=2"` — exactly one commit: state `not-sent` (a birth). Two: state `missing`. An empty repository (`HTTP 409`): `failed`, "the repository has no commit".
- `plan` ends there: `equal` → `unchanged`; `not-sent` → `would-create`; `differs` → `pending`, item `declaration differs from the repository`, how "merge the change (a pull request), then update this folder"; `missing` → `pending`, item `declaration is not in the repository`, how "open a pull request that adds `<path>`". Both items have `"reason": "manual"`.
- `apply` acts only on `not-sent` with the repository existing (a repository that does not exist: `failed`, "create it first"); `equal`, `differs`, `missing` end as in `plan`. Commands, in order:
  6. `gh api user` — `login` and `id`, used only in step 9, never printed.
  7. `git rev-parse --is-inside-work-tree` — non-zero: `git init -b <defaultBranch>`.
  8. `git remote get-url origin` — non-zero: `git remote add origin https://github.com/<owner>/<name>.git`; a different address: `failed`, nothing changed.
  9. `git config --local user.name <login>` and `git config --local user.email <id>+<login>@users.noreply.github.com`, always, whatever `git config user.email` would say.
  10. `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull origin <defaultBranch>`
  11. `git add -- <path>`, then `git commit -m "<message>"`
  12. `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin <defaultBranch>` — refused with text containing `GH013`, `protected branch` or `rule violations`: status `pending`, item `declaration is not in the repository` (how: open a pull request), the local commit kept. Any other refusal: `failed`.
  13. Verify: steps 3 and 4 again; `equal` → `created`. Not equal or unreadable: `created` with a `pending` item `verify`.
- `outputs`: `{ "state": "equal|not-sent|differs|missing", "defaultBranch": "<branch or null>", "path": "<path>", "pushed": true|false }`. `resources`: the repository when it exists.

- [ ] **Step 1: Write the scenarios** (each with `files/.aleogr/project.json`, the example of Task 2 with owner `example-org`, repository `example-repo`):

```
# gh-checkout-plan-birth      (repo exists, contents 404, one commit; mode=plan)
CALLED ^gh api repos/example-org/example-repo/contents/\.aleogr/project\.json
CALLED ^gh api "?repos/example-org/example-repo/commits\?per_page=2
OUTPUT "state": "not-sent"
OUTPUT "status": "would-create"
# gh-checkout-plan-equal      (contents = same JSON with other spacing, key order and CRLF)
OUTPUT "state": "equal"
OUTPUT "status": "unchanged"
# gh-checkout-plan-differs    (contents has another description)
OUTPUT "state": "differs"
OUTPUT "status": "pending"
# gh-checkout-not-a-birth     (contents 404, two commits; mode=apply)
OUTPUT "state": "missing"
OUTPUT "status": "pending"
OUTPUT pull request
# gh-checkout-no-repository   (repo 404; mode=apply)
OUTPUT "status": "failed"
# gh-checkout-apply           (birth; rev-parse exits 128; remote get-url exits 2; contents answers 404, then the file +after+git_push)
ORDER ^git init -b main >> ^git remote add origin https://github.com/example-org/example-repo\.git
CALLED ^git config --local user\.name example-user$
CALLED ^git config --local user\.email 1234567\+example-user@users\.noreply\.github\.com$
ORDER ^git config --local user\.email >> ^git commit
ORDER ^git .*pull origin main >> ^git add -- \.aleogr/project\.json
CALLED ^git commit -m "?Add the project declaration"?
CALLED ^git .*credential\.helper=!gh auth git-credential.* push -u origin main
OUTPUT "status": "created"
OUTPUT "pushed": true
RESULT_NOT example-user
OUTPUT_NOT example-user
# gh-checkout-global-identity (as apply; the response for "git config user.email" is owner@example.com)
CALLED ^git config --local user\.email 1234567\+example-user@users\.noreply\.github\.com$
OUTPUT_NOT owner@example\.com
OUTPUT "status": "created"
# gh-checkout-push-protected  (push exits 1 with "remote: error: GH013: Repository rule violations found for refs/heads/main")
OUTPUT "status": "pending"
OUTPUT pull request
OUTPUT "pushed": false
# gh-checkout-push-refused    (push exits 1 with "fatal: unable to access ... 503")
OUTPUT "status": "failed"
RESULT_NOT "status": "pending"
# gh-checkout-other-remote    (remote get-url prints https://github.com/example-org/other.git)
NOT_CALLED ^git (config|commit|push|pull)
OUTPUT "status": "failed"
# gh-checkout-invalid-path    (path=../secret)
NOT_CALLED ^gh
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Write `SKILL.md`**, bump the version. Before writing, try in a temporary folder that the two `-c credential.helper` arguments are accepted by `git` as written (for example with `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' config --show-origin --get-all credential.helper`); record the output. The skill says that in PowerShell the same single-quoted form is used.
- [ ] **Step 4: Run them; expected PASS.**
- [ ] **Step 5: Commit:** `Add github_checkout-setup`.

### Task 4: The exit-code rule in the four existing GitHub skills

**Files:**
- Modify: `skills/github_repo-describe/SKILL.md`, `github_repo-create/SKILL.md`, `github_repo-configure/SKILL.md`, `github_branch-protect/SKILL.md` (and `github_checkout-setup/SKILL.md` so that all five carry the same sentence)

- [ ] **Step 1: Add one paragraph, identical in the five skills,** at the start of "Steps":

> A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted.

- [ ] **Step 2: Check each decision in the five skills names its identifying text** (they already name `HTTP 404`, `HTTP 403` + `Upgrade`; add the text for "not logged in" and "command not found" where only the exit code is named). No other change.
- [ ] **Step 3: Run** `gh-describe-missing`, `gh-describe-read-refused`, `gh-create-apply`, `gh-create-read-refused`, `gh-configure-apply`, `gh-protect-private-plan`, `gh-protect-no-admin`, `gh-checkout-apply`; expected PASS.
- [ ] **Step 4: Commit:** `Make the GitHub skills decide by text as well as exit code`.

### Task 5: `project-declare`

**Files:**
- Create: `.claude-plugin/plugins/aleogr/skills/project-declare/SKILL.md`, scenarios `project-declare-*`

**Interfaces:**
- Consumes: the rules of Task 2; `${CLAUDE_PLUGIN_ROOT}/defaults.json` (`repo`).
- Arguments: `name`, `owner`, `repoName`, `visibility`, `description`, `topics` (comma-separated extras; `topics=` empty means none), `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`, `notes`.
- No `.aleogr/project.json` in the folder: `name`, `owner` and `description` are required (missing: `failed`, naming them, nothing written); `repoName` defaults to `name`; the rest comes from `defaults.json`. Status `created`.
- File exists: it must be valid by the rules (else `failed`, file untouched); only the given arguments change. `name`, `owner` or `repoName` different from the file: `failed`, "that is another project", file untouched. Nothing differs: `unchanged`, file untouched. Otherwise `updated`.
- It writes the file in the canonical form (Task 2), shows it, and runs no command and invokes no skill.
- `outputs`: `{ "path": ".aleogr/project.json", "declaration": { the whole file }, "changes": ["<key path>"] }`.

- [ ] **Step 1: Write the scenarios:**

```
# project-declare-new        (name=demo owner=example-org description="Demo project")
FILE .aleogr/project.json "name": "demo"
FILE .aleogr/project.json "owner": "example-org"
FILE .aleogr/project.json "visibility": "private"
FILE .aleogr/project.json "rebase": false
FILE .aleogr/project.json "version": 1
NOT_CALLED ^gh
OUTPUT "status": "created"
# project-declare-new-public (… visibility=public topics=sample,docs repoName=demo-app)
FILE .aleogr/project.json "visibility": "public"
FILE .aleogr/project.json "name": "demo-app"
FILE .aleogr/project.json "docs"
OUTPUT "status": "created"
# project-declare-edit       (files/ has the example; topics=sample,status-page)
FILE .aleogr/project.json "status-page"
FILE .aleogr/project.json "description": "Demo project"
OUTPUT "status": "updated"
# project-declare-unchanged  (files/ has the example; visibility=private)
OUTPUT "status": "unchanged"
# project-declare-missing-owner   (name=demo description="Demo project")
NO_FILE .aleogr/project.json
OUTPUT "status": "failed"
# project-declare-invalid-name    (name=test-demo owner=example-org description="Demo project")
NO_FILE .aleogr/project.json
OUTPUT "status": "failed"
# project-declare-derived-topic   (… topics=aleogr-demo)
NO_FILE .aleogr/project.json
OUTPUT "status": "failed"
# project-declare-rename-refused  (files/ has the example; name=other)
FILE .aleogr/project.json "name": "demo"
OUTPUT "status": "failed"
# project-declare-broken-file     (files/.aleogr/project.json is "{ not json"; description="New")
FILE .aleogr/project.json not json
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Write `SKILL.md`** (the rules of Task 2 in a section titled "The declaration's rules", the text Task 6 copies).
- [ ] **Step 4: Run them; expected PASS.**
- [ ] **Step 5: Commit:** `Add project-declare`.

### Task 6: `project-plan`

**Files:**
- Create: `.claude-plugin/plugins/aleogr/skills/project-plan/SKILL.md`, scenarios `project-plan-*`

**Interfaces:**
- Consumes: "The declaration's rules" (copied verbatim from `project-declare`); `aleogr:tools-check command=gh`; `aleogr-repo-github:github_repo-describe` (`outputs.exists`, `visibility`, `description`, `topics`, `settings`, `protection.state`, `protection.matches`); `aleogr-repo-github:github_checkout-setup … mode=plan` (`outputs.state`).
- No arguments. Steps: read and validate `.aleogr/project.json` (missing: `failed`, "declare the project first with /aleogr:project-declare"; invalid: `failed`, naming the first problem) → `tools-check command=gh` (`failed`: stop) → `github_repo-describe owner=<repo.owner> name=<repo.name>` (`failed`: stop) → when the repository exists, `github_checkout-setup owner=… name=… mode=plan` (`failed`: stop).
- Items, in this order, each `{ "item", "state", "action" }`:

| Item | State → action |
|---|---|
| `repository` | `missing` → `create`; `exists` → `none` |
| `settings` | `as declared` → `none`; `differs: <names>` → `update` (names among `description`, `topics`, and the seven settings; topics compared as the derived topic plus `repo.topics`) |
| `visibility` | `as declared` → `none`; `differs` → `update`, with the note "needs confirmVisibility=<declared>" |
| `declaration` | checkout `equal` → `in the repository` / `none`; `not-sent` → `not sent yet` / `send`; `differs` → `differs from the repository` / `merge first`; `missing` → `not in the repository` / `open a pull request` |
| `protection` | `protected` and matches → `protected` / `none`; `protected` and not → `differs` / `update`; `unprotected` → `unprotected` / `create`; `unavailable` → `not available on this plan` / `none`, with the notice "main is held by the working rule, not by GitHub" |

- Repository `missing`: the other four are `follows the creation` with the action they will have (`update`, `none`, `send`, `create`; `visibility` is `none` because it is created as declared), and no further skill is invoked.
- Declaration `differs`: `settings`, `visibility` and `protection` are `not checked until the change is merged` / `none`.
- It writes the line `nothing to do` only when every action is `none`. `status`: `unchanged` then; `would-create` when the repository is to create; `would-update` for any other `create`/`update`/`send`; `pending` when the only non-`none` actions are `merge first` or `open a pull request` (item in `pending` with the how of the checkout skill); `failed`.
- `outputs`: `{ "project": "<name>", "repository": "<owner>/<name>", "visibility": "<declared>", "exposes": true|false, "items": [...] }` — `exposes` is true when the plan would create a public repository or make one public.

- [ ] **Step 1: Write the scenarios** (all with `files/.aleogr/project.json`; fixtures for both skills' calls):

```
# project-plan-missing-repository
ORDER ^gh --version >> ^gh api repos/example-org/demo$
NOT_CALLED contents
OUTPUT "item": "repository", "state": "missing", "action": "create"
OUTPUT "status": "would-create"
OUTPUT "exposes": false
# project-plan-missing-public      (declared public)
OUTPUT "exposes": true
# project-plan-nothing-to-do      (everything as declared, ruleset matches, contents equal)
OUTPUT nothing to do
OUTPUT "status": "unchanged"
NOT_CALLED --method|^gh repo|^git (commit|push)
# project-plan-settings-differ    (rebase true, an extra topic on GitHub)
OUTPUT "item": "settings".*rebase
OUTPUT "item": "settings".*topics
OUTPUT "status": "would-update"
# project-plan-visibility-differs (declared public, GitHub private)
OUTPUT confirmVisibility=public
OUTPUT "exposes": true
# project-plan-private-unprotected-plan-limit (private, rulesets read refused with 403 Upgrade, the rest as declared)
OUTPUT not available on this plan
OUTPUT nothing to do
OUTPUT "status": "unchanged"
# project-plan-declaration-differs
OUTPUT "action": "merge first"
OUTPUT not checked until the change is merged
OUTPUT "status": "pending"
# project-plan-birth-interrupted  (repository exists with one commit, no declaration, unprotected, settings at GitHub defaults)
OUTPUT "item": "declaration".*"action": "send"
OUTPUT "item": "protection".*"action": "create"
# project-plan-no-declaration     (no files/)
NOT_CALLED ^gh
OUTPUT project-declare
OUTPUT "status": "failed"
# project-plan-invalid-json  and  project-plan-unknown-key
NOT_CALLED ^gh
OUTPUT "status": "failed"
# project-plan-gh-not-logged-in
NOT_CALLED ^gh api
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Write `SKILL.md`.**
- [ ] **Step 4: Run them; expected PASS.**
- [ ] **Step 5: Commit:** `Add project-plan`.

### Task 7: `project-apply`

**Files:**
- Create: `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md`, scenarios `project-apply-*`
- Modify: `.claude-plugin/plugins/aleogr/.claude-plugin/plugin.json` (`0.6.0`), the `aleogr` entry's description in `marketplace.json`

**Interfaces:**
- Consumes: `aleogr:project-plan` (`outputs.items`, `outputs.exposes`, `outputs.visibility`); the five `aleogr-repo-github` skills.
- Arguments: `confirm=yes`, `confirmVisibility=public|private` (any other value: `failed`).
- Steps:
  1. Invoke `aleogr:project-plan`. `failed`: stop with its cause. Every action `none`: no confirmation is needed; with no argument or with `confirm=yes` the run ends `unchanged` with the line `nothing to do`; with a `confirmVisibility` it ends `failed` by the last rule of step 3.
  2. An action `merge first` or `open a pull request`: `pending`, nothing changed, with the plan's how.
  3. Confirmation, before any change — the run is all or nothing:
     - `exposes` true: needs `confirmVisibility=public`. Without it: `pending`, how `/aleogr:project-apply confirmVisibility=public`, and one sentence saying the repository would be public.
     - a visibility change to private: needs `confirmVisibility=private`, the same way.
     - otherwise: needs `confirm=yes`; without it `pending`, how `/aleogr:project-apply confirm=yes`.
     - `confirmVisibility` given when the plan has no visibility change or creation in that direction: `failed`, nothing changed.
  4. Act, in this order, invoking only what the plan lists:
     - `repository` `create`: `github_repo-create owner name visibility description="<…>" topics=<derived + extras> mode=apply`, plus `confirmVisibility=public` when declared public.
     - `settings` `update`, or after a creation: `github_repo-configure owner name description="<…>" topics=<…> <the seven settings> mode=apply`; a `visibility` `update` goes in the same call as `visibility=<declared> confirmVisibility=<declared>`.
     - `declaration` `send`: `github_checkout-setup owner name mode=apply`.
     - `protection` `create` or `update`, or after a creation: `github_branch-protect owner name mode=apply`. Its `pending` with reason `plan-limit` is the expected end on a private repository and does not stop the run.
     - Any other step ending `failed`, or with the status `pending`, or with a non-empty `pending` list: stop; the answer carries its cause and its items.
  5. Invoke `aleogr:project-plan` again, in full. Write `nothing to do` only if that plan wrote it; otherwise list what is left and end `pending`.
- `status`: `created` when the repository was created in this run; `updated` when anything else changed; `unchanged`; `pending`; `failed`. `outputs`: `{ "project", "repository", "url", "items": [the final plan's items] }`.

- [ ] **Step 1: Write the scenarios:**

```
# project-apply-birth-private     (confirm=yes; repository 404, then everything +after+ each step; rulesets read refused 403 Upgrade)
ORDER ^gh repo create example-org/demo .*--private >> ^gh repo edit example-org/demo
ORDER ^gh repo edit example-org/demo .*--enable-rebase-merge=false >> ^git .*push -u origin main
CALLED ^gh repo edit .*--add-topic aleogr-demo
NOT_CALLED --method POST
OUTPUT nothing to do
OUTPUT "status": "created"
# project-apply-birth-public      (declared public, confirmVisibility=public; rulesets list [] then the ruleset +after+ POST)
CALLED ^gh repo create example-org/demo .*--public
ORDER ^git .*push -u origin main >> ^gh api --method POST repos/example-org/demo/rulesets
OUTPUT nothing to do
OUTPUT "status": "created"
# project-apply-birth-public-unconfirmed   (declared public, confirm=yes)
NOT_CALLED ^gh repo|--method|^git (init|commit|push)
OUTPUT confirmVisibility=public
OUTPUT "status": "pending"
# project-apply-unconfirmed       (private birth, no argument)
NOT_CALLED ^gh repo|--method|^git (init|commit|push)
OUTPUT "status": "pending"
# project-apply-update-settings   (confirm=yes; repository exists, rebase differs, rest as declared)
CALLED ^gh repo edit example-org/demo .*--enable-rebase-merge=false
NOT_CALLED ^gh repo create|--method|^git (commit|push)
OUTPUT nothing to do
OUTPUT "status": "updated"
# project-apply-nothing-to-do     (no argument; everything as declared)
NOT_CALLED ^gh repo|--method|^git (commit|push)
OUTPUT nothing to do
OUTPUT "status": "unchanged"
# project-apply-merge-first       (confirm=yes; contents differ)
NOT_CALLED ^gh repo|--method|^git (commit|push)
OUTPUT "status": "pending"
# project-apply-adopt-stops       (confirm=yes; private repository with two commits and no declaration)
NOT_CALLED ^git (init|commit|push)|^gh repo
OUTPUT pull request
OUTPUT "status": "pending"
# project-apply-confirm-without-change   (confirmVisibility=public; private as declared, rebase differs)
NOT_CALLED ^gh repo|--method|^git (commit|push)
OUTPUT "status": "failed"
# project-apply-step-fails        (confirm=yes; private birth, gh repo create exits 1 with HTTP 403)
NOT_CALLED ^gh repo edit|^git (init|commit|push)
OUTPUT "status": "failed"
# project-apply-no-declaration    (no files/)
NOT_CALLED ^gh
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Write `SKILL.md`**, bump the version.
- [ ] **Step 4: Run them; expected PASS.** These are long runs (many nested skills): run two at a time if four time out, and say in the report how long the birth scenarios took.
- [ ] **Step 5: Commit:** `Add project-apply`.

### Task 8: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md`, `docs/CONTRACTS.md`, `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`, `.claude-plugin/README.md` if it lists skills
- Create: `docs/plans/2026-11-18-pilot-stage-3b-run.md`

- [ ] **Step 1: `docs/DESIGN.md`**, as decisions:
  - section 2 tree: the three `project-*` skills and `github_checkout-setup` as built, the schema and its example, the fake `git`.
  - section 7: project state is discovered from the provider; there is no `state.json` until something cannot be discovered (the open question is answered for now).
  - section 11: the declaration's version 1 (what it holds and that it grows by stage), the derived topic, the birth (declaration sent as the first content, then the protection), the rule that after the birth only the merged declaration is applied, and that a repository with history is adopted by pull request.
  - section 12: the three skills as built, and the confirmation rule (one per run, all or nothing, `confirmVisibility` for exposure).
  - section 12.2: for the repository part, the order create → configure → send the declaration → protect.
  - section 17: 3b built; section 18: the exit-code item closed, a new unchecked item "First real run of stage 3b" linking the checklist.
- [ ] **Step 2: `docs/CONTRACTS.md`**: `checkout-setup` in the repo-* table (input, output, the birth rule, the commit identity, `pending` with reason `manual` in `plan`); `repo-create` loses `local directory`; section 1.4 says a `plan` may be `pending` with reason `manual` for a step only the owner can take.
- [ ] **Step 3: `docs/cloud-shell.md`**: working in a project folder (`mkdir ~/<project> && cd ~/<project> && claude`), the three skills in the table, updating the two plugins.
- [ ] **Step 4: READMEs** ("What exists").
- [ ] **Step 5: The run checklist**, in the form of `2026-11-18-pilot-stage-3a-run.md`, with the seven steps of the design's "The real run": the exact text of each command, the expected `status` and table, and what to send back. It includes: how to delete `aleogr-sandbox/pilot` by hand (Settings → General → Delete this repository) and that the old checkout folder, if any, is not reused; `project-declare name=pilot owner=aleogr-sandbox visibility=public description="Reference project of aleogr: status pages per tenant"`; for step 7 the sentence the owner says to Claude Code to open the pull request ("abra um pull request com a mudança da declaração"), the merge, `git pull` in the folder, then `project-apply confirm=yes`. Nothing in it costs money.
- [ ] **Step 6: Check:** `grep -rn "aleogr-sandbox" .claude-plugin` prints nothing; every relative link in the changed documents resolves.
- [ ] **Step 7: Commit:** `Document stage 3b and add its run checklist`.
