---
description: Google Cloud SQL (gcp-cloud-sql) instance create. Use to create the lab's shared Cloud SQL for PostgreSQL instance, leave it stopped and verify it. Idempotent (an existing instance is never touched); plan by default; apply needs confirm=yes. Fixed cost of about R$ 50 per month while stopped.
---

# gcp-cloud-sql_instance-create

Creates the lab's shared Cloud SQL instance, waits for it, stops it (activation policy `NEVER`) and verifies that it is stopped. If the instance already exists it changes nothing and never stops it. The instance has a fixed cost: about R$ 50 per month while stopped.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode` and `confirm`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that will hold the instance. |
| `instance=<name>` | The instance name (the lab uses `aleogr-lab`). |
| `platform=lab` | Must be `lab`: this skill only creates the lab's shared instance. |
| `version=<POSTGRES_n>` | The database version, for example `POSTGRES_17`. |
| `tier=<tier>` | The machine tier, for example `db-f1-micro`. |
| `edition=<edition>` | The Cloud SQL edition, for example `enterprise`. |
| `region=<region>` | The region. |
| `storageGb=<n>` | Disk size in GB. |
| `backupStartUtc=<HH:MM>` | Start of the daily backup window, UTC. |
| `retainedBackups=<n>` | How many automated backups to keep. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |
| `confirm=yes` | Required for `apply` to create anything. |

## Validate first

Before any command, check the arguments. If one required argument is missing, ask for it. Any other failure ends the skill with the result block, `status` `failed`, one sentence saying which rule failed, and no `gcloud` call.

- `projectId`: 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter, not ending with `-`.
- `instance`: lowercase letters, digits and `-`, starting with a letter, at most 60 characters.
- `platform` must be `lab`. Anything else, or absent, is `failed`.
- `version` matches `POSTGRES_[0-9]+`.
- `storageGb` is an integer from 10 to 100.
- `backupStartUtc` is `HH:MM` (24 hours).
- `retainedBackups` is an integer from 1 to 30.
- `mode` is `plan` or `apply`; `confirm`, when given, is `yes`.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Check whether the instance exists: invoke `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe` with `projectId=<projectId> instance=<instance>`. Its `aleogr-result` block is only input: do not repeat it; this skill's answer ends with exactly one block, its own.
   - Describe `status` `failed`: stop with `failed` and its one-sentence cause. Run nothing else.
   - `exists` true: run nothing else and end with `status` `unchanged`, `outputs.exists` true and `outputs.state` as the describe reported it. Never stop, start or change an existing instance.
   - `exists` false: continue.

2. `plan` ends here: say what would be created (instance, version, tier, edition, region, disk, backups, deletion protection, then stopped) and the cost, and end with `status` `would-create`.

3. `apply` without `confirm=yes` ends here with `status` `pending`, creating nothing. `pending` has one item whose `how` is this same invocation plus `confirm=yes`, and the answer says to run it with `confirm=yes`.

4. `apply` with `confirm=yes`. Say first that creation takes several minutes, then create the instance (asynchronous, so the command returns at once). The instance gets a public address with no authorized networks, and IAM database authentication is on.

   ```
   gcloud sql instances create <instance> --project=<projectId> --database-version=<version> --edition=<edition> --tier=<tier> --region=<region> --availability-type=zonal --storage-type=SSD --storage-size=<storageGb> --no-storage-auto-increase --assign-ip --backup --backup-start-time=<backupStartUtc> --retained-backups-count=<retainedBackups> --no-enable-point-in-time-recovery --database-flags="cloudsql.iam_authentication=on" --deletion-protection --async --quiet
   ```

   A non-zero exit stops with `failed` (nothing was created) and one sentence of cause, without raw error text. Do not run the patch. From here on the instance exists: any later failure ends with `pending`, never `failed`.

5. Wait until the instance is running. Run this describe command (the command alone, not the describe skill):

   ```
   gcloud sql instances describe <instance> --project=<projectId> --format=json
   ```

   Read the state with the table below. When it already shows `running`, no waiting happens: go straight to step 6. Otherwise wait 30 seconds, describe again, and repeat for at most 20 minutes. Timeout, or a describe that fails, ends with `pending` (the instance exists, and is not stopped): `resources` lists it and `pending[].how` is `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=<projectId> instance=<instance>`.

6. Stop it (the lab keeps the instance stopped until someone needs it):

   ```
   gcloud sql instances patch <instance> --project=<projectId> --activation-policy=NEVER --quiet
   ```

   A non-zero exit ends with `pending` with the same `how` as in step 5.

7. Verify with the same describe command as step 5, once. `created` only when the state is `stopped`. Any other state, or a failure, ends with `pending` and the same `how`, saying what was seen.

Then answer in a few lines: the instance, its state, the cost, and the result block.

## Reading the state

From `settings.activationPolicy` and `state` of the describe JSON:

| `settings.activationPolicy` | `state` | Skill's `state` |
|---|---|---|
| `NEVER` | any | `stopped` |
| `ALWAYS` | `RUNNABLE` | `running` |
| `ALWAYS` | `PENDING_CREATE` | `creating` |
| `ALWAYS` | anything else | `starting` |

## Result block

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

- `mode` echoes the mode used. `status` is one of `would-create` (plan), `created`, `unchanged` (the instance already existed), `pending` (unconfirmed apply, or the instance exists and a later step failed), `failed`.
- `would-create`, unconfirmed `pending` and `failed`: `resources` is empty and `outputs` is `{ "exists": false, "state": null }`; a `failed` caused by the check itself has `{ "exists": null, "state": null }`.
- `unchanged`: `resources` lists the instance; `outputs` is `{ "exists": true, "state": "<its state>" }`.
- `created`: `resources` lists the instance; `outputs.state` is `stopped`.
- `pending` after the create: `resources` lists the instance, `outputs.exists` is true and `outputs.state` the last state seen.
- Always `cost` as above.
