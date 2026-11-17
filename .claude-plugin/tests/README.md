# Skill tests

A headless harness that runs the real skills of `plugins/aleogr`,
`plugins/aleogr-cloud-gcp` and `plugins/aleogr-db-gcp-cloud-sql` with `claude -p`, against a fake `gcloud`, and checks
which `gcloud` calls the skill made. Nothing is created outside the repository.

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
`PATH`, so the skill's `gcloud` calls reach `bin/gcloud`. The fake appends its
arguments (one line per call) to a log and prints a canned response. The
temporary directory, the log and Claude's output are removed afterwards.

## Adding a scenario

Create `scenarios/<name>/` with:

- `prompt.txt`: what the user types, for example `/aleogr-cloud-gcp:gcp_environment-describe project=demo environment=lab`.
- `responses/`: the canned output of the fake `gcloud`. A file answers a call
  when its name, without extension, is a prefix of the arguments with spaces
  written as `_` (`projects_list.txt` answers `projects list ...`). Otherwise
  `default.txt` answers, or nothing is printed. A name ending in `.exit1`
  (`projects_create.txt.exit1`) prints its content and makes the call fail.
  Numbered files (`billing_projects_describe_x.1.txt`, `...2.txt`) answer the
  first, second, ... call that matches the prefix, and later calls get the
  last file (`.exit1` may follow any number). Use them when a call must
  answer differently before and after a change, such as a billing link.
- `expect.txt`, one check per line (blank lines and `#` comments are ignored):

| Line | Holds when |
|---|---|
| `CALLED <regex>` | some logged call matches (the log has the arguments only, without `gcloud`) |
| `NOT_CALLED <regex>` | no logged call matches |
| `COUNT <n> <regex>` | at least `<n>` logged calls match (pins a repeated call, such as a check before and after a change) |
| `OUTPUT <regex>` | Claude's final answer matches |
| `RESULT_NOT <regex>` | no line inside the fenced `aleogr-result` block(s) of Claude's answer matches (fails when the answer has no such block; use it to keep identifiers out of the result block) |
| `ORDER <regex1> >> <regex2>` | the first call matching regex1 comes before the first matching regex2 |

Regexes are `grep -E`. Use fictitious values only: the repository is public.

`scenarios/harness-selftest` checks the harness itself.
