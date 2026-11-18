# Reference project, stage 3c-1: the pull-request cycle — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A change to a project goes `project-apply` → the owner merges → `project-apply`: the tooling opens the pull request and, after the merge, updates the folder and applies.

**Architecture:** One new skill in `aleogr-repo-github`, `github_pull-request-open`, commits named files on a new branch and opens the pull request. `github_checkout-setup` learns to tell a stale folder from a local change and to fast-forward the folder. `project-plan` and `project-apply` replace the stage 3b endings `merge first` and `open a pull request` by actions the apply takes (`propose`, `update`) or names (`merge it`, `fix the folder`).

**Tech Stack:** Claude Code plugin skills (Markdown), `gh`, `git`, the bash harness under `.claude-plugin/tests/` (fake `gh` and `git`).

**Spec:** [`2026-11-19-pilot-stage-3c-design.md`](2026-11-19-pilot-stage-3c-design.md), part 3c-1. Models of style: the five skills of `aleogr-repo-github` (especially `github_checkout-setup`) and `aleogr/skills/project-plan`, `project-apply`.

## Global Constraints

- Everything versioned is in English. The repository is public: fixtures use only `example-org`, `example-repo`, the project `demo`, the account `example-user` with id `1234567`, and `owner@example.com` as the address that must never appear in an output. `aleogr-sandbox` appears only in documents, never under `.claude-plugin/`.
- No `SKILL.md` has `name:` in its frontmatter. Every skill validates before any command, shows each command before running it, runs only the commands (or invokes only the skills) its steps list, and ends with exactly one fenced `aleogr-result` block.
- The orchestrator skills run no `gh` or `git` command; they invoke `aleogr:tools-check` and the `aleogr-repo-github` skills.
- Skills never wait for an answer. Status `pending` means nothing was changed; once something was done the status says what (`created`/`updated`) and what is left is an item in the `pending` list. Each `pending` item is `{ "item", "reason", "how" }`.
- A commit made by the tooling: only the named files (`git commit -m "<message>" -- <paths>`); the checkout's identity set first, always, with `git config --local` to the account's login and `<id>+<login>@users.noreply.github.com`; never `--global`; never on the default branch (the birth of stage 3b aside). The login, the id, the no-reply address and the output of `git remote get-url` are never repeated in an answer or a result block (the `owner` argument as given is the exception).
- `git` reaches GitHub only as `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' <pull|push> …`, the same single-quoted form in bash and PowerShell.
- A command whose result decides a step is run alone, not piped; each decision names the identifying text as well as the exit code; raw error text is never quoted. The paragraph that says so is identical in every `aleogr-repo-github` skill: copy it from `github_checkout-setup`.
- Tooling branches are named `aleogr/change-<6 random characters of a-z0-9>`. A repository has at most one open tooling pull request.
- The skills never merge, close or delete a pull request or a branch.
- "The declaration's rules" stay byte-identical in `project-declare` and `project-plan`; this plan does not touch that section.
- Do not change the root `README.md`; never create `.github/README.md`; no skill, plugin or workflow beyond this plan. `docs/DESIGN.md` states decisions in the present tense; its section 16 gets no entry.
- Commit messages end with the two attribution lines given by the session; no model name anywhere else. `.superpowers/` is never committed.
- Scenarios: `bash .claude-plugin/tests/run.sh <scenario>`; four at a time with `xargs -P 4`, two at a time for `project-apply-*`. Each run costs model usage. A thing that does not exist answers with an error and exit 1; expectations pin content, not prose; no bare `NOT_CALLED ^git` (Claude Code itself runs `git … ls-files`).

## Review Focus

1. The folder has a local change to a file that is NOT in `paths` (the owner's own work): it is neither committed nor lost, and it does not block the proposal. Test: `gh-pr-open-other-changes` (Task 1).
2. A path given is a folder, or contains `..`: `failed` before any command. Tests: `gh-pr-open-folder-path`, `gh-pr-open-invalid-path` (Task 1).
3. An open tooling pull request already exists: nothing is committed or pushed, in any skill. Tests: `gh-pr-open-already-open` (Task 1), `project-apply-proposed-stops` (Task 4).
4. The folder was left on an `aleogr/change-*` branch by an interrupted run: nothing is done and the answer says how to return. Tests: `gh-checkout-other-branch-plan` (Task 2), `project-plan-folder-needs-attention` (Task 3).
5. After the merge, the merged change makes the repository public: the run updates the folder and stops for `confirmVisibility=public`. Test: `project-apply-update-then-exposure` (Task 4).
6. `confirm=yes` is missing on a plan that only proposes: nothing is committed. Test: `project-apply-propose-unconfirmed` (Task 4).

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/plugins/aleogr-repo-github/skills/github_pull-request-open/SKILL.md` | branch, commit of named files, push, pull request |
| `.../skills/github_checkout-setup/SKILL.md` | states `behind`, `needs-attention`; fast-forward of the folder |
| `.claude-plugin/plugins/aleogr/skills/project-plan/SKILL.md` | new `declaration` states and actions |
| `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md` | `propose`, `update`, the two stops |
| `.claude-plugin/plugins/aleogr/skills/project-declare/SKILL.md` | the visibility notice only where it is true |
| both `plugin.json`, `marketplace.json` | `aleogr` 0.7.0, `aleogr-repo-github` 0.3.0 |
| `.claude-plugin/tests/scenarios/*` | scenarios |
| `docs/DESIGN.md`, `docs/CONTRACTS.md`, `docs/cloud-shell.md`, READMEs, `docs/plans/2026-11-19-pilot-stage-3c-1-run.md` | documents |

---

### Task 1: `github_pull-request-open`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-repo-github/skills/github_pull-request-open/SKILL.md`, scenarios `gh-pr-open-*`
- Modify: `.claude-plugin/plugins/aleogr-repo-github/.claude-plugin/plugin.json` (`0.3.0`), the plugin's description in `marketplace.json` if it lists what the plugin does

**Interfaces:**
- Arguments: `owner`, `name`, `paths` (comma-separated; each a relative file path with no `..`, no leading `/`, no trailing `/`, no space), `title` (required in `apply`; the description rule of the sibling skills, 1 to 100 characters), `body` (optional, same character rule; default `Proposed by aleogr.`), `mode`.
- Reading steps, both modes, in this order:
  1. `gh api repos/<owner>/<name>` — classified as in `github_checkout-setup` (copy the text). `HTTP 404`: `failed`, "create the repository first". Take `default_branch`.
  2. `gh pr list --repo <owner>/<name> --state open --json number,url,headRefName` — the open tooling pull request is the one whose `headRefName` starts with `aleogr/change-` (several: the lowest number). Non-zero exit: `failed`.
  3. `git rev-parse --is-inside-work-tree` — not `true`: folder `not-a-checkout`.
  4. `git remote get-url origin` — compared by the rule of `github_checkout-setup` (case and a trailing `.git` or `/` ignored). Different or missing: folder `other-remote`.
  5. `git branch --show-current` — not `<default_branch>`: folder `other-branch`.
  6. `git rev-parse HEAD`, then `gh api repos/<owner>/<name>/commits/<sha>` — exit 0: the folder's last commit is in the repository; `HTTP 404` or `HTTP 422`: folder `local-commits`; anything else `failed`.
  7. `git status --porcelain -- <path1> <path2> …` — the paths it lists are `changed`. A listed entry that ends with `/` is a folder: `failed`, "paths must be files".
  - The folder is `ready` when steps 3 to 6 found nothing. Steps stop at the first folder problem (later steps are not run).
- `plan` ends there:
  - an open tooling pull request: `pending`, item `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge or close <url>" }`;
  - folder not `ready`: `pending`, item `{ "item": "this folder needs attention", "reason": "manual", "how": <one sentence per case: not a checkout of the repository; origin is another repository; "git switch <default_branch>"; the folder has commits that are not in the repository> }`;
  - `ready`, no open pull request, `changed` not empty: `would-create`;
  - `ready`, nothing changed: `unchanged`.
- `apply` goes on only from `would-create` (the other three end as in `plan`; `title` missing: `failed`):
  8. `gh api user` — `login` and `id`, for step 9 only.
  9. `git config --local user.name <login>` and `git config --local user.email <id>+<login>@users.noreply.github.com`.
  10. `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin <default_branch>` — non-zero: `failed`, "the change in this folder conflicts with what the repository has now"; nothing committed.
  11. `git switch -c aleogr/change-<random>`
  12. `git add -- <changed paths>`, then `git commit -m "<title>" -- <changed paths>`
  13. `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin aleogr/change-<random>` — non-zero: `git switch <default_branch>`, then `failed`; the answer says the commit is kept in the local branch and nothing reached GitHub.
  14. `gh pr create --repo <owner>/<name> --base <default_branch> --head aleogr/change-<random> --title "<title>" --body "<body>"` — exit 0: the last line of its output is the pull request's address. Non-zero: the branch is on GitHub but no pull request: status `updated`, item `{ "item": "open the pull request", "reason": "manual", "how": "<the same gh pr create command>" }`.
  15. `git switch <default_branch>`, always after step 11 succeeded, whatever happened after.
  - Status `created` when step 14 succeeded.
- `outputs`: `{ "folder": "ready|not-a-checkout|other-remote|other-branch|local-commits", "changed": ["<path>"], "openPullRequest": { "number", "url", "branch" } | null, "pullRequest": { "number", "url", "branch" } | null, "defaultBranch" }` — `openPullRequest` is what step 2 found; `pullRequest` is what this run created. `resources`: `[{ "type": "pull-request", "id": "<owner>/<name>#<n>", "name": "<branch>" }]` when created.

- [ ] **Step 1: Write the scenarios** (the folder is seeded with `files/.aleogr/project.json`; `git status --porcelain` answers ` M .aleogr/project.json` unless said otherwise):

```
# gh-pr-open-plan            (mode=plan, everything ready)
NOT_CALLED ^git (switch|add|commit|config|-c credential)
NOT_CALLED ^gh pr create
OUTPUT "status": "would-create"
OUTPUT "folder": "ready"
# gh-pr-open-apply           (mode=apply title="Change the project declaration")
ORDER ^git config --local user\.email 1234567\+example-user@users\.noreply\.github\.com >> ^git commit
ORDER ^git -c credential.* pull --ff-only origin main >> ^git switch -c aleogr/change-[a-z0-9]{6}
CALLED ^git commit -m "?Change the project declaration"? -- \.aleogr/project\.json
CALLED ^git -c credential\.helper= -c '?credential\.helper=!gh auth git-credential'? push -u origin aleogr/change-[a-z0-9]{6}
CALLED ^gh pr create --repo example-org/example-repo --base main --head aleogr/change-[a-z0-9]{6} --title
ORDER ^gh pr create >> ^git switch main
NOT_CALLED ^git push|^git .*push .*origin main|--global
OUTPUT "status": "created"
OUTPUT "number": 7
RESULT_NOT example-user
OUTPUT_NOT example-user|owner@example\.com
# gh-pr-open-already-open    (gh pr list answers one pull request, branch aleogr/change-abc123, number 4; mode=apply)
NOT_CALLED ^git (switch|add|commit|config|-c credential)|^gh pr create
OUTPUT "status": "pending"
OUTPUT "number": 4
# gh-pr-open-other-pr-ignored (gh pr list answers an open pull request with branch feature/x; mode=plan)
OUTPUT "openPullRequest": null
OUTPUT "status": "would-create"
# gh-pr-open-nothing-changed (git status --porcelain prints nothing; mode=apply)
NOT_CALLED ^git (switch|add|commit)|^gh pr create
OUTPUT "status": "unchanged"
# gh-pr-open-other-changes   (paths=.aleogr/project.json; the status call for that path lists only it; mode=apply)
CALLED ^git status --porcelain -- \.aleogr/project\.json$
CALLED ^git add -- \.aleogr/project\.json$
NOT_CALLED ^git (add|commit) .*(-A|--all| \.$)|^git (stash|reset|checkout|restore|clean)
OUTPUT "status": "created"
# gh-pr-open-not-a-checkout  (rev-parse exits 128; mode=apply)
NOT_CALLED ^git (switch|add|commit|init)|^gh pr create
OUTPUT "folder": "not-a-checkout"
OUTPUT "status": "pending"
# gh-pr-open-other-branch    (branch --show-current prints aleogr/change-zzz999; mode=apply)
NOT_CALLED ^git (switch|add|commit)|^gh pr create
OUTPUT "folder": "other-branch"
OUTPUT git switch main
# gh-pr-open-local-commits   (the commits read for the local sha exits 1 with HTTP 422)
OUTPUT "folder": "local-commits"
OUTPUT "status": "pending"
# gh-pr-open-conflict        (pull --ff-only exits 1; mode=apply)
NOT_CALLED ^git (switch|add|commit)|^gh pr create
OUTPUT "status": "failed"
# gh-pr-open-push-refused    (push exits 1 with a 503; mode=apply)
ORDER ^git -c credential.* push >> ^git switch main
NOT_CALLED ^gh pr create
OUTPUT "status": "failed"
# gh-pr-open-create-refused  (gh pr create exits 1; mode=apply)
CALLED ^git switch main$
OUTPUT "status": "updated"
OUTPUT gh pr create
# gh-pr-open-folder-path     (git status --porcelain answers "?? status/"; paths=status)
NOT_CALLED ^git (switch|add|commit)
OUTPUT "status": "failed"
# gh-pr-open-invalid-path    (paths=../x)
NOT_CALLED ^gh
OUTPUT "status": "failed"
# gh-pr-open-no-repository   (repository read 404)
NOT_CALLED ^gh pr
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Write `SKILL.md`**; bump the version. Check `gh pr create --help` and `gh pr list --help` for the flags used.
- [ ] **Step 4: Run them; expected PASS.**
- [ ] **Step 5: Commit:** `Add github_pull-request-open`.

### Task 2: `github_checkout-setup` tells a stale folder from a local change

**Files:**
- Modify: `.claude-plugin/plugins/aleogr-repo-github/skills/github_checkout-setup/SKILL.md`
- Create: scenarios `gh-checkout-behind-*`, `gh-checkout-local-change`, `gh-checkout-other-branch-plan`, `gh-checkout-not-a-checkout-differs`

**Interfaces:**
- The comparison step is unchanged. Only when the repository's copy is present and NOT equal, new read-only steps decide the state (both modes; no `git fetch`):
  1. `git rev-parse --is-inside-work-tree` — not `true`: state `needs-attention`, reason `not-a-checkout`.
  2. `git branch --show-current` — not the default branch: `needs-attention`, reason `other-branch`.
  3. `git status --porcelain -- <path>` — it lists the path: state `differs` (a local change, as in stage 3b).
  4. Nothing listed: `git rev-parse HEAD`, then `gh api repos/<owner>/<name>/commits/<sha>` — exit 0: state `behind`; `HTTP 404`/`HTTP 422`: `needs-attention`, reason `local-commits`.
- `outputs.state` gains `behind` and `needs-attention`; `outputs.reason` is the reason for `needs-attention`, else `null`; `outputs.updated` is true only when this run fast-forwarded the folder.
- `plan`: `behind` → `would-update`; `needs-attention` → `pending`, item `{ "item": "this folder needs attention", "reason": "manual", "how": <as in Task 1, same sentences> }`; `differs` → `pending` as today, but its item becomes `{ "item": "declaration changed in this folder", "reason": "manual", "how": "propose the change with a pull request" }`.
- `apply`: `behind` → `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin <defaultBranch>`; exit 0: status `updated`, then the read and comparison once more, expecting `equal` (otherwise a `pending` item `verify`); non-zero: `failed`. `needs-attention` and `differs` end as in `plan`. The birth path (`not-sent`) and `missing` are unchanged.
- Existing scenario `gh-checkout-plan-differs`: its fixtures gain the three git answers of a local change, and its expected item text changes.

- [ ] **Step 1: Write the scenarios:**

```
# gh-checkout-local-change        (plan; status --porcelain lists the path)
OUTPUT "state": "differs"
OUTPUT "status": "pending"
OUTPUT declaration changed in this folder
# gh-checkout-behind-plan         (plan; status prints nothing; the local sha is in the repository)
NOT_CALLED ^git (-c credential|pull|fetch)
OUTPUT "state": "behind"
OUTPUT "status": "would-update"
# gh-checkout-behind-apply        (apply; the repository's copy is newer than the seeded file)
CALLED ^git -c credential\.helper= -c '?credential\.helper=!gh auth git-credential'? pull --ff-only origin main
NOT_CALLED ^git (add|commit|init|config)|^git .*push
OUTPUT "updated": true
OUTPUT "status": "updated"
# gh-checkout-behind-pull-fails   (apply; the pull exits 1)
OUTPUT "status": "failed"
# gh-checkout-other-branch-plan   (plan; branch --show-current prints aleogr/change-zzz999)
OUTPUT "state": "needs-attention"
OUTPUT "reason": "other-branch"
OUTPUT git switch main
OUTPUT "status": "pending"
# gh-checkout-not-a-checkout-differs (plan; rev-parse exits 128)
OUTPUT "reason": "not-a-checkout"
# gh-checkout-local-commits-differs  (plan; the commits read for the local sha exits 1 with HTTP 422)
OUTPUT "reason": "local-commits"
```

  For `gh-checkout-behind-apply`, the fake cannot change the seeded file, so the verification after the pull will read a file that still differs: the scenario expects `"status": "updated"` with a non-empty `pending` (`RESULT_NOT "pending": \[\]`) and says so in a comment. The equal-after-update path is exercised for real in the run checklist.

- [ ] **Step 2: Run them, plus `gh-checkout-plan-differs` with its new expectation; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Change `SKILL.md`**: the new steps go after the comparison step; existing steps keep their numbers where possible, and every "step N" cross-reference is checked after the edit.
- [ ] **Step 4: Run the new scenarios and every existing `gh-checkout-*` scenario; expected PASS.**
- [ ] **Step 5: Commit:** `Teach github_checkout-setup a stale folder from a local change`.

### Task 3: `project-plan` — the declaration row

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-plan/SKILL.md`, existing scenarios `project-plan-declaration-differs`, `project-plan-protected-not-sent`
- Create: scenarios `project-plan-changed-here`, `project-plan-proposed`, `project-plan-folder-behind`, `project-plan-folder-needs-attention`

**Interfaces:**
- Consumes: `github_checkout-setup … mode=plan` (`outputs.state`, `outputs.reason`) and, new, `aleogr-repo-github:github_pull-request-open owner=<…> name=<…> paths=.aleogr/project.json mode=plan` (`outputs.openPullRequest`, `outputs.folder`), invoked after the checkout skill whenever the repository exists.
- The `declaration` row, first case that applies:

| Condition | State | Action |
|---|---|---|
| `openPullRequest` is not null | `proposed in pull request #<n>` | `merge it` |
| checkout `equal` | `in the repository` | `none` |
| checkout `not-sent`, repository not protected | `not sent yet` | `send` |
| checkout `behind` | `this folder is behind` | `update` |
| checkout `needs-attention`, or (`differs`, `missing`, or `not-sent` on a protected repository) while `folder` is not `ready` | `this folder needs attention` | `fix the folder` |
| checkout `differs` | `changed here` | `propose` |
| checkout `missing`, or `not-sent` on a protected repository | `not in the repository` | `propose` |

- The texts `merge first` and `open a pull request` no longer exist anywhere in the skill.
- While the action is `merge it`, `update`, `fix the folder` or `propose`, the rows `settings`, `visibility` and `protection` are `not checked until the change is merged` / `none`, and `exposes` is false.
- `pending` items: `merge it` → `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge <url>, then run /aleogr:project-apply confirm=yes" }`; `fix the folder` → the item of the skill that reported it.
- Status: `would-update` when the plan has `propose` or `update` (and no `create`); `pending` when its only non-`none` actions are `merge it` or `fix the folder`; the other statuses as today.

- [ ] **Step 1: Write the four scenarios and change the two existing ones:**

```
# project-plan-changed-here            (was project-plan-declaration-differs: rename it with git mv)
OUTPUT "state": "changed here"
OUTPUT "action": "propose"
OUTPUT not checked until the change is merged
OUTPUT "status": "would-update"
OUTPUT_NOT merge first
# project-plan-proposed                (gh pr list answers pull request 4 on aleogr/change-abc123)
OUTPUT proposed in pull request #4
OUTPUT "action": "merge it"
OUTPUT "status": "pending"
NOT_CALLED ^git (switch|add|commit|-c credential)
# project-plan-folder-behind
OUTPUT "state": "this folder is behind"
OUTPUT "action": "update"
OUTPUT "status": "would-update"
# project-plan-folder-needs-attention  (the folder is on aleogr/change-zzz999)
OUTPUT "action": "fix the folder"
OUTPUT git switch main
OUTPUT "status": "pending"
# project-plan-protected-not-sent      (existing; folder is a ready checkout)
OUTPUT "action": "propose"
OUTPUT_NOT "action": "send"
OUTPUT_NOT open a pull request
```

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Change `SKILL.md`** (steps, the items table, the answer, the status rules and the `pending` rules; "The declaration's rules" untouched).
- [ ] **Step 4: Run them and every other `project-plan-*` scenario** (their fixtures need the answer of `gh pr list`: an empty list `[]`, and the folder reads where the new step runs them); expected PASS.
- [ ] **Step 5: Commit:** `Give project-plan the proposal and folder states`.

### Task 4: `project-apply` — propose, update, and the two stops

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md`, `.claude-plugin/plugins/aleogr/.claude-plugin/plugin.json` (`0.7.0`), existing scenarios `project-apply-merge-first`, `project-apply-adopt-stops`
- Create: scenarios `project-apply-propose`, `project-apply-propose-unconfirmed`, `project-apply-proposed-stops`, `project-apply-update-then-apply`, `project-apply-update-then-exposure`, `project-apply-folder-needs-attention`

**Interfaces:**
- Step 2 (the stops, before any confirmation): an item with the action `merge it` or `fix the folder` → `pending`, nothing changed, with the plan's items.
- Confirmation is unchanged in its rules; a plan whose only actions are `propose` and/or `update` exposes nothing, so it needs `confirm=yes`.
- New in step 4, before the existing sub-steps:
  - `declaration` `update`: invoke `github_checkout-setup owner=<…> name=<…> mode=apply`. `failed`, or a non-empty `pending` list: stop. Otherwise invoke `aleogr:project-plan` again and go on **with that new plan**: if it needs a `confirmVisibility` that this run was not given, stop with status `updated` and the `pending` item naming `/aleogr:project-apply confirmVisibility=<value>`; if it has `merge it` or `fix the folder`, stop the same way with its items; otherwise carry on with its actions under the `confirm=yes` already given.
  - `declaration` `propose`: invoke `github_pull-request-open owner=<…> name=<…> paths=.aleogr/project.json title="Change the project declaration" mode=apply`. `created`: the run ends with status `updated` and the `pending` item `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge <url>, then run /aleogr:project-apply confirm=yes" }`; no other sub-step runs and no final plan is run (the answer says the folder shows the merged state again). Any other ending: stop with its cause and items.
- The existing sub-steps (create, configure, send, protect) and the final plan are unchanged.
- `outputs` gains `"pullRequest": { "number", "url" } | null`.

- [ ] **Step 1: Write the scenarios and change the two existing ones** (`project-apply-merge-first` becomes `project-apply-propose` by `git mv`; `project-apply-adopt-stops` keeps its name and now expects a proposal):

```
# project-apply-propose                 (confirm=yes; local change; folder ready; no open pull request)
CALLED ^git commit -m "?Change the project declaration"? -- \.aleogr/project\.json
CALLED ^gh pr create --repo example-org/demo --base main --head aleogr/change-[a-z0-9]{6}
NOT_CALLED ^gh repo|--method|^git .*push .*origin main
OUTPUT "status": "updated"
OUTPUT merge https://github\.com/example-org/demo/pull/7
OUTPUT /aleogr:project-apply confirm=yes
OUTPUT_NOT ^[[:space:]]*nothing to do[[:space:]]*$
# project-apply-propose-unconfirmed     (no argument)
NOT_CALLED ^git (switch|add|commit|-c credential)|^gh pr create
OUTPUT "status": "pending"
OUTPUT /aleogr:project-apply confirm=yes
# project-apply-proposed-stops          (confirm=yes; gh pr list answers pull request 4)
NOT_CALLED ^git (switch|add|commit|-c credential)|^gh pr create|^gh repo
OUTPUT pull request #4
OUTPUT "status": "pending"
# project-apply-update-then-apply       (confirm=yes; folder behind; after the pull the plan shows settings differs: topics)
ORDER ^git -c credential.* pull --ff-only origin main >> ^gh repo edit example-org/demo
CALLED ^gh repo edit example-org/demo .*--add-topic status-page
OUTPUT "status": "updated"
OUTPUT ^[[:space:]]*nothing to do[[:space:]]*$
# project-apply-update-then-exposure    (confirm=yes; folder behind; the merged declaration says public, GitHub private)
CALLED ^git -c credential.* pull --ff-only origin main
NOT_CALLED ^gh repo edit|--method
OUTPUT /aleogr:project-apply confirmVisibility=public
OUTPUT "status": "updated"
# project-apply-folder-needs-attention  (confirm=yes; folder on aleogr/change-zzz999)
NOT_CALLED ^git (switch|add|commit|-c credential)|^gh pr create|^gh repo
OUTPUT git switch main
OUTPUT "status": "pending"
# project-apply-adopt-stops             (existing; private repository with two commits, no declaration, folder ready; confirm=yes)
CALLED ^gh pr create
NOT_CALLED ^git .*push .*origin main
OUTPUT "status": "updated"
```

  The seeded declaration cannot change during a run, so in the two `update-then-*` scenarios the "merged" file the fixtures answer after the pull marker is the same content as the seeded file, and what differs is GitHub's state (topics; visibility): the fixtures are built so that the plan before the pull says `behind` and the plan after it says `equal`.

- [ ] **Step 2: Run them; expected FAIL.** Commit the scenarios.
- [ ] **Step 3: Change `SKILL.md`**; bump the version; the `aleogr` description in `marketplace.json` if needed.
- [ ] **Step 4: Run them and every other `project-apply-*` scenario** (fixtures gain the `gh pr list` answer and the folder reads); expected PASS.
- [ ] **Step 5: Commit:** `Let project-apply propose a change and update the folder`.

### Task 5: `project-declare` — the visibility notice only where it is true

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-declare/SKILL.md`, scenarios `project-declare-edit`, `project-declare-new-public`

- [ ] **Step 1: Change the expectations:** `project-declare-edit` adds `OUTPUT_NOT confirmVisibility`; `project-declare-new-public` adds `OUTPUT confirmVisibility=public`. Run them: `project-declare-edit` is expected to FAIL.
- [ ] **Step 2: Change the skill:** the sentence that nothing is public until `project-apply` runs with `confirmVisibility=public` is written only when the file is created with `visibility` `public`, or when this run changes `repo.visibility` to `public`. No other change; "The declaration's rules" untouched (check with a diff against `project-plan`).
- [ ] **Step 3: Run both; expected PASS.** Commit: `Say the visibility notice of project-declare only where it is true`.

### Task 6: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md`, `docs/CONTRACTS.md`, `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`
- Create: `docs/plans/2026-11-19-pilot-stage-3c-1-run.md`

- [ ] **Step 1: `docs/DESIGN.md`**, as decisions: section 2 (tree: the new skill); section 11.4 (after the birth a change is proposed by `project-apply` as a pull request and applied after the owner merges it; one tooling pull request at a time; the folder shows the merged state after a proposal; "only the merged declaration is applied" concerns the provider); section 12 (the cycle apply → merge → apply; `update` and the rule for a merged change of exposure); section 17 (3c in two parts, 3c-1 built); section 18 (close the `project-declare` notice item; new unchecked "First real run of stage 3c-1").
- [ ] **Step 2: `docs/CONTRACTS.md`**: repo-\* gains `pull-request-open` (input, output, the one-at-a-time rule, never merges); `checkout-setup` gains the states `behind` and `needs-attention` and the folder update.
- [ ] **Step 3: `docs/cloud-shell.md`** and `.claude-plugin/plugins/README.md`: the new skill; the cycle in three steps; the stage 3b sentence for Claude Code is no longer needed.
- [ ] **Step 4: The run checklist**, in the form of `2026-11-18-pilot-stage-3b-run.md`: update the two plugins (`aleogr` 0.7.0, `aleogr-repo-github` 0.3.0); in `~/pilot` (`cd ~/pilot && claude`): `/aleogr:project-plan` (`nothing to do`); `/aleogr:project-declare topics=status-page,demo` (`updated`); `/aleogr:project-apply` (`pending`, asks `confirm=yes`, nothing committed); `/aleogr:project-apply confirm=yes` (`updated`, a pull request address, the folder back on `main`); the owner merges on GitHub; `/aleogr:project-apply confirm=yes` (updates the folder, adds the topic `demo`, `nothing to do`); `/aleogr:project-plan` (`unchanged`). It says what each step is expected to print, what to send back, what `proposed in pull request #N` and `this folder needs attention` mean, and how to drop a proposal (close the pull request; the change is declared again to redo it). The check of the commit's `.patch` (no-reply address) is repeated for the pull request's commit.
- [ ] **Step 5: Check:** `grep -rn "aleogr-sandbox" .claude-plugin` prints nothing; `grep -rn "merge first" .claude-plugin docs --include=*.md` finds it only in the stage 3b plan, design and run documents; every relative link in the changed documents resolves.
- [ ] **Step 6: Commit:** `Document stage 3c-1 and add its run checklist`.
