---
description: GitHub repository create, with the gh CLI. Use to create a GitHub repository with a README (so `main` exists from the start), a description and topics, then verify it. Idempotent (an existing repository is never changed; what differs is reported for github_repo-configure); plan by default; private by default, and a public repository needs confirmVisibility=public.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_repo-create), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_repo-create *)
---

# github_repo-create

Creates a GitHub repository with the `gh` CLI, with a README, an optional description and optional topics, and verifies it. An existing repository is never changed: the skill reports what differs from the arguments, and `github_repo-configure` is the skill that corrects it.

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces is written in quotes (`description="Status pages, per tenant"`).

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `visibility=<public\|private>` | Visibility of the new repository. Default `private`. |
| `confirmVisibility=public` | Confirms that the repository is created public. Needed by `apply` with `visibility=public`. |
| `description=<text>` | Description of the repository. Optional. |
| `topics=<t1>,<t2>` | Topics, comma-separated. Optional. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` creates. |

`owner` and `name` are required.

`apply` with `visibility=public` creates nothing without `confirmVisibility=public`: the answer then asks the owner "Create `<owner>/<name>` as PUBLIC?" and ends `pending`. If the owner answers yes later in this conversation, run this skill again with the same arguments plus `confirmVisibility=public`; any other answer creates nothing.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" github_repo-create <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_repo-create <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`description="Status pages, per tenant"`) is one argument whose value is the text inside them: write it `'description=Status pages, per tenant'`, without the double quotes.

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
  "action": "repo-create",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-repo-github, then try again" } ]
}
```
