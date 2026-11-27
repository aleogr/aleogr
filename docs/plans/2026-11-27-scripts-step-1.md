# Skills as thin shells over scripts, step 1: plan

Builds step 1 of [the design](2026-11-27-scripts-design.md): the reads and the plan. Nothing that writes to GitHub or Google Cloud is touched.

## The trial, done on 2026-11-27

The three facts the design depends on hold, tried with two throwaway plugins of one line each:

| Fact | Result |
|---|---|
| A plugin's `bin/` command is found by its bare name | yes, under `claude -p` with `--plugin-dir` and with the plugins installed from a local marketplace; the executable bit is kept in the plugin cache |
| A command started by another plugin's command finds it | yes, on the same `PATH` |
| `allowed-tools: Bash(<command> *)` spares the permission | yes: with the line the command ran with no Bash permission given; without it the run was refused |

Left for the step's real run: the same with the plugins installed from GitHub in Cloud Shell.

## What is converted

| Plugin | Skill | Part moved to the command | Scenarios that become free |
|---|---|---|---|
| `aleogr` | `tools-check` | all | 9 |
| `aleogr` | `project-plan` | all | 80 |
| `aleogr-repo-github` | `github_repo-describe` | all | 12 |
| `aleogr-repo-github` | `github_checkout-setup` | `mode=plan` | 12 |
| `aleogr-repo-github` | `github_pull-request-open` | `mode=plan` | 3 |
| `aleogr-repo-github` | `github_ci-setup` | `mode=plan` | 2 |
| `aleogr-repo-github` | `github_variables-set` | `mode=plan` | 2 |
| `aleogr-cloud-gcp` | `gcp_environment-describe` | all | 6 |
| `aleogr-cloud-gcp` | `gcp_login-describe` | all | 10 |
| `aleogr-cloud-gcp` | `gcp_deploy-describe` | all | 14 |
| `aleogr-cloud-gcp` | `gcp_ci-identity-setup` | `mode=plan` | 3 |
| `aleogr-registry-gcp-artifact-registry` | `gcp-artifact-registry_registry-describe` | all | 9 |
| `aleogr-db-gcp-cloud-sql` | `gcp-cloud-sql_database-describe` | all | 7 |
| `aleogr-db-gcp-cloud-sql` | `gcp-cloud-sql_instance-describe` | all | 7 |
| `aleogr-stack-go` | `go_setup` | `mode=plan` | 4 |

About 180 scenarios. The counts are of today's scenarios whose prompt names the skill; the build confirms them.

## Tasks

Each task ends with its scenarios passing in the direct mode, `expect.txt` unchanged except lines that pin something only a model does, each listed in the task's report.

1. **Foundation.**
   - The shared module (run a provider command and show it first, the read-only runner, `key=value` arguments, the answer and the result block, `--json`), one copy per plugin under `scripts/`, and the test that the copies are equal.
   - One `bin/` command per plugin, answering for an unconverted skill or mode with a fixed exit code, so the harness can tell.
   - `run.sh`: the direct mode, which runs the command of the scenario's prompt instead of `claude -p`; a script that runs every scenario whose skill and mode are converted and reports the others as not converted.
   - The workflow `self-test-skills.yml`: on pull requests that change `.claude-plugin/`, `permissions: contents: read`, no secret, pinned action versions as the other workflows.
   - `dependencies` of the orchestrator's `plugin.json`.
2. **`aleogr-repo-github`**: its five skills above.
3. **`aleogr-cloud-gcp`**: its four skills above.
4. **`aleogr-registry-gcp-artifact-registry`, `aleogr-db-gcp-cloud-sql`, `aleogr-stack-go`**: their four skills above.
5. **`aleogr`**: `tools-check` and `project-plan`, over the commands of tasks 2 to 4. The byte-identical paragraph "The database's settings" that `project-plan` shares with `project-apply` stays in `project-apply`; the plan's command holds the same rule in code, and a unit test pins the sentence.
6. **The shells and the documents.**
   - Each converted skill's `SKILL.md` becomes its shell (for the six skills converted in part: `mode=plan` runs the command, `mode=apply` keeps its prose).
   - At most ten model scenarios, run once: a shell passes its arguments and relays the answer with nothing added; `project-apply` still reads the plan's block.
   - `docs/DESIGN.md` (structure, behaviour of every skill, tests, implementation strategy, open items), `docs/CONTRACTS.md` where it describes how a skill runs, the READMEs of the plugins and of the tests. Version bumps.

Tasks 2, 3 and 4 run at the same time after task 1; task 5 after them; task 6 last. One review of the whole step at the end.

## Limits on the build

- No model scenario is run to test a rule: rules are tested in the direct mode and by unit tests.
- At most ten model scenarios in the whole step, once.
- One agent per task, fresh, and one for the final review. A second round only for a finding about cost, exposure, or a read that could write.

## Proof by a real run

In Cloud Shell, after the merge and the plugins' update, in `~/pilot`, with the shared instance stopped:

1. `/aleogr:project-plan`: the same fourteen rows, every action `none`, the line that the database was not read, `nothing to do`; no permission asked; how long it took.
2. `/aleogr:project-apply`: `unchanged`, `nothing to do`.

No cost: nothing is created and the instance is not started.
