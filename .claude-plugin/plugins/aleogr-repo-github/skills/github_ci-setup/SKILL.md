---
description: GitHub CI setup, with the gh CLI. Use to write a project's `.github/workflows/ci.yml`, which runs a reusable workflow once per declared component (only when that component's folder or the file itself changed) and ends with one job `ci` that is the required status check, plus, when an environment is given, one deploy job per listed component (those whose service exists) that runs only on a push to the default branch, or, in plan mode, to learn whether the file in this folder and in the repository is as declared. The file's first line is a marker built from the components; the reusable workflow is pinned by commit, kept when the file is regenerated. Writes only that file in this folder; never commits or pushes (a pull request carries it). Plan by default.
allowed-tools: Bash(aleogr-repo-github --read-only github_ci-setup), Bash(aleogr-repo-github --read-only github_ci-setup *)
---

# github_ci-setup

Writes the project's CI file, `.github/workflows/ci.yml`, in the current folder, from the components the caller declares. The file has one job per component, which calls the reusable workflow of the component's stack (`ci-go.yml` of the `workflows` repository, pinned by commit) when that component's folder, or `ci.yml` itself, changed; and a last job `ci`, the status check that branch protection requires, which passes only when the change detection succeeded and every component job passed or was skipped. With `deploy`, the job of each component listed in `deployComponents` (the components whose service exists) is followed by a deploy job, which calls the reusable workflow `deploy-cloud-run.yml` of the same repository, at the same commit, only on a push to the default branch and only after that component's job succeeded; the deploy jobs are not part of the job `ci`. A component not listed gets no deploy job, so a component added to a deployed project neither breaks the default branch nor stops the others' deploys.

The first line of the file is a marker, `# aleogr-ci 1 <name>:<path>:<stack>:<version>,...` (or, with `deploy`, `# aleogr-ci 2 <name>:<path>:<stack>:<version>,... deploy=<environment>:<name>+... project=<project> branch=<defaultBranch> region=<region>`, so that a change of the deployed components, of the project, of the default branch or of the region, all written into the deploy jobs, also rewrites the file), with the components sorted by name. Whether a file is "as declared" is decided by comparing that line, never the rest of the file. The file is fully owned by the tooling: when the marker differs it is rewritten whole. It reads the copy on the repository's default branch only to report it. It never commits, pushes or opens anything: the pull request that proposes the change carries the file.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `components=<name>:<path>:<stack>:<version>[,...]` | The declared components, comma-separated, in any order. Empty or not given: no component. |
| `workflows=<owner>/<name>` | The repository that holds the reusable workflows. Required when `components` is not empty. |
| `ref=<keep\|latest>` | `keep` (default) keeps the commit the existing file pins (with `deploy`, only when that file's marker is of version 2 and it pins the deploy workflow at the same commit); `latest` pins the head of the `workflows` repository's `main`. |
| `defaultBranch=<branch>` | The repository's default branch, the one `push` runs CI on. Default `main`. |
| `deploy=<environment>[,...]` | The environments the components of `deployComponents` are deployed to by CI. Empty or not given: no deploy job, and the file and its marker are those of version 1. This version accepts exactly one environment. |
| `deployComponents=<name>[,...]` | The components that get a deploy job (those whose service exists), comma-separated, in any order. Required when `deploy` is not empty; not allowed otherwise. |
| `region=<region>` | The region of the services, written literally in each deploy job (it is in the public declaration; it is not an identifier). Required when `deploy` is not empty; not used otherwise. |
| `project=<project>` | The project name; each component's service is `<project>-<name>`. Required when `deploy` is not empty; not used otherwise. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` writes the file when it is missing or differs. |

`owner` and `name` are required, `workflows` is required when `components` is not empty, and `project`, `deployComponents` and `region` are required when `deploy` is not empty. A region is never guessed: it is given.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-repo-github github_ci-setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-repo-github --read-only github_ci-setup <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command aleogr-repo-github ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command aleogr-repo-github could not be run: update the plugin aleogr-repo-github, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "ci-setup",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-repo-github, then try again" } ]
}
```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
