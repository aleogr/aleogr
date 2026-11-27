---
description: GitHub Actions variables and secrets set, with the gh CLI. Use to make a repository's Actions variables hold the given values, or (kind=secrets) to make sure its Actions secrets exist, such as the identifiers a deploy job reads through `secrets`; in plan mode, to learn which would be set. One read of the repository's variables (or secrets' names), then one set per variable that is missing or differs (per secret that is missing, or every given secret with replace=yes). Only the given names are touched: none is ever deleted. Values never appear in the result block, only names. Plan by default.
allowed-tools: Bash(aleogr-repo-github --read-only github_variables-set), Bash(aleogr-repo-github --read-only github_variables-set *)
---

# github_variables-set

Makes the repository's Actions variables (repository level, read by a workflow as `${{ vars.<NAME> }}`) hold the given values, with the `gh` CLI. It reads the repository's variables once, and sets each given variable that is missing or holds another value. A variable that was not given is never read as a wish, never changed and never deleted; this skill deletes no variable at all. A variable is not a secret, but its value is still kept out of the result block: the block names variables, never their values.

With `kind=secrets` it does the same for the repository's Actions secrets (read by a workflow as `${{ secrets.<NAME> }}`), which GitHub masks in every log and never gives to a pull request from a fork. A secret's value cannot be read back: only its name can. So a given secret whose name already exists is **already** and is left alone, unless `replace=yes`, which sets every given secret (for a value that may have changed). A secret's value never appears in the answer, the result block or a failure sentence.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `variables=<NAME>=<value>[,...]` | The wanted variables, comma-separated, each its name, `=` and its value. Required. |
| `kind=<variables\|secrets>` | `variables` (default): Actions variables; `secrets`: Actions secrets. Here "variable" means a secret too when `kind` is `secrets`. |
| `replace=<yes\|no>` | `kind=secrets` only: `yes` sets every given secret, even one that exists; `no` (default) sets only the missing ones. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` sets the variables that are missing or differ (the secrets that are missing, or all of them with `replace=yes`). |

`owner`, `name` and `variables` are required. A value is passed only in `variables`, and the command never prints it.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-repo-github github_variables-set <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-repo-github --read-only github_variables-set <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

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
  "action": "variables-set",
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
