# Skill tests

A headless harness that runs the real skills of `plugins/aleogr`,
`plugins/aleogr-cloud-gcp`, `plugins/aleogr-db-gcp-cloud-sql`,
`plugins/aleogr-registry-gcp-artifact-registry`, `plugins/aleogr-repo-github` and
`plugins/aleogr-stack-go` with `claude -p`, against a fake `gcloud`, a fake
`gh` and a fake `git`, and checks which calls the skill made and which files it wrote. Nothing is created outside the repository.

```
bash .claude-plugin/tests/run.sh <scenario>
```

It exits 0 when every line of the scenario's `expect.txt` holds. On failure it
prints each failed line, the call log and Claude's output.

Requirements: an authenticated `claude` CLI, bash and coreutils. **Every run
costs model usage.** The model is `sonnet`; override it with `TEST_MODEL`.
Tests are run by hand; no workflow runs them.

## How it works

`run.sh` runs Claude from an empty temporary directory with `tests/bin` first on
`PATH`, so the skill's `gcloud`, `gh` and `git` calls reach `bin/gcloud`, `bin/gh` and `bin/git`, three
wrappers of `bin/fake-cli`. The fake appends one line per call to a log and
prints a canned response. The `gcloud` line is its arguments; the `gh` and `git` lines are
`gh <arguments>` and `git <arguments>`, and when the arguments contain `--input <file>` it ends with
` <<< ` and the file's content with all whitespace removed (so a body file can be
checked: `CALLED ... --input .* <<< \{"name":"main"\}$`). The working folder starts with the content of the scenario's `files/` folder, if it has one. The
temporary directory, the log and Claude's output are removed afterwards.

## Adding a scenario

Create `scenarios/<name>/` with:

- `prompt.txt`: what the user types, for example `/aleogr-cloud-gcp:gcp_environment-describe project=demo environment=dev`.
- `files/` (optional): copied, dotfiles included, into the working folder before Claude starts (`files/.aleogr/project.json` becomes `<cwd>/.aleogr/project.json`).
- `responses/`: the canned output of the fake `gcloud`, `gh` and `git`. A file answers a call
  when its name, without extension, is a prefix of the arguments with spaces
  written as `_` (`projects_list.txt` answers `projects list ...`). For `gh` and `git`
  the name starts with `gh_` or `git_` and `/` is also written as `_`
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
- `expect.txt`, one check per line (blank lines and `#` comments are ignored):

| Line | Holds when |
|---|---|
| `CALLED <regex>` | some logged call matches (a `gcloud` line has the arguments only, without `gcloud`; a `gh` line starts with `gh `, a `git` line with `git `) |
| `NOT_CALLED <regex>` | no logged call matches |
| `COUNT <n> <regex>` | at least `<n>` logged calls match (pins a repeated call, such as a check before and after a change) |
| `OUTPUT <regex>` | Claude's final answer matches |
| `OUTPUT_NOT <regex>` | Claude's final answer does not match (keeps raw error text out of the answer) |
| `RESULT_NOT <regex>` | no line inside the fenced `aleogr-result` block(s) of Claude's answer matches (fails when the answer has no such block; use it to keep identifiers out of the result block) |
| `FILE <relative path> <regex>` | the file exists in the working folder after the run and some line of it matches (the regex is required: a `FILE` line with a path only is a bad expect line and fails) |
| `NO_FILE <relative path>` | the file does not exist in the working folder after the run |
| `ORDER <regex1> >> <regex2>` | the first call matching regex1 comes before the first matching regex2 |

Regexes are `grep -E`. Use fictitious values only: the repository is public.

Claude Code itself runs `git ... ls-files --error-unmatch -- :(icase).claude/settings.local.json` through `PATH` during a run. `run.sh` drops the lines of that exact call from the call log before the checks, so `NOT_CALLED .` holds when the skill ran nothing. Pinning the subcommand remains good practice (`NOT_CALLED ^git (add|commit|push)` rather than a bare `NOT_CALLED ^git`): Claude Code may run other commands in a later version.

`scenarios/harness-selftest`, `scenarios/harness-selftest-gh`, `scenarios/harness-selftest-files` and `scenarios/harness-selftest-state` check the harness itself.
