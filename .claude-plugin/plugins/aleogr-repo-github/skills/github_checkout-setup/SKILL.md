---
description: GitHub checkout setup, with the gh and git CLIs. Use to tie the current folder to a GitHub repository and send one file (by default the project declaration `.aleogr/project.json`) as the repository's first content after its README, or, in plan mode, to learn whether the repository already has that file and whether it equals the local one. Pushes only to a repository whose default branch has exactly one commit and lacks the file; sets this checkout's commit identity to the account's no-reply address; changes no global configuration. Plan by default.
---

# github_checkout-setup

Ties the current folder to a GitHub repository and sends one file as the repository's first content after its README (the "birth"), with the `gh` and `git` CLIs. In `plan` mode it only reads, through the GitHub API, so it works in a folder that is not a checkout yet: it answers whether the repository has the file and whether it equals the local one.

The file is pushed to the default branch only when that branch has exactly one commit (the README of `github_repo-create`) and does not have the file. A repository with any other history is never pushed to. The commit is signed with the account's login and GitHub's no-reply address, set in this checkout only; a real e-mail address is never used, and no global git or machine configuration is changed.

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces is written in quotes (`message="Add the project declaration"`).

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `path=<path>` | The file to send, relative to the current folder. Default `.aleogr/project.json`. |
| `message=<text>` | The commit message. Default `Add the project declaration`. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` sends the file when the repository is at its birth. |

`owner` and `name` are required: a missing `owner` or `name` ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `path`, when given, is a relative path: not empty, does not start with `/`, has no `..` anywhere, has no space, and has only the characters `A-Z`, `a-z`, `0-9`, `.`, `_`, `-` and `/`.
- `message`, when given, is not empty and has no line break, no `"`, no `“`, no `”`, no `„`, no backtick, no `$` and no `\` (they could break out of the quotes of the command).
- `mode`, when given, is `plan` or `apply`.

## Steps

Show each command before running it. Run only the commands below, in this order, each step's command at most once (the read of step 3 runs again as the verification of step 13): no `gh auth status`, no `gh repo view`, no `gh repo clone`, no `git clone`, no `git fetch`, no `git config --global`, no `git config` without `--local`, no other `gh` or `git` command, no retry. Never print the account name, the account id or the token: when a command of step 10 is shown, or named in the answer, it is written with `<login>` and `<id>` in place of the values. Read the local file with the Read tool, never a shell command.

The state of the file in the repository is one of `equal`, `not-sent`, `differs` or `missing` (steps 1 to 5).

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

4. The file is present: compare the two as JSON values, not byte by byte. Key order, spacing, indentation and line endings (`\r\n` or `\n`) are ignored; every key and every value must be equal, and lists keep their order. Equal: the state is `equal`. Different, or the repository's copy is not valid JSON: the state is `differs`. Run no command; go to step 6.

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
   - `differs`: `status` `pending`, in `plan` and in `apply`, with the item `declaration differs from the repository`. Run nothing else: the repository's copy is the one that holds; the local change goes to the repository through a pull request.
   - `missing`: `status` `pending`, in `plan` and in `apply`, with the item `declaration is not in the repository`. Run nothing else: a repository with history is never pushed to.
   - `not-sent`, `plan`: `status` `would-create`. Show the commands of steps 7 to 12 that `apply` would run (with `<login>` and `<id>`), without running them. Run nothing else.
   - `not-sent`, `apply`, the repository does not exist (step 1 answered `HTTP 404`): `failed`. Say in one sentence that the repository must be created first, with `/aleogr-repo-github:github_repo-create`. Run nothing else.
   - `not-sent`, `apply`, the repository exists: continue with step 7 below. `<branch>` is the `default_branch` of step 1.

   From here on (`apply` at a birth), any `failed` before the push of step 12 changed nothing on GitHub; the answer says which local changes were already made (a new git checkout, the remote `origin`, this checkout's identity, a local commit), if any.

7. Read the account, for the commit identity only, with the command exactly as written (no `--jq`, no other flag):

   ```
   gh api user
   ```

   Exit 0 and the JSON has `login` and `id`: keep them for step 10, without printing them. Anything else: `failed` (one sentence, no raw error text); run nothing else.

8. Is the folder a git checkout?

   ```
   git rev-parse --is-inside-work-tree
   ```

   - Exit 0 and the output is `true`: it is a checkout. Go to step 9.
   - Non-zero exit and the output contains `not a git repository`: make it one, with the default branch of the repository:

     ```
     git init -b <branch>
     ```

     A non-zero exit: `failed`; run nothing else.
   - `git` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `git` must be installed. Run nothing else.
   - Any other answer: `failed` (one sentence, no raw error text); run nothing else.

9. Is the remote `origin` this repository?

   ```
   git remote get-url origin
   ```

   - Exit 0 and the output is `https://github.com/<owner>/<name>.git` or `https://github.com/<owner>/<name>`: it is. Go to step 10.
   - Exit 0 and any other address: `failed`. Say in one sentence that this folder's `origin` points to another address and that nothing was changed. Run nothing else: never change or remove an existing remote.
   - Non-zero exit and the output contains `No such remote`: add it:

     ```
     git remote add origin https://github.com/<owner>/<name>.git
     ```

     A non-zero exit: `failed`; run nothing else.
   - Any other non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

10. Set this checkout's commit identity, always, whatever the machine's global identity is (never read it, never use it, never change it): the account's login as the name and GitHub's no-reply address as the e-mail. Run the two commands, each alone:

    ```
    git config --local user.name <login>
    git config --local user.email <id>+<login>@users.noreply.github.com
    ```

    Shown as `git config --local user.name <login>` and `git config --local user.email <id>+<login>@users.noreply.github.com`, with the placeholders. A non-zero exit on either: `failed`; run nothing else (never commit with another identity).

11. Bring the repository's first commit (its README) into the folder. Git authenticates through `gh` for this command only: the first `-c` empties the credential helpers of the machine's configuration, the second uses `gh`; nothing is written to any git configuration. The same single-quoted form is used in bash and in PowerShell:

    ```
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull origin <branch>
    ```

    A non-zero exit: `failed` (one sentence, no raw error text); run nothing else.

12. Commit the file, then push it to the default branch:

    ```
    git add -- <path>
    git commit -m "<message>"
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin <branch>
    ```

    - `git add` non-zero: `failed`; run nothing else.
    - `git commit` non-zero and the output contains `nothing to commit`: the file is already committed in this folder by an earlier run; go on to the push. Any other non-zero exit: `failed`; run nothing else.
    - The push exits 0: the file is in the repository; the status is `created` whatever happens in step 13. Go to step 13.
    - The push exits non-zero and the output contains `GH013`, `protected branch` or `rule violations`: the repository's rules refused it. This is not a failure of the tooling: `status` `pending`, with the item `declaration is not in the repository`. Nothing was changed on GitHub; the local commit is kept (do not undo it). Run nothing else.
    - Any other non-zero exit: `failed`. Nothing was changed on GitHub; the local commit is kept. Say the cause in one sentence, with no raw error text. Run nothing else.

13. Verify, once: run the read of step 3 again and compare by the rule of step 4. The status stays `created`. Exit 0 and `equal`: nothing is left. The read fails, or the copy is not equal: say so in one sentence and add the item `verify`.

Then answer in a few lines: the state of the file in the repository, what was done (or would be done), the local changes made in this folder, anything left in `pending`, and the result block. The answer never contains the account's login, id or no-reply address.

## Result block

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
    "pushed": true
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-create`: `plan`, state `not-sent` (the repository exists at its birth, or does not exist yet).
  - `created`: `apply`, the push of step 12 succeeded in this run, whatever happened after it.
  - `unchanged`: state `equal` (`plan` or `apply`); nothing was done.
  - `pending`: nothing was changed on GitHub and the rest is the owner's to do: state `differs` or `missing` (`plan` or `apply`), or the push refused by the repository's rules (`apply`).
  - `failed`: an argument missing or broke a rule, `gh` or `git` missing, `gh` not logged in, the repository read refused, `apply` on a repository that does not exist, the local file missing or not valid JSON, a read of steps 3 or 5 refused, a repository with no commit, `gh api user` refused, the folder's `origin` pointing to another address, or a `git` command of steps 8 to 12 refused (the push for any reason other than the repository's rules). Nothing was changed on GitHub.
- `pending` items are `{ "item": "<what>", "reason": "manual", "how": "<text>" }`:
  - State `differs`: exactly one item `{ "item": "declaration differs from the repository", "reason": "manual", "how": "merge the change (a pull request), then update this folder" }`.
  - State `missing`, or the push refused by the repository's rules: exactly one item `{ "item": "declaration is not in the repository", "reason": "manual", "how": "open a pull request that adds <path>" }`.
  - `created` with a verification that failed or differs: one item `{ "item": "verify", "reason": "manual", "how": "/aleogr-repo-github:github_checkout-setup owner=<owner> name=<name> mode=plan" }` (plus `path=<path>` when it is not the default). `created` with a non-empty `pending` is allowed.
  - Every other ending: `[]`.
- `outputs` has the same four keys in every ending:
  - `state`: `equal`, `not-sent`, `differs` or `missing`, as found by steps 1 to 5. After a push (`created`), it is the verification of step 13: `equal`, `differs` when the copy is not equal, and `null` when the read failed. `null` when the run failed before the state was known (an argument, `gh`, the repository read, the local file, the reads of steps 3 and 5). On a `failed` ending after step 6 (`apply`), it is the state found, `not-sent`.
  - `defaultBranch`: the `default_branch` of step 1; `null` when the repository does not exist or step 1 did not succeed.
  - `path`: the file, `.aleogr/project.json` when not given (as given, even when it broke a rule).
  - `pushed`: `true` only when the push of step 12 exited 0 in this run; `false` otherwise.
- `resources` is `[{ "type": "repository", "id": "<owner>/<name>", "name": "<name>" }]` when step 1 proved the repository exists, `[]` otherwise.
- The result block never contains the account's login, id or no-reply address.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`.
