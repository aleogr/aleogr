# Lab platform, stage 2: checklist for the first real run

For the owner. Run this in the Claude Code Windows app, where `gcloud` is authenticated. Unlike stage 1, this run creates something that costs money: one Cloud SQL PostgreSQL instance, about R$ 50 per month while stopped. It is stopped as soon as it is created, and Google Cloud stops it every night.

Source of truth: [`2026-11-17-lab-platform-stage-2-design.md`](2026-11-17-lab-platform-stage-2-design.md) and [`DESIGN.md`](../DESIGN.md) section 6.8.

## Before you start

- Stage 1 is done: the shared project exists and `/aleogr:platform-plan` ends with `nothing to do` for its three items.
- The pull request of stage 2 is **merged into `main`**. The workflow in step 5 only works from `main`.
- The Google account used by `gcloud` can create service accounts, roles and Cloud Scheduler jobs in the shared project.

## 1. Update the marketplace and install the new plugin

If you registered the marketplace with the `"ref"` line while the work was unmerged, remove that line first (stage 1, step 1), or re-add the marketplace from the plugin browser without a branch.

In the app, open **Directory**, then **Plugins**, then the **Code** tab. Next to the marketplace `aleogr`, click the **`···`** menu and choose **update** (the same menu has **check for updates**). The new plugin **Cloud SQL (database)** appears in the list: click its **`+`** to install it. Also confirm that `aleogr` and `aleogr-cloud-gcp` show their new version.

Plugins are loaded when a session starts: **open a new session** after installing or updating.

## 2. Plan

In the new session, run `/aleogr:platform-plan`. It changes nothing. Expected: the three stage 1 items `none`, and two new items to `create`: `database switch` (`missing`) and `database instance` (`missing`).

## 3. Apply

Run `/aleogr:platform-apply`. It shows the plan and asks **one** question, which says the instance has a fixed cost of `about R$ 50 per month while stopped`. Answer yes only if you accept that cost; without a clear yes nothing is created.

It then creates, in this order: the switch (a role, a service account, the federation of GitHub, and two Cloud Scheduler jobs) and the instance. Before the instance it says the cost again. Creating the instance takes **several minutes**: wait, the session does the waiting. It ends with a new plan that must say `nothing to do`, with the instance `stopped`.

The creation also **proves the night stop**: once the new instance is running, the skill stops it by running the job `aleogr-lab-stop-weeknight` once (`gcloud scheduler jobs run`) and waits up to 5 minutes for the instance to show `stopped`.

- When the job works, the instance step ends `created` and says the night stop was proven.
- When it does not (the job cannot be run, or the instance is still running after 5 minutes), the skill stops the instance itself, so it is still left `stopped`, and the run ends `pending` with a sentence saying the night-stop job did NOT stop the instance, and the item `the night stop does not work: send this output; until it is fixed, stop the instance by hand after each use`. Do exactly that: send the output, and stop the instance by hand (step 5's `stop`, or `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop`) every time you start it, until the fix arrives.

If it stops before the end, send its output and run `/aleogr:platform-apply` again: it resumes from what already exists and never creates a second instance.

## 4. Paste the three GitHub secrets

Whenever the switch is ready at the end of its run, `platform-apply` prints a **GitHub secrets** section with three names and their values. Pasting them is done once, by hand (nothing else can write them for you):

1. On GitHub, open the repository `aleogr/aleogr`, **Settings**, **Secrets and variables**, **Actions**, **New repository secret**.
2. Create three secrets, with exactly these names and the values printed by the skill:
   - `LAB_GCP_PROJECT_ID`
   - `LAB_GCP_WIF_PROVIDER`
   - `LAB_GCP_SWITCH_ACCOUNT`

If you lost the values, run `/aleogr:platform-apply` again: when everything exists it changes nothing, and it prints the section again.

## 5. Run the workflow

On GitHub, in the repository `aleogr/aleogr`, open the **Actions** tab, choose `self-lab-database` in the list on the left, click **Run workflow**, keep the branch `main`, choose the action and run. Do these three, in this order, and wait for each to finish (green) before the next:

1. `status`: expected `aleogr-lab: stopped`.
2. `start`: expected `aleogr-lab: starting` or `aleogr-lab: running` (right after the start it may also show `stopped` for a moment), followed by the note that it takes about ten minutes to accept connections. The run does not wait for those ten minutes. Run `status` again after a few minutes; it ends as `running`.
3. `stop`: the run waits until Google Cloud reports the stop as done (up to about 5 minutes), then prints `aleogr-lab: stopped`. **Do not skip this one**: it is what turns the cost back to the fixed part.

A red run with `Missing secret` means step 4 was not finished. Any other red run: send the text of the error (the logs are public, so they hold no project id).

## 6. Look at the night jobs

In the Google Cloud console, open **Cloud Scheduler** in the shared project (region `us-central1`). Expected: two jobs, both enabled:

- `aleogr-lab-stop-weeknight`: 22:30, Sunday to Thursday, time zone `America/Sao_Paulo`.
- `aleogr-lab-stop-weekend`: 04:00, Saturday and Sunday, same time zone.

Note the **next run** time of each. **Force run** is optional now: the creation in step 3 already ran the weeknight job once and saw the instance stop. If you force a run anyway, the instance is already stopped, so nothing changes, but the job's result shows whether the call works.

## 7. What to send back

- The final plan output of `platform-apply` (the table and the `aleogr-result` block).
- The result of the three workflow runs (the line each prints, or the error).
- Whether the instance step said the night stop was proven (step 3).
- The two jobs' next run times, and, if you forced a run, whether it succeeded.
- The full text of any error, from any step. Never paste the three secret values.

## 8. Not verified until this run

- Every `gcloud sql`, `gcloud scheduler` and `gcloud iam` flag used by the new skills.
- Whether the instance can be created directly in the stopped state, or must be created and then stopped.
- Whether "idle" in the address charge means "stopped": the first bill confirms it.
- The rule that derives `stopped` from the activation policy (`NEVER` is `stopped`; `ALWAYS` with `RUNNABLE` is `running`): that `gcloud` and the API report these values as assumed.
- The text of the "does not exist" error of `gcloud sql instances describe`: the skills rely on `does not exist` or `404`.
- Whether `db-f1-micro` exists for the PostgreSQL version chosen (the newest one Cloud SQL offers).
- That the Cloud SQL Admin API accepts the jobs' call: Cloud Scheduler cannot send a `PATCH`, so each job sends a `POST` with the header `X-HTTP-Method-Override: PATCH`. The creation in step 3 proves it (or says it does not work).
- `gcloud scheduler jobs run`, which the creation uses to run the weeknight job once.
- The PowerShell quoting of the provider's `--attribute-condition` value, which holds `&&` and single quotes inside double quotes.

What fails becomes a fix in the skills and, when it is provider behaviour, a line in [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md).
