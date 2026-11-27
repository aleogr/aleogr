---
description: Google Cloud SQL (gcp-cloud-sql) database create. Use to make an aleogr project's database for one environment on the shared platform's Cloud SQL instance when it is missing. Never starts the instance: on a stopped one it ends pending and names the command that starts it. Idempotent; plan by default. No cost of its own.
---

# gcp-cloud-sql_database-create

Makes the database `<project>_<environment>` on the shared Cloud SQL instance when it is missing, with the instance's defaults (no character set, no collation given). A database that exists is left alone. It creates no user and no password, and grants nothing: `gcp-cloud-sql_access-grant` makes each component's user.

It never starts, stops or changes the instance. A database is made through the Cloud SQL Admin API, which needs the instance running, and what that API answers on a stopped instance is not documented: so on an instance that is not running this skill runs no other command and ends `pending`, naming what to do by the state: on a stopped one, `/aleogr:project-apply confirm=yes`, which starts the instance when something must be made in it. A database costs nothing of its own: only the instance's running hours cost.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `sharedProjectId=<id>` | The GCP project of the shared platform, which holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |
| `project=<name>` | The aleogr project name. |
| `environment=<name>` | The environment: `dev`, `hom` or `prd`. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check every argument, and never ask for anything. Each argument that is missing or breaks its rule gives its one sentence below, word for word, one per line; when there is at least one, the skill ends with the result block, `status` `failed`, those sentences and no `gcloud` call.

- A missing required argument: `<argument> is missing.`
- `sharedProjectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `sharedProjectId is not a GCP project id.`
- `instance` has 1 to 60 characters of `a-z`, `0-9` and `-` and starts with a letter. Otherwise: `instance must have 1 to 60 lowercase letters, digits and hyphens, starting with a letter.`
- `project` has 1 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.`
- `environment` is `dev`, `hom` or `prd`. Otherwise: `environment must be dev, hom or prd.`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

## Names

- `<database>` is `<project>_<environment>` with every `-` of the project's name written `_` (`my-app` and `dev` give `my_app_dev`; `demo` and `dev` give `demo_dev`). It has at most 18 characters (`project` has at most 14, `environment` 3), so it always fits PostgreSQL's limit of 63 and needs no check of its own.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. A value written in double quotes below keeps its quotes. The text of a non-zero exit is never read to decide and is never quoted: repeat no word of `gcloud`'s answer (not even its status words, codes or reasons). Whether a database exists is decided only by the list of step 3 or 5, never by the text of a failed create (the text Cloud SQL gives for a database that already exists is not documented). Each failure, and each other sentence written in backquotes below, is said word for word, and nothing else about a failure. This skill never runs `gcloud sql instances patch` or any other command that starts, stops or changes the instance.

1. The instance (both modes), with the read and the state rule of `gcp-cloud-sql_instance-describe`, copied here (its backups are not read):

   ```
   gcloud sql instances describe <instance> --project=<sharedProjectId> --format=json
   ```

   Any non-zero exit: say `The instance <instance> of the shared project could not be read; nothing was changed. Check that it exists and that the active gcloud account may read it.` and end with `failed`. Exit 0: read the state from `settings.activationPolicy` and `state` with this table:

   | `settings.activationPolicy` | `state` | Skill's `state` |
   |---|---|---|
   | `NEVER` | any | `stopped` |
   | `ALWAYS` | `RUNNABLE` | `running`, or `starting` while an `UPDATE` operation is unfinished (below) |
   | `ALWAYS` | `PENDING_CREATE` | `creating` |
   | `ALWAYS` | anything else | `starting` |
   | any other value, or absent | any | `unknown` |

   Only when it gave activation policy `ALWAYS` with state `RUNNABLE`, the pending operations:

   ```
   gcloud sql operations list --instance=<instance> --project=<sharedProjectId> --filter="status!=DONE" --limit=10 --format="value(operationType,status)"
   ```

   Cloud SQL shows an instance as `RUNNABLE` as soon as a start is accepted, minutes before it accepts connections; the unfinished operation is what tells the two apart. If any printed line has the operation type `UPDATE`, the state is `starting`; otherwise it is `running`. If this command alone fails, keep `running`, say in one sentence that pending operations could not be checked, and go on.

2. The state is not `running` (both modes): run nothing else. End with `pending` and the item `{ "item": "instance", "reason": "The shared instance is <state>: the database is made only while it runs.", "how": "<how>" }`, with `<how>` and the answer's sentence by the state:

   | State | `how` of the item `instance` | The answer's sentence |
   |---|---|---|
   | `stopped` | `/aleogr:project-apply confirm=yes` | `The shared instance is stopped: the database is made only while it runs; /aleogr:project-apply confirm=yes starts it.` |
   | `starting` or `creating` | `Wait a few minutes, then /aleogr:project-plan.` | `The shared instance is <state>: the database is made once it runs. Wait a few minutes, then run /aleogr:project-plan.` |
   | `unknown` | `/aleogr:platform-plan` | `The state of the shared instance is not one this skill knows: the database is made only while it runs. Run /aleogr:platform-plan.` |

   Nothing was changed.

3. The state is `running`: the databases (both modes):

   ```
   gcloud sql databases list --instance=<instance> --project=<sharedProjectId> --format="value(name)"
   ```

   Any non-zero exit: say `The databases of the instance <instance> could not be read although it is running; nothing was changed.` and end with `failed`. Exit 0: the database exists when a printed line is exactly `<database>`. It exists: end with `unchanged`. `plan` ends here, changing nothing: `would-create` when it is missing.

4. `apply`, the database is missing: create it, with these flags and nothing else (no `--async`, so the command waits for its operation; no `--charset`, no `--collation`):

   ```
   gcloud sql databases create <database> --instance=<instance> --project=<sharedProjectId> --quiet
   ```

   The create is run once in a run, never again, whatever its exit.

5. Verify, after the create whatever its exit, with the command of step 3, once, alone. A non-zero exit of the create does not prove that nothing was made: the list decides.

   - Listed, the create exited 0: `created`.
   - Listed, the create failed: the database exists (made by this run, or by someone else in the meantime): say `The command that creates the database <database> failed, but the database exists.` and end with `created`.
   - Not listed, the create exited 0: say `The database <database> was not found after its creation. Run this same skill again to check.` and end with `failed`.
   - Not listed, the create failed: say `The database <database> could not be created on the instance <instance>.` and end with `failed`.
   - The list fails, the create exited 0: `created`, with the `pending` item `{ "item": "database", "reason": "The database could not be read after its creation.", "how": "/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_database-create sharedProjectId=<sharedProjectId> instance=<instance> project=<project> environment=<environment> mode=apply" }`.
   - The list fails, the create failed: say `The command that creates the database <database> failed and the databases could not be read: it may exist. Run this same skill again to check.` and end with `failed`.

Then answer in a few lines: the instance's state, the database's name and whether it exists, was created by this run, or would be (plan); the sentence of each failure or `pending` said above; and the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "database-create",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "instance", "id": "<sharedProjectId>/<instance>", "name": "<instance>", "labels": {} },
    { "type": "database", "id": "<sharedProjectId>/<instance>/<database>", "name": "<database>", "labels": {} }
  ],
  "outputs": {
    "instanceState": "running",
    "database": "<database>",
    "exists": true
  },
  "cost": { "fixed": false, "notes": "a database adds no cost of its own; the instance costs by the hour while it runs" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create` (plan), `created`, `unchanged`, `pending`, `failed`. `pending` means nothing was changed.
- `outputs.instanceState` is the skill's state of step 1 (`null` when it was not read).
- `outputs.database` is `<database>` as computed, also on a failure, when `project` and `environment` are valid (`null` otherwise).
- `outputs.exists` is `true` or `false` as of the last list, or `null` when no list ran or the last one failed.
- `resources` lists the instance when step 1 read it, and the database when the last list showed it.
- `failed` from validation or step 1: `resources` is empty and `outputs` is `{ "instanceState": null, "database": <as above>, "exists": null }`.
- `pending` holds the item `instance` of step 2 or the item `database` of step 5; it is empty otherwise.
- The result block holds no e-mail at all.
