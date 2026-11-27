---
description: GitHub checkout setup, with the gh and git CLIs. Use to tie the current folder to a GitHub repository and send one file (by default the project declaration `.aleogr/project.json`) as the repository's first content after its README, or, in plan mode, to learn whether the repository already has that file and whether it equals the local one - and, when it differs, whether this folder has a local change, is behind the repository (it then fast-forwards the folder in apply mode) or needs attention; with head=check, also when the file is equal, whether the folder's last commit is behind the repository's head. Pushes only to a repository whose default branch has exactly one commit and lacks the file; sets this checkout's commit identity to the account's no-reply address; changes no global configuration. Plan by default.
allowed-tools: Bash(aleogr-repo-github github_checkout-setup), Bash(aleogr-repo-github github_checkout-setup *)
---

# github_checkout-setup

Ties the current folder to a GitHub repository and sends one file as the repository's first content after its README (the "birth"), with the `gh` and `git` CLIs. In `plan` mode it only reads, through the GitHub API, so it works in a folder that is not a checkout yet: it answers whether the repository has the file and whether it equals the local one. When the repository's copy differs from the local one, it also reads the folder with read-only `git` commands, to tell a local change from a folder that is behind the repository (the repository moved on, after a merge) or one that needs attention; `apply` fast-forwards a folder that is behind, and does nothing else on that path.

The file is pushed to the default branch only when that branch has exactly one commit (the README of `github_repo-create`) and does not have the file. A repository with any other history is never pushed to. The commit is signed with the account's login and GitHub's no-reply address, set in this checkout only; a real e-mail address is never used, and no global git or machine configuration is changed.

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces is written in quotes (`message="Add the project declaration"`).

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `path=<path>` | The file to send, relative to the current folder. Default `.aleogr/project.json`. |
| `message=<text>` | The commit message. Default `Add the project declaration`. |
| `head=check` | Also when the file is equal, compare the folder's last commit with the head of the repository's default branch (step 4). Absent: an equal file is `equal`, and no command is run for it. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` sends the file when the repository is at its birth, or fast-forwards a folder that is behind the repository. |

`owner` and `name` are required: a missing `owner` or `name` ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `path`, when given, is a relative path: not empty, does not start with `/`, has no `..` anywhere, has no space, and has only the characters `A-Z`, `a-z`, `0-9`, `.`, `_`, `-` and `/`.
- `message`, when given, is not empty and has no line break, no `"`, no `“`, no `”`, no `„`, no backtick, no `$` and no `\` (they could break out of the quotes of the command).
- `head`, when given, is `check`.
- `mode`, when given, is `plan` or `apply`.

## mode=plan: the command

When `mode` is `plan` or absent, do not follow the steps below. The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
aleogr-repo-github github_checkout-setup <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command aleogr-repo-github could not be run: update the plugin aleogr-repo-github, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "checkout-setup",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-repo-github, then try again" } ]
}
```

Everything below is for `mode=apply` only, except the first paragraph of "Result block", which holds in both modes.

## Steps

Show each command before running it. Run only the commands below, in this order, each step's command at most once (the read of step 3 runs again as the verification of step 16 or of step 18): no `gh auth status`, no `gh repo view`, no `gh repo clone`, no `git clone`, no `git fetch`, no `git config --global`, no `git config` without `--local`, no other `gh` or `git` command, no retry. Never print the account name, the account id or the token, and never repeat the login in the answer or the result block (the `owner` argument, as the caller gave it, is the only exception): when a command of step 11 is shown, or named in the answer, it is written with `<login>` and `<id>` in place of the values. Never repeat the output of `git remote get-url` in the answer or the result block. Read the local file with the Read tool, never a shell command.

The state of the file in the repository is one of `equal`, `not-sent`, `differs`, `behind`, `needs-attention` or `missing` (steps 1 to 5). Steps 7 to 16 are the birth (`not-sent`, `apply`); steps 17 and 18 are the update of a folder that is `behind` (`apply`).

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

1. Read the repository:

   ```
   gh api repos/<owner>/<name>
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: the repository does not exist (or this account cannot see it). This is the only answer that means "does not exist". The state is `not-sent`; run no further command (steps 3 to 5 are skipped). Go to step 2.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else): `failed`. The state is unknown: never report it as "does not exist". Say the cause in one sentence, with no raw error text. Run nothing else.
   - Exit 0: the repository exists. From the JSON take `default_branch`. Continue.

2. Read the local file at `path` with the Read tool. When it does not exist, or is not valid JSON: `failed`; say so in one sentence and run nothing else.

3. Only when the repository exists, read the repository's copy of the file from its default branch:

   ```
   gh api repos/<owner>/<name>/contents/<path> -H "Accept: application/vnd.github.raw"
   ```

   - Exit 0: the output is the repository's copy. Go to step 4.
   - Non-zero exit and the output contains `HTTP 404`: the file is absent. Go to step 5.
   - Any other non-zero exit: `failed`. Say the cause in one sentence, with no raw error text. Run nothing else.

4. The file is present: compare the two as JSON values, not byte by byte. Key order, spacing, indentation and line endings (`\r\n` or `\n`) are ignored; every key and every value must be equal, and lists keep their order. Equal, without `head=check`: the state is `equal`; run no command and go to step 6. Equal, with `head=check`: the folder's head decides (a merge can move the repository on without changing the file); see "An equal file with `head=check`" below. Different, or the repository's copy is not valid JSON: the folder tells which kind of difference it is. Run the reads of steps 4a to 4e, in `plan` and in `apply`, in this order; the first that decides the state ends them, and the run goes to step 6. They only read the folder: never `git fetch`, `git pull` or any command that changes the folder.

   4a. Is the folder a git checkout?

   ```
   git rev-parse --is-inside-work-tree
   ```

   - Exit 0 and the output is `true`: continue.
   - `git` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `git` must be installed. Run nothing else.
   - Any other answer (a non-zero exit, such as one with `not a git repository`, or an output that is not `true`): the state is `needs-attention`, with the reason `not-a-checkout`. Go to step 6.

   4b. Is the remote `origin` this repository?

   ```
   git remote get-url origin
   ```

   Run it as written, with no redirection, and read its output; never repeat that output in the answer or the result block (an address can carry a token): say only whether it matches.

   - Exit 0 and the output is `https://github.com/<owner>/<name>`, compared ignoring letter case and ignoring a trailing `.git` or `/` (the rule of step 9): continue.
   - Exit 0 and any other address, or a non-zero exit and the output contains `No such remote`: the state is `needs-attention`, with the reason `other-remote`. Go to step 6. Never add, change or remove a remote.
   - Any other non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

   4c. Is the folder on the default branch?

   ```
   git branch --show-current
   ```

   - Exit 0 and the output is exactly `<branch>` (the `default_branch` of step 1): continue.
   - Exit 0 and any other output (another branch, or nothing when no branch is checked out): the state is `needs-attention`, with the reason `other-branch`. Go to step 6.
   - A non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

   4d. Is the file changed in this folder? The skill runs in the checkout's top folder, so `<path>` here, and the paths this command prints, are relative to it:

   ```
   git status --porcelain -- <path>
   ```

   - Exit 0 and the output lists `<path>` (any status: modified, added, untracked): the state is `differs`, a local change the repository does not have. Go to step 6.
   - Exit 0 and an empty output: continue.
   - A non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

   4e. Has the repository really moved on from this folder? Read the folder's last commit, then the head of the repository's default branch:

   ```
   git rev-parse HEAD
   ```

   Exit 0 and the output is one commit hash (40 characters of `0-9` and `a-f`): it is `<sha>`. Anything else: `failed` (one sentence, no raw error text); run nothing else.

   ```
   gh api repos/<owner>/<name>/commits/<branch>
   ```

   Exit 0 and the JSON has a `sha`: it is the head of the default branch. Anything else: `failed`. Say the cause in one sentence, with no raw error text. Run nothing else.

   - `<sha>` equals the head: the folder already has the repository's last commit, yet its file differs and git sees no change in it (an ignored file, for example). The state is `needs-attention`, with the reason `untracked-difference`. Go to step 6.
   - `<sha>` differs from the head: look `<sha>` up in the repository:

     ```
     gh api repos/<owner>/<name>/commits/<sha>
     ```

     - Exit 0: the folder's last commit is in the repository and the repository has moved on since. The state is `behind`. Go to step 6.
     - Non-zero exit and the output contains `HTTP 404` or `HTTP 422`: the state is `needs-attention`, with the reason `local-commits`. Go to step 6.
     - Any other non-zero exit: `failed`. Say the cause in one sentence, with no raw error text. Run nothing else.

   An equal file with `head=check`: run the reads of steps 4a, 4b, 4c and 4e, in this order, with their commands and their rules, in `plan` and in `apply`; step 4d is not run (the file is equal, so there is no change of it to find). The first that decides the state ends them, and the run goes to step 6. Their outcomes, where they differ from the list above:

   - 4a finds that the folder is not a checkout: the state is `equal` (`plan` keeps working in a folder that is not a checkout yet); run nothing else.
   - 4b finds another remote: `needs-attention`, with the reason `other-remote`, as in 4b.
   - 4c finds another branch: `needs-attention`, with the reason `other-branch`, as in 4c.
   - 4e: `<sha>` equals the head: the state is `equal` (never `untracked-difference`: the file is equal). `<sha>` differs and its lookup exits 0: `behind`. Its lookup answers `HTTP 404` or `HTTP 422`: `needs-attention`, with the reason `local-commits`.
   - Every `failed` of those steps stays `failed`.

5. The file is absent: count the commits of the default branch, at most two:

   ```
   gh api "repos/<owner>/<name>/commits?per_page=2"
   ```

   (With the double quotes, in bash and in PowerShell.)

   - Exit 0 and the output is a JSON list with exactly one commit: the branch has only its README. The state is `not-sent` (a birth).
   - Exit 0 and a JSON list with two commits: the repository has other history. The state is `missing`.
   - Non-zero exit and the output contains `HTTP 409`, or exit 0 with an empty list: `failed`. Say in one sentence that the repository has no commit (it was not created with its README). Run nothing else.
   - Any other non-zero exit, or an output that is not a JSON list: `failed`. Say the cause in one sentence, with no raw error text. Run nothing else.

6. Decide, by the state.

   - `equal`: `status` `unchanged`, in `plan` and in `apply`. Run nothing else.
   - `differs`: `status` `pending`, in `plan` and in `apply`, with the item `declaration changed in this folder`. Run nothing else: the local change goes to the repository through a pull request.
   - `needs-attention`: `status` `pending`, in `plan` and in `apply`, with the item `this folder needs attention`. Run nothing else: the owner fixes the folder by hand.
   - `behind`, `plan`: `status` `would-update`. Show the command of step 17 that `apply` would run, without running it. Run nothing else.
   - `behind`, `apply`: go to step 17. `<branch>` is the `default_branch` of step 1.
   - `missing`: `status` `pending`, in `plan` and in `apply`, with the item `declaration is not in the repository`. Run nothing else: a repository with history is never pushed to.
   - `not-sent`, `plan`: `status` `would-create`. Show the commands of steps 7 to 15 that `apply` would run (with `<login>` and `<id>`), without running them. Run nothing else.
   - `not-sent`, `apply`, the repository does not exist (step 1 answered `HTTP 404`): `failed`. Say in one sentence that the repository must be created first, with `/aleogr-repo-github:github_repo-create`. Run nothing else.
   - `not-sent`, `apply`, the repository exists: continue with step 7 below. `<branch>` is the `default_branch` of step 1.

   From here on (`apply` at a birth), any `failed` before the push of step 15 changed nothing on GitHub; the answer says which local changes were already made (a new git checkout, the remote `origin`, this checkout's identity, the pulled README, a local commit), if any.

7. Read the account, for the commit identity only, with the command exactly as written (no `--jq`, no other flag):

   ```
   gh api user
   ```

   Exit 0 and the JSON has `login` and `id`: keep them for step 11, without printing them. Anything else: `failed` (one sentence, no raw error text); run nothing else.

8. Is the folder a git checkout?

   ```
   git rev-parse --is-inside-work-tree
   ```

   - Exit 0 and the output is `true`: it is a checkout. Go to step 9.
   - Non-zero exit and the output contains `not a git repository`: make it one, with the default branch of the repository:

     ```
     git init -b <branch>
     ```

     A non-zero exit: `failed`. Say in one sentence that `git init -b` needs git 2.28 or later. Run nothing else.
   - `git` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `git` must be installed. Run nothing else.
   - Any other answer: `failed` (one sentence, no raw error text); run nothing else.

9. Is the remote `origin` this repository?

   ```
   git remote get-url origin
   ```

   Run it as written, with no redirection, and read its output; never repeat that output in the answer or the result block (an address can carry a token): say only whether it matches.

   - Exit 0 and the output is `https://github.com/<owner>/<name>`, compared ignoring letter case and ignoring a trailing `.git` or `/`: it is. Go to step 10.
   - Exit 0 and any other address: `failed`. Say in one sentence that this folder's `origin` is not this repository and that nothing was changed. Run nothing else: never change or remove an existing remote.
   - Non-zero exit and the output contains `No such remote`: add it:

     ```
     git remote add origin https://github.com/<owner>/<name>.git
     ```

     A non-zero exit: `failed`; run nothing else.
   - Any other non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

10. Is the folder on the default branch?

    ```
    git branch --show-current
    ```

    Exit 0 and the output is exactly `<branch>` (a fresh `git init -b <branch>` prints it): go to step 11. Anything else: `failed`. Say in one sentence which branch the folder is on (or that it is on none) and that it must be on `<branch>`. Run nothing else.

11. Set this checkout's commit identity, always, whatever the machine's global identity is (never read it, never use it, never change it): the account's login as the name and GitHub's no-reply address as the e-mail. Run the two commands, each alone:

    ```
    git config --local user.name <login>
    git config --local user.email <id>+<login>@users.noreply.github.com
    ```

    Shown as `git config --local user.name <login>` and `git config --local user.email <id>+<login>@users.noreply.github.com`, with the placeholders. A non-zero exit on either: `failed`; run nothing else (never commit with another identity).

12. Bring the repository's first commit (its README) into the folder. Git authenticates through `gh` for this command only: the first `-c` empties the credential helpers of the machine's configuration, the second uses `gh`; nothing is written to any git configuration. The same single-quoted form is used in bash and in PowerShell:

    ```
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull origin <branch>
    ```

    A non-zero exit: `failed` (one sentence, no raw error text); run nothing else. The answer lists what was changed locally; when the folder was already a checkout before this run (step 8 printed `true`), it also says that an interrupted merge may be left in this folder.

13. Only this run's commit may be pushed. Count the local commits that are not in the repository:

    ```
    git rev-list --count origin/<branch>..HEAD
    ```

    - Exit 0 and the output is `0`: go to step 14.
    - Exit 0 and the output is `1`: see whether it is the commit an earlier, interrupted run left:

      ```
      git diff --name-only origin/<branch> HEAD
      ```

      Exit 0 and the output is exactly one line, `<path>`: see who authored it:

      ```
      git log -1 --format=%ae HEAD
      ```

      Exit 0 and the output is exactly `<id>+<login>@users.noreply.github.com` (the values of step 7): it is; skip step 14 and go to step 15. The address is read only to compare it and is never repeated in the answer or the result block. Anything else, from either command: `failed`, as below.
    - Anything else (another number, a non-zero exit): `failed`. Say in one sentence that this folder has local commits that are not in the repository, and that nothing was pushed. Run nothing else.

14. Commit the file, and only the file (anything else staged stays uncommitted):

    ```
    git add -- <path>
    git commit -m "<message>" -- <path>
    ```

    A non-zero exit on either: `failed` (one sentence, no raw error text); run nothing else.

15. Push to the default branch:

    ```
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin <branch>
    ```

    - Exit 0: the file is in the repository; the status is `created` whatever happens in step 16. Go to step 16.
    - Non-zero exit and the output contains `GH013`, `GH006`, `protected branch` (in any letter case) or `rule violations`: the repository's rules refused it. This is not a failure of the tooling: `status` `pending`, with the item `declaration is not in the repository`. Nothing was changed on GitHub; the local commit is kept (do not undo it). Run nothing else.
    - Any other non-zero exit: `failed`. Nothing was changed on GitHub; the local commit is kept. Say the cause in one sentence, with no raw error text. Run nothing else.

16. Verify, once: run the read of step 3 again and compare by the rule of step 4 (the comparison only: steps 4a to 4e do not run). The status stays `created`. Exit 0 and `equal`: nothing is left. The read fails, or the copy is not equal: say so in one sentence and add the item `verify`.

17. The folder is `behind`: bring it up to date, by a fast-forward only. This is the only command of this path that changes anything: nothing is committed, pushed, configured or initialised. Git authenticates through `gh` for this command only, as in step 12, in the same single-quoted form in bash and in PowerShell:

    ```
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin <branch>
    ```

    - Exit 0: the folder is up to date; the status is `updated` whatever happens in step 18. Go to step 18.
    - Non-zero exit and the output contains `would be overwritten`, `Not possible to fast-forward`, `diverging` or `CONFLICT`: `failed`. Say in one sentence, in your own words, that this folder cannot be brought up to date by a fast-forward, and that nothing was changed on GitHub; the words of git's output (these included) are never repeated or quoted. Run nothing else.
    - Any other non-zero exit: `failed`. Say the cause in one sentence, with no raw error text, and that nothing was changed on GitHub. Run nothing else.

18. Verify, once: run the read of step 3 again and compare it with the local file, read again with the Read tool, by the rule of step 4 (the comparison only: steps 4a to 4e do not run again). The status stays `updated`. Exit 0 and `equal`: nothing is left. The read fails, or the copy is not equal: say so in one sentence and add the item `verify`.

Then answer in a few lines: the state of the file in the repository, what was done (or would be done), the local changes made in this folder (including the fast-forward of step 17), anything left in `pending`, and the result block. The answer never contains the account's login, id or no-reply address (except the `owner` argument as given), nor the output of `git remote get-url`.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "checkout-setup",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "repository", "id": "<owner>/<name>", "name": "<name>" }
  ],
  "outputs": {
    "state": "equal",
    "defaultBranch": "main",
    "path": ".aleogr/project.json",
    "pushed": true,
    "updated": false,
    "reason": null
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-create`: `plan`, state `not-sent` (the repository exists at its birth, or does not exist yet).
  - `would-update`: `plan`, state `behind`.
  - `created`: `apply`, the push of step 15 succeeded in this run, whatever happened after it.
  - `updated`: `apply`, state `behind`, the fast-forward of step 17 succeeded in this run, whatever happened after it.
  - `unchanged`: state `equal` (`plan` or `apply`); nothing was done.
  - `pending`: nothing was changed on GitHub and the rest is the owner's to do: state `differs`, `needs-attention` or `missing` (`plan` or `apply`), or the push refused by the repository's rules (`apply`).
  - `failed`: an argument missing or broke a rule, `gh` or `git` missing, `gh` not logged in, the repository read refused, `apply` on a repository that does not exist, the local file missing or not valid JSON, a read of steps 3 or 5 refused, a folder read of steps 4b to 4e refused, the fast-forward of step 17 refused, a repository with no commit, `gh api user` refused, `git init -b` refused (git older than 2.28), the folder's `origin` pointing to another address, the folder on another branch, local commits that are not in the repository (including a single commit with `<path>` whose author is not the account's no-reply address), or a `git` command of steps 8 to 15 refused (the push for any reason other than the repository's rules). Nothing was changed on GitHub.
- `pending` items are `{ "item": "<what>", "reason": "manual", "how": "<text>" }`:
  - State `differs`: exactly one item `{ "item": "declaration changed in this folder", "reason": "manual", "how": "propose the change with a pull request" }`.
  - State `needs-attention`: exactly one item `{ "item": "this folder needs attention", "reason": "manual", "how": "<how>" }`, where `<how>` is, by the reason: `not-a-checkout`, `this folder is not a checkout of the repository`; `other-remote`, `this folder's origin is another repository`; `other-branch`, `git switch <branch>`; `untracked-difference`, `the file in this folder differs from the repository's but git sees no change in it; check that the file is not ignored`; `local-commits`, `this folder has commits that are not in the repository`.
  - State `missing`, or the push refused by the repository's rules: exactly one item `{ "item": "declaration is not in the repository", "reason": "manual", "how": "open a pull request that adds <path>" }`.
  - `created` or `updated` with a verification (step 16 or 18) that failed or differs: one item `{ "item": "verify", "reason": "manual", "how": "/aleogr-repo-github:github_checkout-setup owner=<owner> name=<name> mode=plan" }` (plus `path=<path>` when it is not the default, and `head=check` when it was given). `created` or `updated` with a non-empty `pending` is allowed.
  - Every other ending: `[]`.
- `outputs` has the same six keys in every ending:
  - `state`: `equal`, `not-sent`, `differs`, `behind`, `needs-attention` or `missing`, as found by steps 1 to 5. After a push (`created`) or a fast-forward (`updated`), it is the verification of step 16 or 18: `equal`, `differs` when the copy is not equal, and `null` when the read failed. `null` when the run failed before the state was known (an argument, `gh`, `git` missing, the repository read, the reads of steps 3, 4b to 4e and 5), and `null` whenever the local file is missing or not valid JSON, whatever step 1 found. On a `failed` ending after step 6 (`apply`), it is the state found, `not-sent` or `behind`.
  - `defaultBranch`: the `default_branch` of step 1; `null` when the repository does not exist or step 1 did not succeed.
  - `path`: the file, `.aleogr/project.json` when not given (as given, even when it broke a rule).
  - `pushed`: `true` only when the push of step 15 exited 0 in this run; `false` otherwise.
  - `updated`: `true` only when the fast-forward of step 17 exited 0 in this run; `false` otherwise.
  - `reason`: for state `needs-attention`, `not-a-checkout`, `other-remote`, `other-branch`, `untracked-difference` or `local-commits` (steps 4a to 4e; with an equal file and `head=check`, only `other-remote`, `other-branch` or `local-commits`); `null` in every other ending.
- `resources` is `[{ "type": "repository", "id": "<owner>/<name>", "name": "<name>" }]` when step 1 proved the repository exists, `[]` otherwise.
- The result block never contains the account's login, id or no-reply address (except the `owner` argument as given).
- `cost` is always `{ "fixed": false, "notes": "no cost" }`.
