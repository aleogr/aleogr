---
description: Google Cloud SQL (gcp-cloud-sql) instance stop. Use to stop the shared platform's Cloud SQL instance when nobody needs the database, so it stops costing by the hour. Acts at once, no mode; an instance that is already stopped is left alone. Fixed cost of about R$ 50 per month while stopped.
---

# gcp-cloud-sql_instance-stop

Stops a running Cloud SQL instance by setting its activation policy to `NEVER`. It has no `mode`: it acts when invoked. A stopped instance keeps costing about R$ 50 per month while stopped.

## Arguments

Free text after the skill name, as `key=value` pairs. Both are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |

Validate before any command, and never ask for anything. If one is missing, end with the result block with `status` `failed`, the one sentence `<argument> is missing.` and no command. `projectId` must have 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. `instance` must be lowercase letters, digits and `-`, starting with a letter, at most 60 characters. If a value is invalid, end with the result block with `status` `failed`, one sentence saying which argument is wrong, and no command.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Check the instance: invoke `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe` with `projectId=<projectId> instance=<instance>`. Its `aleogr-result` block is only input: do not repeat it; this skill's answer ends with exactly one block, its own.
   - Describe `status` `failed`: stop with `failed` and its one-sentence cause. Run nothing else.
   - `exists` false: stop with `failed` and one sentence saying the instance does not exist. Run nothing else.
   - `state` is `stopped`: run nothing else and end with `status` `unchanged` and `outputs.state` `stopped`.
   - `state` is `creating`: do not patch an instance that is still being created. Run nothing else and end with `failed`, `outputs.state` `creating`, and one sentence: wait for the creation to end, then run this skill again.
   - Any other state (`running`, `starting`, or `unknown`): continue.

2. Stop it:

   ```
   gcloud sql instances patch <instance> --project=<projectId> --activation-policy=NEVER --quiet
   ```

   A non-zero exit ends with `failed` and one sentence of cause, without raw error text. Do not describe again.

3. Verify with one describe, once:

   ```
   gcloud sql instances describe <instance> --project=<projectId> --format=json
   ```

   Read the state with the table below. `updated` only when the state is `stopped`. Any other state, or a failure of the describe, ends with `failed` and one sentence saying what was seen.

Then answer in a few lines: the instance and its state, the cost, and the result block.

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
  "action": "instance-stop",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "instance", "id": "<projectId>/<instance>", "name": "<instance>", "labels": {} }
  ],
  "outputs": { "exists": true, "state": "stopped" },
  "cost": { "fixed": true, "notes": "about R$ 50 per month while stopped" },
  "pending": []
}
```

- `status` is one of `updated` (the instance is now stopped), `unchanged` (it already was), `failed`.
- `mode` is always `apply`: the skill acts.
- `updated` and `unchanged`: `outputs.state` is `stopped`.
- `failed` because an argument is invalid or the check failed: `resources` is empty and `outputs` is `{ "exists": null, "state": null }`. Instance missing: `resources` is empty and `outputs` is `{ "exists": false, "state": null }`. The instance is still being created, or the patch or the verification failed: `resources` lists the instance and `outputs` is `{ "exists": true, "state": "<last state seen>" }`.
- Always `cost` as above.
