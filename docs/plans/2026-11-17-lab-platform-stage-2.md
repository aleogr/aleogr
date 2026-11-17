# Lab Platform, Stage 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the shared PostgreSQL instance to the lab platform: created stopped, started and stopped by skills and by a manual workflow, and stopped every night by Google Cloud.

**Architecture:** A new family plugin, `aleogr-db-gcp-cloud-sql`, holds five skills that run `gcloud`. The orchestrator's `platform-plan` and `platform-apply` gain two items (`database switch`, `database instance`) driven by new values in `defaults.json`. A manually triggered workflow in `aleogr/aleogr` starts and stops the instance through workload identity federation. Skills are tested headless against the fake `gcloud` of stage 1.

**Tech Stack:** Claude Code plugins (Markdown skills, JSON manifests), `gcloud` CLI, Bash test harness, one GitHub Actions workflow.

**Spec:** [`2026-11-17-lab-platform-stage-2-design.md`](2026-11-17-lab-platform-stage-2-design.md). Conventions: [`DESIGN.md`](../DESIGN.md), [`CONTRACTS.md`](../CONTRACTS.md) section 1, and the stage 1 skills in `.claude-plugin/plugins/` (copy their structure: Arguments, Validate first, Steps, Result block).

## Global Constraints

- Everything versioned is in English.
- The repository is public: no organization ID, folder ID, billing account ID, project ID, project number, e-mail or secret in any file. Fixtures use fictitious values (project `aleogr-lab-shared-zz99`, number `123456789012`, account `owner@example.com`).
- Skill folder names: family skills `<provider>_<object>-<verb>` (one underscore), here `gcp-cloud-sql_instance-<verb>`. No `name:` in any `SKILL.md` frontmatter; the `description` names the provider and says when to use the skill.
- Every skill: validates its arguments before any command, checks before creating (idempotent), shows each command before running it, ends with a verification and with exactly one fenced `aleogr-result` JSON block.
- Modes: `plan` reports and changes nothing; `apply` executes. Default is `plan`.
- Every value with a comma, a space, a quote or `&` is double-quoted in the commands the skills show and run (PowerShell splits unquoted values at commas). A JSON body is never inline: it is a file of the plugin, referenced with `${CLAUDE_PLUGIN_ROOT}`.
- Every command that changes something carries `--quiet`.
- On Windows, when `gcloud` fails to start, the skills use `gcloud.cmd` (same sentence as in the stage 1 skills).
- Result blocks never hold a project number, an e-mail, or organization, folder or billing identifiers. The shared project id is allowed (as in stage 1).
- Fixed names: instance `aleogr-lab`; custom role `aleogrLabSqlSwitch`; service account `aleogr-lab-sql-switch`; pool `github`; provider `aleogr`; jobs `aleogr-lab-stop-weeknight`, `aleogr-lab-stop-weekend`; GitHub secrets `LAB_GCP_PROJECT_ID`, `LAB_GCP_WIF_PROVIDER`, `LAB_GCP_SWITCH_ACCOUNT`.
- Fixed cost wording, wherever the instance's cost is stated: `about R$ 50 per month while stopped`.
- Do not create plugins, skills, hooks or workflows beyond the ones listed here.
- Commit trailers, on every commit:
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01NLyiUHJqDCFUtZDW4kD2Yk`. No other model name anywhere.
- Tests: `bash .claude-plugin/tests/run.sh <scenario>` prints `PASS <scenario>`. Each run costs model usage: run the scenarios of the task at hand, not the whole suite, except in Task 8.

## Review Focus

- The instance exists and is running because the owner started it: `instance-create` and `platform-apply` report it and never stop it.
- Describing the instance fails for a reason other than "does not exist" (no permission, API disabled): the result is `failed`, never "missing", so nothing tries to create a second instance.
- `instance-create mode=apply` without `confirm=yes`, called directly: nothing is created and the result says how to confirm.
- The switch is half created (role and account exist, jobs missing): `instance-switch-setup` creates only what is missing.
- A scheduler job exists with a schedule different from the defaults: it is updated, not duplicated and not left alone.
- `instance-start` on an instance that does not exist, and `instance-stop` on a stopped one: `failed` and `unchanged`, with no change command.

## File Structure

```
.claude-plugin/
├── marketplace.json                                   + entry aleogr-db-gcp-cloud-sql
├── plugins/
│   ├── aleogr/
│   │   ├── defaults.json                              + platform.database, platform.switch, services
│   │   └── skills/platform-plan/SKILL.md              + two items
│   │   └── skills/platform-apply/SKILL.md             + two steps, cost in the question, secrets checklist
│   └── aleogr-db-gcp-cloud-sql/
│       ├── .claude-plugin/plugin.json
│       ├── files/stop-body.json                       body of the scheduler's PATCH
│       └── skills/
│           ├── gcp-cloud-sql_instance-describe/SKILL.md
│           ├── gcp-cloud-sql_instance-create/SKILL.md
│           ├── gcp-cloud-sql_instance-start/SKILL.md
│           ├── gcp-cloud-sql_instance-stop/SKILL.md
│           └── gcp-cloud-sql_instance-switch-setup/SKILL.md
└── tests/
    ├── run.sh                                         + --plugin-dir of the new plugin
    └── scenarios/sql-*/ , switch-*/ , platform-*/     new and updated scenarios
.github/workflows/self-lab-database.yml                manual start / stop / status
docs/DESIGN.md, CONTRACTS.md, PROVIDER-FACTS.md        decisions and facts
docs/plans/2026-11-17-lab-platform-stage-2-run.md      owner's checklist for the real run
```

## Shared definitions

**State of the instance**, derived from `gcloud sql instances describe --format=json`:

| `settings.activationPolicy` | `state` | Skill's `state` |
|---|---|---|
| `NEVER` | any | `stopped` |
| `ALWAYS` | `RUNNABLE` | `running` |
| `ALWAYS` | `PENDING_CREATE` | `creating` |
| `ALWAYS` | anything else | `starting` |

**"Does not exist":** `gcloud sql instances describe` exits non-zero and its text contains `does not exist` or `404`. Any other non-zero exit is a failure of the check, never "missing".

**Common arguments** of the five skills: `projectId=<id>` (required; same rule as stage 1: 6 to 30 characters of `a-z`, `0-9`, `-`, starting with a letter, not ending with `-`) and `instance=<name>` (required; lowercase letters, digits and `-`, starting with a letter, at most 60 characters).

**Result block** of the five skills: `"family": "db"`, `"provider": "gcp-cloud-sql"`, `"action"` the part of the folder name after the underscore, and `resources` listing `{ "type": "instance", "id": "<projectId>/<instance>", "name": "<instance>", "labels": {} }` when the instance exists.

---

### Task 1: Decisions and facts in the documents

**Files:**
- Modify: `docs/DESIGN.md` (sections 2.1 tree, 6.8, 13.1, 18)
- Modify: `docs/CONTRACTS.md` (the `db-*` table)
- Modify: `docs/PROVIDER-FACTS.md`

**Interfaces:**
- Produces: `platform.database.version` value for Task 6 (the newest PostgreSQL major version Cloud SQL offers, written as `POSTGRES_<n>`), recorded in the commit message and in `PROVIDER-FACTS.md`.

- [ ] **Step 1: Find the newest PostgreSQL version of Cloud SQL.** Read `https://cloud.google.com/sql/docs/postgres/db-versions`. If the page cannot be read, use `POSTGRES_18` and say so in the commit message.

- [ ] **Step 2: `PROVIDER-FACTS.md`.** In "GCP — Cloud SQL": replace the sentence that a stopped instance costs only its disk with: a stopped instance costs its disk AND its public IPv4 address (US$ 0.01 per hour "while idle", pricing page read on 2026-11-17; that "idle" means "stopped" is a reading to confirm on the first bill); keep the rest of that item (no backup while stopped). Add: `gcloud sql instances create` and `patch` have no flag for the storage growth limit nor for labels (SDK 570, checked on 2026-11-17); the newest PostgreSQL version found in Step 1 with the date. Add a section "GCP — Cloud Scheduler": three free jobs per billing account, counted on the account, US$ 0.10 per extra job per month (read on 2026-11-17); a job can call a Google API directly with an OAuth token of a service account.

- [ ] **Step 3: `DESIGN.md` section 6.8.** Bring it in line with the spec: the address (public, no authorized networks) and the fixed cost (`about R$ 50 per month while stopped`); the two stop times in `America/Sao_Paulo` (22:30 Sunday to Thursday, 04:00 Saturday and Sunday) and the 20:00 backup window; one switch identity with a custom role limited to reading and updating the instance, used by the scheduler and by the workflow through workload identity federation; the switch is created before the instance; the three GitHub secrets, pasted by hand; no automatic disk growth. Rename the skills there to `gcp-cloud-sql_instance-start` and `gcp-cloud-sql_instance-stop` if written otherwise. In section 16 (discarded), add one entry: private address only (alternative B of the spec), with its reason in one sentence.

- [ ] **Step 4: `DESIGN.md` sections 2.1, 13.1 and 18.** Add `aleogr-db-gcp-cloud-sql` and `self-lab-database.yml` to the tree with one-line descriptions. In 13.1, say the destructive-command hook is built with the first `*-remove` skill and that until then the instance is covered by the provider's deletion protection. In 18, replace the stage 2 item with: "implemented; waits for the first real run" and add an open item for the destructive hook.

- [ ] **Step 5: `CONTRACTS.md` `db-*` table.** `instance-create`: add the `platform=lab` exception (the lab's shared instance, passed only by the orchestrator's platform skills), as `environment-create` has. Add rows `instance-describe`, `instance-start`, `instance-stop`, `instance-switch-setup` with the inputs and outputs of Tasks 2 to 5, marked as actions of providers whose instances do not scale to zero.

- [ ] **Step 6: Verify and commit.**

Run: `grep -n "only its disk" docs/PROVIDER-FACTS.md; grep -c "instance-switch-setup" docs/CONTRACTS.md docs/DESIGN.md`
Expected: the first prints nothing; both counts are at least 1.

```bash
git add docs && git commit -m "docs: record the decisions and facts of the lab platform stage 2"
```

---

### Task 2: Plugin skeleton and `gcp-cloud-sql_instance-describe`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/.claude-plugin/plugin.json`
- Create: `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/skills/gcp-cloud-sql_instance-describe/SKILL.md`
- Modify: `.claude-plugin/marketplace.json`, `.claude-plugin/tests/run.sh`, `.claude-plugin/plugins/README.md`
- Test: `.claude-plugin/tests/scenarios/sql-describe-missing/`, `sql-describe-stopped/`, `sql-describe-running/`, `sql-describe-denied/`, `sql-describe-invalid/`

**Interfaces:**
- Produces: `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe projectId=<id> instance=<name>`, read-only. `status` is `unchanged` or `failed`. `outputs`: `exists` (bool), `state` (see Shared definitions; `null` when missing), `databaseVersion`, `edition`, `tier`, `region`, `diskSizeGb`, `storageAutoIncrease` (bool), `publicAddress` (bool), `authorizedNetworks` (count), `backupEnabled` (bool), `backupStartUtc`, `deletionProtection` (bool), `lastBackup` (timestamp or `null`).

- [ ] **Step 1: Write the five scenarios.** Prompts call the skill with `projectId=aleogr-lab-shared-zz99 instance=aleogr-lab` (the invalid one uses `instance=Bad_Name`).

| Scenario | Fake responses | `expect.txt` |
|---|---|---|
| `sql-describe-missing` | `sql_instances_describe.txt.exit1` with `ERROR: (gcloud.sql.instances.describe) HTTPError 404: The Cloud SQL instance does not exist.` | `CALLED ^sql instances describe aleogr-lab .*--project=aleogr-lab-shared-zz99` / `NOT_CALLED ^sql backups list` / `OUTPUT "exists": false` / `OUTPUT "status": "unchanged"` |
| `sql-describe-stopped` | describe JSON with `activationPolicy` `NEVER`, `state` `RUNNABLE`, tier `db-f1-micro`; `sql_backups_list.txt` with one timestamp | `CALLED ^sql backups list .*--instance=aleogr-lab` / `OUTPUT "state": "stopped"` / `OUTPUT "exists": true` / `OUTPUT "lastBackup": "20` |
| `sql-describe-running` | same with `ALWAYS`; empty backups list | `OUTPUT "state": "running"` / `OUTPUT "lastBackup": null` |
| `sql-describe-denied` | `sql_instances_describe.txt.exit1` with `ERROR: (gcloud.sql.instances.describe) HTTPError 403: The client is not authorized to make this request.` | `OUTPUT "status": "failed"` / `NOT_CALLED ^sql backups list` |
| `sql-describe-invalid` | none | `NOT_CALLED .` / `OUTPUT "status": "failed"` |

- [ ] **Step 2: Add the plugin to the harness and run the scenarios to see them fail.** In `run.sh`, add `--plugin-dir "$plugins/aleogr-db-gcp-cloud-sql"`.

Run: `bash .claude-plugin/tests/run.sh sql-describe-missing`
Expected: `FAIL sql-describe-missing` (the skill does not exist).

- [ ] **Step 3: Write `plugin.json`, the catalog entry and the skill.** `plugin.json`: name `aleogr-db-gcp-cloud-sql`, version `0.1.0`, description `Cloud SQL family: the lab's shared PostgreSQL instance and its start and stop.`, author as the other plugins. Catalog entry: `source` `./.claude-plugin/plugins/aleogr-db-gcp-cloud-sql`, `category` `db`, `displayName` `Cloud SQL (database)`. The skill runs exactly:

```
gcloud sql instances describe <instance> --project=<projectId> --format=json
gcloud sql backups list --instance=<instance> --project=<projectId> --filter="status=SUCCESSFUL" --sort-by="~windowStartTime" --limit=1 --format="value(windowStartTime)"
```

The second only when the instance exists. Missing and failure follow Shared definitions; a failure of the backups list alone gives `lastBackup` `null` and one sentence, not `failed`.

- [ ] **Step 4: Run the five scenarios and the validation.**

Run: `for s in sql-describe-missing sql-describe-stopped sql-describe-running sql-describe-denied sql-describe-invalid; do bash .claude-plugin/tests/run.sh $s | head -1; done; claude plugin validate .`
Expected: five `PASS` lines and `Validation passed`.

- [ ] **Step 5: Commit.**

```bash
git add .claude-plugin && git commit -m "feat: add the Cloud SQL plugin with instance-describe"
```

---

### Task 3: `gcp-cloud-sql_instance-create`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/skills/gcp-cloud-sql_instance-create/SKILL.md`
- Test: scenarios `sql-create-plan/`, `sql-create-apply/`, `sql-create-unconfirmed/`, `sql-create-existing-running/`, `sql-create-not-platform/`, `sql-create-failed/`, `sql-create-denied/`

**Interfaces:**
- Consumes: `gcp-cloud-sql_instance-describe` (Task 2), invoked as its first step.
- Produces: `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-create projectId=<id> instance=<name> platform=lab version=<POSTGRES_n> tier=<tier> edition=<edition> region=<region> storageGb=<n> backupStartUtc=<HH:MM> retainedBackups=<n> mode=plan|apply [confirm=yes]`. `status`: `would-create`, `created`, `unchanged`, `pending`, `failed`. `outputs`: `exists`, `state`. `cost`: `{ "fixed": true, "notes": "about R$ 50 per month while stopped" }`.

- [ ] **Step 1: Write the scenarios.**

| Scenario | Setup | `expect.txt` |
|---|---|---|
| `sql-create-plan` | describe: missing; `mode=plan` | `NOT_CALLED ^sql instances create` / `OUTPUT "status": "would-create"` / `OUTPUT about R\$ 50 per month while stopped` |
| `sql-create-apply` | describe numbered: 1 missing, 2 `ALWAYS`+`RUNNABLE`, 3 `NEVER`; `mode=apply confirm=yes` | `CALLED ^sql instances create aleogr-lab .*--tier=db-f1-micro` / `CALLED ^sql instances create .*--edition=enterprise` / `CALLED ^sql instances create .*--no-storage-auto-increase` / `CALLED ^sql instances create .*--deletion-protection` / `CALLED ^sql instances create .*--storage-size=10` / `NOT_CALLED --authorized-networks` / `ORDER ^sql instances create >> ^sql instances patch aleogr-lab .*--activation-policy=NEVER` / `OUTPUT "status": "created"` / `OUTPUT "state": "stopped"` |
| `sql-create-unconfirmed` | describe: missing; `mode=apply` without `confirm` | `NOT_CALLED ^sql instances create` / `OUTPUT "status": "pending"` / `OUTPUT confirm=yes` |
| `sql-create-existing-running` | describe: `ALWAYS`+`RUNNABLE`; `mode=apply confirm=yes` | `NOT_CALLED ^sql instances (create\|patch)` / `OUTPUT "status": "unchanged"` / `OUTPUT "state": "running"` |
| `sql-create-not-platform` | prompt without `platform=lab` | `NOT_CALLED .` / `OUTPUT "status": "failed"` |
| `sql-create-failed` | describe: missing; `sql_instances_create.txt.exit1` | `NOT_CALLED ^sql instances patch` / `OUTPUT "status": "failed"` |
| `sql-create-denied` | describe: 403 | `NOT_CALLED ^sql instances create` / `OUTPUT "status": "failed"` |

- [ ] **Step 2: Run one to see it fail.**

Run: `bash .claude-plugin/tests/run.sh sql-create-apply`
Expected: `FAIL sql-create-apply`.

- [ ] **Step 3: Write the skill.** Validation: all arguments required; `platform` must be `lab` (anything else: `failed`, this skill only creates the lab's shared instance); `version` matches `POSTGRES_[0-9]+`; `storageGb` an integer from 10 to 100; `backupStartUtc` is `HH:MM`; `retainedBackups` from 1 to 30; `confirm`, when given, is `yes`. Order: describe; if it exists, `unchanged` with its state and nothing else (never stop it); `plan` ends with `would-create`; `apply` without `confirm=yes` ends with `pending` and `pending[].how` equal to the same invocation plus `confirm=yes`. Before creating, say that creation takes several minutes. Commands:

```
gcloud sql instances create <instance> --project=<projectId> --database-version=<version> --edition=<edition> --tier=<tier> --region=<region> --availability-type=zonal --storage-type=SSD --storage-size=<storageGb> --no-storage-auto-increase --assign-ip --backup --backup-start-time=<backupStartUtc> --retained-backups-count=<retainedBackups> --no-enable-point-in-time-recovery --database-flags="cloudsql.iam_authentication=on" --deletion-protection --async --quiet
gcloud sql instances patch <instance> --project=<projectId> --activation-policy=NEVER --quiet
```

Between them, poll the describe command every 30 seconds until the state is `running`, for at most 20 minutes; a timeout ends with `pending` (the instance exists; `pending[].how` is `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=<id> instance=<name>`). After the patch, describe once more: `created` only when the state is `stopped`. A failed create is `failed`; any failure after it is `pending`, never `failed`.

- [ ] **Step 4: Run the seven scenarios.**

Run: `for s in sql-create-plan sql-create-apply sql-create-unconfirmed sql-create-existing-running sql-create-not-platform sql-create-failed sql-create-denied; do bash .claude-plugin/tests/run.sh $s | head -1; done`
Expected: seven `PASS` lines.

- [ ] **Step 5: Commit.**

```bash
git add .claude-plugin && git commit -m "feat: add instance-create for the lab's shared instance"
```

---

### Task 4: `gcp-cloud-sql_instance-start` and `gcp-cloud-sql_instance-stop`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/skills/gcp-cloud-sql_instance-start/SKILL.md`
- Create: `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/skills/gcp-cloud-sql_instance-stop/SKILL.md`
- Test: scenarios `sql-start/`, `sql-start-running/`, `sql-start-missing/`, `sql-stop/`, `sql-stop-stopped/`, `sql-stop-failed/`

**Interfaces:**
- Consumes: `gcp-cloud-sql_instance-describe` (Task 2).
- Produces: `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-start projectId=<id> instance=<name>` and `...instance-stop` with the same arguments. No `mode`: they act. `status`: `updated`, `unchanged`, `failed`. `outputs.state`: `starting` after a start, `stopped` after a stop.

- [ ] **Step 1: Write the scenarios.**

| Scenario | Setup | `expect.txt` |
|---|---|---|
| `sql-start` | describe numbered: 1 `NEVER`, 2 `ALWAYS` with `state` `MAINTENANCE` | `CALLED ^sql instances patch aleogr-lab .*--activation-policy=ALWAYS .*--async` / `OUTPUT "status": "updated"` / `OUTPUT "state": "starting"` / `OUTPUT ten minutes` |
| `sql-start-running` | describe: `ALWAYS`+`RUNNABLE` | `NOT_CALLED ^sql instances patch` / `OUTPUT "status": "unchanged"` |
| `sql-start-missing` | describe: 404 | `NOT_CALLED ^sql instances patch` / `OUTPUT "status": "failed"` |
| `sql-stop` | describe numbered: 1 `ALWAYS`+`RUNNABLE`, 2 `NEVER` | `CALLED ^sql instances patch aleogr-lab .*--activation-policy=NEVER` / `OUTPUT "status": "updated"` / `OUTPUT "state": "stopped"` |
| `sql-stop-stopped` | describe: `NEVER` | `NOT_CALLED ^sql instances patch` / `OUTPUT "status": "unchanged"` |
| `sql-stop-failed` | describe: `ALWAYS`+`RUNNABLE`; `sql_instances_patch.txt.exit1` | `OUTPUT "status": "failed"` |

- [ ] **Step 2: Run one to see it fail.**

Run: `bash .claude-plugin/tests/run.sh sql-start`
Expected: `FAIL sql-start`.

- [ ] **Step 3: Write the two skills.** Both: describe; missing is `failed` with one sentence; already in the wanted state (`running`, `starting` or `creating` for start; `stopped` for stop) is `unchanged`. Commands:

```
gcloud sql instances patch <instance> --project=<projectId> --activation-policy=ALWAYS --async --quiet
gcloud sql instances patch <instance> --project=<projectId> --activation-policy=NEVER --quiet
```

Then describe once. Start says the instance takes about ten minutes to accept connections, that the describe skill shows when it is `running`, and that the instance costs by the hour until it is stopped. `cost.notes` of start: `charged by the hour while running`.

- [ ] **Step 4: Run the six scenarios.**

Run: `for s in sql-start sql-start-running sql-start-missing sql-stop sql-stop-stopped sql-stop-failed; do bash .claude-plugin/tests/run.sh $s | head -1; done`
Expected: six `PASS` lines.

- [ ] **Step 5: Commit.**

```bash
git add .claude-plugin && git commit -m "feat: add instance-start and instance-stop"
```

---

### Task 5: `gcp-cloud-sql_instance-switch-setup`

**Files:**
- Create: `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/skills/gcp-cloud-sql_instance-switch-setup/SKILL.md`
- Create: `.claude-plugin/plugins/aleogr-db-gcp-cloud-sql/files/stop-body.json` with exactly `{"settings":{"activationPolicy":"NEVER"}}`
- Test: scenarios `switch-plan-missing/`, `switch-apply/`, `switch-ready/`, `switch-resume-jobs/`, `switch-job-drift/`, `switch-job-retry/`, `switch-invalid/`

**Interfaces:**
- Produces: `/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-switch-setup projectId=<id> instance=<name> region=<region> timeZone=<tz> weeknightStop="<cron>" weekendStop="<cron>" repository=<owner>/<repo> mode=plan|apply`. `status`: `would-create`, `would-update`, `created`, `updated`, `unchanged`, `pending`, `failed`. `outputs`: `ready` (bool), `missing` (array of the parts below still missing or different). Parts, in order: `role`, `account`, `role-grant`, `act-as`, `pool`, `provider`, `federation-grant`, `job-weeknight`, `job-weekend`.
- Produces, in the answer's prose and never in the result block, when `ready` is true (both modes), a section titled `GitHub secrets` with the three names of Global Constraints and their values: the project id; `projects/<number>/locations/global/workloadIdentityPools/github/providers/aleogr`; `aleogr-lab-sql-switch@<projectId>.iam.gserviceaccount.com`; and where to paste them (repository `Settings`, `Secrets and variables`, `Actions`, `New repository secret`).

- [ ] **Step 1: Write the scenarios.** Fictitious values from Global Constraints. "Missing" for a describe is a `.exit1` response containing `NOT_FOUND`.

| Scenario | Setup | `expect.txt` |
|---|---|---|
| `switch-plan-missing` | every check missing; `mode=plan` | `NOT_CALLED (create\|add-iam-policy-binding)` / `OUTPUT "status": "would-create"` / `OUTPUT "ready": false` |
| `switch-apply` | every check missing first, present afterwards (numbered responses); `mode=apply` | `CALLED ^iam roles create aleogrLabSqlSwitch .*cloudsql.instances.get,cloudsql.instances.update` / `CALLED ^iam service-accounts create aleogr-lab-sql-switch` / `CALLED ^iam workload-identity-pools providers create-oidc aleogr .*assertion.repository=='aleogr/aleogr'` / `CALLED ^scheduler jobs create http aleogr-lab-stop-weeknight .*--schedule=30 22 \* \* 0-4` / `CALLED ^scheduler jobs create http aleogr-lab-stop-weekend .*--time-zone=America/Sao_Paulo` / `CALLED ^scheduler jobs create http .*--http-method=PATCH` / `CALLED ^scheduler jobs create http .*stop-body.json` / `ORDER ^iam service-accounts create >> ^scheduler jobs create` / `OUTPUT "status": "created"` / `OUTPUT "ready": true` / `OUTPUT LAB_GCP_WIF_PROVIDER` / `OUTPUT projects/123456789012/locations/global/workloadIdentityPools/github/providers/aleogr` |
| `switch-ready` | everything present and equal; `mode=apply` | `NOT_CALLED (create\|update http)` / `OUTPUT "status": "unchanged"` / `OUTPUT LAB_GCP_SWITCH_ACCOUNT` |
| `switch-resume-jobs` | role, account, grants, pool, provider present; both jobs missing; `mode=apply` | `NOT_CALLED ^iam roles create` / `NOT_CALLED ^iam service-accounts create` / `COUNT 2 ^scheduler jobs create http` / `OUTPUT "status": "created"` |
| `switch-job-drift` | everything present, weeknight job with schedule `0 23 * * *`; `mode=apply` | `CALLED ^scheduler jobs update http aleogr-lab-stop-weeknight .*--schedule=30 22 \* \* 0-4` / `NOT_CALLED ^scheduler jobs create` / `OUTPUT "status": "updated"` |
| `switch-job-retry` | as `switch-resume-jobs`, with `scheduler_jobs_create_http.1.txt.exit1` (`PERMISSION_DENIED`) and `.2.txt` succeeding | `COUNT 3 ^scheduler jobs create http` / `OUTPUT "status": "created"` |
| `switch-invalid` | `repository=not-a-repo` | `NOT_CALLED .` / `OUTPUT "status": "failed"` |

- [ ] **Step 2: Run one to see it fail.**

Run: `bash .claude-plugin/tests/run.sh switch-apply`
Expected: `FAIL switch-apply`.

- [ ] **Step 3: Write the skill.** Validation: all arguments required; `repository` is `<owner>/<repo>` of letters, digits, `-`, `_`, `.`; each cron has five fields of digits, `*`, `,`, `-`, `/`; `timeZone` is `Area/City` of letters and `_`. Read commands (one per part; a part is checked only when the part it depends on exists):

```
gcloud projects describe <projectId> --format="value(projectNumber)"
gcloud config get-value account
gcloud iam roles describe aleogrLabSqlSwitch --project=<projectId> --format="value(includedPermissions)"
gcloud iam service-accounts describe <account> --project=<projectId> --format="value(email)"
gcloud projects get-iam-policy <projectId> --flatten="bindings[].members" --filter="bindings.role:roles/aleogrLabSqlSwitch" --format="value(bindings.members)"
gcloud iam service-accounts get-iam-policy <account> --project=<projectId> --format=json
gcloud iam workload-identity-pools describe github --project=<projectId> --location=global --format="value(state)"
gcloud iam workload-identity-pools providers describe aleogr --project=<projectId> --location=global --workload-identity-pool=github --format="value(attributeCondition)"
gcloud scheduler jobs describe <job> --project=<projectId> --location=<region> --format="value(schedule,timeZone)"
```

Change commands, each run only when its part is missing, in the order of the parts:

```
gcloud iam roles create aleogrLabSqlSwitch --project=<projectId> --title="aleogr lab SQL switch" --permissions="cloudsql.instances.get,cloudsql.instances.update" --stage=GA --quiet
gcloud iam service-accounts create aleogr-lab-sql-switch --project=<projectId> --display-name="aleogr lab SQL switch" --quiet
gcloud projects add-iam-policy-binding <projectId> --member="serviceAccount:<account>" --role="projects/<projectId>/roles/aleogrLabSqlSwitch" --condition=None --quiet
gcloud iam service-accounts add-iam-policy-binding <account> --project=<projectId> --member="user:<active account>" --role="roles/iam.serviceAccountUser" --quiet
gcloud iam workload-identity-pools create github --project=<projectId> --location=global --display-name="GitHub" --quiet
gcloud iam workload-identity-pools providers create-oidc aleogr --project=<projectId> --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" --attribute-condition="assertion.repository=='<repository>' && assertion.ref=='refs/heads/main'" --quiet
gcloud iam service-accounts add-iam-policy-binding <account> --project=<projectId> --member="principalSet://iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/github/attribute.repository/<repository>" --role="roles/iam.workloadIdentityUser" --quiet
gcloud scheduler jobs create http <job> --project=<projectId> --location=<region> --schedule="<cron>" --time-zone="<timeZone>" --uri="https://sqladmin.googleapis.com/v1/projects/<projectId>/instances/<instance>" --http-method=PATCH --headers="Content-Type=application/json" --message-body-from-file="${CLAUDE_PLUGIN_ROOT}/files/stop-body.json" --oauth-service-account-email=<account> --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform" --max-retry-attempts=5 --min-backoff=5m --max-backoff=15m --max-doublings=2 --attempt-deadline=60s --quiet
gcloud scheduler jobs update http <job> --project=<projectId> --location=<region> --schedule="<cron>" --time-zone="<timeZone>" --quiet
```

A job whose schedule or time zone differs is updated (status `updated`). A job creation that fails is retried once after one minute (the grant of `act-as` may not have propagated), as the budget skill retries its list. A failure of any other change command stops the skill with `pending` (when something was created in this run or existed before) or `failed` (nothing exists), listing in `outputs.missing` what is left. `apply` ends by running the read commands again: `ready` is true only when no part is missing. The e-mails and the project number appear in the commands shown and in the `GitHub secrets` section only.

- [ ] **Step 4: Run the seven scenarios.**

Run: `for s in switch-plan-missing switch-apply switch-ready switch-resume-jobs switch-job-drift switch-job-retry switch-invalid; do bash .claude-plugin/tests/run.sh $s | head -1; done`
Expected: seven `PASS` lines.

- [ ] **Step 5: Commit.**

```bash
git add .claude-plugin && git commit -m "feat: add instance-switch-setup (identity, federation, night stop)"
```

---

### Task 6: Orchestrator — defaults, `platform-plan`, `platform-apply`

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/defaults.json`
- Modify: `.claude-plugin/plugins/aleogr/skills/platform-plan/SKILL.md`
- Modify: `.claude-plugin/plugins/aleogr/skills/platform-apply/SKILL.md`
- Modify: `.claude-plugin/plugins/aleogr/.claude-plugin/plugin.json` (version `0.2.0`, description mentions the database)
- Test: update every existing `platform-*` scenario; add `platform-plan-database-missing/`, `platform-apply-database/`, `platform-apply-database-unconfirmed/`, `platform-apply-resume-instance/`, `platform-apply-instance-running/`

**Interfaces:**
- Consumes: the skills of Tasks 2, 3 and 5 with the argument names given there; `POSTGRES_<n>` from Task 1.
- Produces: `defaults.json` keys:

```json
"platform": {
  "shared": { "project": "shared", "environment": "lab", "services": ["cloudresourcemanager.googleapis.com", "billingbudgets.googleapis.com", "sqladmin.googleapis.com", "cloudscheduler.googleapis.com", "iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com"] },
  "budget": { "...": "unchanged" },
  "database": { "instance": "aleogr-lab", "version": "POSTGRES_<n>", "edition": "enterprise", "tier": "db-f1-micro", "storageGb": 10, "backupStartUtc": "23:00", "retainedBackups": 7 },
  "switch": { "timeZone": "America/Sao_Paulo", "weeknightStop": "30 22 * * 0-4", "weekendStop": "0 4 * * 6,0", "repository": "aleogr/aleogr" }
}
```

- Produces: plan items, in this order: `shared project`, `services`, `budget alert`, `database switch`, `database instance`.

- [ ] **Step 1: Write the new scenarios and update the old ones.** The old `platform-*` scenarios gain responses for the new read commands (switch parts present, instance stopped) so that their existing expectations still hold, and their expectations for "nothing to do" stay.

| Scenario | Setup | `expect.txt` |
|---|---|---|
| `platform-plan-database-missing` | stage 1 items ready, all seven services enabled, switch parts missing, instance 404 | `NOT_CALLED (create\|enable\|patch\|add-iam-policy-binding)` / `OUTPUT database switch` / `OUTPUT database instance` / `OUTPUT "status": "would-update"` |
| `platform-apply-database` | same start, `confirm=yes`, numbered responses turning everything present | `ORDER ^scheduler jobs create http >> ^sql instances create` / `CALLED ^sql instances create aleogr-lab` / `OUTPUT GitHub secrets` / `OUTPUT nothing to do` / `OUTPUT "status": "created"` |
| `platform-apply-database-unconfirmed` | same start, no `confirm` | `NOT_CALLED (create\|patch\|add-iam-policy-binding)` / `OUTPUT about R\$ 50 per month while stopped` / `OUTPUT "status": "pending"` |
| `platform-apply-resume-instance` | switch ready, instance 404, `confirm=yes` | `NOT_CALLED ^iam (roles\|service-accounts) create` / `CALLED ^sql instances create` / `OUTPUT "status": "created"` |
| `platform-apply-instance-running` | everything ready, instance `ALWAYS`+`RUNNABLE`, `confirm=yes` | `NOT_CALLED ^sql instances (create\|patch)` / `OUTPUT nothing to do` / `OUTPUT "status": "unchanged"` |

- [ ] **Step 2: Run one new scenario to see it fail.**

Run: `bash .claude-plugin/tests/run.sh platform-plan-database-missing`
Expected: `FAIL platform-plan-database-missing`.

- [ ] **Step 3: Change `defaults.json` and `platform-plan`.** New steps after the budget step, each run only when the project exists and the services result shows every service enabled (otherwise the item's state is `not checked, will be checked after the services are enabled`, action `create`):
  - `database switch`: invoke `instance-switch-setup` with `mode=plan` and the values of `platform.switch`, `cloud.region` and `platform.database.instance`. `unchanged` is `ready`, `none`; `would-create` is `missing`, `create`; `would-update` is `incomplete: <outputs.missing>`, `update`.
  - `database instance`: invoke `instance-describe`. Missing is `missing`, `create`; otherwise `exists, <state>`, `none` (a running instance is never a difference).
  The result block's `cost.notes` stays `read-only plan`.

- [ ] **Step 4: Change `platform-apply`.** The confirmation question, when `database instance` is to create, adds one sentence: the instance has a fixed cost of `about R$ 50 per month while stopped`. New creating steps after the budget, with the same stop-on-failure rule: 4. `instance-switch-setup mode=apply`; 5. `instance-create` with `platform=lab mode=apply confirm=yes` and the values of `platform.database` and `cloud.region`. After step 4 created or completed the switch, repeat its `GitHub secrets` section in the answer and say it is done once, by hand. The final plan and the `nothing to do` rule cover the five items. `cost` of the result block: `fixed` is true and `notes` is the fixed cost wording when the instance exists at the end; otherwise as today.

- [ ] **Step 5: Run the platform scenarios.**

Run: `for s in $(ls .claude-plugin/tests/scenarios | grep '^platform-'); do bash .claude-plugin/tests/run.sh $s | head -1; done`
Expected: one `PASS` line per scenario (`platform-apply-resume` is known to be flaky: run it up to three times before treating a failure as real).

- [ ] **Step 6: Commit.**

```bash
git add .claude-plugin && git commit -m "feat: plan and create the lab's database with the platform skills"
```

---

### Task 7: Workflow `self-lab-database.yml`

**Files:**
- Create: `.github/workflows/self-lab-database.yml`
- Modify: `.github/workflows/README.md` (one line for the workflow and its three secrets)

**Interfaces:**
- Consumes: secrets `LAB_GCP_PROJECT_ID`, `LAB_GCP_WIF_PROVIDER`, `LAB_GCP_SWITCH_ACCOUNT`; instance name `aleogr-lab` (written in the file; it is not an identifier of the account).

- [ ] **Step 1: Write the workflow.** `on: workflow_dispatch` with one input `action`, type `choice`, options `status`, `start`, `stop`, default `status`. `permissions: { contents: read, id-token: write }`. `concurrency: lab-database`. One job on `ubuntu-latest`, `if: github.ref == 'refs/heads/main'`, steps:
  1. Fail with `Missing secret <name>: see docs/plans/2026-11-17-lab-platform-stage-2-run.md` when any of the three secrets is empty (secrets reach the script through `env`, never interpolated in `run`).
  2. `google-github-actions/auth`, pinned to the commit of its latest release (find it with `git ls-remote --tags https://github.com/google-github-actions/auth`, comment with the tag), with `workload_identity_provider`, `service_account` and `token_format: access_token`.
  3. For `start` or `stop`: `curl` `PATCH https://sqladmin.googleapis.com/v1/projects/$PROJECT/instances/aleogr-lab` with body `{"settings":{"activationPolicy":"ALWAYS"}}` or `"NEVER"`, bearer token from step 2, `--fail-with-body`; print only the HTTP status and the operation's `status` field (`jq`).
  4. Always: `GET` the instance and print one line, `aleogr-lab: <stopped|running|starting>`, by the rule of Shared definitions, to the log and to `$GITHUB_STEP_SUMMARY`. After `start`, add that it takes about ten minutes to accept connections.
  The input `action` reaches the script through `env` and is compared with fixed strings. No step prints a response body in full.

- [ ] **Step 2: Check it statically.**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/self-lab-database.yml')); print(d[True]['workflow_dispatch']['inputs']['action']['options'], d['permissions'])"; grep -nE 'uses: [^ ]+@[0-9a-f]{40}' .github/workflows/self-lab-database.yml; grep -nE '\$\{\{ *(secrets|inputs|github\.event)' .github/workflows/self-lab-database.yml`
Expected: `['status', 'start', 'stop'] {'contents': 'read', 'id-token': 'write'}`; one `uses:` line pinned to 40 hex characters; every `${{ secrets… }}` or `${{ inputs… }}` line is under an `env:` or `with:` key, none inside a `run:` script. If `actionlint` is installed, run it too and expect no output.

- [ ] **Step 3: Commit.**

```bash
git add .github && git commit -m "feat: add the manual workflow that starts and stops the lab database"
```

---

### Task 8: Run checklist, full suite, validation

**Files:**
- Create: `docs/plans/2026-11-17-lab-platform-stage-2-run.md`
- Modify: `.claude-plugin/tests/README.md` (the third plugin), `.claude-plugin/README.md` and `.claude-plugin/plugins/README.md` if they list the plugins

- [ ] **Step 1: Write the owner's checklist**, in the style of `2026-11-16-lab-platform-stage-1-run.md`: (1) after the merge, in the app's plugin browser, update the marketplace `aleogr` and install `Cloud SQL (database)`; (2) new session, `/aleogr:platform-plan`: expected two items to create; (3) `/aleogr:platform-apply`: one question that states `about R$ 50 per month while stopped`; it takes several minutes; expected end `nothing to do` with the instance `stopped`; (4) paste the three GitHub secrets it prints; (5) on GitHub, `Actions`, `self-lab-database`, run with `status`, then `start`, then `stop`; (6) in the Google Cloud console, Cloud Scheduler: two jobs with their next run times; (7) what to send back. End with the list "not verified until this run" from the spec, plus: the rule that derives `stopped` from the activation policy, the text of the "does not exist" error, and whether `db-f1-micro` exists for the chosen PostgreSQL version.

- [ ] **Step 2: Run the whole suite and the validation.**

Run: `for s in $(ls .claude-plugin/tests/scenarios); do bash .claude-plugin/tests/run.sh $s | head -1; done 2>&1 | sort | uniq -c | sort -rn | head -80; claude plugin validate .`
Expected: every line starts with `1 PASS`; `Validation passed`. A `FAIL` is run again alone to read its output; a real failure is fixed in the skill or the scenario that owns it, not skipped.

- [ ] **Step 3: Check the public-repository rule.**

Run: `git diff origin/main --name-only | xargs grep -nE '[0-9]{12}|@[a-z0-9.-]+\.(com|dev|me)|[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}' | grep -vE '123456789012|example\.com|noreply@anthropic\.com|iam\.gserviceaccount\.com' `
Expected: no output.

- [ ] **Step 4: Commit.**

```bash
git add -A && git commit -m "docs: add the checklist for the first real run of stage 2"
```
