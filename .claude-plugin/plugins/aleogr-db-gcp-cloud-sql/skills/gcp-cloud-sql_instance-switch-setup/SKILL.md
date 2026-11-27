---
description: Google Cloud SQL (gcp-cloud-sql) instance switch setup. Use to create, in the shared platform's Google Cloud project, what starts and stops the shared instance without the owner - a custom role, a service account, its grants, a GitHub Actions workload identity federation pool and provider, and two Cloud Scheduler jobs that stop the instance at night. Idempotent; plan by default.
allowed-tools: Bash(aleogr-db-gcp-cloud-sql --read-only gcp-cloud-sql_instance-switch-setup), Bash(aleogr-db-gcp-cloud-sql --read-only gcp-cloud-sql_instance-switch-setup *)
---

# gcp-cloud-sql_instance-switch-setup

Creates the "switch": a custom role (`aleogrSharedSqlSwitch`) that can only get and update Cloud SQL instances, a service account (`aleogr-shared-sql-switch`) that holds it, a workload identity federation pool (`github`) and provider (`aleogr`) that let GitHub Actions of one repository, on `main`, act as that account, and two Cloud Scheduler jobs (`aleogr-shared-stop-weeknight`, `aleogr-shared-stop-weekend`) that stop the instance at night. Without the jobs an instance left running would keep running all night, so `ready` is true only when every part exists and matches. There is no fixed cost beyond the instance's own (about R$ 50 per month while stopped); the jobs are free at this volume.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`. Values with a space are double-quoted.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The shared platform's GCP project. |
| `instance=<name>` | The instance the jobs stop (the shared platform uses `aleogr-shared`). |
| `region=<region>` | The Cloud Scheduler location, for example `southamerica-east1`. |
| `timeZone=<tz>` | The time zone of both schedules, for example `America/Sao_Paulo`. |
| `weeknightStop="<cron>"` | Cron schedule of the weeknight stop, for example `"30 22 * * 0-4"`. |
| `weekendStop="<cron>"` | Cron schedule of the weekend stop. |
| `repository=<owner>/<repo>` | The GitHub repository allowed to act as the switch account. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

When every part is as declared (`outputs.ready` true), the answer has a section `GitHub secrets`: the three secrets with their values and where to paste them, by hand, once. Those values are never in the result block.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-db-gcp-cloud-sql gcp-cloud-sql_instance-switch-setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-db-gcp-cloud-sql --read-only gcp-cloud-sql_instance-switch-setup <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`weeknightStop="30 22 * * 0-4"`) is one argument whose value is the text inside them: write it `'weeknightStop=30 22 * * 0-4'`, without the double quotes.

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
  "action": "instance-switch-setup",
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
