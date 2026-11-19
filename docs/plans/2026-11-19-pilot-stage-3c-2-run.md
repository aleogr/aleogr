# Reference project, stage 3c-2: checklist for the first real run

For the owner. Run this in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)), in the project folder `~/pilot` that stage 3c-1 left. It gives `aleogr-sandbox/pilot` two Go components, `status` and `admin`: `project-apply` writes their starting points and the project's CI file and proposes them in one pull request, CI runs on that pull request, you merge it, and `project-apply` updates the folder and makes the protection of `main` require the check `ci`. The last step proves, by hand on GitHub, that a pull request whose test fails cannot be merged. **Nothing here costs money**: the repository is public, and GitHub Actions on a public repository is free.

Source of truth: [`2026-11-19-pilot-stage-3c-design.md`](2026-11-19-pilot-stage-3c-design.md) (part 3c-2), [`2026-11-19-pilot-stage-3c-2.md`](2026-11-19-pilot-stage-3c-2.md) and [`DESIGN.md`](../DESIGN.md) sections 4, 11.5 and 12.

How to read each step: type the text in the box exactly as it is, in the Claude Code session of the folder `~/pilot` (you may write to Claude in Portuguese, but the skill text is typed as written). Every skill ends with an `aleogr-result` block; its `status` line, and the table the `project-*` skills print (item, state, action), are what to compare with **Expected**. Write what you saw in the table of [section 6](#6-results) as you go.

When Claude Code asks for permission:

- to edit `.aleogr/project.json`, or to write the generated files (`admin/go.mod`, `admin/main.go`, `admin/main_test.go`, the same three under `status/`, and `.github/workflows/ci.yml`): allow it (**Yes**);
- to run a `gh` or `git` command it shows: allow it (**Yes**), except the ones listed under step 7;
- to run `ls -1Ap -- admin/` or `ls -1Ap -- status/` (the Go skill looking into the component's folder; it changes nothing): allow it (**Yes**);
- to run the short command that makes the 6 random characters of the branch name (in bash, it starts with `LC_ALL=C tr -dc 'a-z0-9'`): allow it (**Yes**);
- to read a file outside the working directory (the orchestrator reading its own `defaults.json`, a GitHub skill reading `ruleset-main.json` or `ruleset-main-ci.json`, or the Go skill reading its three templates `go.mod.tmpl`, `main.go.tmpl` and `main_test.go.tmpl`): choose **"Yes, but ask again next time"**. Step 7 asks for the templates once per component.

The skills never wait for an answer: when one needs a confirmation, it ends `pending`, changes nothing, and shows the exact text that confirms it. You confirm by running that text. **You merge the pull request yourself, on GitHub, with the normal button. Never ask Claude Code to merge it**: the skills never merge.

## Before you start

- The pull request of stage 3c-2 is **merged into `main`** of `aleogr/aleogr`, and on that pull request the check `self-test-ci-go` was green. This matters for more than the plugins: the project's `ci.yml` pins the reusable workflow `ci-go.yml` to the commit at the head of `main` of `aleogr/aleogr` when it is generated (step 7), so that commit must already have it.
- `gh` is still signed in. In the Cloud Shell terminal (outside Claude Code), `gh auth status` says an account is logged in to `github.com`. Do not paste what it prints anywhere. If it says it is not logged in, sign in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md).
- **`gh` may push a workflow file.** As a precaution (not yet confirmed by a real run): GitHub may refuse a push that adds `.github/workflows/ci.yml` when the token of `gh` lacks the scope `workflow`, and step 7 pushes that file. In the same terminal, look at the line `Token scopes:` of `gh auth status` and check that `workflow` is among them, without pasting the output anywhere. If it is not, run:

  ```bash
  gh auth refresh -h github.com -s workflow
  ```

  It shows a one-time code and an address, as the login did: open the address and type the code in the browser. Then `gh auth status` lists `workflow` among the scopes.
- **The organization lets its repositories use actions and reusable workflows of other repositories.** The project's CI uses `actions/checkout`, `actions/setup-go`, `dorny/paths-filter` and the reusable workflow `ci-go.yml` of `aleogr/aleogr`, none of which is in `aleogr-sandbox`. Open <https://github.com/organizations/aleogr-sandbox/settings/actions> (the organization's **Settings**, then **Actions**, then **General**) and look at the section **Policies** (on some pages it is called **Actions permissions**):
  - expected: **Allow all actions and reusable workflows** is selected (the default for a new organization). Change nothing;
  - if **Disable actions** is selected, or an option that allows only `aleogr-sandbox`'s own actions, select **Allow all actions and reusable workflows** and **Save**;
  - if an option with a list of allowed actions is selected, either select **Allow all actions and reusable workflows**, or make sure the list allows the actions created by GitHub and has `dorny/paths-filter@*` and `aleogr/aleogr/.github/workflows/ci-go.yml@*`.

  Then open <https://github.com/aleogr-sandbox/pilot/settings/actions> (the repository's **Settings**, **Actions**, **General**): its section **Actions permissions** follows the organization's choice and must not say that actions are disabled.
- The folder `~/pilot` exists from stage 3c-1, and is on `main` with no change of its own. In the terminal (outside Claude Code):

  ```bash
  cd ~/pilot && git status
  ```

  Expected: the first line is `On branch main`, and `.aleogr/project.json` is not listed (a list under `Untracked files:` is fine, as long as that file is not in it, and nothing under `admin/`, `status/` or `.github/` is in it).

  - If the first line names another branch: run `git switch main`, then `git status` again.
  - If `.aleogr/project.json` is listed as modified, or `git status` says the folder is ahead of `origin/main`, or anything else is unclear: stop and send what it printed (it holds no secret).

## 1. Update the plugins

In the Cloud Shell terminal, outside Claude Code (type `/exit` first if a session is open), run one command at a time:

```bash
claude plugin marketplace update aleogr
```

```bash
claude plugin update aleogr@aleogr
```

```bash
claude plugin update aleogr-repo-github@aleogr
```

The Go plugin is new, so it is installed, not updated:

```bash
claude plugin install aleogr-stack-go@aleogr
```

Then `claude plugin list` shows `aleogr` at version `0.8.0`, `aleogr-repo-github` at version `0.4.0` and `aleogr-stack-go` at version `0.1.0`, all enabled. Plugins are loaded when a session starts: the session of the next section is new, so nothing else is needed.

## 2. The run

Do the steps in order, in one Claude Code session. If a status or a table differs from **Expected**, stop there and send the whole answer of that skill (see [section 5](#5-what-to-send-back)).

### Step 1. Start in the project folder

In the terminal:

```bash
cd ~/pilot && claude
```

Expected: Claude Code starts in `~/pilot`.

### Step 2. Plan: nothing to do

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the line `nothing to do`, and the table of stage 3c-1, five items (the declaration has no component yet):

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `as declared` | `none` |
| `visibility` | `as declared` | `none` |
| `declaration` | `in the repository` | `none` |
| `protection` | `protected` | `none` |

### Step 3. Declare the component `status`

```
/aleogr:project-declare component=status stack=go
```

Expected: `status` `updated`, the changed key `components.status`, and the file it shows now ends with:

```json
  "components": [
    { "name": "status", "stack": "go", "path": "status", "version": "1.27" }
  ]
}
```

The folder is the name and the Go version is the default of `defaults.json`. Everything else in the file is as before. No `gh` or `git` command runs, and nothing happens on GitHub.

### Step 4. Declare the component `admin`

```
/aleogr:project-declare component=admin stack=go
```

Expected: `status` `updated`, the changed key `components.admin`, and the components sorted by name:

```json
  "components": [
    { "name": "admin", "stack": "go", "path": "admin", "version": "1.27" },
    { "name": "status", "stack": "go", "path": "status", "version": "1.27" }
  ]
```

### Step 5. Plan: two components and CI to generate

```
/aleogr:project-plan
```

It now also invokes `github_ci-setup` (which reads `gh api repos/aleogr-sandbox/pilot/contents/.github/workflows/ci.yml`; the repository does not have the file yet, so GitHub answers "not found", which is expected) and `go_setup` once per component, in `mode=plan` (each runs `ls -1Ap -- <folder>/`; the folder does not exist yet, which is expected).

Expected: `status` `would-update` and this table, seven items:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `not checked until the change is merged` | `none` |
| `visibility` | `not checked until the change is merged` | `none` |
| `declaration` | `changed here` | `propose` |
| `components` | `to generate: admin, status` | `generate` |
| `ci` | `missing` | `generate` |
| `protection` | `not checked until the change is merged` | `none` |

Under the table: that `project-apply` writes the files in this folder and proposes them, with the declaration, in one pull request; then that three items have an action. No file is written: `admin/`, `status/` and `.github/` do not exist yet.

### Step 6. Apply without the confirmation

```
/aleogr:project-apply
```

Expected: `status` `pending`, nothing changed, the table of step 5, and one `pending` item, `confirm`, whose text is `/aleogr:project-apply confirm=yes`. The answer names the files the confirmed run would write: `go.mod`, `main.go` and `main_test.go` under `admin/` and `status/`, and `.github/workflows/ci.yml`. No file is written and no pull request exists: <https://github.com/aleogr-sandbox/pilot/pulls> shows no open pull request. If a file was written or a pull request opened, stop and send the answer.

### Step 7. Apply, confirmed: generate and propose

```
/aleogr:project-apply confirm=yes
```

It shows the first plan (the table of step 5), then:

1. `aleogr-stack-go:go_setup component=admin path=admin version=1.27 module=github.com/aleogr-sandbox/pilot/admin mode=apply`: reads its three templates and writes `admin/main_test.go`, `admin/main.go` and `admin/go.mod`. Expected `created`.
2. The same for `status`, with `module=github.com/aleogr-sandbox/pilot/status`. Expected `created`.
3. `aleogr-repo-github:github_ci-setup owner=aleogr-sandbox name=pilot components=admin:admin:go:1.27,status:status:go:1.27 workflows=aleogr/aleogr mode=apply`: reads the repository's copy of `ci.yml` (not found), reads the head of `main` of `aleogr/aleogr` (`gh api repos/aleogr/aleogr/commits/main`) and writes `.github/workflows/ci.yml`, whose first line is `# aleogr-ci 1 admin:admin:go:1.27,status:status:go:1.27`. Expected `created`.
4. `aleogr-repo-github:github_pull-request-open` with the eight files (`.aleogr/project.json`, `.github/workflows/ci.yml` and the three files of each component) and the title `Add the components admin, status and CI`. As in stage 3c-1 it sets this folder's commit identity, brings `main` up to date, creates a branch `aleogr/change-` followed by 6 random characters, commits only those files, pushes that branch, opens the pull request (`gh pr create`) and returns the folder to `main`.

Expected: `status` `updated`, a pull request address `https://github.com/aleogr-sandbox/pilot/pull/<N>`, and one `pending` item, `pull request #<N> is open`, whose text is `merge https://github.com/aleogr-sandbox/pilot/pull/<N>, then run /aleogr:project-apply confirm=yes`. There is no last plan in this run, and no `nothing to do`.

If Claude Code proposes `gh auth setup-git`, a `git config` without `--local`, a commit on `main`, a push to `main`, `gh pr merge`, `go` (any Go command), `mkdir`, or an address with a token in it: answer **No** and send the answer.

Check that the folder is back on `main`, in Claude Code (a line that starts with `!` runs in the terminal):

```
!git branch --show-current
```

Expected: `main`. The folders `admin/` and `status/` and the file `.github/workflows/ci.yml` are no longer in the folder (`!ls -a` does not list `admin` or `status`), and `.aleogr/project.json` has no `components` again: that is the merged state; the new files are in the pull request.

### Step 8. Look at the proposal

```
/aleogr:project-plan
```

Expected: `status` `pending` and this table, with the number of step 7. It has five items, not seven: the folder is back on `main`, whose declaration has no components yet, so the plan has no `components` or `ci` row.

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `not checked until the change is merged` | `none` |
| `visibility` | `not checked until the change is merged` | `none` |
| `declaration` | `proposed in pull request #<N>` | `merge it` |
| `protection` | `not checked until the change is merged` | `none` |

Under the table: `merge https://github.com/aleogr-sandbox/pilot/pull/<N>, then run /aleogr:project-apply confirm=yes`, and that `project-apply` stops until that is done.

Then open the pull request's address in the browser:

- **Files changed** shows eight files: `.aleogr/project.json` (the `components` list added), `.github/workflows/ci.yml`, and `go.mod`, `main.go` and `main_test.go` under both `admin/` and `status/`;
- **Commits** shows one commit, `Add the components admin, status and CI`. Open it and add `.patch` to the end of its address: the `From:` line has `@users.noreply.github.com` just before its closing `>`. Do not paste that line anywhere; just say whether it has it there (yes or no).

### Step 9. CI runs on the pull request

On the pull request's page, open the tab **Checks** (or look at the box above the merge button on **Conversation**). Within a few minutes the workflow `ci` shows four jobs, all green:

- `changes`;
- `admin / go` and `status / go` (each component's job, with the job `go` of `ci-go.yml` inside it; GitHub may show them as `admin` and `status`);
- `ci`.

Both components run, because the pull request adds `ci.yml` itself. Open `status / go`: its steps `Format`, `Vet`, `Test` and `Build` are green.

- **The workflow did not start** (after five minutes the pull request shows no check, and the repository's **Actions** tab shows no run): see "CI does not start" in [section 4](#4-if-something-goes-wrong). Do not merge.
- **A job is red**: do not merge. Open the red job, find the first red step, and send the job's name, the step's name and the lines of the log under it (the logs of a public repository are public and hold no secret).

At this point the protection does not require `ci` yet, so GitHub would let you merge even with a red check: merge only when all four are green.

### Step 10. Merge on GitHub

On the pull request's page: **Merge pull request** (or **Squash and merge**), then **Confirm merge**. GitHub deletes the branch on GitHub by itself. Do this on GitHub only; never ask Claude Code to merge.

The merge is a push to `main`, so the workflow `ci` runs once more: the repository's **Actions** tab shows a run of `ci` for `main`, with the same four jobs green. If its `changes` job is red, send its log.

### Step 11. Apply after the merge: CI becomes required

```
/aleogr:project-apply confirm=yes
```

Expected, in this order:

1. The first plan, five items (this folder's declaration still has no components: the merge is not in the folder yet):

   | Item | State | Action |
   |---|---|---|
   | `repository` | `exists` | `none` |
   | `settings` | `not checked until the change is merged` | `none` |
   | `visibility` | `not checked until the change is merged` | `none` |
   | `declaration` | `this folder is behind` | `update` |
   | `protection` | `not checked until the change is merged` | `none` |

2. `github_checkout-setup` updates the folder (`git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin main`): expected `updated`. The folder now has `admin/`, `status/` and `.github/workflows/ci.yml` from `main`.
3. A new plan, from the merged declaration: `settings`, `visibility`, `components` and `ci` `as declared` / `none`, `declaration` `in the repository` / `none`, and `protection` `differs` / `update`: `ci.yml` is on `main` now, so the protection is expected to require the check `ci`, and the ruleset does not yet. It exposes nothing, so the run goes on under the same `confirm=yes`.
4. `aleogr-repo-github:github_branch-protect owner=aleogr-sandbox name=pilot checks=ci mode=apply`: it sends `ruleset-main-ci.json` (`gh api --method PUT repos/aleogr-sandbox/pilot/rulesets/<id> --input …/ruleset-main-ci.json`) and reads the ruleset back. Expected `updated`, with `requiredChecks` `["ci"]`.
5. The last plan: the table of step 12 and the line `nothing to do`.

The run ends with `status` `updated` and `pending` `[]`.

### Step 12. Everything is as declared

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the line `nothing to do`, and:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `as declared` | `none` |
| `visibility` | `as declared` | `none` |
| `declaration` | `in the repository` | `none` |
| `components` | `as declared` | `none` |
| `ci` | `as declared` | `none` |
| `protection` | `protected, requires ci` | `none` |

Then look at <https://github.com/aleogr-sandbox/pilot/rules> (the repository's **Settings**, **Rules**, **Rulesets**) and open `main`: besides the rules of stage 3a, it has **Require status checks to pass** with the check `ci`.

### Step 13. Last proof: a broken test cannot be merged

This step is done by hand on GitHub, not in Claude Code, and changes nothing in `~/pilot`.

1. Open <https://github.com/aleogr-sandbox/pilot/blob/main/status/main_test.go> and click the pencil (**Edit this file**).
2. In `TestHealthz`, change `"ok\n"` to `"broken\n"`.
3. **Commit changes…**: choose **Create a new branch for this commit and start a pull request** (GitHub may offer only this, because `main` is protected), keep the branch name it suggests, then **Propose changes** and **Create pull request**.

Expected, within a few minutes, on that pull request:

- `changes` green, `status / go` red at its step `Test` (the log says `body = "ok\n", want "broken\n"`), `admin / go` skipped (the pull request does not touch `admin/`), and `ci` red;
- the merge box says that merging is blocked because the required check `ci` failed, and **Merge pull request** cannot be clicked. If GitHub offers to merge anyway (bypassing the rules), do not use it: send what it says.

Then close it: **Close pull request** at the bottom of its page, then **Delete branch** in the box that appears. Nothing else is needed: `/aleogr:project-plan` still says `nothing to do` (that pull request was not one of the tooling).

## 3. What the new states mean

The plan has two more rows, after `declaration`, only while the declaration in this folder (`.aleogr/project.json`) has components: seven rows then, five otherwise. After the proposing run of step 7 the folder is back on `main`, whose declaration has no components until the merge reaches the folder, so steps 8 and 11 (its first plan) show five rows.

- **`components`**: `as declared` / `none` when every component's folder has a `go.mod`; `to generate: <names>` / `generate` when some have none (`project-apply confirm=yes` writes their starting point and proposes it); `needs attention: <names>` / `fix the folder` when a folder has Go files but no `go.mod` (code started by hand): the tooling never writes over it, and the line under the table says to add a `go.mod` or empty the folder.
- **`ci`**: `as declared` / `none` when the first line of `.github/workflows/ci.yml` in this folder matches the components; `missing` or `differs` / `generate` otherwise (`project-apply confirm=yes` writes it again and proposes it).
- When the folder's declaration has components and the declaration is `proposed in pull request #N`, `this folder is behind` or `this folder needs attention`, both rows say `not checked until the change is merged`.
- **`protection`** says `protected, requires ci` once `ci.yml` is on `main` and the ruleset requires the check `ci`. Before `ci.yml` is on `main`, the ruleset must not require it (no workflow would report the check, and every pull request would be blocked), so the check is added only by the run after the merge.

The `declaration` row means what it meant in stage 3c-1 ([`2026-11-19-pilot-stage-3c-1-run.md`](2026-11-19-pilot-stage-3c-1-run.md), section 3).

## 4. If something goes wrong

- Nothing in this run costs money: repositories, pull requests, rulesets and GitHub Actions on a public repository are free.
- **A run prints a plan and stops without going on** (the table of `project-plan`, sometimes with its own `aleogr-result` block, and nothing after it): run the same command again. The plan reads what exists, so the run goes on from where things are.
- **CI does not start on the pull request** (step 9): check the organization's and the repository's Actions settings as in "Before you start", fix them if needed, then on the pull request's page click **Close pull request** and then **Reopen pull request**: reopening runs the workflow again. If it still does not start, send what the repository's **Actions** tab shows (a run with an error message, or nothing).
- **A job is red on the pull request of step 7**: do not merge, and send the job, the step and its log lines (step 9). The pull request can stay open; the fix comes from a change to the tooling.
- **GitHub refuses the ruleset body** (step 11: `github_branch-protect` ends `failed` after the `PUT`): the folder is already updated and the ruleset is unchanged, so `main` is still protected, without the check. Do not edit the ruleset by hand; send the whole answer of step 11.
- **The merge of step 13 is not blocked**, or a pull request stays blocked although `ci` is green, with the check `ci` shown as **Expected — Waiting for status to be reported**: GitHub reports the check under another name than the ruleset requires. Send the list of checks exactly as the pull request shows it.
- **Step 7 says `needs attention: admin` (or `status`)**: that folder already has Go files but no `go.mod`. Nothing was written or proposed. Send the answer; do not delete the folder alone.
- **Step 7 stops before the pull request** (at `github_ci-setup`, which could not read the head of `main` of `aleogr/aleogr`, for example): nothing reached GitHub. The starting points already written stay in the folder, and the run ends `updated` with an item saying that the next `/aleogr:project-apply confirm=yes` proposes them. Send the whole answer before running it.
- **A second `project-apply` while the pull request is open** changes nothing: it ends `pending`, with `proposed in pull request #N` / `merge it`. Merge the pull request (step 10), then run `/aleogr:project-apply confirm=yes`. If it still says `merge it` right after the merge, wait a few seconds and run it again.
- **Step 11 says `nothing to do` right after the merge**, or does not update the folder: GitHub has not shown the merge yet. Wait a few seconds and run `/aleogr:project-apply confirm=yes` again.
- **`this folder needs attention`**: see section 3 of the stage 3c-1 checklist.
- **The push of step 7 is refused**: if `gh auth status` does not list `workflow` among the token scopes (do not paste what it prints), run `gh auth refresh -h github.com -s workflow` as in "Before you start". The run ends with a `pending` item that says the generated files and the changed declaration are in a local branch `aleogr/change-…`, which it names, not in the folder: the folder is back on `main`, without `admin/`, `status/`, `.github/workflows/ci.yml` and without the `components`. Do what its `how` says (fix the cause, then declare the two components again as in steps 3 and 4 and run `/aleogr:project-apply confirm=yes`), and send the whole answer of step 7 before going on.
- If a skill says `gh` is not logged in, sign it in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md) and run the step again.

## 5. What to send back

- The table of [section 6](#6-results), filled in.
- The answer of every step whose status or table differed from **Expected** (the text and the `aleogr-result` block).
- The whole answer of step 7, whatever it said: it shows the first generated files and the pull request that carries them.
- The whole answer of step 11, whatever it said: it shows the folder updated and the protection made to require `ci`.
- The list of checks of step 9 and of step 13, as the pull requests show them (names and green, red or skipped).
- Whether the `From:` line of step 8 has `@users.noreply.github.com` just before its closing `>` (yes or no; not the line itself).
- The full text of any error, from any step. Never paste the code of `gh auth login`, a token, or what `gh auth status` prints.

What the run shows goes into [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md), and whatever failed becomes a fix in the skills.

## 6. Results

First real run: 2026-11-19, in Cloud Shell, by the owner. Every step answered as expected on the first attempt.

| Step | What you should see | Result |
|---|---|---|
| Before you start | `self-test-ci-go` green on the stage's pull request; Actions allowed in `aleogr-sandbox`; `~/pilot` on `main`, clean | as expected; the token of `gh` had the scope `workflow`; **Allow all actions and reusable workflows** was selected |
| 1. Update the plugins | `aleogr` 0.8.0, `aleogr-repo-github` 0.4.0, `aleogr-stack-go` 0.1.0 | as expected |
| 2. Plan | `unchanged`, `nothing to do`, five items | as expected |
| 3. Declare `status` | `updated`, `components.status` | as expected |
| 4. Declare `admin` | `updated`, `components.admin`, sorted | as expected (a plan run before it showed `to generate: status` alone, which was right for the file at that moment) |
| 5. Plan | `would-update`; `to generate: admin, status`; `ci` `missing` | as expected; `checks` `none` |
| 6. Apply, no confirmation | `pending`, item `confirm`, nothing written | as expected; the answer named the seven files |
| 7. Apply, confirmed | two `go_setup` `created`, `github_ci-setup` `created`, one pull request, `updated`, folder on `main` | as expected; pull request #3, branch `aleogr/change-ad5x6p`, about 2 minutes 30 seconds |
| 8. Look at the proposal | `proposed in pull request #N`; eight files; one commit with the no-reply address | not run: the plan and the `.patch` reading were skipped; the pull request page showed one commit and eight files |
| 9. CI on the pull request | `changes`, `admin / go`, `status / go`, `ci` green | as expected: four checks green in under a minute |
| 10. Merge | merged; `ci` green on `main` | as expected; `ci` green on `main` in 52 seconds, `changes` included |
| 11. Apply after the merge | folder updated, ruleset updated with `checks=ci`, `nothing to do`, `updated` | as expected, about 3 minutes; `go_setup` answered `unchanged` for both components after the update |
| 12. Plan | `unchanged`; `protected, requires ci`; the ruleset has the check `ci` | as expected; the page of the ruleset was not opened |
| 13. A broken test | `status / go` and `ci` red, merge blocked; pull request closed and branch deleted | as expected: `ci` (marked **Required**) and `status / go` red, `admin` skipped, `changes` green, **Merge pull request** disabled (pull request #4) |
