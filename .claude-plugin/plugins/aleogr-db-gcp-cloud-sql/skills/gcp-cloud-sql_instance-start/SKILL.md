---
description: Google Cloud SQL (gcp-cloud-sql) instance start. Use to start the shared platform's stopped Cloud SQL instance when someone needs the database. Acts at once, no mode; an instance that is already running, starting or creating is left alone. The instance costs by the hour until it is stopped.
---

# gcp-cloud-sql_instance-start

Starts a stopped Cloud SQL instance by setting its activation policy to `ALWAYS`. It has no `mode`: it acts when invoked. The command is asynchronous, so the instance takes about twelve minutes to accept connections. While it runs it is charged by the hour, until it is stopped.

## Arguments

Free text after the skill name, as `key=value` pairs. Both are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |

Validate before any command, and never ask for anything. If one is missing, end with the result block with `status` `failed`, the one sentence `<argument> is missing.`, word for word, and no command. `projectId` must have 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. `instance` must be lowercase letters, digits and `-`, starting with a letter, at most 60 characters. If a value is invalid, end with the result block with `status` `failed`, one sentence saying which argument is wrong, and no command.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Check the instance: invoke `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe` with `projectId=<projectId> instance=<instance>`. Its `aleogr-result` block is only input: do not repeat it; this skill's answer ends with exactly one block, its own.
   - Describe `status` `failed`: stop with `failed` and the sentence `The instance <instance> could not be read, so it was not started.` Run nothing else.
   - `exists` false: stop with `failed` and the sentence `The instance <instance> does not exist, so it was not started.` Run nothing else.
   - `state` is `running`, `starting` or `creating`: run nothing else and end with `status` `unchanged` and `outputs.state` as the describe reported it.
   - `state` is `unknown`: run nothing else and end with `failed` and one sentence giving the activation policy the describe reported.
   - `state` is `stopped`: continue.

2. Start it (asynchronous, so the command returns at once):

   ```
   gcloud sql instances patch <instance> --project=<projectId> --activation-policy=ALWAYS --async --quiet
   ```

   A non-zero exit is not yet the end: the command may have reached Cloud SQL even though it failed here, and a started instance is charged by the hour. Read the instance once, with the describe command of step 3, and decide by its `settings.activationPolicy` alone, never by the text of the failure:

   - `ALWAYS`: the start was accepted after all. Go on as after an accepted patch, with this describe as the verification of step 3 (do not describe again): `updated`, `outputs.state` `starting`, and the answer also says `The start command failed, but the instance is starting: it is charged by the hour until it is stopped.`
   - `NEVER`: `failed`, `outputs.state` `stopped`, with the sentence `The instance <instance> could not be started: it is still stopped, so it is not charged by the hour.`
   - The describe fails, or any other value: `failed`, `outputs.state` `null`, with the sentence `The instance <instance> could not be started, and a read after the failure could not tell whether it is running: /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe shows whether it is charged by the hour.`

   No raw error text in any of them, and no other command: this is the one read after a failed patch.

3. Verify with one describe, once (after a patch that exited 0):

   ```
   gcloud sql instances describe <instance> --project=<projectId> --format=json
   ```

   Read the state with the table below. The patch was accepted, so the status is `updated`, with `outputs.state` `starting`: Cloud SQL shows the instance as running as soon as the start is accepted, minutes before it accepts connections, so a `running` or `starting` reading right after the patch is reported as `starting`. A describe right after an asynchronous patch may still show `stopped` for a moment, which is not a failure; then `outputs.state` is `stopped` and the answer says it may show `stopped` for a moment before `starting`. If the describe itself fails, the status is still `updated` (the patch was accepted) with `outputs.state` `null`, and the answer says the state could not be read.

Then answer in a few lines: the instance and its state, that it takes about twelve minutes to accept connections, that `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe projectId=<projectId> instance=<instance>` shows when it is `running`, that it is charged by the hour until it is stopped (`/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop`), and the result block. Every sentence written in backquotes in this skill is said word for word, never reworded, shortened or split: an invoking skill relays it as it is. This skill does not check the night stop (the scheduler jobs of `gcp-cloud-sql_instance-switch-setup`): when the caller knows the night stop is not set up, the instance runs until someone stops it by hand, and the answer says so.

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
  "action": "instance-start",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "instance", "id": "<projectId>/<instance>", "name": "<instance>", "labels": {} }
  ],
  "outputs": { "exists": true, "state": "starting" },
  "cost": { "fixed": false, "notes": "charged by the hour while running" },
  "pending": []
}
```

- `status` is one of `updated` (the start was requested, or a failed patch was read back as `ALWAYS`), `unchanged` (already `running`, `starting` or `creating`), `failed`.
- `mode` is always `apply`: the skill acts.
- `updated`: `outputs.state` is `starting` (or briefly `stopped`; `null` when that describe failed). `unchanged`: `outputs.state` is the state seen.
- `failed` because an argument is invalid or the check failed: `resources` is empty and `outputs` is `{ "exists": null, "state": null }`. Instance missing: `resources` is empty and `outputs` is `{ "exists": false, "state": null }`. The patch failed and the read after it shows `NEVER`: `resources` lists the instance and `outputs` is `{ "exists": true, "state": "stopped" }`; that read failed or showed another value: `resources` lists the instance and `outputs` is `{ "exists": true, "state": null }`. The patch failed and the read shows `ALWAYS`: `updated`, as above. State `unknown`: `resources` lists the instance and `outputs` is `{ "exists": true, "state": "unknown" }`.
- Always `cost` as above.
