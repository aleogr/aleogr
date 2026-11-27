---
description: Google Cloud SQL (gcp-cloud-sql) database create. Use to make an aleogr project's database for one environment on the shared platform's Cloud SQL instance when it is missing. Never starts the instance: on a stopped one it ends pending and names the command that starts it. Idempotent; plan by default. No cost of its own.
allowed-tools: Bash(aleogr-db-gcp-cloud-sql --read-only gcp-cloud-sql_database-create), Bash(aleogr-db-gcp-cloud-sql --read-only gcp-cloud-sql_database-create *)
---

# gcp-cloud-sql_database-create

Makes the database `<project>_<environment>` on the shared Cloud SQL instance when it is missing, with the instance's defaults (no character set, no collation given). A database that exists is left alone. It creates no user and no password, and grants nothing: `gcp-cloud-sql_access-grant` makes each component's user.

It never starts, stops or changes the instance. A database is made through the Cloud SQL Admin API, which needs the instance running, and what that API answers on a stopped instance is not documented: so on an instance that is not running this skill runs no other command and ends `pending`, naming what to do by the state: on a stopped one, `/aleogr:project-apply confirm=yes`, which starts the instance when something must be made in it. A database costs nothing of its own: only the instance's running hours cost.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `sharedProjectId=<id>` | The GCP project of the shared platform, which holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |
| `project=<name>` | The aleogr project name. |
| `environment=<name>` | The environment: `dev`, `hom` or `prd`. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

It never starts the instance: on one that is not running it ends `pending` with the item `instance`.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-db-gcp-cloud-sql gcp-cloud-sql_database-create <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-db-gcp-cloud-sql --read-only gcp-cloud-sql_database-create <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command aleogr-db-gcp-cloud-sql ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command aleogr-db-gcp-cloud-sql could not be run: update the plugin aleogr-db-gcp-cloud-sql, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "database-create",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-db-gcp-cloud-sql, then try again" } ]
}
```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
