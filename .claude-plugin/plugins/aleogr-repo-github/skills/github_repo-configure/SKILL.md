---
description: GitHub repository configure, with the gh CLI. Use to correct the settings of an existing GitHub repository (description, topics, merge methods, delete branch on merge, issues, wiki, projects) and its visibility. Only the given settings are touched; plan by default; a visibility change needs confirmVisibility equal to the requested visibility.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_repo-configure), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_repo-configure *)
---

# github_repo-configure

Corrects the settings and the visibility of an existing GitHub repository with the `gh` CLI, and verifies them. Only the settings given as arguments are compared and changed: an argument left out is not read as a wish and is never changed. It never creates a repository (that is `github_repo-create`).

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces or commas is written in quotes (`description="Status pages, per tenant"`, `topics="a,b"`).

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `description=<text>` | The wanted description. |
| `topics=<t1>,<t2>` | The complete wanted list of topics, comma-separated. `topics=` (empty) means no topics. |
| `mergeCommit=<true\|false>` | Allow merge commits. |
| `squash=<true\|false>` | Allow squash merging. |
| `rebase=<true\|false>` | Allow rebase merging. |
| `deleteBranchOnMerge=<true\|false>` | Delete the head branch when a pull request is merged. |
| `issues=<true\|false>` | Issues on or off. |
| `wiki=<true\|false>` | Wiki on or off. |
| `projects=<true\|false>` | Projects on or off. |
| `visibility=<public\|private>` | The wanted visibility. |
| `confirmVisibility=<public\|private>` | Confirms the visibility change. Needed by `apply` when the visibility changes. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` changes. |

`owner` and `name` are required, and so is at least one setting: `description`, `topics`, `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects` or `visibility` (`topics=` with an empty value counts as a given setting).

A visibility change runs only in `apply` with `confirmVisibility` equal to `visibility`: without it the answer asks the owner ("Make `<owner>/<name>` PUBLIC? Its whole history becomes visible." or "Make `<owner>/<name>` PRIVATE? Branch protection stops being enforced on the free plan.") and leaves the visibility as it is, with the `pending` item `confirm visibility <value>`. If the owner answers yes later in this conversation, run this skill again with that item's `how`; any other answer changes nothing.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" github_repo-configure <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-repo-github" --read-only github_repo-configure <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`description="Status pages, per tenant"`, `topics="a,b"`) is one argument whose value is the text inside them: write it `'description=Status pages, per tenant'`, `'topics=a,b'`, without the double quotes.

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
  "action": "repo-configure",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-repo-github, then try again" } ]
}
```
