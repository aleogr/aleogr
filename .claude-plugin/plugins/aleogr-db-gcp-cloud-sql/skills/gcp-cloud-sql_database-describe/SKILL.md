---
description: Google Cloud SQL (gcp-cloud-sql) database describe. Use to learn, for an aleogr project and environment, whether the shared platform's Cloud SQL instance is running, whether the project's database exists on it, which of the given service accounts are its users, and whether each holds the two connection roles on the shared project. Read-only; a stopped or starting instance is a normal state, not a failure. The plan of a project calls it.
---

# gcp-cloud-sql_database-describe

Reads, for one aleogr project and environment, what its database on the shared Cloud SQL instance needs: the instance's state, the database `<project>_<environment>`, and, for each given service account, whether it is a user of the instance and whether it holds `roles/cloudsql.client` and `roles/cloudsql.instanceUser` on the shared project. It never creates, changes, starts, stops or deletes anything and has no `mode`.

A database and a user can only be read through the Cloud SQL Admin API while the instance runs. When the instance is stopped or starting, this skill reads the instance and the roles, marks the database and the users `not read` (`null`), and ends `unchanged`: a stopped instance is the shared platform's normal state, never a failure. What the Admin API answers on a stopped instance is not documented, so this skill never asks it: it decides by the instance's state alone.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required.

| Argument | Meaning |
|---|---|
| `sharedProjectId=<id>` | The GCP project of the shared platform, which holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |
| `project=<name>` | The aleogr project name. |
| `environment=<name>` | The environment: `dev`, `hom` or `prd`. |
| `accounts=<e-mail>[,<e-mail>…]` | The service accounts of the project's components that use the database, in the declaration's order. |

## Validate first

Before any command, check every argument, and never ask for anything. Each argument that is missing or breaks its rule gives its one sentence below, word for word, one per line; when there is at least one, the skill ends with the result block, `status` `failed`, those sentences and no `gcloud` call.

- A missing argument: `<argument> is missing.`
- `sharedProjectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `sharedProjectId is not a GCP project id.`
- `instance` has 1 to 60 characters of `a-z`, `0-9` and `-` and starts with a letter. Otherwise: `instance must have 1 to 60 lowercase letters, digits and hyphens, starting with a letter.`
- `project` has 1 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.`
- `environment` is `dev`, `hom` or `prd`. Otherwise: `environment must be dev, hom or prd.`
- `accounts` holds one or more entries separated by `,`, with no space and no empty entry. Each entry matches `^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$` (a service account's address, all lowercase, with no prefix such as `serviceAccount:`). Otherwise, for each entry that breaks it: `Entry <n> of accounts is not the address of a service account (<id>@<project id>.iam.gserviceaccount.com).`, with `<n>` its position from 1. An entry given twice: `Entry <n> of accounts is given twice.` An entry whose `<user>` (see "Names") has more than 63 characters: `The database user of entry <n> of accounts would have <length> characters: PostgreSQL allows 63.`

## Names

- `<database>` is `<project>_<environment>` with every `-` of the project's name written `_` (`my-app` and `dev` give `my_app_dev`; `demo` and `dev` give `demo_dev`). It has at most 18 characters (`project` has at most 14, `environment` 3), so it always fits PostgreSQL's limit of 63.
- For each entry `<account>` of `accounts`, its `<user>` is `<account>` without the ending `.gserviceaccount.com` (`<id>@<project id>.iam`): the name Cloud SQL gives an IAM service-account user on PostgreSQL. Its `<member>` is `serviceAccount:<account>`. Neither is ever written in the result block.
- In the shared project's policy, an account holds a role when a binding whose `role` is exactly that role lists its `<member>` in `members` (compared without regard to case), **with or without a `condition`**: a binding narrowed by a condition still counts as granted. A binding of another role does not count. A role held only under a condition counts as held: when that condition does not cover the shared instance, the connection is refused, and this skill does not see it.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. A value written in double quotes below keeps its quotes. The text of a non-zero exit is never read to decide and is never quoted: repeat no word of `gcloud`'s answer (not even its status words, codes or reasons). Each failure, and each other sentence written in backquotes below, is said word for word, and nothing else about a failure. This skill never runs `gcloud sql instances patch` or any other command that starts, stops or changes the instance.

1. The instance, with the read and the state rule of `gcp-cloud-sql_instance-describe`, copied here (its backups are not read):

   ```
   gcloud sql instances describe <instance> --project=<sharedProjectId> --format=json
   ```

   Any non-zero exit: say `The instance <instance> of the shared project could not be read; nothing was changed. Check that it exists and that the active gcloud account may read it.` and end with `failed`. Exit 0: read the state from `settings.activationPolicy` and `state` with the table under "The instance's state".

   Only when it gave activation policy `ALWAYS` with state `RUNNABLE`, the pending operations:

   ```
   gcloud sql operations list --instance=<instance> --project=<sharedProjectId> --filter="status!=DONE" --limit=10 --format="value(operationType,status)"
   ```

   Cloud SQL shows an instance as `RUNNABLE` as soon as a start is accepted, minutes before it accepts connections; the unfinished operation is what tells the two apart. If any printed line has the operation type `UPDATE`, the state is `starting`; otherwise it is `running`. If this command alone fails, keep `running`, say in one sentence that pending operations could not be checked, and go on.

2. The shared project's policy (whatever the instance's state):

   ```
   gcloud projects get-iam-policy <sharedProjectId> --format=json
   ```

   Any non-zero exit: say `The access policy of the shared project could not be read; nothing was changed. Check that the active gcloud account may read it.` and end with `failed`. Exit 0: decide, for each account, `client` (it holds `roles/cloudsql.client`) and `instanceUser` (it holds `roles/cloudsql.instanceUser`), as "Names" says.

3. Only when the state is `running`, the databases and the users of the instance, each command alone:

   ```
   gcloud sql databases list --instance=<instance> --project=<sharedProjectId> --format="value(name)"
   gcloud sql users list --instance=<instance> --project=<sharedProjectId> --format="value(name)"
   ```

   - Both exit 0: `databaseExists` is true when a printed line is exactly `<database>`; for each account, `user` is true when a printed line of the users is exactly its `<user>`. `read` is true.
   - Any non-zero exit of either: say `The databases and users of the instance <instance> could not be read although it is running; nothing was changed.` and end with `failed`.
   - Any other state (`stopped`, `starting`, `creating`, `unknown`): neither command runs; `databaseExists` and each `user` are `null` (not read), and `read` is false. This is not a failure.

Then answer in a few lines: the instance's state; the database's name and whether it exists, or, when the instance is not running, the sentence `The database and its users were not read: the shared instance is <state>.`, word for word; for each account, which may be named in the text, whether it is a user (or not read) and which of the two roles it holds; and the result block. When the state is `unknown`, the answer reports the raw `settings.activationPolicy` value (or that it is absent).

## The instance's state

The table of `gcp-cloud-sql_instance-describe`, unchanged:

| `settings.activationPolicy` | `state` | Skill's `state` |
|---|---|---|
| `NEVER` | any | `stopped` |
| `ALWAYS` | `RUNNABLE` | `running`, or `starting` while an `UPDATE` operation is unfinished (step 1) |
| `ALWAYS` | `PENDING_CREATE` | `creating` |
| `ALWAYS` | anything else | `starting` |
| any other value, or absent | any | `unknown` |

Only `running` lets the databases and the users be read.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "database-describe",
  "mode": "plan",
  "status": "unchanged",
  "resources": [
    { "type": "instance", "id": "<sharedProjectId>/<instance>", "name": "<instance>", "labels": {} }
  ],
  "outputs": {
    "instanceState": "running",
    "database": "<database>",
    "databaseExists": true,
    "users": [
      { "account": 1, "user": true, "client": true, "instanceUser": true },
      { "account": 2, "user": false, "client": true, "instanceUser": false }
    ],
    "read": true
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `mode` is always `plan`: the skill only reads. `status` is `unchanged` whenever steps 1 and 2 succeeded and step 3 either succeeded or did not run; `failed` otherwise.
- `outputs.instanceState` is the skill's state of "The instance's state" (`null` when step 1 failed or was not run).
- `outputs.database` is `<database>` as computed, also on a failure, when `project` and `environment` are valid (`null` otherwise).
- `outputs.users` has one item per entry of `accounts`, in their order, each written on one line as above: `account` is the entry's position from 1 (never its address), `user` is `true`, `false` or `null` (not read), `client` and `instanceUser` are `true` or `false`. It is `[]` when step 2 did not succeed.
- `outputs.databaseExists` is `true`, `false` or `null` (not read); `outputs.read` is `true` only when step 3 ran and succeeded.
- `failed` from validation or step 1: `resources` is empty and `outputs` is `{ "instanceState": null, "database": <as above>, "databaseExists": null, "users": [], "read": false }`. `failed` from step 2 or 3: `resources` lists the instance, `instanceState` is as read, and what was read before the failure is kept.
- `pending` is always `[]`.
- The result block holds no e-mail at all: no account's address, no `<user>`, no `<member>`, no member of the policy.
