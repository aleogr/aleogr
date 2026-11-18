# Reference project, stage 3a: GitHub repository plugin — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new plugin `aleogr-repo-github` with four skills that describe, create, configure and protect a GitHub repository, public or private, plus a `gh` check in `tools-check`.

**Architecture:** Each skill is one `SKILL.md` that drives the `gh` CLI, like the cloud skills drive `gcloud`. Skills are tested headless against a fake `gh` that logs its calls, in the existing harness. Nothing is created on GitHub by this plan; the real run is a separate checklist the owner follows after the merge.

**Tech Stack:** Claude Code plugin skills (Markdown), `gh` (2.89 here, 2.104 in Cloud Shell), bash test harness under `.claude-plugin/tests/`.

**Spec:** [`2026-11-18-pilot-stage-3a-design.md`](2026-11-18-pilot-stage-3a-design.md). Read it, and one existing skill as the model of style: `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_environment-describe/SKILL.md`.

## Global Constraints

- Everything versioned is in English. The repository is public: fixtures use only `example-org`, `example-repo`, `https://github.com/example-org/example-repo`; no real owner, account name, token or e-mail anywhere (the organization name `aleogr-sandbox` appears only in documents, never in fixtures).
- No `SKILL.md` has `name:` in its frontmatter; the `description` names GitHub and the `gh` CLI.
- Every skill: validates arguments before any command (a broken rule ends with `status` `failed`, one sentence, no command); shows each command before running it; runs only the commands its steps list; ends with exactly one fenced `aleogr-result` block (`"family": "repo"`, `"provider": "github"`).
- Statuses: `plan` gives `would-create`, `would-update`, `unchanged`, `pending`, `failed`; `apply` gives `created`, `updated`, `unchanged`, `pending`, `failed`. `github_repo-describe` has no `mode` and reports `"mode": "plan"`.
- A missing `gh` (command not found), a `gh` that is not logged in, or a refusal: one sentence, no raw error text, `status` `failed`. The account name and the token are never printed.
- Values with spaces, commas or quotes are quoted in commands (PowerShell splits unquoted commas). A JSON body is a file under the plugin's `files/`, passed as `--input "${CLAUDE_PLUGIN_ROOT}/files/<file>"`, never inline.
- `owner`: 1 to 39 characters of `A-Z a-z 0-9 -`, not starting or ending with `-`. `name`: 1 to 100 characters of `A-Z a-z 0-9 . _ -`, not `.` or `..`. `visibility`: `public` or `private`. `mode`: `plan` (default) or `apply`. A topic: 1 to 50 characters of `a-z 0-9 -`, starting with a letter or digit.
- Nothing becomes public without `confirmVisibility=public` or the owner answering the question in that run.
- Do not change the root `README.md`; never create `.github/README.md`; create no skill, plugin or workflow beyond this plan.
- Commit messages end with the two attribution lines given by the session; no model name anywhere else.
- Run scenarios with `bash .claude-plugin/tests/run.sh <scenario>`; several at once with `printf '%s\n' <names> | xargs -P 4 -n 1 bash .claude-plugin/tests/run.sh`. Each run costs model usage: run a scenario when its step says so, not in loops.
- Scenario lessons from stages 1 and 2: a thing that does not exist answers with an error and exit 1, never with empty success; expectations pin content (a call, a status), not exact prose; "before and after a change" uses `+after+` state responses, not numbered files.

## Review Focus

1. A read that fails for a reason other than "not found" (HTTP 403, 5xx, network) must end `failed`, never be read as "the repository does not exist" (which would lead to a create). Tests: `gh-describe-read-refused` (Task 2), `gh-create-read-refused` (Task 3).
2. A rulesets read refused for a reason other than the plan (HTTP 403 "Must have admin rights") must end `failed`, not `pending`. Test: `gh-protect-no-admin` (Task 5).
3. `confirmVisibility` that does not equal the requested visibility, or given without `visibility`, is an argument error, not a confirmation. Tests: `gh-configure-confirm-mismatch` (Task 4), `gh-create-confirm-mismatch` (Task 3).
4. A repository that already has other rulesets (a different name) keeps them untouched and they are reported. Test: `gh-protect-other-ruleset` (Task 5).
5. A description with spaces, quotes and a comma reaches `gh` as one quoted value. Test: `gh-create-apply` (Task 3) uses `description="Status pages, per tenant"`.

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/plugins/aleogr-repo-github/.claude-plugin/plugin.json` | manifest, version `0.1.0` |
| `.claude-plugin/plugins/aleogr-repo-github/files/ruleset-main.json` | the one ruleset body |
| `.claude-plugin/plugins/aleogr-repo-github/skills/github_repo-describe/SKILL.md` | read state |
| `.../skills/github_repo-create/SKILL.md` | create |
| `.../skills/github_repo-configure/SKILL.md` | correct settings, visibility |
| `.../skills/github_branch-protect/SKILL.md` | ruleset `main` |
| `.claude-plugin/marketplace.json` | new entry |
| `.claude-plugin/tests/bin/fake-cli`, `bin/gcloud`, `bin/gh` | shared fake and two wrappers |
| `.claude-plugin/tests/run.sh`, `tests/README.md` | load the new plugin; document `gh` |
| `.claude-plugin/tests/scenarios/gh-*`, `tools-gh-*` | scenarios |
| `.claude-plugin/plugins/aleogr/skills/tools-check/SKILL.md`, `aleogr/.claude-plugin/plugin.json` | `command=gh`; version `0.5.0` |
| `docs/DESIGN.md`, `docs/CONTRACTS.md`, `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`, `docs/plans/2026-11-18-pilot-stage-3a-run.md` | documents |

---

### Task 1: Plugin skeleton and a fake `gh`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-repo-github/.claude-plugin/plugin.json`, `.claude-plugin/plugins/aleogr-repo-github/files/ruleset-main.json`, `.claude-plugin/tests/bin/fake-cli`, `.claude-plugin/tests/bin/gh`, `.claude-plugin/tests/scenarios/harness-selftest-gh/`
- Modify: `.claude-plugin/tests/bin/gcloud`, `.claude-plugin/tests/run.sh`, `.claude-plugin/tests/README.md`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Produces: the fake `gh`. Its log line is `gh <arguments>`; when the arguments contain `--input <file>`, the line ends with ` <<< ` followed by the file's content with all whitespace removed. Response files for `gh` live in the scenario's `responses/` with the prefix `gh_` (`gh_api_repos_example-org_example-repo.txt` answers `gh api repos/example-org/example-repo ...`: in the key, spaces and `/` are both written as `_`). `gcloud` log lines and response names stay exactly as they are (no prefix), so the 92 existing scenarios do not change.
- Produces: `ruleset-main.json`, exactly:

```json
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": false,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false,
      "allowed_merge_methods": ["merge", "squash", "rebase"]
    } }
  ]
}
```

- [ ] **Step 1: Write the self-test scenario `harness-selftest-gh`**, modelled on `scenarios/harness-selftest`. Its prompt asks Claude to run exactly `gh api repos/example-org/example-repo` and then `gh api --method POST repos/example-org/example-repo/rulesets --input <a file it first writes with {"name": "main"}>`, and to report the outputs. `responses/gh_api_repos_example-org_example-repo.txt` holds `{"name":"example-repo"}`. `expect.txt`:

```
CALLED ^gh api repos/example-org/example-repo$
CALLED ^gh api --method POST repos/example-org/example-repo/rulesets --input .* <<< \{"name":"main"\}$
OUTPUT example-repo
```

- [ ] **Step 2: Run it; expected FAIL** (the real `gh` answers, or no call is logged).

- [ ] **Step 3: Move the body of `bin/gcloud` to `bin/fake-cli`** with two additions driven by a first argument `<tool>`: for `gcloud`, behaviour is byte-for-byte what it is today (log line `$*`, key `$*` with spaces as `_`); for `gh`, the log line and the key are prefixed with `gh ` / `gh_`, the key also has `/` written as `_`, and the `--input` content is appended to the log line as defined above. `bin/gcloud` and `bin/gh` become two-line wrappers calling `fake-cli gcloud "$@"` / `fake-cli gh "$@"`. In `run.sh`: add `--plugin-dir "$plugins/aleogr-repo-github"`, and print the log under the heading `call log:` with `gcloud ` prefixed only to lines that do not start with `gh `.

- [ ] **Step 4: Create `plugin.json`** (`"name": "aleogr-repo-github"`, `"version": "0.1.0"`, `"description": "GitHub family: repositories, their settings and branch protection."`, `"author": { "name": "aleogr" }`), `ruleset-main.json`, and the `marketplace.json` entry (same description, `"category": "repo"`, `"displayName": "GitHub (repository)"`, `"source": "./.claude-plugin/plugins/aleogr-repo-github"`). The plugin needs one skill folder to load: create `skills/github_repo-describe/SKILL.md` in Task 2, and until then keep `--plugin-dir` for it out of `run.sh` if `claude` refuses an empty plugin (check by running the self-test).

- [ ] **Step 5: Run `harness-selftest-gh` and `harness-selftest`; expected PASS both.** Then run four existing scenarios as a regression of the refactor: `create-apply`, `budget-existing-equal`, `describe-existing`, and one that uses `+after+` responses (pick with `ls scenarios/*/responses | grep -m1 after`). Expected PASS.

- [ ] **Step 6: Update `tests/README.md`** (the fake `gh`, the `gh_` prefix, the `--input` rule, the fourth plugin) and commit: `Add the GitHub plugin skeleton and a fake gh to the tests`.

### Task 2: `github_repo-describe`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-repo-github/skills/github_repo-describe/SKILL.md`, scenarios `gh-describe-public`, `gh-describe-private`, `gh-describe-missing`, `gh-describe-read-refused`, `gh-describe-invalid`, `gh-describe-no-gh`

**Interfaces:**
- Arguments: `owner=<owner> name=<name>`.
- Commands, in this order, and nothing else:
  1. `gh api repos/<owner>/<name>` — exit 0: exists. Non-zero with `HTTP 404`: does not exist, stop and report. Any other non-zero: `failed`. `command not found`: `failed`, fix is to install `gh`. Output naming authentication (`gh auth login`): `failed`, fix is `gh auth login`.
  2. `gh api repos/<owner>/<name>/rulesets` — exit 0: a JSON list. Non-zero with `HTTP 403` and a message containing `Upgrade`: protection `unavailable`. Any other non-zero: `failed`.
  3. Only when the list has a ruleset named `main`: `gh api repos/<owner>/<name>/rulesets/<id>`.
- Produces, in `outputs` (later skills and 3b read these names):

```json
{
  "exists": true,
  "url": "https://github.com/<owner>/<name>",
  "visibility": "public",
  "defaultBranch": "main",
  "description": "<text>",
  "topics": ["<topic>"],
  "settings": { "mergeCommit": true, "squash": true, "rebase": false, "deleteBranchOnMerge": true, "issues": true, "wiki": false, "projects": false },
  "protection": { "state": "protected", "rulesetId": 123, "matches": true, "otherRulesets": ["<name>"] }
}
```

  `protection.state` is `protected` (a ruleset named `main` exists), `unprotected` or `unavailable`; `matches` says whether it equals `ruleset-main.json` on target, enforcement, bypass actors, the `ref_name` condition and the three rules (parameters compared only on the keys the file has; `allowed_merge_methods` as a set); `rulesetId` and `matches` are `null` unless `protected`. Missing repository: `{ "exists": false }` with every other key `null` or empty. Mapping from the API: `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, `delete_branch_on_merge`, `has_issues`, `has_wiki`, `has_projects`, `default_branch`, `visibility`, `html_url`.
- `resources`: one `{ "type": "repository", "id": "<owner>/<name>", "name": "<name>" }` when it exists, else empty.

- [ ] **Step 1: Write the six scenarios.** Fixtures: a full repository JSON for public and private; rulesets list `[]` (public, unprotected) for `gh-describe-public`; for `gh-describe-private`, `gh_api_repos_example-org_example-repo_rulesets.txt.exit1` with `{"message":"Upgrade to GitHub Team or make this repository public to enable this feature.","status":"403"}` and a line `gh: Upgrade to GitHub Team or make this repository public to enable this feature. (HTTP 403)`; for missing, the repository read is `.exit1` with `gh: Not Found (HTTP 404)`; for read-refused, `.exit1` with `gh: Server Error (HTTP 502)`; for `gh-describe-no-gh`, a `default.txt.exit1` printing `To get started with GitHub CLI, please run:  gh auth login`. Key expectations:

```
# gh-describe-public
CALLED ^gh api repos/example-org/example-repo$
CALLED ^gh api repos/example-org/example-repo/rulesets$
OUTPUT "visibility": "public"
OUTPUT "state": "unprotected"
OUTPUT "status": "unchanged"
# gh-describe-private
OUTPUT "state": "unavailable"
OUTPUT "status": "unchanged"
# gh-describe-missing
NOT_CALLED rulesets
OUTPUT "exists": false
OUTPUT "status": "unchanged"
# gh-describe-read-refused
NOT_CALLED rulesets
OUTPUT "status": "failed"
RESULT_NOT "exists": false
# gh-describe-invalid   (prompt: owner=-bad name=example-repo)
NOT_CALLED ^gh
OUTPUT "status": "failed"
# gh-describe-no-gh
OUTPUT "status": "failed"
OUTPUT gh auth login
```

- [ ] **Step 2: Run the six; expected FAIL** (unknown skill).
- [ ] **Step 3: Write `SKILL.md`** from the Interfaces block, in the structure of `gcp_environment-describe` (Arguments, Steps, Result block with the rules for each status).
- [ ] **Step 4: Run the six; expected PASS.** A failure caused by an expectation that pins wording instead of content is fixed in the expectation; any other is fixed in the skill.
- [ ] **Step 5: Commit:** `Add github_repo-describe`.

### Task 3: `github_repo-create`

**Files:**
- Create: `.../skills/github_repo-create/SKILL.md`, scenarios `gh-create-plan`, `gh-create-apply`, `gh-create-existing`, `gh-create-existing-differs`, `gh-create-public-asks`, `gh-create-public-confirmed`, `gh-create-confirm-mismatch`, `gh-create-refused`, `gh-create-read-refused`, `gh-create-invalid-topic`

**Interfaces:**
- Arguments: `owner`, `name`, `visibility` (default `private`), `confirmVisibility`, `description`, `topics` (comma-separated), `mode`.
- Validation adds: `confirmVisibility`, when given, must equal `visibility` and `visibility` must be `public`.
- Commands:
  1. `gh api repos/<owner>/<name>` (as in Task 2: 404 = missing, other failure = `failed`).
  2. Exists: change nothing. `status` `unchanged`; `outputs.differences` lists the names among `visibility`, `description`, `topics` whose value differs from the arguments given, and the answer says `github_repo-configure` corrects them.
  3. Missing, `plan`: `would-create`, no further command.
  4. Missing, `apply`, `visibility=public` without `confirmVisibility=public`: ask "Create `<owner>/<name>` as PUBLIC?" and stop; in a headless run with no answer, end with `status` `pending` and a `pending` item `confirm visibility public`.
  5. `gh repo create <owner>/<name> --private|--public --add-readme [--description "<description>"]`
  6. Per topic, one flag: `gh repo edit <owner>/<name> --add-topic <t1> --add-topic <t2>` (only when topics were given).
  7. Verify: `gh api repos/<owner>/<name>`.
- `outputs`: `{ "url", "sshUrl", "visibility", "defaultBranch", "topics", "differences": [] }`. `cost`: `{ "fixed": false, "notes": "private repositories of a free organization use the 2,000 Actions minutes a month" }` for private, `"no cost"` for public.

- [ ] **Step 1: Write the ten scenarios.** `gh-create-apply` prompt: `/aleogr-repo-github:github_repo-create owner=example-org name=example-repo description="Status pages, per tenant" topics=aleogr-example,demo mode=apply`; responses: repository read `.exit1` 404, `+after+gh_repo_create` returning the private repository JSON. Key expectations:

```
# gh-create-apply
ORDER ^gh api repos/example-org/example-repo$ >> ^gh repo create
CALLED ^gh repo create example-org/example-repo .*--private
CALLED ^gh repo create .*--add-readme
CALLED ^gh repo create .*--description "?Status pages, per tenant"?
NOT_CALLED ^gh repo create .*--public
CALLED ^gh repo edit example-org/example-repo .*--add-topic aleogr-example
CALLED ^gh repo edit .*--add-topic demo
COUNT 2 ^gh api repos/example-org/example-repo$
OUTPUT "status": "created"
# gh-create-plan
NOT_CALLED ^gh repo
OUTPUT "status": "would-create"
# gh-create-existing
NOT_CALLED ^gh repo
OUTPUT "status": "unchanged"
# gh-create-existing-differs   (exists public, asked private)
NOT_CALLED ^gh repo
OUTPUT "status": "unchanged"
OUTPUT "differences": \[[^]]*"visibility"
# gh-create-public-asks   (visibility=public mode=apply)
NOT_CALLED ^gh repo create
OUTPUT "status": "pending"
# gh-create-public-confirmed   (visibility=public confirmVisibility=public mode=apply)
CALLED ^gh repo create .*--public
OUTPUT "status": "created"
# gh-create-confirm-mismatch   (visibility=private confirmVisibility=public)
NOT_CALLED ^gh
OUTPUT "status": "failed"
# gh-create-refused   (gh repo create exits 1: "HTTP 403: You need admin access to the organization")
OUTPUT "status": "failed"
NOT_CALLED ^gh repo edit
# gh-create-read-refused   (first read exits 1 with HTTP 502)
NOT_CALLED ^gh repo create
OUTPUT "status": "failed"
# gh-create-invalid-topic   (topics=Bad_Topic)
NOT_CALLED ^gh
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.**
- [ ] **Step 3: Write `SKILL.md`.**
- [ ] **Step 4: Run them; expected PASS.**
- [ ] **Step 5: Commit:** `Add github_repo-create`.

### Task 4: `github_repo-configure`

**Files:**
- Create: `.../skills/github_repo-configure/SKILL.md`, scenarios `gh-configure-plan`, `gh-configure-apply`, `gh-configure-equal`, `gh-configure-topics`, `gh-configure-public-asks`, `gh-configure-public-confirmed`, `gh-configure-private-warns`, `gh-configure-confirm-mismatch`, `gh-configure-missing`, `gh-configure-no-arguments`

**Interfaces:**
- Arguments: `owner`, `name`, `mode`, and any of `description`, `topics` (the complete wanted list, comma-separated; `topics=` empty means none), `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects` (each `true` or `false`), `visibility`, `confirmVisibility`. An argument left out is not read as a wish and is never changed. With none of them: `failed`, "nothing to configure was given".
- Validation adds: `confirmVisibility` needs `visibility` and must equal it. At least one merge method must stay on: a call whose result would turn all three off is `failed`.
- Commands:
  1. `gh api repos/<owner>/<name>`; missing repository = `failed` ("create it first").
  2. Compare each given argument with the value read. Nothing differs: `unchanged`.
  3. `plan`: `would-update`, `outputs.changes` lists `{ "setting", "from", "to" }`; no further command.
  4. `apply`, settings other than visibility, one command with only the flags that differ: `gh repo edit <owner>/<name> [--description "<d>"] [--enable-merge-commit=<bool>] [--enable-squash-merge=<bool>] [--enable-rebase-merge=<bool>] [--delete-branch-on-merge=<bool>] [--enable-issues=<bool>] [--enable-wiki=<bool>] [--enable-projects=<bool>] [--add-topic <t>]... [--remove-topic <t>]...`
  5. `apply`, visibility differs: without a matching `confirmVisibility`, ask "Make `<owner>/<name>` PUBLIC? Its whole history becomes visible." (or "PRIVATE? Branch protection stops being enforced on the free plan.") and, with no answer, apply the other settings, leave visibility, and end `pending` with the item `confirm visibility <value>`. Confirmed: `gh repo edit <owner>/<name> --visibility <value> --accept-visibility-change-consequences`, always as its own command, after step 4.
  6. Verify: `gh api repos/<owner>/<name>`; a given setting that still differs = `failed`.
- `outputs`: `{ "changes": [...], "settings": {...as in describe}, "visibility", "description", "topics" }`.

- [ ] **Step 1: Write the ten scenarios.** The starting fixture is a repository with every setting at GitHub's default (all merge methods on, delete branch off, issues/wiki/projects on, private). `gh-configure-apply` prompt uses the `pilot` settings: `mergeCommit=true squash=true rebase=false deleteBranchOnMerge=true issues=true wiki=false projects=false mode=apply`. Key expectations:

```
# gh-configure-apply
CALLED ^gh repo edit example-org/example-repo .*--enable-rebase-merge=false
CALLED ^gh repo edit .*--delete-branch-on-merge(=true)?
CALLED ^gh repo edit .*--enable-wiki=false
CALLED ^gh repo edit .*--enable-projects=false
NOT_CALLED --enable-merge-commit
NOT_CALLED --enable-issues
NOT_CALLED --visibility
OUTPUT "status": "updated"
# gh-configure-plan
NOT_CALLED ^gh repo edit
OUTPUT "status": "would-update"
OUTPUT "setting": "rebase"
# gh-configure-equal
NOT_CALLED ^gh repo edit
OUTPUT "status": "unchanged"
# gh-configure-topics   (has: old,keep ; topics=keep,new mode=apply)
CALLED --add-topic new
CALLED --remove-topic old
NOT_CALLED topic keep
# gh-configure-public-asks   (wiki=false visibility=public mode=apply)
CALLED ^gh repo edit .*--enable-wiki=false
NOT_CALLED --visibility
OUTPUT "status": "pending"
# gh-configure-public-confirmed
CALLED ^gh repo edit example-org/example-repo --visibility public --accept-visibility-change-consequences
OUTPUT "status": "updated"
# gh-configure-private-warns   (public repo, visibility=private mode=plan)
OUTPUT "status": "would-update"
OUTPUT [Pp]rotection
# gh-configure-confirm-mismatch   (visibility=private confirmVisibility=public)
NOT_CALLED ^gh
OUTPUT "status": "failed"
# gh-configure-missing
NOT_CALLED ^gh repo edit
OUTPUT "status": "failed"
# gh-configure-no-arguments
NOT_CALLED ^gh
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.**
- [ ] **Step 3: Write `SKILL.md`.**
- [ ] **Step 4: Run them; expected PASS.**
- [ ] **Step 5: Commit:** `Add github_repo-configure`.

### Task 5: `github_branch-protect`

**Files:**
- Create: `.../skills/github_branch-protect/SKILL.md`, scenarios `gh-protect-plan`, `gh-protect-apply`, `gh-protect-equal`, `gh-protect-equal-handmade`, `gh-protect-differs-apply`, `gh-protect-private-plan`, `gh-protect-private-apply`, `gh-protect-no-admin`, `gh-protect-other-ruleset`, `gh-protect-missing`

**Interfaces:**
- Consumes: `files/ruleset-main.json` and the comparison rule of Task 2.
- Arguments: `owner`, `name`, `mode`.
- Commands:
  1. `gh api repos/<owner>/<name>` — missing = `failed`.
  2. `gh api repos/<owner>/<name>/rulesets` — refused with `HTTP 403` and `Upgrade` in the message: end `pending` in both modes, with the `pending` item `branch protection needs a paid plan or a public repository`, empty `resources`, and no write. Any other refusal: `failed`.
  3. A ruleset named `main` in the list: `gh api repos/<owner>/<name>/rulesets/<id>` and compare. Equal: `unchanged`.
  4. `plan`: `would-create` (none) or `would-update` (differs, listing what differs).
  5. `apply`, none: `gh api --method POST repos/<owner>/<name>/rulesets --input "${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json"`. Differs: `gh api --method PUT repos/<owner>/<name>/rulesets/<id> --input "${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json"`. A write refused with `HTTP 403` and `Upgrade`: `pending` as in step 2.
  6. Verify: read the ruleset again and compare; a difference = `failed`.
  - Rulesets with another name are never changed; their names go in `outputs.otherRulesets` and one sentence of the answer.
- `outputs`: `{ "rulesetId", "rules": ["deletion", "non_fast_forward", "pull_request"], "requiredApprovals": 0, "otherRulesets": [] }`. `resources`: `{ "type": "ruleset", "id": "<id>", "name": "main" }`.

- [ ] **Step 1: Write the ten scenarios.** `gh-protect-equal-handmade` uses as the ruleset detail the real shape read from `aleogr/aleogr` on 2026-11-18, with the id changed to `123` and `source` to `example-org/example-repo`: it has the extra keys `required_reviewers: []` and `require_extra_approval_for_unattributed_changes: true`, `current_user_can_bypass`, `created_at`, `_links`; it must compare as equal. `gh-protect-differs-apply`: a ruleset `main` with `required_approving_review_count: 1` and without the `deletion` rule. `gh-protect-no-admin`: rulesets read `.exit1` with `gh: Must have admin rights to Repository. (HTTP 403)`. Key expectations:

```
# gh-protect-apply
ORDER ^gh api repos/example-org/example-repo/rulesets$ >> ^gh api --method POST
CALLED ^gh api --method POST repos/example-org/example-repo/rulesets --input .*ruleset-main\.json
CALLED <<< .*"name":"main".*"~DEFAULT_BRANCH".*"required_approving_review_count":0
OUTPUT "status": "created"
# gh-protect-plan
NOT_CALLED --method
OUTPUT "status": "would-create"
# gh-protect-equal  and  gh-protect-equal-handmade
NOT_CALLED --method
OUTPUT "status": "unchanged"
# gh-protect-differs-apply
CALLED ^gh api --method PUT repos/example-org/example-repo/rulesets/123 --input
NOT_CALLED --method POST
OUTPUT "status": "updated"
# gh-protect-private-plan  and  gh-protect-private-apply
NOT_CALLED --method
OUTPUT "status": "pending"
OUTPUT paid plan or a public repository
# gh-protect-no-admin
NOT_CALLED --method
OUTPUT "status": "failed"
RESULT_NOT "status": "pending"
# gh-protect-other-ruleset   (list has only "release-tags"; mode=apply)
CALLED ^gh api --method POST
NOT_CALLED --method (PUT|DELETE)
OUTPUT release-tags
# gh-protect-missing
NOT_CALLED rulesets
OUTPUT "status": "failed"
```

- [ ] **Step 2: Run them; expected FAIL.**
- [ ] **Step 3: Write `SKILL.md`.**
- [ ] **Step 4: Run them; expected PASS.**
- [ ] **Step 5: Commit:** `Add github_branch-protect`.

### Task 6: `tools-check command=gh`

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/tools-check/SKILL.md`, `.claude-plugin/plugins/aleogr/.claude-plugin/plugin.json` (version `0.5.0`)
- Create: scenarios `tools-gh-ok`, `tools-gh-missing`, `tools-gh-not-authenticated`

**Interfaces:**
- Argument: `command=gcloud|gh`, default `gcloud`. Any other value: `failed`, no command. Without the argument the skill does exactly what it does today, and the frontmatter description says the `gh` check is opt-in.
- With `command=gh`: step 1 (where it runs) as today; then `gh --version` (command not found: `missing`, fix `https://cli.github.com`), then `gh auth status` read by exit code only (non-zero: `not-authenticated`, fix `gh auth login`). Its output names the account and is never repeated. `outputs.tools` has the one entry `{ "name": "gh", "command": "gh", "state", "fix" }`.

- [ ] **Step 1: Write the three scenarios.** For `missing`, the scenario needs the fake to behave as an absent command: add to `fake-cli` the rule that a response file named `<prefix>.exit127` prints its content and exits 127, and use `gh_--version.txt.exit127` containing `bash: gh: command not found`. Expectations:

```
# tools-gh-ok
CALLED ^gh --version
CALLED ^gh auth status
NOT_CALLED ^(auth|projects|--version)
OUTPUT "name": "gh"
OUTPUT "state": "ok"
RESULT_NOT example-user
# tools-gh-missing
NOT_CALLED ^gh auth
OUTPUT "state": "missing"
OUTPUT "status": "failed"
# tools-gh-not-authenticated
OUTPUT "state": "not-authenticated"
OUTPUT gh auth login
```

  (`tools-gh-ok`'s `gh auth status` response contains `Logged in to github.com account example-user`.)

- [ ] **Step 2: Run them; expected FAIL.**
- [ ] **Step 3: Change `SKILL.md` and bump the version.**
- [ ] **Step 4: Run the three, plus the four existing `tools-*` scenarios and `platform-plan-empty`; expected PASS.**
- [ ] **Step 5: Commit:** `Let tools-check check gh`.

### Task 7: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md`, `docs/CONTRACTS.md`, `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`
- Create: `docs/plans/2026-11-18-pilot-stage-3a-run.md`

- [ ] **Step 1: `docs/DESIGN.md`**, as decisions (not as history):
  - section 2 tree: `aleogr-repo-github` as built with its four skills and `files/ruleset-main.json`; `tests/bin` with the fake `gh`; `marketplace.json` line.
  - section 10.3: a feature the provider's plan forbids is `pending` in `plan` and in `apply`.
  - section 11.1: repository visibility is declared, default `private`; nothing becomes public without its own confirmation; on a free organization a private repository has no branch protection and `main` is held by the working rule.
  - section 12: `tools-check` checks `gh` when asked.
  - section 15.4: `pilot` is born private and then made public, and stays public.
  - section 17: stage 3 in three parts (3a plugin, 3b declaration and `project-*`, 3c Go skeleton and CI).
  - section 18: new open items — "First real run of stage 3a" (unchecked, linking the run checklist); "Confirm how GitHub answers a ruleset request on a private repository of a free organization".
- [ ] **Step 2: `docs/CONTRACTS.md`**, repo-* table and notes: `repo-configure` input gains description, topics and visibility (with confirmation); `repo-create` creates the repository with a README and its `local directory` input is marked "from stage 3c"; `branch-protect` on a plan without protection is `pending`; section 1.2 says `pending` may be a `plan` result for a feature the provider's plan forbids.
- [ ] **Step 3: `docs/cloud-shell.md`**: `gh auth login` once (web flow; the code is typed in the browser, never pasted in the conversation), `claude plugin install aleogr-repo-github@aleogr`, and the four skills in the skills table.
- [ ] **Step 4: `.claude-plugin/plugins/README.md`** "What exists": the new plugin; also correct the `aleogr-db-gcp-cloud-sql` line, which lists one skill of its five.
- [ ] **Step 5: Write the run checklist** `2026-11-18-pilot-stage-3a-run.md`, in the form of `2026-11-17-shared-platform-stage-2-run.md`: preparation (update the marketplace, install the plugin, on Windows install `gh` with `winget install GitHub.cli`, `gh auth login`, confirm the organization `aleogr-sandbox` exists and the account owns it), then the eight steps of the design's "The real run" with the exact command of each and what is expected, including for `pilot`: `owner=aleogr-sandbox name=pilot description="Reference project of aleogr: status pages per tenant" topics=aleogr-pilot` and the settings `mergeCommit=true squash=true rebase=false deleteBranchOnMerge=true issues=true wiki=false projects=false`. Step 5 is run in `plan` and then in `apply`, and says what to send back if the answer is not `pending`.
- [ ] **Step 6: Check links and leftovers:** `grep -rn "aleogr-sandbox" .claude-plugin` prints nothing; every relative link in the changed documents points to an existing file or heading.
- [ ] **Step 7: Run the whole `gh-*` and `tools-*` set once more, four at a time; expected PASS all.** Commit: `Document stage 3a and add its run checklist`.
