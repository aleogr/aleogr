# Skills as thin shells over scripts: design

Status: proposed on 2026-11-27, not built. It changes how the skills are made, not what they do: no command, argument, answer or step of the owner changes.

## Why

The fixed logic of the tooling is written as prose that a model follows on every run. `project-plan` and `project-apply` alone are about 30,000 words. Three costs follow:

- **Testing costs model usage.** Each of the 673 scenarios is a model run; the two orchestrators have 207 of them. Stage 4c spent most of a week's allowance on reruns.
- **Running is slow.** A plan with nothing to do takes more than a minute; a run after a merge took almost ten minutes in stage 4b-2.
- **The answer varies.** The model sometimes adds a sentence, skips a read or rewords a prescribed line.

Almost everything these skills do is fixed: read a declaration, ask GitHub and Google Cloud, compare, print a table, run a known command. That is a script's work.

## Destination

**Every skill is a thin shell over a command of its plugin.** The command holds the rules; the skill tells the model to run it and to give its answer. Each rule is written in one place.

- The destination is reached in steps, and the tooling stays usable after each one. Between steps some skills are prose and some are shells; the mix ends with step 3.
- What stays with the model for good: choosing the skill from what the owner asks, passing the arguments, and showing the answer. Nothing else.

## Structure

### One command per plugin

Each plugin ships one executable in `bin/` at its root, named after the plugin: `aleogr`, `aleogr-cloud-gcp`, `aleogr-db-gcp-cloud-sql`, `aleogr-registry-gcp-artifact-registry`, `aleogr-repo-github`, `aleogr-stack-go`. Claude Code puts a plugin's `bin/` on the `PATH` of its Bash tool while the plugin is enabled, so a skill, and another plugin's command, runs it by its bare name.

- Its first argument is the skill's name, the rest are the skill's own `key=value` arguments, unchanged: `aleogr-cloud-gcp gcp_environment-describe project=demo environment=dev`.
- **A command reaches another plugin only through that plugin's command**, found on the `PATH`. An installed plugin cannot read another plugin's files, and no path of the plugin cache is used. A command that is not found is a failure with one fixed sentence naming the plugin to install, as a missing tool is today.
- The orchestrator's `plugin.json` does not list them as `dependencies`: [DESIGN.md](../DESIGN.md) section 2.2 keeps activation per project, and the fixed sentence above covers a plugin that is not installed.

### Language

Python 3, standard library only, written for Python 3.9 or later. It is already in Cloud Shell and in Claude Code's cloud sessions, so nothing is installed. The Windows app is not covered, as it is not today ([DESIGN.md](../DESIGN.md) section 18).

Code shared by every command (running a provider command, printing, the result block, parsing arguments) is one module, copied into each plugin under `scripts/`, because a plugin reaches only its own files. A test fails when the copies differ, as the shared paragraph of the skills is checked today.

### What a command prints

The same answer the skill gives today, so nothing changes for the owner or for a skill that still reads it:

1. each provider command, on its own line, before it runs;
2. the prescribed lines, table and sentences;
3. one fenced `aleogr-result` block, last.

With `--json` as its first option a command prints only the result object, for another command to read. Commands talk to each other this way; the fenced block stays for the model and for the skills that are still prose.

No value of a provider's output is printed, as today. No secret, password or login code is read or printed by any command.

### What a skill becomes

Frontmatter with its `description`, then a few lines: run the command with the arguments given, show the commands it printed, give its answer as it is, add nothing. The shared paragraph for a skill invoked by another skill stays while a prose skill can still invoke it.

### Reads cannot write

A command that only reads (every `-describe`, every `mode=plan`, `project-plan`, `tools-check`) runs provider commands through a runner that accepts only read verbs (`describe`, `list`, `get-iam-policy`, `gh` reads, `git` reads) and refuses anything else before running it. This is enforced in code and tested, so a mistake in a plan cannot create, change or start anything.

Writing commands (steps 2 and 3) keep every rule of [DESIGN.md](../DESIGN.md) section 10.4: nothing with a cost, nothing irreversible and nothing that exposes something runs without `confirm=yes` given in the command, and the cost is said before it.

### Permissions

A shell skill of a read-only command lists that command in its `allowed-tools`, so a plan asks nothing. A skill whose command can write does not: Claude Code asks, once, before the command runs. The owner sees each provider command in the output rather than approving them one by one; the confirmation in the command (`confirm=yes`) stays the gate for cost.

## Tests

- **The scenarios become free tests.** `run.sh` gains a mode that runs the skill's command directly instead of `claude -p`, with the same fake `gcloud`, `gh`, `git`, `go` and `sleep`, the same `responses` and the same `expect.txt`. A scenario's `prompt.txt` already is the command and its arguments. Run this way a scenario takes a second and no model usage.
- **The existing scenarios are the acceptance test of each step**: the command of a converted skill passes that skill's scenarios with their `expect.txt` unchanged. A line that pins something only a model does (a tool it used) is the only kind that may change, each one listed in the step's report.
- **Unit tests** (`unittest`, standard library) cover the rules without a provider: the declaration's rules, the names, each row's states.
- **A workflow** `self-test-skills.yml` runs both on every pull request that changes a plugin or a test. It needs no secret and has `permissions: contents: read`. The skills get the automatic check they never had.
- **Model runs stay only for the shells**: that the model runs the command with the arguments and relays the answer. At most ten scenarios per step, run once.

## Steps

### Step 1: the reads and the plan

- The shared module, the `bin/` commands, the direct mode of `run.sh`, the workflow.
- Every skill that only reads becomes a shell: `tools-check`, `github_repo-describe`, `gcp_environment-describe`, `gcp_login-describe`, `gcp_deploy-describe`, `gcp-artifact-registry_registry-describe`, `gcp-cloud-sql_database-describe`, `gcp-cloud-sql_instance-describe`.
- The `mode=plan` of the skills the plan invokes moves to their command: `github_checkout-setup`, `github_pull-request-open`, `github_ci-setup`, `github_variables-set`, `gcp_ci-identity-setup`, `go_setup`. Their `mode=apply` stays prose until step 2, so for these six a read is written twice between the two steps.
- `project-plan` becomes a shell over `aleogr project-plan`, which calls the commands above.
- `project-apply`, `platform-plan`, `platform-apply` and every writing skill stay as they are. `project-apply` still invokes the skill `project-plan` and reads its block, which is unchanged.
- Reads run one after another, in today's order, so the scenarios' order lines hold. Running them at the same time is a later decision, taken with a measurement.

Proof by a real run: `/aleogr:project-plan` in `~/pilot` says `nothing to do` with the same fourteen rows, and one `/aleogr:project-apply` with nothing to do still ends `unchanged`. No cost.

### Step 2: the writing skills, one family at a time

Repository, then stack, then cloud and registry, then database, then the platform's skills. Each family's commands pass its scenarios; each family is proven by one real run of what it makes, the ones with a cost under the owner's confirmation.

### Step 3: `project-apply` and the platform's orchestrators

Last, when everything they call is a command. The fenced block and the shared paragraph are then reviewed: with no prose skill left to read them, they may go.

Steps 2 and 3 are designed when their turn comes, and may be interleaved with the reference project's stages.

## Before building: three facts to prove

They are documented by Claude Code but not for every way the tooling runs. One short trial, with a one-line command in one plugin, before any real code:

1. a plugin's `bin/` command is found by its bare name under `claude -p` with `--plugin-dir` (the harness) and in an installed plugin in Cloud Shell, with its executable bit kept;
2. a command started by another plugin's command finds it on the same `PATH`;
3. an `allowed-tools` rule for the bare command spares the permission prompt.

If 1 or 2 fails, this design stops and is revised before anything is built. If 3 fails, a plan asks for one permission, and nothing else changes.

## What does not change

- The plugins, the skills' names, their arguments and their answers.
- The owner's steps: declare, apply, merge, apply.
- The contracts, the declaration, the schema, the workflows of a project.
- The rules on identifiers and secrets: none in a versioned file, fixtures with fictitious values.

## Known limits

- **The plan will not answer in a second.** Its time becomes the provider's: some thirty to forty `gcloud` and `gh` reads, each taking about a second. What goes away is the model's time between them.
- **Between steps 1 and 2 six skills hold a read twice** (their command for `mode=plan`, their prose for `mode=apply`). A difference between the two would show as a plan that disagrees with an apply; the scenarios of both modes pin the same reads.
- **The model still relays the answer**, so a shell can still add a sentence. The answer it relays is fixed text it did not compose, and the shells' scenarios pin that nothing is added.
- **One permission covers a writing command's provider commands** (from step 2). The gate for cost remains `confirm=yes`.
