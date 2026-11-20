---
description: Google Cloud SQL (gcp-cloud-sql) instance create. Use to create the shared platform's Cloud SQL for PostgreSQL instance, leave it stopped (with stopJob, by running the night-stop job, which proves it works) and verify it. Idempotent (an existing instance is never touched); plan by default; apply needs confirm=yes. Fixed cost of about R$ 50 per month while stopped.
---

# gcp-cloud-sql_instance-create

Creates the shared platform's Cloud SQL instance, waits for it, stops it (activation policy `NEVER`) and verifies that it is stopped. With `stopJob`, the stop is made by running that Cloud Scheduler job, which proves the night stop works on the new instance. If the instance already exists it changes nothing and never stops it. The instance has a fixed cost: about R$ 50 per month while stopped.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`, `confirm` and `stopJob`.

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

## Validate first

Before any command, check the arguments. A missing required argument is a validation failure: do not ask for it. Any failure ends the skill with the result block, `status` `failed`, one sentence saying which rule failed, and no `gcloud` call.

- `projectId`: 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter, not ending with `-`.
- `instance`: lowercase letters, digits and `-`, starting with a letter, at most 60 characters.
- `platform` must be `shared`. Anything else, or absent, is `failed`.
- `version` matches `POSTGRES_[0-9]+`.
- `storageGb` is an integer from 10 to 100.
- `backupStartUtc` is `HH:MM` (24 hours).
- `retainedBackups` is an integer from 1 to 30.
- `mode` is `plan` or `apply`; `confirm`, when given, is `yes`.
- `stopJob`, when given: lowercase letters, digits and `-`.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Check whether the instance exists: invoke `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe` with `projectId=<projectId> instance=<instance>`. Its `aleogr-result` block is only input: do not repeat it; this skill's answer ends with exactly one block, its own.
   - Describe `status` `failed`: stop with `failed` and its one-sentence cause. Run nothing else.
   - `exists` true: run nothing else and end with `status` `unchanged`, `outputs.exists` true and `outputs.state` as the describe reported it. Never stop, start or change an existing instance.
   - `exists` false: continue.

2. `plan` ends here: say what would be created (instance, version, tier, edition, region, disk, backups, deletion protection, then stopped, by the job `stopJob` when given) and the cost, and end with `status` `would-create`.

3. `apply` without `confirm=yes` ends here with `status` `pending`, creating nothing. `pending` has one item whose `how` is this same invocation plus `confirm=yes`, and the answer says to run it with `confirm=yes`.

4. `apply` with `confirm=yes`. Say first that creation takes several minutes, then create the instance (asynchronous, so the command returns at once). The instance gets a public address with no authorized networks, and IAM database authentication is on.

   ```
   gcloud sql instances create <instance> --project=<projectId> --database-version=<version> --edition=<edition> --tier=<tier> --region=<region> --availability-type=zonal --storage-type=SSD --storage-size=<storageGb> --no-storage-auto-increase --assign-ip --backup --backup-start-time=<backupStartUtc> --retained-backups-count=<retainedBackups> --no-enable-point-in-time-recovery --database-flags="cloudsql.iam_authentication=on" --no-enable-dataplex-integration --deletion-protection --async --quiet
   ```

   A non-zero exit stops with `failed` (nothing was created) and one sentence of cause, without raw error text. Do not run the patch. From here on the instance exists: any later failure ends with `pending`, never `failed`.

5. Wait until the instance is running. Run this describe command (the command alone, not the describe skill):

   ```
   gcloud sql instances describe <instance> --project=<projectId> --format=json
   ```

   Read the state with the table below. When it already shows `running`, no waiting happens: go straight to step 6. When it shows `stopped`, the instance exists and is already stopped: the wait ends, run no stop command and no job, and go to step 7 (with `stopJob`, the answer says the night stop was not tested). Otherwise wait 30 seconds, describe again, and repeat for at most 20 minutes. Timeout, or a describe that fails, ends with `pending` (the instance exists, and is not stopped): `resources` lists it and `pending[].how` is `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=<projectId> instance=<instance>`.

6. Stop it (the shared instance stays stopped until someone needs it).

   **Without `stopJob`**, stop it with this skill's own command:

   ```
   gcloud sql instances patch <instance> --project=<projectId> --activation-policy=NEVER --quiet
   ```

   A non-zero exit ends with `pending` with the same `how` as in step 5.

   **With `stopJob`**, stop it with the night-stop job, which proves that the job really stops the instance. Do not run the patch first. Run the job once:

   ```
   gcloud scheduler jobs run <stopJob> --project=<projectId> --location=<region> --quiet
   ```

   - Exit zero: describe with the command of step 5 at once; while the state is not `stopped`, wait 30 seconds and describe again, for at most 5 minutes after the run. When a describe already shows `stopped`, no waiting happens. `stopped` within the 5 minutes: the night stop is proven; go to step 7.
   - Non-zero exit of the run, a describe that fails, or still not `stopped` after 5 minutes: the job did not stop the instance. Stop it with this skill's own patch command above (a non-zero exit ends with `pending` with the same `how` as in step 5, plus the night-stop item below), then go to step 7. Whatever step 7 sees, the status is then `pending`, never `created` (when step 7 does not see `stopped`, `pending` also has the item of step 5), and the answer has one sentence saying that the instance exists and is stopped but the night-stop job `<stopJob>` did NOT stop it. `pending` gets one item whose `item` is `night stop`, `reason` `manual`, and whose `how` is exactly: `the night stop does not work: send this output; until it is fixed, stop the instance by hand after each use`.

7. Verify with the same describe command as step 5, once (the describe of step 6 that showed `stopped` already is this verification: do not repeat it). `created` only when the state is `stopped` and step 6 did not fall back to the patch after a job that did not stop the instance. Any other state, or a failure, ends with `pending` and the same `how` as in step 5, saying what was seen.

Then answer in a few lines: the instance, its state, the cost (`about R$ 50 per month while stopped`), with `stopJob` whether the night stop was proven (the job stopped the new instance) or not, and the result block.

## Reading the state

From `settings.activationPolicy` and `state` of the describe JSON:

| `settings.activationPolicy` | `state` | Skill's `state` |
|---|---|---|
| `NEVER` | any | `stopped` |
| `ALWAYS` | `RUNNABLE` | `running` |
| `ALWAYS` | `PENDING_CREATE` | `creating` |
| `ALWAYS` | anything else | `starting` |

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "instance-create",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "instance", "id": "<projectId>/<instance>", "name": "<instance>", "labels": {} }
  ],
  "outputs": { "exists": true, "state": "stopped" },
  "cost": { "fixed": true, "notes": "about R$ 50 per month while stopped" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create` (plan), `created`, `unchanged` (the instance already existed), `pending` (unconfirmed apply, the instance exists and a later step failed, or the night-stop job did not stop it), `failed`.
- `would-create`, unconfirmed `pending` and a `failed` create command: `resources` is empty and `outputs` is `{ "exists": false, "state": null }`. A `failed` from validation or from the check itself has `{ "exists": null, "state": null }`.
- `unchanged`: `resources` lists the instance; `outputs` is `{ "exists": true, "state": "<its state>" }`.
- `created`: `resources` lists the instance; `outputs.state` is `stopped`.
- `pending` after the create: `resources` lists the instance, `outputs.exists` is true and `outputs.state` the last state seen (`stopped` when only the night-stop job failed). Each `pending` item is `{ "item": "<what>", "reason": "manual", "how": "<text>" }`.
- Always `cost` as above.
