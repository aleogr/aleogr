# Reference project, stage 4c: design of a project's database

Status: waiting for the owner's approval. Source of truth after approval: [`DESIGN.md`](../DESIGN.md) and [`CONTRACTS.md`](../CONTRACTS.md); this document is what the implementation plan is written from. It replaces the outline of part 4c in [`2026-11-19-pilot-stage-4-design.md`](2026-11-19-pilot-stage-4-design.md). The owner asked the designer to decide everything: every decision here is the designer's, listed at the end for the owner to check.

## Intent

After stage 4b, `pilot`'s two components run on Cloud Run behind the login, and neither has anywhere to keep data. Stage 4c gives a project a database without a dashboard: the owner declares that a component uses the database, and one `project-apply` and one merge later that component reaches its own database on the shared instance, with no password anywhere.

It is the last part of stage 4: with it, "running in `dev`" is complete.

## Goals

- A component is declared as using the database with one key; nothing else is typed.
- One `project-apply confirm=yes` makes everything in the cloud that the component needs, also when the shared instance is stopped, and proposes the code in one pull request.
- No password and no secret: a service reaches the database as its own service account.
- The component says plainly whether the database is reachable, and says that the shared instance may be stopped instead of failing with a connection error.
- Nothing with a new fixed cost. What a run can cost is stated before it is made.
- A declaration without a database, and a component that does not use it, behave exactly as today.

## Non-goals

- Tables, migrations, and any permission inside the database (schemas, grants): the first stage that stores something.
- Keeping one project's service out of another project's database inside the shared instance (see "What stays open").
- A dedicated instance (`hom`, `prd`), backups per project, removal of a database or a user.
- Reaching the database from the owner's computer or from CI.
- `status` using the database.

## Anti-goals

- A password, a connection string with a credential, or a database key in the repository, in an Actions secret, in a service's settings or in a skill's output.
- A run that starts the instance without saying so, or that leaves it running with no stop in sight.
- A role on the shared project that lets a project's service do more than connect to the shared instance.
- The tooling rewriting code the owner (or anyone) changed.

## Constraints

- The shared instance `aleogr-shared` (PostgreSQL 18, `db-f1-micro`, in the shared project) is stopped by default and stopped again by a scheduler at night; started, it takes about 11.5 minutes to accept connections (measured), and it is charged by the hour while it runs (about R$ 0.06). It was created with IAM database authentication on, with a public address and no authorized network: nothing reaches it except through Google's connector.
- A database and a user are created through the Cloud SQL Admin API, which needs the instance running.
- Cloud SQL's connection roles are granted on a project, not on an instance.
- No command runs SQL: what needs a statement inside the database is out of this stage.
- The tooling writes a component's starting files once and never overwrites them ([`DESIGN.md`](../DESIGN.md) section 11.5); `pilot`'s `admin` already exists, with the `main.go` the tooling wrote.
- A component's server builds its own router (`newMux`): a new file cannot add a route by itself.
- The repository of a project may be public: identifiers never go into versioned files; the shared project's id reaches a service only as a setting of that service.
- The premise of [`DESIGN.md`](../DESIGN.md) section 10.4: a run goes on by itself, waits are bounded, an answer is short.

## Approaches

How a service reaches the database:

1. **Google's Cloud SQL connector for Go, with IAM authentication (chosen).** The service's code opens the connection through the connector as its own service account; no password exists. One Go dependency for the connector and one for the PostgreSQL driver.
2. **Cloud Run's built-in Cloud SQL socket with a database password in Secret Manager.** No connector in the code, but a password to generate, store, rotate and never leak: the anti-goal.
3. **A proxy container beside the service.** No dependency in the code, but a second container in every service, with its own memory and its own settings to keep as declared.

Where the check's code comes from:

1. **`go_setup` writes it (chosen).** With `database=yes` the stack skill writes a new file with the check and its dependencies, and adds the one route to `main.go` only while that file is still exactly what the tooling wrote. The next project gets a database the same way.
2. **A change made by hand in `pilot`.** Smaller, but it proves nothing about the tooling: the next project would need the same hand.
3. **The tooling regenerates `main.go` whenever the declaration changes.** It would overwrite code that is the project's.

When the instance is stopped and something must be created:

1. **The run starts it, waits, creates, and leaves it running until the night stop, saying so (chosen).** One command; the cost has a ceiling (hours of a `db-f1-micro`, cents) and is stated in the plan and in the answer.
2. **The run stops and names the command that starts it.** Two commands and a wait in the middle: against the premise.
3. **The run starts, creates and stops it again.** Cheapest, but the owner's next step is to see the check answer, which needs the instance running.

## The design

### The declaration

A component gains one optional key, `"database": true` (absent or `false`: no database). `project-declare component=<name> database=yes|no` sets it. No new version of the declaration: the key is additive. "The declaration's rules" (identical in `project-declare` and `project-plan`) gain: `database` is a boolean; `true` needs `environments` and `cloud` (a database lives in an environment).

### What exists, and its names

| Thing | Name | Where |
|---|---|---|
| Database | `<project>_<environment>`, hyphens of the project's name written as `_` (`pilot_dev`) | the shared instance |
| Database user of a component | the component's service account, as Cloud SQL names an IAM service account user (`<project>-<component>@<project id>.iam`) | the shared instance |
| API | `sqladmin.googleapis.com`, added to the APIs of the project's own GCP project only when a component declares the database (the connector calls the Cloud SQL Admin API as the service's account, counted against that project) | the project's GCP project |
| Connection roles of that account | `roles/cloudsql.client` and `roles/cloudsql.instanceUser`, with a condition that limits them to the shared instance where Cloud SQL supports one; a binding with or without the condition counts as granted, so the row never reads `differs` over the form | the shared project |
| Settings of the service | `DB_INSTANCE` (the instance's connection name), `DB_NAME`, `DB_USER` | the Cloud Run service |
| Code | `<path>/db.go` (the check), the route `GET /db` in `main.go`, two requirements in `go.mod` | the project's repository |

One database per project and environment, shared by the project's components that use it; one user per component.

### Skills

- `aleogr-db-gcp-cloud-sql` gains the `shared` mode of the db family ([`CONTRACTS.md`](../CONTRACTS.md)):
  - `gcp-cloud-sql_database-describe`: for a project and environment, whether the instance is running, whether the database exists, which of the given accounts are users, and whether each has the two roles. With the instance stopped it reports what a stopped instance still lets it read and marks the rest `not read`; that is not a failure.
  - `gcp-cloud-sql_database-create`: creates the database when missing. It never starts the instance: on a stopped one it ends `pending`.
  - `gcp-cloud-sql_access-grant`: for one service account, creates the IAM user when missing and grants the two roles when missing. A binding refused for an account just created is waited for by the bounded wait.
- `gcp_deploy-setup` and `gcp_deploy-describe` gain `env=<NAME>=<value>[,…]` per component: the settings are part of "as declared" (difference `env`), set without touching the image. A setting the tooling did not write is left alone.
- `go_setup` gains `database=yes`:
  - a new component gets the starting files with the route already there, plus `db.go`;
  - an existing component gets `db.go` when it is missing; its `main.go` is replaced by the variant with the route **only when it is byte for byte the file the tooling wrote**; otherwise `main.go` is left alone and the result carries the item `route`, whose `how` is the one line to add;
  - the two requirements are added to `go.mod` with `go get <module>@<version>` (versions pinned in `defaults.json`), which also writes `go.sum`, run with the local toolchain only (`GOTOOLCHAIN=local`). After it the skill checks that the `go` line of `go.mod` is still the declared version and that no `toolchain` line appeared: if either changed, it restores `go.mod` and `go.sum` and ends `failed` with one sentence (the pinned modules must not need a newer Go than the component declares). This needs Go, at least the component's version, where the skill runs; without it the skill ends `failed` with one sentence.
- `tools-check` gains `command=go`.

### The check

`GET /db` in the component, behind the login like every route:

- the settings are missing: `503`, `database: not configured`;
- a connection through the connector as the service's account and one `SELECT 1`, within 5 seconds: `200`, `database: ok`;
- anything else: `503`, `database: not reachable (the shared instance may be stopped)`. The error itself goes to the service's log, never to the page.

### The plan and the run

- `project-plan`, when a component declares the database, counts `sqladmin.googleapis.com` among the APIs of the row `apis` (the existing wait for a just-enabled API covers it), and gains the row `database` after `services`: `follows the services`; `missing: <what>` / `create`; `differs: <what>` / `update`; `as declared` / `none`. "As declared" is: each such service has the three settings, each account has the two roles, and, when the instance is running, the database exists and each account is a user. With the instance stopped and the settings and roles right, the row is `as declared` and a line under the table says the database itself was not read because the instance is stopped. The settings are written last by the run, so they mark that the rest was made.
- When the row has `create` or `update` and the instance is stopped, a line under the table says that `project-apply` starts the instance, that it then runs, charged by the hour, until the night stop, and that the start takes about twelve minutes.
- `components` shows `to generate` while `db.go` is missing; `ci` and `ci secrets` are unchanged.
- `project-apply confirm=yes`, after the services exist: when the instance is stopped, `gcp-cloud-sql_instance-start`, then a bounded wait (30 seconds a try, at most 30 tries: the start was measured at 11.5 minutes, so this one wait is longer than the usual ten tries) until the start's operation is done and a list of the instance's databases answers: the instance's own state reads as running from the first moment, so it is not the signal; then `database-create`, `access-grant` for each component, `gcp_deploy-setup` with the settings; then the plan; then `go_setup database=yes` and the pull request. The answer says, when the run started the instance, that it is running until the night stop and how to stop it sooner.
- After the merge CI deploys the component with the check, as any change.

### The owner's run, on `pilot`

`/aleogr:project-declare component=admin database=yes` → `/aleogr:project-apply confirm=yes` (the declaration's pull request) → merge → `/aleogr:project-apply confirm=yes` (starts the instance if needed, makes the database, the user, the roles and the settings, proposes the code) → merge → open `admin`'s address with `/db`: `database: ok`. Then stop the instance (the workflow `self-shared-database` or the skill): `/db` says the instance may be stopped.

### Cost

No new fixed cost. The instance already costs its disk and address while stopped. A run that starts it adds the hours until the night stop: at about R$ 0.06 an hour, less than R$ 1.50 a day. The connector and the roles cost nothing.

## What stays open (recorded in `DESIGN.md` section 18)

- **Inside the shared instance, a project's user can connect to another project's database.** PostgreSQL lets any user connect to any database unless that is revoked with a statement, and no command here runs SQL. Users created through the API may also belong to Cloud SQL's administrative role, which would let them do more than connect (to be read in the reference by the builder and recorded). With no table anywhere this exposes nothing; it must be closed in the stage that creates the first table (with migrations, which need a way to run SQL anyway).
- The user has no permission to create anything in its own database yet: same stage.
- A long wait (the instance's start) in a terminal that can expire: the answer of the run is lost if the session drops, as seen in stage 4b-2.

## Decisions made by the designer, for the owner to check

- One key per component, `"database": true`; one database per project and environment, one user per component.
- No password: Google's connector with IAM authentication.
- `go_setup` writes the check; it replaces `main.go` only while it is still the file the tooling wrote.
- `project-apply` starts a stopped instance by itself, says so, and leaves it running until the night stop.
- The connection roles are on the shared project (Cloud SQL has no narrower place), limited to the instance by a condition where one is supported.
- The settings of a service are the marker that its database was made, so a plan is useful with the instance stopped. A database deleted by hand while the instance is stopped is therefore not seen until the instance runs: accepted.
- The Cloud SQL Admin API is enabled in a project's own GCP project only when one of its components uses the database.
- The roles on the shared project are granted by whoever runs `project-apply` (the owner, who owns the shared project); a refusal ends the step with one sentence, as every grant does.
- The wait for the instance's start is up to 15 minutes, the one wait longer than the rule's five.
- Isolation between projects inside the instance is left open, stated, until the first table.

## Left to the builder

- The exact commands and flags, checked against the reference: `gcloud sql databases` and `users` (the type of an IAM service account user and how its name is written), what each reads or refuses on a stopped instance, and how "accepts calls" is read after a start; recorded in `PROVIDER-FACTS.md`.
- Whether an IAM condition can limit `roles/cloudsql.client` and `roles/cloudsql.instanceUser` to one instance, and its exact expression; if not, the binding is unconditioned and section 18 says so.
- The connector's and the driver's modules and versions, and the smallest code of the check; whether the pinned `go get` leaves `go.mod` stable across runs.
- How `main.go` is recognised as "still the file the tooling wrote" (the template with the component's name filled in, compared byte for byte).
- The scenario lists and fixtures; a fake `go` in the harness.
