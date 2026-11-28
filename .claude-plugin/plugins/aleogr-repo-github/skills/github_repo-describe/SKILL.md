---
description: GitHub repository describe, with the gh CLI. Use to learn whether a GitHub repository exists and what state it is in (visibility, default branch, description, topics, merge settings, features, and whether the branch protection ruleset `main` exists and matches the plugin's ruleset-main.json, or with checks=ci ruleset-main-ci.json, which also requires the status check `ci`). Read-only; the other aleogr-repo-github skills call it first.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" github_repo-describe), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" github_repo-describe *)
---

# github_repo-describe

Reads the real state of a GitHub repository with the `gh` CLI and reports it. It never creates, changes or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. |
| `name=<name>` | The repository name. |
| `checks=<ci\|none>` | `none` (default): the ruleset file is `ruleset-main.json`. `ci`: the ruleset file is `ruleset-main-ci.json`, the same ruleset plus the rule that requires the status check `ci`. |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" github_repo-describe <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github could not be run: update the plugin aleogr-repo-github, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "repo-describe",
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
