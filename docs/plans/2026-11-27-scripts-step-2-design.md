# Skills as thin shells over scripts, step 2: design

Status: proposed on 2026-11-27, not built. Step 2 of [the design](2026-11-27-scripts-design.md): the skills that create and change. As in step 1, no command, argument, answer or step of the owner changes.

## What is converted

Every skill that is still prose except the four orchestrators that invoke other skills (`project-apply`, `platform-plan`, `platform-apply`, `project-access`), which are step 3.

| Plugin | Skills | Scenarios |
|---|---|---|
| `aleogr-repo-github` | `github_repo-create`, `github_repo-configure`, `github_branch-protect`; `mode=apply` of `github_checkout-setup`, `github_pull-request-open`, `github_ci-setup`, `github_variables-set` | about 125 |
| `aleogr-stack-go` | `mode=apply` of `go_setup` | 26 |
| `aleogr` | `project-declare` (it writes one local file and invokes nothing) | 44 |
| `aleogr-cloud-gcp` | `gcp_environment-create`, `gcp_services-enable`, `gcp_budget-alert-setup`, `gcp_login-setup`, `gcp_deploy-setup`, `gcp_access-grant`; `mode=apply` of `gcp_ci-identity-setup` | about 115 |
| `aleogr-registry-gcp-artifact-registry` | `gcp-artifact-registry_repository-create`, `gcp-artifact-registry_cleanup-configure`, `gcp-artifact-registry_access-grant` | 31 |
| `aleogr-db-gcp-cloud-sql` | `gcp-cloud-sql_instance-create`, `gcp-cloud-sql_instance-start`, `gcp-cloud-sql_instance-stop`, `gcp-cloud-sql_instance-switch-setup`, `gcp-cloud-sql_database-create`, `gcp-cloud-sql_access-grant` | 56 |

About 400 scenarios become free. After this step every skill but the four orchestrators is a shell, and no skill holds a read twice.

## Two parts, two pull requests

- **2a: what writes to GitHub and to the folder.** The foundation below, `aleogr-repo-github`, `aleogr-stack-go` and `project-declare`. Nothing in it can cost money.
- **2b: what writes to Google Cloud.** `aleogr-cloud-gcp`, the registry and the database. It holds every command with a cost.

Each part has its own free tests, its own review and its own real run.

## What writing adds to the structure

### A command writes only in `mode=apply`, and only what its skill names

- The read-only runner stays the runner of every `mode=plan` and of every read made in `mode=apply`.
- The writing runner exists only in `mode=apply`. It accepts only the command shapes that the plugin's skills prescribe, from an allowlist of writes kept beside the allowlist of reads: a write that no skill names is refused before it runs, as an unknown read is. So a mistake in a module cannot delete something or grant a role no skill grants.
- **Golden commands.** For each skill, a unit test holds the write commands exactly as today's SKILL.md writes them (every flag) and checks that the command builds them, argument for argument. The scenarios pin a command by a pattern; this pins the whole of it.

### `--read-only`

`<command> --read-only <skill> …` forces the read-only runner whatever the arguments say; with it `mode=apply` is refused. A shell runs every mode other than `apply` this way, and its `allowed-tools` name only this form. So a plan asks no permission and cannot write, and an apply is never covered by a standing permission: Claude Code asks before it, once per command.

### Confirmation and cost

Unchanged, and now in code: nothing with a cost, nothing irreversible and nothing that exposes something runs without the argument its skill requires (`confirm=yes`, `confirmVisibility=…`); the sentence that states a cost is printed before the command that incurs it; a skill that must stop for the owner (a secret typed in a terminal, a page of the console) still ends `pending` with its checklist.

### Waits

- A wait is the command `sleep 30` run by the script (the fake `sleep` of the tests logs it, so the scenarios still count the tries).
- A shell of a skill that can wait tells the model to run the command in the foreground with the Bash tool's longest timeout (ten minutes), once, never in the background. Tried on 2026-11-27: a command that waited 150 seconds by itself ran to its end this way.
- **A command never waits past eight minutes in one run.** A skill whose waits could add up to more ends `pending` at that point, with the item that says to run it again; every skill reads before it changes, so the second run goes on from where the first stopped. No leaf skill of today reaches the limit in its documented waits (ten tries of thirty seconds); the rule is there so none can be killed half-way by the tool's timeout.

### Files

A command writes a file of the folder itself (the declaration, a component's starting files, `ci.yml`) and prints `+ write <path>` before it, as it prints a provider command. It writes only inside the current folder, never through a link that leads out of it, and only the paths its skill names.

### Values that must not be shown

As today: a variable's or secret's value is passed to `gh` the way the skill prescribes and is never printed, neither in the `+` line (the value is replaced by `<value>`) nor in the answer.

## Tests

- The scenarios of each converted skill pass in the direct mode with their expectations unchanged, as in step 1.
- Unit tests: the golden commands; the allowlist of writes refusing what no skill names (`delete`, a role outside the skill's list, `set-iam-policy`, `--activation-policy=NEVER` outside `instance-stop`, a push to the default branch, `gh pr merge`); that `--read-only` refuses an apply; that a file is not written outside the folder; that a value is not printed.
- Model runs: at most ten per part, once, for the shells and for `project-apply` still reading the blocks of the skills it invokes.

## Real runs

- **2a, no cost:** in the reference project, declare a harmless change to the repository (one more topic), `project-apply confirm=yes`, merge, `project-apply confirm=yes`. It exercises `project-declare`, the checkout, the pull request and `github_repo-configure` as commands, under the prose `project-apply`.
- **2b, cents:** declare the database for the second component, as stage 4c did for the first. It exercises `go_setup`, the pull request, the instance's start and stop, the database user, the roles and the service's settings as commands. The instance runs for less than an hour.
- **Not exercised by either:** the paths that create a repository, a GCP project, an image repository, a CI identity, the login, a budget, the instance and its night stop. They exist already, and creating them again needs a new project. They are proven by their scenarios and golden commands until the next project is created; this is recorded as an open item.

## Build

One task per plugin after a short foundation task (the writing runner and its allowlist, `--read-only`, the file and wait helpers); the tasks of a part run at the same time. One review per part, with the same questions as step 1 and one more: every write command compared with the SKILL.md it came from.

## Known limits

- `project-apply` stays prose until step 3: it still decides which skill to invoke and when, and still takes minutes after a merge.
- During a long wait the owner sees nothing until the command ends (up to eight minutes).
- An apply now asks for one permission for the whole command, where the prose asked per provider command. The gate for cost stays the confirmation in the command.
