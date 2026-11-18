# Reference project, stage 3b: checklist for the first real run

For the owner. Run this in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)). It deletes the hand-built repository `aleogr-sandbox/pilot` and has `project-apply` build it again from its declaration, `.aleogr/project.json`; then it changes the declaration through a pull request and applies the change. **Nothing here costs money.**

Source of truth: [`2026-11-18-pilot-stage-3b-design.md`](2026-11-18-pilot-stage-3b-design.md) and [`DESIGN.md`](../DESIGN.md) sections 11.4, 12 and 12.2.

How to read each step: type the text in the box exactly as it is, in the Claude Code session of the folder `~/pilot` (you may write to Claude in Portuguese, but the skill text is typed as written). Every skill ends with an `aleogr-result` block; its `status` line, and the table the `project-*` skills print (item, state, action), are what to compare with **Expected**.

When Claude Code asks for permission:

- to create or edit `.aleogr/project.json`: allow it (**Yes**);
- to run a `gh` or `git` command it shows: allow it (**Yes**);
- to read a file outside the working directory (the orchestrator reading its own `defaults.json`, or a GitHub skill reading its `ruleset-main.json`): choose **"Yes, but ask again next time"**.

The skills never wait for an answer: when one needs a confirmation, it ends `pending`, changes nothing, and shows the exact text that confirms it. You confirm by running that text. One confirmation covers the whole run: `confirm=yes`, or `confirmVisibility=public` when the plan makes the repository public.

## Before you start

- The pull request of stage 3b is **merged into `main`**.
- `gh` is still signed in from stage 3a. In the Cloud Shell terminal (outside Claude Code), `gh auth status` says an account is logged in to `github.com`. Do not paste what it prints anywhere. If it says it is not logged in, sign in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md).

### Delete `aleogr-sandbox/pilot` by hand

No skill deletes a repository; this is the one step done by hand.

1. Open <https://github.com/aleogr-sandbox/pilot>.
2. **Settings**, **General**, at the bottom of the page **Delete this repository**.
3. GitHub asks you to confirm in several steps and to type the repository's name, `aleogr-sandbox/pilot`, exactly as it shows it. It may also ask for your password or your two-factor code.
4. Check: <https://github.com/aleogr-sandbox/pilot> now shows "404".

### Do not reuse an old folder

The run uses a new, empty folder `~/pilot`. If you ever made a folder with that name, it is not reused: in the terminal, `ls ~/pilot` must say `No such file or directory`. If it lists anything, move it out of the way:

```bash
mv ~/pilot ~/pilot-old
```

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

Then `claude plugin list` shows `aleogr` at version `0.6.0` and `aleogr-repo-github` at version `0.2.0`, both enabled. Plugins are loaded when a session starts: the session of the next section is new, so nothing else is needed.

## 2. The run

Do the steps in order, in one Claude Code session. If a status or a table differs from **Expected**, stop there and send the whole answer of that skill (see section 4).

### Step 1. A new, empty work folder

In the terminal:

```bash
mkdir ~/pilot && cd ~/pilot && claude
```

Expected: Claude Code starts in `~/pilot`. If it asks whether you trust the files in this folder, answer yes. If `mkdir` says `File exists`, go back to "Do not reuse an old folder".

### Step 2. Declare the project

```
/aleogr:project-declare name=pilot owner=aleogr-sandbox visibility=public description="Reference project of aleogr: status pages per tenant"
```

Expected: `status` `created`. It shows the file it wrote, `.aleogr/project.json`, and adds that nothing is public until `project-apply` runs with `confirmVisibility=public`. Nothing else happens: no `gh` or `git` command, nothing on GitHub. The file holds:

```json
{
  "$schema": "https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json",
  "version": 1,
  "name": "pilot",
  "repo": {
    "provider": "github",
    "owner": "aleogr-sandbox",
    "name": "pilot",
    "visibility": "public",
    "description": "Reference project of aleogr: status pages per tenant",
    "topics": [],
    "settings": {
      "mergeCommit": true,
      "squash": true,
      "rebase": false,
      "deleteBranchOnMerge": true,
      "issues": true,
      "wiki": false,
      "projects": false
    }
  }
}
```

The topic `aleogr-pilot` is not in the file on purpose: it is derived from the name and added when the repository is created.

### Step 3. Plan: everything to create

```
/aleogr:project-plan
```

Expected: `status` `would-create` and this table:

| Item | State | Action |
|---|---|---|
| `repository` | `missing` | `create` |
| `settings` | `follows the creation` | `update` |
| `visibility` | `follows the creation` | `none` |
| `declaration` | `follows the creation` | `send` |
| `protection` | `follows the creation` | `create` |

Under the table: `This plan makes the repository public: project-apply runs it only with confirmVisibility=public.` It changes nothing. If `repository` says `exists`, the deletion did not happen: send the answer.

### Step 4. Apply without the confirmation

```
/aleogr:project-apply
```

Expected: `status` `pending`. It shows the same table as step 3, says the repository would be public (its whole history visible), and has one `pending` item, `confirm visibility public`, whose text is `/aleogr:project-apply confirmVisibility=public`. Nothing is created: <https://github.com/aleogr-sandbox/pilot> still shows "404". If anything was created, stop and send the answer.

### Step 5. Apply, confirmed: the repository is born

```
/aleogr:project-apply confirmVisibility=public
```

It shows the first plan (the table of step 3), then runs, in this order:

1. `github_repo-create`: expected `created` (public, with a README and the topic `aleogr-pilot`);
2. `github_repo-configure`: expected `updated` (`unchanged` is also fine);
3. `github_checkout-setup`: expected `created`. It makes `~/pilot` a git checkout of the repository, sets the commit identity of this folder only (your GitHub login and GitHub's no-reply address; your e-mail is never used), brings the README, commits `.aleogr/project.json` and pushes it to `main`;
4. `github_branch-protect`: expected `created`.

Then it plans again. Expected: `status` `created`, `pending` `[]`, the line `nothing to do`, and this last table:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `as declared` | `none` |
| `visibility` | `as declared` | `none` |
| `declaration` | `in the repository` | `none` |
| `protection` | `protected` | `none` |

**The first real `git push` from Cloud Shell happens here**, in `github_checkout-setup`: it is one of the things this run proves. If it is refused (`github_checkout-setup` ends `failed`, the run ends `created` with items in `pending`, and the last plan shows `declaration` `not sent yet` / `send` and `protection` `unprotected` / `create`), stop and send the whole answer: do not run anything again until the cause is known.

### Step 6. Everything is as declared

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the same table as the end of step 5, and the line `nothing to do`.

Then look at <https://github.com/aleogr-sandbox/pilot> in the browser:

- it opens without signing in (public), and has two files: `README.md` and `.aleogr/project.json`, in two commits, the second one `Add the project declaration`;
- **About** shows the description and the topic `aleogr-pilot`;
- **Settings**, **General**: merge commits and squash merging allowed, rebase merging not allowed, "Automatically delete head branches" on; Issues on, Wikis and Projects off;
- **Settings**, **Rules**, **Rulesets**: the ruleset `main`, active;
- open the commit `Add the project declaration` and add `.patch` to the end of its address: the `From:` line ends with `@users.noreply.github.com`. Do not paste that line anywhere; just say whether it ends that way.

### Step 7. A change goes through a pull request

Edit the declaration, adding one topic:

```
/aleogr:project-declare topics=status-page
```

Expected: `status` `updated`, the changed key `repo.topics`, and the file now has `"topics": ["status-page"]`. Nothing changes on GitHub.

Try to apply it before it is merged:

```
/aleogr:project-apply
```

Expected: `status` `pending`, nothing changed, and this table:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `not checked until the change is merged` | `none` |
| `visibility` | `not checked until the change is merged` | `none` |
| `declaration` | `differs from the repository` | `merge first` |
| `protection` | `not checked until the change is merged` | `none` |

with one `pending` item, `declaration differs from the repository`: "merge the change (a pull request), then update this folder".

Ask Claude Code, in your own words, for example:

```
abra um pull request com a mudança da declaração
```

Expected: Claude Code makes a new branch, commits `.aleogr/project.json`, pushes the branch and opens the pull request, and shows its link. Allow the `git` and `gh` commands it shows.

Merge it on GitHub: open the link, **Merge pull request** (or **Squash and merge**), then **Confirm**. The branch is deleted by GitHub.

Update the folder. In Claude Code, a line that starts with `!` runs in the terminal; type each one:

```
!git switch main
```

```
!git pull
```

Expected: the pull says `Fast-forward` and names `.aleogr/project.json`. If it says the branches have diverged, or anything else fails, send the answer.

Apply the merged change:

```
/aleogr:project-apply confirm=yes
```

Expected: the first plan shows `settings` `differs: topics` / `update` and every other action `none`; it runs only `github_repo-configure` (expected `updated`); it ends with `status` `updated`, `pending` `[]`, the line `nothing to do` and the table of step 5.

Last check:

```
/aleogr:project-plan
```

Expected: `status` `unchanged` and `nothing to do`. **About** on GitHub shows the topics `aleogr-pilot` and `status-page`.

## 3. If something goes wrong

- Nothing in this run costs money: repositories and rulesets are free, and no workflow runs.
- Every skill can be run again: it reads what exists first and does only what is missing.
- **A half-born repository** (created, but the run stopped before the declaration was sent or before the protection) is completed by running `project-apply` again. Run it with no argument first: since the repository is already public, the plan no longer makes it public, so it asks for `confirm=yes` instead of `confirmVisibility=public` (giving `confirmVisibility=public` to a plan that does not need it ends `failed` and changes nothing). Run exactly the confirming text it shows. The exception is a refused `git push` (step 5): send the answer first.
- **`merge first`** means the declaration in this folder differs from the one merged in the repository. After the birth only the merged declaration is applied: open a pull request with the change, merge it, update the folder (`!git switch main`, then `!git pull`), and run `project-apply` again.
- **`open a pull request`** means the repository has history but not this declaration, so it is never pushed to directly: ask Claude Code to open a pull request that adds `.aleogr/project.json`, merge it, update the folder, and run `project-apply` again.
- A repository created by mistake (a wrong name, for example) is deleted by hand, as in "Delete `aleogr-sandbox/pilot` by hand".
- If a skill says `gh` is not logged in, sign it in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md) and run the step again.

## 4. What to send back

- The answer of every step whose status or table differed from **Expected** (the text and the `aleogr-result` block).
- The whole answer of step 5, whatever it said: it shows the birth, and the first `git push` from Cloud Shell.
- The answer of the first `project-apply` of step 7 (`merge first`).
- Whether the `From:` line of step 6 ends with `@users.noreply.github.com` (yes or no; not the line itself).
- The full text of any error, from any step. Never paste the code of `gh auth login`, a token, or what `gh auth status` prints.

What the run shows goes into [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md), and whatever failed becomes a fix in the skills.
