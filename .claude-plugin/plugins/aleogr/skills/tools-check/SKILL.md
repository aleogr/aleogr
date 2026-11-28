---
description: aleogr tools check. Use before planning or applying platform changes, to confirm the Google Cloud CLI (gcloud) is installed and authenticated and to see where Claude is running. With the opt-in argument command=gh it checks the GitHub CLI (gh) instead, for the GitHub repository skills, and with command=go the Go command (go), for the Go stack's database check. Read-only.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr" tools-check), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr" tools-check *)
---

# tools-check

Checks that the command-line tools aleogr needs are ready, and where this session runs. It changes nothing and has no cost. By default the only tool it checks is `gcloud`. The opt-in `command=gh` checks the GitHub CLI (`gh`) instead, and the opt-in `command=go` the Go command (`go`). Other skills run it first and stop if it reports a problem.

## Arguments

`command` (optional): `gcloud` (default), `gh` or `go`. Without it the skill checks `gcloud`, exactly as before.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr" tools-check <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr could not be run: update the plugin aleogr, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "tools-check",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr, then try again" } ]
}
```
