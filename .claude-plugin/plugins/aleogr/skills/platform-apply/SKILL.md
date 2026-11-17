---
description: aleogr platform apply. Use to create the free part of the owner's lab platform on Google Cloud (shared project with billing, required APIs, one budget alert), then the shared Cloud SQL instance with the switch that stops it at night, from the owner's defaults. Shows the plan and asks for confirmation unless confirm=yes.
---

# platform-apply

Creates what `platform-plan` lists as missing, in order: the shared project, its APIs, the budget alert, the database switch, the database instance. Everything up to the switch is free; the instance has a fixed cost of `about R$ 50 per month while stopped`. Then it plans again to prove nothing is left.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `confirm=yes` | Proceed without asking. Any other value of `confirm` fails validation. |

## Steps

Show each command before running it. Other skills end with their own `aleogr-result` block: use those blocks only as input, never repeat them. Your answer ends with exactly one block, its own.

1. Read `${CLAUDE_PLUGIN_ROOT}/defaults.json`. If `cloud.provider` is not `gcp`, stop with `failed`: only GCP is implemented. Run no command. Take the same values `platform-plan` takes, `platform.database` and `platform.switch` included.
2. Invoke `aleogr:platform-plan`. Every `gcloud` command in the skills run below uses the command name the plan's tools-check reported (`gcloud` or `gcloud.cmd`). Its `status`:
   - `failed`: stop with `failed` and carry its `pending[].how`.
   - `unchanged`: say `nothing to do` and end with `unchanged`. Run no creating step.
3. Confirmation. Without `confirm=yes`, show the plan table and ask one yes/no question: create the items marked `create` or `update`? When `database instance` is to `create`, the question adds one sentence: the instance has a fixed cost of `about R$ 50 per month while stopped`. If the answer is not a clear yes (or nobody answers), change nothing: end with `pending`, `pending[].how` being `platform-apply confirm=yes`. With `confirm=yes`, go on without asking.
4. Create, in this order (the services come before the budget because the budget commands need the Budget API enabled on the quota project):
   1. `aleogr-cloud-gcp:gcp_environment-create` with `project=<shared.project> environment=<shared.environment> platform=lab mode=apply`. Take `projectId` from its result.
   2. `aleogr-cloud-gcp:gcp_services-enable` with `projectId=<projectId> services=<comma-separated> mode=apply` (by id: a search by labels may not show a project created seconds ago).
   3. `aleogr-cloud-gcp:gcp_budget-alert-setup` with `displayName=<..> amount=<..> currency=<..> thresholds=<comma-separated> quotaProject=<projectId> mode=apply`.
   4. `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-switch-setup` with `projectId=<projectId> instance=<database.instance> region=<cloud.region> timeZone=<switch.timeZone> weeknightStop="<switch.weeknightStop>" weekendStop="<switch.weekendStop>" repository=<switch.repository> mode=apply`. When it created or completed the switch (`created` or `updated`), repeat its `GitHub secrets` section (the three secrets and where to paste them) in the answer and say that pasting them is done once, by hand.
   5. `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-create` with `projectId=<projectId> instance=<database.instance> platform=lab mode=apply confirm=yes version=<database.version> tier=<database.tier> edition=<database.edition> region=<cloud.region> storageGb=<database.storageGb> backupStartUtc=<database.backupStartUtc> retainedBackups=<database.retainedBackups>`.

   `projectId` is the one the create step returned when it ran; when it was skipped (the plan marked the project `none`), it is the plan's `outputs.projectId`. Never guess it and never run a describe only to find it. If it is `null` when the services, budget, switch or instance step is due, stop with `failed`.

   Run each skill in full, including the describe it starts with: the plan's results are stale once an earlier step has changed something. Skip a step whose item the plan marked `none`. The switch comes before the instance: the night jobs must exist before an instance that could be left running does. If a step ends `failed` or `pending`, stop: run no later step, end with that same status, mark that item `blocked` and the later ones with the plan's action, and carry the step's `pending[].how` into `pending`.
5. Run `aleogr:platform-plan projectId=<projectId>` again (without `projectId` if the project still does not exist), in full, even when every step succeeded: its own commands are the proof. Say exactly `nothing to do` only if every action in that last plan is `none`. Otherwise list the leftover items and end with `pending`, `pending[].how` being `platform-apply confirm=yes`.

## Answer

The table of what each step did (item, state, action), the result of the last plan, and the result block.

## Result block

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "platform-apply",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "project", "id": "<projectId>", "name": "shared", "labels": {} }
  ],
  "outputs": {
    "projectId": "<projectId>",
    "items": [
      { "item": "shared project", "state": "created", "action": "none" },
      { "item": "services", "state": "enabled", "action": "none" },
      { "item": "budget alert", "state": "created", "action": "none" },
      { "item": "database switch", "state": "ready", "action": "none" },
      { "item": "database instance", "state": "exists, stopped", "action": "none" }
    ]
  },
  "cost": { "fixed": true, "notes": "about R$ 50 per month while stopped" },
  "pending": []
}
```

- `mode` is `apply`. `status`: `created` when the project, the switch or the instance was created, `updated` when only existing things changed, `unchanged` when there was nothing to do, otherwise `pending` or `failed` as taken from the step that stopped (or the confirmation that was not given). Every step succeeded but the final plan still shows an action other than `none`: `pending`, with each leftover item in `pending`.
- `cost`: `fixed` true with the notes above when the instance exists at the end (the final plan shows it, or this run created it); otherwise `"fixed": false` and `"notes": "everything created here is free"`.
- Each item's `state` and `action` come from the final plan; for a stopped run, the stopped item is `blocked`.
- `outputs.projectId` and `resources` carry the shared project whenever it exists, also when a later step ended `pending` or `failed`; `projectId` is `null` and `resources` empty when it does not exist. No organization, folder or billing identifiers except inside `pending[].how`.
