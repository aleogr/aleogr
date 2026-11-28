---
description: Google Cloud SQL (gcp-cloud-sql) instance describe. Use to learn whether the shared platform's Cloud SQL instance exists and what state it is in (running or stopped, version, tier, disk, network exposure, backups, deletion protection). Read-only; the other Cloud SQL skills and the platform plan call it first.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_instance-describe), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_instance-describe *)
---

# gcp-cloud-sql_instance-describe

Reads the real state of a Cloud SQL instance and reports it. It never creates, changes, starts, stops or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs. Both are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_instance-describe <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql could not be run: update the plugin aleogr-db-gcp-cloud-sql, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "instance-describe",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-db-gcp-cloud-sql, then try again" } ]
}
```
