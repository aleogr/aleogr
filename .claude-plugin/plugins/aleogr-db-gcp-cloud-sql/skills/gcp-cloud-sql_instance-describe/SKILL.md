---
description: Google Cloud SQL (gcp-cloud-sql) instance describe. Use to learn whether the lab's shared Cloud SQL instance exists and what state it is in (running or stopped, version, tier, disk, network exposure, backups, deletion protection). Read-only; the other Cloud SQL skills and the platform plan call it first.
---

# gcp-cloud-sql_instance-describe

Reads the real state of a Cloud SQL instance and reports it. It never creates, changes, starts, stops or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs. Both are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the lab uses `aleogr-lab`). |

Validate before any command. If one is missing, ask for it. `projectId` must have 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. `instance` must be lowercase letters, digits and `-`, starting with a letter, at most 60 characters. If a value is invalid, end with the result block with `status` `failed`, one sentence saying which argument is wrong, and no command.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Describe the instance:

   ```
   gcloud sql instances describe <instance> --project=<projectId> --format=json
   ```

   - Exit non-zero and the text contains `does not exist` or `404`: the instance does not exist. Skip step 2 and report `exists` false.
   - Any other non-zero exit (permission denied, API disabled, `gcloud` missing or not authenticated) is a failure of the check, never "missing": say the cause in one sentence, with no raw error text, run nothing else and end with the result block with `status` `failed`.
   - Success: take the values listed under "Reading the JSON" below.

2. Last backup, only when the instance exists:

   ```
   gcloud sql backups list --instance=<instance> --project=<projectId> --filter="status=SUCCESSFUL" --sort-by="~windowStartTime" --limit=1 --format="value(windowStartTime)"
   ```

   `lastBackup` is the printed timestamp, or `null` when the output is empty. If this command alone fails, use `null`, say so in one sentence and keep `status` `unchanged`: it is not a failure of the check.

Then answer in a few lines: the instance, its state, tier and version, whether it has a public address, the last backup, and the result block.

## Reading the JSON

| Output | Source |
|---|---|
| `state` | From `settings.activationPolicy` and `state`, see the table below. |
| `databaseVersion` | `databaseVersion` |
| `edition` | `settings.edition` |
| `tier` | `settings.tier` |
| `region` | `region` |
| `diskSizeGb` | `settings.dataDiskSizeGb`, as a number |
| `storageAutoIncrease` | `settings.storageAutoResize` |
| `publicAddress` | `settings.ipConfiguration.ipv4Enabled` |
| `authorizedNetworks` | the number of entries in `settings.ipConfiguration.authorizedNetworks` (0 when absent) |
| `backupEnabled` | `settings.backupConfiguration.enabled` |
| `backupStartUtc` | `settings.backupConfiguration.startTime` (`null` when absent) |
| `deletionProtection` | `settings.deletionProtectionEnabled` |

A boolean that is absent from the JSON is `false`.

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
  "action": "instance-describe",
  "mode": "plan",
  "status": "unchanged",
  "resources": [
    { "type": "instance", "id": "<projectId>/<instance>", "name": "<instance>", "labels": {} }
  ],
  "outputs": {
    "exists": true,
    "state": "stopped",
    "databaseVersion": "POSTGRES_17",
    "edition": "ENTERPRISE",
    "tier": "db-f1-micro",
    "region": "southamerica-east1",
    "diskSizeGb": 10,
    "storageAutoIncrease": true,
    "publicAddress": true,
    "authorizedNetworks": 0,
    "backupEnabled": true,
    "backupStartUtc": "06:00",
    "deletionProtection": false,
    "lastBackup": "2026-11-16T06:12:03.123Z"
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `status` is `unchanged` whenever the state was read, whether or not the instance exists. It is `failed` when an argument is invalid or step 1 failed for any reason other than "does not exist"; then `resources` is empty and `outputs` is `{ "exists": null }`.
- Instance does not exist: `resources` is empty and `outputs` is `{ "exists": false, "state": null }` with every other output `null`, except the counts and booleans, which are `0` and `false`.
- `mode` is always `plan`: the skill only reads.
