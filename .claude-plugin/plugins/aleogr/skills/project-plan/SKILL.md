---
description: aleogr project plan. Use in a project's folder to see what the project's GitHub repository is missing or has different from the declaration `.aleogr/project.json` (the repository, its settings and topics, its visibility, the declaration in the repository, the branch protection, when components are declared, their Go starting points and the CI file, and, when environments are declared, the GCP environment dev: its project, its APIs, the image repository and the CI identity). Prints a table of items, state and action. Read-only; changes nothing.
---

# project-plan

Compares the project's declaration, `.aleogr/project.json` in the folder the skill runs in, with the real GitHub repository and prints a table: item, state, action. The plan only reads: it runs no `gh`, `git` or `gcloud` command itself, it invokes `aleogr:tools-check`, the read-only skills of `aleogr-repo-github` and, when components are declared, `github_ci-setup` and `aleogr-stack-go:go_setup` in `mode=plan`, and, when environments are declared, `aleogr:tools-check` for `gcloud`, `aleogr-cloud-gcp:gcp_environment-describe`, `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe` and `aleogr-cloud-gcp:gcp_ci-identity-setup` in `mode=plan`, and running it changes nothing anywhere. `project-apply` runs it first and acts on its items.

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

Show each skill invocation before making it. The skills below end with their own `aleogr-result` block: use those blocks only as input, never repeat them, and after each one go on with the next step: a skill's block is never the end of this answer, which always ends with the table and this skill's own block. Invoke only these skills, in this order, each at most once (`tools-check` once for `gh` and, with environments, once more for `gcloud` right after it, before any GitHub read; `go_setup` once per component), and run no command yourself (no `gh`, no `git`, no `gcloud`, no `ls`, no `cat`). Your answer ends with exactly one block, its own. Never print the account name (the account `gh` or `gcloud` is signed in with): not in the answer and not in the result block.

A declaration without components (`components` absent or `[]`) skips steps 3 and 8, invokes step 4 without `checks`, step 5 without `head` and step 6 with `paths=.aleogr/project.json`, and has the five items of "Items"; a `ci.yml` left in the repository after the last component is removed is not reported by this skill (removing a component is not built yet). Only a declaration with at least one component invokes `github_ci-setup` and `go_setup` and has seven items.

A declaration without `environments` skips the `gcloud` check of step 2 and steps 9 to 11, and has exactly the items above: for it this skill invokes no cloud skill, and not one `gcloud` command is run. Only a declaration with `environments` (its only environment is `dev`) has, after `protection`, the four items of "The environment's items": nine items without components, eleven with.

1. Read `.aleogr/project.json` in the current folder with the Read tool.
   - It does not exist: `failed`, with the sentence `There is no .aleogr/project.json in this folder: declare the project first with /aleogr:project-declare.` Invoke nothing.
   - It is not valid JSON, or breaks a rule of "The declaration's rules" (the canonical form is not a rule: a valid file in another layout is accepted): `failed`, one sentence naming the first problem found (for example, that it is not valid JSON, or the unknown key and where it is). Invoke nothing.
   - Otherwise take `name`, `repo.owner`, `repo.name`, `repo.visibility`, `repo.description`, `repo.topics` (absent means `[]`), `repo.settings` and `components` (absent means `[]`). The declared topics are `aleogr-<name>` plus `repo.topics`, without duplicates.
   - With at least one component, also read `${CLAUDE_PLUGIN_ROOT}/defaults.json` with the Read tool and take `ci.workflowsRepository`. It cannot be read, or has no such string: `failed`, one sentence saying so. Invoke nothing. Then, with the components sorted by `name`:
     - `<components>` is the entries `<name>:<path>:<stack>:<version>` of the components, joined by `,` (for the two components of the example, `api:services/api:go:1.27,web:web:go:1.27`).
     - The module of a component is `github.com/<repo.owner>/<repo.name>/<path>`.
     - The tooling paths are `.aleogr/project.json`, `.github/workflows/ci.yml` and, for each component, `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, in that order, joined by `,`.
   - With `environments`, also take `cloud.region`, and read `${CLAUDE_PLUGIN_ROOT}/defaults.json` with the Read tool (the same read as for components, made once) and take `project.services` (a list of API names) and `project.registry.keep` (a number). It cannot be read, or lacks either: `failed`, one sentence saying so. Invoke nothing.
2. Invoke `aleogr:tools-check command=gh`. Its `status` `failed`: stop with `failed`, carry its `fix` into `pending[].how`, and invoke nothing else.
   - With `environments`, and only then: right after it, before step 3 and before anything on GitHub is read, invoke `aleogr:tools-check` with no argument (it checks `gcloud`). Its block is input only: go on. Its `status` `failed` (`gcloud` missing or not signed in): stop with `failed`, carry its `fix` into `pending[].how`, and invoke nothing else: no row is read. Only then go to step 3 (or, without components, step 4).
3. Only with at least one component: invoke `aleogr-repo-github:github_ci-setup owner=<repo.owner> name=<repo.name> components=<components> workflows=<ci.workflowsRepository> mode=plan`. In `plan` it writes nothing; it reads the local `.github/workflows/ci.yml` and the repository's copy.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else.
   - Otherwise (any other status: `would-create`, `would-update` or `unchanged` are all input here) take `outputs.local` (`as-declared`, `missing` or `differs`) and `outputs.inRepository` (`true` when `ci.yml` is on the repository's default branch). Go to step 4.
4. Invoke `aleogr-repo-github:github_repo-describe owner=<repo.owner> name=<repo.name>`, with `checks=ci` added exactly when step 3 ran and its `inRepository` is `true` (the protection then is expected to require the check `ci`); otherwise with no `checks` argument.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else.
   - `outputs.exists` false: the repository is to create. Invoke nothing else: every other item follows the creation (see "Items"). Go to the answer.
   - `outputs.exists` true: take `visibility`, `description`, `topics`, `settings`, `protection.state` and `protection.matches`, and, with `environments`, `id`, `ownerId` and `defaultBranch`. Go to step 5.
5. Invoke `aleogr-repo-github:github_checkout-setup owner=<repo.owner> name=<repo.name> mode=plan`, with `head=check` added exactly when the declaration has at least one component. It reads the repository's copy of `.aleogr/project.json`, compares it with the local one and, when they differ, reads the folder. With `head=check` it also reads the folder when they are equal, and reports `behind` when the repository's head moved on from this folder's last commit: a merged pull request that added code or `ci.yml` without changing the declaration leaves this folder behind all the same.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else.
   - Otherwise take `outputs.state` (`equal`, `not-sent`, `differs`, `missing`, `behind` or `needs-attention`), `outputs.reason` and its `pending` items. Also note the environments of the repository's copy of the declaration (the output `repositoryEnvironments`), from what this step already read, with no other read: state `equal`, the names of the folder's `environments` (the two are equal); state `not-sent` or `missing` (the repository has no declaration), `[]`; any other state, the keys of `environments` of the repository's copy that this step read and showed (`gh api repos/<owner>/<name>/contents/.aleogr/project.json`), `[]` when that copy has no `environments`, and `null` when the copy could not be read as JSON. Go to step 6.
6. Invoke `aleogr-repo-github:github_pull-request-open owner=<repo.owner> name=<repo.name> paths=<paths> mode=plan`, where `<paths>` is `.aleogr/project.json` without components and the tooling paths with components. It reports the open tooling pull request, if any, whether the folder is fit for a proposal and which of the paths changed.
   - `status` `failed`: stop with `failed` and its cause.
   - Otherwise (any other status: `pending`, `would-create` or `unchanged` are all input here) take `outputs.openPullRequest` (`null`, or its `number` and `url`), `outputs.folder` (`ready`, `not-a-checkout`, `other-remote`, `other-branch` or `local-commits`), `outputs.changed` and its `pending` items. Go to step 7.
7. Decide the `declaration` item now, by the list under "Items". Without components: with `environments` and the action `none`, go to step 9; otherwise go to the answer. With components: its action `merge it`, `update`, `fix the folder` or `send`: invoke nothing else (the rows `components` and `ci` are not checked, nor the environment's) and go to the answer; its action `propose` or `none`: go to step 8.
8. For each component, sorted by `name`, invoke `aleogr-stack-go:go_setup component=<name> path=<path> version=<version> module=<module> mode=plan`. In `plan` it writes nothing; it reads the component's folder.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else.
   - Otherwise (any other status: `unchanged`, `would-create` or `pending` are all input here) take its `status` and its `pending` items, and go on with the next component. After the last one: with `environments` and the `declaration` action `none`, go to step 9; otherwise go to the answer.

Steps 9 to 11 run only with `environments`, and only when the `declaration` action is `none` (the declaration in the repository is this one).

Write nothing between the invocations of steps 9 to 11 and the table: no summary of a skill's run, no copy of its block.

9. Invoke `aleogr-cloud-gcp:gcp_environment-describe projectId=<projectId>` when the argument `projectId` was given, otherwise `aleogr-cloud-gcp:gcp_environment-describe project=<name> environment=dev`. It only reads. Read its block, then take the case below that applies.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else. Go to the Answer: your next output is the sentence of the failure; write nothing before it.
   - `outputs.exists` false, or `outputs.billingLinked` false: nothing inside the GCP project is read. Go to the Answer. Your next output is the table, starting with its header row; write nothing before it.
   - Otherwise take `projectId` and `enabledServices`. The APIs to enable are the names of `project.services` that are not in `enabledServices`. Some (no Artifact Registry or IAM read works before they are on): go to the Answer. Your next output is the table, starting with its header row; write nothing before it. None: write nothing and go straight to step 10.
10. Invoke `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe projectId=<projectId> project=<name> region=<cloud.region>`. It only reads. Read its block, then take the case below that applies.
   - `status` `failed`: stop with `failed` and its cause. Invoke nothing else. Go to the Answer: your next output is the sentence of the failure; write nothing before it.
   - Otherwise take `exists`, `otherRegions`, `format`, `cleanup` (`keep`, `deletesTheRest`, `dryRun`, `rules`) and `push`. Write nothing and go straight to step 11.
11. Invoke `aleogr-cloud-gcp:gcp_ci-identity-setup projectId=<projectId> project=<name> repository=<repo.owner>/<repo.name> repositoryId=<id> ownerId=<ownerId> branch=<defaultBranch> mode=plan`, with `id`, `ownerId` and `defaultBranch` of step 4. In `plan` it only reads. Read its block, then go to the Answer.
   - `status` `failed` with `outputs.account` `null` (it refused an argument, or could not read the GCP project): stop with `failed` and its cause. Invoke nothing else. Your next output is the sentence of the failure; write nothing before it.
   - `status` `failed` with `outputs.account` set (a pool or provider deleted or disabled, a pool that holds another provider, or a part it could not read): this is not a failure of the plan but something the owner fixes by hand. Keep its sentence (the cause and what the owner does) for the `ci identity` item. Your next output is the table, starting with its header row; write nothing before it.
   - Otherwise (`would-create`, `would-update` or `unchanged` are all input here) take its `status`, `outputs.account` and `outputs.ciVariables`. Your next output is the table, starting with its header row; write nothing before it.

## Items

Without components, always these five items, in this order: `repository`, `settings`, `visibility`, `declaration`, `protection`. With at least one component, always these seven, in this order: `repository`, `settings`, `visibility`, `declaration`, `components`, `ci`, `protection`. Each is `{ "item": "<item>", "state": "<state>", "action": "<action>" }`, with the state and action texts exactly as written here.

| Item | State → action |
|---|---|
| `repository` | `exists` false: `missing` → `create`. `exists` true: `exists` → `none`. |
| `settings` | Compare `repo.description` with `outputs.description`, the declared topics with `outputs.topics` as sets (order ignored), and each of the seven `repo.settings` with the same key of `outputs.settings`. All equal: `as declared` → `none`. Otherwise `differs: <names>` → `update`, where `<names>` are the names that differ, comma-separated, in this order: `description`, `topics`, `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects` (for example `differs: topics, rebase`). |
| `visibility` | `outputs.visibility` equals `repo.visibility`: `as declared` → `none`. Otherwise (including `internal`): `differs` → `update`, and the note `visibility: needs confirmVisibility=<repo.visibility>` under the table. |
| `declaration` | From the checkout's `outputs.state` and the pull request skill's `outputs.openPullRequest`, `outputs.folder` and `outputs.changed`: the first case of the list under the table that applies. |
| `components` | Only with components, from the `status` of each `go_setup` of step 8. Some `pending`: `needs attention: <names>` → `fix the folder`, with their `pending` items. Otherwise some `would-create` (no `go.mod` in the component's folder): `to generate: <names>` → `generate`. Otherwise (every one `unchanged`): `as declared` → `none`. `<names>` are the names of the components with that status, sorted, separated by `, ` (for example `to generate: api, web`). |
| `ci` | Only with components, from `outputs.local` of step 3: `as-declared` → `as declared` / `none`; `missing` → `missing` / `generate`; `differs` → `differs` / `generate`. |
| `protection` | From `protection.state`: `protected` with `matches` true → `protected` / `none`, or `protected, requires ci` / `none` when step 4 had `checks=ci`; `protected` with `matches` false → `differs` / `update`; `unprotected` → `unprotected` / `create`; `unavailable` → `not available on this plan` / `none`, and the notice `main is held by the working rule, not by GitHub` under the table (when `visibility` is `differs` and `repo.visibility` is `public`, the notice adds `protection is checked again once the repository is public`). With `checks=ci` (`ci.yml` is on the default branch) the ruleset is expected to require the check `ci`, so one without it `differs`; without `checks`, one that requires it `differs` too. |

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

With the `declaration` action `propose` or `none`, `components` and `ci` are computed from the local declaration and this folder, as the table says: writing files in the folder and proposing them changes nothing on GitHub, so they do not wait for a merge.

`merge it` and `fix the folder` are the owner's to do: `project-apply` stops on them.

## The environment's items

Only with `environments`: four more items after `protection`, in this order: `environment dev`, `apis`, `registry`, `ci identity`, each `{ "item": "<item>", "state": "<state>", "action": "<action>" }` with the texts exactly as written here.

| Item | State → action |
|---|---|
| `environment dev` | From step 9: `exists` false: `missing` → `create`. `exists` true and `billingLinked` false: `billing not linked` → `repair`. Otherwise `exists` → `none`. |
| `apis` | From the APIs to enable of step 9: none: `enabled` → `none`; otherwise `to enable: <n>` → `enable`, where `<n>` is how many (for example `to enable: 1`). |
| `registry` | From step 10: `exists` false and `otherRegions` empty: `missing` → `create`. `exists` false and `otherRegions` not empty (the repository exists only in another region): `in another region` → `fix by hand`. `exists` true and `format` is not `DOCKER` (a repository of another format holds no images, and a format never changes): `not a Docker repository` → `fix by hand`, whatever its cleanup. `exists` true and `cleanup.keep` is not `project.registry.keep`, or `cleanup.deletesTheRest` is false, or `cleanup.dryRun` is true, or `cleanup.rules` is not `2` (the policy holds a rule the tooling does not own, such as a third rule added by hand): `cleanup differs` → `configure`. Otherwise `as declared` → `none`. |
| `ci identity` | From step 11, and the `registry` item. `failed` with an `account` (step 11 says when): `needs attention` → `fix by hand`. Otherwise, by `registry`: **`as declared` or `cleanup differs`** (the repository is in the declared region): `would-create`: `missing` → `create`; `would-update`: `differs` → `update`; with either, `project-apply` also grants the account push after creating or updating it, when `push` does not hold `serviceAccount:<account>` (a new account is never in it). `unchanged`: `push` holds `serviceAccount:<account>`: `as declared` → `none`; otherwise `cannot push` → `grant` (this skill decides it). **`missing`**: `would-create`: `missing` → `create`; `would-update`: `differs` → `update`; with either, `project-apply` also grants the account push once the repository exists. `unchanged`: `cannot push` → `grant`. **`in another region`** or **`not a Docker repository`**: the identity's own state, and no grant (the `registry` row carries the block): `would-create`: `missing` → `create`; `would-update`: `differs` → `update`; `unchanged`: `as declared` → `none`. |

These cases replace the rows above, the first that applies:

- **Repository missing** (step 4, `exists` false): the four items are `follows the creation` / `none`.
- **Declaration not in the repository yet** (`declaration` action other than `none`): the four items are `not checked until the change is merged` / `none`, and steps 9 to 11 are not run.
- **Environment not ready** (`environment dev` is `missing` or `billing not linked`): `apis`, `registry` and `ci identity` are `follows the environment` / `none`: nothing can be read inside a project that does not exist or has no billing.
- **APIs to enable** (`apis` is `to enable: <n>`): `registry` and `ci identity` are `follows the apis` / `none`: their reads are refused until the APIs are on.

`fix by hand` is the owner's to do as well: `project-apply` never makes it, and it is never `nothing to do`.

## Answer

Print the table (item, state, action). Under the table, these lines when they apply, worded as here:

- `visibility` has action `update`: `visibility: needs confirmVisibility=<repo.visibility>`.
- `exposes` is true: `This plan makes the repository public: project-apply runs it only with confirmVisibility=public.`
- `protection` is `not available on this plan`: `main is held by the working rule, not by GitHub.` When `visibility` is `differs` and `repo.visibility` is `public`, the line is `main is held by the working rule, not by GitHub; protection is checked again once the repository is public.`
- `declaration` has action `merge it` or `fix the folder`: the `how` of the `pending` item (below), and that `project-apply` stops until it is done.
- `components` has action `fix the folder`: the `how` of each of its `pending` items, and that `project-apply` stops until it is done.
- `components` or `ci` has action `generate`: that `project-apply` writes the files in this folder and proposes them, with the declaration, in one pull request.
- `registry` or `ci identity` has action `fix by hand`: the `how` of its `pending` item, and that the owner does it by hand: `project-apply` does not.

The words `requires ci` appear only as the `protection` state `protected, requires ci`, never elsewhere in the answer.

Then one line: `nothing to do` when every action is `none`. Otherwise how many items have an action other than `none` and that `project-apply` makes them (for `merge it`, `fix the folder` or `fix by hand`, that it is the owner's to do). Never write the words `nothing to do` when an action is not `none`. On `failed`: the sentence of the failed step instead of the table. Then the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill's lines and its block are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). Its answer never contains this block and never ends with it.

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
    "ciVariables": null
  },
  "cost": { "fixed": false, "notes": "read-only plan" },
  "pending": []
}
```

Write each item of `outputs.items` on one line, as in the example.

- `mode` is always `plan`.
- `status`, in this order:
  - `failed`: the declaration is missing or invalid, `defaults.json` could not be read, or tools-check, `github_ci-setup`, the describe, the checkout, the pull request skill, a `go_setup`, `gcp_environment-describe` or `gcp-artifact-registry_registry-describe` ended `failed`, or `gcp_ci-identity-setup` ended `failed` without an `account`.
  - `unchanged`: every action is `none` (the answer has the line `nothing to do`).
  - `would-create`: the repository is to create.
  - `would-update`: some action is `create`, `update`, `send`, `propose`, `generate`, `repair`, `enable`, `configure` or `grant`.
  - `pending`: the only actions other than `none` are `merge it`, `fix the folder` or `fix by hand`.
- `outputs` has the same eleven keys in every ending:
  - `project`: the declaration's `name`; `repository`: `<repo.owner>/<repo.name>`; `visibility`: the declared `repo.visibility`. All three `null` when the declaration is missing or invalid.
  - `exposes`: `true` when the plan would create a public repository (repository missing and `repo.visibility` `public`) or make one public (`visibility` `differs` and `repo.visibility` `public`); `false` otherwise, always `false` while the `declaration` action is `merge it`, `update`, `fix the folder` or `propose`, and always `false` on `failed`.
  - `items`: the five items in order, or the seven with components, followed by the four of the environment when the declaration has `environments`; `[]` on `failed`.
  - `generate`: `true` when some action is `generate`, `false` otherwise (always `false` without components and on `failed`).
  - `checks`: `ci` when `.github/workflows/ci.yml` is in the repository's default branch (step 4 used `checks=ci`), `none` otherwise; the protection row may still be `not checked`.
  - `changed`: the `outputs.changed` of the pull request skill of step 6, as it gave it (the tooling paths that changed in this folder, in its order); `[]` when step 6 was not invoked or failed. `project-apply` chooses the pull request's title from it.
  - `environment`: `null` without `environments` and on `failed`. Otherwise `{ "name": "dev", "projectId": <id> }`, on one line, where `<id>` is `outputs.projectId` of step 9 when it ran and the GCP project exists, and `null` otherwise.
  - `repositoryEnvironments`: the names of the environments the repository's copy of the declaration has (the keys of its `environments`, sorted), as step 5 noted them, on one line: `[]` when that copy has none, when the repository has no declaration, or when the repository does not exist (step 4: `exists` false); `null` when it is not known (the copy could not be read as JSON, or the plan ended `failed` before step 5 decided it). `project-apply` reads it to know whether a proposal adds an environment.
  - `ciVariables`: `outputs.ciVariables` of step 11 as it gave it (set only when the CI identity exists as declared), on one line; `null` when step 11 was not run or ended `failed`.
- `pending` holds the items of every case below that applies, in the order of the items:
  - `declaration` action `merge it`: exactly one item `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge <url>, then run /aleogr:project-apply confirm=yes" }`, with the `number` and `url` of `openPullRequest`.
  - `declaration` action `fix the folder`: exactly one item, the `this folder needs attention` item of the skill that reported it, as it gave it (`item`, `reason` `manual`, `how`): the checkout's when its state is `needs-attention`, otherwise the pull request skill's.
  - `components` action `fix the folder`: the `pending` items of the `go_setup` runs that ended `pending`, as they gave them, in the order of the components.
  - `registry` action `fix by hand`: one item. For `in another region`, `{ "item": "registry", "reason": "manual", "how": "the image repository <name> exists in <otherRegions, joined by , > and not in the declared region <cloud.region>: delete or move it by hand, then run /aleogr:project-plan again" }`. For `not a Docker repository`, `{ "item": "registry", "reason": "manual", "how": "the repository <name> in <cloud.region> is not a Docker repository (its format is <format>) and a format never changes: remove it by hand, then run /aleogr:project-plan again" }`.
  - `ci identity` action `fix by hand`: one item `{ "item": "ci identity", "reason": "manual", "how": "<the sentence of gcp_ci-identity-setup: the cause and what the owner does>, then run /aleogr:project-plan again" }`.
  - `failed`: only one item `{ "item": "<what failed>", "reason": "manual", "how": "<fix>" }`: for a missing declaration `{ "item": "declaration", "reason": "manual", "how": "declare the project first with /aleogr:project-declare" }`; for an invalid one, `item` `declaration` and `how` the problem to fix in `.aleogr/project.json`; for `defaults.json`, `item` `defaults` and the problem; for tools-check, `item` `gh` and its `fix`, or, for the check of `gcloud`, `item` `gcloud` and its `fix`; for the describe, the checkout or the pull request skill, `item` `repository` or `declaration` and the cause it gave; for `github_ci-setup`, `item` `ci`, and for a `go_setup`, `item` the component's `name`, with the cause it gave; for `gcp_environment-describe`, `item` `environment dev`, for `gcp-artifact-registry_registry-describe`, `item` `registry`, and for `gcp_ci-identity-setup`, `item` `ci identity`, with the cause it gave.
  - None of these: `[]`.
- `resources` is `[{ "type": "repository", "id": "<repo.owner>/<repo.name>", "name": "<repo.name>" }]` when `outputs.exists` of the describe is true, `[]` otherwise.
- `cost` is always `{ "fixed": false, "notes": "read-only plan" }`. The block never holds the account name.
