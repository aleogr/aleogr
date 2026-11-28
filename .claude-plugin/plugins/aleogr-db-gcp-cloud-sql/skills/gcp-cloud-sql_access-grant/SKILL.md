---
description: Google Cloud SQL (gcp-cloud-sql) access grant. Use to let one component's service account reach its database on the shared platform's Cloud SQL instance with no password - by granting it, as `serviceAccount:<e-mail>` only, the two connection roles (`roles/cloudsql.client`, `roles/cloudsql.instanceUser`) on the shared project, and by making it an IAM service-account user of the instance. Never a password, never another user type, never a wider role; never starts the instance. Idempotent; plan by default. No cost.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" --read-only gcp-cloud-sql_access-grant), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" --read-only gcp-cloud-sql_access-grant *)
---

# gcp-cloud-sql_access-grant

Lets one service account connect to the shared Cloud SQL instance as itself, with IAM database authentication and no password:

- it makes the account a user of the instance, of the IAM service-account type, when it is missing; then
- it grants `serviceAccount:<account>` the roles `roles/cloudsql.client` (connect) and `roles/cloudsql.instanceUser` (log in) on the shared project, each when missing, without a condition. Cloud SQL grants these roles on a project, not on an instance; they let the account connect and log in, and nothing more.

It never creates a user with a password, never generates, reads or writes a password, never creates a user of any other type, never gives the user a database role, and never grants any other role or any role to another member. It removes nothing. It never starts, stops or changes the instance: a user is made through the Cloud SQL Admin API, which needs the instance running, so on an instance that is not running it makes nothing and grants nothing, and ends `pending` with the item `instance`, naming what to do by the state (on a stopped one, `/aleogr:project-apply confirm=yes`). The user always comes before the roles: the roles held mean that the user exists. There is no cost: roles and users cost nothing.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `sharedProjectId=<id>` | The GCP project of the shared platform, which holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |
| `account=<e-mail>` | The component's service account (`<project>-<component>@<project id>.iam.gserviceaccount.com`). |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

It never starts the instance: on one that is not running it ends `pending` with the item `instance`.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_access-grant <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" --read-only gcp-cloud-sql_access-grant <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql could not be run: update the plugin aleogr-db-gcp-cloud-sql, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "access-grant",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-db-gcp-cloud-sql, then try again" } ]
}
```
