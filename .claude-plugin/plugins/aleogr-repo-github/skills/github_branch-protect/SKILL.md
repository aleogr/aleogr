---
description: GitHub branch protect, with the gh CLI. Use to protect the default branch of a GitHub repository with the repository ruleset `main` (no deletion, no force push, changes through a pull request, 0 approvals), creating or updating it from the plugin's ruleset-main.json, or with checks=ci from ruleset-main-ci.json (the same ruleset plus the required status check `ci`), then verify it. Idempotent; plan by default; reports pending when the GitHub plan does not allow rulesets on the repository. Never touches a ruleset with another name.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_branch-protect), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_branch-protect *)
---

# github_branch-protect

Protects the default branch of a GitHub repository with the `gh` CLI: the repository ruleset named `main` is made equal to `${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json`, or, with `checks=ci`, to `${CLAUDE_PLUGIN_ROOT}/files/ruleset-main-ci.json`, which also requires the status check `ci`. It creates the ruleset when there is none, updates it when it differs, and verifies it. When the GitHub plan does not allow rulesets on the repository (a private repository on the free plan), it changes nothing and reports `pending`. A ruleset with any other name is never changed or deleted.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` creates or updates the ruleset `main`. |
| `checks=<ci\|none>` | `none` (default): the ruleset file is `ruleset-main.json`. `ci`: the ruleset file is `ruleset-main-ci.json`, the same ruleset plus the rule that requires the status check `ci`. |

`owner` and `name` are required.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" github_branch-protect <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_branch-protect <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

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
  "action": "branch-protect",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-repo-github, then try again" } ]
}
```
