# Skill tests

A headless harness that runs the real skills of `plugins/aleogr`,
`plugins/aleogr-cloud-gcp`, `plugins/aleogr-db-gcp-cloud-sql`,
`plugins/aleogr-registry-gcp-artifact-registry`, `plugins/aleogr-repo-github` and
`plugins/aleogr-stack-go` with `claude -p` (or, in the direct mode below, their
commands, with no model), against a fake `gcloud`, a fake
`gh`, a fake `git`, a fake `go` and a fake `sleep`, and checks which calls the skill made and which files it wrote. Nothing is created outside the repository.

```
bash .claude-plugin/tests/run.sh <scenario>
```

It exits 0 when every line of the scenario's `expect.txt` holds. On failure it
prints each failed line, the call log and Claude's output.

Requirements: an authenticated `claude` CLI, bash and coreutils. **Every run
costs model usage.** The model is `sonnet`; override it with `TEST_MODEL`.
Runs with the model are made by hand; no workflow runs them.

## The direct mode: no model

Every skill's logic lives in its plugin's command, `plugins/<plugin>/bin/<plugin>`
(`docs/DESIGN.md` sections 2.2 and 10.4). The same scenarios run against that command
alone, with no model and no cost:

```
RUN_MODE=direct bash .claude-plugin/tests/run.sh <scenario>
bash .claude-plugin/tests/run-direct.sh                  # every scenario, in parallel
bash .claude-plugin/tests/run-direct.sh -s <skill>       # those whose prompt names the skill
bash .claude-plugin/tests/run-direct.sh <s1> <s2>        # named scenarios; -j <n> sets the parallelism
```

`run.sh` in the direct mode reads the scenario's `prompt.txt`, which must be one line
`/<plugin>:<skill> key=value ...` (only its first line with a `random` file, below), splits it as a shell splits words, with no expansion,
and runs `plugins/<plugin>/bin/<plugin> <skill> key=value ...` of this repository, by the
full real path of its executable (as a shell runs the command of its own plugin's folder,
`"${CLAUDE_PLUGIN_ROOT}/bin/<plugin>"`, never a command of that name found on `PATH`), in
the working folder, with `tests/bin` and every plugin's `bin/` first on `PATH`, the same fakes and `responses/`. The command's stdout is the
answer that the `OUTPUT`, `OUTPUT_NOT` and `RESULT_NOT` lines check; its stderr (each
provider command, `+ ` first, printed before it runs) is shown only on a failure. Every
other line of `expect.txt` is checked exactly as with the model. It exits 0 for a pass, 1
for a failure, 2 for bad usage, and **3, printing `NOT CONVERTED <scenario>`**, when the
scenario cannot be run this way.

**A run in more than one command.** When the command's answer ends with a block whose
`status` is `continue` (`docs/DESIGN.md` section 10.4), `run.sh` runs the command of its
`next:` line, as the shell's model will: the line is split with `shlex`, and it must be the
same plugin command, written as the full real path of the executable the harness ran first
(the command prints its own, in double quotes), the same skill, the same arguments and one
`run=<id>`, or the scenario fails (`(the answer says continue, but its next: line is not this command)`). It goes on
while the answer says `continue`, at most eight commands in all; a run still at `continue`
after the eighth fails (`(the run did not end within eight commands)`). The answer that the
`OUTPUT`, `OUTPUT_NOT` and `RESULT_NOT` lines check is the **last** command's stdout; the
call log, the files of the working folder and the stderr shown on a failure are the whole
run's, and a failure lists every command run. Every command must exit 0. The harness unsets
`ALEOGR_RUN_ENDS`, `ALEOGR_STEP_LIMIT`, `ALEOGR_WAIT_CLOCK_LIMIT`,
`ALEOGR_TEST_SLEEP_CLOCK`, `ALEOGR_TEST_RANDOM`, `FAKE_AFTER` and `FAKE_FOLDER` before each
command (and sets them only from the scenario's `clock`, `step-limit`, `random` and `after/`,
below), so a scenario does
not depend on the shell it is run from. The line `COMMANDS <n>` of `expect.txt` pins the
number of commands the run took (the direct mode only: with the model the loop is the
model's, and the line is not checked).

**The `clock` file.** The fake `sleep` returns at once, so the run's clock does not move and
every existing scenario runs in one command. A scenario that has a file `clock` holding the
one line `sleep-counts` runs with `ALEOGR_TEST_SLEEP_CLOCK=1`, in both modes (with the model,
the commands the model runs inherit it from `claude`): each `sleep <n>` that the fake
logs during a command moves that command's clock by `<n>` seconds (the shared module counts
the `sleep` lines of `FAKE_LOG`, and honours the variable only when `FAKE_LOG` is set, so
only under these fakes; it only adds to the clock, so it can only shorten a run). Thirty
seconds per wait reach the step limit of four minutes after eight waits, so such a scenario
continues over several commands, as a real run would. A `clock` file with any other content
is a bad scenario (exit 2). The loop and the `clock` file are tested on a copy of the
harness with stand-in commands (`unit/test_continue.py`). Nine scenarios have a `clock`
file. Three are of `platform-apply`: `platform-apply-continue-instance-create` (the instance's
creation cut by the clock in the first command and resumed with `resume=yes` in the second,
with the one-command answer), `platform-apply-continue-instance-resume-missing` (the same,
but the resumed create's own check reads the instance as missing: it creates nothing and
the run ends `failed`, saying the instance may run) and
`platform-apply-continue-instance-commands-limit` (an instance that never leaves its
creation: eight commands, one create and seven resumes, the eighth `pending`);
`platform-apply-continue-instance-carry-lost` is the second command of that run with its
carried file lost. Six are of `project-apply`: the two of the
`step-limit` file (below), and four, each made from a one-command scenario whose final
answer it pins: `project-apply-continue-start-wait-limit` (the instance's wait over three commands, to
its limit of thirty tries), `project-apply-continue-create-stopped` (the instance started in
the first command and ready in the second), `project-apply-continue-already-starting`
(an instance someone else started, never started by the run) and
`project-apply-continue-after-merge` (the run after a merge: the folder updated, an API
enabled and its wait, the instance started in the first command and ready in the second; the
last answer keeps every line of the first command, the start's sentence and its cost).
`project-apply`'s own wait is bounded by the clock's limit for waits, not by the step limit,
so its commands make thirteen waits each.

**The `step-limit` file.** A scenario that has a file `step-limit` holding one whole number
of seconds from 1 to 240 runs with `ALEOGR_STEP_LIMIT` set to it, in both modes (any other
content is a bad scenario, exit 2). The first step of a command after its plan is never held
by the step limit and every later one is (`docs/DESIGN.md` section 10.4), so a limit of one
second, shorter than any plan (a plan of the fakes takes more than a second), makes every
command of a run make exactly one step: that is how a real run proves the loop without a
wait. `project-apply-continue-step-limit` (as `project-apply-update-then-apply`: the
folder's update, the configure, the last plan, in three commands) and
`project-apply-continue-pull-rewrites` (below) have one, and pin `COMMANDS 3` and a final
answer that is the one-command run's.

**The `random` file.** A skill that makes up a random suffix (the `<random>` of a new GCP
project's id) cannot be pinned by a scenario. A scenario that has a file `random` holding one
line of 1 to 12 characters of `a-z` and `0-9` (such as `zz99`) runs with `ALEOGR_TEST_RANDOM`
set to it, in both modes (any other content is a bad scenario, exit 2). The shared module's
random-suffix helper honours it only when `FAKE_LOG` is set (so only under these fakes), and
only for a `<random>` of its own length made of the characters asked: the suffix of a project
id takes it, while the run's id and the names of temporary files, of other lengths, stay
random. In the direct mode such a scenario runs the command of the first line of its
`prompt.txt`: the second line is the model's ("Test run: wherever a random project ID suffix
is needed, use zz99 ..."). `platform-apply-billing-refused`, `platform-apply-empty` and
`platform-apply-empty-login` have one. The aid is tested in `unit/test_writes.py` (ignored
without `FAKE_LOG`, a malformed value ignored) and on the copy of the harness in
`unit/test_continue.py`.

**The folder `after/`: a call that rewrites the working folder.** A real `git pull` brings
the merged declaration into the folder; the fakes print canned text and change no file.
A scenario that has a folder `after/` holds, in `after/<name>/`, files that the fake
`gcloud`, `gh`, `git` and `go` (`bin/fake-cli`) copy over the working folder, dotfiles
included and at the same relative paths, each time a call matching `<name>` is made (after
the call is logged, before its response is printed). `<name>` is written as a response
file's name is: a prefix of the call with spaces written `_` (and `/` for `gh`, `git` and
`go`), `git_`, `gh_` or `go_` first, a `%` standing for one or more of `a-z0-9`; when
several folders match, all are copied, in glob order. So
`after/git_-c_credential.helper=_-c_credential.helper=!gh_auth_git-credential_pull/.aleogr/project.json`
becomes the folder's declaration when `github_checkout-setup` pulls. `run.sh` passes the
folder to the fakes as `FAKE_AFTER` and the working folder as `FAKE_FOLDER`, in both modes;
a scenario without `after/` changes no file, as before (the fake `go`'s
`responses/<prefix>.files/`, below, is the same idea for `go get` and `go mod tidy`, kept as
it is). `project-apply-pull-rewrites-declaration` (the folder behind, the pull bringing one
more topic: the repository is configured with the new topics and the run ends `nothing to
do`; built from the declaration as it was before the pull, the run of 505a827 failed it) and
`project-apply-continue-pull-rewrites` (the same over three commands: the digest of the
carried file is taken after the update, so the second command recalls the first) use it. The
digest taken after the update is also tested by a unit test (`TestDigestAfterTheUpdate` in
`unit/test_project_apply.py`).

"Not converted" means one of: the prompt is not one slash command of a skill (a prompt of
several lines without a `random` file, such as the `harness-selftest*` scenarios); the plugin
has no command; or the command answers 64 because that skill has no module (none is left).
`run-direct.sh` counts those apart, never as failures, and exits 1 only when a scenario
failed. At the end of step 1 it printed `passed 180, failed 0, not converted 493`; at the end
of part 2a of step 2, `passed 357, failed 0, not converted 316`; at the end of part 2b,
`passed 556, failed 0, not converted 117`; at the end of part 3a of step 3 it prints
`passed 635, failed 0, not converted 41` (the 76 scenarios of `project-apply` and the three
`project-apply-continue-*` pass; the 41 are the 35 scenarios of the three orchestrators still
prose and the 6 `harness-selftest*`); after the fixes of its final review, `passed 636`, with
the fourth `project-apply-continue-*`; after task 0 of part 3b, `passed 639`, with
`project-apply-continue-step-limit`, `project-apply-pull-rewrites-declaration` and
`project-apply-continue-pull-rewrites`. At the end of part 3b it prints `passed 680, failed 0,
not converted 6`: every scenario of every skill passes with no model (the 38 of
`platform-plan`, `platform-apply` and `project-access`, three of them the new
`platform-apply-continue-instance-*`, and the new `sql-create-resume`,
`sql-create-resume-refused` and `deploy-setup-env-access-refused` among them); the 6 left are the `harness-selftest*`
scenarios, which test `run.sh` with the model and whose prompts are not a slash command of a
skill. After the fixes of part 3b's final review it prints `passed 681, failed 0, not
converted 6`, with the new `platform-apply-continue-instance-resume-missing`.

A scenario of a command that writes runs in the scenario's working folder, a copy of its
`files/`, so the `FILE`, `SAME_FILE`, `NO_FILE` and `FILE_NOT` lines check what the command
wrote there. A command that refuses a read or a write it does not allow (a bug of the
command) prints a `failed` result and exits 70, which the direct mode reports as a failure.

**Unit tests**, with the standard library's `unittest`, cover the commands' rules without a
provider (the declaration's rules, each row's states, the arguments of each skill), that the
copies of `aleogr_common.py` are byte-identical, that the read-only runner refuses every
command that is not a read before running it, that the writing runner accepts only each
skill's own write shapes and that the refusals of Google Cloud hold for every skill
(`test_writes.py`), each cost gate (absent, with another value, and no write built then), how
each waiting skill ends when the eight-minute budget is spent, that an argument given twice,
a refused command, the run's time limit and an unexpected error still end with a `failed` result
(`test_refusals.py`), what each skill that creates something says when its run is aborted after
the create, and that every
script parses as Python 3.9:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .claude-plugin/tests/unit
```

In a unit test, load a skill's module with `helpers.load_skill(plugin, skill)`, never with
`from skills import ...`: every plugin has a package named `skills`.

**The writing runner.** A command writes only in `mode=apply`, without `--read-only`, through
`ctx.write` (a provider command), `ctx.write_file` (a file of the folder) and `ctx.backup` (copies
to put back). Each refuses, before anything runs or is shown, what is not on the skill's own
allowlist (`WRITE_SHAPES` and `FILE_WRITES` in `aleogr_common.py`), and `ctx.write_temp_file`
writes the one temporary file a skill names (`TEMP_FILE_WRITES`), created new, mode 0600, in a
private folder (`aleogr-<random>`, 0700) of the system's temporary folder that the process removes
when it ends. A wait is `ctx.wait()`, which runs `sleep 30` (so the fake logs it) and says no once
the run's eight minutes of waiting are spent, or when the wait would end after seven minutes of the
run (`WAIT_CLOCK_LIMIT`; the fake `sleep` returns at once, so in the scenarios the count decides).
Every provider command is bounded by the run's deadline (`RUN_DEADLINE`, nine and a half minutes):
past it the command is killed and the run ends with the `failed` result of an aborted run
(`aborted_result`), which any unexpected exception also gets, with no traceback; a unit test moves
the clock (`common.set_clock`) or raises `TimeLimit` from a context to reach these endings.
A run in more than one command (the status `continue`, its `next:` line, the carried file and
each of its refusals, the bound of eight commands, the deadline passed to a called command and
its `data.waitRefused` / `data.timeLimit`, the step limit, the environment variables that only
lower a limit, the uncounted wait `ctx.wait(counted=False)`) is tested in `test_continue.py`
with module objects given to `common.run_command`, an injected clock and a temporary folder
for the carried files (`common.set_carry_folder`).
A unit test replaces `ctx.execute(argv)`, the one place a command runs, to record each write.

**Golden commands.** Each writing skill's unit test holds its write commands exactly as the
skill's text gave them, every flag, in order, and checks that the module builds them argument
for argument, that a hidden value is a `Hidden` argument, and that each is on the allowlist
(`TestGoldenCommands`). Where a skill's text gave a whole file or text the command prints
(`ci.yml`, the declaration's canonical form, the login's list of what is left), or a unit test
checks the command's sentences against it (`gcp_environment-create`, `gcp_login-setup`), that
text, as the skill's SKILL.md held it before it became a shell, is kept in `unit/golden/`
and the unit test reads it there.

The workflow `self-test-skills.yml` runs the unit tests and `run-direct.sh` on every pull
request that changes `.claude-plugin/`. A skill's command passes its scenarios with
their `expect.txt` unchanged; a line that pins something only a model does is the only kind
that may change, and none has.

**A run with the model is needed only** for what the direct mode cannot see: that a shell
skill runs the right one of its commands with the arguments it was given and relays the answer
with nothing added, and that the shells of `project-apply` and `platform-apply` run each
`next:` command while the answer says `continue` and give the last answer (a
`project-apply-continue-*` or `platform-apply-continue-instance-*` scenario run with the model).
No skill is prose any more, and a rule is never tested with the model.

## How it works

With the model, `run.sh` runs Claude from an empty temporary directory with `tests/bin` first on
`PATH`, so the skill's `gcloud`, `gh`, `git` and `go` calls reach `bin/gcloud`, `bin/gh`, `bin/git` and
`bin/go`, four wrappers of `bin/fake-cli`. The fake appends one line per call to a log and
prints a canned response. The `gcloud` line is its arguments; the `gh`, `git` and `go` lines are
`gh <arguments>`, `git <arguments>` and `go <arguments>`, and when the arguments contain `--input <file>` it ends with
` <<< ` and the file's content with all whitespace removed (so a body file can be
checked: `CALLED ... --input .* <<< \{"name":"main"\}$`). The working folder starts with the content of the scenario's `files/` folder, if it has one. The
temporary directory, the log and Claude's output are removed afterwards.

`bin/sleep` is a fake wait: it appends `sleep <arguments>` to the same log and returns
at once, printing nothing, with exit 0. It reads no response file (a scenario's
`default.txt` or `default.txt.exit1` never answers it). A skill's wait is pinned as
`COUNT <n> ^sleep 30$`. Claude Code refuses a `sleep` run in the foreground before it
runs, so such a refused call is not logged; a `sleep` run in the background is logged,
returns at once, and the run goes on when its completion notice arrives. A `sleep` line
starts with `s`, so `NOT_CALLED ^([a-fi-z-]|g[^hi])` (below) also holds that the skill
did not wait.

`bin/go` is a fake Go command. It logs and answers through `bin/fake-cli` like the fake `gh`
and `git` (response names start with `go_`, with spaces and `/` written as `_`:
`go_version.txt` answers `go version`, `go_version.txt.exit127` makes Go absent,
`go_-C_web_get.txt.exit1` makes `go -C web get ...` fail). A real `go get` or `go mod tidy`
rewrites `go.mod` and `go.sum`; the fake does the same from a folder of the scenario's
`responses/`: when a call succeeds (exit 0) and `responses/<prefix>.files/` exists with
`<prefix>` a prefix of the call's response name (the longest wins), each file in that folder
is copied over the file of the same name in the call's working folder, which is the folder
after a leading `-C <dir>`, otherwise the current folder. So
`responses/go_-C_web_get.files/go.mod` and `.../go.sum` become `web/go.mod` and `web/go.sum`
after `go -C web get ...` (`go-setup-database-go-line-moved` uses this to move the `go`
line). A call that fails copies nothing, and a call with no such folder changes no file.
The fake never runs a real Go command and never reaches the network. `mktemp`, `cp` and
`rm` are not faked and not logged: a skill's copies and their putting back (`go_setup`
step 6) run for real, `mktemp -d` making its folder under the system's temporary folder, and
the `FILE` lines on `go.mod` and `go.sum` prove the result (`go-setup-database-toolchain-line`
pins the first and the last line of a multi-line `go.sum` put back).

## Adding a scenario

Create `scenarios/<name>/` with:

- `prompt.txt`: what the user types, for example `/aleogr-cloud-gcp:gcp_environment-describe project=demo environment=dev`.
- `files/` (optional): copied, dotfiles included, into the working folder before Claude starts (`files/.aleogr/project.json` becomes `<cwd>/.aleogr/project.json`).
- `after/` (optional): `after/<name>/` holds files copied over the working folder each time a call matching `<name>` is made (the pull that brings a merged declaration; see "The folder `after/`" above).
- `clock` and `step-limit` (optional): one line each, `sleep-counts` and a whole number of seconds from 1 to 240 (see above).
- `responses/`: the canned output of the fake `gcloud`, `gh`, `git` and `go`, and the
  `<prefix>.files/` folders of the fake `go` (above). A file answers a call
  when its name, without extension, is a prefix of the arguments with spaces
  written as `_` (`projects_list.txt` answers `projects list ...`). For `gh`, `git` and `go`
  the name starts with `gh_`, `git_` or `go_` and `/` is also written as `_`
  (`gh_api_repos_example-org_example-repo.txt` answers
  `gh api repos/example-org/example-repo ...`). When several names are a
  prefix, the longest wins (`gh_api_repos_example-org_example-repo_rulesets.txt`
  answers `gh api repos/example-org/example-repo/rulesets` even next to the
  shorter file). Otherwise
  `default.txt` answers, or nothing is printed. A name ending in `.exit1`
  (`projects_create.txt.exit1`) prints its content and makes the call fail; a name ending in `.exit127`
  (`gh_--version.txt.exit127`) prints its content and exits 127, as an absent
  command does.
  Numbered files (`billing_projects_describe_x.1.txt`, `...2.txt`) answer the
  first, second, ... call that matches the prefix, and later calls get the
  last file (`.exit1` may follow any number). They count every matching call,
  so they break when a model reads one more or one less time than the fixture
  assumes: prefer state responses below for "before and after a change".
  State responses (`<prefix>+after+<marker>.txt`, `.exit1` allowed) answer a
  call that matches `<prefix>` once an earlier call matching `<marker>` (same
  `_` rule) is in the log; when several apply, the one whose marker call is the
  most recent wins (on the same marker call, the one with the longest prefix,
  as for the files above), and when none applies the other files answer as above. For
  example `sql_instances_describe.txt.exit1` (missing),
  `sql_instances_describe+after+sql_instances_create.txt` (running) and
  `sql_instances_describe+after+sql_instances_patch.txt` (stopped) answer by
  what was done before each read, however many reads there are. A marker call
  counts even when it failed: for a change that fails first and works on a
  retry, use numbered files.
  A `+after+` file on the repository read (`gh_api_repos_example-org_demo+after+gh_repo_edit.txt`)
  also answers the `contents`, `commits` and `rulesets` reads, whose names it is
  a prefix of. Give each of those reads its own state file on the same marker
  (`gh_api_repos_example-org_demo_contents+after+gh_repo_edit.txt`, ...): the
  longer prefix wins the tie, so every read answers by what was done before it,
  whatever the number of reads (`project-apply-update-then-apply` does this).
  Some `project-apply-*` scenarios still use numbered files for the repository
  read (`gh_api_repos_example-org_demo.1.txt`, ...): a model that reads the
  repository once more or once less than such a fixture assumes fails the
  scenario (it never passes it wrongly): rerun such a failure before debugging it.
  Two rules serve a value the skill makes up, such as the random suffix of a GCP
  project id. A `%` in a file's name stands for one or more of `a-z0-9`
  (`projects_describe_aleogr-dev-demo-%_--format=json.txt` answers
  `projects describe aleogr-dev-demo-x7k2 --format=json`); the longest name still wins.
  `{{log:<regex>}}` in a file's content is replaced by the last text of the call log,
  this call's line included, that matches the `grep -E` regex (which must not contain
  `}}`), or by nothing: `projects_list+after+projects_create.txt` holding
  `{{log:aleogr-dev-demo-[a-z0-9][a-z0-9][a-z0-9][a-z0-9]}}` answers the search with the
  id the skill created (`project-apply-environment-new-project` does this). Names without
  `%` and contents without `{{log:` behave as before.
- `expect.txt`, one check per line (blank lines and `#` comments are ignored):

| Line | Holds when |
|---|---|
| `CALLED <regex>` | some logged call matches (a `gcloud` line has the arguments only, without `gcloud`; a `gh` line starts with `gh `, a `git` line with `git `, a `go` line with `go `) |
| `NOT_CALLED <regex>` | no logged call matches |
| `COUNT <n> <regex>` | at least `<n>` logged calls match (pins a repeated call, such as a check before and after a change) |
| `AT_MOST <n> <regex>` | at most `<n>` logged calls match (`0` included; pins that a call is not repeated, such as one start or one pull request: `AT_MOST 1 ^sql instances patch`) |
| `COMMANDS <n>` | the run took exactly `<n>` commands, the first and the `next:` ones (the direct mode only; with the model the line is not checked) |
| `OUTPUT <regex>` | Claude's final answer matches |
| `OUTPUT_NOT <regex>` | Claude's final answer does not match (keeps raw error text out of the answer) |
| `RESULT_NOT <regex>` | no line inside the fenced `aleogr-result` block(s) of Claude's answer matches (fails when the answer has no such block; use it to keep identifiers out of the result block) |
| `FILE <relative path> <regex>` | the file exists in the working folder after the run and some line of it matches (the regex is required: a `FILE` line with a path only is a bad expect line and fails) |
| `SAME_FILE <relative path> <repository path>` | the file exists in the working folder after the run and is byte for byte (`cmp`) the file at `<repository path>`, relative to the repository's root (pins a template written unchanged: `SAME_FILE web/db.go .claude-plugin/plugins/aleogr-stack-go/files/db.go.tmpl`) |
| `NO_FILE <relative path>` | the file does not exist in the working folder after the run |
| `FILE_NOT <relative path> <regex>` | the file does not exist in the working folder after the run, or no line of it matches (the regex is required, as for `FILE`; pins that a written file lacks something) |
| `ORDER <regex1> >> <regex2>` | the first call matching regex1 comes before the first matching regex2 |

Regexes are `grep -E`. Use fictitious values only: the repository is public.

Claude Code itself runs `git ... ls-files --error-unmatch -- :(icase).claude/settings.local.json` through `PATH` during a run. `run.sh` drops the lines of that exact call from the call log before the checks, so `NOT_CALLED .` holds when the skill ran nothing. Pinning the subcommand remains good practice (`NOT_CALLED ^git (add|commit|push)` rather than a bare `NOT_CALLED ^git`): Claude Code may run other commands in a later version.

A `gcloud` line has no word `gcloud` in it, so `NOT_CALLED ^gcloud` holds whatever ran. To pin that a skill ran no `gcloud` command, pin the subcommands instead: `NOT_CALLED ^(projects|services|artifacts|iam)( |$)`, or, to cover every `gcloud` line while letting `gh` and `git` through, `NOT_CALLED ^([a-fi-z-]|g[^hi])` (as `project-plan-nothing-to-do` does). That pattern also
matches a `go` line (`go ` is `g` then `o`), so it holds that no `go` command ran either.

`scenarios/harness-selftest`, `scenarios/harness-selftest-gh`, `scenarios/harness-selftest-files`, `scenarios/harness-selftest-state`, `scenarios/harness-selftest-sleep` and `scenarios/harness-selftest-go` check the harness itself.
