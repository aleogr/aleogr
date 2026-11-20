---
description: GitHub CI setup, with the gh CLI. Use to write a project's `.github/workflows/ci.yml`, which runs a reusable workflow once per declared component (only when that component's folder or the file itself changed) and ends with one job `ci` that is the required status check, plus, when an environment is given, one deploy job per listed component (those whose service exists) that runs only on a push to the default branch, or, in plan mode, to learn whether the file in this folder and in the repository is as declared. The file's first line is a marker built from the components; the reusable workflow is pinned by commit, kept when the file is regenerated. Writes only that file in this folder; never commits or pushes (a pull request carries it). Plan by default.
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

`owner` and `name` are required, `workflows` is required when `components` is not empty, and `project`, `deployComponents` and `region` are required when `deploy` is not empty: a missing one ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command or read; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `workflows`, when given, is `<owner>/<name>`: exactly one `/`, the part before it follows the rule of `owner`, the part after it the rule of `name`.
- `components`, when not empty, is one or more entries separated by `,`, with no empty entry. Each entry is exactly four fields separated by `:`, `<name>:<path>:<stack>:<version>`:
  - `name` has 1 to 20 characters of `a-z`, `0-9` and `-`, starts with a letter, and is not `changes` or `ci` (those are the file's own jobs), does not start with `deploy-` (a deploy job's name could be the same as a component's) nor is `true`, `false`, `null`, `yes`, `no`, `on` or `off` (as a job name or a filter key YAML would read it as something other than text). No two entries have the same `name`.
  - `path` is the component's folder, relative to the repository's root; empty means the same as `name`. It is made of one or more parts separated by `/` (so it does not start or end with `/` and has no empty part). Each part uses only `a-z`, `0-9`, `-`, `_` and `.`; it is not `.` or `..`, does not start with `-` or `.`, and does not end with `.` (so `.github`, `.aleogr` and every folder under them are never a component's folder). No two entries have the same `path` (after an empty one is replaced by its `name`), and no entry's `path` is inside another entry's `path` (`web` and `web/api` cannot both be components): one module per component folder.
  - `stack` is `go`, the only stack implemented.
  - `version` matches `^[0-9]+\.[0-9]+$` (for example `1.27`).
- `ref`, when given, is `keep` or `latest`.
- `defaultBranch`, when given, has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_`, `-` and `/`, does not start with `-` or `/`, does not end with `/` or `.`, and has no `..` and no `//`.
- `deploy`, when not empty, is one or more entries separated by `,`, with no empty entry; each entry has 1 to 20 characters of `a-z` and `0-9` and starts with a letter. More than one entry fails with exactly the sentence `deploy names more than one environment; this version deploys to exactly one, because the Actions variables the deploy job reads would clash.` (no command).
- `deploy` not empty and `region` not given (or empty): the run fails with exactly the sentence `deploy needs region=<region>: the deploy jobs write the services' region, which is never guessed.` and no command. Never take a region from anywhere else.
- `region`, when `deploy` is not empty, has 1 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`.
- `project`, when `deploy` is not empty, has 1 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`.
- `deployComponents`, when given: `deploy` is not empty (otherwise the run fails with exactly the sentence `deployComponents is given without deploy; give deploy=<environment> as well, or leave deployComponents out.`); it is one or more names separated by `,`, with no empty entry and no name twice; and each name is the `name` of one of `components` (otherwise the run fails with exactly the sentence `deployComponents names <name>, which is not one of the components.`, with the first such name). An empty `deployComponents` with `deploy` not empty is missing. No command in any of these cases.
- When `deploy` is not empty, each listed component's service name `<project>-<name>` (the components of `deployComponents` only) has 6 to 30 characters and no listed component's `name` ends with `-` (the rule the service skills enforce). Otherwise the run fails with exactly the sentence `The service name <project>-<name> breaks the rule on service names (6 to 30 characters, not ending with -); shorten the project or the component name.` (with the first such service, in the order of the sorted listed components) and no command.
- `mode`, when given, is `plan` or `apply`.

Below, the components are always taken **sorted by `name`**, in byte order (ASCII), with each empty `path` replaced by its `name`. The **marker** is the text `# aleogr-ci 1 ` followed by the entries `<name>:<path>:<stack>:<version>` of the sorted components, joined by `,`, with no space (for `components=web:web:go:1.27,api:services/api:go:1.27` it is `# aleogr-ci 1 api:services/api:go:1.27,web:web:go:1.27`). With `deploy` not empty, the **marker** is instead the text `# aleogr-ci 2 `, the same entries joined by `,`, one space, `deploy=`, the environment, `:` and the names of `deployComponents` sorted by name and joined by `+`, one space, `project=<project>`, one space, `branch=<defaultBranch>`, one space, `region=<region>` (for the same components, `deploy=dev`, `deployComponents=web,api`, `project=demo`, the default branch `main` and `region=us-central1` it is `# aleogr-ci 2 api:services/api:go:1.27,web:web:go:1.27 deploy=dev:api+web project=demo branch=main region=us-central1`; with `deployComponents=api` it ends `deploy=dev:api project=demo branch=main region=us-central1`). With no component there is no marker, with or without `deploy`.

## Steps

Show each command before running it. Run only the commands below, in this order, each at most once: no `gh auth status`, no `gh repo view`, no other `gh api` call, no `gh pr`, no `git` command of any kind (no `git add`, no `git commit`, no `git push`), no other command, no retry. Read and write the local file with the Read and Write tools only, never a shell command. Write no file other than `.github/workflows/ci.yml`, and never delete or rename a file.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

1. Read the local file `.github/workflows/ci.yml` with the Read tool. It does not exist: it is missing. It exists: keep its first line (with a trailing carriage return removed) and its content, for step 3.

2. Read the repository's copy, from its default branch:

   ```
   gh api repos/<owner>/<name>/contents/.github/workflows/ci.yml -H "Accept: application/vnd.github.raw"
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: the file (or the repository) is not there. `inRepository` is `false`. Continue.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else): `failed`. Whether the repository has the file is unknown: never report it as absent. Say exactly `The repository's CI file could not be read; nothing was written. Check that gh is signed in, may read the repository, and that GitHub answers, then run this skill again.` Never explain which text decided this, and repeat no word of `gh`'s answer (not its message, not its HTTP status or status words): that sentence is all the answer says about the failure. Write nothing and run nothing else.
   - Exit 0: the output is the repository's copy. `inRepository` is `true`; `repositoryAsDeclared` is `true` when its first line (with a trailing carriage return removed) equals the marker, `false` otherwise (and `false` whenever there is no component). Continue.

3. Decide `local`, then the status:

   - No component and the local file is missing: `local` is `not-needed`. `status` `unchanged`, in `plan` and in `apply`. Run nothing else.
   - No component and the local file exists: `local` is `differs`. `status` `pending`, in `plan` and in `apply`, with the item `ci.yml is not needed`: the file is left as it is, and the answer says to remove it by hand (removing it is not done by this skill). Run nothing else.
   - The local file's first line equals the marker: `local` is `as-declared`. `status` `unchanged`, in `plan` and in `apply`. Run nothing else.
   - The local file is missing: `local` is `missing`. `plan`: `status` `would-create`. `apply`: go to step 4.
   - Otherwise (the file exists and its first line is not the marker): `local` is `differs`. `plan`: `status` `would-update`. `apply`: go to step 4.

   In `plan`, say which commit `apply` would pin (by the rule of step 4, without running its command) and run nothing else.

4. `apply` only: choose the commit `<sha>` of the reusable workflow.

   - `ref` is `keep`, `deploy` is empty, and the local file exists: look in its content for the lines `uses: <workflows>/.github/workflows/ci-<stack>.yml@<commit>`, where `<workflows>` is the argument exactly and `<commit>` is 40 characters of `0-9` and `a-f`. At least one such line, and every one names the same commit: that commit is `<sha>`; run no command; go to step 5. Otherwise (no such line, or lines naming different commits): read it as below.
   - `ref` is `keep`, `deploy` is not empty, the local file exists and its first line starts with `# aleogr-ci 2 `: look in its content for the lines `uses: <workflows>/.github/workflows/ci-<stack>.yml@<commit>` and the lines `uses: <workflows>/.github/workflows/deploy-cloud-run.yml@<commit>`, as above. At least one line of each kind, and every one of them names the same commit: that commit is `<sha>`; run no command; go to step 5. Otherwise (a kind with no line, or lines naming different commits): read it as below.
   - Otherwise (`ref` is `latest`; or the local file is missing; or `deploy` is not empty and the local file's marker is not of version 2, whose commit may be older than the deploy workflow), read the head of the `workflows` repository's `main`:

     ```
     gh api repos/<workflows>/commits/main
     ```

     - Exit 0 and the JSON has a `sha` of 40 characters of `0-9` and `a-f`: it is `<sha>`. Go to step 5.
     - Non-zero exit and the output contains `HTTP 404`: `failed`. Say in one sentence that the repository `<workflows>` or its branch `main` was not found. Write nothing.
     - Any other answer: `failed`. Say the cause in one sentence, with no raw error text. Write nothing.

5. `apply` only: write `.github/workflows/ci.yml` with the Write tool (it creates the folder), replacing the whole file. The content is exactly the text below, built from the sorted components, with `<branch>` the `defaultBranch`, `<workflows>` the argument, `<sha>` the commit of step 4, two spaces per indentation level, no tab, no trailing space, and one line break at the end. The `working-directory`, `go-version`, `service` and `image-name` values are written in double quotes, as shown; the `region` value too; the values that are expressions (`${{ secrets.<NAME> }}`) are written without quotes, as shown. No `vars.` is ever written. The two action commits and their version comments are fixed: write them exactly as here. Nothing is added, removed or reordered.

   The text, in five parts (part d has its deploy jobs only when `deploy` is not empty):

   a. The head, once (the first line is the marker):

   ```yaml
   <marker>
   # Generated by aleogr from .aleogr/project.json. Do not edit: change the declaration and run project-apply.
   name: ci

   on:
     pull_request:
     push:
       branches: [<branch>]

   permissions:
     contents: read

   jobs:
     changes:
       runs-on: ubuntu-latest
       permissions:
         contents: read
         pull-requests: read
       outputs:
   ```

   b. For each component, in order, one line:

   ```yaml
         <name>: ${{ steps.filter.outputs.<name> }}
   ```

   c. Then, once:

   ```yaml
       steps:
         - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
         - id: filter
           uses: dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d # v4.0.3
           with:
             filters: |
   ```

   followed, for each component in order, by its three lines (a change to `ci.yml` itself runs every component):

   ```yaml
               <name>:
                 - '<path>/**'
                 - '.github/workflows/ci.yml'
   ```

   d. For each component, in order, an empty line and its job:

   ```yaml

     <name>:
       needs: changes
       if: needs.changes.outputs.<name> == 'true'
       uses: <workflows>/.github/workflows/ci-<stack>.yml@<sha>
       with:
         working-directory: "<path>"
         go-version: "<version>"
   ```

   and then, when `deploy` is not empty and the component is listed in `deployComponents`, for each environment in `deploy`, an empty line and its deploy job (a component not listed has none), with `<project>` the argument:

   ```yaml

     deploy-<name>-<environment>:
       needs: [<name>]
       if: github.event_name == 'push' && github.ref == 'refs/heads/<branch>' && needs.<name>.result == 'success'
       permissions:
         contents: read
         id-token: write
       uses: <workflows>/.github/workflows/deploy-cloud-run.yml@<sha>
       with:
         working-directory: "<path>"
         service: "<project>-<name>"
         image-name: "<name>"
         region: "<region>"
       secrets:
         project-id: ${{ secrets.GCP_PROJECT_ID }}
         workload-identity-provider: ${{ secrets.GCP_WIF_PROVIDER }}
         service-account: ${{ secrets.GCP_CI_ACCOUNT }}
         image-path: ${{ secrets.GCP_IMAGE_PATH }}
   ```

   The four identifiers are the repository's Actions secrets (`github_variables-set kind=secrets` sets them): GitHub masks them in every log and never gives them to a pull request from a fork. They go as `secrets:` of the reusable workflow; `secrets: inherit` is never written. The deploy job runs only on a push to the default branch, never on a pull request: no trigger other than `pull_request` and `push` is ever written (never `pull_request_target`, never `workflow_run`).

   e. The job `ci`, once, after an empty line. `<names>` is the components' names in order, separated by `, ` (never a deploy job: the deploy jobs are not part of the required check); `<results>` is `${{ needs.<name>.result }}` for each component in order, separated by one space:

   ```yaml

     ci:
       needs: [changes, <names>]
       if: always()
       runs-on: ubuntu-latest
       steps:
         - name: The change detection passed, and every component job passed or was skipped
           env:
             CHANGES: ${{ needs.changes.result }}
             RESULTS: <results>
           run: |
             if [ "$CHANGES" != "success" ]; then echo "the job changes ended: $CHANGES"; exit 1; fi
             for r in $RESULTS; do
               case "$r" in success|skipped) ;; *) echo "a component job ended: $r"; exit 1 ;; esac
             done
   ```

   The job `ci` needs `changes` and requires it to have succeeded: if the change detection failed, every component job would be skipped, and skipped must not read as passed.

   For `components=web:web:go:1.27,api:services/api:go:1.27 workflows=example-org/tooling`, `<sha>` `2222222222222222222222222222222222222222` and `defaultBranch` `main`, the whole file is:

   ```yaml
   # aleogr-ci 1 api:services/api:go:1.27,web:web:go:1.27
   # Generated by aleogr from .aleogr/project.json. Do not edit: change the declaration and run project-apply.
   name: ci

   on:
     pull_request:
     push:
       branches: [main]

   permissions:
     contents: read

   jobs:
     changes:
       runs-on: ubuntu-latest
       permissions:
         contents: read
         pull-requests: read
       outputs:
         api: ${{ steps.filter.outputs.api }}
         web: ${{ steps.filter.outputs.web }}
       steps:
         - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
         - id: filter
           uses: dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d # v4.0.3
           with:
             filters: |
               api:
                 - 'services/api/**'
                 - '.github/workflows/ci.yml'
               web:
                 - 'web/**'
                 - '.github/workflows/ci.yml'

     api:
       needs: changes
       if: needs.changes.outputs.api == 'true'
       uses: example-org/tooling/.github/workflows/ci-go.yml@2222222222222222222222222222222222222222
       with:
         working-directory: "services/api"
         go-version: "1.27"

     web:
       needs: changes
       if: needs.changes.outputs.web == 'true'
       uses: example-org/tooling/.github/workflows/ci-go.yml@2222222222222222222222222222222222222222
       with:
         working-directory: "web"
         go-version: "1.27"

     ci:
       needs: [changes, api, web]
       if: always()
       runs-on: ubuntu-latest
       steps:
         - name: The change detection passed, and every component job passed or was skipped
           env:
             CHANGES: ${{ needs.changes.result }}
             RESULTS: ${{ needs.api.result }} ${{ needs.web.result }}
           run: |
             if [ "$CHANGES" != "success" ]; then echo "the job changes ended: $CHANGES"; exit 1; fi
             for r in $RESULTS; do
               case "$r" in success|skipped) ;; *) echo "a component job ended: $r"; exit 1 ;; esac
             done
   ```

   With `deploy=dev deployComponents=web,api project=demo region=us-central1` and the same arguments otherwise, the first line is `# aleogr-ci 2 api:services/api:go:1.27,web:web:go:1.27 deploy=dev:api+web project=demo branch=main region=us-central1`, and the job `api` is followed by:

   ```yaml

     deploy-api-dev:
       needs: [api]
       if: github.event_name == 'push' && github.ref == 'refs/heads/main' && needs.api.result == 'success'
       permissions:
         contents: read
         id-token: write
       uses: example-org/tooling/.github/workflows/deploy-cloud-run.yml@2222222222222222222222222222222222222222
       with:
         working-directory: "services/api"
         service: "demo-api"
         image-name: "api"
         region: "us-central1"
       secrets:
         project-id: ${{ secrets.GCP_PROJECT_ID }}
         workload-identity-provider: ${{ secrets.GCP_WIF_PROVIDER }}
         service-account: ${{ secrets.GCP_CI_ACCOUNT }}
         image-path: ${{ secrets.GCP_IMAGE_PATH }}
   ```

   and the job `web` by `deploy-web-dev`, built the same way; the rest of the file (the job `ci` included) is the same as above. With `deployComponents=api`, only `deploy-api-dev` is written and the job `web` is followed directly by the job `ci`.

   The Write tool refuses: `failed`; say so in one sentence. Written: `status` `created` when `local` was `missing`, `updated` when it was `differs`. Go to step 6.

6. Verify, once: read `.github/workflows/ci.yml` again with the Read tool. Its first line is the marker: nothing is left. Otherwise, or the read fails: the status stays; say so in one sentence and add the item `verify`.

Then answer in a few lines: the state of the file in this folder and in the repository, the commit pinned (or that `apply` would pin), what was written (or would be), that nothing was committed or pushed and the file goes to the repository with the pull request, anything left in `pending`, and the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "ci-setup",
  "mode": "apply",
  "status": "created",
  "resources": [],
  "outputs": {
    "path": ".github/workflows/ci.yml",
    "local": "missing",
    "inRepository": false,
    "repositoryAsDeclared": null,
    "marker": "# aleogr-ci 1 api:services/api:go:1.27,web:web:go:1.27",
    "ref": "2222222222222222222222222222222222222222",
    "written": true,
    "checks": ["ci"],
    "deploy": [],
    "deployComponents": []
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-create`: `plan`, `local` `missing`, with components.
  - `would-update`: `plan`, `local` `differs`, with components.
  - `created`: `apply`, the file was missing and step 5 wrote it in this run.
  - `updated`: `apply`, the file differed and step 5 rewrote it in this run.
  - `unchanged`: `local` `as-declared` or `not-needed` (`plan` or `apply`); nothing was written.
  - `pending`: nothing was written and the rest is the owner's to do: no component but a local `ci.yml` (`plan` or `apply`).
  - `failed`: an argument missing or broke a rule, `gh` missing, `gh` not logged in, the read of step 2 refused, the read of step 4 refused, or the write of step 5 refused. Nothing was written.
- `pending` items are `{ "item": "<what>", "reason": "manual", "how": "<text>" }`:
  - No component and a local file: exactly one item `{ "item": "ci.yml is not needed", "reason": "manual", "how": "remove .github/workflows/ci.yml by hand and propose the removal with a pull request" }`.
  - `created` or `updated` with a verification (step 6) that failed: one item `{ "item": "verify", "reason": "manual", "how": "/aleogr-repo-github:github_ci-setup owner=<owner> name=<name> components=<components> workflows=<workflows> mode=plan" }`, with the arguments as given (plus `deploy=<deploy> deployComponents=<deployComponents> project=<project> region=<region>` when `deploy` was given). `created` or `updated` with a non-empty `pending` is allowed.
  - Every other ending: `[]`.
- `outputs` has the same ten keys in every ending:
  - `path`: always `.github/workflows/ci.yml`.
  - `local`: `as-declared`, `missing`, `differs` or `not-needed`, as decided by step 3; `null` when the run ended before step 3 (an argument, `gh`, the read of step 2).
  - `inRepository`: `true` or `false` as read by step 2; `null` when step 2 did not succeed or did not run.
  - `repositoryAsDeclared`: `true` or `false` as decided by step 2 when `inRepository` is `true`; `null` otherwise.
  - `marker`: the marker of the components; `null` when there is no component or an argument broke a rule.
  - `ref`: the commit `<sha>` written in the file by this run; `null` when nothing was written.
  - `written`: `true` only when step 5 wrote the file in this run; `false` otherwise.
  - `checks`: `["ci"]` when the arguments are valid and `components` is not empty; `[]` otherwise. The deploy jobs are never in it.
  - `deploy`: the environments of `deploy`, on one line (`["dev"]`), when the arguments are valid and `components` is not empty; `[]` otherwise.
  - `deployComponents`: the names of `deployComponents` sorted by name, on one line (`["api", "web"]`), when the arguments are valid, `components` is not empty and `deploy` is given; `[]` otherwise.
- `resources` is always `[]`.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`.
