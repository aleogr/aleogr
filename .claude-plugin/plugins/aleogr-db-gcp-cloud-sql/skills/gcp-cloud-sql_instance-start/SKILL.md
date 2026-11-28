---
description: Google Cloud SQL (gcp-cloud-sql) instance start. Use to start the shared platform's stopped Cloud SQL instance when someone needs the database. Acts at once, no mode; an instance that is already running, starting or creating is left alone. The instance costs by the hour until it is stopped.
---

# gcp-cloud-sql_instance-start

Starts a stopped Cloud SQL instance by setting its activation policy to `ALWAYS`. It has no `mode`: it acts when invoked. The command is asynchronous, so the instance takes about twelve minutes to accept connections. While it runs it is charged by the hour, until it is stopped.

## Arguments

Free text after the skill name, as `key=value` pairs. Both are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |

It takes no `mode`: a `mode` other than `apply` ends `failed` before any command.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_instance-start <arguments>
```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql ended without an answer: it may have changed something before it stopped. Read the state (run /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe) before running it again. An instance that runs is charged by the hour: stop it with /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "instance-start",
  "mode": "apply",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "the run may have changed something" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-db-gcp-cloud-sql, then try again" } ]
}
```
