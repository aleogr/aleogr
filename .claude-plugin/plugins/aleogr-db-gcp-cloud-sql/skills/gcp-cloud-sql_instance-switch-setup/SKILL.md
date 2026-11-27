---
description: Google Cloud SQL (gcp-cloud-sql) instance switch setup. Use to create, in the shared platform's Google Cloud project, what starts and stops the shared instance without the owner - a custom role, a service account, its grants, a GitHub Actions workload identity federation pool and provider, and two Cloud Scheduler jobs that stop the instance at night. Idempotent; plan by default.
---

# gcp-cloud-sql_instance-switch-setup

Creates the "switch": a custom role (`aleogrSharedSqlSwitch`) that can only get and update Cloud SQL instances, a service account (`aleogr-shared-sql-switch`) that holds it, a workload identity federation pool (`github`) and provider (`aleogr`) that let GitHub Actions of one repository, on `main`, act as that account, and two Cloud Scheduler jobs (`aleogr-shared-stop-weeknight`, `aleogr-shared-stop-weekend`) that stop the instance at night. Without the jobs an instance left running would keep running all night, so `ready` is true only when every part exists and matches. There is no fixed cost beyond the instance's own (about R$ 50 per month while stopped); the jobs are free at this volume.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`. Values with a space are double-quoted.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The shared platform's GCP project. |
| `instance=<name>` | The instance the jobs stop (the shared platform uses `aleogr-shared`). |
| `region=<region>` | The Cloud Scheduler location, for example `southamerica-east1`. |
| `timeZone=<tz>` | The time zone of both schedules, for example `America/Sao_Paulo`. |
| `weeknightStop="<cron>"` | Cron schedule of the weeknight stop, for example `"30 22 * * 0-4"`. |
| `weekendStop="<cron>"` | Cron schedule of the weekend stop. |
| `repository=<owner>/<repo>` | The GitHub repository allowed to act as the switch account. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check the arguments, and never ask for anything. A missing required argument ends the skill with the result block, `status` `failed`, the one sentence `<argument> is missing.` and no `gcloud` call. Any other failure ends the skill with the result block, `status` `failed`, one sentence saying which rule failed, and no `gcloud` call.

- `projectId`: 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter, not ending with `-`.
- `instance`: lowercase letters, digits and `-`, starting with a letter, at most 60 characters.
- `region`: lowercase letters, digits and `-`.
- `timeZone`: `Area/City`, letters and `_` on each side of one `/`.
- `weeknightStop`, `weekendStop`: five space-separated fields, each of digits, `*`, `,`, `-` and `/` only.
- `repository`: `<owner>/<repo>`, each side of letters, digits, `-`, `_` and `.`, with exactly one `/`.
- `mode` is `plan` or `apply`.

## Names

`<account>` is `aleogr-shared-sql-switch@<projectId>.iam.gserviceaccount.com`. `<number>` is the project number, read in step 1. `<active account>` is the account `gcloud` is logged in as (step 1). The jobs are `aleogr-shared-stop-weeknight` (schedule `weeknightStop`) and `aleogr-shared-stop-weekend` (schedule `weekendStop`).

## The parts

Nine parts, in this order. A part is checked only when the part it depends on exists; a part whose dependency is missing is missing too, without a command.

| # | Part | Exists and equal when | Depends on |
|---|---|---|---|
| 1 | `role` | the role exists and its permissions are exactly `cloudsql.instances.get` and `cloudsql.instances.update` | - |
| 2 | `account` | the service account exists | - |
| 3 | `role-grant` | the account holds the role at project level | `role`, `account` |
| 4 | `act-as` | the active account holds `roles/iam.serviceAccountUser` on the service account | `account` |
| 5 | `pool` | the pool exists and its state is `ACTIVE` | - |
| 6 | `provider` | the provider exists and its attribute condition is exactly the one of the create command below for `repository` | `pool` |
| 7 | `federation-grant` | the service account has `roles/iam.workloadIdentityUser` for the `principalSet` of the pool and `repository` | `account`, `pool` |
| 8 | `job-weeknight` | the job exists with the schedule, time zone, URI (`https://sqladmin.googleapis.com/v1/projects/<projectId>/instances/<instance>`) and service account (`<account>`) asked, its HTTP method is `POST`, its headers include `X-HTTP-Method-Override=PATCH` and `Content-Type=application/json`, its body is the stop body, its token scope is `https://www.googleapis.com/auth/cloud-platform`, and its state is `ENABLED` | `account` |
| 9 | `job-weekend` | same, for the weekend job | `account` |

Why `POST` with a header: the Cloud SQL Admin API changes an instance with an HTTP `PATCH`, and Cloud Scheduler cannot send a `PATCH` (its methods are `DELETE`, `GET`, `HEAD`, `POST` and `PUT`). The job sends a `POST` with the header `X-HTTP-Method-Override: PATCH`, which Google APIs read as a `PATCH`. Never `PUT`: it would replace the whole instance resource with the one-line body.

The stop body: the describe prints the job's body encoded in base64; decoded, it must be the JSON object `{"settings":{"activationPolicy":"NEVER"}}` and nothing else (spaces and line breaks do not matter). The body of `${CLAUDE_PLUGIN_ROOT}/files/stop-body.json` encodes to `eyJzZXR0aW5ncyI6eyJhY3RpdmF0aW9uUG9saWN5IjoiTkVWRVIifX0=`. An empty body, or any other body, would not stop the instance.

A job that exists with another schedule, time zone, URI, account, HTTP method, body or token scope, or without one of the two headers is "different" and is updated with all its values (Cloud Scheduler may add headers of its own, such as `User-Agent`: extra headers do not make a job different); a job whose state is not `ENABLED` (paused) is "different" and is resumed. A job that points at another instance would not stop this one, and a job without the override header would not stop any instance, so neither is ever "equal". A role, pool or provider that exists but differs has no command here to change it: no create command runs for it (creating it again would fail, and would not fix it), it is not touched, it stays in `missing`, and the answer says what to fix by hand.

## The last run of each job

The job describe also prints when the job last ran (`lastAttemptTime`) and the result of that run (`status.code`: absent or `0` when it succeeded, another number when it failed). A job whose last run failed is still "equal" when its settings are right — nothing here changes it — but the night stop may not be working: list it in `outputs.lastRunFailed` (`job-weeknight`, `job-weekend`) and say in the answer, in one sentence, that the last run of that job failed and that the instance may have been left running. A job that never ran has neither value: that is not a failure. `ready` and the status do not change because of it.

## Steps

Show each command before running it. Run only the commands below, in the order of the parts. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. The project number and the e-mails (the account, the active account) appear in the commands shown and in the `GitHub secrets` section; they never appear in the result block nor elsewhere in the answer. Every value with a comma, a space, a quote or `&` is double-quoted, as below.

1. Read the project number and the active account (both modes):

   ```
   gcloud projects describe <projectId> --format="value(projectNumber)"
   gcloud config get-value account
   ```

   A non-zero exit or empty output stops with `failed`.

2. Check the parts, in order, with these read commands. A non-zero exit whose text contains `NOT_FOUND` (or `404`) means the part is missing; any other non-zero exit is a failure of the check: stop with `failed` (or `pending` if a change was already made) and never treat it as missing.

   ```
   gcloud iam roles describe aleogrSharedSqlSwitch --project=<projectId> --format="value(includedPermissions)"
   gcloud iam service-accounts describe <account> --project=<projectId> --format="value(email)"
   gcloud projects get-iam-policy <projectId> --flatten="bindings[].members" --filter="bindings.role:roles/aleogrSharedSqlSwitch" --format="value(bindings.members)"
   gcloud iam service-accounts get-iam-policy <account> --project=<projectId> --format=json
   gcloud iam workload-identity-pools describe github --project=<projectId> --location=global --format="value(state)"
   gcloud iam workload-identity-pools providers describe aleogr --project=<projectId> --location=global --workload-identity-pool=github --format="value(attributeCondition)"
   gcloud scheduler jobs describe <job> --project=<projectId> --location=<region> --format="value(schedule,timeZone,state,httpTarget.uri,httpTarget.oauthToken.serviceAccountEmail,httpTarget.httpMethod,httpTarget.headers,httpTarget.body,httpTarget.oauthToken.scope,lastAttemptTime,status.code)"
   ```

   The service account policy is read once and answers both `act-as` and `federation-grant`. Run the jobs describe once per job. Its output is one line of tab-separated values in the order of the format; the headers print as `Name=value` pairs separated by `;`.

3. `plan` ends here, changing nothing: list each part as present, missing or different, and end with `would-create` (some part missing and nothing differs that no command can change), `would-update` (only jobs differ), `unchanged` (nothing to do) or `pending` (a role, pool or provider exists but differs: no command changes it, so `pending[].how` is the manual fix, in `plan` too). `ready` is whether nothing is missing or different.

4. `apply`: for each part that is missing, run its command, in the order of the parts. A part that exists and is equal is skipped.

   ```
   gcloud iam roles create aleogrSharedSqlSwitch --project=<projectId> --title="aleogr shared SQL switch" --permissions="cloudsql.instances.get,cloudsql.instances.update" --stage=GA --quiet
   gcloud iam service-accounts create aleogr-shared-sql-switch --project=<projectId> --display-name="aleogr shared SQL switch" --quiet
   gcloud projects add-iam-policy-binding <projectId> --member="serviceAccount:<account>" --role="projects/<projectId>/roles/aleogrSharedSqlSwitch" --condition=None --quiet
   gcloud iam service-accounts add-iam-policy-binding <account> --project=<projectId> --member="user:<active account>" --role="roles/iam.serviceAccountUser" --quiet
   gcloud iam workload-identity-pools create github --project=<projectId> --location=global --display-name="GitHub" --quiet
   gcloud iam workload-identity-pools providers create-oidc aleogr --project=<projectId> --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" --attribute-condition="assertion.repository=='<repository>' && assertion.ref=='refs/heads/main'" --quiet
   gcloud iam service-accounts add-iam-policy-binding <account> --project=<projectId> --member="principalSet://iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/github/attribute.repository/<repository>" --role="roles/iam.workloadIdentityUser" --quiet
   gcloud scheduler jobs create http <job> --project=<projectId> --location=<region> --schedule="<cron>" --time-zone="<timeZone>" --uri="https://sqladmin.googleapis.com/v1/projects/<projectId>/instances/<instance>" --http-method=POST --headers="Content-Type=application/json,X-HTTP-Method-Override=PATCH" --message-body-from-file="${CLAUDE_PLUGIN_ROOT}/files/stop-body.json" --oauth-service-account-email=<account> --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform" --max-retry-attempts=5 --min-backoff=5m --max-backoff=15m --max-doublings=2 --attempt-deadline=60s --quiet
   gcloud scheduler jobs update http <job> --project=<projectId> --location=<region> --schedule="<cron>" --time-zone="<timeZone>" --uri="https://sqladmin.googleapis.com/v1/projects/<projectId>/instances/<instance>" --http-method=POST --update-headers="Content-Type=application/json,X-HTTP-Method-Override=PATCH" --message-body-from-file="${CLAUDE_PLUGIN_ROOT}/files/stop-body.json" --oauth-service-account-email=<account> --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform" --quiet
   gcloud scheduler jobs resume <job> --project=<projectId> --location=<region> --quiet
   ```

   - Write `${CLAUDE_PLUGIN_ROOT}` as the real folder of this plugin, so the file is `<plugin folder>/files/stop-body.json`. The body is a file of the plugin, never inline.
   - The `create` of a job is for a missing job; the `update` is for a job that exists with another schedule, time zone, URI, account, HTTP method or headers (always with the full set of values above); the `resume` is for a paused job (state other than `ENABLED`), run after the update when the job also differs. The two jobs use their own cron.
   - A job creation that fails is retried once after waiting about one minute (the `act-as` grant may not have propagated yet); the single retry applies to each job on its own. A second failure of the same job stops the skill.
   - A role, pool or provider that exists but differs gets no command at all (no create, no change): it is left as it is and reported.
   - A failure of any other change command stops the skill at once, with no retry and no later command: end with `pending` when something exists (created in this run or before), `failed` when nothing exists. Say in one sentence which part failed, without raw error text. `outputs.missing` lists every part not present and equal.

5. Verify: run the read commands of step 2 again (all parts, all checked now that their dependencies exist), and read the project number again only if needed. If no change command ran, the check of step 2 already is the verification: do not repeat it. `ready` is true only when no part is missing or different. Anything left ends with `pending` and `outputs.missing`.

6. Status of `apply`: `unchanged` (no change command ran and nothing is missing), `updated` (only job updates or resumes ran), `created` (something was created), `pending`, `failed`. If a change ran but verification shows a part still missing, `pending`.

7. When `ready` is true (both modes), the answer's prose has a section titled `GitHub secrets` with the three secrets and their values, one per line:

   - `GCP_SHARED_PROJECT_ID`: the project id.
   - `GCP_SHARED_WIF_PROVIDER`: `projects/<number>/locations/global/workloadIdentityPools/github/providers/aleogr`.
   - `GCP_SHARED_SWITCH_ACCOUNT`: `<account>`.

   And where to paste them: in the repository on GitHub, `Settings`, `Secrets and variables`, `Actions`, `New repository secret`. This section is prose only: the result block holds none of these values. When `ready` is false, there is no such section; say which parts are missing.

Then answer in a few lines: each part's state, the section above when it applies, and the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "instance-switch-setup",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "role", "id": "aleogrSharedSqlSwitch", "name": "aleogrSharedSqlSwitch", "labels": {} },
    { "type": "service-account", "id": "aleogr-shared-sql-switch", "name": "aleogr-shared-sql-switch", "labels": {} },
    { "type": "workload-identity-pool", "id": "github", "name": "github", "labels": {} },
    { "type": "workload-identity-provider", "id": "github/aleogr", "name": "aleogr", "labels": {} },
    { "type": "scheduler-job", "id": "aleogr-shared-stop-weeknight", "name": "aleogr-shared-stop-weeknight", "labels": {} },
    { "type": "scheduler-job", "id": "aleogr-shared-stop-weekend", "name": "aleogr-shared-stop-weekend", "labels": {} }
  ],
  "outputs": { "ready": true, "missing": [], "lastRunFailed": [] },
  "cost": { "fixed": false, "notes": "the switch has no cost of its own; the instance costs about R$ 50 per month while stopped" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create`, `would-update` (plan), `created`, `updated`, `unchanged`, `pending`, `failed`.
- `resources` lists only the parts that exist at the end (as of the last check), with the ids above. The identifiers of the account, the project number and any e-mail never appear in it, nor in `outputs`.
- `outputs.ready` is true only when every part exists and is equal; `outputs.missing` lists the parts still missing or different, by the names `role`, `account`, `role-grant`, `act-as`, `pool`, `provider`, `federation-grant`, `job-weeknight`, `job-weekend`, in that order. In `plan`, `ready` is false whenever `missing` is not empty.
- `pending` (the status) has one item per part left, whose `how` is this same invocation with `mode=apply` (or the manual fix for a part that differs).
- `failed` from validation or from the first check: `resources` is empty and `outputs` is `{ "ready": false, "missing": [], "lastRunFailed": [] }`; a `failed` where nothing exists (after the checks) has all nine parts in `missing`.
- `cost` as above.
