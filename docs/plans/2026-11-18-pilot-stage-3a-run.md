# Reference project, stage 3a: checklist for the first real run

For the owner. Run this in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)) or in the Claude Code Windows app. It creates the repository `aleogr-sandbox/pilot` with the four skills of the plugin `aleogr-repo-github`: first private, then public and protected. **Nothing here costs money.**

Source of truth: [`2026-11-18-pilot-stage-3a-design.md`](2026-11-18-pilot-stage-3a-design.md) and [`DESIGN.md`](../DESIGN.md) sections 11.1 and 15.4.

How to read each step: type the text in the box exactly as it is, in a Claude Code session (you may write to Claude in Portuguese, but the skill text is typed as written). Every skill ends with an `aleogr-result` block; its `status` line is what to compare with **Expected**. When Claude Code asks to allow a `gh` command it shows, allow it. When it asks to allow a read outside the working directory (the skill reading its own `ruleset-main.json`), choose **"Yes, but ask again next time"**.

The skills never wait for an answer: when one needs a confirmation, it ends, says so, and shows the exact text that confirms it. You confirm by running that text.

## Before you start

- The pull request of stage 3a is **merged into `main`**.
- The GitHub organization `aleogr-sandbox` exists and your GitHub account is an **owner** of it: open <https://github.com/organizations/aleogr-sandbox/settings/profile> in the browser; if the settings page opens, you are an owner.
- The repository `aleogr-sandbox/pilot` does **not** exist yet: <https://github.com/aleogr-sandbox/pilot> shows "404".

## 1. Update the plugins

- **Cloud Shell:** follow "After a change is merged" in [`cloud-shell.md`](../cloud-shell.md), but skip its line `claude plugin update aleogr-repo-github@aleogr` this first time (the plugin is not installed yet), then install the new plugin:

  ```bash
  claude plugin install aleogr-repo-github@aleogr
  ```

- **Windows app:** open **Plugins** in the sidebar, then **Add → Manage marketplaces**. On the marketplace `aleogr`, open the **`···`** menu and choose **Check for updates**. Back in **Plugins**, install **GitHub (repository)** with its **`+`**, and update `aleogr` (its page must show version `0.5.0`; if the **Update** button stays disabled, delete the plugin and install it again, as recorded in [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md)).

Plugins are loaded when a session starts: **open a new session** after installing or updating.

## 2. Install and sign in `gh`, once

- **Cloud Shell:** `gh` is already installed. Sign it in as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md).
- **Windows app:** open a PowerShell window (outside Claude Code) and run:

  ```powershell
  winget install GitHub.cli
  ```

  Close that window, open a new one (so it finds `gh`) and run:

  ```powershell
  gh auth login --hostname github.com --git-protocol https --web
  ```

  Then close and open the Claude Code app, so that it finds `gh` too.

`gh auth login` shows a one-time code and opens (or shows) a GitHub address. If it asks whether to authenticate Git with your GitHub credentials, answer yes. Sign in to GitHub in the browser and **type the code there**. On GitHub's authorization page, if `aleogr-sandbox` is shown, press **Grant** next to it: a new organization restricts OAuth apps by default, and without that grant the repository reads as not found and the create is refused. Never paste that code, or anything `gh auth status` prints, in the conversation with Claude.

## 3. The run

Do the steps in order, in one Claude Code session. If a status differs from **Expected**, stop there and send the whole answer of that skill (see section 5).

### Step 1. `gh` is ready

```
/aleogr:tools-check command=gh
```

Expected: `status` `unchanged`, `gh` `ok`. If it says `missing` or `not authenticated`, redo section 2.

### Step 2. The protection of `aleogr/aleogr` is recognised (read-only)

```
/aleogr-repo-github:github_branch-protect owner=aleogr name=aleogr mode=plan
```

Expected: `status` `unchanged` (the hand-made ruleset `main` matches the plugin's file). If it says `would-update`, `would-create`, `pending` or `failed`: send the answer, and **never** run this one with `mode=apply`.

### Step 3. Create `pilot`, private

Plan:

```
/aleogr-repo-github:github_repo-create owner=aleogr-sandbox name=pilot visibility=private description="Reference project of aleogr: status pages per tenant" topics=aleogr-pilot mode=plan
```

Expected: `status` `would-create`, visibility `private`. If it says `unchanged`, the repository already exists: send the answer.

Apply:

```
/aleogr-repo-github:github_repo-create owner=aleogr-sandbox name=pilot visibility=private description="Reference project of aleogr: status pages per tenant" topics=aleogr-pilot mode=apply
```

Expected: `status` `created`, visibility `private`, default branch `main`, topics `aleogr-pilot`, and `pending` `[]`. If it says `created` with something in `pending`, or `failed`: send the answer.

### Step 4. Configure `pilot`

Plan:

```
/aleogr-repo-github:github_repo-configure owner=aleogr-sandbox name=pilot mergeCommit=true squash=true rebase=false deleteBranchOnMerge=true issues=true wiki=false projects=false mode=plan
```

Expected: `status` `would-update`, with a list of changes (probably `rebase`, `deleteBranchOnMerge`, `wiki` and `projects`; GitHub's defaults decide). `unchanged` is also fine: then skip the apply.

Apply:

```
/aleogr-repo-github:github_repo-configure owner=aleogr-sandbox name=pilot mergeCommit=true squash=true rebase=false deleteBranchOnMerge=true issues=true wiki=false projects=false mode=apply
```

Expected: `status` `updated` and `pending` `[]`. If something is in `pending`, or the status is `failed`: send the answer.

### Step 5. Protection of a private repository: `pending`

Run both, even if the first one surprises you: together they show how GitHub answers.

```
/aleogr-repo-github:github_branch-protect owner=aleogr-sandbox name=pilot mode=plan
```

```
/aleogr-repo-github:github_branch-protect owner=aleogr-sandbox name=pilot mode=apply
```

Expected, both times: `status` `pending`, with one `pending` item "branch protection needs a paid plan or a public repository". Nothing is changed. On a private repository of a free organization, `main` is held by the working rule (Claude Code opens the pull request, you merge).

If either answer is **not** `pending` (for example `would-create` in plan, or `created` or `failed` in apply), send **both** answers: the skill is corrected from them. If the `apply` answered `created`, stop here and send it; otherwise go on with step 6.

### Step 6. Make `pilot` public

First without the confirmation:

```
/aleogr-repo-github:github_repo-configure owner=aleogr-sandbox name=pilot visibility=public mode=apply
```

Expected: `status` `pending`. It asks "Make `aleogr-sandbox/pilot` PUBLIC? Its whole history becomes visible.", changes nothing, and shows the confirming text in the `pending` item `confirm visibility public`. If it says anything else, stop and send the answer.

Then confirm by running exactly:

```
/aleogr-repo-github:github_repo-configure owner=aleogr-sandbox name=pilot visibility=public confirmVisibility=public mode=apply
```

Expected: `status` `updated`, one change `visibility` from `private` to `public`, and `pending` `[]`. <https://github.com/aleogr-sandbox/pilot> now opens without signing in.

### Step 7. Protect `main` of the public repository

Plan:

```
/aleogr-repo-github:github_branch-protect owner=aleogr-sandbox name=pilot mode=plan
```

Expected: `status` `would-create`, with the rules `deletion`, `non_fast_forward` and `pull_request`, and 0 required approvals. (If the `apply` of step 5 answered `created`, this step would show `unchanged`.)

Apply:

```
/aleogr-repo-github:github_branch-protect owner=aleogr-sandbox name=pilot mode=apply
```

Expected: `status` `created` and `pending` `[]`. If it says `pending` here, the repository is still private or GitHub answers differently than expected: send the answer.

### Step 8. Everything is as wanted

Run each one. Expected for all four: `status` `unchanged`.

```
/aleogr-repo-github:github_repo-create owner=aleogr-sandbox name=pilot visibility=public description="Reference project of aleogr: status pages per tenant" topics=aleogr-pilot mode=plan
```

(Also expected: no differences.)

```
/aleogr-repo-github:github_repo-configure owner=aleogr-sandbox name=pilot description="Reference project of aleogr: status pages per tenant" topics=aleogr-pilot mergeCommit=true squash=true rebase=false deleteBranchOnMerge=true issues=true wiki=false projects=false visibility=public mode=plan
```

```
/aleogr-repo-github:github_branch-protect owner=aleogr-sandbox name=pilot mode=plan
```

```
/aleogr-repo-github:github_repo-describe owner=aleogr-sandbox name=pilot
```

(Also expected from the last one: visibility `public`, protection `protected`, and it matches the plugin's file.)

## 4. If something goes wrong

- Nothing in this run costs money: repositories and rulesets are free, and no workflow runs.
- Every skill can be run again: it reads what exists first and does only what is missing. A step that stopped in the middle is resumed by running the same text again. The exception is `github_repo-create`: after `created` with items in `pending`, run the command shown in each item (running the create again changes nothing).
- No skill deletes a repository. A repository created by mistake (a wrong name, for example) is deleted by hand: open it on GitHub, **Settings**, **General**, at the bottom **Delete this repository**.
- If a skill says `gh` is not logged in, redo section 2 and run the step again.

## 5. What to send back

- The answer of every step whose status differed from **Expected** (the text and the `aleogr-result` block).
- The two answers of step 5, whatever they said: they show how GitHub answers on a private repository of a free organization.
- The final `aleogr-result` block of `github_repo-describe` in step 8.
- The full text of any error, from any step. Never paste the code of `gh auth login`, a token, or what `gh auth status` prints.

What the run shows goes into [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md), and whatever failed becomes a fix in the skills.
