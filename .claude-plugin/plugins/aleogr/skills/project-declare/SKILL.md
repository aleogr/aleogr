---
description: aleogr project declare. Use to write or edit the project's declaration, `.aleogr/project.json` in the current folder (project name, GitHub repository, visibility, description, topics, settings, components), pre-filled from the owner's defaults. It only writes that file: it runs no command and changes nothing on GitHub.
---

# project-declare

Writes or edits the declaration of the project, `.aleogr/project.json` in the folder the skill runs in. A new declaration takes what the arguments do not give from the owner's defaults in `${CLAUDE_PLUGIN_ROOT}/defaults.json`; an existing one keeps everything the arguments do not change. The skill shows the resulting file and writes it in the canonical form. It runs no command and invokes no skill: nothing changes on GitHub or anywhere else (`project-plan` and `project-apply` do that from the file).

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces is written in quotes (`description="Status pages, per tenant"`).

| Argument | Key in the file | Meaning |
|---|---|---|
| `name=<name>` | `name` | The project name. Required for a new declaration. |
| `owner=<owner>` | `repo.owner` | The user or organization that owns the repository. Required for a new declaration (there is no default owner). |
| `repoName=<name>` | `repo.name` | The repository name. Default for a new declaration: the project name. |
| `visibility=<public\|private>` | `repo.visibility` | Default for a new declaration: `repo.visibility` of the defaults. |
| `description=<text>` | `repo.description` | Description of the repository. Required for a new declaration. |
| `topics=<t1>,<t2>` | `repo.topics` | Extra topics, comma-separated. `topics=` with an empty value means none. Default for a new declaration: none. Never the derived topic `aleogr-<name>`. |
| `mergeCommit=<true\|false>` | `repo.settings.mergeCommit` | Default for a new declaration: the same key of `repo.settings` in the defaults. |
| `squash=<true\|false>` | `repo.settings.squash` | Same. |
| `rebase=<true\|false>` | `repo.settings.rebase` | Same. |
| `deleteBranchOnMerge=<true\|false>` | `repo.settings.deleteBranchOnMerge` | Same. |
| `issues=<true\|false>` | `repo.settings.issues` | Same. |
| `wiki=<true\|false>` | `repo.settings.wiki` | Same. |
| `projects=<true\|false>` | `repo.settings.projects` | Same. |
| `notes=<text>` | `notes` | Optional free text. `notes=` with an empty value removes the key. Default for a new declaration: no `notes` key. |
| `component=<name>` | `components` | The component this run adds or changes: one per call. A component not in the declaration is added; an existing one is changed. |
| `stack=<go>` | `stack` of the component | Required when the component is new. For an existing component, when given, it equals the component's `stack`. |
| `path=<folder>` | `path` of the component | Default for a new component: its name. For an existing component, when given, it equals the component's `path`. |
| `version=<major.minor>` | `version` of the component | Default for a new component: `stacks.<stack>.version` of the defaults. For an existing component, the new version. |

`stack`, `path` and `version` describe the component named by `component`: given without `component`, the run fails. Removing a component is not done by this skill.

A missing required argument is never asked for: the run ends with `status` `failed`, one sentence naming every missing argument, and nothing written.

## The declaration's rules

The declaration of a project is the file `.aleogr/project.json` in the project's folder. It is a JSON object, version 1, described by the schema `https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json`. A file is a valid declaration only when it is valid JSON and every rule below holds; a file that breaks any of them is not a valid declaration.

- No object in the file has a key other than the ones listed here (no unknown keys, at any level).
- The top level has `version`, `name` and `repo` (required), and may have `$schema`, `components` and `notes`.
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
- `notes`, when present, is a string of free text.

The canonical form of the file, the form in which it is written:

- Two-space indentation, one key per line, and a final newline.
- Keys in this order: `$schema`, `version`, `name`, `repo`, `components`, `notes`; inside `repo`: `provider`, `owner`, `name`, `visibility`, `description`, `topics`, `settings`; inside `settings`: `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`; inside each component: `name`, `stack`, `path`, `version`.
- `$schema` is always present, with the value `https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json`.
- `repo.topics` is always present, on one line, sorted: `"topics": []` or `"topics": ["docs", "sample"]`.
- `components` is present only when it has at least one component. The components are sorted by `name`, each on one line: `{ "name": "web", "stack": "go", "path": "web", "version": "1.27" }`.
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

Two declarations are equal when they hold the same values: the order of keys, the spacing, line endings and the order of `repo.topics` and the order of `components` do not matter, an absent `repo.topics` equals `[]` and an absent `components` equals `[]`.

## Steps

Use only the Read tool and the Write tool. Run no shell command at all (no `ls`, `cat`, `mkdir`, `gh`, `git`: the Write tool creates the `.aleogr` folder) and invoke no skill. On `failed`, write nothing: the file stays as it was, or absent.

1. Read `${CLAUDE_PLUGIN_ROOT}/defaults.json` and take its block `repo` (`provider`, `visibility`, `settings`) and its block `stacks` (the default `version` of each stack). If `repo.provider` is not `github`: `failed`, only GitHub is implemented.
2. Read `.aleogr/project.json` in the current folder.
   - It does not exist: this is a new declaration. Go to step 3.
   - It exists: check it against every rule of "The declaration's rules" (the canonical form is not a rule: a valid file in another layout is accepted). If it is not valid JSON or breaks a rule: `failed`, one sentence saying which rule the file breaks (for example, that it is not valid JSON), and the file untouched. Otherwise go to step 3.
3. Check the arguments. Each failure is `failed`, with one sentence per problem, and nothing written:
   - Every argument is one of the table. An unknown argument fails, and so does an argument given twice.
   - New declaration: `name`, `owner` and `description` are all given; the sentence names every one that is missing.
   - Each given value follows the rule of its key in "The declaration's rules": `name` (including the reserved names), `owner`, `repoName`, `visibility`, `description`. Each of the seven settings is exactly `true` or `false`.
   - `topics` (when not empty) is split on `,`; each item follows the topic rule (no empty item, no capitals, no spaces); a topic repeated counts once. A topic equal to `aleogr-<name>`, where `<name>` is the project name (the argument for a new declaration, the file's `name` otherwise), fails: that topic is derived and never written.
   - `stack`, `path` or `version` given without `component`: `failed`, one sentence naming them, "they describe a component: give `component=<name>`".
   - `component`, `stack`, `path` and `version`, when given, follow the rules of a component's `name`, `stack`, `path` and `version` in "The declaration's rules" (`version=1.27.4` fails). A `version` of the right form but earlier than `1.22` for the stack `go` (the `stack` argument, or the existing component's `stack`) fails with the sentence "`version=<value>` is too old: a Go component needs Go 1.22 or later." (with the value given). `component=` with `changes`, `ci`, `true`, `false`, `null`, `yes`, `no`, `on` or `off` fails with the sentence "`component=<value>` is a reserved name: `changes` and `ci` are jobs of the project's CI file, and YAML does not read `true`, `false`, `null`, `yes`, `no`, `on` and `off` as names." A `path` that breaks its rule fails with the sentence "`path=<value>` cannot hold a component:" followed by the part of the rule it breaks (for `path=.github/web`: a part starts with `.`, so it is under `.github`).
   - The component is new (the declaration has no component with that `name`, or the declaration is new): `stack` is given, otherwise `failed`, and the sentence naming missing arguments names `stack` too. Its `path` (the argument, or the name) is not the `path` of another component of the declaration, otherwise `failed` with the sentence "`path=<value>` is the folder of the component `<other>`: no two components share a folder." It is not inside another component's `path`, and no other component's `path` is inside it (`web/api` next to `web`, or `web` next to `web/api`), otherwise `failed` with the sentence "`path=<value>` and the folder of the component `<other>` are one inside the other: a component's folder is never inside another component's folder."
   - The component exists: `stack`, when given, equals its `stack`, and `path`, when given, equals its `path`. Any of them different: `failed`, "that is another component": a component never changes folder or stack; only its `version` changes. Write nothing.
   - Existing declaration: `name`, when given, equals the file's `name`; `owner`, when given, equals the file's `repo.owner`; `repoName`, when given, equals the file's `repo.name`. Any of them different: `failed`, "that is another project": a declaration is never renamed and never moved to another repository. Run nothing, write nothing.
4. Build the result.
   - New declaration: `name`, `repo.owner` and `repo.description` from the arguments; `repo.provider` from the defaults; `repo.name` from `repoName`, or the project name; `repo.visibility` from `visibility`, or the defaults; `repo.topics` from `topics`, or `[]`; each of the seven settings from its argument, or the defaults' `repo.settings`; `notes` from `notes`, or no key.
   - Existing declaration: start from the file and set only the keys whose argument was given.
   - `component`: a new component is `{ "name": <component>, "stack": <stack>, "path": <path, or the name>, "version": <version, or stacks.<stack>.version of the defaults> }`, added to `components`; for an existing component only `version` is set, when given. `components` is kept sorted by `name`. A run without `component` keeps the file's components unchanged and writes them in the canonical form (sorted by `name`; an empty list is dropped); a declaration without `components` gets none.
   - `topics=` replaces the whole list of extra topics (it does not add to the file's list); `topics=` with an empty value makes it `[]`.
   - The argument text `true` or `false` of a setting is written as the JSON boolean `true` or `false`, never as a string.
   - Check the result: at least one of `mergeCommit`, `squash` and `rebase` is `true`, otherwise `failed`, nothing written.
5. Compare and write.
   - New declaration: `created`. `outputs.changes` lists every key path written, in the canonical order: `$schema`, `version`, `name`, `repo.provider`, `repo.owner`, `repo.name`, `repo.visibility`, `repo.description`, `repo.topics`, `repo.settings.mergeCommit`, `repo.settings.squash`, `repo.settings.rebase`, `repo.settings.deleteBranchOnMerge`, `repo.settings.issues`, `repo.settings.wiki`, `repo.settings.projects`, `components.<name>` when a component is written, and `notes` when written.
   - Existing declaration: `outputs.changes` lists, in the canonical order, the key paths whose value in the result differs from the file's (equality as in "The declaration's rules": `repo.topics` compared as a set). A component added, or whose `version` changes, is `components.<name>`, between `repo.settings.projects` and `notes`. An empty list is `unchanged`: do not write, the file stays byte for byte as it was. Otherwise `updated`. Only values count: a valid file without `$schema`, without `repo.topics`, with `"components": []`, or in a non-canonical layout (other indentation, other key order) does not differ for that alone, so with no argument that changes a value the result is `unchanged` and the file is left as it is.
   - `created` or `updated`: write `.aleogr/project.json` with the Write tool, the whole file in the canonical form.

## Answer

On `created`, `updated` or `unchanged`: one sentence saying what happened and which keys changed (`outputs.changes`), then the declaration in a fenced `json` block, exactly as the file now holds it (for `unchanged`, the file as it is). Only when the file is created with `repo.visibility` `public`, or when this run changes `repo.visibility` to `public`, add: `The declaration only states the visibility: nothing is public until project-apply runs with confirmVisibility=public.`; in every other case (including an edit of another key of a declaration that is already `public`, and `unchanged`) do not write that sentence. On `failed`: the sentence(s) of the failed check, and no file.

Then the result block. The answer ends with exactly one block.

## Result block

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-declare",
  "mode": "apply",
  "status": "updated",
  "resources": [],
  "outputs": {
    "path": ".aleogr/project.json",
    "declaration": {
      "$schema": "https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json",
      "version": 1,
      "name": "demo",
      "repo": {
        "provider": "github",
        "owner": "example-org",
        "name": "demo",
        "visibility": "private",
        "description": "Demo project",
        "topics": ["sample", "status-page"],
        "settings": { "mergeCommit": true, "squash": true, "rebase": false, "deleteBranchOnMerge": true, "issues": true, "wiki": false, "projects": false }
      }
    },
    "changes": ["repo.topics"]
  },
  "cost": { "fixed": false, "notes": "writes a local file only" },
  "pending": []
}
```

- `status`: `created` (no file existed; it was written), `updated` (the file existed and some value changed; it was rewritten), `unchanged` (the file existed and no value changed; it was not written), `failed` (a check failed; nothing was written).
- `outputs.path` is always `.aleogr/project.json`.
- `outputs.declaration` is the whole declaration as the file holds it at the end of the run: the file written on `created` and `updated`, the file as it is on `unchanged`. On `failed` it is `null`.
- `outputs.changes` is the list of key paths described in step 5: every key written on `created`, the keys whose value changed on `updated`, `[]` on `unchanged` and on `failed`.
- `resources` is always empty and `pending` is always `[]`: the skill creates nothing outside the file and leaves nothing to confirm.
