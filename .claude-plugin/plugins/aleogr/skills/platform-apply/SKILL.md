---
description: aleogr platform apply. Use to create the free part of the owner's shared platform on Google Cloud (shared project with billing, required APIs, one budget alert), then the shared Cloud SQL instance with the switch that stops it at night, from the owner's defaults, and prepares the login of the organization as far as a command can (the few clicks and the one command left are printed for the owner). Shows the plan and asks for confirmation unless confirm=yes.
---

# platform-apply

Creates what `platform-plan` lists as missing, in order: the shared project, its APIs, the budget alert, the database switch, the database instance; last, it prepares the login of the organization as far as a command can. Everything but the instance is free; the instance has a fixed cost of `about R$ 50 per month while stopped`. Then it plans again to prove nothing is left.

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
   - `unchanged`: write the line `nothing to do` (in exactly those words) and end with `unchanged`, with the `GitHub secrets` section (see "GitHub secrets" below). Run no creating step.
3. Confirmation. Without `confirm=yes`, show the plan table and ask one yes/no question: create the items marked `create` or `update`, and prepare the login when it is marked `prepare` (it grants the account that runs this the role `roles/iap.settingsAdmin` on the organization and enables the IAP API in the shared project; both are free)? When `database instance` is to `create`, the question adds the plan's cost line: `Cost: the database instance has a fixed cost of about R$ 50 per month while stopped, from its creation.` If the answer is not a clear yes (or nobody answers), change nothing: end with `pending`, `pending[].how` being `/aleogr:platform-apply confirm=yes`. With `confirm=yes`, go on without asking.
4. Create, in this order (the services come before the budget because the budget commands need the Budget API enabled on the quota project):
   1. `aleogr-cloud-gcp:gcp_environment-create` with `project=<shared.project> platform=shared mode=apply` (the shared project has no environment). Take `projectId` from its result.
   2. `aleogr-cloud-gcp:gcp_services-enable` with `projectId=<projectId> services=<comma-separated> mode=apply` (by id: a search by labels may not show a project created seconds ago).
   3. `aleogr-cloud-gcp:gcp_budget-alert-setup` with `displayName=<..> amount=<..> currency=<..> thresholds=<comma-separated> quotaProject=<projectId> mode=apply`.
   4. `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-switch-setup` with `projectId=<projectId> instance=<database.instance> region=<cloud.region> timeZone=<switch.timeZone> weeknightStop="<switch.weeknightStop>" weekendStop="<switch.weekendStop>" repository=<switch.repository> mode=apply`. Its `GitHub secrets` section goes into the answer as "GitHub secrets" below says.
   5. Before this step, in every path (asked or `confirm=yes`), write the cost line: `Cost: the database instance has a fixed cost of about R$ 50 per month while stopped, from its creation.` Then invoke `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-create` with `projectId=<projectId> instance=<database.instance> platform=shared mode=apply confirm=yes version=<database.version> tier=<database.tier> edition=<database.edition> region=<cloud.region> storageGb=<database.storageGb> backupStartUtc=<database.backupStartUtc> retainedBackups=<database.retainedBackups> stopJob=aleogr-shared-stop-weeknight`. `stopJob` is the switch's weeknight job (its fixed name; the switch step created it in `cloud.region`, the instance's region): the create skill stops the new instance by running that job, which proves the night stop works. When the step ends `pending` (for example because the job did not stop the instance), it stops the run like any `pending`, and its one-sentence cause and its `pending` items go into the answer as the step wrote them.

   6. Login, last, after every other step: when the plan's `login` has action `prepare` (also when its state is `not checked`: the setup makes its own read), invoke `aleogr-cloud-gcp:gcp_login-setup` with `projectId=<projectId> mode=apply`. It may grant the active account the role `roles/iap.settingsAdmin` on the organization and enable the IAP API in the shared project, both free; it never sees the client's secret. Write nothing of that skill's answer: not its list, not its sentences, not its result block. They are input, never the end of the run; the `Login` section of this skill's answer is the only place the list appears. After it, go on to step 5. Its `status`:
      - `unchanged`: the login is prepared (by this run or by someone else). Nothing to keep.
      - `updated`: it granted the role or enabled the API; the login is not prepared yet (only the owner's clicks and one command are left, or the skill could not read the setting yet). It does not stop the run (see the exception after the rule below). Keep its `outputs.steps`, for the `Login` section of the answer only, and every item of its `pending` (`login`, or `api`) as it gave them, for the answer and the result block; go on to step 5.
      - `pending`: the role and the API were already right and nothing was changed; only the clicks are left. The same as `updated`: it does not stop the run; keep its `outputs.steps` and its `pending` items the same way; go on to step 5.
      - `failed`: stop like any failed step (the rule below); its one sentence goes into the answer as the step wrote it.
      - `would-update` cannot come from `mode=apply`; if it does, treat it as `failed`.

      Never run the command of its list, never fill a value into it and never ask for one. If the owner pastes a client id or a secret into the conversation, do not use, repeat or store it: point to the command of the list instead.

   `projectId` is the one the create step returned when it ran; when it was skipped (the plan marked the project `none`), it is the plan's `outputs.projectId`. Never guess it and never run a describe only to find it. If it is `null` when the services, budget, switch, instance or login step is due, stop with `failed`.

   Run each skill in full, including the describe it starts with: the plan's results are stale once an earlier step has changed something. Skip a step whose item the plan marked `none`. The switch comes before the instance: the night jobs must exist before an instance that could be left running does. If a step ends `failed` or `pending`, stop: run no later step, end with that same status, mark that item `blocked` and the later ones with the plan's action, and carry the step's `pending[].how` into `pending`. The one exception is the login step (6): its `updated` and `pending` never stop the run, because it is the last step and what it leaves is the owner's clicks and one command.
5. Run `aleogr:platform-plan projectId=<projectId>` again (without `projectId` if the project still does not exist), in full, even when every step succeeded: its own commands are the proof. Only if every action in that last plan is `none`, write the line `nothing to do`, in exactly those words (not paraphrased); otherwise never write those words, not even to say that they do not apply. Otherwise list the leftover items and end with `pending`, `pending[].how` being `/aleogr:platform-apply confirm=yes`. The one exception: a `login` that is still `prepare` after the login step ended `updated` or `pending` is not such a leftover. Its items from the login step stand in its place (never a second item for it), and the run ends with the status the other steps give (see Result block).

## GitHub secrets

Whenever the database switch is `ready` at the end of the run (whether this run created it, updated it, or found it ready, and also when a later step stopped the run), the answer has a section titled `GitHub secrets`: the three secrets with their values and where to paste them, repeated from the last `GitHub secrets` section the switch skill printed in this run (its own step, or the switch check of the plan). Say that pasting them is needed once, by hand; running `/aleogr:platform-apply confirm=yes` again shows them again and changes nothing when everything exists. The values never go into the result block. When the switch is not `ready` at the end, there is no such section.

## Login

When the login step gave a list in this run (its `outputs.steps` is not empty), the answer has a section titled `Login`: those lines, once and only here, exactly as the skill gave them (the two addresses, the values of the fields, the one command in a fenced `bash` block of its own, byte for byte), never restated in your own words. When the list's last line does not already say to run `/aleogr:platform-apply confirm=yes` again once the clicks and the command are done, add that one line after it. The list never goes into the result block: `outputs.steps` is kept for this section only. When the login step did not run or gave no list, there is no such section (its one sentence and its `pending` item say what is left).

## Answer

In every path (including `nothing to do`): the table of what each step did (item, state, action), the result of the last plan with the lines it printed under its table (the cost line, the running-instance line, the login line), the `GitHub secrets` section when it applies, the `Login` section when it applies, and the result block. The nested skills' result blocks are never part of the answer, and the answer never ends at one.

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
      { "item": "database instance", "state": "exists, stopped", "action": "none" },
      { "item": "login", "state": "prepared", "action": "none" }
    ]
  },
  "cost": { "fixed": true, "notes": "about R$ 50 per month while stopped" },
  "pending": []
}
```

- `mode` is `apply`. `status`: `created` only when the project, the switch or the instance was created; `updated` when only other things changed (services enabled, the budget alert created, jobs updated, the login's role granted or its API enabled) — a run that created only the budget alert is `updated`; `unchanged` when there was nothing to do, otherwise `pending` or `failed` as taken from the step that stopped (or the confirmation that was not given). Every step succeeded but the final plan still shows an action other than `none`: `pending`, with each leftover item in `pending`. When the login step ended `updated` or `pending`, its `pending` items are in `pending` and the status is the one the other steps give: `created` or `updated` when this run changed something (the login step's `updated` included), `pending` when nothing at all was changed in the run (only the clicks are left). `unchanged` and the line `nothing to do` only when the login is `prepared` too.
- `cost`: `fixed` true with the notes above when the instance exists at the end (the final plan shows it, or this run created it); otherwise `"fixed": false` and `"notes": "everything created here is free"`.
- The result block holds no line of the login's list: no console address and no command (the `pending` item `login` is the setup's own, as it gave it).
- Each item's `state` and `action` come from the final plan; for a stopped run, the stopped item is `blocked`.
- `outputs.projectId` and `resources` carry the shared project whenever it exists, also when a later step ended `pending` or `failed`; `projectId` is `null` and `resources` empty when it does not exist. No organization, folder or billing identifiers except inside `pending[].how`.
