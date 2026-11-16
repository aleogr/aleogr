---
description: aleogr platform plan. Use to see what the free part of the owner's lab platform on Google Cloud (shared project with billing, required APIs, one budget alert) is missing, comparing the owner's defaults with the real cloud. Changes nothing; takes no arguments.
---

# platform-plan

Compares the owner's choices in `${CLAUDE_PLUGIN_ROOT}/defaults.json` with what exists in the cloud and prints a table: item, current state, action. It changes nothing and has no cost. `platform-apply` runs it first.

## Arguments

None.

## Steps

Show each command before running it. Other skills end with their own `aleogr-result` block: use those blocks only as input, never repeat them. Your answer ends with exactly one block, its own.

1. Read `${CLAUDE_PLUGIN_ROOT}/defaults.json`. If `cloud.provider` is not `gcp`, stop here with `status` `failed`: only GCP is implemented. Run no command. Otherwise take `platform.shared` (`project`, `environment`, `services`) and `platform.budget` (`displayName`, `amount`, `currency`, `thresholds`).
2. Invoke `aleogr:tools-check`. If its `status` is `failed`, stop with `failed`, carry its `fix` into `pending[].how`, and run nothing else.
3. Invoke `aleogr-cloud-gcp:gcp_environment-describe` with `project=<shared.project> environment=<shared.environment>`.
   - `status` `failed`: stop with `failed` and its cause.
   - `exists` false: the shared project, its services and its budget are all to create. Run no command for the services and the budget: both need the project, so they are checked after it exists. Go to the answer.
   - Otherwise take `projectId` and `billingLinked`.
4. Services (project exists): invoke `aleogr-cloud-gcp:gcp_services-enable` with `project=<shared.project> environment=<shared.environment> services=<shared.services, comma-separated> mode=plan`.
5. Budget (project exists): invoke `aleogr-cloud-gcp:gcp_budget-alert-setup` with `displayName=<..> amount=<..> currency=<..> thresholds=<comma-separated> quotaProject=<projectId> mode=plan`.

If step 4 or 5 returns `failed`, stop and report it: no later item is guessed.

## Items

| Item | State and action |
|---|---|
| `shared project` | Missing: state `missing`, action `create`. Exists with billing linked: `ready`, `none`. Exists without billing: `billing not linked`, `update`. |
| `services` | Project missing: `not checked, will be checked after the project exists`, `create`. Otherwise from the services result: `unchanged` is `all enabled`, `none`; `would-update` is `missing: <list>`, `update`. |
| `budget alert` | Project missing: `not checked, will be checked after the project exists`, `create`. Otherwise `would-create` is `missing`, `create`; `unchanged` is `exists`, `none`. |

An item whose step `failed` has state `unknown` and action `blocked`.

## Answer

Print the table (item, state, action). Then one line: `nothing to do` when every action is `none`, otherwise how many items need changes and that `platform-apply` creates them. Then the result block.

## Result block

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "platform-plan",
  "mode": "plan",
  "status": "would-create",
  "resources": [],
  "outputs": {
    "items": [
      { "item": "shared project", "state": "missing", "action": "create" },
      { "item": "services", "state": "not checked, will be checked after the project exists", "action": "create" },
      { "item": "budget alert", "state": "not checked, will be checked after the project exists", "action": "create" }
    ]
  },
  "cost": { "fixed": false, "notes": "read-only plan" },
  "pending": []
}
```

- `status`: `unchanged` when every action is `none`; otherwise `would-create` if the shared project is missing, else `would-update`; `failed` when a step failed or tools-check failed or the provider is not `gcp`.
- `failed`: `outputs.items` lists what was checked before the stop, and `pending[].how` holds the fix or next command the stopped step gave.
- `resources` is empty. The block never holds organization, folder or billing identifiers.
