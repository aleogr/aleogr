---
description: GitHub pull request open, with the gh and git CLIs. Use, in a folder that is a checkout of a GitHub repository, to propose named files by pull request - commits only those files on a new branch aleogr/change-<random>, pushes that branch, opens the pull request and returns the folder to the default branch - or, in plan mode, to learn whether a tooling pull request is already open, whether the folder is fit for a proposal and which of the named files changed. Never commits on or pushes to the default branch, never merges; one open tooling pull request per repository; sets this checkout's commit identity to the account's no-reply address; changes no global configuration. Plan by default.
---

# github_pull-request-open

Proposes a change to a GitHub repository by pull request, with the `gh` and `git` CLIs. In a folder that is a checkout of the repository, on its default branch and with no commit the repository does not have, it commits the named files (and nothing else) on a new branch `aleogr/change-<random>`, pushes that branch, opens a pull request into the default branch and returns the folder to the default branch. In `plan` mode it only reads: it answers whether a tooling pull request is already open, whether the folder is fit for a proposal and which of the named files changed.

Nothing is ever committed on, or pushed to, the default branch, and the skill never merges, closes or deletes a pull request or a branch. A repository has at most one open tooling pull request (one whose branch is in the repository itself and starts with `aleogr/change-`): while one is open, nothing is committed. After a proposal the folder shows the default branch again: the proposed files live in the pull request and in the local branch, which is kept. Changes in the folder outside the named files are neither committed nor discarded. The commit is signed with the account's login and GitHub's no-reply address, set in this checkout only; a real e-mail address is never used, and no global git or machine configuration is changed.

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces is written in quotes (`title="Change the project declaration"`).

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `paths=<path>[,<path>...]` | The files to propose, comma-separated, relative to the current folder. Files only, never a folder. Required. |
| `title=<text>` | The commit message and the pull request's title. Required with `mode=apply`. |
| `body=<text>` | The pull request's body. Default `Proposed by aleogr.` |
| `note=<text>` | One sentence appended to the pull request's body, after `<body>` and a space (`Proposed by aleogr. <note>` by default). Optional: without it the body is `<body>` alone. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` opens the pull request when the folder is ready and a named file changed. |

`owner`, `name` and `paths` are required, and `title` is required with `mode=apply`: a missing one ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `paths` is one or more paths separated by `,`, with no empty entry. Each path is a relative file path: not empty, does not start with `/` or `./`, does not end with `/`, has no `//`, has no `..` anywhere, has no space, and has only the characters `A-Z`, `a-z`, `0-9`, `.`, `_`, `-` and `/`. A path named twice counts once.
- `title`, when given, has 1 to 100 characters, and has no line break, no `"`, no `“`, no `”`, no `„`, no backtick, no `$` and no `\` (they could break out of the quotes of the command).
- `body`, when given, has 1 to 100 characters, and has no line break, no `"`, no `“`, no `”`, no `„`, no backtick, no `$` and no `\` (they could break out of the quotes of the command).
- `note`, when given, has 1 to 100 characters, and has no line break, no `"`, no `“`, no `”`, no `„`, no backtick, no `$` and no `\` (they could break out of the quotes of the command).
- `mode`, when given, is `plan` or `apply`.

In the commands below, `<paths>` is the list of `paths` separated by spaces, in the order given, `<full body>` is `<body>` alone, or, when `note` is given, `<body>`, one space and `<note>`, and `<changed>` is the list `changed` of step 7, separated by spaces, in the same order.

## Steps

Show each command before running it. Run only the commands below, in this order, each step's command at most once (the `git switch <branch>` of step 15 runs at most once in a run, wherever it is reached from): no `gh auth status`, no `gh repo view`, no `gh repo clone`, no `gh pr view`, no `gh pr merge`, no `gh pr close`, no `git clone`, no `git fetch`, no `git init`, no `git stash`, no `git reset`, no `git checkout`, no `git restore`, no `git clean`, no `git branch -d` or `-D`, no `git config --global`, no `git config` without `--local`, no other `gh` or `git` command, no retry. Never print the account name, the account id or the token, and never repeat the login in the answer or the result block (the `owner` argument, as the caller gave it, is the only exception): when a command of step 9 is shown, or named in the answer, it is written with `<login>` and `<id>` in place of the values. Never repeat the output of `git remote get-url` in the answer or the result block.

The commit message is exactly `<title>` and the pull request's body is exactly `<full body>`: nothing else is added to either (no signature, no attribution line), and the `note` goes in the body only, never in the commit message. Nothing is ever committed on, or pushed to, the default branch: the only branch committed on and pushed is the new `aleogr/change-<random>` of step 11.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

Steps 1 to 7 run in `plan` and in `apply`. Steps 3 to 6 examine the folder; the folder is one of `ready`, `not-a-checkout`, `other-remote`, `other-branch` or `local-commits`. It is `ready` when steps 3 to 6 found nothing. They stop at the first folder problem: the folder takes that value, the later steps of 3 to 7 are not run, and the run goes to step 8.

1. Read the repository:

   ```
   gh api repos/<owner>/<name>
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: the repository does not exist (or this account cannot see it). This is the only answer that means "does not exist". `failed`, in `plan` and in `apply`: say in one sentence that the repository must be created first, with `/aleogr-repo-github:github_repo-create`. Run nothing else.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else): `failed`. The state is unknown: never report it as "does not exist". Say the cause in one sentence, with no raw error text. Run nothing else.
   - Exit 0: the repository exists. From the JSON take `default_branch`; below it is `<branch>`. Continue.

2. Look for an open tooling pull request:

   ```
   gh pr list --repo <owner>/<name> --state open --json number,url,headRefName,isCrossRepository
   ```

   - Exit 0 and the output is a JSON list: the open tooling pull request is the entry whose `headRefName` starts with `aleogr/change-` and whose `isCrossRepository` is `false`; when several do, the one with the lowest `number`; when none does (an empty list, or only other branches), there is none. Pull requests on other branches are ignored, and so is a pull request from a fork (`isCrossRepository` `true`), whatever its branch is named. Keep its `number`, `url` and `headRefName`. Continue.
   - Any other answer (a non-zero exit, an output that is not a JSON list): `failed`. Say the cause in one sentence, with no raw error text. Run nothing else.

3. Is the folder a git checkout?

   ```
   git rev-parse --is-inside-work-tree
   ```

   - Exit 0 and the output is `true`: continue.
   - `git` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `git` must be installed. Run nothing else.
   - Any other answer (a non-zero exit, such as one with `not a git repository`, or an output that is not `true`): the folder is `not-a-checkout`. Go to step 8.

4. Is the remote `origin` this repository?

   ```
   git remote get-url origin
   ```

   Run it as written, with no redirection, and read its output; never repeat that output in the answer or the result block (an address can carry a token): say only whether it matches.

   - Exit 0 and the output is `https://github.com/<owner>/<name>`, compared ignoring letter case and ignoring a trailing `.git` or `/`: it is. Continue.
   - Exit 0 and any other address, or a non-zero exit and the output contains `No such remote`: the folder is `other-remote`. Go to step 8. Never add, change or remove a remote.
   - Any other non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

5. Is the folder on the default branch?

   ```
   git branch --show-current
   ```

   - Exit 0 and the output is exactly `<branch>`: continue.
   - Exit 0 and any other output (another branch, or nothing when no branch is checked out): the folder is `other-branch`. Go to step 8.
   - A non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

6. Is the folder's last commit in the repository? Read it, then look it up in the repository:

   ```
   git rev-parse HEAD
   ```

   Exit 0 and the output is one commit hash (40 characters of `0-9` and `a-f`): it is `<sha>`. Anything else: `failed` (one sentence, no raw error text); run nothing else.

   ```
   gh api repos/<owner>/<name>/commits/<sha>
   ```

   - Exit 0: the folder's last commit is in the repository. The folder is `ready`. Continue.
   - Non-zero exit and the output contains `HTTP 404` or `HTTP 422`: the folder is `local-commits`. Go to step 8.
   - Any other non-zero exit: `failed`. Say the cause in one sentence, with no raw error text. Run nothing else.

7. Which of the named files changed?

   ```
   git status --porcelain -- <paths>
   ```

   - Exit 0: each line is two status characters, a space and a path (for a rename, the path is the text after ` -> `). The paths it lists, in the order of `paths`, are `changed` (an empty output: `changed` is empty). A listed path that ends with `/` is a folder, and a listed path that is not exactly one of `paths` is a file inside a folder named in `paths`: either way `failed`. Say in one sentence that paths must be files, and run nothing else.
   - A non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

8. Decide. Take every case that applies, in this order:

   - An open tooling pull request (step 2): `status` `pending`, with the item `pull request #<n> is open`.
   - The folder is not `ready`: `status` `pending`, with the item `this folder needs attention`.

   When either applied, run nothing else, in `plan` and in `apply`. Otherwise (the folder is `ready`, no open tooling pull request):

   - `changed` is empty: `status` `unchanged`, in `plan` and in `apply`. Run nothing else.
   - `changed` is not empty, `plan`: `status` `would-create`. Show the commands of steps 9 to 15 that `apply` would run (with `<login>`, `<id>` and `<random>`), without running them. Run nothing else.
   - `changed` is not empty, `apply`: continue with step 9.

   From here on (`apply`), any `failed` before step 11 changed nothing on GitHub and committed nothing; the answer says which local changes were already made (this checkout's identity, a fast-forward of the default branch), if any.

9. Read the account, for the commit identity only, with the command exactly as written (no `--jq`, no other flag):

   ```
   gh api user
   ```

   Exit 0 and the JSON has `login` and `id`: keep them for the next commands, without printing them. Anything else: `failed` (one sentence, no raw error text); run nothing else.

   Set this checkout's commit identity, always, whatever the machine's global identity is (never read it, never use it, never change it): the account's login as the name and GitHub's no-reply address as the e-mail. Run the two commands, each alone:

   ```
   git config --local user.name <login>
   git config --local user.email <id>+<login>@users.noreply.github.com
   ```

   Shown as `git config --local user.name <login>` and `git config --local user.email <id>+<login>@users.noreply.github.com`, with the placeholders. A non-zero exit on either: `failed`; run nothing else (never commit with another identity).

10. Bring the default branch up to date, by a fast-forward only. Git authenticates through `gh` for this command only: the first `-c` empties the credential helpers of the machine's configuration, the second uses `gh`; nothing is written to any git configuration. The same single-quoted form is used in bash and in PowerShell:

    ```
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin <branch>
    ```

    - Exit 0: continue.
    - Non-zero exit and the output contains `would be overwritten`, `Not possible to fast-forward`, `diverging` or `CONFLICT`: `failed`. Say in one sentence that the change in this folder conflicts with what the repository has now, and that nothing was committed. Run nothing else.
    - Any other non-zero exit: `failed`. Say the cause in one sentence, with no raw error text, and that nothing was committed. Run nothing else.

11. Create the branch of the proposal. `<random>` is 6 random characters of `a-z0-9`, produced once, here, by a command (pick the means that works in the current shell, such as `LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 6` in bash or `-join ((48..57) + (97..122) | Get-Random -Count 6 | ForEach-Object { [char]$_ })` in PowerShell); never written by hand, never taken from an example or an earlier run. It is the only command of this skill that is not `gh` or `git`:

    ```
    git switch -c aleogr/change-<random>
    ```

    - Exit 0: the folder is on the new branch. From here on, step 15 always runs, whatever happens after. Continue.
    - A non-zero exit: `failed` (one sentence, no raw error text); nothing was committed. Run nothing else.

12. Commit the changed files, and only them (anything else in the folder stays as it is, uncommitted):

    ```
    git add -- <changed>
    git commit -m "<title>" -- <changed>
    ```

    A non-zero exit on either: the run will end `failed` (one sentence, no raw error text); nothing reached GitHub. What is left: the named files stay staged in the folder, which step 15 returns to the default branch, and the empty local branch `aleogr/change-<random>` is kept. Go to step 15, then end.

13. Push the new branch, never the default branch:

    ```
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin aleogr/change-<random>
    ```

    - Exit 0: the branch is on GitHub. Continue.
    - A non-zero exit: the run will end `failed`. Say the cause in one sentence, with no raw error text, that nothing reached GitHub, and that the commit is kept in the local branch `aleogr/change-<random>`. Go to step 15, then end.

14. Open the pull request:

    ```
    gh pr create --repo <owner>/<name> --base <branch> --head aleogr/change-<random> --title "<title>" --body "<full body>"
    ```

    - Exit 0 and the last line of the output is the address `https://github.com/<owner>/<name>/pull/<n>`: the pull request is open; its number is `<n>`. `status` `created`. Continue.
    - Any other answer: the branch is on GitHub but no pull request was opened. `status` `updated`, with the item `open the pull request`. Say the cause in one sentence, with no raw error text. Continue.

15. Return the folder to the default branch. This runs always once step 11 succeeded, whatever happened after (a failed commit, a refused push, a refused `gh pr create`):

    ```
    git switch <branch>
    ```

    A non-zero exit does not change the status: say in one sentence that the folder is still on `aleogr/change-<random>`, and add the item `return this folder to the default branch`. Never force it, never discard a change.

Then answer in a few lines: the open tooling pull request (number and address) if any, the folder's state and the changed files, what was done (or would be done), the local changes made in this folder (this checkout's identity, the fast-forward, the local branch and its commit, which is kept), anything left in `pending`, and the result block. The answer never contains the account's login, id or no-reply address (except the `owner` argument as given), nor the output of `git remote get-url`.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). Its answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "pull-request-open",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "pull-request", "id": "<owner>/<name>#7", "name": "aleogr/change-<random>" }
  ],
  "outputs": {
    "folder": "ready",
    "changed": [".aleogr/project.json"],
    "openPullRequest": null,
    "pullRequest": { "number": 7, "url": "https://github.com/<owner>/<name>/pull/7", "branch": "aleogr/change-<random>" },
    "defaultBranch": "main"
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-create`: `plan`, the folder `ready`, no open tooling pull request, and `changed` not empty.
  - `created`: `apply`, `gh pr create` of step 14 opened the pull request in this run, whatever happened after it.
  - `updated`: `apply`, the branch was pushed in this run but `gh pr create` did not open the pull request.
  - `unchanged`: the folder `ready`, no open tooling pull request, and `changed` empty (`plan` or `apply`); nothing was done.
  - `pending`: nothing was changed, in this folder or on GitHub, and the rest is the owner's to do: an open tooling pull request, or a folder that is not `ready` (`plan` or `apply`).
  - `failed`: an argument missing or broke a rule, `gh` or `git` missing, `gh` not logged in, the repository read refused, a repository that does not exist, the pull request list refused, a folder read of steps 4 to 7 refused, a named path that is a folder, `gh api user` refused, a `git config --local` refused, the fast-forward of step 10 refused (a conflict with what the repository has now, or any other cause), the branch of step 11 not created, the add or commit of step 12 refused, or the push of step 13 refused. Nothing reached GitHub.
- `pending` items are `{ "item": "<what>", "reason": "manual", "how": "<text>" }`:
  - An open tooling pull request: `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge or close <url>" }`, with the `number` and `url` of step 2.
  - A folder that is not `ready`: `{ "item": "this folder needs attention", "reason": "manual", "how": "<how>" }`, where `<how>` is, by the folder: `not-a-checkout`, `this folder is not a checkout of the repository`; `other-remote`, `this folder's origin is another repository`; `other-branch`, `git switch <branch>`; `local-commits`, `this folder has commits that are not in the repository`.
  - Both apply: both items, in that order.
  - `updated`: exactly one item `{ "item": "open the pull request", "reason": "manual", "how": "gh pr create --repo <owner>/<name> --base <branch> --head aleogr/change-<random> --title \"<title>\" --body \"<full body>\"" }`, the command of step 14 with its values.
  - The `git switch` of step 15 refused (any ending after step 11): one more item `{ "item": "return this folder to the default branch", "reason": "manual", "how": "git switch <branch>" }`.
  - Every other ending: `[]`.
- `outputs` has the same five keys in every ending:
  - `folder`: `ready`, `not-a-checkout`, `other-remote`, `other-branch` or `local-commits`, as found by steps 3 to 6; `null` when the run ended before it was known (an argument, `gh`, the repository read, the pull request list, a folder read refused).
  - `changed`: the paths of step 7 that changed, in the order of `paths`; `[]` when step 7 did not run or listed nothing, or when it found a folder.
  - `openPullRequest`: `{ "number": <n>, "url": "<url>", "branch": "<headRefName>" }` for the open tooling pull request of step 2; `null` when there is none or step 2 did not run.
  - `pullRequest`: `{ "number": <n>, "url": "<url>", "branch": "aleogr/change-<random>" }` for the pull request this run opened (`created`); `null` in every other ending.
  - `defaultBranch`: the `default_branch` of step 1; `null` when step 1 did not succeed.
- `resources` is `[{ "type": "pull-request", "id": "<owner>/<name>#<n>", "name": "aleogr/change-<random>" }]` when `created`, `[]` otherwise.
- The result block never contains the account's login, id or no-reply address (except the `owner` argument as given), nor the output of `git remote get-url`.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`.
