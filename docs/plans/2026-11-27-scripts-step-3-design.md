# Skills as thin shells over scripts, step 3: design

Status: proposed on 2026-11-27, not built. The last step of [the design](2026-11-27-scripts-design.md): the four skills that invoke other skills. After it every skill is a shell over a command and no rule is written as prose. No command, argument or answer of the owner changes.

## What is converted

| Skill | What it is | Scenarios |
|---|---|---|
| `project-apply` | makes what the plan says is missing, in order, with its waits | 76 |
| `platform-plan` | reads the shared platform | 12 |
| `platform-apply` | creates the shared platform | 16 |
| `project-access` | lets a person in | 7 |

The 111 scenarios are the last that need a model. After this step a model run is needed only to check that a shell passes its arguments and relays the answer.

## Two parts, two pull requests

- **3a: `project-apply`**, and what a run longer than one command needs (below).
- **3b: `platform-plan`, `platform-apply`, `project-access`**, the creation of the instance made resumable, and the clean-up that the end of the prose allows.

## The problem this step has and the others did not

A command runs under the tool's timeout of ten minutes, and since step 2 it bounds itself to nine and a half. A leaf skill fits. An orchestrator does not always: the start of the shared instance alone takes ten to fifteen minutes, and a run after a merge may enable an API, start the instance, and create several things, each with its own wait.

### A run in more than one command

`aleogr project-apply` does as much as fits and, when it cannot finish in time, ends with the status `continue` and one line that says what it is waiting for. The shell tells the model: while the answer's block says `continue`, run the command again, exactly as its `next:` line writes it, in the foreground, and say nothing else in between. The answer of the last command is the answer of the run.

- **A new command starts from the top**: it plans again and makes what is still missing. Nothing is skipped by memory. This is safe by a rule the tooling already has: every skill reads before it changes, so a run can always be run again. It costs one more plan (about forty seconds) for each continuation, and a run that fits in one command has none: the real run after a merge of part 2a took under two minutes.
- **When it stops to continue.** Before each step, when the run's clock has passed four minutes; and when a wait or a called command is ended by the clock. A called command gets the caller's deadline, so it cannot outlive it, and says in its result when the clock ended its wait; the caller then answers `continue` and does not treat it as a failure.
- **What is carried from one command to the next** is only what the answer needs and a count: the lines of what the earlier commands made, whether this run started the instance, and how many tries the instance's wait has used (the limit stays thirty tries for the whole run). It is kept in a private file of the machine's temporary folder, named in the `next:` line by a short random id; it holds no secret and no value of a provider's output. A file that is missing or does not match the declaration is ignored: the run goes on as a new one and its answer says that an earlier part of it could not be recalled.
- **A bound.** At most eight commands for one run. Past that the run ends as its text ends a wait that passed its limit, with what was made and what is left.
- **Cost.** A continuation never repeats a confirmation by itself: `confirm=yes` is in the `next:` line because the owner gave it for this run, and the instance is started only in the conditions of [DESIGN.md](../DESIGN.md) section 6.4, checked again by each command from what it reads.

### The owner sees progress

Between two commands the model shows the one line of the `continue` answer (`Waiting for the shared instance: try 14 of 30.`). During a command nothing is shown, as in step 2.

## Structure

- `project-apply` and the platform's orchestrators call the plan as a function of their own plugin (step 1 kept reading, deciding and printing apart for this) and the other plugins' commands through `call_plugin`, in `mode=apply` only where their text does.
- **The orchestrator writes nothing itself.** It runs no provider command that changes something: every write is a called skill's, inside that skill's own allowlist of writes. Its only own commands are reads and `sleep 30`.
- The gates stay where they are and are now code: `confirm=yes` for the run, `confirmVisibility=<value>` for a change of visibility, the announcement before a GCP project is created, the night stop read before the instance is started, Go checked and the check's code written before any cost.
- The prescribed sentences, the order of the answer and the result block are unchanged.

## Part 3b also closes

- **The creation of the instance becomes resumable.** `gcp-cloud-sql_instance-create` gains the argument `resume=yes`, given only by `platform-apply` when its own run created the instance in an earlier command: the skill then skips the creation, waits for the instance, stops it and tests the night stop, as its text does after a creation. Without the carried file (another machine, a lost session) the behaviour is today's: the answer says the instance runs, what it costs and how to stop it.
- **The paragraph "When another skill invoked this one"** leaves every shell: no prose skill invokes another any more, and commands talk through `--json`.
- **`gcp_deploy-setup` after a refused grant** (open item of part 2b): one reading is chosen and pinned by a scenario.

## Tests

- The 111 scenarios pass in the direct mode with their expectations unchanged. With the fake `sleep` the clock never ends a wait, so each scenario runs in one command, as it did as prose: the count of waits and the order of calls stay as pinned.
- **The continuation is tested on purpose**: unit tests with an injected clock for every place a run can stop to continue, and a few new scenarios in which the harness makes each `sleep` count as thirty seconds of the clock and runs the `next:` command until the run ends, as the model will. They pin that the answer is the same as the one-command run's, that the tries add up to thirty, that nothing is made twice, and that the instance is not started by a continuation that finds it starting.
- Model runs: at most ten per part, once: the shell's loop, and the answer relayed.

## Real runs

- **3a, no cost:** `project-apply` with nothing to do, and the run after a merge of a harmless change, both timed. Then the continuation for real: the same run with the step limit lowered by an environment variable that can only shorten it, so that an ordinary run is forced into two or three commands; the answer must be the one-command answer.
- **3a, cents, optional:** the instance started through `project-apply` needs something missing in the database, and both components have theirs. It is exercised when a third component or a new project needs the database; until then the long wait across commands is proven by the forced continuation and the scenarios.
- **3b, no cost:** `platform-plan` (`nothing to do`) and `project-access` listing who has access. `platform-apply` creates a platform that exists: it is run once to see `nothing to do`.

## Known limits

- A run that needs several commands plans again in each: about forty seconds more per continuation.
- The loop between commands is the model's: a shell that stops the loop early leaves a run unfinished with a `continue` answer on the screen, which says the command to run.
- What a run made in its earlier commands is recalled from a file of the machine: on another machine the answer of a continued run lacks those lines and says so.
