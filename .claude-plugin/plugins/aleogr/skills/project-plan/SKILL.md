---
description: aleogr project plan. Use in a project's folder to see what the project's GitHub repository is missing or has different from the declaration `.aleogr/project.json` (the repository, its settings and topics, its visibility, the declaration in the repository, the branch protection, when components are declared, their Go starting points and the CI file, and, when environments are declared, the GCP environment dev: its project, its APIs, the image repository and the CI identity, and, with components, the login of the organization, the Cloud Run services and the repository's CI secrets). Prints a table of items, state and action. Read-only; changes nothing.
---

# project-plan

Compares the project's declaration, `.aleogr/project.json` in the folder the skill runs in, with the real GitHub repository and prints a table: item, state, action. The plan only reads: it runs no `gh`, `git` or `gcloud` command itself, it invokes `aleogr:tools-check`, the read-only skills of `aleogr-repo-github` and, when components are declared, `github_ci-setup` and `aleogr-stack-go:go_setup` in `mode=plan`, and, when environments are declared, `aleogr:tools-check` for `gcloud`, `aleogr-cloud-gcp:gcp_environment-describe`, `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe` and `aleogr-cloud-gcp:gcp_ci-identity-setup` in `mode=plan`, and, when both are declared, `aleogr-cloud-gcp:gcp_login-describe`, `aleogr-cloud-gcp:gcp_deploy-describe` and `aleogr-repo-github:github_variables-set` with `kind=secrets` in `mode=plan`, and running it changes nothing anywhere. `project-apply` runs it first and acts on its items.

## Arguments

Free text after the skill name, as `key=value` pairs. Everything else comes from the declaration, and any other text is ignored.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Optional. The GCP project id of `dev`, when the caller already knows it (`project-apply` passes it after it created or found the project in its run): step 9 reads that project by its id instead of searching by labels, which can lag behind a creation. |

Before invoking anything, check it: `projectId`, when given, has 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. Otherwise end with `status` `failed`, one sentence saying which rule failed (item `arguments`), and invoke nothing. A `projectId` given for a declaration without `environments` is not used.

## The declaration's rules

The declaration of a project is the file `.aleogr/project.json` in the project's folder. It is a JSON object, version 1, described by the schema `https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json`. A file is a valid declaration only when it is valid JSON and every rule below holds; a file that breaks any of them is not a valid declaration.

- No object in the file has a key other than the ones listed here (no unknown keys, at any level).
- The top level has `version`, `name` and `repo` (required), and may have `$schema`, `components`, `cloud`, `environments` and `notes`.
- `$schema`, when present, is a string.
- `version` is the number `1`.
- `name`, the project name, is a string of 1 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. It is not `test`, not `shared` and does not start with `test-` (those names are reserved for tests and for the shared platform).
- `repo` is an object with `provider`, `owner`, `name`, `visibility`, `description` and `settings` (all required), and may have `topics`.
- `repo.provider` is `github`, the only provider implemented.
- `repo.owner`, the user or organization that owns the repository, is a string of 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `repo.name`, the repository name, is a string of 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `repo.visibility` is `public` or `private`.
- `repo.description` is a string of 1 to 350 characters with no line break and none of these characters: `"`, backtick, `$`, `\`, `“`, `”`, `„`.
- `repo.topics`, when present, is a list of strings without repeated items; when absent it means the empty list. Each topic has 1 to 50 characters of `a-z`, `0-9` and `-`, and starts with a letter or a digit. The list holds only extra topics: it never contains `aleogr-<name>` (with the project's `name`), because that topic is derived, not typed. The topics sent to GitHub are `aleogr-<name>` plus `repo.topics`, sorted, without duplicates.
- `repo.settings` is an object with exactly these seven keys, all required, each a JSON boolean (`true` or `false`, never a string): `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`. At least one of `mergeCommit`, `squash` and `rebase` is `true`.
- `components`, when present, is a list (possibly empty) of the project's components; when absent it means the empty list. Each component is an object with exactly these four keys, all required:
  - `name`: a string of 1 to 20 characters of `a-z`, `0-9` and `-`, starting with a letter. It is not `changes` or `ci` (the names of jobs of the project's CI file, where each component is a job named after it), and not `true`, `false`, `null`, `yes`, `no`, `on` or `off` (YAML does not read those as names). No two components have the same `name`.
  - `stack`: `go`, the only stack implemented.
  - `path`: the component's folder, a string relative to the repository's root, made of one or more parts separated by `/` (so it does not start or end with `/` and has no empty part). Each part uses only `a-z`, `0-9`, `-`, `_` and `.`; it is not `.` or `..`, does not start with `-` or `.`, and does not end with `.` (so `.github`, `.aleogr` and every folder under them are never a component's folder). No two components have the same `path`, and no component's `path` is inside another component's `path` (`web` and `web/api` cannot both be components): one module per component folder.
  - `version`: the language version, `major.minor`: digits, a dot, digits (`1.27`; never `1.27.4`). With the stack `go` it is `1.22` or later, comparing the major and then the minor as numbers (`1.22`, `1.27` and `2.0` are accepted; `1.21` and `1.9` are not): the Go starting point's routes need Go 1.22.
- `cloud`, when present, says where the project's environments run. It is an object with `provider` and `region` (both required), and may have `root`:
  - `provider`: `gcp`, the only cloud implemented.
  - `region`: a GCP region name: lowercase letters, `-`, lowercase letters, then one or more digits (`us-central1`).
  - `root`: `tst`, its only value: the project tests the tooling, and its cloud projects are created inside the folder `tst`. A real project has no `root`.
  - `cloud` without `environments` is valid and asks for nothing in the cloud.
- `environments`, when present, is an object with at least one key. Its only allowed key is `dev`, and the value of `dev` is an empty object, `{}` (no key inside). Other environments, such as `hom` and `prd`, are not built yet and are not allowed. A declaration with `environments` has `cloud`, and its `name` has at least three characters (the CI identity's service account id is `<name>-ci`, and a service account id has at least six).
  With `environments`, each component runs as a service named `<name>-<component name>`, which is also its account's id: no component's `name` ends with `-`, and `<name>-<component name>` has 6 to 30 characters (`demo-web` has 8).
- `notes`, when present, is a string of free text.

The canonical form of the file, the form in which it is written:

- Two-space indentation, one key per line, and a final newline.
- Keys in this order: `$schema`, `version`, `name`, `repo`, `components`, `cloud`, `environments`, `notes`; inside `repo`: `provider`, `owner`, `name`, `visibility`, `description`, `topics`, `settings`; inside `settings`: `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`; inside each component: `name`, `stack`, `path`, `version`; inside `cloud`: `provider`, `region`, `root`.
- `$schema` is always present, with the value `https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json`.
- `repo.topics` is always present, on one line, sorted: `"topics": []` or `"topics": ["docs", "sample"]`.
- `components` is present only when it has at least one component. The components are sorted by `name`, each on one line: `{ "name": "web", "stack": "go", "path": "web", "version": "1.27" }`.
- `cloud`, when present, is on one line: `"cloud": { "provider": "gcp", "region": "us-central1" }`, or with `root`, `"cloud": { "provider": "gcp", "region": "us-central1", "root": "tst" }`.
- `environments`, when present, is on one line: `"environments": { "dev": {} }`.
- `notes` is present only when it has a value.

For example, a canonical declaration:

```json
{
  "$schema": "https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json",
  "version": 1,
  "name": "demo",
  "repo": {
    "provider": "github",
    "owner": "example-org",
    "name": "demo",
    "visibility": "private",
    "description": "Demo project",
    "topics": ["sample"],
    "settings": {
      "mergeCommit": true,
      "squash": true,
      "rebase": false,
      "deleteBranchOnMerge": true,
      "issues": true,
      "wiki": false,
      "projects": false
    }
  }
}
```

The same declaration with two components ends like this:

```json
    }
  },
  "components": [
    { "name": "api", "stack": "go", "path": "services/api", "version": "1.27" },
    { "name": "web", "stack": "go", "path": "web", "version": "1.27" }
  ]
}
```

With the environment `dev` and the root `tst` as well, it ends like this:

```json
    { "name": "web", "stack": "go", "path": "web", "version": "1.27" }
  ],
  "cloud": { "provider": "gcp", "region": "us-central1", "root": "tst" },
  "environments": { "dev": {} }
}
```

Two declarations are equal when they hold the same values: the order of keys, the spacing, line endings and the order of `repo.topics` and the order of `components` do not matter, an absent `repo.topics` equals `[]` and an absent `components` equals `[]`.

## Steps

Show each skill invocation before making it. The skills below end with their own `aleogr-result` block: use those blocks only as input, never repeat them, and after each one go on with the next step: a skill's block is never the end of this answer, which always ends with the table and this skill's own block. Invoke only these skills, in this order, each at most once (`tools-check` once for `gh` and, with environments, once more for `gcloud` right after it, before any GitHub read; `go_setup` once per component; `github_repo-describe` a second time only in step 16), and run no command yourself (no `gh`, no `git`, no `gcloud`, no `ls`, no `cat`). Your answer ends with exactly one block, its own. Never print the signed-in login (the account `gh` or `gcloud` is signed in with): not in the answer and not in the result block. This does not cover the CI account `<name>-ci@…` of `ciVariables`, which is an identifier of the project, not a login.

A declaration without components (`components` absent or `[]`) skips steps 3, 8, 15 and 16, invokes step 4 without `checks`, step 5 without `head` and step 6 with `paths=.aleogr/project.json`, and has the five items of "Items"; a `ci.yml` left in the repository after the last component is removed is not reported by this skill (removing a component is not built yet). Only a declaration with at least one component invokes `github_ci-setup` and `go_setup` and has seven items.

A declaration without `environments` skips the `gcloud` check of step 2 and steps 9 to 14, and has exactly the items above: for it this skill invokes no cloud skill, and not one `gcloud` command is run. Only a declaration with `environments` (its only environment is `dev`) has, after `protection`, the items of "The environment's items": four without components (nine items in all), six with components (thirteen in all). Only a declaration with both components and `environments` runs steps 12 to 14.

1. Read `.aleogr/project.json` in the current folder with the Read tool.
   - It does not exist: `failed`, with the sentence `There is no .aleogr/project.json in this folder: declare the project first with /aleogr:project-declare.` Invoke nothing.
   - It is not valid JSON, or breaks a rule of "The declaration's rules" (the canonical form is not a rule: a valid file in another layout is accepted): `failed`, one sentence naming the first problem found (for example, that it is not valid JSON, or the unknown key and where it is). Invoke nothing.
   - Otherwise take `name`, `repo.owner`, `repo.name`, `repo.visibility`, `repo.description`, `repo.topics` (absent means `[]`), `repo.settings` and `components` (absent means `[]`). The declared topics are `aleogr-<name>` plus `repo.topics`, without duplicates.
   - With at least one component, also read `${CLAUDE_PLUGIN_ROOT}/defaults.json` with the Read tool and take `ci.workflowsRepository`. It cannot be read, or has no such string: `failed`, one sentence saying so. Invoke nothing. Then, with the components sorted by `name`:
     - `<components>` is the entries `<name>:<path>:<stack>:<version>` of the components, joined by `,` (for the two components of the example, `api:services/api:go:1.27,web:web:go:1.27`).
     - The module of a component is `github.com/<repo.owner>/<repo.name>/<path>`.
     - The tooling paths are `.aleogr/project.json`, `.github/workflows/ci.yml` and, for each component, `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, followed, with `environments`, by `<path>/Dockerfile`, in that order, joined by `,`.
   - With `environments`, also take `cloud.region`, and read `${CLAUDE_PLUGIN_ROOT}/defaults.json` with the Read tool (the same read as for components, made once) and take `project.services` (a list of API names), `project.registry.keep` (a number), `ci.workflowsRepository` and `ci.deployWorkflow` (a file name such as `deploy-cloud-run.yml`; the CI identity's `workflow=` is built from both, with or without components), and, with at least one component, `project.deploy.maxInstances`, `project.deploy.cpu` and `project.deploy.memory`. It cannot be read, or lacks any of them: `failed`, one sentence saying so. Invoke nothing. These values are passed as the skills' arguments below, as read: none is written into this skill.
2. Invoke `aleogr:tools-check command=gh`. Its `status` `failed`: stop with `failed`, carry its `fix` into `pending[].how`, and invoke nothing else.
   - With `environments`, and only then: right after it, before step 4 and before anything on GitHub is read, invoke `aleogr:tools-check` with no argument (it checks `gcloud`). Its block is input only: go on. Its `status` `failed` (`gcloud` missing or not signed in): stop with `failed`, carry its `fix` into `pending[].how`, and invoke nothing else: no row is read. Only then go to step 3 (or, without components, step 4).
3. Only with at least one component: read the local `.github/workflows/ci.yml` with the Read tool, only to learn whether it exists and to keep its first line (no skill is invoked here). `github_ci-setup` is invoked once, in step 15, after everything it depends on: the repository's default branch (step 4) and, with `environments`, the services (step 13).
4. Invoke `aleogr-repo-github:github_repo-describe owner=<repo.owner> name=<repo.name>`, with `checks=ci` added exactly when step 3 found the local `ci.yml` (the protection is expected to require the check `ci` while `ci.yml` is on the default branch; step 16 reads the protection again when step 15 finds that it is not); otherwise with no `checks` argument.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else.
   - `outputs.exists` false: the repository is to create. Invoke nothing else: every other item follows the creation (see "Items"). Go to the answer.
   - `outputs.exists` true: take `visibility`, `description`, `topics`, `settings`, `protection.state`, `protection.matches` and `defaultBranch`, and, with `environments`, `id` and `ownerId`. Go to step 5.
5. Invoke `aleogr-repo-github:github_checkout-setup owner=<repo.owner> name=<repo.name> mode=plan`, with `head=check` added exactly when the declaration has at least one component. It reads the repository's copy of `.aleogr/project.json`, compares it with the local one and, when they differ, reads the folder. With `head=check` it also reads the folder when they are equal, and reports `behind` when the repository's head moved on from this folder's last commit: a merged pull request that added code or `ci.yml` without changing the declaration leaves this folder behind all the same.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else.
   - Otherwise take `outputs.state` (`equal`, `not-sent`, `differs`, `missing`, `behind` or `needs-attention`), `outputs.reason` and its `pending` items. Also note the environments of the repository's copy of the declaration (the output `repositoryEnvironments`), from what this step already read, with no other read: state `equal`, the names of the folder's `environments` (the two are equal); state `not-sent` or `missing` (the repository has no declaration), `[]`; any other state, the keys of `environments` of the repository's copy that this step read and showed (`gh api repos/<owner>/<name>/contents/.aleogr/project.json`), `[]` when that copy has no `environments`, and `null` when the copy could not be read as JSON. Go to step 6.
6. Invoke `aleogr-repo-github:github_pull-request-open owner=<repo.owner> name=<repo.name> paths=<paths> mode=plan`, where `<paths>` is `.aleogr/project.json` without components and the tooling paths with components. It reports the open tooling pull request, if any, whether the folder is fit for a proposal and which of the paths changed.
   - `status` `failed`: stop with `failed` and its cause.
   - Otherwise (any other status: `pending`, `would-create` or `unchanged` are all input here) take `outputs.openPullRequest` (`null`, or its `number` and `url`), `outputs.folder` (`ready`, `not-a-checkout`, `other-remote`, `other-branch` or `local-commits`), `outputs.changed` and its `pending` items. Go to step 7.
7. Decide the `declaration` item now, by the list under "Items". Without components: with `environments` and the action `none`, go to step 9; otherwise go to the answer. With components: its action `merge it`, `update` or `fix the folder`: invoke nothing else (the rows `components`, `ci` and `protection` are not checked, nor the environment's) and go to the answer; its action `send` (the birth): invoke nothing else (`components` and `ci` wait for the declaration to be sent; `protection` is judged from step 4) and go to the answer; its action `propose` or `none`: go to step 8. When this step goes to the answer, the last invocation is over. Now write this skill's answer, and nothing before it: not the lines or the block of `github_pull-request-open`, of `github_checkout-setup` or of a `go_setup`. Start with the table's header row (on `failed`, with the sentence of the failure), and end with this skill's block.
8. For each component, sorted by `name`, invoke `aleogr-stack-go:go_setup component=<name> path=<path> version=<version> module=<module> mode=plan`, with `dockerfile=yes` added exactly when the declaration has `environments` (a component whose module exists but whose `Dockerfile` is missing is then `would-create` too). In `plan` it writes nothing; it reads the component's folder.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else.
   - Otherwise (any other status: `unchanged`, `would-create` or `pending` are all input here) take its `status` and its `pending` items, and go on with the next component. After the last one: with `environments` and the `declaration` action `none`, go to step 9; otherwise go to step 15. Write nothing before it: not the lines or the block of `github_pull-request-open`, of `github_checkout-setup` or of a `go_setup`.

Steps 9 to 11 run only with `environments`, and only when the `declaration` action is `none` (the declaration in the repository is this one). Steps 12 to 14 run after them, only when the declaration also has at least one component.

Write nothing between the invocations of steps 8 to 16 and the table: no summary of a skill's run, no copy of its block. Every ending of steps 9 to 14 that is not `failed` goes on, with components, to step 15: the plan never ends before `github_ci-setup` when it has components and the `declaration` action is `propose` or `none`.

9. Invoke `aleogr-cloud-gcp:gcp_environment-describe projectId=<projectId>` when the argument `projectId` was given, otherwise `aleogr-cloud-gcp:gcp_environment-describe project=<name> environment=dev`. It only reads. Read its block, then take the case below that applies.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else. Go to the Answer: your next output is the sentence of the failure; write nothing before it.
   - `outputs.exists` false, or `outputs.billingLinked` false: nothing inside the GCP project is read. With components, go to step 15; without, go to the Answer: your next output is the table, starting with its header row; write nothing before it.
   - Otherwise take `projectId` and `enabledServices`. The APIs to enable are the names of `project.services` that are not in `enabledServices`. Some (no Artifact Registry or IAM read works before they are on): with components, go to step 15; without, go to the Answer: your next output is the table, starting with its header row; write nothing before it. None: write nothing and go straight to step 10.
10. Invoke `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe projectId=<projectId> project=<name> region=<cloud.region>`. It only reads. Read its block, then take the case below that applies.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else. Go to the Answer: your next output is the sentence of the failure; write nothing before it.
   - Otherwise take `exists`, `otherRegions`, `format`, `cleanup` (`keep`, `deletesTheRest`, `dryRun`, `rules`), `push` and `imagePath`. Write nothing and go straight to step 11.
11. Invoke `aleogr-cloud-gcp:gcp_ci-identity-setup projectId=<projectId> project=<name> repository=<repo.owner>/<repo.name> repositoryId=<id> ownerId=<ownerId> branch=<defaultBranch> workflow=<ci.workflowsRepository>/.github/workflows/<ci.deployWorkflow> mode=plan`, with `id`, `ownerId` and `defaultBranch` of step 4 (for the defaults of this plugin, `workflow=aleogr/aleogr/.github/workflows/deploy-cloud-run.yml`). In `plan` it only reads. Read its block, then take the case below that applies.
   - `status` `failed` with `outputs.account` `null` (it refused an argument, or could not read the GCP project): stop with `failed` and its cause. Invoke nothing else. Your next output is the sentence of the failure; write nothing before it.
   - `status` `failed` with `outputs.account` set (a pool or provider deleted or disabled, a pool that holds another provider, or a part it could not read): this is not a failure of the plan but something the owner fixes by hand. Keep its sentence (the cause and what the owner does) for the `ci identity` item, and `outputs.account`.
   - Otherwise (`would-create`, `would-update` or `unchanged` are all input here) take its `status`, `outputs.account` and `outputs.ciVariables`.

   Without components, this was the last invocation: your next output is the table, starting with its header row; write nothing before it (not the lines of `gcp_ci-identity-setup`, not its CI values, not its block). With components, write nothing and go straight to step 12.
12. Invoke `aleogr-cloud-gcp:gcp_login-describe projectId=<projectId>`. It only reads the organization's login setting, counted against the project of `dev`. Read its block, then take the case below that applies.
   - `outputs.prepared` true: write nothing and go straight to step 13.
   - `readable` false because the IAP API is off in the project the read is counted against (its sentence says so) while `iap.googleapis.com` is in the `enabledServices` of step 9: the API was enabled a moment ago and still refuses; the login is not known to be unprepared. Stop with `failed`, the sentence `The login of the organization could not be read yet: the IAP API of the GCP project of dev was just enabled; wait a minute, then run /aleogr:project-plan again.` and the item `services` (see "Result block"). Invoke nothing else. Your next output is that sentence; write nothing before it. (`project-apply` waits for this refusal by itself after it enabled the APIs.)
   - Any other ending (`prepared` false, `readable` false, or `status` `failed`): the login is not prepared, or could not be read. This is not a failure of the plan: a service is never created without the login, so the `services` row waits for it. Step 13 is not run (no service is read). Write nothing and go straight to step 14.
13. Invoke `aleogr-cloud-gcp:gcp_deploy-describe projectId=<projectId> project=<name> region=<cloud.region> components=<names> maxInstances=<project.deploy.maxInstances> cpu=<project.deploy.cpu> memory=<project.deploy.memory> ciAccount=<account> environment=dev`, where `<names>` are the components' names sorted by `name`, joined by `,`, and `<account>` is `outputs.account` of step 11. It only reads. Read its block, then take the case below that applies.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else. Your next output is the sentence of the failure; write nothing before it.
   - Otherwise take `outputs.services` (each component's `exists` and `url`), `outputs.missing`, `outputs.differing` and `outputs.waiting`. A service open to anyone (the difference `open`: its login policy lets in `allUsers` or `allAuthenticatedUsers`) is in `differing`. Write nothing and go straight to step 14.
14. Only when the `ci identity` row's action is `none`, step 11 gave `outputs.ciVariables` (not `null`) and step 10 gave an `imagePath` (not `null`): invoke `aleogr-repo-github:github_variables-set owner=<repo.owner> name=<repo.name> kind=secrets variables=GCP_PROJECT_ID=<projectId>,GCP_WIF_PROVIDER=<provider>,GCP_CI_ACCOUNT=<account>,GCP_IMAGE_PATH=<imagePath> mode=plan`, where `<projectId>`, `<provider>` and `<account>` are the values of `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER` and `GCP_CI_ACCOUNT` in `outputs.ciVariables` of step 11, and `<imagePath>` is `imagePath` of step 10: the four values come from reads this plan already made, and no other read is made for them. The four are the repository's Actions secrets that the deploy jobs read (there is no `GCP_REGION`: the region is written in the CI file). Otherwise invoke nothing here (the `ci secrets` row follows the row that has to change first). In `plan` it only reads the names of the repository's secrets: a secret's value cannot be read back, so the plan learns only which of the four exist. Read its block, then take the case below that applies.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else. Your next output is the sentence of the failure; write nothing before it.
   - Otherwise (`would-update` or `unchanged`) take its `status` and `outputs.set` (the names that do not exist).

   Write nothing and go straight to step 15.

Steps 15 and 16 run only with components.

15. Invoke `aleogr-repo-github:github_ci-setup owner=<repo.owner> name=<repo.name> components=<components> workflows=<ci.workflowsRepository> defaultBranch=<defaultBranch> mode=plan`, with `defaultBranch` of step 4, and, when **the deploy list** is not empty, with `deploy=dev deployComponents=<the deploy list, joined by ,> project=<name> region=<cloud.region>` added; when it is empty, without `deploy`, `deployComponents`, `project` and `region` (the version 1 file). The deploy list, the components that get a deploy job, is decided here and nowhere else, sorted by name:
   - The declaration has no `environments`: empty.
   - Step 13 ran in this plan (the services were read): the declared components whose service is not in its `outputs.missing`. A deploy job never runs for a service that does not exist; `project-apply` creates the missing services first and plans again, which then lists them.
   - Step 13 did not run (the declaration is being proposed, the environment or its APIs are not ready, the login could not be read or is not prepared): when the first line of the local `ci.yml` read in step 3 starts with `# aleogr-ci 2 `, the names after `deploy=dev:` in it (separated by `+`) that are still components of the declaration: deploy jobs that are there are kept, and a component added since gets none until its service exists. Otherwise (no local file, or a file of version 1): empty.

   So a deploy job never comes before its service. When `project-apply` creates the services and then proposes the files in the same run, that one proposal already carries their deploy jobs; a file proposed before the services exist (a declaration being proposed, an environment added later, the login not prepared) carries none for them, and their jobs come in the proposal made after the services exist. In `plan` it writes nothing; it reads the local `.github/workflows/ci.yml` and the repository's copy.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else. Your next output is the sentence of the failure; write nothing before it.
   - Otherwise (any other status: `would-create`, `would-update` or `unchanged` are all input here) take `outputs.local` (`as-declared`, `missing` or `differs`) and `outputs.inRepository` (`true` when `ci.yml` is on the repository's default branch). Read its block without writing it: no line of `github_ci-setup` and no copy of its block goes into this answer. Go to step 16.
16. The protection is expected to require the check `ci` exactly when step 15 ran and its `inRepository` is `true` (the output `checks` is then `ci`). Only when the `declaration` action is `none` (with `send`, the birth, the repository is unprotected or rulesets are not available, so the check `ci` does not change the row), and step 4 was invoked with `checks=ci` while that is not expected, or without it while it is: invoke `aleogr-repo-github:github_repo-describe owner=<repo.owner> name=<repo.name>` again, with `checks=ci` exactly when it is expected, and take `protection.state` and `protection.matches` from this read instead of step 4's (its other outputs are not used). `status` `failed`: stop with `failed` and its cause. Otherwise invoke nothing here. Say nothing about this step: it has no line in the answer.

   This was the last invocation. Your next output is the table, starting with its header row (on `failed`, the sentence of the failure); write nothing before it: not the lines of `github_ci-setup`, `github_repo-describe`, `gcp_ci-identity-setup`, `gcp_login-describe`, `gcp_deploy-describe` or `github_variables-set`, not the CI values, not a block of theirs. Start with the table's header row (on `failed`, with the sentence of the failure), and end with this skill's block.

## Items

Without components, always these five items, in this order: `repository`, `settings`, `visibility`, `declaration`, `protection`. With at least one component, always these seven, in this order: `repository`, `settings`, `visibility`, `declaration`, `components`, `ci`, `protection`. Each is `{ "item": "<item>", "state": "<state>", "action": "<action>" }`, with the state and action texts exactly as written here.

| Item | State → action |
|---|---|
| `repository` | `exists` false: `missing` → `create`. `exists` true: `exists` → `none`. |
| `settings` | Compare `repo.description` with `outputs.description`, the declared topics with `outputs.topics` as sets (order ignored), and each of the seven `repo.settings` with the same key of `outputs.settings`. All equal: `as declared` → `none`. Otherwise `differs: <names>` → `update`, where `<names>` are the names that differ, comma-separated, in this order: `description`, `topics`, `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects` (for example `differs: topics, rebase`). |
| `visibility` | `outputs.visibility` equals `repo.visibility`: `as declared` → `none`. Otherwise (including `internal`): `differs` → `update`, and the note `visibility: needs confirmVisibility=<repo.visibility>` under the table. |
| `declaration` | From the checkout's `outputs.state` and the pull request skill's `outputs.openPullRequest`, `outputs.folder` and `outputs.changed`: the first case of the list under the table that applies. |
| `components` | Only with components, from the `status` of each `go_setup` of step 8. Some `pending`: `needs attention: <names>` → `fix the folder`, with their `pending` items. Otherwise some `would-create` (no `go.mod` in the component's folder, or, with `environments`, no `Dockerfile` in it): `to generate: <names>` → `generate`. Otherwise (every one `unchanged`): `as declared` → `none`. `<names>` are the names of the components with that status, sorted, separated by `, ` (for example `to generate: api, web`). |
| `ci` | Only with components, from `outputs.local` of step 15: `as-declared` → `as declared` / `none`; `missing` → `missing` / `generate`; `differs` → `differs` / `generate`. |
| `protection` | From `protection.state`: `protected` with `matches` true → `protected` / `none`, or `protected, requires ci` / `none` when the check `ci` is expected (step 16); `protected` with `matches` false → `differs` / `update`; `unprotected` → `unprotected` / `create`; `unavailable` → `not available on this plan` / `none`, and the notice `main is held by the working rule, not by GitHub` under the table (when `visibility` is `differs` and `repo.visibility` is `public`, the notice adds `protection is checked again once the repository is public`). With the check `ci` expected (`ci.yml` is on the default branch) the ruleset is expected to require the check `ci`, so one without it `differs`; without `checks`, one that requires it `differs` too. |

The `declaration` item: take the first case that applies, in this order. "Protected" means `protection.state` is `protected` (matching or not), where the protection refuses a push to the default branch. "Generated files changed" means `changed` holds a path other than `.aleogr/project.json`: a generated file this folder has and the repository does not (without components, `paths` is the declaration alone, so this never holds).

1. `openPullRequest` is not `null`: `proposed in pull request #<n>` / `merge it`, with its `number`, whatever the checkout found.
2. Checkout `equal`, and no generated files changed: `in the repository` / `none`.
3. Checkout `not-sent`, the repository not protected: `not sent yet` / `send` (the birth), whatever `folder` is.
4. Checkout `behind`: `this folder is behind` / `update`.
5. Checkout `needs-attention`; or checkout `differs`, `missing`, or `not-sent` with the repository protected, while `folder` is not `ready`: `this folder needs attention` / `fix the folder`.
6. Checkout `differs`; or checkout `equal` with generated files changed (the folder is then `ready`): `changed here` / `propose`.
7. Checkout `missing`, or `not-sent` with the repository protected: `not in the repository` / `propose`.

These cases replace the rows above:

- **Repository missing** (step 4, `exists` false): `repository` is `missing` / `create`, and the other items have the state `follows the creation` with the action they will have: `settings` → `update`, `visibility` → `none` (the repository is created with the declared visibility), `declaration` → `send`, `protection` → `create`, and, with components, `components` → `none` and `ci` → `none` (they are generated by a later run, once the declaration is in the repository).
- **Declaration being changed** (`declaration` action `merge it`, `update`, `fix the folder` or `propose`): the repository's declaration is the one that holds until the change is merged and the folder is up to date, so nothing on GitHub is compared with the local file: `settings`, `visibility` and `protection` are `not checked until the change is merged` / `none`, and `exposes` is `false`. `repository` and `declaration` are as above.
- **Code not checked** (with components, `declaration` action `merge it`, `update` or `fix the folder`): `components` and `ci` are `not checked until the change is merged` / `none`, and step 8 is not run. With the action `send` (the birth): `components` and `ci` are `not checked until the declaration is sent` / `none`, and step 8 is not run.

With the `declaration` action `propose` or `none`, `components` and `ci` are computed from the local declaration and this folder, as the table says: writing files in the folder and proposing them changes nothing on GitHub, so they do not wait for a merge. `settings`, `visibility` and `protection` do wait for it: with the `declaration` action `propose` (as with `merge it`, `update` and `fix the folder`, and never with `send` or `none`) they are `not checked until the change is merged` / `none`, whatever the repository's state, by the case "Declaration being changed" above.

`merge it` and `fix the folder` are the owner's to do: `project-apply` stops on them.

## The environment's items

Only with `environments`: four more items after `protection`, in this order: `environment dev`, `apis`, `registry`, `ci identity`, and, only when the declaration also has at least one component, two more after them: `services`, then `ci secrets`. Each is `{ "item": "<item>", "state": "<state>", "action": "<action>" }` with the texts exactly as written here.

| Item | State → action |
|---|---|
| `environment dev` | From step 9: `exists` false: `missing` → `create`. `exists` true and `billingLinked` false: `billing not linked` → `repair`. Otherwise `exists` → `none`. |
| `apis` | From the APIs to enable of step 9: none: `enabled` → `none`; otherwise `to enable: <n>` → `enable`, where `<n>` is how many (for example `to enable: 1`). |
| `registry` | From step 10: `exists` false and `otherRegions` empty: `missing` → `create`. `exists` false and `otherRegions` not empty (the repository exists only in another region): `in another region` → `fix by hand`. `exists` true and `format` is not `DOCKER` (a repository of another format holds no images, and a format never changes): `not a Docker repository` → `fix by hand`, whatever its cleanup. `exists` true and `cleanup.keep` is not `project.registry.keep`, or `cleanup.deletesTheRest` is false, or `cleanup.dryRun` is true, or `cleanup.rules` is not `2` (the policy holds a rule the tooling does not own, such as a third rule added by hand): `cleanup differs` → `configure`. Otherwise `as declared` → `none`. |
| `ci identity` | From step 11, and the `registry` item. `failed` with an `account` (step 11 says when): `needs attention` → `fix by hand`. Otherwise, by `registry`: **`as declared` or `cleanup differs`** (the repository is in the declared region): `would-create`: `missing` → `create`; `would-update`: `differs` → `update`; with either, `project-apply` also grants the account push after creating or updating it, when `push` does not hold `serviceAccount:<account>` (a new account is never in it). `unchanged`: `push` holds `serviceAccount:<account>`: `as declared` → `none`; otherwise `cannot push` → `grant` (this skill decides it). **`missing`**: `would-create`: `missing` → `create`; `would-update`: `differs` → `update`; with either, `project-apply` also grants the account push once the repository exists. `unchanged`: `cannot push` → `grant`. **`in another region`** or **`not a Docker repository`**: the identity's own state, and no grant (the `registry` row carries the block): `would-create`: `missing` → `create`; `would-update`: `differs` → `update`; `unchanged`: `as declared` → `none`. |
| `services` | From steps 12 and 13. The login not prepared, or not readable (step 12, any ending but `prepared` true): `waits for the login` → `prepare the login` (step 13 did not run). Otherwise, from `outputs` of step 13, the first that applies: `missing` not empty: `missing: <names>` → `create`; `differing` not empty (a service open to anyone included): `differs: <names>` → `update`; `waiting` not empty: `waiting for the first deploy: <names>` → `none` (each service is as declared and still runs the placeholder image, until the first deploy of CI replaces it); otherwise `as declared` → `none`. `<names>` are the components of that list, sorted, separated by `, ` (for example `missing: api, web`). |
| `ci secrets` | From step 14, when it ran: `unchanged` (the four secrets exist): `as declared` → `none`; `would-update`: `missing: <names>` → `set`, where `<names>` are its `outputs.set` (the secrets that do not exist), separated by `, ` (for example `missing: GCP_IMAGE_PATH`). An existing secret is `as declared` whatever it holds (`project-apply` sets the four again when it changed what they name); this is said in no line of the answer unless the row has the action `set` (below). When step 14 did not run: the `ci identity` row has an action other than `none`: `follows the ci identity` → `none` (its values are known once the identity is as declared); otherwise (the `registry` row is `fix by hand`, so the image path is not known): `follows the registry` → `none`. |

These cases replace the rows above, the first that applies:

- **Repository missing** (step 4, `exists` false): the four items, and `services` and `ci secrets` with components, are `follows the creation` / `none`.
- **Declaration not in the repository yet** (`declaration` action other than `none`): the four items, and `services` and `ci secrets` with components, are `not checked until the change is merged` / `none`, and steps 9 to 14 are not run.
- **Environment not ready** (`environment dev` is `missing` or `billing not linked`): `apis`, `registry` and `ci identity`, and `services` and `ci secrets` with components, are `follows the environment` / `none`: nothing can be read inside a project that does not exist or has no billing.
- **APIs to enable** (`apis` is `to enable: <n>`): `registry` and `ci identity`, and `services` and `ci secrets` with components, are `follows the apis` / `none`: their reads are refused until the APIs are on.

`fix by hand` and `prepare the login` are the owner's to do as well: `project-apply` never makes them, and they are never `nothing to do`. `prepare the login` is done on the platform (`/aleogr:platform-plan` shows what it makes and what it costs); `project-apply` makes the other actions of the plan meanwhile and creates no service.

## Answer

Whichever step led here, the last skill invoked is over: your next output is this skill's answer, with nothing before it, not that skill's lines, table or block.

Print the table (item, state, action). Under the table, these lines when they apply, worded as here:

- `visibility` has action `update`: `visibility: needs confirmVisibility=<repo.visibility>`.
- `exposes` is true: `This plan makes the repository public: project-apply runs it only with confirmVisibility=public.`
- `protection` is `not available on this plan`: `main is held by the working rule, not by GitHub.` When `visibility` is `differs` and `repo.visibility` is `public`, the line is `main is held by the working rule, not by GitHub; protection is checked again once the repository is public.`
- `declaration` has action `merge it` or `fix the folder`: the `how` of the `pending` item (below), and that `project-apply` stops until it is done.
- `components` has action `fix the folder`: the `how` of each of its `pending` items, and that `project-apply` stops until it is done.
- `components` or `ci` has action `generate`: that `project-apply` writes the files in this folder and proposes them, with the declaration, in one pull request.
- `ci` has action `generate`, with `environments`: `ci.yml is generated with the deploy jobs of dev for <names>.` (the deploy list of step 15, joined by `, `), or `ci.yml is generated without deploy jobs.` when that list is empty; then, when a declared component is not in the list, `The deploy job of <names> comes once its service exists.` (those components, joined by `, `).
- `registry` or `ci identity` has action `fix by hand`: the `how` of its `pending` item, and that the owner does it by hand: `project-apply` does not.
- `services` has action `prepare the login`: `The services wait for the login of the organization: /aleogr:platform-plan shows what preparing it makes and what it costs. project-apply creates no service until it is prepared.` Name no other command for it.
- `services` is `waiting for the first deploy: <names>`: `The services of <names> still run the placeholder image until CI deploys them: merge the pull request that carries the deploy jobs, or, once it is merged, merge a change to the component (re-running an older run deploys nothing new).` (with the names of the row).
- `ci secrets` has the action `set`: `The CI secrets are compared by name only: a secret's value cannot be read back.` With any other action (`none` included) no line about the secrets is written: not that they exist, not that they are compared by name.

No other line goes under the table than these and the line below.

The words `requires ci` appear only as the `protection` state `protected, requires ci`, never elsewhere in the answer.

Then one line: `nothing to do` when every action is `none`. Otherwise how many items have an action other than `none` and that `project-apply` makes them (for `merge it`, `fix the folder`, `fix by hand` or `prepare the login`, that it is the owner's to do). Never write the words `nothing to do` when an action is not `none`. On `failed`: the sentence of the failed step instead of the table. Then the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-plan",
  "mode": "plan",
  "status": "would-create",
  "resources": [],
  "outputs": {
    "project": "demo",
    "repository": "example-org/demo",
    "visibility": "private",
    "exposes": false,
    "items": [
      { "item": "repository", "state": "missing", "action": "create" },
      { "item": "settings", "state": "follows the creation", "action": "update" },
      { "item": "visibility", "state": "follows the creation", "action": "none" },
      { "item": "declaration", "state": "follows the creation", "action": "send" },
      { "item": "protection", "state": "follows the creation", "action": "create" }
    ],
    "generate": false,
    "checks": "none",
    "changed": [],
    "environment": null,
    "repositoryEnvironments": [],
    "ciVariables": null,
    "urls": null,
    "ciDeployComponents": null,
    "defaultBranch": null
  },
  "cost": { "fixed": false, "notes": "read-only plan" },
  "pending": []
}
```

Write each item of `outputs.items` on one line, as in the example.

- `mode` is always `plan`.
- `status`, in this order:
  - `failed`: the declaration is missing or invalid, `defaults.json` could not be read, or tools-check, `github_ci-setup`, the describe, the checkout, the pull request skill, a `go_setup`, `gcp_environment-describe`, `gcp-artifact-registry_registry-describe`, `gcp_deploy-describe` or `github_variables-set` ended `failed`, or `gcp_ci-identity-setup` ended `failed` without an `account`, or the login's read was refused by an IAP API just enabled (step 12) (otherwise `gcp_login-describe` never makes the plan fail: its failure is `waits for the login`).
  - `unchanged`: every action is `none` (the answer has the line `nothing to do`).
  - `would-create`: the repository is to create (`repository` is `missing` / `create`); a `create` on any other row is `would-update`.
  - `would-update`: some action is `create`, `update`, `send`, `propose`, `generate`, `repair`, `enable`, `configure`, `grant` or `set`.
  - `pending`: the only actions other than `none` are `merge it`, `fix the folder`, `fix by hand` or `prepare the login`.
- `outputs` has the same fourteen keys in every ending:
  - `project`: the declaration's `name`; `repository`: `<repo.owner>/<repo.name>`; `visibility`: the declared `repo.visibility`. All three `null` when the declaration is missing or invalid.
  - `exposes`: `true` when the plan would create a public repository (repository missing and `repo.visibility` `public`) or make one public (`visibility` `differs` and `repo.visibility` `public`); `false` otherwise, always `false` while the `declaration` action is `merge it`, `update`, `fix the folder` or `propose`, and always `false` on `failed`.
  - `items`: the five items in order, or the seven with components, followed by the four of the environment when the declaration has `environments`, and by `services` and `ci secrets` when it has both components and `environments`; `[]` on `failed`.
  - `generate`: `true` when some action is `generate`, `false` otherwise (always `false` without components and on `failed`).
  - `checks`: `ci` when step 15 ran and found `.github/workflows/ci.yml` in the repository's default branch (`inRepository` true), `none` otherwise; the protection row may still be `not checked`.
  - `changed`: the `outputs.changed` of the pull request skill of step 6, as it gave it (the tooling paths that changed in this folder, in its order); `[]` when step 6 was not invoked or failed. `project-apply` chooses the pull request's title from it.
  - `environment`: `null` without `environments` and on `failed`. Otherwise `{ "name": "dev", "projectId": <id> }`, on one line, where `<id>` is `outputs.projectId` of step 9 when it ran and the GCP project exists, and `null` otherwise.
  - `repositoryEnvironments`: the names of the environments the repository's copy of the declaration has (the keys of its `environments`, sorted), as step 5 noted them, on one line: `[]` when that copy has none, when the repository has no declaration, or when the repository does not exist (step 4: `exists` false); `null` when it is not known (the copy could not be read as JSON, or the plan ended `failed` before step 5 decided it). `project-apply` reads it to know whether a proposal adds an environment.
  - `ciVariables`: the four CI secrets, on one line: `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER` and `GCP_CI_ACCOUNT` as `outputs.ciVariables` of step 11 gave them, then `GCP_IMAGE_PATH` (`imagePath` of step 10); no `GCP_REGION`. Set only when step 11 gave its `ciVariables` (the CI identity exists as declared) and step 10 gave an `imagePath`; `null` otherwise, when step 11 was not run, and on `failed`. No other key of the block holds these values.
  - `urls`: `null` when step 13 did not run, and on `failed`. Otherwise, on one line, an object whose keys are the components whose service exists and has an address, in the order of the components, each with that address (`url` of step 13): `{ "api": "https://demo-api-<n>.us-central1.run.app", "web": "https://demo-web-<n>.us-central1.run.app" }`; `{}` when none does.
  - `ciDeployComponents`: the deploy list of step 15 (the components given to `github_ci-setup` in `deployComponents`), sorted, on one line: `[]` when it was invoked without `deploy` (the version 1 file), `null` when step 15 did not run. `defaultBranch`: the `defaultBranch` passed to `github_ci-setup` in step 15, `null` when step 15 did not run. `project-apply` passes exactly these (`deploy=dev deployComponents=<list> project=<name> region=<cloud.region>` when the list is not empty, and `defaultBranch`) to `github_ci-setup … mode=apply`, so the file it writes is the file the next plan expects.
- `pending` holds the items of every case below that applies, in the order of the items:
  - `declaration` action `merge it`: exactly one item `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge <url>, then run /aleogr:project-apply confirm=yes" }`, with the `number` and `url` of `openPullRequest`.
  - `declaration` action `fix the folder`: exactly one item, the `this folder needs attention` item of the skill that reported it, as it gave it (`item`, `reason` `manual`, `how`): the checkout's when its state is `needs-attention`, otherwise the pull request skill's.
  - `components` action `fix the folder`: the `pending` items of the `go_setup` runs that ended `pending`, as they gave them, in the order of the components.
  - `registry` action `fix by hand`: one item. For `in another region`, `{ "item": "registry", "reason": "manual", "how": "the image repository <name> exists in <otherRegions, joined by , > and not in the declared region <cloud.region>: delete or move it by hand, then run /aleogr:project-plan again" }`. For `not a Docker repository`, `{ "item": "registry", "reason": "manual", "how": "the repository <name> in <cloud.region> is not a Docker repository (its format is <format>) and a format never changes: remove it by hand, then run /aleogr:project-plan again" }`.
  - `ci identity` action `fix by hand`: one item `{ "item": "ci identity", "reason": "manual", "how": "<the sentence of gcp_ci-identity-setup: the cause and what the owner does>, then run /aleogr:project-plan again" }`.
  - `services` action `prepare the login`: one item `{ "item": "login", "reason": "manual", "how": "prepare the login of the organization: /aleogr:platform-plan shows what it makes and what it costs; then run /aleogr:project-plan again" }`.
  - `failed`: only one item `{ "item": "<what failed>", "reason": "manual", "how": "<fix>" }`: for a missing declaration `{ "item": "declaration", "reason": "manual", "how": "declare the project first with /aleogr:project-declare" }`; for an invalid one, `item` `declaration` and `how` the problem to fix in `.aleogr/project.json`; for `defaults.json`, `item` `defaults` and the problem; for tools-check, `item` `gh` and its `fix`, or, for the check of `gcloud`, `item` `gcloud` and its `fix`; for the describe, the checkout or the pull request skill, `item` `repository` or `declaration` and the cause it gave; for `github_ci-setup`, `item` `ci`, and for a `go_setup`, `item` the component's `name`, with the cause it gave; for `gcp_environment-describe`, `item` `environment dev`, for `gcp-artifact-registry_registry-describe`, `item` `registry`, for `gcp_ci-identity-setup`, `item` `ci identity`, for `gcp_deploy-describe`, `item` `services`, and for `github_variables-set`, `item` `ci secrets`, with the cause it gave; for the login's read refused by an IAP API just enabled (step 12), `{ "item": "services", "reason": "manual", "how": "the IAP API of the GCP project of dev was just enabled: wait a minute, then run /aleogr:project-plan again" }`.
  - None of these: `[]`.
- `resources` is `[{ "type": "repository", "id": "<repo.owner>/<repo.name>", "name": "<repo.name>" }]` when `outputs.exists` of the describe is true, `[]` otherwise.
- `cost` is always `{ "fixed": false, "notes": "read-only plan" }`. The block never holds the signed-in login.
