# Reference project, stage 4c: a project's database — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a component declared with `"database": true` reaches its own database on the shared Cloud SQL instance as its service account, with no password, made by one `project-apply`, and answers at `GET /db` whether the database is reachable.

**Architecture:** `aleogr-db-gcp-cloud-sql` gains the `shared` mode of the db family (`gcp-cloud-sql_database-describe`, `gcp-cloud-sql_database-create`, `gcp-cloud-sql_access-grant`). The service skills carry a service's settings (`env=`). `go_setup database=yes` writes the check and its dependencies. `project-declare` gains the key, `project-plan` the row `database`, and `project-apply` starts a stopped instance, waits, and makes what is missing.

**Tech Stack:** Claude Code plugin skills (Markdown), `gcloud`, `gh`, Go (`cloud.google.com/go/cloudsqlconn`, `github.com/jackc/pgx/v5`), the bash harness under `.claude-plugin/tests/`.

**Spec:** [`2026-11-26-pilot-stage-4c-design.md`](2026-11-26-pilot-stage-4c-design.md). Facts checked against primary sources on 2026-11-26: `.superpowers/sdd/2026-11-26-pilot-stage-4c/facts.md` (scratch, not versioned; each implementer reads the sections its task names; what a task relies on goes to `docs/PROVIDER-FACTS.md` in Task 6, marked as read in the reference, never as seen in a real run). Models of style: `gcp_deploy-setup`, `gcp_access-grant`, `gcp-cloud-sql_instance-describe`, `github_variables-set`.

## Global Constraints

- **The premise** (`docs/DESIGN.md` section 10.4): a run goes on by itself; waits are bounded polls with `sleep 30`; a stop only before something irreversible, exposing or with a cost; one command per thing left; a short answer with one result block; never a question.
- **No password and no secret anywhere.** No skill creates a database user with a password, generates one, reads one, or writes a connection string with a credential. The only user type created is the IAM service-account type.
- **No new fixed cost.** No instance is created; the shared instance's tier, storage and flags are never changed by this plan. The only cost a run can add is the instance's running hours, and the plan and the answer say so before and after.
- **The instance is started only by `project-apply confirm=yes`, only when something must be created or changed in it, and the answer says it is running until the night stop.** No leaf skill of this plan starts or stops the instance. Nothing stops it.
- **The tooling never overwrites changed code.** `main.go` is replaced only when it is byte for byte the tooling's own template with the component's name filled in; `db.go` is written only when missing; `go.mod`/`go.sum` are changed only by `go get` of the two pinned modules followed by `go mod tidy`.
- Everything versioned is in English. The repository is public: no organization, folder, billing account or project identifier or number, no e-mail, no OAuth client id, no secret. Fixtures use only fictitious values (`demo`, `aleogr-dev-demo-ab12`, `aleogr-shared-ab12`, `123456789012`, `example-org/example-repo`, addresses at `example.com`, `us-central1`). `aleogr-sandbox` and `pilot` only under `docs/`.
- No e-mail of any kind in a result block (a service account's address included, except inside the existing `ciVariables` of `project-plan`); the answer's text may name an account.
- No `SKILL.md` has `name:` in its frontmatter. Every skill validates before any command, shows each command before running it, runs only the commands (or invokes only the skills) its steps list, and ends with exactly one fenced `aleogr-result` block. `pending` means nothing was changed. A missing argument is `failed`, never a question. Each failure has one prescribed sentence, written word for word; no word of `gcloud`'s, `gh`'s or `go`'s answer is repeated.
- Every skill another skill invokes holds, as the first paragraph under `## Result block`, the paragraph "When another skill invoked this one …" byte-identical to the one in the skills that have it. Orchestrators keep the sentence that names their answer as the next output on every end.
- "The declaration's rules" stay byte-identical in `project-declare` and `project-plan` (Task 4 changes both in one commit and proves it).
- A declaration with no component using the database behaves exactly as before this plan: no new row, read or invocation. Every existing scenario passes, changed only where this plan changes the behaviour it pins.
- Names and values: database `<project>_<environment>` with every `-` of the project's name written `_`; user `<project>-<component>@<project id>.iam`; roles `roles/cloudsql.client` and `roles/cloudsql.instanceUser` on the shared project, without a condition, granted with `--condition=None`; a binding with or without a condition counts as granted; API `sqladmin.googleapis.com` in the project's own GCP project; settings `DB_INSTANCE` (`<shared project id>:<region>:<instance>`), `DB_NAME`, `DB_USER`; instance name from `defaults.json` `platform.database.instance`; the shared project found by its labels as the platform skills find it.
- Go: modules and versions from `defaults.json` `stacks.go.database` — `cloud.google.com/go/cloudsqlconn` `v1.27.1`, `github.com/jackc/pgx/v5` `v5.13.0`, `minVersion` `1.26`. A component with `"database": true` declares Go `1.26` or later.
- Waits: the usual bounded poll is 10 tries; the one wait for the instance's start is 30 tries (the start was measured at 11.5 minutes).
- Do not change the root `README.md`; never create `.github/README.md`; no skill, plugin or workflow beyond this plan. `docs/DESIGN.md` states decisions in the present tense; section 16 only gains real rejected alternatives.
- Commits: `git commit -m … -- <paths>` (a pathspec, always); messages end with the two lines the workspace's constraints file gives; no other model name anywhere. `.superpowers/` is never committed.
- Scenarios: `bash .claude-plugin/tests/run.sh <scenario>`; four at a time, two at a time for `project-apply-*`. Each run costs model usage. Expectations pin content; failure scenarios pin a word of the prescribed sentence. `COUNT` means "at least": a limit is pinned by an (N+1)th response that succeeds.

## Review Focus

1. A password or a credential appearing anywhere. Tests: `sql-access-apply` pins the user's type in the creating command and `NOT_CALLED --password|set-password|--prompt-for-password`; `go-setup-database-new` pins `FILE_NOT … password` on `db.go` (Tasks 1, 3).
2. The instance started when nothing needs it, or by a plan. Tests: `project-plan-database-missing-stopped` pins `NOT_CALLED instances patch`; `project-apply-database-as-declared-stopped` (nothing to do, instance stopped) pins the same (Tasks 4, 5).
3. A run that starts the instance and never says so, or waits without end. Tests: `project-apply-database-create-stopped` pins the sentence in the answer and `ORDER` start → wait → create; `-start-wait-limit` pinned by an accepting 31st response (Task 5).
4. Changed code overwritten. Tests: `go-setup-database-existing-changed-main` (`main.go` differs by one byte → untouched, item `route`); `-existing-db-present` (`db.go` present → untouched) (Task 3).
5. The Go version of the component moved by the dependencies. Tests: `go-setup-database-go-line-moved` (the fake `go` rewrites the `go` line → restored, `failed`) (Task 3).
6. A project with no database behaving differently. Tests: every existing `project-plan-*`/`project-apply-*` scenario unchanged and passing; `project-plan-database-not-declared` pins `NOT_CALLED ^sql ` (Tasks 4, 5).
7. A role wider than the two, or granted on the wrong project. Tests: `sql-access-apply` pins both roles, the shared project as the binding's target, `--condition=None`, and `NOT_CALLED roles/(owner|editor|cloudsql.admin|cloudsql.editor)` (Task 1).
8. A plan that is useless while the instance is stopped. Tests: `sql-database-describe-stopped` (`not read`, `unchanged`, not `failed`); `project-plan-database-as-declared-stopped` (`as declared`, the line under the table) (Tasks 1, 4).

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/skills/gcp-cloud-sql_database-describe`, `_database-create`, `_access-grant`, `plugin.json` (0.5.0) | the database, the user, the roles |
| `.../aleogr-cloud-gcp/skills/gcp_deploy-describe`, `gcp_deploy-setup`, `plugin.json` (0.7.0) | a service's settings |
| `.../aleogr-stack-go/skills/go_setup`, `files/db.go.tmpl`, `files/db_test.go.tmpl`, `files/main-database.go.tmpl`, `plugin.json` (0.3.0); `.claude-plugin/tests/bin/go`, tests README | the check and its dependencies; a fake `go` |
| `.../aleogr/defaults.json`, `skills/project-declare`, `project-plan`, `tools-check` | the key, the rule, the row, `command=go` |
| `.../aleogr/skills/project-apply`, `plugin.json` (0.12.0) | the run |
| `docs/DESIGN.md`, `CONTRACTS.md`, `PROVIDER-FACTS.md`, `cloud-shell.md`, `.claude-plugin/plugins/README.md`, `marketplace.json` descriptions, `docs/plans/2026-11-26-pilot-stage-4c-run.md` | documents |

Tasks 1, 2 and 3 touch disjoint paths and run in parallel. Task 4 follows them. Task 5 follows 4. Task 6 last.

---

### Task 1: The database, the user and the roles

**Files:**
- Create: the three skills under `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/skills/`
- Modify: that plugin's `plugin.json` (0.5.0) and its description in `marketplace.json`
- Test: scenarios `sql-database-describe-*`, `sql-database-create-*`, `sql-access-*`

**Interfaces:**
- Produces: `gcp-cloud-sql_database-describe sharedProjectId= instance= project= environment= accounts=<service account e-mail>[,…]`. Reads the instance (the same read and state rule as `gcp-cloud-sql_instance-describe`: `stopped`, `starting`, `running`), the shared project's IAM policy, and, only when the state is `running`, the instance's databases and users. Outputs: `instanceState`; `database` (`<project>_<environment>` as computed); `databaseExists` (`true`/`false`, or `null` when not read); `users`: a list of `{ "account": <index of the account in the argument, from 1>, "user": true|false|null, "client": true|false, "instanceUser": true|false }` (no address in the block); `read` (`true` when databases and users were read). Status `unchanged` or `failed`. A stopped or starting instance is not a failure. A read of databases or users that fails although the state is `running` is `failed` (one sentence).
- Produces: `gcp-cloud-sql_database-create sharedProjectId= instance= project= environment= mode=plan|apply`. Instance not `running`: `pending`, item `instance` (`how`: `/aleogr:project-apply confirm=yes` starts it), no other command. Database exists: `unchanged`. Otherwise `gcloud sql databases create <name> --instance=<instance> --project=<sharedProjectId> --quiet`, then one list to verify. A create that fails is followed by one list: the database may exist. Statuses `would-create`, `created`, `unchanged`, `pending`, `failed`.
- Produces: `gcp-cloud-sql_access-grant sharedProjectId= instance= account=<service account e-mail> mode=plan|apply`. `account` matches `^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$`; the user's name is the address without `.gserviceaccount.com`. The two roles are read from the policy and granted when missing (`gcloud projects add-iam-policy-binding <sharedProjectId> --member=serviceAccount:<account> --role=<role> --condition=None --quiet`), whatever the instance's state; a refusal that names an account that does not exist yet is waited for by the bounded poll. The user is created only when the instance is `running` and the user is missing (`gcloud sql users create <user> --instance=<instance> --project=<sharedProjectId> --type=cloud_iam_service_account --quiet`); on an instance not running, with the user unknown, the run ends `pending` with the item `instance` after granting what it could (then `updated` when a role was granted). Outputs `user` (`true`/`false`/`null`), `client`, `instanceUser`, `granted` (role names), `userCreated`. Statuses `would-update`, `updated`, `unchanged`, `pending`, `failed`.

- [ ] **Step 1: Read facts sections 1, 2, 3, 7 and 9; check every flag against `gcloud sql databases --help`, `gcloud sql users create --help`, `gcloud projects add-iam-policy-binding --help` here.** What the facts could not verify (the Admin API's answers on a stopped instance; the texts for "already exists") is decided by state and by a read after a failure, never by an error's text: say so in the skills.
- [ ] **Step 2: Scenarios first.** `sql-database-describe-running-as-declared`, `-running-missing` (no database, one account not a user, one role missing), `-stopped` (Review Focus 8), `-starting`, `-read-refused`, `-invalid`; `sql-database-create-plan`, `-apply`, `-exists`, `-stopped` (`pending`, `NOT_CALLED databases create|instances patch`), `-create-failed-then-read`, `-invalid` (a project name whose database name would not fit PostgreSQL's 63 characters cannot happen: say why and pin the hyphen→underscore mapping with `my-app` → `my_app_dev`); `sql-access-plan`, `-apply` (Review Focus 1 and 7), `-unchanged`, `-roles-only-stopped` (roles granted, user not read, `updated` + item `instance`), `-binding-wait` (two refusals, `COUNT 2 ^sleep 30`), `-binding-wait-limit`, `-policy-has-conditions` (a policy with an unrelated conditional binding: the grant still passes `--condition=None`), `-conditional-binding-counts` (the role bound under a condition → counted as granted, no command), `-invalid`.
- [ ] **Step 3: Run four of them; they fail.**
- [ ] **Step 4: Write the three skills.**
- [ ] **Step 5: Run all of them and two existing `sql-*` scenarios.**
- [ ] **Step 6: Commit** — scenarios first, then `Add the skills of a project's database on the shared instance`.

### Task 2: A service's settings

**Files:**
- Modify: `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_deploy-describe/SKILL.md`, `gcp_deploy-setup/SKILL.md`, the plugin's `plugin.json` (0.7.0) and its description in `marketplace.json`
- Test: scenarios `deploy-describe-*`, `deploy-setup-*`

**Interfaces:**
- Produces: both skills gain the optional argument `env=<component>:<NAME>=<value>[;<component>:<NAME>=<value>…]` (`;` between entries; names `^[A-Z][A-Z0-9_]{0,63}$`; values of `a-z`, `A-Z`, `0-9`, `-`, `_`, `.`, `:` and `@`, 1 to 200 characters; each component is one of `components`). Absent: today's behaviour byte for byte.
- `gcp_deploy-describe`: a service whose template lacks a given setting, or holds another value for it, has the difference `env`. Settings not given are ignored (never a difference).
- `gcp_deploy-setup`: for an existing service with the difference `env`, one `gcloud run services update <service> --update-env-vars=^##^<NAME>=<value>##… --region --project --quiet`, alone (never with `--image`, never with a security flag); a service created in the run gets the settings in the same way right after its creation. Values never appear in the result block (names only, in `envSet`).

- [ ] **Step 1: Read facts section 8; check `--update-env-vars` and the `^##^` delimiter in `gcloud topic escaping` and `gcloud run services update --help`.**
- [ ] **Step 2: Scenarios first.** `deploy-describe-env-as-declared`, `-env-missing`, `-env-other-value`, `-env-extra-ignored`; `deploy-setup-env-apply` (one update with the three settings, `NOT_CALLED --image`, `RESULT_NOT aleogr-shared-ab12`), `-env-unchanged`, `-env-with-create`, `-env-invalid` (a value with a space; a component not in `components`), `-env-update-refused`. Every existing scenario of the two skills passes unchanged.
- [ ] **Step 3: Run four; they fail.**
- [ ] **Step 4: Change the two skills.**
- [ ] **Step 5: Run every `deploy-describe-*` and `deploy-setup-*`.**
- [ ] **Step 6: Commit** — scenarios first, then `Carry a service's settings in the service skills`.

### Task 3: The check and its dependencies

**Files:**
- Create: `.claude-plugin/plugins/aleogr-stack-go/files/db.go.tmpl`, `db_test.go.tmpl`, `main-database.go.tmpl`; `.claude-plugin/tests/bin/go`
- Modify: `go_setup/SKILL.md`, the plugin's `plugin.json` (0.3.0) and its description in `marketplace.json`; `.claude-plugin/tests/README.md`
- Test: scenarios `go-setup-*`, `harness-selftest-*`

**Interfaces:**
- Produces: `go_setup` gains `database=yes|no` (default `no`: today's behaviour byte for byte) and, required with `yes`, `modules=<module>@<version>[,…]` and `minVersion=<major.minor>`. With `yes`:
  - `version` below `minVersion`: `failed`, one sentence, nothing written.
  - a new component: `main.go` from `main-database.go.tmpl` (the plain template plus the one line `mux.HandleFunc("GET /db", dbCheck)`), `db.go`, `db_test.go`, and the other starting files;
  - an existing component: `db.go` and `db_test.go` each written only when missing; `main.go` replaced by the database variant only when its content equals, byte for byte, the plain template with the component's name filled in; equal to the database variant already: left; anything else: left, and the result carries `{ "item": "route", "reason": "manual", "how": "add the line mux.HandleFunc(\"GET /db\", dbCheck) to the router in <path>/main.go" }` (the run still ends `created`/`unchanged` by the files);
  - then, when `go.mod` lacks a `require` of any of the modules: in the folder, `go get <module>@<version>` for all of them in one command, then `go mod tidy`; then the `go` line of `go.mod` must still be the component's version and no `toolchain` line may exist: otherwise `go.mod` and `go.sum` are put back as they were (the skill reads both before the command) and the run ends `failed`;
  - `go` missing (`go version` cannot start): `failed`, one sentence, before any file is written.
  - Outputs gain `database` (`written` / `would-write` / `present` / `not-asked`), `route` (`added` / `present` / `manual` / `not-asked`), `modules` (`added` / `present` / `not-asked`).
- The check (`db.go`), exactly this behaviour: `GET /db`; `DB_INSTANCE`, `DB_NAME` or `DB_USER` empty → `503`, `database: not configured`; otherwise a dialer with automatic IAM authentication and lazy refresh, one connection through it with `pgx`, `SELECT 1`, everything under one 5-second deadline, the connection and the dialer closed → `200`, `database: ok`; any error → `503`, `database: not reachable (the shared instance may be stopped)`, the error written to the log only. No password, no DSN with a credential, no global connection pool.
- The harness: `bin/go` logs each call as `go <arguments>` and plays numbered responses like the other fakes; `go get` and `go mod tidy` may be given a response file that the fake copies over `go.mod`/`go.sum` in the working folder (describe the convention in the README).

- [ ] **Step 1: Read facts sections 5 and 6.** Write the three templates and build them for real: in a scratch folder outside the repository, a module with `go 1.27` (the Go command downloads the toolchain), the two modules at the pinned versions, `go vet ./...` and `go test ./...` green, and `gofmt -l` empty. Record the commands and their results in the report. `db_test.go` tests the not-configured answer and that the route is registered.
- [ ] **Step 2: Scenarios first.** `go-setup-database-new`, `-database-existing` (plain `main.go` → replaced; `db.go` written; `ORDER go get → go mod tidy`; both modules with versions in the one `go get`), `-database-existing-changed-main` (Review Focus 4), `-database-existing-db-present`, `-database-already` (everything present → `unchanged`, `NOT_CALLED ^go (get|mod)`), `-database-go-line-moved` (Review Focus 5: `FILE` pins the `go` line restored), `-database-toolchain-line`, `-database-go-missing`, `-database-version-too-old`, `-database-plan` (nothing written, `NOT_CALLED ^go (get|mod)`), `-database-with-dockerfile`; `harness-selftest-go`. Every existing `go-setup-*` passes unchanged.
- [ ] **Step 3: Run four; they fail.**
- [ ] **Step 4: The fake `go` and the README; then the skill.**
- [ ] **Step 5: Run every `go-setup-*` and `harness-selftest-*`.**
- [ ] **Step 6: Commit** — the templates and the fake, the scenarios, then `Let go_setup write the database check of a component`.

### Task 4: The key, the rule and the plan's row

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/defaults.json`, `skills/project-declare/SKILL.md`, `skills/project-plan/SKILL.md`, `skills/tools-check/SKILL.md`
- Test: scenarios `project-declare-*`, `project-plan-*`, `tools-*`

**Interfaces:**
- Consumes: Tasks 1, 2, 3.
- Produces: `defaults.json` gains `stacks.go.database`: `{ "minVersion": "1.26", "modules": ["cloud.google.com/go/cloudsqlconn@v1.27.1", "github.com/jackc/pgx/v5@v5.13.0"] }`.
- Produces: "The declaration's rules" (both skills, identical): a component may have `"database"`, a boolean; `true` needs `cloud` and `environments`, and the component's `version` at least the stack's `minVersion` for the database (read from the defaults by the skills; the rule names the key, not the number).
- Produces: `project-declare component=<name> database=yes|no` (sets or removes the key; an existing component keeps its other keys).
- Produces: `tools-check command=go`: `go version` runs → `ok`; otherwise `failed` with the fix.
- Produces: `project-plan`, when at least one component has `"database": true`:
  - the API list of the row `apis` also holds `sqladmin.googleapis.com`;
  - `components`: `go_setup … database=yes modules=… minVersion=… mode=plan` for those components; `to generate` when `db.go`, the route or a module is missing;
  - the row `database`, after `services` and before `ci secrets`. It reads the shared project by its labels (the read the platform skills make) and invokes `gcp-cloud-sql_database-describe` and, for the settings, passes `env=` to `gcp_deploy-describe`. States: `follows the services` (a service of a database component is missing, or the rows before have an action); `missing: <words from: api, database, user, roles, settings>` / `create`; `differs: settings` / `update`; `as declared` / `none`. With the instance not running: the database and the users are not judged; when roles and settings are right the row is `as declared`, with the line under the table `The database itself was not read: the shared instance is stopped.`; when something is missing and the instance is stopped, the line `project-apply starts the shared instance (about twelve minutes); it then runs, charged by the hour, until the night stop.`
  - no shared project found: the row is `needs the shared platform` / `none`, with the line naming `/aleogr:platform-plan`.
  - outputs gain `database` (`{ "name", "instanceState", "start": true|false }`, or `null`) — `start` true when `project-apply` would have to start the instance.
- Without a database component: no new row, read or invocation.

- [ ] **Step 1: Scenarios first.** `project-declare-component-database` (key written), `-database-off` (removed), `-database-no-environment` (`failed`), `-database-version-too-old`; `tools-check-go-ok`, `-go-missing`; `project-plan-database-not-declared` (Review Focus 6), `-database-follows-services`, `-database-missing-stopped` (Review Focus 2; the cost line), `-database-missing-running`, `-database-as-declared-running` (fourteen rows, `nothing to do`), `-database-as-declared-stopped` (Review Focus 8), `-database-settings-differ`, `-database-no-shared-project`, `-database-code-missing` (`components` `to generate`). Existing scenarios untouched.
- [ ] **Step 2: Run six; they fail.**
- [ ] **Step 3: Change `defaults.json` and the three skills; prove "The declaration's rules" identical with a script.**
- [ ] **Step 4: Run every `project-declare-*`, `tools-*` and `project-plan-*`; report each with its run count and any form defect.**
- [ ] **Step 5: Commit** — scenarios first, then `Declare a component's database and plan it`.

### Task 5: The run

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md`, the plugin's `plugin.json` (0.12.0) and its description in `marketplace.json`
- Test: scenarios `project-apply-*`

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces: `project-apply confirm=yes`, in the environment part, after the services' step and before the CI secrets, when the plan's row `database` has `create` or `update`:
  1. when the plan's `database.start` is true: `gcp-cloud-sql_instance-start`, then the bounded wait of 30 tries on `gcp-cloud-sql_database-describe` until `read` is true (a starting instance is not read); the limit passed: the run stops, `updated`, item `database` (`how`: wait some minutes, `/aleogr:project-plan`, apply when it shows the instance running), and the answer still says the instance was started;
  2. `gcp-cloud-sql_database-create … mode=apply`;
  3. `gcp-cloud-sql_access-grant … mode=apply` for each database component;
  4. `gcp_deploy-setup` with `env=` (the settings last: they mark that the rest was made);
  then the existing steps (CI secrets, the plan, the files, the proposal). `go_setup` is invoked with `database=yes modules=… minVersion=…` for the database components, so the proposal carries `db.go`, the route and the dependencies; `go.sum` and `db_test.go` are among the proposed paths.
- The APIs' step enables `sqladmin.googleapis.com` with the others (the existing wait covers it).
- The answer, when the run started the instance, holds exactly: `This run started the shared database instance: it runs, charged by the hour, until the night stop. To stop it sooner: /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop, or the workflow self-shared-database.` (check the real invocation name of the stop skill and of the workflow, and correct the sentence to them).
- A stop of any of the four steps: one item `database`, with a `how` the owner can run; nothing proposed after it; no "apply again" on a guess.
- `project-apply` runs no command of its own beyond `sleep 30`.

- [ ] **Step 1: Scenarios first.** `project-apply-database-create-running` (`ORDER` create → grant → settings → the proposal; `NOT_CALLED instances patch`), `-database-create-stopped` (Review Focus 3), `-database-start-wait-limit`, `-database-as-declared-stopped` (Review Focus 2: `nothing to do`), `-database-grant-refused` (stop, item `database`, `NOT_CALLED pr create`), `-database-code-only` (the cloud as declared, `db.go` missing → only the proposal), `-database-route-manual` (`main.go` changed → the proposal without `main.go`, the item `route` carried). Existing scenarios untouched.
- [ ] **Step 2: Run four; they fail.**
- [ ] **Step 3: Change `project-apply`.**
- [ ] **Step 4: Run every `project-apply-*` (two at a time); report each with its run count and any form defect. Run `project-apply-database-create-stopped` five times.**
- [ ] **Step 5: Commit** — scenarios first, then `Make a component's database in project-apply`.

### Task 6: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md` (6.4 the database of a project as built; 6.8 what a project adds to the shared platform; 11.5 the key; 12 the row and the run; 16; 17; 18), `docs/CONTRACTS.md` (the db family's `shared` actions as built: no password, no `secretRef`; `env=`; `go_setup database=`; `tools-check command=go`), `docs/PROVIDER-FACTS.md`, `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`
- Create: `docs/plans/2026-11-26-pilot-stage-4c-run.md`

- [ ] **Step 1: Documents**, from the built files. Section 16 gains the real rejected alternatives (a password in Secret Manager; a proxy container; the tooling regenerating `main.go`; the run stopping, or stopping the instance again). Section 18 gains what stays open: a project's user can connect to another project's database inside the instance until the first table's stage closes it; the user can create nothing yet; the connection roles are not narrowed by a condition; a long wait in a terminal that can expire; everything the facts could not verify, listed as what the first real run must prove (the Admin API's answers on a stopped instance; the connector across projects with the API on in both; that an IAM user with no grant runs `SELECT 1`; the check's answer on a stopped instance within its deadline; the Go toolchain download in Cloud Shell).
- [ ] **Step 2: The run checklist**, short, for someone who does not know the console, same shape as the 4b-2 one: update the plugins; `go version` in Cloud Shell; `/aleogr:project-declare component=admin database=yes`; `/aleogr:project-apply confirm=yes` and the merge of the declaration; `/aleogr:project-plan` (expected rows, the cost line); `/aleogr:project-apply confirm=yes` (what it starts and makes; keep the tab in front: about twelve minutes; what to do if the session expires — a plan, and the direct reads); the merge of the code; `admin`'s address with `/db` → `database: ok`; stop the instance (the workflow) and `/db` again → the stopped sentence within a few seconds; `/aleogr:project-apply` → `nothing to do`; the cost check (the instance stopped again). Stop rules for each thing only the run can prove. Never paste an address, an id, a number or an e-mail. A results table.
- [ ] **Step 3: Check every relative link and anchor, and that no identifier, e-mail or client id was written.**
- [ ] **Step 4: Commit** — `Document a project's database` and `Add the stage 4c run checklist`.
