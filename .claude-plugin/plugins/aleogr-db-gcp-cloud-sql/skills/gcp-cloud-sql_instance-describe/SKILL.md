---
description: Google Cloud SQL (gcp-cloud-sql) instance describe. Use to learn whether the shared platform's Cloud SQL instance exists and what state it is in (running or stopped, version, tier, disk, network exposure, backups, deletion protection). Read-only; the other Cloud SQL skills and the platform plan call it first.
---

# gcp-cloud-sql_instance-describe

Reads the real state of a Cloud SQL instance and reports it. It never creates, changes, starts, stops or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs. Both are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |

Validate before any command. If one is missing, ask for it. `projectId` must have 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. `instance` must be lowercase letters, digits and `-`, starting with a letter, at most 60 characters. If a value is invalid, end with the result block with `status` `failed`, one sentence saying which argument is wrong, and no command.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Describe the instance:

   ```
   gcloud sql instances describe <instance> --project=<projectId> --format=json
   ```

   - Exit non-zero and the text contains `does not exist` or `404`: the instance does not exist. Skip steps 2 and 3 and report `exists` false.
   - Any other non-zero exit (permission denied, API disabled, `gcloud` missing or not authenticated) is a failure of the check, never "missing": say the cause in one sentence, with no raw error text, run nothing else and end with the result block with `status` `failed`.
   - Success: take the values listed under "Reading the JSON" below.

2. Pending operations, only when the instance exists and step 1 gave activation policy `ALWAYS` with state `RUNNABLE`:

   ```
   gcloud sql operations list --instance=<instance> --project=<projectId> --filter="status!=DONE" --limit=10 --format="value(operationType,status)"
   ```

   Cloud SQL shows an instance as `RUNNABLE` as soon as a start is accepted, minutes before it accepts connections; the unfinished operation is what tells the two apart. If any printed line has the operation type `UPDATE`, the state is `starting`; otherwise it is `running`. If this command alone fails, keep `running`, say in one sentence that pending operations could not be checked, and keep `status` `unchanged`.

3. Last backup, only when the instance exists:

   ```
   gcloud sql backups list --instance=<instance> --project=<projectId> --filter="status=SUCCESSFUL" --sort-by="~windowStartTime" --limit=1 --format="value(windowStartTime)"
   ```

   `lastBackup` is the printed timestamp, or `null` when the output is empty. If this command alone fails, use `null`, say so in one sentence and keep `status` `unchanged`: it is not a failure of the check.

Then answer in a few lines: the instance, its state, tier and version, whether it has a public address, the last backup, and the result block. When the state is `starting`, say that it takes about ten minutes from the start to accept connections.

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
| `knowledgeCatalog` | `settings.enableDataplexIntegration` (the Knowledge Catalog integration, formerly Dataplex) |

A boolean that is absent from the JSON is `false`.

| `settings.activationPolicy` | `state` | Skill's `state` |
|---|---|---|
| `NEVER` | any | `stopped` |
| `ALWAYS` | `RUNNABLE` | `running`, or `starting` while an `UPDATE` operation is unfinished (step 2) |
| `ALWAYS` | `PENDING_CREATE` | `creating` |
| `ALWAYS` | anything else | `starting` |
| any other value, or absent | any | `unknown` |

When the state is `unknown`, the answer reports the raw `settings.activationPolicy` value (or that it is absent); the status stays `unchanged`.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

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
    "databaseVersion": "POSTGRES_18",
    "edition": "ENTERPRISE",
    "tier": "db-f1-micro",
    "region": "us-central1",
    "diskSizeGb": 10,
    "storageAutoIncrease": false,
    "publicAddress": true,
    "authorizedNetworks": 0,
    "backupEnabled": true,
    "backupStartUtc": "23:00",
    "deletionProtection": true,
    "knowledgeCatalog": false,
    "lastBackup": "2026-11-16T23:12:03.123Z"
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `status` is `unchanged` whenever the state was read, whether or not the instance exists. It is `failed` when an argument is invalid or step 1 failed for any reason other than "does not exist"; then `resources` is empty and `outputs` is `{ "exists": null }`.
- Instance does not exist: `resources` is empty and `outputs` is `{ "exists": false, "state": null }` with every other output `null`, except the counts and booleans, which are `0` and `false`.
- `mode` is always `plan`: the skill only reads.
