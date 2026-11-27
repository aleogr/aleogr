# Reference project, stage 4c: checklist for the real run

For the owner, in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)), in the folder `~/pilot` that stage 4b-2 left. It proves that `pilot`'s component `admin` reaches its own database on the shared Cloud SQL instance, as its own service account, with no password: one `project-apply` proposes the declaration with the database check in one pull request; you merge it; one more `project-apply` starts the instance when it is stopped and makes the database, the user, its two roles and the service's settings; `admin` then answers `database: ok` at `/db`. Nothing of this has run against real Google Cloud before: this run is the proof ([`DESIGN.md`](../DESIGN.md) section 18).

**Cost: no new fixed cost.** The instance already costs its disk and its address while stopped. If it is stopped when step 3 runs, that run starts it, and it is charged by the hour while it runs, about R$ 0.06 an hour as read on an earlier bill ([`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md)), a reading, not a promise. Step 5 stops it again, so this run should add well under R$ 1. A database, a user, roles and settings cost nothing.

Source of truth: [`2026-11-26-pilot-stage-4c-design.md`](2026-11-26-pilot-stage-4c-design.md) and [`DESIGN.md`](../DESIGN.md) sections 6.4, 6.8, 11.5 and 12.

**Never paste in the conversation with Claude, nor in what you send back:** a service's address (it holds the project's number), a project's id or number, an e-mail, a database user's name (it holds an e-mail and a project id), a connection name, or what `gcloud auth list` or `gh auth status` print. Write `<id>` in their place. Send a screenshot only where a step asks for one, and only of what it names.

## What to have ready

- The pull request of stage 4c is merged into `main` of `aleogr/aleogr`.
- `gcloud` and `gh` are signed in, `gh` with `workflow` among its `Token scopes` (as in stage 4b-2). Do not paste what they print.
- `~/pilot` is on `main` with no change of its own: `cd ~/pilot && git status` says `On branch main` and lists nothing as modified.
- For the terminal steps, paste this once in the Cloud Shell terminal, outside Claude Code (it prints nothing; paste it again if Cloud Shell reconnects):

  ```bash
  P=$(gcloud projects list --filter="labels.aleogr-project=pilot AND labels.aleogr-environment=dev" --format="value(projectId)")
  S=$(gcloud projects list --filter="labels.aleogr-project=shared AND labels.aleogr-platform=shared" --format="value(projectId)")
  ```

When Claude Code asks for permission: allow the `gh`, `git` and `gcloud` commands it shows; the Go commands of step 2 (`go version`, `go -C admin get …`, `go -C admin mod tidy`) and the file commands around them (`cmp -s …`, `mktemp -d`, `cp -p …`, `rm -rf --` of the folder `mktemp` made); `sleep 30` in the background (a skill waiting by itself); in step 3 only, `gcloud sql instances patch aleogr-shared … --activation-policy=ALWAYS`, `gcloud sql databases create pilot_dev`, `gcloud sql users create … --type=cloud_iam_service_account`, the two `gcloud projects add-iam-policy-binding` on the shared project with `--member="serviceAccount:pilot-admin@…"`, `--role="roles/cloudsql.client"` or `--role="roles/cloudsql.instanceUser"` and `--condition=None`, and `gcloud run services update pilot-admin --update-env-vars=…`. Answer **"Yes, but ask again next time"** to the reads of the plugins' files (`defaults.json`, the templates). **Never allow**, and send the answer if it is proposed: `--password`, `--database-roles`, any other role (`roles/owner`, `roles/editor`, `roles/cloudsql.admin`, …), a member other than `serviceAccount:pilot-admin@…`, `set-iam-policy`, `--activation-policy=NEVER`, `--image` with `run services update`, `--set-env-vars`, `--remove-env-vars`, `--clear-env-vars`, any `delete`, `gh pr merge`, a push to `main`; and `gcloud sql instances patch` outside step 3.

## Where you stop, and why

- **Step 2, before the merge:** the answer and the pull request say that applying it starts the shared instance when it is stopped. This is where you see what will be started and what it costs. Merge only if you accept it.
- **Step 2, first thing after the merge:** confirm that the deploy's log shows neither the project's id nor its number.
- **Step 3: keep the Cloud Shell tab in front** while the run waits for the instance (about twelve minutes when it was stopped): a session that expires loses the answer.
- **The merges are yours**, on GitHub, never Claude Code's.

## 1. Update the plugins, and Go

In the terminal, outside Claude Code:

```bash
claude plugin marketplace update aleogr
```

```bash
for p in aleogr aleogr-cloud-gcp aleogr-db-gcp-cloud-sql aleogr-registry-gcp-artifact-registry aleogr-repo-github aleogr-stack-go; do claude plugin update "$p@aleogr"; done
```

Expected: `claude plugin list` shows, all enabled: `aleogr` 0.12.0, `aleogr-cloud-gcp` 0.7.0, `aleogr-db-gcp-cloud-sql` 0.5.1, `aleogr-registry-gcp-artifact-registry` 0.1.2, `aleogr-repo-github` 0.6.2, `aleogr-stack-go` 0.3.0.

```bash
go version
```

Expected: one line `go version go1.<n> linux/amd64` (any version: the Go command downloads the one `admin` declares, 1.27, when it needs it). **Stop and send** if it says `command not found`.

## 2. The declaration and the check, in one pull request

```bash
cd ~/pilot && claude
```

```
/aleogr:project-declare component=admin database=yes
```

Expected: `updated`, the declaration's line for `admin` now ends with `"database": true`; nothing else changed.

```
/aleogr:project-apply confirm=yes
```

It writes, in `~/pilot/admin`, `db_test.go` and `db.go`, replaces `main.go` by the tooling's own file with the line of the route `GET /db` (only because it is still the file the tooling wrote), adds the two modules with `go get` and `go mod tidy` (which write `go.mod` and `go.sum`; the first time, the Go command downloads its 1.27 toolchain, which can take a minute), and proposes them with the declaration in one pull request titled `Add the database check of admin`. It makes nothing in Google Cloud.

Expected answer, `status` `updated`:

- the lines `go_setup: created` and `github_pull-request-open: created`;
- the plan's table: `declaration` `changed here` / `propose`, `components` `to generate: admin` / `generate`, `ci` `as declared`, and `settings`, `visibility`, `protection`, `environment dev`, `apis`, `registry`, `ci identity`, `services`, `database` and `ci secrets` `not checked until the change is merged` / `none`;
- word for word: `Applying this after the merge starts the shared database instance when it is stopped: it then runs, charged by the hour, until the night stop.`;
- the pull request's address on its own line, and what is left: merge it, then `/aleogr:project-apply confirm=yes`.

**Stop and send the answer** if it carries the item `route` (`main.go` was not the tooling's file: the route is left to you), or if `go_setup` failed.

In the terminal, the pull request's files and the `go` line (they print no identifier):

```bash
N=$(gh pr list --repo aleogr-sandbox/pilot --state open --json number --jq '.[0].number')
gh pr view "$N" --repo aleogr-sandbox/pilot --json title,files --jq '.title, .files[].path'
gh pr diff "$N" --repo aleogr-sandbox/pilot | grep -E '^[+-](go|toolchain) '
```

Expected: the title, then six paths, `.aleogr/project.json`, `admin/db.go`, `admin/db_test.go`, `admin/go.mod`, `admin/go.sum`, `admin/main.go` (in any order); then nothing, or exactly `-go 1.27` and `+go 1.27.0`. **Stop and send** if a `toolchain` line or another Go version appears.

**STOP here: the cost.** The pull request's description has the same sentence. Read-only, whether the instance is stopped now:

```bash
gcloud sql instances describe aleogr-shared --project="$S" --format="value(settings.activationPolicy,state)"
```

`NEVER` and a state: stopped, so step 3 starts it (about twelve minutes, then charged by the hour until the night stop or step 5). `ALWAYS RUNNABLE`: it already runs, and step 3 adds nothing to its cost.

On GitHub, the pull request: its checks `ci / ci` green. **Squash and merge.**

**First thing after the merge: the deploy's log.** When the run of `ci` on `main` has ended (the repository's **Actions** tab), in the terminal (it prints only a summary and counts):

```bash
R=$(gh run list --repo aleogr-sandbox/pilot --workflow ci --branch main --limit 1 --json databaseId --jq '.[0].databaseId')
NUM=$(gcloud projects describe "$P" --format="value(projectNumber)")
gh run view "$R" --repo aleogr-sandbox/pilot
gh run view "$R" --repo aleogr-sandbox/pilot --log > /tmp/deploy.log; wc -l < /tmp/deploy.log; grep -c -e "$P" -e "$NUM" /tmp/deploy.log; rm -f /tmp/deploy.log
```

Expected: the summary says `Triggered via push` a few minutes ago and lists `deploy-admin-dev`, green; then the log's line count and `0`. An empty `P` or `NUM` makes the second number equal the first: set them again and repeat. Anything else: **stop**, say so (without the value), and delete that run's logs at once (`gh run delete "$R" --repo aleogr-sandbox/pilot`).

Then open `admin`'s address in the browser, signed in, with `/db` at the end. Expected: **`database: not configured`** (the settings come in step 3). The address without `/db`: `admin: ok`.

## 3. The database

```
/aleogr:project-apply confirm=yes
```

It brings the folder up to date with the merge, plans again and, under the same confirmation, enables the Cloud SQL Admin API in `pilot`'s GCP project when it is off (waiting by itself while it still refuses), starts the shared instance when it is stopped and waits until it accepts calls (`sleep 30` in the background, up to 30 times), makes the database `pilot_dev`, the database user of `admin`'s service account (no password), its two connection roles on the shared project, and the three settings of `pilot-admin` (`DB_INSTANCE`, `DB_NAME`, `DB_USER`, its image untouched), then plans again. No pull request. **Keep the Cloud Shell tab in front:** about twelve minutes when the instance was stopped.

Expected answer, `status` `updated`:

- one line per skill that made something: `github_checkout-setup: updated`, when the API was off `gcp_services-enable: updated` (and maybe `Waited for the APIs enabled in this run: <skill> answered on try <n>.`), when the instance was stopped `gcp-cloud-sql_instance-start: updated`, then `gcp-cloud-sql_database-create: created`, `gcp-cloud-sql_access-grant: updated`, `gcp_deploy-setup: updated`;
- when it started the instance, word for word: `This run started the shared database instance: it runs, charged by the hour, until the night stop. To stop it sooner: /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop, or the workflow self-shared-database of aleogr/aleogr (action stop).`;
- the last plan's table, fourteen rows, every action `none`: `components`, `ci`, `services`, `database` and `ci secrets` `as declared`, `protection` `protected, requires ci`; then `nothing to do`;
- the two lines `admin: https://…run.app` and `status: https://…run.app`, then `admin: https://…run.app/db`;
- the result block. Nothing else.

Write down how long the run waited for the instance (from the start's line to the next one, roughly).

**Stop and send the answer** if the run stopped with the item `database` (send its sentence), if it says `did not accept calls after 30 tries`, or if `database` is not `as declared` in its last table.

**If the session expires during the run:** reconnect, paste `P` and `S` again, `cd ~/pilot && claude`, and run `/aleogr:project-plan`. `nothing to do` with `database` `as declared`: the run had finished. Anything left: run `/aleogr:project-apply confirm=yes` once more (it reads first and makes only what is missing). Then check by direct reads, in the terminal (each prints no identifier):

```bash
gcloud sql instances describe aleogr-shared --project="$S" --format="value(settings.activationPolicy,state)"
gcloud sql databases list --instance=aleogr-shared --project="$S" --format="value(name)" | grep -cx pilot_dev
gcloud sql users list --instance=aleogr-shared --project="$S" --format="value(name)" | grep -c '^pilot-admin@'
gcloud projects get-iam-policy "$S" --flatten="bindings[].members" --filter="bindings.members:serviceAccount:pilot-admin@" --format="value(bindings.role)"
gcloud run services describe pilot-admin --region=us-central1 --project="$P" --format=json | grep -o '"name": "DB_[A-Z_]*"'
```

Expected: `ALWAYS RUNNABLE`; `1`; `1`; `roles/cloudsql.client` and `roles/cloudsql.instanceUser`, nothing else; the three names `DB_INSTANCE`, `DB_NAME`, `DB_USER`.

## 4. `admin` reaches its database

Open `admin`'s address with `/db`, signed in. Expected: **`database: ok`**. The address without `/db`: `admin: ok` (the settings' update kept the image CI deployed). In the terminal:

```bash
gcloud run services describe pilot-admin --region=us-central1 --project="$P" --format="value(spec.template.spec.containers[0].image)" | grep -c cloudrun/container/hello
```

Expected: `0` (not Google's sample image).

**Stop and send** if `/db` says `database: not reachable (the shared instance may be stopped)` while the first read of step 3's recovery says `ALWAYS RUNNABLE`: the connection was refused. Then, in the terminal, the check's last log lines, and send them with every id, number, address and e-mail replaced by `<id>`:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="pilot-admin" AND textPayload:"database check"' --project="$P" --limit=3 --format="value(textPayload)"
```

## 5. Stop the instance; the check says so

On GitHub, repository `aleogr/aleogr`: **Actions**, `self-shared-database`, **Run workflow**, branch `main`, action **stop**. Expected: the run green, its summary `aleogr-shared: stopped` (it waits for the stop, a minute or so).

Then open `admin`'s address with `/db` again. Expected: **`database: not reachable (the shared instance may be stopped)`**, within a few seconds (the check gives up after 5). **Stop and send** if it takes much longer, or shows another page (an error page of Google, a timeout).

Optional, read-only, what the Admin API answers on a stopped instance (the skills never ask it; [`DESIGN.md`](../DESIGN.md) section 18):

```bash
gcloud sql databases list --instance=aleogr-shared --project="$S" --format="value(name)"; echo "exit $?"
```

Send what it prints, with any id replaced by `<id>`.

## 6. Nothing to do, and the instance stays stopped

```
/aleogr:project-apply confirm=yes
```

Expected: fourteen rows, every action `none`, `database` `as declared` with the line `The database itself was not read: the shared instance is stopped.`, then `nothing to do`, the addresses, `status` `unchanged`. Then:

```
/aleogr:project-apply
```

Expected: the same, `nothing to do`, `unchanged`.

**Stop and send the answer** if either run proposes `gcloud sql instances patch` (deny it) or says it started the instance: nothing needs it here.

## 7. Cost check

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

Stop at that step and send its whole answer (or the terminal's text), with every id, number, e-mail and address replaced by `<id>`. A session interrupted at any point is safe to resume: every step reads before it changes, so `/aleogr:project-plan`, then `/aleogr:project-apply confirm=yes`, can always be run again. If the instance was started and you stop for the day, stop it with the workflow (step 5).

## Results

| Step | Expected | Result |
|---|---|---|
| Ready | 4c merged; `gcloud` and `gh` signed in; `~/pilot` clean on `main` | |
| 1. Plugins and Go | the six versions above; `go version` prints a version | |
| 2. Declaration and check | `updated`; the warning sentence; six files; `go` line unchanged or `.0`, no `toolchain`; the log count `0`; `deploy-admin-dev` green; `/db` `database: not configured` | |
| 3. The database | `updated`; the start's sentence when stopped; fourteen rows `none`, `nothing to do`; `admin: …/db`; how long the wait took | |
| 4. `/db` | `database: ok`; `/` `admin: ok`; image count `0` | |
| 5. Stopped | workflow green, `stopped`; `/db` `may be stopped` within a few seconds; (optional) what the list answers | |
| 6. Nothing to do | `unchanged` twice; the line `not read: … stopped`; the instance not started | |
| 7. Cost | `NEVER`; two services, maximum 2, 512Mi, minimum 0 | |
