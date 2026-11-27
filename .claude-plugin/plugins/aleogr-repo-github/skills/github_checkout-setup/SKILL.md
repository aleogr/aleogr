---
description: GitHub checkout setup, with the gh and git CLIs. Use to tie the current folder to a GitHub repository and send one file (by default the project declaration `.aleogr/project.json`) as the repository's first content after its README, or, in plan mode, to learn whether the repository already has that file and whether it equals the local one - and, when it differs, whether this folder has a local change, is behind the repository (it then fast-forwards the folder in apply mode) or needs attention; with head=check, also when the file is equal, whether the folder's last commit is behind the repository's head. Pushes only to a repository whose default branch has exactly one commit and lacks the file; sets this checkout's commit identity to the account's no-reply address; changes no global configuration. Plan by default.
allowed-tools: Bash(aleogr-repo-github --read-only github_checkout-setup), Bash(aleogr-repo-github --read-only github_checkout-setup *)
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
| `head=check` | Also when the file is equal, compare the folder's last commit with the head of the repository's default branch. Absent: an equal file is `equal`, and no command is run for it. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` sends the file when the repository is at its birth, or fast-forwards a folder that is behind the repository. |

`owner` and `name` are required.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-repo-github github_checkout-setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-repo-github --read-only github_checkout-setup <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`message="Add the project declaration"`) is one argument whose value is the text inside them: write it `'message=Add the project declaration'`, without the double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command aleogr-repo-github ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command aleogr-repo-github could not be run: update the plugin aleogr-repo-github, then try again.` and the block is as it is below.

The block:

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

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
