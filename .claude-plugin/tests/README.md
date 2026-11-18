# Skill tests

A headless harness that runs the real skills of `plugins/aleogr`,
`plugins/aleogr-cloud-gcp`, `plugins/aleogr-db-gcp-cloud-sql` and
`plugins/aleogr-repo-github` with `claude -p`, against a fake `gcloud` and a fake
`gh`, and checks which `gcloud` and `gh` calls the skill made. Nothing is created outside the repository.

```
bash .claude-plugin/tests/run.sh <scenario>
```

It exits 0 when every line of the scenario's `expect.txt` holds. On failure it
prints each failed line, the `gcloud` call log and Claude's output.

Requirements: an authenticated `claude` CLI, bash and coreutils. **Every run
costs model usage.** The model is `sonnet`; override it with `TEST_MODEL`.
Tests are run by hand; no workflow runs them.

## How it works

`run.sh` runs Claude from an empty temporary directory with `tests/bin` first on
`PATH`, so the skill's `gcloud` and `gh` calls reach `bin/gcloud` and `bin/gh`, two
wrappers of `bin/fake-cli`. The fake appends one line per call to a log and
prints a canned response. The `gcloud` line is its arguments; the `gh` line is
`gh <arguments>`, and when the arguments contain `--input <file>` it ends with
` <<< ` and the file's content with all whitespace removed (so a body file can be
checked: `CALLED ... --input .* <<< \{"name":"main"\}$`). The
temporary directory, the log and Claude's output are removed afterwards.

## Adding a scenario

Create `scenarios/<name>/` with:

- `prompt.txt`: what the user types, for example `/aleogr-cloud-gcp:gcp_environment-describe project=demo environment=dev`.
- `responses/`: the canned output of the fake `gcloud` and `gh`. A file answers a call
  when its name, without extension, is a prefix of the arguments with spaces
  written as `_` (`projects_list.txt` answers `projects list ...`). For `gh`
  the name starts with `gh_` and `/` is also written as `_`
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
  most recent wins, and when none applies the other files answer as above. For
  example `sql_instances_describe.txt.exit1` (missing),
  `sql_instances_describe+after+sql_instances_create.txt` (running) and
  `sql_instances_describe+after+sql_instances_patch.txt` (stopped) answer by
  what was done before each read, however many reads there are. A marker call
  counts even when it failed: for a change that fails first and works on a
  retry, use numbered files.
- `expect.txt`, one check per line (blank lines and `#` comments are ignored):

| Line | Holds when |
|---|---|
| `CALLED <regex>` | some logged call matches (a `gcloud` line has the arguments only, without `gcloud`; a `gh` line starts with `gh `) |
| `NOT_CALLED <regex>` | no logged call matches |
| `COUNT <n> <regex>` | at least `<n>` logged calls match (pins a repeated call, such as a check before and after a change) |
| `OUTPUT <regex>` | Claude's final answer matches |
| `RESULT_NOT <regex>` | no line inside the fenced `aleogr-result` block(s) of Claude's answer matches (fails when the answer has no such block; use it to keep identifiers out of the result block) |
| `ORDER <regex1> >> <regex2>` | the first call matching regex1 comes before the first matching regex2 |

Regexes are `grep -E`. Use fictitious values only: the repository is public.

`scenarios/harness-selftest` and `scenarios/harness-selftest-gh` check the harness itself.
