---
description: Google Cloud SQL (gcp-cloud-sql) database describe. Use to learn, for an aleogr project and environment, whether the shared platform's Cloud SQL instance is running, whether the project's database exists on it, which of the given service accounts are its users, and whether each holds the two connection roles on the shared project. Read-only; a stopped or starting instance is a normal state, not a failure. The plan of a project calls it.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_database-describe), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_database-describe *)
---

# gcp-cloud-sql_database-describe

Reads, for one aleogr project and environment, what its database on the shared Cloud SQL instance needs: the instance's state, the database `<project>_<environment>`, and, for each given service account, whether it is a user of the instance and whether it holds `roles/cloudsql.client` and `roles/cloudsql.instanceUser` on the shared project. It never creates, changes, starts, stops or deletes anything and has no `mode`.

A database and a user can only be read through the Cloud SQL Admin API while the instance runs. When the instance is stopped or starting, this skill reads the instance and the roles, marks the database and the users `not read` (`null`), and ends `unchanged`: a stopped instance is the shared platform's normal state, never a failure. What the Admin API answers on a stopped instance is not documented, so this skill never asks it: it decides by the instance's state alone.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required.

| Argument | Meaning |
|---|---|
| `sharedProjectId=<id>` | The GCP project of the shared platform, which holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |
| `project=<name>` | The aleogr project name. |
| `environment=<name>` | The environment: `dev`, `hom` or `prd`. |
| `accounts=<e-mail>[,<e-mail>…]` | The service accounts of the project's components that use the database, in the declaration's order. |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_database-describe <arguments>
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
  "action": "database-describe",
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
