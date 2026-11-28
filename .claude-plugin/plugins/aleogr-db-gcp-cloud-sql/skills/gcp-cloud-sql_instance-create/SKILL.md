---
description: Google Cloud SQL (gcp-cloud-sql) instance create. Use to create the shared platform's Cloud SQL for PostgreSQL instance, leave it stopped (with stopJob, by running the night-stop job, which proves it works) and verify it. Idempotent (an existing instance is never touched); plan by default; apply needs confirm=yes. Fixed cost of about R$ 50 per month while stopped.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" --read-only gcp-cloud-sql_instance-create), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" --read-only gcp-cloud-sql_instance-create *)
---

# gcp-cloud-sql_instance-create

Creates the shared platform's Cloud SQL instance, waits for it, stops it (activation policy `NEVER`) and verifies that it is stopped. With `stopJob`, the stop is made by running that Cloud Scheduler job, which proves the night stop works on the new instance. If the instance already exists it changes nothing and never stops it. The instance has a fixed cost: about R$ 50 per month while stopped.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`, `confirm`, `stopJob` and `resume`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that will hold the instance. |
| `instance=<name>` | The instance name (the shared platform uses `aleogr-shared`). |
| `platform=shared` | Must be `shared`: this skill only creates the shared platform's instance. |
| `version=<POSTGRES_n>` | The database version, for example `POSTGRES_17`. |
| `tier=<tier>` | The machine tier, for example `db-f1-micro`. |
| `edition=<edition>` | The Cloud SQL edition, for example `enterprise`. |
| `region=<region>` | The region. |
| `storageGb=<n>` | Disk size in GB. |
| `backupStartUtc=<HH:MM>` | Start of the daily backup window, UTC. |
| `retainedBackups=<n>` | How many automated backups to keep. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |
| `confirm=yes` | Required for `apply` to create anything. |
| `stopJob=<job>` | Optional. The Cloud Scheduler job, in the location `region`, that stops this instance at night (the shared platform uses `aleogr-shared-stop-weeknight`). When given, the new instance is stopped by running this job instead of by this skill's own command (step 6). |
| `resume=yes` | Optional, given only by `platform-apply`, with `mode=apply` and `confirm=yes`, when its own run asked for the creation in an earlier command: the run skips the creation and goes on from it (the wait, the stop, the check). It never creates: when the instance is not found or cannot be read, the run ends `failed` and nothing was created. It is honoured only for an instance that is not stopped and whose last ten operations show only its creation and backups (an instance of that name made by hand, never stopped and recent, would meet that rule, which is why only `platform-apply` gives it); otherwise nothing is changed, and the answer says why it was not used. |

Nothing is created without `mode=apply` and `confirm=yes` both: with `mode=apply` and no `confirm`, the run creates nothing and ends `pending` with the item `confirm`, whose `how` is the same invocation with `confirm=yes`; any other value of `confirm` fails. Creating the instance starts its fixed cost (about R$ 50 per month while stopped), and it is charged by the hour while it runs, until it is stopped.

One run waits at most eight minutes for the new instance (`sleep 30` at a time, run by the command itself). A creation that takes longer ends `pending`, with the instance running and charged by the hour, and its item gives the command that stops it: run that command once the creation has ended. A second run of this skill finds the instance and changes nothing: it does not stop it.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" gcp-cloud-sql_instance-create <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql" --read-only gcp-cloud-sql_instance-create <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again. An instance that runs is charged by the hour: stop it with /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-db-gcp-cloud-sql could not be run: update the plugin aleogr-db-gcp-cloud-sql, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "instance-create",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-db-gcp-cloud-sql, then try again" } ]
}
```
