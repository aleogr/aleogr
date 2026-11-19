---
description: aleogr platform plan. Use to see what the owner's shared platform on Google Cloud (shared project with billing, required APIs, one budget alert, the shared Cloud SQL instance and the switch that stops it at night, and the login of the organization) is missing, comparing the owner's defaults with the real cloud. Changes nothing.
---

# platform-plan

Compares the owner's choices in `${CLAUDE_PLUGIN_ROOT}/defaults.json` with what exists in the cloud, and reads whether the login of the organization is prepared, and prints a table: item, current state, action. The plan itself only reads: running it changes nothing and costs nothing. What it lists is not all free: the database instance has a fixed cost of `about R$ 50 per month while stopped` once `platform-apply` creates it, and the plan says so whenever it lists the instance to create. `platform-apply` runs it first.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Optional. The shared project's id, when the caller already knows it (`platform-apply` passes it). |

Before running any command, check it: `projectId`, when given, has 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. Otherwise end with `status` `failed`, one sentence saying which rule failed, and no command.

## Steps

Show each command before running it. Other skills end with their own `aleogr-result` block: use those blocks only as input, never repeat them. Your answer ends with exactly one block, its own.

1. Read `${CLAUDE_PLUGIN_ROOT}/defaults.json`. If `cloud.provider` is not `gcp`, stop here with `status` `failed`: only GCP is implemented. Run no command. Otherwise take `platform.shared` (`project`, `services`) and `platform.budget` (`displayName`, `amount`, `currency`, `thresholds`), `platform.database` (`instance`) and `platform.switch` (`timeZone`, `weeknightStop`, `weekendStop`, `repository`), and `cloud.region`.
2. Invoke `aleogr:tools-check`. If its `status` is `failed`, stop with `failed`, carry its `fix` into `pending[].how`, and run nothing else. Every `gcloud` command in the skills run below uses the command name tools-check reported (`command`: `gcloud` or `gcloud.cmd`).
3. Invoke `aleogr-cloud-gcp:gcp_environment-describe` with `projectId=<projectId>` when `projectId` was given, otherwise with `project=<shared.project> platform=shared` (the shared project has no environment).
   - `status` `failed`: stop with `failed` and its cause.
   - `exists` false: the shared project, its services, its budget, the database switch and the database instance are all to create, and the login is to prepare. Run no command and invoke no skill for the other five: all need the project, so they are checked after it exists. Go to the answer.
   - Otherwise take `projectId` and `billingLinked`; `projectId` goes into the result as `outputs.projectId`. Then, before step 4, read the login: invoke `aleogr-cloud-gcp:gcp_login-describe` with `projectId=<projectId>`. Its answer and its result block are input, never part of your answer: write nothing of them, take its `status`, `outputs.prepared` and `outputs.readable`, and go on with step 4 at once. It never stops the plan: a describe that ended `failed` makes the row `login` `not checked` (see Items), not a failed plan.
4. Services (project exists): invoke `aleogr-cloud-gcp:gcp_services-enable` with `projectId=<projectId> services=<shared.services, comma-separated> mode=plan`.
5. Budget: never check an item whose prerequisite is not met (project, then billing linked, then services, then budget). Only when `billingLinked` is true and the services result shows `billingbudgets.googleapis.com` already enabled (its `status` is `unchanged`, or the service is in its `alreadyEnabled`), invoke `aleogr-cloud-gcp:gcp_budget-alert-setup` with `displayName=<..> amount=<..> currency=<..> thresholds=<comma-separated> quotaProject=<projectId> mode=plan`. Otherwise run no budget command: the budget commands fail until that API is enabled.
6. Database switch: only when the project exists and the services result shows every service of `shared.services` enabled (`unchanged`), invoke `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-switch-setup` with `projectId=<projectId> instance=<database.instance> region=<cloud.region> timeZone=<switch.timeZone> weeknightStop="<switch.weeknightStop>" weekendStop="<switch.weekendStop>" repository=<switch.repository> mode=plan`. Otherwise run no switch command: its commands fail until the APIs are enabled.
7. Database instance: under the same condition as step 6, invoke `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe` with `projectId=<projectId> instance=<database.instance>`.

If step 4, 5, 6 or 7 returns `failed`, stop and report it: no later item is guessed. A switch result `pending` (step 6: a role, pool or provider exists but differs, which no command fixes) is treated the same way: stop there, run no instance describe, and carry the switch's `pending[].how` (the manual fix).

## Items

| Item | State and action |
|---|---|
| `shared project` | Missing: state `missing`, action `create`. Exists with billing linked: `ready`, `none`. Exists without billing: `billing not linked`, `update`. |
| `services` | Project missing: `not checked, will be checked after the project exists`, `create`. Otherwise from the services result: `unchanged` is `all enabled`, `none`; `would-update` is `missing: <list>`, `update`. |
| `budget alert` | Project missing: `not checked, will be checked after the project exists`, `create`. Billing not linked or the Budget API not enabled (step 5 not run): `not checked, will be checked after the services are enabled`, `create`. Otherwise `would-create` is `missing`, `create`; `would-update` is `differs: <outputs.differs>`, `update`; `unchanged` is `exists`, `none` (when its `outputs.compared` is false, the state is `exists, not compared`). |
| `database switch` | Project missing: `not checked, will be checked after the project exists`, `create`. Services not all enabled (steps 6 and 7 not run): `not checked, will be checked after the services are enabled`, `create`. Otherwise from the switch result: `unchanged` is `ready`, `none`; `would-create` is `missing`, `create`; `would-update` is `incomplete: <outputs.missing>`, `update`; `pending` (a part exists but differs, and only a manual fix changes it) is `incomplete: <outputs.missing>`, `blocked`; `failed` is `unknown`, `blocked`. |
| `database instance` | Same two "not checked" states as `database switch`. Otherwise from the describe result: `exists` false is `missing`, `create`; otherwise `exists, <state>` (`stopped`, `running`, ...), `none`; describe `failed` is `unknown`, `blocked`. A running instance is never a difference: the night jobs stop it. Not checked (the switch step stopped the plan): `not checked, the database switch is blocked`, `blocked`. |
| `login` | Project missing: `not checked, will be checked after the project exists`, `prepare`. Otherwise from the describe result: `prepared` true is `prepared`, `none`; `prepared` false (also when `readable` is false: the read was refused because the role that reads it is not granted yet) is `not prepared`, `prepare`; describe `failed` is `not checked`, `none`. It is listed also when a later step stopped the plan: it was read before. |

The items are always listed in this order: `shared project`, `services`, `budget alert`, `database switch`, `database instance`, `login`. An item whose step `failed` has state `unknown` and action `blocked`.

## Answer

Print the table (item, state, action). Under the table, these lines when they apply, worded as here:

- `database instance` has action `create`: `Cost: the database instance has a fixed cost of about R$ 50 per month while stopped, from its creation.`
- The switch result has entries in `outputs.lastRunFailed`: `The last run of <job names> failed: the night stop may not be working and the instance may have been left running. Check the instance's state and send this output.`
- `database instance` is `exists, running`, `exists, starting` or `exists, creating`: `The database instance is running and is charged by the hour until it is stopped: /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=<projectId> instance=<database.instance>`.
- `login` is `not checked` because its describe failed: `The login of the organization could not be checked; /aleogr-cloud-gcp:gcp_login-describe projectId=<projectId> shows why.`

Then one line: `nothing to do` when every action is `none`, otherwise how many items need changes and that `platform-apply` creates them, and prepares the login as far as a command can when `login` is `prepare` (or, when an item is `blocked`, what blocks it and its fix). Then the result block.

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
    "projectId": null,
    "items": [
      { "item": "shared project", "state": "missing", "action": "create" },
      { "item": "services", "state": "not checked, will be checked after the project exists", "action": "create" },
      { "item": "budget alert", "state": "not checked, will be checked after the project exists", "action": "create" },
      { "item": "database switch", "state": "not checked, will be checked after the project exists", "action": "create" },
      { "item": "database instance", "state": "not checked, will be checked after the project exists", "action": "create" },
      { "item": "login", "state": "not checked, will be checked after the project exists", "action": "prepare" }
    ]
  },
  "cost": { "fixed": false, "notes": "read-only plan" },
  "pending": []
}
```

- `status`: `unchanged` when every action is `none` (a `login` that is `not checked` because its describe failed has action `none`); otherwise `would-create` if the shared project is missing, else `would-update`; `failed` when a step failed, the switch result was `pending` (an item is `blocked`), tools-check failed or the provider is not `gcp`.
- `failed`: `outputs.items` lists what was checked before the stop (when the switch result `pending` stopped the plan, also `database instance` as `not checked, the database switch is blocked`, `blocked`), and `pending[].how` holds the fix or next command the stopped step gave.
- `outputs.projectId` is the shared project's id when it exists, `null` when it does not (as in the example). `resources` lists the shared project (`{ "type": "project", "id": "<projectId>", "name": "<shared.project>", "labels": {} }`) when it exists, and is empty otherwise. When a step `failed` after the project was found, keep `projectId` and `resources`. The block never holds organization, folder or billing identifiers, nor the login's client id.
