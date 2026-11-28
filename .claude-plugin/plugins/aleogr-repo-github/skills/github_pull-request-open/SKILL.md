---
description: GitHub pull request open, with the gh and git CLIs. Use, in a folder that is a checkout of a GitHub repository, to propose named files by pull request - commits only those files on a new branch aleogr/change-<random>, pushes that branch, opens the pull request and returns the folder to the default branch - or, in plan mode, to learn whether a tooling pull request is already open, whether the folder is fit for a proposal and which of the named files changed. Never commits on or pushes to the default branch, never merges; one open tooling pull request per repository; sets this checkout's commit identity to the account's no-reply address; changes no global configuration. Plan by default.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_pull-request-open), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_pull-request-open *)
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

`owner`, `name` and `paths` are required, and `title` is required with `mode=apply`.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" github_pull-request-open <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_pull-request-open <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`title="Change the project declaration"`) is one argument whose value is the text inside them: write it `'title=Change the project declaration'`, without the double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github could not be run: update the plugin aleogr-repo-github, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "pull-request-open",
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
