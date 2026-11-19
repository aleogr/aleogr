# Reference project, stage 3c-1: checklist for the first real run

For the owner. Run this in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)), in the project folder `~/pilot` that stage 3b left. It changes the declaration of `aleogr-sandbox/pilot` (one more topic, `demo`) through the new cycle: `project-apply` proposes the change as a pull request, you merge it on GitHub, and `project-apply` updates the folder and applies it. **Nothing here costs money.**

Source of truth: [`2026-11-19-pilot-stage-3c-design.md`](2026-11-19-pilot-stage-3c-design.md) (part 3c-1) and [`DESIGN.md`](../DESIGN.md) sections 11.4 and 12.

How to read each step: type the text in the box exactly as it is, in the Claude Code session of the folder `~/pilot` (you may write to Claude in Portuguese, but the skill text is typed as written). Every skill ends with an `aleogr-result` block; its `status` line, and the table the `project-*` skills print (item, state, action), are what to compare with **Expected**.

When Claude Code asks for permission:

- to edit `.aleogr/project.json`: allow it (**Yes**);
- to run a `gh` or `git` command it shows: allow it (**Yes**), except the ones listed under step 5;
- to run the short command that makes the 6 random characters of the branch name (in bash, it starts with `LC_ALL=C tr -dc 'a-z0-9'`): allow it (**Yes**);
- to read a file outside the working directory (the orchestrator reading its own `defaults.json`, or a GitHub skill reading its `ruleset-main.json`): choose **"Yes, but ask again next time"**.

The skills never wait for an answer: when one needs a confirmation, it ends `pending`, changes nothing, and shows the exact text that confirms it. You confirm by running that text. **You merge the pull request yourself, on GitHub, with the normal button. Never ask Claude Code to merge it**: the skills never merge.

## Before you start

- The pull request of stage 3c-1 is **merged into `main`** of `aleogr/aleogr`.
- `gh` is still signed in. In the Cloud Shell terminal (outside Claude Code), `gh auth status` says an account is logged in to `github.com`. Do not paste what it prints anywhere. If it says it is not logged in, sign in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md).
- The folder `~/pilot` exists from stage 3b, and is on `main` with no change of its own. In the terminal (outside Claude Code):

  ```bash
  cd ~/pilot && git status
  ```

  Expected: the first line is `On branch main`, and `.aleogr/project.json` is not listed (a list under `Untracked files:` is fine, as long as that file is not in it).

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

Then `claude plugin list` shows `aleogr` at version `0.7.0` and `aleogr-repo-github` at version `0.3.0`, both enabled. Plugins are loaded when a session starts: the session of the next section is new, so nothing else is needed.

## 2. The run

Do the steps in order, in one Claude Code session. If a status or a table differs from **Expected**, stop there and send the whole answer of that skill (see [section 5](#5-what-to-send-back)).

### Step 1. Start in the project folder

In the terminal:

```bash
cd ~/pilot && claude
```

Expected: Claude Code starts in `~/pilot`. The folder already exists: there is no `mkdir` in this run.

### Step 2. Plan: nothing to do

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the line `nothing to do`, and this table:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `as declared` | `none` |
| `visibility` | `as declared` | `none` |
| `declaration` | `in the repository` | `none` |
| `protection` | `protected` | `none` |

It now also asks GitHub whether a pull request of the tooling is open (`gh pr list`) and reads the folder with `git` commands that change nothing (`git rev-parse`, `git remote get-url origin`, `git branch --show-current`, `git status --porcelain`): allow them.

If `declaration` says `this folder needs attention` / `fix the folder`, see [section 3](#3-what-the-declaration-states-mean): the line under the table says what to fix.

### Step 3. Declare the change

```
/aleogr:project-declare topics=status-page,demo
```

Expected: `status` `updated`, the changed key `repo.topics`, and the file it shows now has:

```json
    "topics": ["demo", "status-page"],
```

Everything else in the file is as before. Since the repository is already public and this run does not change the visibility, it does **not** add the sentence "nothing is public until `project-apply` runs with `confirmVisibility=public`" (it did in stage 3b; that was fixed). Nothing else happens: no `gh` or `git` command, nothing on GitHub.

### Step 4. Apply without the confirmation

```
/aleogr:project-apply
```

Expected: `status` `pending`, nothing changed, and this table:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `not checked until the change is merged` | `none` |
| `visibility` | `not checked until the change is merged` | `none` |
| `declaration` | `changed here` | `propose` |
| `protection` | `not checked until the change is merged` | `none` |

with one `pending` item, `confirm`, whose text is `/aleogr:project-apply confirm=yes`. Nothing is committed and no pull request exists: <https://github.com/aleogr-sandbox/pilot/pulls> shows no open pull request. If one was opened, stop and send the answer.

### Step 5. Apply, confirmed: the change is proposed

```
/aleogr:project-apply confirm=yes
```

It shows the first plan (the table of step 4), then runs `github_pull-request-open`, which:

1. reads the repository, the open pull requests and the folder (the same reads as in step 2);
2. sets the commit identity of this folder only (your GitHub login and GitHub's no-reply address; the commands are shown with `<login>` and `<id>` in place of the values);
3. brings `main` up to date (`git … pull --ff-only origin main`);
4. creates a new branch `aleogr/change-` followed by 6 random characters (`git switch -c …`);
5. commits only `.aleogr/project.json`, with the message `Change the project declaration`;
6. pushes that branch (`git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin aleogr/change-…`);
7. opens the pull request (`gh pr create`);
8. returns the folder to `main` (`git switch main`).

Expected: `status` `updated`, a pull request address `https://github.com/aleogr-sandbox/pilot/pull/<N>`, and one `pending` item, `pull request #<N> is open`, whose text is `merge https://github.com/aleogr-sandbox/pilot/pull/<N>, then run /aleogr:project-apply confirm=yes`. It says the folder shows the merged state again until you merge: the folder is back on `main`, and the proposed declaration lives in the pull request (and in the local branch, which is kept). There is no last plan in this run, and no `nothing to do`.

If Claude Code proposes `gh auth setup-git`, a `git config` without `--local`, a commit on `main`, a push to `main`, `gh pr merge`, or an address with a token in it: answer **No** and send the answer.

Check that the folder is back on `main`, in Claude Code (a line that starts with `!` runs in the terminal):

```
!git branch --show-current
```

Expected: `main`. The file `.aleogr/project.json` in the folder has `"topics": ["status-page"]` again: that is the merged state; the new topic is in the pull request.

### Step 6. Look at the proposal

```
/aleogr:project-plan
```

Expected: `status` `pending` and this table, with the number of step 5:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `not checked until the change is merged` | `none` |
| `visibility` | `not checked until the change is merged` | `none` |
| `declaration` | `proposed in pull request #<N>` | `merge it` |
| `protection` | `not checked until the change is merged` | `none` |

Under the table: `merge https://github.com/aleogr-sandbox/pilot/pull/<N>, then run /aleogr:project-apply confirm=yes`, and that `project-apply` stops until that is done.

Then open the pull request's address in the browser:

- **Files changed** shows one file, `.aleogr/project.json`, with one line changed: the topics, now `["demo", "status-page"]`;
- **Commits** shows one commit, `Change the project declaration`. Open it and add `.patch` to the end of its address: the `From:` line ends with `@users.noreply.github.com`. Do not paste that line anywhere; just say whether it ends that way (yes or no).

### Step 7. Merge on GitHub

On the pull request's page: **Merge pull request** (or **Squash and merge**), then **Confirm merge**. GitHub deletes the branch on GitHub by itself ("Automatically delete head branches" is on). Do this on GitHub only; never ask Claude Code to merge.

### Step 8. Apply after the merge

```
/aleogr:project-apply confirm=yes
```

Expected, in this order:

1. The first plan:

   | Item | State | Action |
   |---|---|---|
   | `repository` | `exists` | `none` |
   | `settings` | `not checked until the change is merged` | `none` |
   | `visibility` | `not checked until the change is merged` | `none` |
   | `declaration` | `this folder is behind` | `update` |
   | `protection` | `not checked until the change is merged` | `none` |

2. `github_checkout-setup` updates the folder (`git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin main`): expected `updated`. Nothing is committed or pushed.
3. A new plan, from the merged declaration: `settings` `differs: topics` / `update`, `declaration` `in the repository` / `none`, `protection` `protected` / `none`, everything else `none`. It exposes nothing, so the run goes on under the same `confirm=yes`.
4. `github_repo-configure`: expected `updated` (it adds the topic `demo`).
5. The last plan: the table of step 2 and the line `nothing to do`.

The run ends with `status` `updated` and `pending` `[]`.

### Step 9. Everything is as declared

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the table of step 2 and the line `nothing to do`.

Then look at <https://github.com/aleogr-sandbox/pilot>: **About** shows the topics `aleogr-pilot`, `demo` and `status-page`, and `.aleogr/project.json` on `main` has `"topics": ["demo", "status-page"]`.

## 3. What the declaration states mean

The `declaration` row of the plan says where a change to the declaration is:

- **`in the repository`** / `none`: the folder and GitHub hold the same declaration.
- **`changed here`** / `propose`: the declaration in this folder has a change GitHub does not have. `project-apply confirm=yes` proposes it as a pull request.
- **`proposed in pull request #N`** / `merge it`: a pull request of the tooling (its branch starts with `aleogr/change-`) is open. A repository has at most one: until you merge or close it, `project-apply` changes nothing and only says to merge it. This is the owner's step, on GitHub.
- **`this folder is behind`** / `update`: GitHub has a newer declaration than this folder, which is what you see right after a merge. `project-apply confirm=yes` updates the folder (a fast-forward, nothing pushed) and goes on with the merged declaration.
- **`this folder needs attention`** / `fix the folder`: the tooling will not touch the folder; you fix it by hand. The line under the table says what is wrong:
  - `git switch main`: the folder is on another branch (an interrupted run, for example). Type `!git switch main` in Claude Code, then run `/aleogr:project-plan` again;
  - `this folder has commits that are not in the repository`, `this folder's origin is another repository`, `this folder is not a checkout of the repository`, or anything else: do not fix it alone; send the answer.

While the declaration is `changed here`, `proposed` or `behind`, the rows `settings`, `visibility` and `protection` say `not checked until the change is merged`: only the merged declaration is applied to GitHub.

## 4. If something goes wrong

- Nothing in this run costs money: repositories, topics, pull requests and rulesets are free, and no workflow runs.
- **A second `project-apply` while the pull request is open** changes nothing: it ends `pending`, with `proposed in pull request #N` / `merge it`. Merge the pull request (step 7), then run `/aleogr:project-apply confirm=yes`. If it still says `merge it` right after the merge, wait a few seconds and run it again.
- **To drop a proposal**, close its pull request on GitHub (**Close pull request**, at the bottom of its page). Nothing else is needed: the folder already shows the merged state, and the next plan says `in the repository`. To make the change again, declare it again (step 3) and apply it (step 5): it gets a new pull request. The branch of the closed pull request stays on GitHub and in the folder; it does no harm.
- **`this folder is behind`** at any other moment means someone merged a change into `main` since this folder was last updated: `project-apply confirm=yes` updates it.
- **`this folder needs attention`**: see [section 3](#3-what-the-declaration-states-mean).
- **Step 5 ends `failed`** (a refused push, for example): nothing reached GitHub, and the folder is back on `main`; the commit may be kept in a local branch `aleogr/change-…`. Do not run anything again: send the whole answer.
- **Step 5 ends `updated` with the item `open the pull request`**: the branch is on GitHub but no pull request was opened. Send the answer; do not open one by hand.
- **Step 5 adds the item `return this folder to the default branch`**: the folder stayed on the branch of the proposal. Type `!git switch main` in Claude Code and send the answer.
- If a skill says `gh` is not logged in, sign it in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md) and run the step again.

## 5. What to send back

- The answer of every step whose status or table differed from **Expected** (the text and the `aleogr-result` block).
- The whole answer of step 5, whatever it said: it shows the first pull request opened by the tooling, and its `git push`.
- The whole answer of step 8, whatever it said: it shows the folder updated and the merged change applied in one run.
- Whether the `From:` line of step 6 ends with `@users.noreply.github.com` (yes or no; not the line itself).
- The full text of any error, from any step. Never paste the code of `gh auth login`, a token, or what `gh auth status` prints.

What the run shows goes into [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md), and whatever failed becomes a fix in the skills.
