---
description: GitHub repository create, with the gh CLI. Use to create a GitHub repository with a README (so `main` exists from the start), a description and topics, then verify it. Idempotent (an existing repository is never changed; what differs is reported for github_repo-configure); plan by default; private by default, and a public repository needs confirmVisibility=public.
allowed-tools: Bash(aleogr-repo-github --read-only github_repo-create), Bash(aleogr-repo-github --read-only github_repo-create *)
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
  aleogr-repo-github github_repo-create <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-repo-github --read-only github_repo-create <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`description="Status pages, per tenant"`) is one argument whose value is the text inside them: write it `'description=Status pages, per tenant'`, without the double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command aleogr-repo-github could not be run: update the plugin aleogr-repo-github, then try again.` followed by this block, and nothing else (with `"mode": "apply"` in place of `"mode": "plan"` when the command was the one for `mode=apply`):

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

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
