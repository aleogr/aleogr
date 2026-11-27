# Reference project, stage 4c: checklist for the real run

For the owner, in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)), in the folder `~/pilot` that stage 4b-2 left. It proves that `pilot`'s component `admin` reaches its own database on the shared Cloud SQL instance, as its own service account, with no password: one `project-apply` proposes the declaration with the database check in one pull request, whose description warns that applying it starts the shared instance; you merge it; one more `project-apply` reads the night stop, starts the instance when it is stopped, and makes the database, the user, its two roles and the service's settings; `admin` then answers `database: ok` at `/db`. Nothing of this has run against real Google Cloud before: this run is the proof ([`DESIGN.md`](../DESIGN.md) section 18).

**Cost: no new fixed cost.** The instance already costs its disk and its address while stopped. If it is stopped when step 4 runs, that run starts it, and it is charged by the hour while it runs, about R$ 0.06 an hour as read on an earlier bill ([`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md)), a reading, not a promise. Step 6 stops it again, so this run should add well under R$ 1. A database, a user, roles and settings cost nothing.

Source of truth: [`DESIGN.md`](../DESIGN.md) sections 6.4, 6.8, 11.5 and 12, and [`CONTRACTS.md`](../CONTRACTS.md). The [design of 4c](2026-11-26-pilot-stage-4c-design.md) was changed during the build: its note at the top lists how.

**Never paste in the conversation with Claude, nor in what you send back:** a service's address (it holds the project's number), a project's id or number, an e-mail, a database user's name (it holds an e-mail and a project id), a connection name, the values of GitHub secrets, or what `gcloud auth list` or `gh auth status` print. Write `<id>` in their place. Send a screenshot only where a step asks for one, and only of what it names.

## What to have ready

- The pull request of stage 4c is merged into `main` of `aleogr/aleogr`.
- `gcloud` and `gh` are signed in, `gh` with `workflow` among its `Token scopes` (as in stage 4b-2). Do not paste what they print.
- `~/pilot` is on `main` with no change of its own: `cd ~/pilot && git status` says `On branch main` and lists nothing as modified.
- For the terminal steps, paste this once in the Cloud Shell terminal, outside Claude Code (it prints nothing; paste it again if Cloud Shell reconnects):

  ```bash
  P=$(gcloud projects list --filter="labels.aleogr-project=pilot AND labels.aleogr-environment=dev" --format="value(projectId)")
  S=$(gcloud projects list --filter="labels.aleogr-project=shared AND labels.aleogr-platform=shared" --format="value(projectId)")
  ```

- The shared instance has IAM database authentication on, which no skill reads back (read-only; it prints no identifier):

  ```bash
  gcloud sql instances describe aleogr-shared --project="$S" --format="value(settings.databaseFlags)"
  ```

  Expected: it holds `cloudsql.iam_authentication` with the value `on`. **Stop and send what it prints** otherwise: without it the database user cannot log in, and the first failure would come after the cost.

When Claude Code asks for permission: allow the `gh`, `git` and `gcloud` commands it shows; the Go commands of step 3 (`go version`, `go -C admin get …`, `go -C admin mod tidy`) and the file commands around them (`ls -1Ap -- admin/`, `cmp -s …` with the `sed` inside `<( )`, `mktemp -d`, `cp -p …`, `rm -rf --` of the folder `mktemp` made); `sleep 30` in the background (a skill waiting by itself); in step 4 only (and in its recovery), the reads of the night stop that come right before the start (`gcloud iam … describe`, `gcloud scheduler jobs describe …`, `gcloud projects get-iam-policy …`: they only read), `gcloud sql instances patch aleogr-shared … --activation-policy=ALWAYS`, `gcloud sql databases create pilot_dev`, `gcloud sql users create … --type=cloud_iam_service_account`, the two `gcloud projects add-iam-policy-binding` on the shared project with `--member="serviceAccount:pilot-admin@…"`, `--role="roles/cloudsql.client"` or `--role="roles/cloudsql.instanceUser"` and `--condition=None`, and `gcloud run services update pilot-admin --update-env-vars=…`. Answer **"Yes, but ask again next time"** to the reads of the plugins' files (`defaults.json`, the templates). **Never allow**, and send the answer if it is proposed: `--password`, `--database-roles`, any other role (`roles/owner`, `roles/editor`, `roles/cloudsql.admin`, …), a member other than `serviceAccount:pilot-admin@…`, `set-iam-policy`, `--activation-policy=NEVER`, `--image` with `run services update`, `--set-env-vars`, `--remove-env-vars`, `--clear-env-vars`, any `delete`, any `gcloud scheduler jobs` command other than `describe`, `gh pr merge`, a push to `main`; and `gcloud sql instances patch` outside step 4.

The read of the night stop (in steps 2 and 4) may print, in Claude's working output, the values of the three GitHub secrets of the workflow `self-shared-database`: never paste them.

## Where you stop, and why

- **Step 2, before anything else:** the night stop must be ready, or no run may start the instance.
- **Step 3, before the merge:** the answer and the pull request say that applying it starts the shared instance when it is stopped. This is where you see what will be started and what it costs. Merge only if you accept it.
- **Step 3, first thing after the merge:** confirm that the deploy's log shows neither the project's id nor its number.
- **Step 4: keep the Cloud Shell tab in front** while the run waits for the instance (about twelve minutes when it was stopped): a session that expires loses the answer (the recovery is at the end of step 4).
- **The merges are yours**, on GitHub, never Claude Code's.

## 1. Update the plugins, and Go

In the terminal, outside Claude Code:

```bash
claude plugin marketplace update aleogr
```

```bash
for p in aleogr aleogr-cloud-gcp aleogr-db-gcp-cloud-sql aleogr-registry-gcp-artifact-registry aleogr-repo-github aleogr-stack-go; do claude plugin update "$p@aleogr"; done
```

Expected: `claude plugin list` shows, all enabled: `aleogr` 0.12.0, `aleogr-cloud-gcp` 0.7.1, `aleogr-db-gcp-cloud-sql` 0.5.2, `aleogr-registry-gcp-artifact-registry` 0.1.2, `aleogr-repo-github` 0.6.2, `aleogr-stack-go` 0.3.1.

```bash
go version
```

Expected: one line `go version go1.<n> linux/amd64` (any version: the Go command downloads the one `admin` declares when it needs it). **Stop and send** if it says `command not found`.

## 2. The shared platform, read only

```bash
cd ~/pilot && claude
```

```
/aleogr:platform-plan
```

It only reads. **Do not send its answer:** when the instance runs, one of its lines names the shared project's id. Read two rows of its table:

- `database switch`: expected `ready` / `none` (the night stop and its identity exist as declared).
- `database instance`: `exists, stopped` / `none` (step 4 will start it), or `exists, running` / `none` (it already runs: step 4 adds nothing to its cost), or `exists, starting` / `none` (someone started it: step 4 waits for it).

Then its last line: expected `nothing to do`.

**Stop and send only those two rows (state and action) and the last line** if `database switch` is anything but `ready`, if `database instance` is `missing`, `unknown` or `not checked …`, or if a line under the table says that the last run of a stop job failed (send that line too: it names the jobs, no identifier). Without a ready switch, step 4 does not start the instance: it stops, saying the night stop could not be confirmed.

## 3. The declaration and the check, in one pull request

In Claude Code, still in `~/pilot`:

```
/aleogr:project-declare component=admin database=yes
```

Expected: `updated`, the declaration's line for `admin` now ends with `"database": true`; nothing else changed. **Stop and send the answer** if it fails saying that the component needs Go 1.26 or later (the steps below assume that `admin` declares Go 1.27, as its declaration of stage 3c-2 did).

```
/aleogr:project-apply confirm=yes
```

It writes, in `~/pilot/admin`, `db_test.go` and `db.go`, replaces `main.go` by the tooling's own file with the line of the route `GET /db` (only because it is still the file the tooling wrote), adds the two modules with `go get` and `go mod tidy` (which write `go.mod` and `go.sum`; the first time, the Go command downloads the toolchain `admin` declares, which can take a minute), and proposes them with the declaration in one pull request titled `Add the database check of admin`. It makes nothing in Google Cloud.

Expected answer, `status` `updated`:

- the lines `go_setup: created` and `github_pull-request-open: created`;
- the plan's table: `declaration` `changed here` / `propose`, `components` `to generate: admin` / `generate`, `ci` `as declared`, and `settings`, `visibility`, `protection`, `environment dev`, `apis`, `registry`, `ci identity`, `services`, `database` and `ci secrets` `not checked until the change is merged` / `none`;
- word for word: `Applying this after the merge starts the shared database instance when it is stopped: it then runs, charged by the hour, until the night stop.`;
- the pull request's address on its own line, and what is left: merge it, then `/aleogr:project-apply confirm=yes`.

**Stop and send the answer** if it carries the item `route` (`main.go` was not the tooling's file: the route is left to you), if `go_setup` failed, or if the warning above is missing.

In the terminal, the pull request's files, its description and the `go` line (they print no identifier):

```bash
N=$(gh pr list --repo aleogr-sandbox/pilot --state open --json number --jq '.[0].number')
gh pr view "$N" --repo aleogr-sandbox/pilot --json title,body,files --jq '.title, .body, .files[].path'
gh pr diff "$N" --repo aleogr-sandbox/pilot | grep -E '^[+-](go|toolchain) '
```

Expected: the title; the description `Proposed by aleogr.` followed by the same warning; then six paths, `.aleogr/project.json`, `admin/db.go`, `admin/db_test.go`, `admin/go.mod`, `admin/go.sum`, `admin/main.go` (in any order); then nothing, or exactly `-go 1.27` and `+go 1.27.0`. **Stop and send** if a `toolchain` line or another Go version appears.

**STOP here: read the warning.** It is the cost of step 4. Read-only, whether the instance is stopped now:

```bash
gcloud sql instances describe aleogr-shared --project="$S" --format="value(settings.activationPolicy,state)"
```

`NEVER` and a state: stopped, so step 4 starts it (about twelve minutes, then charged by the hour until the night stop or step 6). `ALWAYS RUNNABLE`: it already runs, and step 4 adds nothing to its cost.

On GitHub, the pull request: its checks `ci / ci` green. **Squash and merge**, only if you accept the warning.

**First thing after the merge: the deploy's log.** When the run of `ci` on `main` has ended (the repository's **Actions** tab), in the terminal (it prints only a summary and counts):

```bash
R=$(gh run list --repo aleogr-sandbox/pilot --workflow ci --branch main --limit 1 --json databaseId --jq '.[0].databaseId')
NUM=$(gcloud projects describe "$P" --format="value(projectNumber)")
gh run view "$R" --repo aleogr-sandbox/pilot
gh run view "$R" --repo aleogr-sandbox/pilot --log > /tmp/deploy.log; wc -l < /tmp/deploy.log; grep -c -e "$P" -e "$NUM" /tmp/deploy.log; rm -f /tmp/deploy.log
```

Expected: the summary says `Triggered via push` a few minutes ago and lists `deploy-admin-dev`, green; then the log's line count and `0`. An empty `P` or `NUM` makes the second number equal the first: set them again and repeat. Anything else: **stop**, say so (without the value), and delete that run's logs at once (`gh run delete "$R" --repo aleogr-sandbox/pilot`).

Then open `admin`'s address in the browser, signed in, with `/db` at the end. Expected: **`database: not configured`** (the settings come in step 4). The address without `/db`: `admin: ok`.

## 4. The database

```
/aleogr:project-apply confirm=yes
```

It brings the folder up to date with the merge, plans again and, under the same confirmation, enables the Cloud SQL Admin API in `pilot`'s GCP project when it is off (waiting by itself while it still refuses). When the instance is stopped, it reads the night stop first (only reads) and starts the instance only if the night stop is ready; then it waits until the instance accepts calls (`sleep 30` in the background, up to 30 tries; a read that fails counts as a try), makes the database `pilot_dev`, the database user of `admin`'s service account (no password), its two connection roles on the shared project, and the three settings of `pilot-admin` (`DB_INSTANCE`, `DB_NAME`, `DB_USER`, its image untouched), then plans again. No pull request. **Keep the Cloud Shell tab in front:** about twelve minutes when the instance was stopped.

Expected answer, `status` `updated`:

- one line per skill that made something: `github_checkout-setup: updated`, when the API was off `gcp_services-enable: updated` (and maybe `Waited for the APIs enabled in this run: <skill> answered on try <n>.`), when the instance was stopped `gcp-cloud-sql_instance-start: updated`, then `gcp-cloud-sql_database-create: created`, `gcp-cloud-sql_access-grant: updated`, `gcp_deploy-setup: updated`;
- when it started the instance, word for word: `This run started the shared database instance: it runs, charged by the hour, until the night stop. To stop it sooner: /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop, or the workflow self-shared-database of aleogr/aleogr (action stop).`; when the instance was already starting (someone started it), no start's line and no start's sentence, but `The shared instance was already starting: this run waited for it and did not start it.`;
- the last plan's table, fourteen rows, every action `none`: `components`, `ci`, `services`, `database` and `ci secrets` `as declared`, `protection` `protected, requires ci`; then `nothing to do`;
- the two lines `admin: https://…run.app` and `status: https://…run.app`, then `admin: https://…run.app/db`;
- the result block. Nothing else.

Write down how long the run waited for the instance (from the start's line to the next one, roughly).

**Stop and send the answer** (its sentences only, with every id replaced by `<id>`) if:

- it says `The night stop of the shared instance could not be confirmed, so the instance was not started.`: run `/aleogr:platform-plan` and send its row `database switch`;
- the start failed (the item `database` says `the shared instance could not be started`): send its sentence; unless it says the instance is still stopped, read the instance's state (the first command of the recovery below) and, if it says `ALWAYS`, stop it with the workflow (step 6) when you stop for the day;
- it says `did not accept calls after 30 tries`, or that the wait could not be run: the instance runs; stop it with the workflow (step 6) when you stop for the day;
- it stopped with the item `database` (send its sentence), or it ended `pending` with an item that says the shared instance is starting (the run should have waited for it);
- `database` is not `as declared` in its last table (`differs: settings` again right after the run wrote them is the shape of the real settings differing from what the skills read).

**If the session expires during the run, or the answer is cut off:** reconnect, paste `P` and `S` again, and read the instance's state in the terminal (it prints no identifier):

```bash
gcloud sql instances describe aleogr-shared --project="$S" --format="value(settings.activationPolicy,state)"
```

Then `cd ~/pilot && claude` and run `/aleogr:project-apply confirm=yes` again. It reads first and makes only what is missing: when the instance is still starting it waits for it by itself (it does not start it again), when it runs it makes what is left, and `nothing to do` with `database` `as declared` means the first run had finished. The first run's start's sentence is not shown again. Then check by direct reads, in the terminal (each prints no identifier):

```bash
gcloud sql instances describe aleogr-shared --project="$S" --format="value(settings.activationPolicy,state)"
gcloud sql databases list --instance=aleogr-shared --project="$S" --format="value(name)" | grep -cx pilot_dev
gcloud sql users list --instance=aleogr-shared --project="$S" --format="value(name)" | grep -c '^pilot-admin@'
gcloud projects get-iam-policy "$S" --flatten="bindings[].members" --filter="bindings.members:serviceAccount:pilot-admin@" --format="value(bindings.role)"
gcloud run services describe pilot-admin --region=us-central1 --project="$P" --format=json | grep -o '"name": "DB_[A-Z_]*"'
```

Expected: `ALWAYS RUNNABLE`; `1`; `1`; `roles/cloudsql.client` and `roles/cloudsql.instanceUser`, nothing else; the three names `DB_INSTANCE`, `DB_NAME`, `DB_USER`.

## 5. `admin` reaches its database

Open `admin`'s address with `/db`, signed in. Expected: **`database: ok`**. The address without `/db`: `admin: ok` (the settings' update kept the image CI deployed). In the terminal:

```bash
gcloud run services describe pilot-admin --region=us-central1 --project="$P" --format="value(spec.template.spec.containers[0].image)" | grep -c cloudrun/container/hello
```

Expected: `0` (not Google's sample image).

**Stop and send** if `/db` says `database: not reachable (the shared instance may be stopped)` while the first read of step 4's recovery says `ALWAYS RUNNABLE`: the connection was refused. Then, in the terminal, the check's last log lines, and send them with every id, number, address and e-mail replaced by `<id>`:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="pilot-admin" AND textPayload:"database check"' --project="$P" --limit=3 --format="value(textPayload)"
```

## 6. Stop the instance; the check says so

On GitHub, repository `aleogr/aleogr`: **Actions**, `self-shared-database`, **Run workflow**, branch `main`, action **stop**. Expected: the run green, its summary `aleogr-shared: stopped` (it waits for the stop, a minute or so).

Then open `admin`'s address with `/db` again. Expected: **`database: not reachable (the shared instance may be stopped)`**, within a few seconds (the check gives up after 5). **Stop and send** if it takes much longer, or shows another page (an error page of Google, a timeout).

Optional, read-only, what the Admin API answers on a stopped instance (the skills never ask it; [`DESIGN.md`](../DESIGN.md) section 18):

```bash
gcloud sql databases list --instance=aleogr-shared --project="$S" --format="value(name)"; echo "exit $?"
```

Send what it prints, with any id replaced by `<id>`.

## 7. Nothing to do, and the instance stays stopped

```
/aleogr:project-apply confirm=yes
```

Expected: fourteen rows, every action `none`, `database` `as declared` with the line `The database itself was not read: the shared instance is stopped.`, then `nothing to do`, the addresses, `status` `unchanged`. Then:

```
/aleogr:project-apply
```

Expected: the same, `nothing to do`, `unchanged`.

**Stop and send the answer** if either run proposes `gcloud sql instances patch` (deny it), reads the night stop, or says it started the instance: nothing needs it here.

## 8. Cost check

In the terminal:

```bash
gcloud sql instances describe aleogr-shared --project="$S" --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER` and a state (stopped). Then the two services, as in stage 4b-2:

```bash
for s in pilot-admin pilot-status; do echo "$s"; gcloud run services describe "$s" --region=us-central1 --project="$P" --format=json | grep -E 'minScale|maxScale|scalingMode|cpu-throttling|"memory"'; done
```

Expected for each: `run.googleapis.com/maxScale` `"2"` and `"memory": "512Mi"`; no `minScale` other than `"0"`; no `scalingMode` `manual`; `cpu-throttling` absent or `"true"`. Anything else: send these lines (they hold no identifier).

## If something differs

Stop at that step and send its whole answer (or the terminal's text), with every id, number, e-mail and address replaced by `<id>`. A session interrupted at any point is safe to resume: every step reads before it changes, so `/aleogr:project-apply confirm=yes` can always be run again (after step 4's warning was read and merged). If the instance was started and you stop for the day, stop it with the workflow (step 6).

## Results

Run by the owner on 2026-11-27, in one sitting. The shared instance ran for less than an hour.

| Step | Expected | Result |
|---|---|---|
| Ready | 4c merged; `gcloud` and `gh` signed in; `~/pilot` clean on `main`; `cloudsql.iam_authentication` `on` | as expected: `~/pilot` clean on `main`, the flag `cloudsql.iam_authentication` `on` |
| 1. Plugins and Go | the six versions above; `go version` prints a version | updated inside Claude Code (`/plugin marketplace update aleogr`, five plugins bumped, then `/reload-plugins`); the versions were not listed one by one; `go version go1.27.3 linux/amd64` |
| 2. Shared platform | `database switch` `ready`; `database instance` `exists, stopped` (or running); `nothing to do` | `database switch` `ready`, `database instance` `exists, stopped`, `nothing to do` |
| 3. Declaration and check | `updated`; the warning sentence, in the answer and the pull request; six files; `go` line unchanged or `.0`, no `toolchain`; the log count `0`; `deploy-admin-dev` green; `/db` `database: not configured` | `project-declare` `updated`, only `"database": true` added to `admin`. `project-apply` `updated` in 4m21s: `go_setup admin: created`, `github_pull-request-open: created`, the table as expected, the warning word for word, no item `route`, six files in one pull request. After the merge: `admin / go` and `deploy-admin-dev` green, `status` and `deploy-status-dev` skipped; 1808 log lines, `0` with the id or the number; `/db` `database: not configured`. Not captured: the pull request's description and the `go` line of its diff. The log check was first run before the merge, on an older run, and repeated after it |
| 4. The database | `updated`; the start's sentence when stopped; fourteen rows `none`, `nothing to do`; `admin: …/db`; how long the wait took | `updated`, about ten minutes from start to end by the owner's estimate, the Cloud Shell session held: `gcp_services-enable: updated`, `gcp-cloud-sql_instance-start: updated`, `gcp-cloud-sql_database-create: created`, `gcp-cloud-sql_access-grant: updated`, `gcp_deploy-setup: updated`; the start's sentence word for word; fourteen rows `none`, `database` `as declared`, `nothing to do`; the three address lines. No `github_checkout-setup` line: the folder was already up to date. How many reads failed during the wait was not captured |
| 5. `/db` | `database: ok`; `/` `admin: ok`; image count `0` | `database: ok`; `/` `admin: ok`. The image count was not run (`admin: ok` shows the deployed image was kept) |
| 6. Stopped | workflow green, `stopped`; `/db` `may be stopped` within a few seconds; (optional) what the list answers | workflow green in 1m2s, `aleogr-shared: stopped`; `/db` `database: not reachable (the shared instance may be stopped)`, answered quickly. The optional list on the stopped instance was not run |
| 7. Nothing to do | `unchanged` twice; the line `not read: … stopped`; the instance not started | `unchanged` twice (1m15s and 1m6s), fourteen rows `none`, the line `The database itself was not read: the shared instance is stopped.`, `nothing to do`; the instance was not started. The first run added one sentence of its own before the table |
| 8. Cost | `NEVER`; two services, maximum 2, 512Mi, minimum 0 | `NEVER STOPPED`; both services maximum 2, `cpu-throttling` `true`, 512Mi, no minimum |
