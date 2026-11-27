---
description: Google Cloud SQL (gcp-cloud-sql) instance stop. Use to stop the shared platform's Cloud SQL instance when nobody needs the database, so it stops costing by the hour. Acts at once, no mode; an instance that is already stopped is left alone. Fixed cost of about R$ 50 per month while stopped.
---

# gcp-cloud-sql_instance-stop

Stops a running Cloud SQL instance by setting its activation policy to `NEVER`. It has no `mode`: it acts when invoked. A stopped instance keeps costing about R$ 50 per month while stopped.

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
aleogr-db-gcp-cloud-sql gcp-cloud-sql_instance-stop <arguments>
```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command aleogr-db-gcp-cloud-sql could not be run: update the plugin aleogr-db-gcp-cloud-sql, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "instance-stop",
  "mode": "apply",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-db-gcp-cloud-sql, then try again" } ]
}
```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
