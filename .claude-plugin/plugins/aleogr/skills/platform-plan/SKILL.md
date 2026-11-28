---
description: aleogr platform plan. Use to see what the owner's shared platform on Google Cloud (shared project with billing, required APIs, one budget alert, the shared Cloud SQL instance and the switch that stops it at night, and the login of the organization) is missing, comparing the owner's defaults with the real cloud. Changes nothing.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr" platform-plan), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr" platform-plan *)
---

# platform-plan

Compares the owner's choices in `${CLAUDE_PLUGIN_ROOT}/defaults.json` with what exists in the cloud, and reads whether the login of the organization is prepared, and prints a table: item, current state, action. The plan itself only reads: running it changes nothing and costs nothing. What it lists is not all free: the database instance has a fixed cost of `about R$ 50 per month while stopped` once `platform-apply` creates it, and the plan says so whenever it lists the instance to create. `platform-apply` runs it first.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Optional. The shared project's id, when the caller already knows it (`platform-apply` passes it). |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr" platform-plan <arguments>
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
  "action": "platform-plan",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr, then try again" } ]
}
```
