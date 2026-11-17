# Lab platform, stage 2: design of the shared database

Status: waiting for the owner's approval. Source of truth after approval: [`DESIGN.md`](../DESIGN.md) section 6.8; this document is what the implementation plan is written from.

## Intent

The lab needs one PostgreSQL instance that every project's `lab` and `hom` environments share, so that a new project gets a database without creating an instance of its own. The owner has no project in mind yet and chose to create the instance now, so that the platform is ready and its real behaviour (and bill) is known before the first project depends on it.

The concern behind every choice here is **cost**: the instance does not scale to zero, so it stays OFF and runs only while the owner works.

## Goals

- One Cloud SQL PostgreSQL instance exists in the shared project, stopped by default.
- The owner starts and stops it from the Windows app (skills) and from anywhere, including the phone (a manually triggered workflow of `aleogr/aleogr`).
- Google Cloud stops it by itself at night; stopping never depends on the owner remembering.
- `platform-plan` shows what is missing and `platform-apply` creates it, with the same rules as stage 1: idempotent, each command shown, resumable, ending with a plan that says `nothing to do`.
- The identities that start and stop the instance can do nothing else of value, and no key file exists anywhere.

## Non-goals

- A project's database, its users and grants (`database-create`, `access-grant`): they come with the first project.
- A private address, a network, or anything of the alternative B below.
- `prd`: production never uses the shared project.
- The destructive-command hook ([`DESIGN.md`](../DESIGN.md) section 13.1). **My call:** in this stage the only thing worth deleting is the instance, and the provider's own deletion protection covers it. The hook is built with the first skill that removes something (`database-remove`), when there is something for it to guard and a real case to test it against on Windows.

## Anti-goals

- An instance left running overnight because a step failed silently.
- A fixed cost created without the owner seeing the amount and saying yes.
- Any organization, billing, project or pool identifier, or e-mail, in a versioned file.

## Constraints

- The repository is public; identifiers that cannot be deduced live in GitHub Actions variables, never in files.
- The organization forbids service account keys: the workflow authenticates by workload identity federation.
- Default service accounts get no roles: every identity is created and granted explicitly.
- Commands run in PowerShell in the Windows app: any value with commas or quotes is quoted, and a JSON body goes in a file shipped with the plugin, never inline.
- IAM changes take minutes to propagate: a step that uses a grant made seconds before retries once, as the budget step does.
- Region `us-central1`. Times are in `America/Sao_Paulo` (**my assumption** from the owner's currency and language).

## Cost (read on 2026-11-17 from the Cloud SQL pricing page, USD at about R$ 5.50)

| Item | Price | Per month |
|---|---|---|
| SSD disk, 10 GiB, always | US$ 0.17 per GiB-month | about R$ 9 |
| Public IPv4 address while the instance is idle | US$ 0.01 per hour | about R$ 40 if stopped all month |
| Instance running (`db-f1-micro`) | about R$ 0.06 per hour (previous lab's bill) | by use |
| Backups | US$ 0.08 per GiB-month of space used | cents |

Fixed cost with the instance stopped: **about R$ 50 per month**. That "idle" means "stopped" is my reading of the pricing page; the first bill confirms it. The existing fact in `PROVIDER-FACTS.md` ("a stopped instance costs only its disk") is wrong and is corrected with this work.

## Approaches

- **A. Public address with no authorized networks (chosen).** Nothing can connect to the address directly; access goes through the Cloud SQL connector, authenticated by IAM. Simple to build; the owner's computer, Claude Code and CI can all reach the database. Costs the idle address, about R$ 40 per month.
- **B. Private address only.** No address charge (about R$ 9 per month). The database is reachable only from inside Google Cloud: no access from the owner's computer or from GitHub Actions, and every project must be attached to a shared network. More to build, more unverified steps, and every future project becomes more complex.
- **C. Approach A, but create the instance only when the first project exists.** No cost until then; the database part would stay without a real run.

The owner chose **A**, after seeing B in detail, and chose to create the instance now. Moving to B later is possible (a private address can be added and the public one removed on an existing instance) but each existing project would have to be attached to the network.

## Decided by the owner

- Approach A; the instance is created in this stage.
- The schedule below follows the owner's routine: asleep at 22:00 on nights before a working day (Sunday to Thursday), no fixed hour on Friday and Saturday nights.

## The design

### The instance

| Setting | Value | Why |
|---|---|---|
| Name | `aleogr-lab` | Generic: it holds every project's `lab` and `hom` databases. |
| Engine | PostgreSQL, the newest major version Cloud SQL offers when it is created | A new instance has nothing to migrate. |
| Edition and tier | `ENTERPRISE`, `db-f1-micro` | Smallest; the tier only exists in this edition, which must be stated. |
| Availability | Single zone | No fixed cost for a standby. |
| Disk | SSD, 10 GiB (the minimum), automatic growth with a limit of 20 GiB | Disks never shrink; the limit bounds the worst case. |
| Address | Public, no authorized networks | Approach A. |
| IAM authentication | Flag `cloudsql.iam_authentication` on | Needed later by IAM database users; free. |
| Backups | Daily, window starting 20:00 (23:00 UTC), 7 kept | An evening hour when the instance is most likely running; a window that falls while it is stopped produces no backup and no error. |
| Point-in-time recovery | Off | Lab data; saves log storage. |
| Deletion protection | On | Replaces the hook in this stage. |
| Labels | `aleogr-platform=lab` | As the shared project. |

No password is set for the built-in `postgres` user and no database or user is created: nothing connects to the instance in this stage.

The instance is stopped (activation policy `NEVER`) as the last step of its creation. Creation takes several minutes; the skill waits for it and says so before starting. **My call:** the switch (below) is created BEFORE the instance, so that the night stop already exists if the creation is interrupted and leaves the instance running; a scheduler job whose instance does not exist yet fails harmlessly. A later `platform-apply` finds the instance by name and finishes what is missing without creating a second one.

`describe` reports, besides the settings: the state (running, stopped, starting), and the date of the last successful backup, so that a schedule that never meets the backup window is noticed.

### Starting and stopping

Start and stop are a change of the instance's activation policy (`ALWAYS` / `NEVER`). Three ways, all doing the same change:

1. **Skills** `gcp-cloud-sql_instance-start` and `gcp-cloud-sql_instance-stop`, where `gcloud` is authenticated. Start returns as soon as the change is accepted and says that the instance takes about ten minutes to accept connections and how to check; it does not hold the session for that time. Both are idempotent (starting a running instance is `unchanged`).
2. **Workflow** `.github/workflows/self-lab-database.yml` in `aleogr/aleogr`, manually triggered, with one input: `start`, `stop` or `status`. It prints the resulting state.
3. **Scheduler**, stop only (below).

### The night stop

Two Cloud Scheduler jobs in the shared project, both calling the Cloud SQL Admin API directly (an HTTP `PATCH` of the activation policy, authenticated as the switch identity). No function, no code to maintain.

| Job | When (`America/Sao_Paulo`) | Covers |
|---|---|---|
| `aleogr-lab-stop-weeknight` | 22:30, Sunday to Thursday | Nights before a working day; the owner is asleep at 22:00. |
| `aleogr-lab-stop-weekend` | 04:00, Saturday and Sunday | Friday and Saturday nights, which have no fixed end. |

Stopping an instance that is already stopped changes nothing. Worst case of a forgotten instance: it runs until the next job, at most about a day, about R$ 1.50.

A stop can be refused while another operation runs on the instance (a backup, for example). **My call:** each job retries a few times over about an hour (the scheduler's own retry settings), and nothing else: no monitoring and no notification, which would add services and a place to send alerts. A stop that still fails is caught by the next job, and `platform-plan` and `instance-describe` always show whether the instance is running.

Cloud Scheduler's price and free allowance were not verified; the plan verifies them before the jobs are created, and `platform-apply` states the cost in its confirmation.

### Identities

- **One service account, `aleogr-lab-sql-switch`**, in the shared project, used by the scheduler jobs and by the workflow. **My call:** one account instead of two, because both would hold exactly the same role.
- **One custom role** on the shared project, with only `cloudsql.instances.get` and `cloudsql.instances.update`, granted to that account. `update` is the narrowest permission that starts and stops, and it also allows resizing and turning deletion protection off ([`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md)); the account cannot delete the instance, create users or read data. This is accepted.
- **Workload identity federation** for the workflow: a pool and a GitHub provider in the shared project, accepting only tokens of the repository `aleogr/aleogr` on the branch `main`; only those may impersonate the switch account. No key exists.
- The owner, who creates the scheduler jobs, is granted `iam.serviceAccounts.actAs` on the switch account (needed to create a job that runs as it).

### What the workflow needs from GitHub

Three Actions **secrets** in `aleogr/aleogr`: the shared project's id, the federation provider's full name, and the switch account's e-mail. None is a credential, but the repository's workflow logs are public and GitHub masks only secrets; as secrets, the values are hidden even when a command echoes them in an error. **My call.** The workflow reads them; nothing is written in the file, and it prints only the instance's state.

No skill sets GitHub variables yet (there is no GitHub plugin). So this is a **checklist**, not a plan item: after creating the switch, `platform-apply` prints the three names and values and where to paste them (the repository's settings page). The values appear in the session's text only, never in a result block. `instance-switch-setup` in `plan` mode prints them again whenever asked, so they are never lost. The workflow fails with a clear message while a secret is missing.

### Skills and plugin

New plugin **`aleogr-db-gcp-cloud-sql`** (family `db`, provider `gcp-cloud-sql`), category `db` in the catalog:

| Skill | Does |
|---|---|
| `gcp-cloud-sql_instance-describe` | Read-only: exists, settings, state, last backup. |
| `gcp-cloud-sql_instance-create` | Creates the instance with the settings above and leaves it stopped. `plan` / `apply`. Fixed cost: says the amount and is only run after confirmation. |
| `gcp-cloud-sql_instance-start` | Activation policy `ALWAYS`. |
| `gcp-cloud-sql_instance-stop` | Activation policy `NEVER`. |
| `gcp-cloud-sql_instance-switch-setup` | Creates what starts and stops the instance without the owner: the custom role, the switch account and its grant, the federation pool and provider, and the two scheduler jobs. `plan` / `apply`. |

**My call:** the role, account, federation and jobs live in one skill of this plugin instead of generic IAM and scheduler skills in `aleogr-cloud-gcp`. They exist only for this instance; generic skills come when a second use appears ([`DESIGN.md`](../DESIGN.md): new actions come in when a real project needs them).

The contract in [`CONTRACTS.md`](../CONTRACTS.md) says `instance-create` is for the `dedicated` mode and refused in `lab`. It gains the same exception `environment-create` has: `platform=lab` creates the lab's shared instance, and only the orchestrator's platform skills pass it. `instance-start`, `instance-stop` and `instance-switch-setup` are added to the `db-*` table as actions of providers whose instances do not scale to zero.

`aleogr-cloud-gcp` is unchanged except that `gcp_services-enable` is called with more services (Cloud SQL Admin, Cloud Scheduler, IAM, IAM credentials, security token service).

### Orchestrator

`defaults.json` gains the instance's settings, the two schedules and the time zone under `platform`, so that the owner's choices stay in one file.

`platform-plan` gains two items after the existing three, each checked only when its prerequisite is met:

| Item | States |
|---|---|
| `database instance` | `missing` / `exists, stopped` / `exists, running` |
| `database switch` | `missing` / `incomplete: <what>` / `ready` |

`platform-apply` creates them after the services, the switch first and the instance second. Its confirmation question now carries the cost: the instance has a fixed cost of about R$ 50 per month while stopped. The answer for stage 1's free items and for the instance is one question; without a clear yes nothing is created. `confirm=yes` still skips the question: typing it is the owner's yes. `instance-create` in `apply` mode refuses to run without `confirm=yes`, which `platform-apply` passes only after that yes. The final plan says `nothing to do` when the five items need nothing; the GitHub secrets are outside the plan, because the plan cannot read GitHub.

A running instance is never a difference to fix: `platform-apply` does not stop an instance the owner started.

### Tests

The same harness as stage 1 (fake `gcloud`, `expect.txt`): scenarios for each new skill (missing, existing, invalid arguments, a command failing halfway, already in the wanted state) and for the plan and apply with the new items, including resuming after the instance was created and the switch was not.

The workflow is checked statically; its first real run is by the owner.

### First real run

A checklist for the owner, as in stage 1, in `docs/plans/`: update the plugins, install the new one, `platform-plan`, `platform-apply` (one confirmation, several minutes), paste the three secrets, run the workflow with `status`, then `start`, then `stop`, and look at the scheduler jobs' next run times. What fails becomes a fix; provider behaviour goes to `PROVIDER-FACTS.md`.

Not verifiable before that run: every `gcloud sql`, `gcloud scheduler`, `gcloud iam` flag used; whether the instance can be created directly in the stopped state or must be created and then stopped; the scheduler's price; the meaning of "idle" in the address charge.

### Documents changed with this work

- `DESIGN.md`: section 6.8 (address and its cost, schedule, identities, what the platform is made of), section 2 (the new plugin in the tree), section 13.1 (the hook comes with the first `*-remove`), section 18 (open items).
- `CONTRACTS.md`: the `db-*` table.
- `PROVIDER-FACTS.md`: the address charge; whatever the real run shows.

## Left to the builder

- The exact `gcloud` commands and flags, and how each skill verifies its result.
- The order of the steps inside `instance-switch-setup`, and its retries.
- The names of the custom role, the pool and the provider.
- The versions of the GitHub actions the workflow uses (pinned to a commit).
- The scenarios' list and the fake's canned responses.
