---
description: Google Cloud SQL (gcp-cloud-sql) access grant. Use to let one component's service account reach its database on the shared platform's Cloud SQL instance with no password - by granting it, as `serviceAccount:<e-mail>` only, the two connection roles (`roles/cloudsql.client`, `roles/cloudsql.instanceUser`) on the shared project, and by making it an IAM service-account user of the instance. Never a password, never another user type, never a wider role; never starts the instance. Idempotent; plan by default. No cost.
---

# gcp-cloud-sql_access-grant

Lets one service account connect to the shared Cloud SQL instance as itself, with IAM database authentication and no password:

- it grants `serviceAccount:<account>` the roles `roles/cloudsql.client` (connect) and `roles/cloudsql.instanceUser` (log in) on the shared project, each when missing, without a condition. Cloud SQL grants these roles on a project, not on an instance; they let the account connect and log in, and nothing more.
- it makes the account a user of the instance, of the IAM service-account type, when it is missing.

It never creates a user with a password, never generates, reads or writes a password, never creates a user of any other type, never gives the user a database role, and never grants any other role or any role to another member. It removes nothing. It never starts, stops or changes the instance: a user is made through the Cloud SQL Admin API, which needs the instance running, so on an instance that is not running it grants the roles (they live on the project) and ends with the item `instance`, naming what to do by the state (on a stopped one, `/aleogr:project-apply confirm=yes`). There is no cost: roles and users cost nothing.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `sharedProjectId=<id>` | The GCP project of the shared platform, which holds the instance. |
| `instance=<name>` | The Cloud SQL instance name (the shared platform uses `aleogr-shared`). |
| `account=<e-mail>` | The component's service account (`<project>-<component>@<project id>.iam.gserviceaccount.com`). |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check every argument, and never ask for anything. Each argument that is missing or breaks its rule gives its one sentence below, one per line; when there is at least one, the skill ends with the result block, `status` `failed`, those sentences and no `gcloud` call.

- A missing required argument: `<argument> is missing.`
- `sharedProjectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `sharedProjectId is not a GCP project id.`
- `instance` has 1 to 60 characters of `a-z`, `0-9` and `-` and starts with a letter. Otherwise: `instance must have 1 to 60 lowercase letters, digits and hyphens, starting with a letter.`
- `account` matches `^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$`: a service account's address, all lowercase, with no prefix such as `serviceAccount:`, no space and no `,`. Otherwise: `account must be the address of a service account (<id>@<project id>.iam.gserviceaccount.com), with no prefix.` An address that passes is still only ever the member `serviceAccount:<account>`.
- `<user>` (see "Names") has at most 63 characters. Otherwise: `The database user of account would have <length> characters: PostgreSQL allows 63.`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

## Names

- `<user>` is `<account>` without the ending `.gserviceaccount.com` (`<id>@<project id>.iam`): the name Cloud SQL gives an IAM service-account user on PostgreSQL, whose limit for a user's name is 63 characters.
- `<member>` is `serviceAccount:<account>`, always with this prefix. It is used only as the `--member` of the commands of step 5.
- Neither `<account>`, `<user>` nor `<member>` is ever written in the result block, not even inside a `how`; the answer's text may name the account.
- The two roles are `roles/cloudsql.client` and `roles/cloudsql.instanceUser`, always in this order, and no other.
- In the shared project's policy, the account holds a role when a binding whose `role` is exactly that role lists `<member>` in `members` (compared without regard to case), **with or without a `condition`**: a binding narrowed by a condition counts as granted, so narrowing it later never makes it missing. A binding of another role does not count. A role held only under a condition counts as held: when that condition does not cover the shared instance, the connection is refused, and this skill does not see it.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. A value written in double quotes below keeps its quotes. The text of a non-zero exit is never quoted: repeat no word of `gcloud`'s answer (not even its status words, codes or reasons). It is read to decide only once, in the poll of step 5; everything else is decided by the instance's state and by a read after a failed command, never by an error's text (the texts Cloud SQL gives for a user that already exists, or on a stopped instance, are not documented). Each failure is said with its sentence below and nothing else about it. This skill never runs `gcloud sql instances patch` or any other command that starts, stops or changes the instance.

1. The instance (both modes), with the read and the state rule of `gcp-cloud-sql_instance-describe`, copied here (its backups are not read):

   ```
   gcloud sql instances describe <instance> --project=<sharedProjectId> --format=json
   ```

   Any non-zero exit: say `The instance <instance> in <sharedProjectId> could not be read; nothing was changed. Check that it exists and that the active gcloud account may read it.` and end with `failed`. Exit 0: read the state from `settings.activationPolicy` and `state` with this table:

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

2. The shared project's policy (both modes, whatever the instance's state):

   ```
   gcloud projects get-iam-policy <sharedProjectId> --format=json
   ```

   Any non-zero exit: say `The access policy of the shared project <sharedProjectId> could not be read; nothing was changed. Check that the active gcloud account may read it.` and end with `failed`. Exit 0: decide `client` and `instanceUser` as "Names" says. Each role the account does not hold is missing.

3. Only when the state is `running`, the users of the instance (both modes):

   ```
   gcloud sql users list --instance=<instance> --project=<sharedProjectId> --format="value(name)"
   ```

   Exit 0: `user` is true when a printed line is exactly `<user>`, false otherwise. Any non-zero exit: say `The users of the instance <instance> could not be read although it is running; nothing was changed.` and end with `failed`. Any other state: the command does not run and `user` is `null` (not read); this is not a failure.

4. `plan` ends here, changing nothing. `granted` names the missing roles (those that would be granted). The status is `would-update` when a role is missing or `user` is false; otherwise `pending` when the state is not `running`; otherwise `unchanged`. When the state is not `running`, the result carries the item `instance` (below), in `plan` as in `apply`.

5. `apply`, the roles: for each missing role, in the order of "Names", grant it on the shared project, with every flag below and nothing else:

   ```
   gcloud projects add-iam-policy-binding <sharedProjectId> --member="serviceAccount:<account>" --role="<role>" --condition=None --quiet
   ```

   - Only on the shared project `<sharedProjectId>`, only these two roles, only to `serviceAccount:<account>`, always with `--condition=None` (it adds a binding without a condition, and `gcloud` refuses a grant without it on a policy that holds any conditional binding). Never run `set-iam-policy`, never grant on another project, a service, a service account or the instance, never pass a member other than `serviceAccount:<account>`.
   - The account may have been created moments before, in the project of its component, and not yet be visible to IAM. This skill cannot know whether it was: a non-zero exit whose text says the account does not exist (`does not exist` or `NOT_FOUND`) is taken as the refusal that waiting cures, and the grant is polled: wait 30 seconds, then run the same grant command again, alone; while it is refused that same way, wait and try again; at most 10 tries in all for that role, the first one included (so at most 9 waits, about 5 minutes). The budget is per role: in the worst case there are two polls, one for each role. A refusal of any other kind (a permission denied included) is never waited on. Any other non-zero exit, on any try, ends the poll at once, with no further wait and no further try. The tenth refusal is a failure. The answer says only that the grant was refused, and after how many tries: it never says that the account does not exist, and repeats none of the refusal's words (`does not exist`, `Service account`, `NOT_FOUND`, `PERMISSION_DENIED` or any other). This is the one decision made by an error's text, and it is safe either way: a wrong reading either waits a bounded time or ends with a sentence that a second run repairs.
   - The wait is the command `sleep 30`, the one command of this skill that is not `gcloud`. Show it, then run it with the Bash tool in the background (`run_in_background`: Claude Code refuses a `sleep` in the foreground), run nothing else while it runs, and when its completion notice arrives go on with the next try in this same run. A pending wait is part of the run: while one is pending, never end the answer, never give the result block, and never tell the owner to run anything. A wait that cannot be run, or whose completion notice never comes, counts as the refusal that ends the poll: the skill ends as after the tenth refusal, never loops and never leaves the answer unfinished.
   - A refused grant (any non-zero exit that is not polled, or the tenth refusal) has the sentence `The account could not be given the role <role> on the shared project <sharedProjectId>. Check that the active gcloud account may change who has access to it.` The run then takes one path: no later grant, never the user of step 6, and the status is `failed`. When this run granted nothing before it, nothing was changed: end at once. When this run granted the other role before it, what was made stays (nothing is removed): read the policy back once, alone, with the command of step 2, decide `client` and `instanceUser` from it (from step 2's read when this one fails), report in the answer which roles the account now holds, and end; the result carries the item `access`.

   When every grant of this step succeeded, read the policy back, once, alone, with the command of step 2, and decide `client` and `instanceUser` again. A role granted by this run that is still not held, or a read that fails, gives the item `access`, and the answer says what could not be confirmed.

6. `apply`, the user: only when the state is `running`, `user` is false, and no grant of step 5 was refused:

   ```
   gcloud sql users create <user> --instance=<instance> --project=<sharedProjectId> --type=cloud_iam_service_account --quiet
   ```

   With every flag above and nothing else: the type is always `cloud_iam_service_account`; never `--password`, `--database-roles`, `--host` or any other flag, and never the address with `.gserviceaccount.com` as the name. The create is run once in a run, never again, whatever its exit. Then, whatever its exit, read the users once, alone, with the command of step 3: a non-zero exit of the create does not prove that nothing was made, and the list decides.

   - Listed: `user` is true and `userCreated` is true. When the create failed, say `The command that creates the database user of the account failed, but the user exists.`
   - Not listed: `user` is false; say `The database user of the account could not be created on the instance <instance>.`; the result carries the item `access`.
   - The list fails: `user` is `null`. When the create exited 0, `userCreated` is true and the result carries the item `access` (the user could not be confirmed); when it failed, say `The command that creates the database user of the account failed and the users could not be read: it may exist. Run this same skill again to check.` and the result carries the item `access`.

7. The items. When the state is not `running`, the item `{ "item": "instance", "reason": "The shared instance is <state>: the database user is made only while it runs.", "how": "<how>" }`, with `<how>` and the answer's sentence by the state:

   | State | `how` of the item `instance` | The answer's sentence |
   |---|---|---|
   | `stopped` | `/aleogr:project-apply confirm=yes` | `The shared instance is stopped: the database user is made only while it runs; /aleogr:project-apply confirm=yes starts it.` |
   | `starting` or `creating` | `Wait a few minutes, then /aleogr:project-plan.` | `The shared instance is <state>: the database user is made once it runs. Wait a few minutes, then run /aleogr:project-plan.` |
   | `unknown` | `/aleogr:platform-plan` | `The state of the shared instance is not one this skill knows: the database user is made only while it runs. Run /aleogr:platform-plan.` |

   The item `access`, once however many causes, is `{ "item": "access", "reason": "<one sentence, no raw error text, no e-mail>", "how": "/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_access-grant sharedProjectId=<sharedProjectId> instance=<instance> account=<e-mail> mode=apply" }`, where `account=<e-mail>` is written exactly so, as a placeholder, never with the address.

8. Status of `apply`: `failed` when a grant of step 5 was refused, or the user was not listed after its create, or the users could not be read after a create that failed (whatever this run granted before: what was made stays, and the item `access` names the run that finishes it); otherwise `updated` when this run granted a role or created the user (even when `pending` has items); otherwise `pending` when the state is not `running` (nothing was changed, the user is not known); otherwise `unchanged` (both roles held and the user exists).

Then answer in a few lines: the instance's state; for the account, which may be named, each role it already held, was granted by this run or would be (plan), and whether it is a user of the instance, was made one, would be, or was not read; the sentence of each failure said above; that the account connects with no password, as itself; and the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "access-grant",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "instance", "id": "<sharedProjectId>/<instance>", "name": "<instance>", "labels": {} }
  ],
  "outputs": {
    "instanceState": "running",
    "user": true,
    "client": true,
    "instanceUser": true,
    "granted": ["roles/cloudsql.client", "roles/cloudsql.instanceUser"],
    "userCreated": true
  },
  "cost": { "fixed": false, "notes": "roles and database users have no cost" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-update` (plan), `updated`, `unchanged`, `pending`, `failed`. `pending` means nothing was changed.
- `outputs.instanceState` is the skill's state of step 1 (`null` when it was not read).
- `outputs.user` is `true`, `false` or `null` (not read), as of the last read; `outputs.client` and `outputs.instanceUser` are `true` or `false` as of the last read of the policy (`false` when it was not read).
- `outputs.granted` names the roles this run granted (in `apply`) or would grant (in `plan`), in the order of "Names", written on one line; `[]` when none.
- `outputs.userCreated` is `true` when this run created the user; `false` otherwise, always in `plan`.
- `resources` lists the instance when step 1 read it.
- `failed` from validation or step 1: `resources` is empty and `outputs` is `{ "instanceState": null, "user": null, "client": false, "instanceUser": false, "granted": [], "userCreated": false }`.
- `pending` holds the items of step 7; it is empty otherwise.
- The result block holds no e-mail at all: never `<account>`, `<user>`, `<member>` or any member of the policy, not even inside a `how`.
